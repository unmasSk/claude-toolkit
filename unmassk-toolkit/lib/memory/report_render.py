"""Render a zone report or a word-search report as text.

Pure presentation: it draws the `ZoneReport`/`WordReport` it receives and reads nothing else.
"""

from datetime import datetime, timezone
from typing import NamedTuple

import timefmt
from emojis import SECTION_EMOJI
from model import Cluster, Note, WordChunk, WordReport, ZoneReport
from report_render_blocks import (
    blocker_block,
    decision_block,
    incident_block,
    memo_block,
    question_block,
    restriction_block,
)

_BOX_WIDTH = 72
_DIVIDER = "═" * _BOX_WIDTH  # ====
_THIN_DIVIDER = "─" * _BOX_WIDTH  # ----
_CERO_NOTAS = "⚠  C E R O   N O T A S"

_RESTRICTION_TYPES = frozenset({"R"})
_BLOCKER_TYPES = frozenset({"B"})
_DECISION_TYPES = frozenset({"D", "X"})
_MEMO_TYPES = frozenset({"M"})
_INCIDENT_TYPES = frozenset({"I"})
_QUESTION_TYPES = frozenset({"Q"})

_MARK = "› "  # marks a line that matched the word
_NO_MARK = "  "


def _header_line(left: str, right: str) -> str:
    gap = _BOX_WIDTH - len(left) - len(right)
    if gap < 1:
        gap = 1
    return f"{left}{' ' * gap}{right}"


# Public aliases shared with report_render_note.py.
DIVIDER = _DIVIDER
THIN_DIVIDER = _THIN_DIVIDER
header_line = _header_line
utc_label = timefmt.utc_label


# Public alias shared with report_render_chain.py.
NO_MARK = _NO_MARK


def _cluster_block(cluster: Cluster) -> list[str]:
    """Render a decision cluster: the root, then each child with its status and pointer."""
    root = cluster.root
    lines = [_header_line(f"  {root.id}  {root.headline}", root.timestamp.strftime("%Y-%m-%d"))]
    if root.why:
        lines.append(f"         Why: {root.why}")
    if root.issue is not None:
        lines.append(f"         Issue: #{root.issue}")

    children = cluster.children
    for index, child in enumerate(children):
        branch = "└─" if index == len(children) - 1 else "├─"
        if child.type == "X":
            status = "descartada"
        elif child.id in cluster.archived_ids:
            status = "archivada"
        else:
            status = "vigente"

        if root.replaces == child.id:
            pointer = f"replaced by {root.id}"
        elif child.origin:
            pointer = f"Origin {', '.join(child.origin)}"
        elif child.replaces and child.replaces != "none":
            pointer = f"replaces {child.replaces}"
        else:
            pointer = ""

        tail = f"{status} · {pointer}" if pointer else status
        lines.append(f"    {branch} {child.id}  {child.headline}  {tail}")

    return lines


def _empty_zone_lines() -> list[str]:
    """Return the CERO NOTAS block shown for a zone with no notes."""
    return [
        " " * 14 + _CERO_NOTAS,
        "",
        "  La zona existe en zones.json y no tiene ni una: ninguna",
        "  decisión, ningún muro, ningún hecho, ninguna incidencia,",
        "  ninguna pregunta.",
        "",
        "  Es un dato, no un fallo. O el trabajo no ha empezado, o se ha",
        "  hecho sin escribir nada de lo que se decidió.",
    ]


def _no_marker(_note: Note) -> str:
    return _NO_MARK


def _section(
    lines: list[str],
    title: str,
    notes: list[Note],
    block_fn,
    marker_fn,
    archived_notes: frozenset[Note],
    compact: bool = False,
) -> None:
    """Append a section title and one block per note to `lines`; nothing when `notes` is empty.

    `compact` puts a single blank line after the section instead of one per note.
    """
    if not notes:
        return
    lines.append(title)
    lines.append("")
    for note in notes:
        lines.extend(block_fn(note, marker_fn(note), note in archived_notes))
        if not compact:
            lines.append("")
    if compact:
        lines.append("")


def _cluster_section(lines: list[str], title: str, clusters: tuple[Cluster, ...]) -> None:
    if not clusters:
        return
    lines.append(title)
    lines.append("")
    for cluster in clusters:
        lines.extend(_cluster_block(cluster))
        lines.append("")


def _render_zone_sections(r: ZoneReport) -> list[str]:
    """Return the six body sections of a zone report, in contract order."""
    lines: list[str] = []
    before_decisions = (
        (
            f"{SECTION_EMOJI['restricciones']} RESTRICTIONS ({len(r.restrictions)}) "
            f"— literales",
            r.restrictions,
            restriction_block,
            False,
        ),
        (f"{SECTION_EMOJI['bloqueantes']} BLOCKERS ({len(r.blockers)})", r.blockers, blocker_block, False),
    )
    for title, notes, block_fn, compact in before_decisions:
        _section(lines, title, notes, block_fn, _no_marker, r.archived_notes, compact)

    _cluster_section(
        lines, f"{SECTION_EMOJI['decisiones']} DECISIONS ({len(r.decisions)} racimos)", r.decisions
    )

    after_decisions = (
        (f"{SECTION_EMOJI['memos']} MEMOS ({len(r.memos)})", r.memos, memo_block, True),
        (f"{SECTION_EMOJI['incidencias']} INCIDENTS ({len(r.incidents)})", r.incidents, incident_block, False),
        (
            f"{SECTION_EMOJI['preguntas']} OPEN QUESTIONS ({len(r.questions)})",
            r.questions,
            question_block,
            False,
        ),
    )
    for title, notes, block_fn, compact in after_decisions:
        _section(lines, title, notes, block_fn, _no_marker, r.archived_notes, compact)
    return lines


