"""Utilidades compartidas por las pruebas."""

import os
import sys

# Permite importar el paquete "nexus" desde src/ sin instalarlo.
SRC = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)
