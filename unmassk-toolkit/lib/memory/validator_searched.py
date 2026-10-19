"""La pregunta antes de guardar [D-098/D-124] -- partida fuera de
validator.py por tamano, mismo corte que `validator_zones.py`/
`validator_issue.py`/`validator_pointers.py`.

Sigue siendo una sola implementacion de "esto es valido": `validator.py`
importa estos nombres de forma PLANA y los reexpone bajo el mismo
nombre, asi que `validator.validate_searched`, `validator.carry_searched`,
etc. no cambian para nadie que los llame.

Puras: no abren ficheros ni llaman a git. No importa nada fuera de la
biblioteca estandar de Python y de sus hermanos de `lib/memory/`.
"""

import dataclasses
import shlex

from model import Rejection
import rejection as rejection_

# D-098/D-124: la pregunta antes de guardar, en palabras del propietario.
SEARCHED_QUESTION = "¿lo busqué y no está ya escrito ni es sentido común?"
SEARCHED_FLAG = "--searched"
SEARCHED_PLACEHOLDER = "<lo que busqué>: <lo que encontré>"


def searched_given(value: str | None) -> bool:
    """`--searched` contestado: cualquier texto no vacio vale [X-105:
    nadie comprueba QUE se busco]."""
    return value is not None and bool(value.strip())


def _without_searched(tokens: list[str]) -> list[str]:
    """`tokens` sin ninguna aparicion de `--searched` (forma `--searched X`
    o `--searched=X`) -- para que el relanzamiento no lleve dos."""
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
    """D-098: `gitmem note`/`gitmem rule` que guarda sin `--searched` con
    contenido rebota con la pregunta. `command_tokens` es el comando tal
    cual se tecleo (`["gitmem", "note", ...]`): el relanzamiento es ese
    mismo comando, cada valor intacto, mas `--searched`."""
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
    """` --searched '<respuesta>'` para pegar a un relanzamiento, o `""`
    si no se contesto."""
    if not searched_given(searched):
        return ""
    return f" {SEARCHED_FLAG} {shlex.quote(searched)}"


def carry_searched(r: Rejection, searched: str | None, prefix: str) -> Rejection:
    """Otro rechazo, ya contestado `--searched`: sus relanzamientos que
    empiezan por `prefix` lo arrastran, o obedecerlos rebota otra vez en
    D-098 y la respuesta se pierde."""
    suffix = searched_suffix(searched)
    if not suffix:
        return r
    relaunch = tuple(
        command + suffix if command.startswith(prefix) and SEARCHED_FLAG not in command else command
        for command in r.relaunch
    )
    return dataclasses.replace(r, relaunch=relaunch)
