# Casos de prueba (primera versión)

Issue: #5 · Ejecutar todos: `./verif/verify.sh`

Cada caso tiene una prueba automatizada en `verif/tests/`. El nombre de la
función empieza con su identificador (ej. `test_tc006_...`).

| ID | Título | Precondición | Pasos | Resultado esperado | Prueba |
| :- | :----- | :----------- | :---- | :----------------- | :----- |
| TC-001 | Transiciones válidas | — | Consultar `can_transition` para las 6 transiciones del modelo | Todas permitidas | `test_states.py` |
| TC-002 | Estados finales inmutables | — | Intentar salir de `SUCCEEDED`, `FAILED`, `CANCELED` | Ninguna permitida | `test_states.py` |
| TC-003 | ID único | Base vacía | Crear 50 trabajos | 50 IDs distintos, estado `QUEUED` | `test_store.py` |
| TC-004 | Transición inválida rechazada | Trabajo `SUCCEEDED` | Intentar pasarlo a `RUNNING` | `InvalidTransition`; estado y bitácora sin cambios | `test_store.py` |
| TC-005 | Recuperación tras reinicio | Trabajo `RUNNING` en la base | Reabrir base y ejecutar recuperación | Pasa a `FAILED` | `test_store.py` |
| TC-006 | Ejecución exitosa | Servicio activo | `submit echo hola nexus` | `SUCCEEDED`, código `0`, stdout `hola nexus` | `test_runner.py` |
| TC-007 | Proceso separado | Servicio activo | `submit true` | PID registrado ≠ PID del servicio | `test_runner.py` |
| TC-008 | Código distinto de cero | Servicio activo | `submit sh -c 'echo fallo >&2; exit 3'` | `FAILED`, código `3`, stderr `fallo` | `test_runner.py` |
| TC-009 | Comando inexistente | Servicio activo | `submit comando_que_no_existe_xyz`, también con un `PATH` que incluye carpetas sin permiso (como las de Windows en WSL); y `submit` de una ruta que existe sin permiso de ejecución | Inexistente: `FAILED`, código `127`. Ruta no ejecutable: `FAILED`, código `126`. El siguiente trabajo funciona | `test_runner.py` |
| TC-010 | Comando inválido | Servicio activo | `submit` con vacío, espacios, comillas sin cerrar, byte nulo | Rechazado, no se crea trabajo | `test_runner.py` |
| TC-011 | Cancelación con SIGTERM | Trabajo `sleep 30` en `RUNNING` | `cancel` | `CANCELED`, código `-15` | `test_runner.py` |
| TC-012 | Escalado a SIGKILL | Trabajo que ignora SIGTERM | `cancel` | `CANCELED`, código `-9` | `test_runner.py` |
| TC-013 | Límite de concurrencia y cancelar en cola | `max_concurrent=1`, un trabajo corriendo | Enviar otro, verificar `QUEUED`, cancelarlo | Queda `CANCELED` sin PID (nunca se ejecutó) | `test_runner.py` |
| TC-014 | Flujo completo por socket | Servicio real | `submit` → `status` → `list` → `output` | Respuestas `ok`, bitácora ≥ 3 eventos, stdout correcto | `test_service.py` |
| TC-015 | Peticiones inválidas | Servicio real | JSON roto, operación inexistente, id no numérico, id inexistente, estado desconocido | `ok: false` en cada una; `ping` sigue respondiendo | `test_service.py` |
| TC-016 | Cancelar por socket | Servicio real, `sleep 30` | `cancel` por el socket | `CANCELED` | `test_service.py` |
| TC-017 | Apagado sin huérfanos | Servicio real, `sleep 30` corriendo | Detener servicio | El PID ya no existe, socket borrado, trabajo `CANCELED` | `test_service.py` |
| TC-018 | Prueba de humo desde la CLI | Clon limpio | `./verif/verify.sh` | Termina con "VERIFICACIÓN EXITOSA" | `verif/verify.sh` |

## Pendientes (siguientes hitos)

| ID | Tema | Hito |
| :- | :--- | :--- |
| TC-019 | 500 trabajos registrados sin errores | 2 |
| TC-020 | Lectura de estado de 100 trabajos en < 1 s | 2 |
| TC-021 | Nunca más de N procesos simultáneos bajo carga | 2 |
| TC-022 | Mensaje fragmentado por TCP se reconstruye bien | 3 |
| TC-023 | Desconexión abrupta del cliente no deja estado inválido | 3 |
| TC-024 | Conexión rechazada fuera de LAN/VPN | 3 |
