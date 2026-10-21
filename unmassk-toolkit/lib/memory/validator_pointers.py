"""Pointer checks: Replaces/Origin must cite existing notes, and a new R must name its incident.

Re-exported by `validator.py`, plus the helpers that rebuild a relaunch command's answer flags."""

import re
import shlex

from model import Note, Rejection
import rejection as rejection_
from vocabulary import TYPES

# Shape of a note id (e.g. "D-030"), matched case-insensitively on the stripped pointer;
# a v1 commit hash never matches. The lookup in `known_ids` uses the raw value.
_NOTE_ID_PATTERN = re.compile(r"^[DMRQXIB]-\d+$", re.IGNORECASE)


def validate_pointers(
    note: Note,
    known_ids: frozenset[str],
    existing_in_zone: tuple[Note, ...] = (),
) -> Rejection | None:
    """Reject dangling Replaces/Origin ids, and an R without origin when the zone has candidate incidents."""
    missing = []
    if (
        note.replaces is not None
        and note.replaces != "none"
        and note.replaces not in known_ids
    ):
        missing.append(note.replaces)
    for pointer in note.origin:
        if _NOTE_ID_PATTERN.match(pointer.strip()) and pointer not in known_ids:
            missing.append(pointer)

    if missing:
        noun = "un identificador" if len(missing) == 1 else "identificadores"
        what = f"cita {noun} que no existe: {', '.join(missing)}"
        options = (
            "Los punteros (Replaces/Origin) tienen que apuntar a notas que existen de verdad.",
        )
        command = (
            f'gitmem note {note.type} --zones {note.zone1} {note.zone2} '
            f'"{note.headline}" --description "..."',
        )
        return rejection_.build(
            kind="dangling_pointer", what=what, options=options, command=command
        )

    if note.type == "R" and not note.origin:
        candidates = tuple(n for n in existing_in_zone if n.type == "I")
        if candidates:
            return _reject_restriction_without_incident(note, candidates)

    return None


def _reject_restriction_without_incident(
    note: Note, candidates: tuple[Note, ...]
) -> Rejection:
    """Reject an R with no origin, listing every candidate incident in its zone."""
    what = f"este muro nace sin decir de que incidencia sale, en [{note.zone1}][{note.zone2}]"
    options = [
        f"Al nacer un muro, la aduana presenta todas las incidencias candidatas de "
        f"[{note.zone1}][{note.zone2}] -- decide con calma cual, si alguna, la origina:",
        "",
    ]
    for candidate in candidates:
        options.append(
            f"  {candidate.id}   {candidate.timestamp.date().isoformat()}   "
            f"{candidate.headline}"
        )
    options.append("")
    options.extend(
        [
            "Dos salidas:",
            "",
            "  cita una o varias   --origin <id1> <id2> ...   el muro queda enlazado",
            "  ninguna encaja      --origin none               el muro nace sin incidencia",
        ]
    )
    first_id = candidates[0].id
    command = (
        f'gitmem note R --zones {note.zone1} {note.zone2} '
        f'"{note.headline}" --description "..." --origin {first_id}',
    )
    return rejection_.build(
        kind="restriction_without_incident", what=what, options=tuple(options), command=command
    )


def carry_answer_flags(note: Note, *, skip: frozenset[str] = frozenset()) -> str:
    """Return the answer flags `note` already carries for a relaunch command, minus those in ``skip``.

    ``--stops`` is derived from the type (R -> yes, M -> no); no value is ever invented."""
    parts = []
    if "--stops" not in skip and note.type in ("M", "R"):
        parts.append(f' --stops {"yes" if note.type == "R" else "no"}')
    if "--origin" not in skip and note.origin:
        parts.append(f" --origin {shlex.join(note.origin)}")
    if "--replaces" not in skip and note.replaces is not None:
        parts.append(f' --replaces {note.replaces}')
    if "--awaits" not in skip and note.awaits is not None and note.awaits.strip():
        parts.append(f" --awaits {shlex.quote(note.awaits)}")
    if "--keys" not in skip and note.keys:
        parts.append(f" --keys {shlex.join(note.keys)}")
    return "".join(parts)


def takes(note_type: str, field: str) -> bool:
    """Whether a note of ``note_type`` accepts ``field``."""
    spec = TYPES.get(note_type)
    return spec is not None and field in spec.allowed_fields


def why_flag(note: Note, target_type: str) -> str:
    """The given ``--why``, shell-quoted, when ``target_type`` takes it; else nothing."""
    given = note.why is not None and note.why.strip()
    return f" --why {shlex.quote(note.why)}" if given and takes(target_type, "why") else ""


def carry_accepted_flags(note: Note) -> str:
    """``carry_answer_flags`` plus ``--why``, limited to the fields ``note.type`` accepts; ``--replaces none`` fits every type."""
    skip = {f"--{field}" for field in ("origin", "awaits", "keys") if not takes(note.type, field)}
    if not takes(note.type, "replaces") and note.replaces != "none":
        skip.add("--replaces")
    return carry_answer_flags(note, skip=frozenset(skip)) + why_flag(note, note.type)


def description_flag(note: Note) -> str:
    """The given ``--description``, shell-quoted; the ``"..."`` hole only when none was given."""
    if note.description and note.description.strip():
        return f" --description {shlex.quote(note.description)}"
    return ' --description "..."'
