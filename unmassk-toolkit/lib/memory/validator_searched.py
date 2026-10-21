"""`--searched` validation: the question asked before saving a note or rule.

Re-exported by validator.py under the same names. Pure: no file or git access.
"""

import dataclasses
import shlex

from model import Rejection
import rejection as rejection_

SEARCHED_QUESTION = "¿lo busqué y no está ya escrito ni es sentido común?"
SEARCHED_FLAG = "--searched"
SEARCHED_PLACEHOLDER = "<lo que busqué>: <lo que encontré>"


def searched_given(value: str | None) -> bool:
    """True when `--searched` holds any non-blank text."""
    return value is not None and bool(value.strip())


def _without_searched(tokens: list[str]) -> list[str]:
    """Return `tokens` without any `--searched X` or `--searched=X`."""
    out = []
    skip_next = False
    for token in tokens:
        if skip_next:
            skip_next = False
            continue
        if token == SEARCHED_FLAG:
            skip_next = True
            continue
        if token.startswith(SEARCHED_FLAG + "="):
            continue
        out.append(token)
    return out


def validate_searched(searched: str | None, command_tokens: list[str]) -> Rejection | None:
    """Reject a save without `--searched`; the relaunch is `command_tokens` plus the flag."""
    if searched_given(searched):
        return None
    relaunch = shlex.join(_without_searched(list(command_tokens)) + [SEARCHED_FLAG, SEARCHED_PLACEHOLDER])
    options = (
        "Antes de guardar, contesta:",
        "",
        f"  {SEARCHED_QUESTION}",
        "",
        f"Busca en la memoria y di con {SEARCHED_FLAG} lo que buscaste y lo que encontraste,",
        'p. ej. --searched \'busqué "squash": encontré D-057\'.',
    )
    return rejection_.build(
        kind="missing_searched",
        what=f"falta {SEARCHED_FLAG}: no consta que lo buscaras antes de guardarlo",
        options=options,
        command=(relaunch,),
    )


def searched_suffix(searched: str | None) -> str:
    """Return ` --searched '<answer>'` to append to a relaunch, or `""` if unanswered."""
    if not searched_given(searched):
        return ""
    return f" {SEARCHED_FLAG} {shlex.quote(searched)}"


def carry_searched(r: Rejection, searched: str | None, prefix: str) -> Rejection:
    """Append the given `--searched` answer to `r`'s relaunches that start with `prefix`."""
    suffix = searched_suffix(searched)
    if not suffix:
        return r
    relaunch = tuple(
        command + suffix if command.startswith(prefix) and SEARCHED_FLAG not in command else command
        for command in r.relaunch
    )
    return dataclasses.replace(r, relaunch=relaunch)
