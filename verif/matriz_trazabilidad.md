# Matriz de trazabilidad (en construcción)

Issue: #5 · Última verificación: [`evidencia/ultima_verificacion.txt`](evidencia/ultima_verificacion.txt)

Relaciona cada requisito con su implementación, sus casos de prueba, la
evidencia y el estado. **PASS** = la prueba pasó en la última verificación.
**PENDIENTE** = programado para un hito posterior.

## Requisitos funcionales

| Req. | Descripción | Implementación | Casos | Evidencia | Estado |
| :--- | :---------- | :------------- | :---- | :-------- | :----- |
| RF-01 | Enviar un trabajo | `runner.submit`, op `submit` | TC-006, TC-014 | verify.sh | PASS |
| RF-02 | Devolver ID único | `store.create_job` (AUTOINCREMENT) | TC-003 | test_store | PASS |
| RF-03 | Ejecutar como proceso separado | `runner._launch` (`Popen`) | TC-007 | test_runner | PASS |
| RF-04 | Consultar estado | op `status` | TC-014 | verify.sh | PASS |
| RF-05 | Listar trabajos (y filtrar por estado) | op `list` | TC-014 | verify.sh | PASS |
| RF-06 | Solicitar cancelación | `runner.cancel` (SIGTERM→SIGKILL) | TC-011, TC-012, TC-013, TC-016 | test_runner, test_service | PASS |
| RF-07 | Obtener código de salida | `exit_code` en `_finish` | TC-006, TC-008, TC-009, TC-011 | verify.sh | PASS |
| RF-08 | Manejar comandos inválidos sin terminar el servicio | `parse_command`, `handle_line` | TC-009, TC-010, TC-015 | verify.sh | PASS |
| RF-09 | Modelo de estados QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELED | `states.py` | TC-001, TC-002, TC-004 | test_states | PASS |
| RF-10 | Capturar stdout y stderr por separado | archivos `logs/<id>.out/.err`, op `output` | TC-006, TC-008 | test_runner | PASS |
| RF-11 | Bitácora de eventos con marca de tiempo | tabla `events` | TC-004, TC-014 | test_store | PASS |
| RF-12 | Respetar límite de concurrencia | `--max-concurrent` | TC-013, TC-021 | test_runner | PASS (básico) |
| RF-13 | Operación remota en LAN/VPN | — | TC-022 a TC-024 | — | PENDIENTE (Hito 3) |

## Requisitos no funcionales

| Req. | Descripción | Cómo se cubre | Casos | Estado |
| :--- | :---------- | :------------ | :---- | :----- |
| RNF-01 | Construcción reproducible sin root | `./build.sh`, solo biblioteca estándar | TC-018 | PASS |
| RNF-02 | Recuperación coherente tras reinicio | `store.recover_after_restart` | TC-005 | PASS |
| RNF-03 | Sin procesos huérfanos ni estados inválidos | `JobRunner.stop`, grupos de procesos | TC-017 | PASS |
| RNF-04 | Pruebas ejecutables con un solo comando | `./verif/verify.sh` | TC-018 | PASS |
| RNF-05 | Mínimo privilegio | socket `0600`, sin shell, no root | TC-010 | PASS (parcial) |
| RNF-06 | 500 registros; 100 lecturas en < 1 s | — | TC-019, TC-020 | PENDIENTE (Hito 2) |
