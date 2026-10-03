# ADR-002: Ejecución de trabajos con `subprocess.Popen`, grupos de procesos y un hilo planificador

- **Estado:** Aceptada
- **Fecha:** 2026-10-02
- **Issue:** #2

## Contexto

Cada trabajo debe correr en un **proceso separado**, sin bloquear la recepción
de nuevas peticiones, respetando un límite de trabajos simultáneos, y debe
poder cancelarse sin dejar procesos huérfanos ni zombies.

## Alternativas

| Opción | A favor | En contra |
| :----- | :------ | :-------- |
| `os.fork()` + `os.execvp()` a mano | Control total, muy didáctico | Mucho código delicado (redirigir descriptores, cerrar los heredados, manejar errores de `exec` en el hijo). |
| `subprocess.run()` | Una línea | Bloquea hasta que el proceso termina: el servicio no podría atender a nadie. |
| `multiprocessing` | Procesos de Python | Pensado para ejecutar funciones Python, no comandos del sistema. |
| `asyncio.create_subprocess_exec` | No bloquea | Obliga a todo el programa a ser asíncrono; más difícil de explicar. |
| **`subprocess.Popen` + hilo planificador** | No bloquea, internamente usa `fork/exec` de forma segura, se puede consultar con `poll()` | Hay que revisar periódicamente (sondeo cada 0.1 s). |

Para enterarse de que un hijo terminó también se consideró manejar la señal
`SIGCHLD`; se descartó por ahora porque los manejadores de señales en Python
solo corren en el hilo principal y complican el diseño.

## Decisión

- Lanzar con `subprocess.Popen(args, stdin=DEVNULL, stdout=archivo, stderr=archivo, close_fds=True, start_new_session=True)`.
  - `stdout`/`stderr` van a **archivos** (no a tuberías) para que un proceso
    que escribe mucho no se bloquee si nadie lee la tubería.
  - `close_fds=True`: el hijo no hereda descriptores del servicio (ej. el socket).
  - `start_new_session=True`: el hijo es líder de un **grupo de procesos**
    nuevo; así `os.killpg()` alcanza también a sus hijos (ej. `sh -c "sleep 100"`).
- Un hilo **planificador** cada 0.1 s: recoge terminados con `poll()` (que
  hace `waitpid` y evita zombies), escala cancelaciones a `SIGKILL`, y arranca
  trabajos `QUEUED` en orden FIFO mientras haya lugar (`--max-concurrent`).
- Cancelación en dos pasos: `SIGTERM` (pide terminar, se puede atrapar) y,
  tras `--kill-grace` segundos, `SIGKILL` (no se puede ignorar).

## Consecuencias

- La recepción de peticiones nunca espera a un trabajo.
- Un trabajo puede tardar hasta 0.1 s extra en verse como terminado.
- Al apagar el servicio se terminan todos los grupos de procesos vivos.

## Riesgos

- Si el servicio muere con `SIGKILL` no puede limpiar: los hijos siguen vivos
  (huérfanos adoptados por `init`). Mitigación parcial: al reiniciar se marcan
  `FAILED`. En el Hito 2 se evaluará guardar el PGID y terminarlo al reiniciar.

## Evidencia

- TC-006 a TC-013 (`verif/tests/test_runner.py`) y TC-017 (`test_service.py`).
