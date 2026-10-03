# ADR-001: Persistir los trabajos en SQLite

- **Estado:** Aceptada
- **Fecha:** 2026-10-02
- **Issue:** #1

## Contexto

El servicio debe guardar cada trabajo (comando, estado, PID, código de salida,
fechas) y una bitácora de eventos. Los requisitos piden atomicidad, consulta
rápida por ID, filtrado por estado y recuperación coherente tras un reinicio.
Solo se permite la biblioteca estándar de Python.

## Alternativas

| Opción | A favor | En contra |
| :----- | :------ | :-------- |
| **Archivo JSON** por trabajo o uno global | Muy simple, legible | Reescribir el archivo no es atómico: si el servicio muere a la mitad queda corrupto. Filtrar requiere leer todo. Varios hilos escribiendo = condiciones de carrera. |
| **Solo memoria** (diccionario) | Lo más rápido | Se pierde todo al reiniciar. |
| **SQLite (`sqlite3`)** | Viene con Python, transacciones ACID, índices, SQL para filtrar | Un solo escritor a la vez; hay que cuidar el uso entre hilos. |

## Decisión

Usar SQLite con dos tablas (`jobs` y `events`). Cada cambio de estado se hace
en **una transacción**: leer estado actual → validar transición → actualizar
fila → insertar evento. Si algo falla, se deshace todo. Se activa el modo WAL
(`PRAGMA journal_mode=WAL`) para que las lecturas no bloqueen las escrituras.

## Consecuencias

- El ID único lo da SQLite (`INTEGER PRIMARY KEY AUTOINCREMENT`): nunca se
  repite, ni siquiera si se borran filas.
- Hay una sola conexión compartida protegida con `threading.Lock`; es simple
  pero serializa los accesos (suficiente para el Hito 1).
- Al reiniciar se pueden detectar trabajos `RUNNING` que quedaron colgados.

## Riesgos

- Con mucha carga el candado único puede ser cuello de botella (se medirá en
  el Hito 2 contra el RNF de 100 lecturas en < 1 s).

## Evidencia

- TC-003 (IDs únicos), TC-004 (transición inválida no altera la base),
  TC-005 (recuperación tras reinicio): `verif/tests/test_store.py`.
