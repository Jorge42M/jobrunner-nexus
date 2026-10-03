"""Protocolo local cliente <-> servicio (ver docs/adr/ADR-003).

Cada petición es UNA línea de texto con un objeto JSON, terminada en "\\n".
Cada respuesta también es una línea JSON. Ejemplo:

    cliente -> {"op": "submit", "command": "sleep 5"}
    servicio <- {"ok": true, "job": {"id": 1, "state": "QUEUED", ...}}

    cliente -> {"op": "status", "id": 99}
    servicio <- {"ok": false, "error": "no existe el trabajo 99"}

El salto de línea marca dónde termina el mensaje: así, aunque los datos lleguen
en varios pedazos por el socket, el receptor sabe cuándo ya tiene el mensaje
completo.
"""

import json
import socket

MAX_MESSAGE_BYTES = 64 * 1024  # mensajes más grandes se rechazan

OPERATIONS = ("ping", "submit", "status", "list", "cancel", "output")


class ProtocolError(ValueError):
    pass


def encode(message):
    return (json.dumps(message, ensure_ascii=False) + "\n").encode("utf-8")


def decode(line):
    if len(line) > MAX_MESSAGE_BYTES:
        raise ProtocolError("mensaje demasiado grande")
    if not line.endswith(b"\n"):
        raise ProtocolError("mensaje incompleto (falta el salto de línea)")
    try:
        message = json.loads(line.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError("JSON inválido: %s" % exc)
    if not isinstance(message, dict):
        raise ProtocolError("el mensaje debe ser un objeto JSON")
    return message


def request(socket_path, message, timeout=10.0):
    """Lado cliente: conecta, envía un mensaje y devuelve la respuesta."""
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect(socket_path)
        sock.sendall(encode(message))
        with sock.makefile("rb") as reader:
            line = reader.readline(MAX_MESSAGE_BYTES + 1)
    if not line:
        raise ProtocolError("el servicio cerró la conexión sin responder")
    return decode(line)
