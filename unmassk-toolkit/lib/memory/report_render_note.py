"""Render the report of a single note looked up by id (used by `gitmem search --id`).

Paints what `report.build_note()` already resolved; reads nothing on its own.
"""

from emojis import TYPE_EMOJI
from model import Note, NoteReport
from report_render import DIVIDER, THIN_DIVIDER, header_line, utc_label
from vocabulary import TYPE_SPANISH_NAME

_FIELD_GAP = 2  # minimum gap between the longest label and its value
_BODY_INDENT = "    "  # 4 spaces


def _note_fields(note: Note) -> list[str]:
    """Labelled note fields: Why/Description/Keys/Quote aligned, awaits/Issue with one space; empty fields skipped."""
    aligned: list[tuple[str, str]] = []
    if note.why:
        aligned.append(("Why", note.why))
    aligned.append(("Description", note.description))
    if note.keys:
        aligned.append(("Keys", ", ".join(note.keys)))
    if note.quote:
        aligned.append(("Quote", note.quote))

    width = max(len(label) for label, _ in aligned) + _FIELD_GAP
    lines = [
        f"{_BODY_INDENT}{label}{' ' * (width - len(label))}{value}"
        for label, value in aligned
    ]

    if note.type == "B" and note.awaits:
        lines.append(f"{_BODY_INDENT}awaits: {note.awaits}")
    if note.issue is not None:
        lines.append(f"{_BODY_INDENT}Issue: #{note.issue}")
    return lines


def _replaces_line(note: Note) -> list[str]:
    """Return the `sustituye a {old_id}` line, or nothing when there is no replaced note."""
    if not note.replaces or note.replaces == "none":
        return []
    return [f"{_BODY_INDENT}sustituye a {note.replaces}"]


def _child_status(child: Note, archived_ids: frozenset) -> str:
    """Return the child's status: descartada (type X), archivada or vigente."""
    if child.type == "X":
        return "descartada"
    if child.id in archived_ids:
        return "archivada"
    return "vigente"


def _cluster_lines(report: NoteReport) -> list[str]:
    """Render the block of notes pointing to this one; nothing when there is no cluster."""
    if report.cluster is None:
        return []
    root_id = report.note.id
    lines = ["", THIN_DIVIDER, "  LO QUE CUELGA DE ELLA", ""]
    for child in report.cluster.children:
        status = _child_status(child, report.cluster.archived_ids)
        lines.append(
            f"  {TYPE_EMOJI[child.type]} {child.id}  {child.headline}  "
            f"{status} · nace de {root_id}"
        )
    return lines


def render_note(report: NoteReport) -> str:
    """Render the full report of one note."""
    note = report.note
    status = "archivada" if report.archived else "vigente"

    lines = [
        DIVIDER,
        header_line(
            f"  {note.id} · {TYPE_SPANISH_NAME[note.type]} · {status}",
            utc_label(report.generated_at),
        ),
        DIVIDER,
        "",
        f"{TYPE_EMOJI[note.type]}  {note.headline}",
        header_line(
            f"{_BODY_INDENT}[{note.zone1}] [{note.zone2}]",
            f"escrita {note.timestamp:%Y-%m-%d}",
        ),
        "",
    ]
    lines.extend(_note_fields(note))
    lines.extend(_replaces_line(note))
    lines.extend(_cluster_lines(report))
    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(f"  La zona entera:   gitmem search {note.zone1}")
    return "\n".join(lines)
