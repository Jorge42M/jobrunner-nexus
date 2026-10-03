"""Cliente de línea de comandos de Nexus.

Uso (desde la raíz del repositorio, con el atajo ./nexus):

    ./nexus serve                 # inicia el servicio (dejar esta terminal abierta)
    ./nexus submit sleep 30       # envía un trabajo, imprime su id
    ./nexus status 1              # estado, pid, código de salida y bitácora
    ./nexus list                  # todos los trabajos
    ./nexus list --state RUNNING  # solo los que están corriendo
    ./nexus cancel 1              # solicita la cancelación
    ./nexus output 1              # muestra stdout y stderr del trabajo
    ./nexus wait 1                # espera a que termine e imprime el código

Códigos de salida del propio cliente:
    0 = la operación funcionó
    1 = el servicio respondió con un error (ej. id inexistente)
    2 = no se pudo hablar con el servicio (¿está corriendo?)
"""

import argparse
import os
import shlex
import sys
import time

from . import protocol, states
from .server import serve

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_NO_SERVICE = 2


def default_home():
    return os.environ.get("NEXUS_HOME") or os.path.join(os.getcwd(), "nexus-data")


def build_parser():
    parser = argparse.ArgumentParser(
        prog="nexus", description="Nexus: ejecuta comandos de Linux como trabajos.")
    parser.add_argument("--home", default=default_home(),
                        help="carpeta de datos (por defecto $NEXUS_HOME o ./nexus-data)")
    sub = parser.add_subparsers(dest="cmd", metavar="COMANDO")
    sub.required = True

    p = sub.add_parser("serve", help="inicia el servicio")
    p.add_argument("--max-concurrent", type=int, default=2,
                   help="máximo de trabajos ejecutándose a la vez (por defecto 2)")
    p.add_argument("--kill-grace", type=float, default=3.0,
                   help="segundos entre SIGTERM y SIGKILL al cancelar (por defecto 3)")

    sub.add_parser("ping", help="comprueba que el servicio responde")

    p = sub.add_parser("submit", help="envía un trabajo")
    p.add_argument("command", nargs=argparse.REMAINDER,
                   help="comando a ejecutar, ej: sleep 5")

    p = sub.add_parser("status", help="muestra el estado de un trabajo")
    p.add_argument("id", type=int)

    p = sub.add_parser("list", help="lista los trabajos")
    p.add_argument("--state", choices=states.ALL_STATES)

    p = sub.add_parser("cancel", help="solicita cancelar un trabajo")
    p.add_argument("id", type=int)

    p = sub.add_parser("output", help="muestra stdout y stderr de un trabajo")
    p.add_argument("id", type=int)

    p = sub.add_parser("wait", help="espera a que un trabajo termine")
    p.add_argument("id", type=int)
    p.add_argument("--timeout", type=float, default=60.0)
    return parser


def _show(value):
    return "-" if value is None else str(value)


def print_job(job, with_events=False):
    print("Trabajo #%d" % job["id"])
    print("  comando     : %s" % job["command"])
    print("  estado      : %s" % job["state"])
    print("  pid         : %s" % _show(job["pid"]))
    print("  código      : %s" % _show(job["exit_code"]))
    if job.get("error"):
        print("  detalle     : %s" % job["error"])
    print("  creado      : %s" % job["created_at"])
    print("  iniciado    : %s" % _show(job["started_at"]))
    print("  terminado   : %s" % _show(job["finished_at"]))
    if with_events and job.get("events"):
        print("  bitácora:")
        for ev in job["events"]:
            detail = " (%s)" % ev["detail"] if ev["detail"] else ""
            print("    %s  %s%s" % (ev["ts"], ev["event"], detail))


def print_table(jobs):
    if not jobs:
        print("(no hay trabajos)")
        return
    print("%-4s %-10s %-7s %-7s %s" % ("ID", "ESTADO", "PID", "CÓDIGO", "COMANDO"))
    for job in jobs:
        print("%-4d %-10s %-7s %-7s %s" % (job["id"], job["state"], _show(job["pid"]),
                                          _show(job["exit_code"]), job["command"]))


