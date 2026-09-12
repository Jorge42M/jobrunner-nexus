# Cronograma de Hitos y Entregas

- **Hito 0:** Línea base y ADR preliminares (Fase Actual).
- **Hito 1:** Núcleo local (procesos y colas básicas).
- **Hito 2:** Concurrencia y persistencia atómica.
- **Hito 3:** Operación remota en LAN/VPN.
- **Hito 4 & 5:** Integración, regresiones, incidentes simulados y defensa final técnica individual.

# Registro de Riesgos y Dependencias Conocidas

1. **Riesgo de Procesos Huérfanos (Zombies):** Al gestionar procesos hijos en Linux, si el servicio principal falla abruptamente, los procesos hijos podrían quedar como huérfanos. *Mitigación:* Captura de señales (SIGTERM/SIGINT) y limpieza proactiva de descriptores de archivo.
2. **Concurrencia en SQLite:** Al manejar lecturas de estado y escrituras de nuevos trabajos simultáneamente, la base de datos podría bloqueos. *Mitigación:* Gestión adecuada de transacciones (ACID) en sqlite3 nativo.
3. **Fragmentación en Red (Hito 3):** Corrupción de la semántica del protocolo propio por fragmentación TCP. *Mitigación:* Implementar validación estricta de mensajes de red y delimitadores claros.
