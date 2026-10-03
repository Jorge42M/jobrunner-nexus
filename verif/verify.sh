#!/usr/bin/env bash
# Script de verificación de Nexus (Hito 1).
#
# Hace tres cosas y se detiene en el primer error:
#   1. Construye el proyecto (./build.sh).
#   2. Ejecuta todas las pruebas automatizadas (verif/tests).
#   3. Hace una prueba de humo: arranca el servicio real, usa el cliente
#      ./nexus como lo haría una persona y lo apaga con SIGTERM.
#
# Todo lo que se imprime también se guarda en verif/evidencia/ultima_verificacion.txt
#
# Uso:  ./verif/verify.sh
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
mkdir -p verif/evidencia
EVIDENCIA="verif/evidencia/ultima_verificacion.txt"
exec > >(tee "$EVIDENCIA") 2>&1   # duplica la salida: pantalla + archivo

echo "########## Verificación Nexus — $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "Commit: $(git rev-parse --short HEAD 2>/dev/null || echo 'sin git')"
echo "Sistema: $(uname -srm)"
echo

echo "########## 1/3 Construcción"
./build.sh
echo

echo "########## 2/3 Pruebas automatizadas"
python3 -m unittest discover -s verif/tests -t . -v
echo

echo "########## 3/3 Prueba de humo con el servicio real"
export NEXUS_HOME
NEXUS_HOME="$(mktemp -d)"   # carpeta temporal: no toca tus datos
SERVER_PID=""
limpiar() {
    if [ -n "$SERVER_PID" ] && kill -0 "$SERVER_PID" 2>/dev/null; then
        kill -TERM "$SERVER_PID"
        wait "$SERVER_PID" || true
    fi
    rm -rf "$NEXUS_HOME"
}
trap limpiar EXIT

./nexus serve --kill-grace 1 > "$NEXUS_HOME/servicio.log" 2>&1 &
SERVER_PID=$!
for _ in $(seq 50); do ./nexus ping >/dev/null 2>&1 && break; sleep 0.1; done
./nexus ping

paso() { echo; echo "\$ ./nexus $*"; ./nexus "$@"; }
esperar_estado() {  # esperar_estado ID ESTADO
    for _ in $(seq 100); do
        ./nexus status "$1" | grep -q "estado      : $2" && return 0
        sleep 0.1
    done
    echo "FALLO: el trabajo $1 no llegó a $2"; exit 1
}

paso submit echo "hola desde nexus"
paso wait 1
paso output 1

paso submit ls /directorio/que/no/existe
paso wait 2

paso submit comando_que_no_existe
paso wait 3

echo; echo "\$ ./nexus submit \"echo 'comillas sin cerrar\"   (se espera un error)"
if ./nexus submit "echo 'comillas sin cerrar"; then
    echo "FALLO: el comando inválido fue aceptado"; exit 1
fi

paso submit sleep 30
esperar_estado 4 RUNNING
paso cancel 4
paso wait 4

paso list
paso status 4

echo; echo "Comprobando estados finales esperados..."
./nexus status 1 | grep -q "estado      : SUCCEEDED"
./nexus status 2 | grep -q "estado      : FAILED"
./nexus status 3 | grep -q "código      : 127"
./nexus status 4 | grep -q "estado      : CANCELED"
paso ping
echo "El servicio sigue vivo después de las peticiones inválidas."

echo; echo "Deteniendo el servicio con SIGTERM (pid $SERVER_PID)..."
kill -TERM "$SERVER_PID"
wait "$SERVER_PID"
echo "Código de salida del servicio: $?"
SERVER_PID=""
echo "--- registro del servicio ---"
cat "$NEXUS_HOME/servicio.log"

echo
echo "########## RESULTADO: VERIFICACIÓN EXITOSA"
