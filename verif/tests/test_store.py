"""Pruebas de la persistencia en SQLite (TC-003 a TC-005)."""

import os
import tempfile
import unittest

from verif.tests import helpers  # noqa: F401
from nexus import states
from nexus.store import JobStore


class TestStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = os.path.join(self.tmp.name, "nexus.db")
        self.store = JobStore(self.db)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_tc003_ids_unicos(self):
        """TC-003: cada trabajo recibe un identificador único y queda QUEUED."""
        ids = [self.store.create_job("echo %d" % i) for i in range(50)]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(self.store.get_job(ids[0])["state"], states.QUEUED)

    def test_tc004_transicion_invalida_rechazada(self):
        """TC-004: una transición inválida se rechaza y no altera la base."""
        job_id = self.store.create_job("true")
        self.store.transition(job_id, states.RUNNING, pid=123)
        self.store.transition(job_id, states.SUCCEEDED, exit_code=0)
        with self.assertRaises(states.InvalidTransition):
            self.store.transition(job_id, states.RUNNING)
        self.assertEqual(self.store.get_job(job_id)["state"], states.SUCCEEDED)
        eventos = [e["event"] for e in self.store.get_events(job_id)]
        self.assertEqual(eventos, ["SUBMITTED", "QUEUED->RUNNING", "RUNNING->SUCCEEDED"])

    def test_tc005_recuperacion_tras_reinicio(self):
        """TC-005: un trabajo RUNNING de una ejecución anterior pasa a FAILED."""
        job_id = self.store.create_job("sleep 100")
        self.store.transition(job_id, states.RUNNING, pid=999999)
        self.store.close()
        self.store = JobStore(self.db)  # simula reinicio del servicio
        self.assertEqual(self.store.recover_after_restart(), [job_id])
        self.assertEqual(self.store.get_job(job_id)["state"], states.FAILED)

    def test_filtrar_por_estado(self):
        a = self.store.create_job("true")
        self.store.create_job("false")
        self.store.transition(a, states.CANCELED)
        self.assertEqual([j["id"] for j in self.store.list_jobs(states.CANCELED)], [a])


if __name__ == "__main__":
    unittest.main()
