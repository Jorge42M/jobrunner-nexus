"""El servicio Nexus: escucha peticiones en un socket Unix local.

Recorrido de una petición:
  1. El cliente (cli.py) se conecta a <NEXUS_HOME>/nexus.sock y envía una
     línea JSON.
  2. Un hilo del servidor la lee y la valida (protocol.decode).
  3. dispatch() llama al JobRunner / JobStore según la operación.
  4. Se responde con una línea JSON. Cualquier error se convierte en
     {"ok": false, "error": ...}: el servicio NUNCA se cae por una petición mala.

Señales: SIGTERM o SIGINT (Ctrl+C) apagan el servicio de forma ordenada:
dejan de aceptar peticiones, terminan los procesos hijos y borran el socket.
"""

import os
import signal
import socket
import socketserver
import threading

from . import protocol, states
from .runner import InvalidCommand, JobRunner
from .store import JobStore

OUTPUT_LIMIT = 16 * 1024  # bytes de stdout/stderr que devuelve "output"


def job_view(store, job_id):
    job = store.get_job(job_id)
    if job is None:
        raise KeyError(job_id)
    job["events"] = store.get_events(job_id)
    return job


def _read_tail(path, limit=OUTPUT_LIMIT):
    if not path or not os.path.exists(path):
        return ""
    with open(path, "rb") as fh:
        fh.seek(0, os.SEEK_END)
        size = fh.tell()
        fh.seek(max(0, size - limit))
        return fh.read().decode("utf-8", errors="replace")


def _job_id(message):
    value = message.get("id")
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise protocol.ProtocolError("'id' debe ser un entero positivo")
    return value


def dispatch(runner, message):
    """Ejecuta una operación y devuelve el diccionario de respuesta."""
    op = message.get("op")
    store = runner.store
    if op == "ping":
        return {"ok": True, "pong": True, "pid": os.getpid()}
    if op == "submit":
        job_id = runner.submit(message.get("command"))
        return {"ok": True, "job": store.get_job(job_id)}
    if op == "status":
        return {"ok": True, "job": job_view(store, _job_id(message))}
    if op == "list":
        state = message.get("state")
        if state is not None and state not in states.ALL_STATES:
            raise protocol.ProtocolError("estado desconocido: %s" % state)
        return {"ok": True, "jobs": store.list_jobs(state)}
    if op == "cancel":
        return {"ok": True, "job": runner.cancel(_job_id(message))}
    if op == "output":
        job = job_view(store, _job_id(message))
        return {"ok": True, "id": job["id"], "state": job["state"],
                "stdout": _read_tail(job["stdout_path"]),
                "stderr": _read_tail(job["stderr_path"])}
    raise protocol.ProtocolError(
        "operación desconocida: %r (válidas: %s)" % (op, ", ".join(protocol.OPERATIONS)))


def handle_line(runner, line):
    """Convierte una línea recibida en la línea de respuesta. Nunca lanza."""
    try:
        message = protocol.decode(line)
        response = dispatch(runner, message)
    except KeyError as exc:
        response = {"ok": False, "error": "no existe el trabajo %s" % exc.args[0]}
    except (protocol.ProtocolError, InvalidCommand) as exc:
        response = {"ok": False, "error": str(exc)}
    except Exception as exc:  # error inesperado: se informa, no se cae
        response = {"ok": False, "error": "error interno: %r" % exc}
    return protocol.encode(response)


class _Handler(socketserver.StreamRequestHandler):
    def handle(self):
        line = self.rfile.readline(protocol.MAX_MESSAGE_BYTES + 1)
        if not line:
            return  # el cliente se desconectó sin enviar nada
        try:
            self.wfile.write(handle_line(self.server.runner, line))
        except (BrokenPipeError, ConnectionResetError):
            pass  # el cliente se fue antes de leer la respuesta


class NexusServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True

    def __init__(self, socket_path, runner):
        self.runner = runner
        super().__init__(socket_path, _Handler)


def _socket_in_use(path):
    """True si ya hay otro servicio Nexus escuchando en ese socket."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        try:
            sock.connect(path)
            return True
        except OSError:
            return False


class Service:
    """Une las piezas: base de datos + ejecutor + servidor de socket."""

    def __init__(self, home, max_concurrent=2, kill_grace=3.0):
        self.home = os.path.abspath(home)
        os.makedirs(self.home, exist_ok=True)
        self.socket_path = os.path.join(self.home, "nexus.sock")
        self.store = JobStore(os.path.join(self.home, "nexus.db"))
        self.runner = JobRunner(self.store, os.path.join(self.home, "logs"),
                                max_concurrent=max_concurrent, kill_grace=kill_grace)
        self.server = None
        self._server_thread = None

    def start(self):
        recovered = self.store.recover_after_restart()
        if recovered:
            print("[nexus] trabajos marcados FAILED tras reinicio: %s" % recovered,
                  flush=True)
        if os.path.exists(self.socket_path):
            if _socket_in_use(self.socket_path):
                raise RuntimeError("ya hay un servicio Nexus usando %s" % self.socket_path)
            os.unlink(self.socket_path)  # socket viejo de una ejecución anterior
        self.server = NexusServer(self.socket_path, self.runner)
        os.chmod(self.socket_path, 0o600)  # solo el dueño puede conectarse
        self.runner.start()
        self._server_thread = threading.Thread(target=self.server.serve_forever,
                                               name="socket", daemon=True)
        self._server_thread.start()

    def stop(self):
        if self.server:
            self.server.shutdown()      # deja de aceptar peticiones
            self.server.server_close()
        self.runner.stop()              # termina procesos hijos
        self.store.close()
        if os.path.exists(self.socket_path):
            os.unlink(self.socket_path)


def serve(home, max_concurrent=2, kill_grace=3.0):
    """Punto de entrada de `nexus serve`. Bloquea hasta recibir SIGTERM/SIGINT."""
    service = Service(home, max_concurrent=max_concurrent, kill_grace=kill_grace)
    stop_requested = threading.Event()

    def on_signal(signum, _frame):
        print("[nexus] recibida señal %s, apagando..." % signal.Signals(signum).name,
              flush=True)
        stop_requested.set()

    signal.signal(signal.SIGTERM, on_signal)
    signal.signal(signal.SIGINT, on_signal)

    service.start()
    print("[nexus] servicio iniciado (pid %d). Socket: %s. Concurrencia máxima: %d"
          % (os.getpid(), service.socket_path, max_concurrent), flush=True)
    print("[nexus] presiona Ctrl+C para detenerlo.", flush=True)
    while not stop_requested.wait(0.5):
        pass
    service.stop()
    print("[nexus] servicio detenido.", flush=True)
    return 0
