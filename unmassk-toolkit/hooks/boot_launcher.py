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

    # Si este proyecto no ha pasado nunca por el instalador, se instala
    # AQUI, solo, antes de leer memoria [decision del propietario,
    # 2026-08-06: "yo solo tengo que entrar, decir buenos dias y que el me
    # diga lo que hay que hacer"].
    #
    # Por que aqui y no esperando a que alguien lo pida: sin instalador el
    # proyecto se queda a medias para siempre y NADA lo saca de ahi. Sin
    # `config.json` el sistema da por protegida la rama principal y rechaza
    # el primer commit de trabajo del dia -- medido sobre los 14
    # repositorios del propietario, 11 chocarian el primer dia. Sin los
    # ocho indices, sin `.gitignore` y sin el lanzador en el PATH, cada
    # sesion nueva vuelve a empezar de cero. El instalador es idempotente
    # (probado lanzandolo dos veces seguidas: mismo resultado, no duplica
    # nada) y nunca pisa una clave que ya exista.
    #
    # Se traga cualquier fallo, igual que todo lo demas de este fichero: la
    # memoria ayuda, nunca bloquea. Si la instalacion no sale, el arranque
    # sigue y el informe se escribe igual -- el hueco lo canta despues el
    # propio informe, que ya sabe decir que la memoria no esta montada.
    _INSTALLER = os.path.join(_TOOLKIT_ROOT, "bin", "git-memory-install.py")
    manifest = os.path.join(cwd, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest) and os.path.isfile(_INSTALLER):
        try:
            # encoding="utf-8", errors="replace": sin `encoding=`,
            # `text=True` decodifica con el codec de la consola (cp1252 en
            # Windows), y el instalador imprime emojis que no existen en
            # ese codec -- la decodificacion revienta en un hilo lector
            # aparte, fuera del alcance de este try/except [House,
            # 2026-08-08]. `errors="replace"` no es opcional: la salida del
            # instalador no la controlamos.
            done = subprocess.run(
                [sys.executable, _INSTALLER, "--auto"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=60,
                encoding="utf-8",
                errors="replace",
            )
            if done.returncode == 0:
                print(
                    "[memory] este proyecto no estaba instalado y se acaba de "
                    "instalar solo: gitmem en el PATH, los ocho indices y la "
                    "configuracion del repositorio."
                )
            else:
                print(
                    "[memory] este proyecto NO esta instalado y la instalacion "
                    "automatica ha fallado. Lanzala a mano:\n"
                    f"  python3 {_INSTALLER} --auto"
                )
        except Exception:
            pass

    # `flush` antes de ceder la salida al subproceso, y no es cosmetico:
    # `bin/memory/boot.py` escribe directo al descriptor real, mientras que
    # lo impreso aqui se queda en el buffer de Python hasta que el proceso
    # muere. Sin esto, el aviso de "se acaba de instalar solo" aterrizaba
    # DESPUES del informe entero -- justo la linea que explica por que ha
    # cambiado el proyecto, leida al final y fuera de contexto
    # [comprobado ejecutandolo, 2026-08-06].
    sys.stdout.flush()

    subprocess.run([sys.executable, _BOOT_SCRIPT], cwd=cwd)
except Exception:
    pass

sys.exit(0)
