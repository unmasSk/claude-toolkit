#!/usr/bin/env python3
"""`gitmem rule`: add, retract or replace a working rule, or print the rules file.

    rule.py "<text>" [--kind <user|claude>] --quote "<literal words>"|none --searched "..."
    rule.py
    rule.py --retract "<exact text>" --kind <user|claude>
    rule.py "<new text>" --replaces "<old text>" --kind <user|claude> [--quote ...] --searched "..."

`--kind` defaults to "user" only when adding; retract and replace require it.
"""

import argparse
import os
import shlex
import sys

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

force_utf8_streams()

import rejection as rejection_  # noqa: E402
import rules as rules_lib  # noqa: E402
import validator  # noqa: E402
from emojis import CHANNEL_EMOJI  # noqa: E402
# Single words that read the rules, or that are rejected as not a rule.
from save_command import RULE_NOT_A_RULE_WORDS, RULE_READ_WORDS  # noqa: E402

_DEFAULT_KIND = "user"


def _parse_args(argv):
    parser = argparse.ArgumentParser(prog="rule.py")
    parser.add_argument("text", nargs="?", default=None)
    parser.add_argument("--kind", choices=("user", "claude"), default=None)
    parser.add_argument("--quote", default=None)
    parser.add_argument("--retract", default=None)
    parser.add_argument("--replaces", default=None)
    # Required when saving; enforced in main() so the rejection shows the question.
    parser.add_argument("--searched", default=None)
    return parser.parse_args(argv)


def _cmd_read():
    print(rules_lib.read_all(), end="")
    return 0


def _render_similar_rejection(candidates, kind, text, quote, searched):
    """Render the near-duplicate rejection: each candidate with its own owner, plus a relaunch."""
    emoji = CHANNEL_EMOJI["rule"]
    relaunch = f'gitmem rule "..." --kind {kind}'
    if quote is not None:
        relaunch += f" --quote {shlex.quote(quote)}"
    relaunch += validator.searched_suffix(searched)
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
            f"                    {relaunch}",
        ]
    )
    return "\n".join(lines)


def _print_rejection(one_rejection, searched):
    """Print a rejection whose relaunches carry the given `--searched` answer."""
    print(rejection_.render_terminal(validator.carry_searched(one_rejection, searched, "gitmem rule ")))


def _searched_rejection(args, argv):
    """Print the `--searched` rejection if the answer is missing; return True if rejected."""
    rejection = validator.validate_searched(args.searched, ["gitmem", "rule", *argv])
    if rejection is None:
        return False
    print(rejection_.render_terminal(rejection))
    return True


def _cmd_add(text, kind, quote, searched):
    similar = rules_lib.similar_existing(text)
    # Reject only on a same-owner near duplicate, but show every candidate.
    if any(existing_kind == kind for existing_kind, _ in similar):
        print(_render_similar_rejection(similar, kind, text, quote, searched))
        return 1

    result = rules_lib.add(text, kind, quote=quote, searched=searched)
    if not result.ok:
        if result.rejections:
            for one_rejection in result.rejections:
                _print_rejection(one_rejection, searched)
            return 1
        # git may fail with no output; never print an empty detail.
        detalle = result.git_error or "git no dio detalle"
        print(f"git fallo al guardar la regla: {detalle}", file=sys.stderr)
        return 1

    emoji = CHANNEL_EMOJI["rule"]
    print(f"{emoji} regla guardada — [{kind}] {text}")
    return 0


_KIND_REQUIRED_MSG = (
    "❌ {flag} necesita --kind <user|claude> de forma explicita -- a "
    "diferencia del alta, aqui no hay valor por defecto."
)

_NEW_TEXT_REQUIRED_MSG = (
    "❌ --replaces necesita el texto NUEVO de la regla como posicional -- "
    "gitmem rule \"<texto nuevo>\" --replaces \"<texto viejo>\" --kind <user|claude>."
)


def _cmd_retract(text, kind):
    if kind is None:
        print(_KIND_REQUIRED_MSG.format(flag="--retract"), file=sys.stderr)
        return 1

    result = rules_lib.retract(text, kind)
    if not result.ok:
        if result.rejections:
            for one_rejection in result.rejections:
                print(rejection_.render_terminal(one_rejection))
            return 1
        detalle = result.git_error or "git no dio detalle"
        print(f"git fallo al retirar la regla: {detalle}", file=sys.stderr)
        return 1

    emoji = CHANNEL_EMOJI["rule"]
    print(f"{emoji} regla retirada — [{kind}] {text}")
    return 0


def _cmd_replace(new_text, old_text, kind, quote, searched):
    if new_text is None:
        print(_NEW_TEXT_REQUIRED_MSG, file=sys.stderr)
        return 1
    if kind is None:
        print(_KIND_REQUIRED_MSG.format(flag="--replaces"), file=sys.stderr)
        return 1

    result = rules_lib.replace(old_text, new_text, kind, quote=quote, searched=searched)
    if not result.ok:
        if result.rejections:
            for one_rejection in result.rejections:
                _print_rejection(one_rejection, searched)
            return 1
        detalle = result.git_error or "git no dio detalle"
        print(f"git fallo al sustituir la regla: {detalle}", file=sys.stderr)
        return 1

    emoji = CHANNEL_EMOJI["rule"]
    print(f"{emoji} regla sustituida — [{kind}] {old_text} → {new_text}")
    return 0


def main(argv):
    args = _parse_args(argv)
    if args.retract is not None:
        return _cmd_retract(args.retract, args.kind)
    if args.replaces is not None:
        if _searched_rejection(args, argv):
            return 1
        return _cmd_replace(args.text, args.replaces, args.kind, args.quote, args.searched)
    if args.text is not None:
        palabra = args.text.strip().lower()
        if palabra in RULE_READ_WORDS:
            args.text = None
    if args.text is None:
        return _cmd_read()
    if args.text.strip().lower() in RULE_NOT_A_RULE_WORDS:
        print(
            f"❌ \"{args.text}\" no se ha guardado: es una palabra suelta, no una regla.\n"
            "   Para LEER tus reglas:      gitmem rule\n"
            "   Para guardar una nueva:    gitmem rule \"<la regla entera, en una frase>\""
        )
        return 1
    if _searched_rejection(args, argv):
        return 1
    kind = args.kind or _DEFAULT_KIND
    return _cmd_add(args.text, kind, args.quote, args.searched)


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        print(f"rule.py: {exc}", file=sys.stderr)
        sys.exit(1)