def call(home, message):
    """Envía una petición al servicio. Devuelve (código_salida, respuesta)."""
    socket_path = os.path.join(home, "nexus.sock")
    try:
        response = protocol.request(socket_path, message)
    except (FileNotFoundError, ConnectionRefusedError):
        print("Error: el servicio no está corriendo (no se encontró %s).\n"
              "Inícialo en otra terminal con:  ./nexus serve" % socket_path,
              file=sys.stderr)
        return EXIT_NO_SERVICE, None
    except (OSError, protocol.ProtocolError) as exc:
        print("Error de comunicación con el servicio: %s" % exc, file=sys.stderr)
        return EXIT_NO_SERVICE, None
    if not response.get("ok"):
        print("Error: %s" % response.get("error"), file=sys.stderr)
        return EXIT_ERROR, response
    return EXIT_OK, response


def main(argv=None):
    args = build_parser().parse_args(argv)
    home = os.path.abspath(args.home)

    if args.cmd == "serve":
        try:
            return serve(home, args.max_concurrent, args.kill_grace)
        except RuntimeError as exc:
            print("Error: %s" % exc, file=sys.stderr)
            return EXIT_ERROR

    if args.cmd == "ping":
        code, resp = call(home, {"op": "ping"})
        if code == EXIT_OK:
            print("El servicio responde (pid %d)." % resp["pid"])
        return code

    if args.cmd == "submit":
        parts = args.command
        command = parts[0] if len(parts) == 1 else shlex.join(parts)
        code, resp = call(home, {"op": "submit", "command": command})
        if code == EXIT_OK:
            print("Trabajo enviado. ID: %d (estado %s)"
                  % (resp["job"]["id"], resp["job"]["state"]))
        return code

    if args.cmd == "status":
        code, resp = call(home, {"op": "status", "id": args.id})
        if code == EXIT_OK:
            print_job(resp["job"], with_events=True)
        return code

    if args.cmd == "list":
        code, resp = call(home, {"op": "list", "state": args.state})
        if code == EXIT_OK:
            print_table(resp["jobs"])
        return code

    if args.cmd == "cancel":
        code, resp = call(home, {"op": "cancel", "id": args.id})
        if code == EXIT_OK:
            job = resp["job"]
            if job["state"] == states.CANCELED:
                print("Trabajo #%d cancelado." % job["id"])
            elif job["state"] == states.RUNNING:
                print("Cancelación solicitada para #%d (se envió SIGTERM)." % job["id"])
            else:
                print("El trabajo #%d ya había terminado (%s)." % (job["id"], job["state"]))
        return code

    if args.cmd == "output":
        code, resp = call(home, {"op": "output", "id": args.id})
        if code == EXIT_OK:
            print("----- stdout (#%d) -----" % resp["id"])
            print(resp["stdout"], end="" if resp["stdout"].endswith("\n") else "\n")
            print("----- stderr (#%d) -----" % resp["id"])
            print(resp["stderr"], end="" if resp["stderr"].endswith("\n") else "\n")
        return code

    if args.cmd == "wait":
        deadline = time.monotonic() + args.timeout
        while True:
            code, resp = call(home, {"op": "status", "id": args.id})
            if code != EXIT_OK:
                return code
            job = resp["job"]
            if states.is_terminal(job["state"]):
                print("Trabajo #%d terminó: %s, código de salida %s"
                      % (job["id"], job["state"], _show(job["exit_code"])))
                return EXIT_OK
            if time.monotonic() > deadline:
                print("Tiempo de espera agotado; el trabajo sigue en %s" % job["state"],
                      file=sys.stderr)
                return EXIT_ERROR
            time.sleep(0.2)

    return EXIT_ERROR
