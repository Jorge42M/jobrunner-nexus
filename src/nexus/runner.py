"""Ejecución de trabajos como procesos hijos (ver docs/adr/ADR-002).

El JobRunner tiene un hilo "planificador" que cada `poll_interval` segundos:
  1. Recoge los procesos que ya terminaron (poll() hace waitpid y evita zombies).
  2. Si un trabajo cancelado no murió con SIGTERM a tiempo, le manda SIGKILL.
  3. Arranca trabajos QUEUED mientras haya lugar (límite de concurrencia).

Cada trabajo se lanza con subprocess.Popen, que internamente hace fork() +
exec(). Con start_new_session=True el hijo queda en su PROPIO grupo de
procesos, así podemos enviar una señal a él y a todos sus descendientes con
os.killpg().
"""

import os
import shlex
import shutil
import signal
import subprocess
import threading
import time

from . import states
from .store import now

MAX_COMMAND_LENGTH = 4096


class InvalidCommand(ValueError):
    """El texto enviado no se puede convertir en un comando ejecutable."""


def parse_command(command):
    """Valida y separa el comando en argumentos (como lo haría la terminal).

    "echo 'hola mundo'"  ->  ["echo", "hola mundo"]

    No se usa una shell (shell=False): ver ADR-004.
    """
    if not isinstance(command, str):
        raise InvalidCommand("el comando debe ser texto")
    if len(command) > MAX_COMMAND_LENGTH:
        raise InvalidCommand("el comando excede %d caracteres" % MAX_COMMAND_LENGTH)
    if "\x00" in command:
        raise InvalidCommand("el comando contiene un byte nulo")
    try:
        args = shlex.split(command)
    except ValueError as exc:  # ej. comillas sin cerrar
        raise InvalidCommand("sintaxis inválida: %s" % exc)
    if not args:
        raise InvalidCommand("el comando está vacío")
    return args


def describe_exit(returncode):
    """Explica en palabras un código de salida de Popen.

    En Python, si el proceso murió por una señal el código es NEGATIVO:
    -15 significa "terminado por la señal 15 (SIGTERM)".
    """
    if returncode is None:
        return "sigue en ejecución"
    if returncode == 0:
        return "terminó correctamente (0)"
    if returncode < 0:
        try:
            name = signal.Signals(-returncode).name
        except ValueError:
            name = "señal %d" % -returncode
        return "terminado por la señal %s (%d)" % (name, -returncode)
    return "terminó con error (código %d)" % returncode


def find_program(name):
    """Busca el ejecutable como lo haría la terminal y devuelve su ruta.

    - "ls"        -> se busca en cada carpeta del PATH ("/usr/bin/ls").
    - "./script"  -> se usa tal cual (contiene "/").

    Lanza FileNotFoundError si no existe (código 127) y PermissionError si
    la ruta existe pero no es ejecutable (código 126).

    Se busca ANTES de crear el proceso porque, si se deja la búsqueda a
    exec(), un PATH con carpetas sin permiso de lectura (por ejemplo las de
    Windows en WSL, /mnt/c/...) hace que un comando inexistente se reporte
    como "Permission denied" (126) en lugar de "no encontrado" (127).
    """
    if "/" in name:
        if not os.path.exists(name):
            raise FileNotFoundError(name)
        if os.path.isdir(name) or not os.access(name, os.X_OK):
            raise PermissionError(name)
        return name
    path = shutil.which(name)  # solo devuelve archivos con permiso de ejecución
    if path is None:
        raise FileNotFoundError(name)
    return path


class _Running:
    """Datos en memoria de un proceso que está corriendo."""

    def __init__(self, proc, out_file, err_file):
        self.proc = proc
        self.out_file = out_file
        self.err_file = err_file
        self.kill_deadline = None  # cuándo mandar SIGKILL si no muere con SIGTERM


