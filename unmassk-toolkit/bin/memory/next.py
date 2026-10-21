#!/usr/bin/env python3
"""`gitmem next`: write the session-close [NEXT] commit (headline plus prose context).

Usage: next.py "<headline>" --context "<prose>" [--keys k1 k2 ...]
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

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

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

    # The flag is required, but its value can still be blank: reject it.
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

    # Placeholder: the real timestamp is the commit's author date.
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
    except Exception as exc:  # never a stack trace
        print(f"next.py: {exc}", file=sys.stderr)
        sys.exit(1)
