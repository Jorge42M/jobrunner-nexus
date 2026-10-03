"""Modelo de estados de un trabajo (job).

Un trabajo siempre está en UNO de estos cinco estados. Solo se permiten las
transiciones de la tabla TRANSITIONS; cualquier otra es un error de programación
y se rechaza con InvalidTransition.

    QUEUED ──► RUNNING ──► SUCCEEDED   (código de salida 0)
      │           ├──────► FAILED      (código distinto de 0 o muerto por señal)
      │           └──────► CANCELED    (el usuario pidió cancelar)
      ├──────────────────► CANCELED    (cancelado antes de arrancar)
      └──────────────────► FAILED      (no se pudo lanzar: comando inexistente)
"""

QUEUED = "QUEUED"
RUNNING = "RUNNING"
SUCCEEDED = "SUCCEEDED"
FAILED = "FAILED"
CANCELED = "CANCELED"

ALL_STATES = (QUEUED, RUNNING, SUCCEEDED, FAILED, CANCELED)

# Estados finales: de aquí ya no se sale.
TERMINAL_STATES = frozenset({SUCCEEDED, FAILED, CANCELED})

# Para cada estado, a qué estados se puede pasar.
TRANSITIONS = {
    QUEUED: frozenset({RUNNING, CANCELED, FAILED}),
    RUNNING: frozenset({SUCCEEDED, FAILED, CANCELED}),
    SUCCEEDED: frozenset(),
    FAILED: frozenset(),
    CANCELED: frozenset(),
}


class InvalidTransition(Exception):
    """Se intentó una transición no permitida (por ejemplo SUCCEEDED -> RUNNING)."""

    def __init__(self, old, new):
        super().__init__("transición inválida: %s -> %s" % (old, new))
        self.old = old
        self.new = new


def can_transition(old, new):
    """Devuelve True si se puede pasar del estado `old` al estado `new`."""
    return new in TRANSITIONS.get(old, frozenset())


def is_terminal(state):
    return state in TERMINAL_STATES
