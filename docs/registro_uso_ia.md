# Registro de uso de IA

Issue: #8

Este registro documenta cómo se usó un asistente de IA (Claude, en un
proyecto de claude.ai conectado al repositorio) durante el Avance 1, qué se
aceptó, qué se modificó y qué se rechazó. **Toda propuesta fue revisada,
ejecutada en la terminal y verificada con `./verif/verify.sh` antes de
integrarse.**

## Resumen

| # | Fecha | Solicitud | Resultado | Decisión |
| :- | :---- | :-------- | :-------- | :------- |
| 1 | 2026-10-02 | Implementar el núcleo local del Hito 1 con solo biblioteca estándar | Paquete `src/nexus/` (6 módulos) | Aceptado con modificaciones (ver 1a–1e) |
| 2 | 2026-10-02 | Primeros casos de prueba y script de verificación | 21 pruebas `unittest` y `verif/verify.sh` | Aceptado |
| 3 | 2026-10-02 | Redactar ADR, arquitectura, modelo de estados y matriz | Documentos en `docs/` y `verif/` | Aceptado; fechas del cronograma marcadas como estimadas |

## Detalle de decisiones técnicas sobre propuestas de la IA

**1a. Ejecutar con `shell=True` — RECHAZADO.**
Era la forma más corta de ejecutar el texto del usuario, pero permite
inyección de comandos (`echo hola; rm -rf ~`) y el PID guardado sería el de
`/bin/sh`, no el del programa. Se eligió `shlex.split` + `shell=False`
(ADR-004).

**1b. Capturar stdout/stderr con `subprocess.PIPE` — RECHAZADO.**
Si un trabajo escribe más de lo que cabe en el búfer de la tubería (~64 KiB) y
nadie la lee, el hijo se bloquea para siempre. Se cambió a redirigir a
archivos `logs/<id>.out` y `logs/<id>.err`.

**1c. Cancelar con `proc.terminate()` (solo al PID) — MODIFICADO.**
No alcanza a los nietos (`sh -c "sleep 100"` deja vivo el `sleep`). Se cambió
a `start_new_session=True` + `os.killpg` sobre el grupo, con escalado a
`SIGKILL` (ADR-002). Verificado con TC-012 y TC-017.

**1d. Detectar el fin de los hijos con un manejador de `SIGCHLD` — RECHAZADO
para este hito.** En Python los manejadores de señales solo corren en el hilo
principal; mezclarlo con hilos complica el diseño y su explicación. Se usa
sondeo con `poll()` cada 0.1 s (limitación documentada).

**1e. Usar UUID como identificador — MODIFICADO.** Un UUID es único pero
difícil de escribir en la demo. Se usa el `INTEGER PRIMARY KEY AUTOINCREMENT`
de SQLite, que también es único y nunca se reutiliza.

**1f. Dejar que `exec()` busque el programa en el `PATH` — MODIFICADO tras
probar en WSL.** Al probar en un equipo con WSL2, TC-009 falló: un
comando inexistente salía con `126` en vez de `127`, porque el `PATH` de WSL
incluye carpetas de Windows y la búsqueda de `exec()` devolvía "Permission
denied". Se agregó `find_program` (búsqueda previa con `shutil.which`) y dos
pruebas que simulan ese `PATH`. Lección: probar en el equipo real, no solo
en el entorno donde se generó el código.

**3a. Fechas exactas de Hitos 2–5 — MODIFICADO.** La IA no conoce el
calendario oficial; se dejaron como *estimadas* hasta confirmarlas.

## Cómo se verifica lo generado

1. Leer cada módulo y su explicación en `docs/arquitectura.md`.
2. Ejecutar `./build.sh` y `./verif/verify.sh` en el equipo propio (WSL2 Ubuntu).
3. Repetir a mano el flujo de la sección «Ejecución» del `README.md`.
4. Revisar los procesos con `ps` para confirmar PID, grupo y que no quedan zombies.
