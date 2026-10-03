# Cronograma de Hitos y Entregas

Actualizado: 2026-10-02. Las fechas marcadas con *(estimada)* se ajustarán
cuando el profesor confirme el calendario.

| Hito | Contenido | Fecha | Estado | Issues |
| :--- | :-------- | :---- | :----- | :----- |
| Hito 0 | Línea base: estructura, README, roles, cronograma, ADR preliminares | Septiembre 2026 | Completado | #1, #2, #3 |
| **Hito 1** | **Núcleo local: procesos, cola básica, estados, cancelación, CLI** | **6 oct 2026 (Technical Review 1)** | **Completado — v0.1.0** | #4, #5, #6, #7, #8, #9 |
| Hito 2 | Concurrencia bajo carga y persistencia atómica (500 trabajos, < 1 s) | Noviembre 2026 *(estimada)* | Pendiente | — |
| Hito 3 | Operación remota en LAN/VPN (TCP, autenticación, fragmentación) | Noviembre 2026 *(estimada)* | Pendiente | #3 |
| Hito 4 y 5 | Integración, regresiones, incidentes simulados, defensa final | Diciembre 2026 *(estimada)* | Pendiente | — |

## Plan detallado del Hito 1

| Tarea | Entregable | Issue | Estado |
| :---- | :--------- | :---- | :----- |
| Núcleo: enviar, ID, proceso separado, estado, listar, cancelar, código de salida | `src/nexus/` | #4 | Hecho |
| Manejo de comandos inválidos sin caída | `runner.parse_command`, `server.handle_line` | #4 | Hecho |
| ADR iniciales (4) | `docs/adr/` | #1, #2, #3, #9 | Hecho |
| README, arquitectura, modelo de estados | `README.md`, `docs/` | #6 | Hecho |
| Casos de prueba y matriz de trazabilidad | `verif/` | #5 | En construcción (18 de 24) |
| Script de verificación y evidencia | `verif/verify.sh`, `verif/evidencia/` | #7 | Hecho |
| Registro de uso de IA | `docs/registro_uso_ia.md` | #8 | Hecho |
| Ensayo de la presentación | — | #6 | 3–5 oct |

# Registro de Riesgos y Dependencias Conocidas

| # | Riesgo | Prob. | Impacto | Mitigación | Estado |
| :- | :----- | :---: | :-----: | :--------- | :----- |
| 1 | **Procesos huérfanos o zombies.** Si el servicio falla, los hijos podrían quedar huérfanos; si no se recogen, quedan zombies. | Media | Alto | Cada trabajo en su propio grupo de procesos; `SIGTERM`→`SIGKILL` con `killpg`; `poll()` recoge a los hijos; apagado ordenado con `SIGINT`/`SIGTERM`; al reiniciar, los `RUNNING` pasan a `FAILED`. | Mitigado (excepto `kill -9` al servicio) |
| 2 | **Concurrencia en SQLite.** Lecturas y escrituras simultáneas desde varios hilos. | Media | Medio | Transacciones por cambio de estado, modo WAL, candado único. Medir en Hito 2. | Mitigado para Hito 1 |
| 3 | **Fragmentación en red (Hito 3).** Mensajes partidos o pegados en TCP. | Alta | Alto | Mensajes delimitados por `\n`, límite de tamaño, validación estricta (ya implementado en local, ADR-003). | Preparado |
| 4 | **Inyección de comandos.** Texto del usuario interpretado por una shell. | Media | Alto | Sin shell (`shlex` + `shell=False`, ADR-004). | Mitigado |
| 5 | **Diferencias de entorno (WSL vs Linux nativo, finales de línea CRLF).** | Media | Medio | Solo biblioteca estándar; `.gitattributes` fuerza LF en scripts; `build.sh` valida Python y SQLite. | Mitigado |
| 6 | **Curva de aprendizaje de Linux/Git** (trabajo individual). | Alta | Medio | Ensayos de la demo con `./verif/verify.sh`. | En seguimiento |

## Limitaciones actuales conocidas (v0.1.0)

1. Solo operación **local** (socket Unix); no hay acceso remoto ni autenticación.
2. Sin tuberías ni redirecciones directas: hay que usar `sh -c '...'` explícito.
3. Si el servicio recibe `SIGKILL`, no puede terminar a sus hijos: quedan vivos
   aunque en la base se marquen `FAILED` al reiniciar.
4. El planificador revisa cada 0.1 s (sondeo), no reacciona al instante con `SIGCHLD`.
5. No hay límites de CPU/memoria/tiempo por trabajo ni tamaño máximo de cola.
6. Las salidas se guardan completas en disco; `output` muestra solo los últimos 16 KiB.
7. Una sola conexión SQLite con candado: rendimiento bajo carga no medido aún.
