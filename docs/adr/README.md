# Registro de decisiones de arquitectura (ADR)

Un ADR (*Architecture Decision Record*) documenta una decisión importante:
el contexto, las alternativas que se consideraron, lo que se eligió, sus
consecuencias y la evidencia que la respalda.

| ADR | Decisión | Estado | Issue |
| :-- | :------- | :----- | :---- |
| [ADR-001](ADR-001-persistencia-sqlite.md) | Persistir trabajos en SQLite (no en archivos JSON) | Aceptada | #1 |
| [ADR-002](ADR-002-ejecucion-procesos.md) | `subprocess.Popen` + grupo de procesos + hilo planificador | Aceptada | #2 |
| [ADR-003](ADR-003-protocolo-local.md) | Socket Unix con mensajes JSON delimitados por línea | Aceptada (parte local) | #3 |
| [ADR-004](ADR-004-comandos-sin-shell.md) | Ejecutar comandos sin shell (`shlex` + `shell=False`) | Aceptada | #9 |

Pendiente (Hito 3): ADR-005 sobre el transporte TCP remoto y su autenticación.

Plantilla: Contexto · Alternativas · Decisión · Consecuencias · Riesgos · Evidencia.
