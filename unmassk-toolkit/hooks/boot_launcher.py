#!/usr/bin/env python3
"""hooks/boot_launcher.py -- SessionStart: lanza bin/memory/boot.py.

Contrato: docs/memoria-v2/PIEZAS.md Sec.11, fila `boot_launcher.py`:
"~20 lineas sin logica: llama a bin/memory/boot.py". Se escribe una vez
y no se itera jamas -- corre desde la copia instalada del plugin, y
toda decision real (que se enseña, en que orden, que pasa en un
proyecto recien instalado o en una rama sin un solo commit) vive en
bin/memory/boot.py / lib/memory/boot.py, nunca aqui.

Resuelve el repositorio con `payload["cwd"]` si esta presente -- mismo
patron que ya usa hooks/pre-merge-gate.py ("prefer an explicit cwd in
the hook payload... fall back to the hook process's own working
directory") -- y con el cwd heredado del proceso en caso contrario.
Ningun documento fija cual de los dos manda; las dos son plausibles, y
un test entra solo si compara dos cosas escritas por separado -- afirmar
una de las dos aqui seria fijar una decision que no es de este fichero.

Un fallo de arranque nunca bloquea la sesion -- la memoria ayuda, nunca
bloquea (mismo principio que ya declara hooks/session-start-boot.py:
"Exit codes: 0: Always (never blocks session start)"). Toda excepcion
-- boot.py falla, el directorio no existe, stdin viene vacio o mal
formado -- se traga en silencio; la sesion arranca igual.
"""

import json
import os
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(_HOOKS_DIR)
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

_BOOT_SCRIPT = os.path.join(_TOOLKIT_ROOT, "bin", "memory", "boot.py")

try:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw else {}
    except ValueError:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()

    subprocess.run([sys.executable, _BOOT_SCRIPT], cwd=cwd)
except Exception:
    pass

sys.exit(0)
