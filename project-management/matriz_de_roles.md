# Matriz de Roles - Nexus

Dado que el proyecto se desarrolla en modalidad de trabajo individual, la matriz de responsabilidades se adapta de la siguiente manera:

| Área | Responsable Principal | Revisor / Validador | Responsabilidades Clave |
| :--- | :--- | :--- | :--- |
| **Producto (Requisitos)** | Jorge I. Mariscal Oliva | Profesor / Autoevaluación | Definir alcance, priorizar RF y RNF, validar cumplimiento de Hitos. |
| **Ingeniería (Desarrollo)**| Jorge I. Mariscal Oliva | Jorge I. Mariscal Oliva | Diseño arquitectónico, implementación en Python, concurrencia, IPC, y persistencia en SQLite. |
| **Verificación (Calidad)** | Jorge I. Mariscal Oliva | Pruebas Automatizadas (`verif/verify.sh`) | Creación de matriz de trazabilidad, redacción de Casos de Prueba (TC-XXX), y validación de seguridad/robustez. |
| **Documentación y Presentación** | Jorge I. Mariscal Oliva | Profesor | README, ADR, registro de uso de IA y exposición en las Technical Reviews. |

## Asignación de responsabilidades — Hito 1 (Avance 1)

Notación RACI: **R** = lo realiza, **A** = aprueba / rinde cuentas, **C** = se consulta, **I** = se informa.

| Entregable | Issue | Jorge (R/A) | Asistente de IA (C) | Profesor (I) |
| :--------- | :---- | :---------: | :-----------------: | :----------: |
| Núcleo local (`src/nexus/`) | #4 | R, A | C | I |
| ADR-001 a ADR-004 | #1, #2, #3, #9 | R, A | C | I |
| README, arquitectura y modelo de estados | #6 | R, A | C | I |
| Casos de prueba y matriz de trazabilidad | #5 | R, A | C | I |
| Script de verificación y evidencia | #7 | R, A | C | I |
| Registro de uso de IA | #8 | R, A | — | I |
| Exposición en la Technical Review 1 | — | R, A | — | I |

El uso del asistente de IA se documenta en [`docs/registro_uso_ia.md`](../docs/registro_uso_ia.md).
Toda salida de la IA es revisada, ejecutada y aprobada por el responsable antes de integrarse.
