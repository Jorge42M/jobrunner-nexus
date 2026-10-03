"""Persistencia de trabajos en SQLite (ver docs/adr/ADR-001).

Dos tablas:
  - jobs:   una fila por trabajo con su estado actual.
  - events: bitácora (log) de todo lo que le pasó a cada trabajo, con hora.

Cada cambio de estado se hace dentro de UNA transacción: se lee el estado
actual, se valida la transición y se escribe el nuevo estado junto con su
evento. Si algo falla, SQLite deshace todo (atomicidad).
"""

import sqlite3
import threading
from datetime import datetime, timezone

from . import states

SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    command          TEXT    NOT NULL,
    state            TEXT    NOT NULL,
    pid              INTEGER,
    exit_code        INTEGER,
    error            TEXT,
    cancel_requested INTEGER NOT NULL DEFAULT 0,
    created_at       TEXT    NOT NULL,
    started_at       TEXT,
    finished_at      TEXT,
    stdout_path      TEXT,
    stderr_path      TEXT
);
CREATE TABLE IF NOT EXISTS events (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id  INTEGER NOT NULL REFERENCES jobs(id),
    ts      TEXT    NOT NULL,
    event   TEXT    NOT NULL,
    detail  TEXT
);
CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state);
CREATE INDEX IF NOT EXISTS idx_events_job ON events(job_id);
"""

# Columnas que el código puede modificar con update()/transition().
# Lista blanca: evita construir SQL con nombres de columna arbitrarios.
UPDATABLE_FIELDS = frozenset({
    "pid", "exit_code", "error", "cancel_requested",
    "started_at", "finished_at", "stdout_path", "stderr_path",
})


def now():
    """Hora actual en UTC, formato ISO 8601 (ej. 2026-10-06T15:04:05.123+00:00)."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


class JobStore:
    def __init__(self, db_path):
        # check_same_thread=False: varios hilos usan la conexión, pero siempre
        # protegidos por self._lock, así que nunca dos a la vez.
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.execute("PRAGMA journal_mode = WAL")
        self._conn.executescript(SCHEMA)
        self._lock = threading.Lock()

    def close(self):
        with self._lock:
            self._conn.close()

    # ---------------------------------------------------------------- escritura
    def create_job(self, command):
        """Registra un trabajo nuevo en estado QUEUED y devuelve su id único."""
        with self._lock, self._conn:  # "with self._conn" = una transacción
            cur = self._conn.execute(
                "INSERT INTO jobs (command, state, created_at) VALUES (?, ?, ?)",
                (command, states.QUEUED, now()),
            )
            job_id = cur.lastrowid
            self._add_event(job_id, "SUBMITTED", command)
            return job_id

    def transition(self, job_id, new_state, detail=None, **fields):
        """Cambia el estado de un trabajo validando la transición.

        Lanza KeyError si el trabajo no existe e InvalidTransition si el cambio
        no está permitido por el modelo de estados.
        """
        self._check_fields(fields)
        with self._lock, self._conn:
            row = self._conn.execute(
                "SELECT state FROM jobs WHERE id = ?", (job_id,)).fetchone()
            if row is None:
                raise KeyError(job_id)
            old_state = row["state"]
            if not states.can_transition(old_state, new_state):
                raise states.InvalidTransition(old_state, new_state)
            fields["state"] = new_state
            self._update(job_id, fields)
            self._add_event(job_id, "%s->%s" % (old_state, new_state), detail)

    def update(self, job_id, event=None, detail=None, **fields):
        """Modifica campos sin cambiar el estado (ej. marcar cancel_requested)."""
        self._check_fields(fields)
        with self._lock, self._conn:
            self._update(job_id, fields)
            if event:
                self._add_event(job_id, event, detail)

    def recover_after_restart(self):
        """Corrige trabajos que quedaron RUNNING si el servicio murió de golpe.

        Esos procesos ya no están bajo nuestro control, así que no podemos saber
        cómo terminaron: se marcan FAILED para no dejar un estado inválido.
        Devuelve la lista de ids corregidos.
        """
        with self._lock, self._conn:
            rows = self._conn.execute(
                "SELECT id FROM jobs WHERE state = ?", (states.RUNNING,)).fetchall()
            ids = [r["id"] for r in rows]
            for job_id in ids:
                self._update(job_id, {
                    "state": states.FAILED,
                    "error": "el servicio se reinició mientras el trabajo corría",
                    "finished_at": now(),
                })
                self._add_event(job_id, "RUNNING->FAILED", "recuperación tras reinicio")
            return ids

    # ---------------------------------------------------------------- lectura
    def get_job(self, job_id):
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def list_jobs(self, state=None):
        with self._lock:
            if state:
                rows = self._conn.execute(
                    "SELECT * FROM jobs WHERE state = ? ORDER BY id", (state,)).fetchall()
            else:
                rows = self._conn.execute("SELECT * FROM jobs ORDER BY id").fetchall()
        return [dict(r) for r in rows]

    def queued_jobs(self, limit):
        """Los `limit` trabajos más antiguos en cola (FIFO: primero en entrar)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM jobs WHERE state = ? ORDER BY id LIMIT ?",
                (states.QUEUED, limit)).fetchall()
        return [dict(r) for r in rows]

    def get_events(self, job_id):
        with self._lock:
            rows = self._conn.execute(
                "SELECT ts, event, detail FROM events WHERE job_id = ? ORDER BY id",
                (job_id,)).fetchall()
        return [dict(r) for r in rows]

    # ---------------------------------------------------------------- internos
    @staticmethod
    def _check_fields(fields):
        unknown = set(fields) - UPDATABLE_FIELDS
        if unknown:
            raise ValueError("campos no permitidos: %s" % ", ".join(sorted(unknown)))

    def _update(self, job_id, fields):
        if not fields:
            return
        columns = ", ".join("%s = ?" % name for name in fields)
        values = list(fields.values()) + [job_id]
        self._conn.execute("UPDATE jobs SET %s WHERE id = ?" % columns, values)

    def _add_event(self, job_id, event, detail):
        self._conn.execute(
            "INSERT INTO events (job_id, ts, event, detail) VALUES (?, ?, ?, ?)",
            (job_id, now(), event, detail))
