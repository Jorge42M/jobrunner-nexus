# Procesos, señales y códigos de salida en Nexus

Cada concepto indica **dónde está en el código** y **cómo demostrarlo**.

## 1. Procesos

Un **proceso** es un programa en ejecución. Cada uno tiene un número único, el
**PID**, y un proceso padre (**PPID**).

### ¿Cómo crea Nexus un proceso?

`subprocess.Popen` (en `src/nexus/runner.py`, método `_launch`) hace dos
llamadas al sistema:

1. **`fork()`**: el servicio se duplica. Ahora hay dos procesos casi idénticos:
   el padre (el servicio) y el hijo.
2. **`exec()`** (en el hijo): el hijo se reemplaza por el programa pedido
   (`sleep`, `ls`, ...). Si `exec` falla porque el programa no existe, Python
   lanza `FileNotFoundError` en el padre y Nexus marca el trabajo `FAILED`
   con código `127`.

Antes del `exec`, se preparan los **descriptores de archivo** del hijo:

| Descriptor | Nombre | En Nexus apunta a |
| :--------: | :----- | :---------------- |
| 0 | stdin (entrada) | `/dev/null` (el trabajo no lee del teclado) |
| 1 | stdout (salida) | `nexus-data/logs/<id>.out` |
| 2 | stderr (errores) | `nexus-data/logs/<id>.err` |

`close_fds=True` cierra todo lo demás (por ejemplo, el socket del servicio)
para que el hijo no herede cosas que no le corresponden.

**Demostración:**

```bash
./nexus submit sleep 60          # supongamos ID 1
./nexus status 1                 # mira el pid, por ejemplo 4321
ps -o pid,ppid,pgid,stat,cmd -p 4321
```

Verás que el `PPID` del `sleep` es el PID del servicio y que su `PGID`
(grupo) es igual a su propio PID (por `start_new_session=True`).

### Procesos zombie

Cuando un hijo termina, el kernel guarda su código de salida hasta que el
padre lo lea con `waitpid()`. Mientras tanto el hijo es un **zombie**
(`STAT = Z` en `ps`). Nexus llama `proc.poll()` cada 0.1 s, que hace
`waitpid` sin bloquear: así recoge el código y el zombie desaparece.

### Procesos huérfanos

Si el padre muere antes que el hijo, el hijo queda **huérfano** y lo adopta
`init` (PID 1). Para evitarlo, al apagarse Nexus termina todos sus trabajos
(`JobRunner.stop`).

## 2. Señales

Una **señal** es un aviso asíncrono que el kernel entrega a un proceso.

| Señal | Número | Quién la usa en Nexus | ¿Se puede atrapar o ignorar? |
| :---- | :----: | :-------------------- | :--------------------------: |
| `SIGINT`  | 2  | `Ctrl+C` en la terminal del servicio → apagado ordenado | Sí |
| `SIGTERM` | 15 | `cancel` la envía al trabajo; `kill PID` al servicio → apagado ordenado | Sí |
| `SIGKILL` | 9  | `cancel` si el trabajo ignoró `SIGTERM` por `--kill-grace` segundos | **No** |

- **En el servicio** (`src/nexus/server.py`, función `serve`): se instalan
  manejadores con `signal.signal(SIGTERM/SIGINT, ...)`. El manejador solo
  levanta una bandera (`threading.Event`); el hilo principal hace la limpieza.
  Esto es importante porque un manejador de señales debe hacer el mínimo
  trabajo posible.
- **En los trabajos** (`JobRunner.cancel`): `os.killpg(pgid, SIGTERM)` envía
  la señal a **todo el grupo de procesos**, no solo al PID. Si el trabajo es
  `sh -c "sleep 100"`, también muere el `sleep`.

**Demostración:**

```bash
./nexus submit sh -c 'trap "" TERM; sleep 100'   # ignora SIGTERM
./nexus cancel 2
./nexus wait 2        # -> CANCELED, código -9 (tuvo que usarse SIGKILL)
```

## 3. Códigos de salida

Al terminar, un proceso devuelve un número de 0 a 255:

| Código | Significado convencional |
| :----: | :----------------------- |
| `0` | Éxito |
| `1`, `2`, ... | Error definido por el programa (`ls` de algo inexistente → `2`) |
| `126` | Se encontró pero no es ejecutable |
| `127` | Comando no encontrado |

> **Detalle de WSL:** el `PATH` de WSL incluye carpetas de Windows
> (`/mnt/c/...`). Si se deja que `exec()` busque el programa, al toparse con
> una de esas carpetas puede responder "Permission denied" y un comando
> inexistente se vería como `126`. Por eso Nexus busca el programa primero
> con `shutil.which` (`runner.find_program`): si no hay ningún ejecutable con
> ese nombre da `127`, y solo da `126` cuando la ruta existe pero no tiene
> permiso de ejecución.

Si el proceso **murió por una señal**, no hay código "normal". Python lo
representa como **número negativo**: `-15` = murió por `SIGTERM`, `-9` = por
`SIGKILL`. (En la terminal `bash` el mismo caso se ve como `128 + N`:
`143` y `137`.)

Nexus guarda ese valor en `exit_code` y decide el estado:

```
cancel pedido      → CANCELED
código == 0        → SUCCEEDED
cualquier otro     → FAILED
```

**Ver el código de salida de cualquier comando en la terminal:**

```bash
ls /no/existe
echo $?        # imprime 2
```

El propio cliente `./nexus` también devuelve códigos: `0` ok, `1` error del
servicio (ej. ID inexistente), `2` el servicio no está corriendo.
