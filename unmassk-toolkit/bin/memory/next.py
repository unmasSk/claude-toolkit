#!/usr/bin/env python3
"""bin/memory/next.py -- el [NEXT] del cierre de sesion: un commit
GENUINAMENTE vacio, sin zonas, sin identificador, sin linea de indice y
sin lapida [spec-sistema-memoria-v2.md Sec.9].

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `next.py`, renombrada
desde `context.py` -- decision del propietario, 2026-08-03: "el comando
escribe el cierre de sesion, y lo que importa de el es el Next").
Subcomando `next`.

Grammar de CLI (ASUNCION, sin fuente literal en TEXTOS.md para este
script -- ver el docstring de test_next_script.py, que la fija por
consistencia con `--zones`/`--description` de `note.py`, donde un campo
de texto libre obligatorio va por flag aunque no sea opcional):

    next.py "<titular>" --context "<resumen en prosa>" [--keys k1 k2 ...]

`context.write()` (modulo `lib/memory/context.py`, sin renombrar -- solo
cambian el script y el subcomando, PIEZAS.md Sec.10) es la unica
escritura del sistema exenta de aduana a proposito [docstring del
modulo: "sin candado, sin aduana, sin indice"] -- por eso este script no
arma ningun `Context` del validador ni llama a `validate_note`: no hay
nada que validar.

**El cuerpo es prosa corrida, no una lista de puntos** [decision del
propietario, 2026-08-03, COLA.md Sec.5]: `--context` reemplaza al
`--point` repetible de antes -- `ContextNote.context` es una unica
cadena (posiblemente multilinea), nunca una tupla de puntos.
"""

import argparse
import os
import sys
from datetime import datetime, timezone

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import context as context_lib  # noqa: E402
import emojis  # noqa: E402
from model import ContextNote  # noqa: E402


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="next.py")
    parser.add_argument("headline")
    parser.add_argument("--context", required=True, dest="context_prose")
    parser.add_argument("--keys", nargs="+", default=())
    return parser.parse_args(argv)


def main(argv):
    args = _parse_args(argv)

    # `--context` obligatorio solo garantiza que la BANDERA venga; no que
    # traiga nada dentro. Y un cierre con el cuerpo vacio se guardaba
    # diciendo que todo fue bien: la unica constancia de lo hablado en toda
    # la sesion, perdida sin un aviso [hallazgo de Argus, 2026-08-05].
    #
    # No es aduana -- este commit sigue exento de validar la nota. Es que
    # un campo vacio no es una nota corta: es la ausencia del unico
    # contenido que este comando existe para escribir.
    if not args.context_prose.strip():
        print(
            "⛔ CIERRE RECHAZADO — el contexto viene vacio\n\n"
            "El titular dice que hacer manana; el contexto es lo que se\n"
            "hablo hoy, y no vive en ningun otro sitio. Sin el, el cierre\n"
            "no guarda nada que no dijeran ya los commits.\n\n"
            "Relanza con el resumen dentro:\n"
            f'  gitmem next "{args.headline}" --context "$(cat <fichero>)"',
            file=sys.stderr,
        )
        return 1

    # El timestamp real lo pone git (fecha de autor del commit); este
    # valor es un marcador de posicion que `format.build_context_message`
    # ni siquiera escribe en el texto -- mismo trato que `Note.timestamp`
    # en `note.py` [context.py, docstring: "el [NEXT] reconstruye el
    # timestamp real de git" al LEER, no al escribir].
    note = ContextNote(
        headline=args.headline,
        context=args.context_prose,
        keys=tuple(args.keys),
        timestamp=datetime.now(timezone.utc),
    )

    result = context_lib.write(note)
    if not result.ok:
        print(f"git fallo al cerrar la sesion: {result.git_error}", file=sys.stderr)
        return 1

    print(f"[NEXT] {emojis.CHANNEL_EMOJI['next']} {args.headline}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"next.py: {exc}", file=sys.stderr)
        sys.exit(1)
