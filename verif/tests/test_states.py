"""Pruebas del modelo de estados (TC-001, TC-002)."""

import unittest

from verif.tests import helpers  # noqa: F401  (agrega src/ al path)
from nexus import states


class TestStates(unittest.TestCase):
    def test_tc001_transiciones_validas(self):
        """TC-001: las transiciones del modelo están permitidas."""
        validas = [
            (states.QUEUED, states.RUNNING),
            (states.QUEUED, states.CANCELED),
            (states.QUEUED, states.FAILED),
            (states.RUNNING, states.SUCCEEDED),
            (states.RUNNING, states.FAILED),
            (states.RUNNING, states.CANCELED),
        ]
        for old, new in validas:
            self.assertTrue(states.can_transition(old, new), (old, new))

    def test_tc002_estados_finales_no_cambian(self):
        """TC-002: desde un estado final no se puede pasar a ningún otro."""
        for final in states.TERMINAL_STATES:
            for new in states.ALL_STATES:
                self.assertFalse(states.can_transition(final, new), (final, new))
        self.assertFalse(states.can_transition(states.RUNNING, states.QUEUED))


if __name__ == "__main__":
    unittest.main()
