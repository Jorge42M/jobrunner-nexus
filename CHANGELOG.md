# Historial de versiones

## v0.1.0 — Avance 1 / Hito 1: núcleo local (2026-10)

- Servicio local `./nexus serve` con socket Unix y apagado ordenado por señales.
- Cliente `./nexus` con `submit`, `status`, `list`, `cancel`, `output`, `wait`, `ping`.
- Ejecución en procesos separados con límite de concurrencia y cola FIFO.
- Cancelación SIGTERM → SIGKILL sobre el grupo de procesos.
- Persistencia en SQLite con bitácora de eventos y recuperación tras reinicio.
- 21 pruebas automatizadas (TC-001 a TC-017) y `verif/verify.sh` (TC-018).
- Documentación: arquitectura, modelo de estados, 4 ADR, matriz de trazabilidad,
  registro de uso de IA y evidencia de verificación.

Issues: #1, #2, #3 (parte local), #4, #5, #6, #7, #8, #9.

## v0.0.0 — Hito 0: línea base

- Estructura de carpetas, README inicial, matriz de roles, cronograma y riesgos.