def render_zone(r: ZoneReport) -> str:
    """Render a zone report; a zone with no notes at all shows CERO NOTAS."""
    lines = [_DIVIDER]
    total = r.live_count + r.archived_count

    if total == 0:
        lines.append(_header_line(f"  ZONA {r.zone.name}", timefmt.utc_label(r.generated_at)))
        lines.append(_DIVIDER)
        lines.append("")
        lines.extend(_empty_zone_lines())
        lines.append(_DIVIDER)
        return "\n".join(lines)

    lines.append(
        _header_line(
            f"  ZONA {r.zone.name} · {r.live_count} vigentes · "
            f"{r.archived_count} archivadas",
            timefmt.utc_label(r.generated_at),
        )
    )
    lines.append(_DIVIDER)
    lines.append("")
    lines.extend(_render_zone_sections(r))
    lines.append(_THIN_DIVIDER)
    lines.append(f"  Historia completa, con lo archivado:   gitmem search {r.zone.name} --todo")
    return "\n".join(lines)


class _TypeSplit(NamedTuple):
    """The notes of a `WordChunk` split by type."""

    restrictions: list[Note]
    blockers: list[Note]
    decisions: list[Note]
    memos: list[Note]
    incidents: list[Note]
    questions: list[Note]


def _split_by_type(notes: tuple[Note, ...]) -> _TypeSplit:
    return _TypeSplit(
        restrictions=[n for n in notes if n.type in _RESTRICTION_TYPES],
        blockers=[n for n in notes if n.type in _BLOCKER_TYPES],
        decisions=[n for n in notes if n.type in _DECISION_TYPES],
        memos=[n for n in notes if n.type in _MEMO_TYPES],
        incidents=[n for n in notes if n.type in _INCIDENT_TYPES],
        questions=[n for n in notes if n.type in _QUESTION_TYPES],
    )


def _chunk_header(chunk: WordChunk) -> str:
    header = f"──── [{chunk.zone1}][{chunk.zone2}] · {len(chunk.notes)} notas "
    if len(header) < _BOX_WIDTH:
        header = header + "─" * (_BOX_WIDTH - len(header))
    return header


def _chunk_sections(chunk: WordChunk, by_type: _TypeSplit) -> list[str]:
    """Return a chunk's sections, all but questions."""
    lines: list[str] = []

    def marker_for(note: Note) -> str:
        return _MARK if note.id in chunk.matched_ids else _NO_MARK

    specs = (
        (
            f"{SECTION_EMOJI['restricciones']} RESTRICTIONS ({len(by_type.restrictions)})",
            by_type.restrictions,
            restriction_block,
            False,
        ),
        (
            f"{SECTION_EMOJI['bloqueantes']} BLOCKERS ({len(by_type.blockers)})",
            by_type.blockers,
            blocker_block,
            False,
        ),
        (
            f"{SECTION_EMOJI['decisiones']} DECISIONS ({len(by_type.decisions)})",
            by_type.decisions,
            decision_block,
            False,
        ),
        (f"{SECTION_EMOJI['memos']} MEMOS ({len(by_type.memos)})", by_type.memos, memo_block, True),
        (
            f"{SECTION_EMOJI['incidencias']} INCIDENTS ({len(by_type.incidents)})",
            by_type.incidents,
            incident_block,
            False,
        ),
    )
    for title, notes, block_fn, compact in specs:
        _section(lines, title, notes, block_fn, marker_for, chunk.archived_notes, compact)
    return lines


def _chunk_body(
    chunk: WordChunk, pending_questions: list[tuple[Note, bool, bool]]
) -> list[str]:
    """Return a chunk's body and append its questions to `pending_questions`.

    Each pending entry is `(note, matched, archived)`.
    """
    lines = [_chunk_header(chunk), ""]
    by_type = _split_by_type(chunk.notes)
    lines.extend(_chunk_sections(chunk, by_type))
    for note in by_type.questions:
        pending_questions.append(
            (note, note.id in chunk.matched_ids, note in chunk.archived_notes)
        )
    return lines


def render_word(r: WordReport) -> str:
    """Render a word search across zones; all questions are gathered under one final section."""
    lines = [_DIVIDER]
    lines.append(
        _header_line(
            f"  PALABRA «{r.word}» · {r.zone_count} zonas · {r.live_count} vigentes",
            timefmt.utc_label(r.generated_at),
        )
    )
    lines.append(f"  {_MARK} marca la línea que casó")
    lines.append(_DIVIDER)

    pending_questions: list[tuple[Note, bool, bool]] = []
    for chunk in r.chunks:
        lines.append("")
        lines.extend(_chunk_body(chunk, pending_questions))

    if pending_questions:
        lines.append("")
        lines.append(f"{SECTION_EMOJI['preguntas']} OPEN QUESTIONS ({len(pending_questions)})")
        lines.append("")
        for note, matched, archived in pending_questions:
            marker = _MARK if matched else _NO_MARK
            lines.extend(question_block(note, marker, archived))
            lines.append("")

    lines.append(_THIN_DIVIDER)
    lines.append(f"  Historia completa, con lo archivado:   gitmem search «{r.word}» --todo")
    return "\n".join(lines)
