"""Render one note (id + headline line, then its fields) for each note type.

Shared by `report_render.py` and `report_render_chain.py`; imports neither.
"""

from model import Note


def _status_suffix(note: Note, archived: bool) -> str:
    """Suffix for the note's own line: `archivada` and/or `(↺ old_id)`, or "" when neither applies."""
    parts: list[str] = []
    if archived:
        parts.append("archivada")
    if note.replaces and note.replaces != "none":
        parts.append(f"(↺ {note.replaces})")
    if not parts:
        return ""
    return "  " + "  ".join(parts)


def restriction_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [
        f"{marker}{note.id}  [{note.zone1}][{note.zone2}]  {note.headline}"
        f"{_status_suffix(note, archived)}"
    ]
    if note.why:
        lines.append(f"         Why: {note.why}")
    if note.origin:
        lines.append(f"         Origin: {', '.join(note.origin)}")
    if note.keys:
        lines.append(f"         Keys: {', '.join(note.keys)}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def blocker_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [
        f"{marker}{note.id}  [{note.zone1}][{note.zone2}]  {note.headline}"
        f"{_status_suffix(note, archived)}"
    ]
    if note.awaits:
        lines.append(f"         awaits: {note.awaits}")
    lines.append(f"         Description: {note.description}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def decision_block(note: Note, marker: str, archived: bool) -> list[str]:
    """A single D/X note outside a cluster (used by `render_word`)."""
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.why:
        lines.append(f"         Why: {note.why}")
    if note.origin:
        lines.append(f"         Origin: {', '.join(note.origin)}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def memo_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def incident_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


def question_block(note: Note, marker: str, archived: bool) -> list[str]:
    lines = [f"{marker}{note.id}  {note.headline}{_status_suffix(note, archived)}"]
    if note.description:
        lines.append(f"         {note.description}")
    if note.issue is not None:
        lines.append(f"         Issue: #{note.issue}")
    return lines


# Note type -> block renderer; X shares the decision block.
BLOCK_BY_TYPE = {
    "R": restriction_block,
    "B": blocker_block,
    "D": decision_block,
    "X": decision_block,
    "M": memo_block,
    "I": incident_block,
    "Q": question_block,
}