class JobRunner:
    def __init__(self, store, logs_dir, max_concurrent=2, kill_grace=3.0,
                 poll_interval=0.1):
        self.store = store
        self.logs_dir = logs_dir
        self.max_concurrent = max_concurrent
        self.kill_grace = kill_grace
        self.poll_interval = poll_interval
        self._running = {}             # job_id -> _Running
        self._lock = threading.RLock()  # protege self._running y las decisiones
        self._stop = threading.Event()
        self._thread = None
        os.makedirs(logs_dir, exist_ok=True)

    # ------------------------------------------------------------ API pública
    def start(self):
        self._thread = threading.Thread(target=self._loop, name="planificador",
                                        daemon=True)
        self._thread.start()

    def submit(self, command):
        """Valida el comando, lo guarda como QUEUED y devuelve su id."""
        parse_command(command)  # lanza InvalidCommand si no es válido
        return self.store.create_job(command)

    def cancel(self, job_id):
        """Solicita cancelar un trabajo. Devuelve el trabajo actualizado.

        - QUEUED:  pasa directo a CANCELED (nunca se ejecuta).
        - RUNNING: se envía SIGTERM al grupo del proceso; si en `kill_grace`
                   segundos no terminó, se envía SIGKILL. Queda CANCELED
                   cuando el proceso realmente termina.
        - Terminal: no se hace nada (ya terminó).
        """
        with self._lock:
            job = self.store.get_job(job_id)
            if job is None:
                raise KeyError(job_id)
            if job["state"] == states.QUEUED:
                self.store.transition(job_id, states.CANCELED,
                                      detail="cancelado antes de ejecutarse",
                                      cancel_requested=1, finished_at=now())
            elif job["state"] == states.RUNNING and job_id in self._running:
                running = self._running[job_id]
                if running.kill_deadline is None:
                    self.store.update(job_id, event="CANCEL_REQUESTED",
                                      detail="SIGTERM al grupo %d" % running.proc.pid,
                                      cancel_requested=1)
                    self._signal_group(running.proc, signal.SIGTERM)
                    running.kill_deadline = time.monotonic() + self.kill_grace
            return self.store.get_job(job_id)

    def wait(self, job_id, timeout=None):
        """Espera a que el trabajo llegue a un estado final (útil en pruebas)."""
        deadline = None if timeout is None else time.monotonic() + timeout
        while True:
            job = self.store.get_job(job_id)
            if job is None or states.is_terminal(job["state"]):
                return job
            if deadline is not None and time.monotonic() > deadline:
                return job
            time.sleep(self.poll_interval)

    def stop(self):
        """Apaga el planificador y termina los procesos que sigan vivos.

        Así el servicio no deja procesos huérfanos al detenerse.
        """
        self._stop.set()
        if self._thread:
            self._thread.join()
        with self._lock:
            for running in self._running.values():
                self._signal_group(running.proc, signal.SIGTERM)
            deadline = time.monotonic() + self.kill_grace
            for job_id, running in list(self._running.items()):
                remaining = max(0.0, deadline - time.monotonic())
                try:
                    running.proc.wait(timeout=remaining)
                except subprocess.TimeoutExpired:
                    self._signal_group(running.proc, signal.SIGKILL)
                    running.proc.wait()
                self.store.update(job_id, cancel_requested=1)
                self._finish(job_id, running, reason="el servicio se detuvo")

    # ------------------------------------------------------------ planificador
    def _loop(self):
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as exc:  # el planificador nunca debe morir
                print("[runner] error en el planificador: %r" % exc, flush=True)
            self._stop.wait(self.poll_interval)

    def _tick(self):
        with self._lock:
            # 1) Recoger procesos terminados.
            for job_id, running in list(self._running.items()):
                if running.proc.poll() is not None:
                    self._finish(job_id, running)
            # 2) Escalar a SIGKILL si SIGTERM no bastó.
            for running in self._running.values():
                if (running.kill_deadline is not None
                        and time.monotonic() > running.kill_deadline):
                    self._signal_group(running.proc, signal.SIGKILL)
                    running.kill_deadline = float("inf")  # solo una vez
            # 3) Arrancar trabajos en cola si hay lugar.
            free = self.max_concurrent - len(self._running)
            if free > 0:
                for job in self.store.queued_jobs(free):
                    self._launch(job)

    def _launch(self, job):
        job_id = job["id"]
        try:
            args = parse_command(job["command"])
        except InvalidCommand as exc:
            self.store.transition(job_id, states.FAILED, detail=str(exc),
                                  error=str(exc), finished_at=now())
            return
        out_path = os.path.join(self.logs_dir, "%d.out" % job_id)
        err_path = os.path.join(self.logs_dir, "%d.err" % job_id)
        out_file = open(out_path, "wb")
        err_file = open(err_path, "wb")
        try:
            program = find_program(args[0])
            proc = subprocess.Popen(
                args,
                executable=program,        # ruta ya resuelta; argv[0] no cambia
                stdin=subprocess.DEVNULL,  # el trabajo no lee del teclado
                stdout=out_file,           # salida estándar  -> archivo .out
                stderr=err_file,           # salida de error  -> archivo .err
                close_fds=True,            # no heredar descriptores del servicio
                start_new_session=True,    # nuevo grupo de procesos (para killpg)
            )
        except OSError as exc:
            # El comando no existe o no se puede ejecutar: el trabajo falla,
            # pero el servicio sigue funcionando.
            out_file.close()
            err_file.close()
            code = 127 if isinstance(exc, FileNotFoundError) else 126
            reason = ("comando no encontrado: %s" % args[0] if code == 127
                      else "no se pudo ejecutar %s: %s"
                      % (args[0], exc.strerror or "sin permiso de ejecución"))
            self.store.transition(job_id, states.FAILED, detail=reason,
                                  exit_code=code, error=reason, finished_at=now(),
                                  stdout_path=out_path, stderr_path=err_path)
            return
        self._running[job_id] = _Running(proc, out_file, err_file)
        self.store.transition(job_id, states.RUNNING, detail="pid %d" % proc.pid,
                              pid=proc.pid, started_at=now(),
                              stdout_path=out_path, stderr_path=err_path)

    def _finish(self, job_id, running, reason=None):
        """Registra el final de un proceso que ya terminó."""
        self._running.pop(job_id, None)
        running.out_file.close()
        running.err_file.close()
        code = running.proc.returncode
        job = self.store.get_job(job_id)
        if job["cancel_requested"]:
            new_state = states.CANCELED
        elif code == 0:
            new_state = states.SUCCEEDED
        else:
            new_state = states.FAILED
        detail = describe_exit(code)
        if reason:
            detail = "%s; %s" % (reason, detail)
        self.store.transition(job_id, new_state, detail=detail, exit_code=code,
                              error=None if code == 0 else detail,
                              finished_at=now())

    @staticmethod
    def _signal_group(proc, sig):
        """Envía `sig` a todo el grupo de procesos del trabajo."""
        try:
            os.killpg(proc.pid, sig)
        except ProcessLookupError:
            pass  # ya había terminado
