#!/usr/bin/env python3
"""bin/memory/rule.py -- da de alta una regla de trabajo (remember), o
imprime el fichero de reglas entero.

Contrato: docs/memoria-v2/PIEZAS.md Sec.10 (fila `rule.py`). Llama a UNA
funcion de la libreria por modo (`rules.add`, `rules.read_all`) e imprime
lo que devuelve -- toda la logica vive en `lib/memory/rules.py`, nunca
aqui [PIEZAS.md Sec.10, regla comun a los once scripts].

Grammar de CLI [TEXTOS.md Sec.1.2, literal repetido: `gitmem rule "..."`;
`lib/memory/rules.py`, docstring y `_reject_invalid_kind`: "con el tipo
explicito, `gitmem rule "<texto>" --kind <user|claude>`". El modo lectura
(sin texto) es ASUNCION documentada -- ver el docstring de
test_rule_script.py, que la fija por simetria con como argparse ya trata
un posicional opcional en el resto del sistema, antes de que este
fichero existiera]:

    rule.py "<texto>" [--kind <user|claude>]      # anade, confirma
    rule.py                                       # imprime rules.md entero

`--kind` por defecto es "user" cuando se anade una regla sin el flag
[ASUNCION -- ningun texto del proyecto fija un valor por defecto para el
literal sin `--kind`, `gitmem rule "..."`, que aparece en el rechazo de
zona en lista negra (TEXTOS.md Sec.1.2) dirigido a la persona en el
chat, no a Claude]. Documentado aqui para que se pueda revocar sin
arqueologia.
"""

import argparse
import os
import sys

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import tras sys.path)

force_utf8_streams()

import rejection as rejection_  # noqa: E402
import rules as rules_lib  # noqa: E402
from emojis import CHANNEL_EMOJI  # noqa: E402

_DEFAULT_KIND = "user"


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="rule.py")
    parser.add_argument("text", nargs="?", default=None)
    parser.add_argument("--kind", choices=("user", "claude"), default=None)
    return parser.parse_args(argv)


def _cmd_read():
    print(rules_lib.read_all(), end="")
    return 0


def _render_similar_rejection(candidates, kind, text):
    """El rechazo literal de TEXTOS.md Sec.1.11b, con las candidatas reales
    de `rules.similar_existing()` y la regla que se iba a guardar. No pasa
    por `rejection.build()`/`render_terminal()`: esa tuberia siempre
    antepone el emoji `TYPE_EMOJI["B"]` (``⛔``) al titulo, y Sec.1.11b usa
    ``❌`` -- mismo patron ya usado en este mismo directorio para un
    rechazo que tampoco encaja en esa forma (`zones.py`, ya alta / ya
    alias). Cada candidata sale con SU dueno real (`kind` del propio
    `_RuleMatch`), nunca el de la regla nueva -- lo que
    `test_the_script_never_swaps_the_owner_of_two_near_duplicate_rules`
    verifica.
    """
    emoji = CHANNEL_EMOJI["rule"]
    lines = ["❌ REGLA NO GUARDADA — ya tienes una que dice casi lo mismo", ""]
    for existing_kind, existing_text in candidates:
        lines.append(f"  {emoji} [{existing_kind}] {existing_text}")
    lines.extend(
        [
            "",
            "Lo que ibas a guardar:",
            "",
            f"  {emoji} [{kind}] {text}",
            "",
            "Se queda una. Las reglas se entregan **todas juntas** cada vez que las",
            "pides, así que dos versiones de la misma no añaden nada: solo hacen la",
            "lista más larga y más difícil de obedecer.",
            "",
            "Dos salidas:",
            "",
            "  no hagas nada     la que ya tenías sigue vigente y vale",
            "  reescríbela       si de verdad dicen cosas distintas, que se note:",
            '                    gitmem rule "..."',
        ]
    )
    return "\n".join(lines)


def _cmd_add(text, kind):
    similar = rules_lib.similar_existing(text)
    # El rechazo solo dispara si la casi-duplicada es del MISMO dueno --
    # `rules.similar_existing()` (docstring, endurecimiento 2026-08-04):
    # "una regla [user] y una [claude] con el mismo texto NO son la misma
    # regla". Una vez dispara, se ensena la lista ENTERA que devolvio la
    # libreria (cualquier dueno), no solo la que lo disparo -- es la misma
    # foto completa que ya usa el rechazo por pisar contenido (TEXTOS.md
    # Sec.1.6): ver las dos juntas es lo que permite juzgar si de verdad
    # dicen cosas distintas.
    if any(existing_kind == kind for existing_kind, _ in similar):
        print(_render_similar_rejection(similar, kind, text))
        return 1

    result = rules_lib.add(text, kind)
    if not result.ok:
        if result.rejections:
            for one_rejection in result.rejections:
                print(rejection_.render_terminal(one_rejection))
            return 1
        print(f"git fallo al guardar la regla: {result.git_error}", file=sys.stderr)
        return 1

    emoji = CHANNEL_EMOJI["rule"]
    print(f"{emoji} regla guardada — [{kind}] {text}")
    return 0


def main(argv):
    args = _parse_args(argv)
    if args.text is None:
        return _cmd_read()
    kind = args.kind or _DEFAULT_KIND
    return _cmd_add(args.text, kind)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # nunca una traza de pila -- PIEZAS.md Sec.10
        print(f"rule.py: {exc}", file=sys.stderr)
        sys.exit(1)
