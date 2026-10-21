"""Render a chain report as text (`gitmem search --chain`).

Ancestors are struck through with `~~`; a head is tagged `cerrada` or `sustituida por <id>`.
"""

from model import ChainReport, ChainThread, Note
from report_render import DIVIDER, NO_MARK, THIN_DIVIDER, header_line, utc_label
from report_render_blocks import BLOCK_BY_TYPE

_STRIKE = "~~"


def _note_block(note: Note, closed: bool, replaced_by: str | None = None) -> list[str]:
    """The note's type block, its first line tagged `cerrada` or else `sustituida por <id>`, never both."""
    block_fn = BLOCK_BY_TYPE[note.type]
    lines = list(block_fn(note, NO_MARK, False))
    if closed:
        lines[0] = f"{lines[0]}  cerrada"
    elif replaced_by is not None:
        lines[0] = f"{lines[0]}  sustituida por {replaced_by}"
    return lines


def _render_thread(thread: ChainThread) -> list[str]:
    """The head followed by its struck-through ancestors, in the order given."""
    lines = _note_block(thread.head, closed=thread.closed, replaced_by=thread.replaced_by)
    for ancestor in thread.ancestors:
        ancestor_lines = _note_block(ancestor, closed=False)
        ancestor_lines[0] = f"{_STRIKE}{ancestor_lines[0]}{_STRIKE}"
        lines.extend(ancestor_lines)
    return lines


def render_chain(report: ChainReport) -> str:
    """The whole chain view: one head per thread, its ancestors below."""
    lines = [DIVIDER]
    lines.append(
        header_line(
            f"  CADENA «{report.query}» · {len(report.threads)} hilos",
            utc_label(report.generated_at),
        )
    )
    lines.append(DIVIDER)

    if not report.threads:
        lines.append("")
        lines.append("  Ninguna nota de esta zona o palabra tiene cadena que mostrar.")
        lines.append(DIVIDER)
        return "\n".join(lines)

    for thread in report.threads:
        lines.append("")
        lines.extend(_render_thread(thread))

    lines.append("")
    lines.append(THIN_DIVIDER)
    lines.append(f"  Vista normal, sin cadena:   gitmem search «{report.query}»")
    return "\n".join(lines)
