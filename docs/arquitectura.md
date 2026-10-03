# Arquitectura inicial (Hito 1)

Issue: #6 · Relacionado: #4

## 1. Vista general

Nexus tiene dos programas que se comunican por un **socket Unix** (un archivo
especial que sirve para que dos procesos de la misma máquina se hablen):

```
 Terminal 2                          Terminal 1
┌──────────────┐   línea JSON    ┌──────────────────────────────────────────┐
│ CLIENTE      │ ─────────────►  │ SERVICIO  (./nexus serve)                │
│ ./nexus ...  │                 │                                          │
│ (cli.py)     │ ◄─────────────  │  server.py  ──►  runner.py  ──► store.py │
└──────────────┘   línea JSON    │  (socket,       (procesos,     (SQLite)  │
                nexus-data/      │   señales)       cola)            │      │
                nexus.sock       └──────────────────────┬──────────────┼──────┘
                                                        │ fork + exec  │
                                                        ▼              ▼
                                               ┌──────────────┐  nexus-data/nexus.db
                                               │ PROCESO HIJO │  nexus-data/logs/<id>.out
                                               │ (el trabajo) │  nexus-data/logs/<id>.err
                                               └──────────────┘
```

## 2. Módulos

| Módulo        | Responsabilidad | Conceptos de sistemas |
| :------------ | :-------------- | :-------------------- |
| `cli.py`      | Lee los argumentos del usuario, envía la petición y muestra la respuesta. | Códigos de salida del cliente (0, 1, 2). |
| `protocol.py` | Formato de mensajes: una línea JSON por petición/respuesta. | Sockets `AF_UNIX`, delimitación de mensajes. |
| `server.py`   | Acepta conexiones (un hilo por conexión), valida, despacha, responde. Maneja `SIGTERM`/`SIGINT`. | Señales, apagado ordenado, permisos `0600` del socket. |
| `runner.py`   | Cola FIFO, límite de concurrencia, lanza procesos, los recoge, cancela. | `fork/exec`, grupos de procesos, `killpg`, `waitpid`, descriptores de archivo. |
| `store.py`    | Tablas `jobs` y `events`; cada cambio de estado es una transacción. | ACID, bloqueo con `threading.Lock`. |
| `states.py`   | Define los 5 estados y las transiciones permitidas. | Máquina de estados. |

## 3. Recorrido de una solicitud (de cliente a fin del proceso)

Ejemplo: `./nexus submit sleep 5`

1. **Cliente.** `cli.py` arma el mensaje `{"op":"submit","command":"sleep 5"}`,
   se conecta a `nexus-data/nexus.sock` y lo envía terminado en `\n`.
2. **Servicio recibe.** El servidor crea un hilo para esa conexión, lee la
   línea y la convierte a diccionario (`protocol.decode`). Si el JSON está mal,
   responde `{"ok":false,...}` y sigue vivo.
3. **Validación.** `runner.submit` usa `shlex.split` para separar el comando en
   argumentos (`["sleep","5"]`). Vacío o comillas sin cerrar → error.
4. **Persistencia.** `store.create_job` inserta la fila en SQLite con estado
   `QUEUED` y registra el evento `SUBMITTED`. SQLite asigna el **ID único**
   (`AUTOINCREMENT`).
5. **Respuesta.** El cliente recibe el ID y termina con código 0.
6. **Planificación.** El hilo planificador (cada 0.1 s) ve que hay lugar
   (`max_concurrent`) y toma el trabajo más antiguo en `QUEUED`.
7. **Creación del proceso.** `subprocess.Popen` hace `fork()` (copia el
   proceso) y en el hijo `exec()` (lo reemplaza por `sleep`). Antes, abre
   `logs/<id>.out` y `logs/<id>.err` y los conecta a los descriptores 1
   (stdout) y 2 (stderr) del hijo. `start_new_session=True` hace que el hijo
   sea líder de un **grupo de procesos** nuevo.
8. **RUNNING.** Se guarda el PID y el estado pasa a `RUNNING` (evento
   `QUEUED->RUNNING`).
9. **Terminación.** Cuando `sleep` termina, el kernel deja el proceso como
   *zombie* hasta que el padre lea su código. El planificador llama
   `proc.poll()` (que hace `waitpid`), obtiene el código y lo libera.
10. **Estado final.** Código 0 → `SUCCEEDED`; otro código o señal → `FAILED`;
    si se había pedido cancelar → `CANCELED`. Se guardan `exit_code` y
    `finished_at`.
11. **Consulta.** `./nexus status 1` repite los pasos 1-2 con `op: status` y
    muestra estado, PID, código y bitácora.

### Cancelación

`./nexus cancel ID`:

- Si está `QUEUED`: pasa directo a `CANCELED` (nunca se crea el proceso).
- Si está `RUNNING`: se envía `SIGTERM` a **todo el grupo** del proceso
  (`os.killpg`). Si en `--kill-grace` segundos no terminó, se envía `SIGKILL`
  (que no se puede ignorar). El estado pasa a `CANCELED` cuando el proceso
  realmente termina.

### Apagado del servicio

`Ctrl+C` (`SIGINT`) o `kill PID` (`SIGTERM`) → el manejador de señales solo
levanta una bandera; el hilo principal entonces: deja de aceptar conexiones,
envía `SIGTERM`/`SIGKILL` a los trabajos vivos, los marca `CANCELED`, cierra
SQLite y borra el socket. Así no quedan procesos huérfanos.

Si el servicio muere de golpe (`kill -9`), al volver a iniciar marca como
`FAILED` los trabajos que habían quedado en `RUNNING`.

## 4. Hilos dentro del servicio

| Hilo | Qué hace |
| :--- | :------- |
| Principal | Instala manejadores de señales, espera la orden de apagado. |
| `socket` | `serve_forever()`: acepta conexiones. |
| Uno por conexión | Atiende una petición y termina. |
| `planificador` | Recoge procesos, escala a `SIGKILL`, arranca trabajos en cola. |

El acceso a SQLite se serializa con un candado (`threading.Lock`) y las
decisiones del planificador y de `cancel` con otro (`threading.RLock`), para
que no se crucen (por ejemplo, cancelar un trabajo justo cuando va a arrancar).

## 5. Archivos en tiempo de ejecución (`nexus-data/`)

| Archivo | Contenido |
| :------ | :-------- |
| `nexus.db` | Base SQLite (tablas `jobs`, `events`). |
| `nexus.sock` | Socket Unix del servicio (solo existe mientras corre). |
| `logs/<id>.out` / `logs/<id>.err` | Salida estándar / de error de cada trabajo. |

## 6. Decisiones relacionadas

- [ADR-001](adr/ADR-001-persistencia-sqlite.md) — SQLite para persistencia.
- [ADR-002](adr/ADR-002-ejecucion-procesos.md) — `subprocess.Popen` + grupos de procesos + planificador.
- [ADR-003](adr/ADR-003-protocolo-local.md) — Socket Unix con JSON por líneas.
- [ADR-004](adr/ADR-004-comandos-sin-shell.md) — Ejecutar sin shell.
