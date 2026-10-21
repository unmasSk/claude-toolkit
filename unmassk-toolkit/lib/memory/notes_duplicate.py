"""Handle an id carried by several live lines of its index at once.

remove, replace and promote refuse and list each note with its commit;
`remove --commit <sha>` picks one by full sha or unique prefix."""

from collections.abc import Callable

import query
import rejection as rejection_
from model import IndexLine, Note, Rejection

SHORT_SHA = 10
_MIN_PREFIX = 4  # shortest sha prefix git accepts


def sha_matches(sha: str | None, commit: str) -> bool:
    """True if `commit` is `sha` or a prefix of it at least `_MIN_PREFIX` long."""
    prefix = commit.strip().lower()
    return bool(sha) and len(prefix) >= _MIN_PREFIX and sha.lower().startswith(prefix)


def remove_relaunch(note_id: str, reason: str = '"<motivo>"') -> Callable[[str], str]:
    """Build the ready-to-paste `gitmem remove <id> <reason> --commit <sha>` for a sha."""
    return lambda sha: f"gitmem remove {note_id} {reason} --commit {sha}"


def same_note(note: Note, line: IndexLine) -> bool:
    """True if `line` is `note`'s index line: same headline and zones."""
    return (note.headline, note.zone1, note.zone2) == (line.headline, line.zone1, line.zone2)


def with_commits(note_id: str, lines: list[IndexLine]) -> list[tuple[IndexLine, str | None]]:
    """Pair each line with its note's commit sha, or `None` if none matches.

    Matches on headline and zones first, then on headline only; each commit
    is assigned to one line at most.
    """
    unused = list(query.commits_by_id(note_id))
    shas: list[str | None] = [None] * len(lines)
    for matches in (same_note, lambda note, line: note.headline == line.headline):
        for i, line in enumerate(lines):
            if shas[i] is not None:
                continue
            match = next((pair for pair in unused if matches(pair[1], line)), None)
            if match is not None:
                unused.remove(match)
                shas[i] = match[0]
    return list(zip(lines, shas))


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
    """The single live line of `note_id` in `lines`, or the rejection explaining why not.

    `(None, None)` when there is none and no `commit` was given.
    """
    matches = [line for line in lines if line.id == note_id]
    if commit is None and len(matches) <= 1:
        return (matches[0] if matches else None), None
    paired = with_commits(note_id, matches)
    if commit is None:
        what = f"{note_id} lo llevan {len(matches)} notas vivas a la vez"
        return None, _rejection(what, paired, relaunch_for)
    chosen = [line for line, sha in paired if sha_matches(sha, commit)]
    if len(chosen) == 1:
        return chosen[0], None
    what = f"--commit {commit} no señala una sola nota viva con el numero {note_id}"
    return None, _rejection(what, paired, relaunch_for)
