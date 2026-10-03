"""Pruebas de ejecución de procesos, señales y códigos (TC-006 a TC-013)."""

import os
import tempfile
import time
import unittest

from verif.tests import helpers  # noqa: F401
from nexus import states
from nexus.runner import InvalidCommand, JobRunner, parse_command
from nexus.store import JobStore

TIMEOUT = 10


class RunnerTestCase(unittest.TestCase):
    max_concurrent = 2

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = JobStore(os.path.join(self.tmp.name, "nexus.db"))
        self.runner = JobRunner(self.store, os.path.join(self.tmp.name, "logs"),
                                max_concurrent=self.max_concurrent, kill_grace=1.0,
                                poll_interval=0.05)
        self.runner.start()

    def tearDown(self):
        self.runner.stop()
        self.store.close()
        self.tmp.cleanup()

    def run_job(self, command):
        return self.runner.wait(self.runner.submit(command), timeout=TIMEOUT)

    def wait_state(self, job_id, state):
        deadline = time.monotonic() + TIMEOUT
        while time.monotonic() < deadline:
            if self.store.get_job(job_id)["state"] == state:
                return
            time.sleep(0.05)
        self.fail("el trabajo %d no llegó a %s" % (job_id, state))


class TestRunner(RunnerTestCase):
    def test_tc006_exito_codigo_cero(self):
        """TC-006: un comando correcto termina SUCCEEDED con código 0 y se captura stdout."""
        job = self.run_job("echo hola nexus")
        self.assertEqual(job["state"], states.SUCCEEDED)
        self.assertEqual(job["exit_code"], 0)
        with open(job["stdout_path"]) as fh:
            self.assertEqual(fh.read(), "hola nexus\n")

    def test_tc007_proceso_separado(self):
        """TC-007: el trabajo corre en un proceso distinto al del servicio."""
        job = self.run_job("true")
        self.assertIsNotNone(job["pid"])
        self.assertNotEqual(job["pid"], os.getpid())

    def test_tc008_codigo_distinto_de_cero(self):
        """TC-008: un código de salida != 0 deja el trabajo FAILED con ese código."""
        job = self.run_job("sh -c 'echo fallo >&2; exit 3'")
        self.assertEqual(job["state"], states.FAILED)
        self.assertEqual(job["exit_code"], 3)
        with open(job["stderr_path"]) as fh:
            self.assertEqual(fh.read(), "fallo\n")

    def test_tc009_comando_inexistente(self):
        """TC-009: un comando que no existe falla con 127 y el runner sigue vivo."""
        job = self.run_job("comando_que_no_existe_xyz")
        self.assertEqual(job["state"], states.FAILED)
        self.assertEqual(job["exit_code"], 127)
        self.assertEqual(self.run_job("true")["state"], states.SUCCEEDED)

    def test_tc009b_inexistente_con_path_problematico(self):
        """TC-009: aunque el PATH tenga carpetas sin permiso o archivos no
        ejecutables (como las de Windows en WSL), un comando inexistente da 127."""
        trampa = os.path.join(self.tmp.name, "path_trampa")
        os.makedirs(trampa)
        falso = os.path.join(trampa, "comando_que_no_existe_xyz")
        with open(falso, "w") as fh:  # existe pero SIN permiso de ejecución
            fh.write("#!/bin/sh\necho no\n")
        os.chmod(falso, 0o644)
        sin_permiso = os.path.join(self.tmp.name, "carpeta_sin_permiso")
        os.makedirs(sin_permiso, mode=0o000)
        viejo_path = os.environ.get("PATH", "")
        os.environ["PATH"] = os.pathsep.join([sin_permiso, trampa, viejo_path])
        try:
            job = self.run_job("comando_que_no_existe_xyz")
        finally:
            os.environ["PATH"] = viejo_path
            os.chmod(sin_permiso, 0o755)
        self.assertEqual(job["state"], states.FAILED)
        self.assertEqual(job["exit_code"], 127)

    def test_tc009c_ruta_sin_permiso_de_ejecucion(self):
        """TC-009: una ruta que existe pero no es ejecutable falla con 126."""
        script = os.path.join(self.tmp.name, "script.sh")
        with open(script, "w") as fh:
            fh.write("#!/bin/sh\necho hola\n")
        os.chmod(script, 0o644)
        job = self.run_job(script)
        self.assertEqual(job["state"], states.FAILED)
        self.assertEqual(job["exit_code"], 126)
        self.assertEqual(self.run_job("true")["state"], states.SUCCEEDED)

    def test_tc010_comando_invalido_rechazado(self):
        """TC-010: comandos vacíos o mal formados se rechazan sin crear trabajo."""
        for malo in ["", "   ", "echo 'sin cerrar", None, "a\x00b"]:
            with self.assertRaises(InvalidCommand):
                self.runner.submit(malo)
        self.assertEqual(self.store.list_jobs(), [])
        self.assertEqual(parse_command("echo 'hola mundo'"), ["echo", "hola mundo"])

    def test_tc011_cancelar_en_ejecucion_sigterm(self):
        """TC-011: cancelar un trabajo RUNNING envía SIGTERM; queda CANCELED con -15."""
        job_id = self.runner.submit("sleep 30")
        self.wait_state(job_id, states.RUNNING)
        self.runner.cancel(job_id)
        job = self.runner.wait(job_id, timeout=TIMEOUT)
        self.assertEqual(job["state"], states.CANCELED)
        self.assertEqual(job["exit_code"], -15)

    def test_tc012_sigkill_si_ignora_sigterm(self):
        """TC-012: si el proceso ignora SIGTERM, tras el plazo se envía SIGKILL (-9)."""
        job_id = self.runner.submit("sh -c 'trap \"\" TERM; sleep 30'")
        self.wait_state(job_id, states.RUNNING)
        time.sleep(0.2)  # deja que la shell instale el trap
        self.runner.cancel(job_id)
        job = self.runner.wait(job_id, timeout=TIMEOUT)
        self.assertEqual(job["state"], states.CANCELED)
        self.assertEqual(job["exit_code"], -9)

    def test_cancelar_trabajo_terminado_no_cambia(self):
        job = self.run_job("true")
        self.assertEqual(self.runner.cancel(job["id"])["state"], states.SUCCEEDED)
        with self.assertRaises(KeyError):
            self.runner.cancel(12345)


class TestConcurrency(RunnerTestCase):
    max_concurrent = 1

    def test_tc013_limite_y_cancelar_en_cola(self):
        """TC-013: con límite 1 el segundo trabajo espera QUEUED y puede cancelarse sin ejecutarse."""
        first = self.runner.submit("sleep 30")
        second = self.runner.submit("echo nunca")
        self.wait_state(first, states.RUNNING)
        time.sleep(0.3)
        self.assertEqual(self.store.get_job(second)["state"], states.QUEUED)
        self.assertEqual(self.runner.cancel(second)["state"], states.CANCELED)
        self.assertIsNone(self.store.get_job(second)["pid"])
        self.runner.cancel(first)
        self.runner.wait(first, timeout=TIMEOUT)


if __name__ == "__main__":
    unittest.main()
