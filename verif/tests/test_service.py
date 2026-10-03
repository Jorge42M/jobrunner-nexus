"""Pruebas de extremo a extremo: cliente -> socket -> servicio (TC-014 a TC-017)."""

import os
import socket
import tempfile
import time
import unittest

from verif.tests import helpers  # noqa: F401
from nexus import protocol, states
from nexus.server import Service


class TestService(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = Service(self.tmp.name, max_concurrent=2, kill_grace=1.0)
        self.service.runner.poll_interval = 0.05
        self.service.start()

    def tearDown(self):
        self.service.stop()
        self.tmp.cleanup()

    def req(self, **message):
        return protocol.request(self.service.socket_path, message)

    def wait_terminal(self, job_id):
        return self.service.runner.wait(job_id, timeout=10)

    def test_tc014_flujo_completo(self):
        """TC-014: submit -> status -> list -> output a través del socket."""
        resp = self.req(op="submit", command="echo flujo completo")
        self.assertTrue(resp["ok"])
        job_id = resp["job"]["id"]
        self.wait_terminal(job_id)
        status = self.req(op="status", id=job_id)
        self.assertEqual(status["job"]["state"], states.SUCCEEDED)
        self.assertEqual(status["job"]["exit_code"], 0)
        self.assertGreaterEqual(len(status["job"]["events"]), 3)
        ids = [j["id"] for j in self.req(op="list")["jobs"]]
        self.assertIn(job_id, ids)
        self.assertEqual(self.req(op="output", id=job_id)["stdout"], "flujo completo\n")

    def test_tc015_peticiones_invalidas_no_tumban_el_servicio(self):
        """TC-015: JSON roto, operaciones e ids inválidos devuelven error y el servicio sigue."""
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
            sock.connect(self.service.socket_path)
            sock.sendall(b"esto no es json\n")
            respuesta = protocol.decode(sock.makefile("rb").readline())
        self.assertFalse(respuesta["ok"])
        for message in [{"op": "volar"}, {"op": "status", "id": "x"},
                        {"op": "status", "id": 999}, {"op": "submit", "command": ""},
                        {"op": "list", "state": "DORMIDO"}]:
            self.assertFalse(self.req(**message)["ok"], message)
        self.assertTrue(self.req(op="ping")["ok"])

    def test_tc016_cancelar_por_socket(self):
        """TC-016: cancelar a través del socket termina el proceso."""
        job_id = self.req(op="submit", command="sleep 30")["job"]["id"]
        self.assertTrue(self.req(op="cancel", id=job_id)["ok"])
        job = self.wait_terminal(job_id)
        self.assertEqual(job["state"], states.CANCELED)

    def test_tc017_apagado_sin_huerfanos(self):
        """TC-017: al detener el servicio no quedan procesos hijos vivos."""
        job_id = self.req(op="submit", command="sleep 30")["job"]["id"]
        for _ in range(100):  # espera hasta 5 s a que arranque
            if self.service.store.get_job(job_id)["state"] == states.RUNNING:
                break
            time.sleep(0.05)
        pid = self.service.store.get_job(job_id)["pid"]
        self.service.stop()
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)  # la señal 0 solo pregunta si el proceso existe
        self.assertFalse(os.path.exists(self.service.socket_path))
        # Se vuelve a abrir el servicio para comprobar lo guardado (y para tearDown).
        self.service = Service(self.tmp.name)
        self.service.start()
        self.assertEqual(self.service.store.get_job(job_id)["state"], states.CANCELED)


if __name__ == "__main__":
    unittest.main()
