#!/usr/bin/env bash
# "Construye" Nexus: comprueba la versión de Python y compila todos los
# módulos a bytecode tratando cualquier advertencia como error.
# Python no genera un ejecutable binario; compilar sirve para detectar
# errores de sintaxis antes de ejecutar.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "==> Comprobando Python 3.8 o superior"
python3 -c 'import sys; assert sys.version_info >= (3, 8), sys.version; print("    " + sys.version.split()[0])'

echo "==> Comprobando que sqlite3 está disponible"
python3 -c 'import sqlite3; print("    SQLite " + sqlite3.sqlite_version)'

echo "==> Compilando src/ (advertencias = error)"
python3 -W error -m compileall -q src

echo "==> Construcción correcta. Ejecuta:  ./nexus serve"
