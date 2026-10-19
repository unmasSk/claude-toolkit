"""Un id que llevan varias lineas vivas de su indice a la vez (D-145).

remove, replace y promote no eligen por su cuenta: se niegan listando cada
nota con su commit y su titular, sin tocar nada; `remove --commit <sha>`
elige una, por el sha entero o por un prefijo unico, como git.

No importa nada fuera de la biblioteca estandar de Python. Imports planos
entre hermanos de `lib/memory/`.
"""

from collections.abc import Callable

import query
import rejection as rejection_
from model import IndexLine, Rejection

SHORT_SHA = 10
_MIN_PREFIX = 4  # el minimo que git acepta como prefijo de un sha


def sha_matches(sha: str | None, commit: str) -> bool:
    """`True` si `commit` es el sha entero de `sha` o un prefijo suyo de al
    menos `_MIN_PREFIX` caracteres.
    """
    prefix = commit.strip().lower()
    return bool(sha) and len(prefix) >= _MIN_PREFIX and sha.lower().startswith(prefix)


def _with_commits(note_id: str, lines: list[IndexLine]) -> list[tuple[IndexLine, str | None]]:
    """Cada linea con el sha del commit de su nota (mismo id y titular), o
    `None` si ninguno casa. Un commit se asigna a una sola linea, asi dos
    lineas con el mismo titular reciben dos commits distintos.
    """
    unused = list(query.commits_by_id(note_id))
    paired: list[tuple[IndexLine, str | None]] = []
    for line in lines:
        match = next((pair for pair in unused if pair[1].headline == line.headline), None)
        if match is not None:
            unused.remove(match)
        paired.append((line, match[0] if match else None))
    return paired


def _rejection(
    what: str, paired: list[tuple[IndexLine, str | None]], relaunch_for: Callable[[str], str]
) -> Rejection:
    listed = tuple(
        f"  {sha[:SHORT_SHA] if sha else '(sin commit)':<{SHORT_SHA}}  {line.headline}"
        for line, sha in paired
    )
    options = (
        "Las notas que llevan ese numero, con el commit que escribio cada una:",
        "",
        *listed,
        "",
        "No se elige ninguna a ciegas. Elige cual con --commit <sha> (vale un",
        "prefijo unico del sha, como en git).",
    )
    commands = tuple(relaunch_for(sha[:SHORT_SHA]) for _line, sha in paired if sha)
    return rejection_.build(
        kind="duplicate_id",
        what=what,
        options=options,
        command=commands or (relaunch_for("<sha>"),),
    )


def pick(
    note_id: str,
    lines: tuple[IndexLine, ...],
    commit: str | None,
    relaunch_for: Callable[[str], str],
) -> tuple[IndexLine | None, Rejection | None]:
    """La unica linea viva de `note_id` en `lines`, o el rechazo que lo
    explica. `(None, None)` si no hay ninguna y no se dio `commit`: quien
    llama sigue con su propio fallo de "no esta".
    """
    matches = [line for line in lines if line.id == note_id]
    if commit is None and len(matches) <= 1:
        return (matches[0] if matches else None), None
    paired = _with_commits(note_id, matches)
    if commit is None:
        what = f"{note_id} lo llevan {len(matches)} notas vivas a la vez"
        return None, _rejection(what, paired, relaunch_for)
    chosen = [line for line, sha in paired if sha_matches(sha, commit)]
    if len(chosen) == 1:
        return chosen[0], None
    what = f"--commit {commit} no señala una sola nota viva con el numero {note_id}"
    return None, _rejection(what, paired, relaunch_for)
