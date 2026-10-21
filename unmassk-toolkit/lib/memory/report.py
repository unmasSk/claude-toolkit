"""Decide what a zone, word, note or chain report shows; `report_render.py` turns it into text.

A note belongs to a zone when either `zone1` or `zone2` matches.
"""

from datetime import datetime, timezone
from pathlib import Path

import clusters
import gitcmd
import health
import indexes
import notes
import query
import zones as zones_mod
from model import (
    ArchiveLine,
    ChainReport,
    ChainThread,
    Cluster,
    Note,
    NoteReport,
    WordChunk,
    WordReport,
    Zone,
    ZoneReport,
)

_DECISION_TYPES = frozenset({"D", "X"})
_RESTRICTION_TYPES = frozenset({"R"})
_BLOCKER_TYPES = frozenset({"B"})
_MEMO_TYPES = frozenset({"M"})
_INCIDENT_TYPES = frozenset({"I"})
_QUESTION_TYPES = frozenset({"Q"})


def _repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def _zones_json_path(pm_root: Path) -> Path:
    return pm_root / "zones.json"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _load_zone(zone: str, pm_root: Path) -> Zone:
    """The registered `Zone` for `zone`; raises `ValueError` if it is not in zones.json."""
    zone_obj = zones_mod.load(_zones_json_path(pm_root)).get(zone)
    if zone_obj is None:
        raise ValueError(
            f"report.build_zone: la zona {zone!r} no esta registrada en zones.json"
        )
    return zone_obj


def _notes_touching_zone(zone: str) -> tuple[Note, ...]:
    """Every note in history, live or archived, whose `zone1` or `zone2` is `zone`."""
    return tuple(dict.fromkeys(query.by_zone(zone, None) + query.by_zone(None, zone)))


def _archived_state(root: Path) -> tuple[frozenset[str], frozenset[tuple[str, str]]]:
    """Ids in ``ARCHIVED.md`` and the ``(id, headline)`` of each live index line."""
    archived_ids = indexes.archived_ids(notes.pm_root(root))
    live_keys = frozenset((line.id, line.headline) for line in health.current_index_lines(root))
    return archived_ids, live_keys


def _archived_among(
    notes: tuple[Note, ...], state: tuple[frozenset[str], frozenset[tuple[str, str]]]
) -> frozenset[Note]:
    """The notes in ``notes`` archived today; for an id still live in its index, the headline decides."""
    archived_ids, live_keys = state
    return frozenset(
        n for n in notes if n.id in archived_ids and (n.id, n.headline) not in live_keys
    )


def _filter_archived(
    notes: tuple[Note, ...], archived_notes: frozenset[Note], include_archived: bool
) -> tuple[Note, ...]:
    if include_archived:
        return notes
    return tuple(n for n in notes if n not in archived_notes)


def _by_type(notes: tuple[Note, ...], types: frozenset[str]) -> tuple[Note, ...]:
    return tuple(sorted((n for n in notes if n.type in types), key=lambda n: n.id))


def build_zone(zone: str, include_archived: bool) -> ZoneReport:
    """The report of ``zone``: counts always real, content per ``include_archived``."""
    root = _repo_root()
    pm_root = notes.pm_root(root)
    zone_obj = _load_zone(zone, pm_root)
    state = _archived_state(root)
    archived_ids = state[0]

    all_notes = _notes_touching_zone(zone)
    archived_notes = _archived_among(all_notes, state)
    archived_count = len(archived_notes)
    live_count = len(all_notes) - archived_count

    visible = _filter_archived(all_notes, archived_notes, include_archived)
    decisions = clusters.group(_by_type(visible, _DECISION_TYPES), archived_ids)

    return ZoneReport(
        zone=zone_obj,
        generated_at=_now(),
        live_count=live_count,
        archived_count=archived_count,
        restrictions=_by_type(visible, _RESTRICTION_TYPES),
        blockers=_by_type(visible, _BLOCKER_TYPES),
        decisions=decisions,
        memos=_by_type(visible, _MEMO_TYPES),
        incidents=_by_type(visible, _INCIDENT_TYPES),
        questions=_by_type(visible, _QUESTION_TYPES),
        archived_notes=archived_notes,
    )


def build_word(word: str, include_archived: bool) -> WordReport:
    """Word search: one ``WordChunk`` per matching zone pair, with the pair's full state
    and which of its notes matched. The searched word is stored lowercased.
    """
    state = _archived_state(_repo_root())

    matched_ids_by_pair: dict[tuple[str, str], set[str]] = {}
    for note, _matched_lines in query.by_word(word):
        matched_ids_by_pair.setdefault((note.zone1, note.zone2), set()).add(note.id)

    chunks = []
    for (zone1, zone2), matched_ids_here in matched_ids_by_pair.items():
        pair_all = query.by_zone(zone1, zone2)
        archived_notes = _archived_among(pair_all, state)
        pair_notes = _filter_archived(pair_all, archived_notes, include_archived)
        matched_ids = frozenset(n.id for n in pair_notes if n.id in matched_ids_here)
        chunks.append(
            WordChunk(
                zone1=zone1,
                zone2=zone2,
                notes=pair_notes,
                matched_ids=matched_ids,
                archived_notes=archived_notes,
            )
        )
    chunks.sort(key=lambda c: (c.zone1, c.zone2))

    return WordReport(
        word=word.lower(),
        generated_at=_now(),
        zone_count=len(chunks),
        live_count=sum(len(c.matched_ids) for c in chunks),
        chunks=tuple(chunks),
    )


def build_note(note_id: str) -> NoteReport | None:
    """The report of one note by id, or ``None`` if it does not exist.

    The requested note is always the cluster root; its children are the notes in
    either of its zones that name it in ``origin`` or ``replaces``. No children
    gives ``cluster=None``.
    """
    note = query.by_id(note_id)
    if note is None:
        return None
    note_id = note.id

    root = _repo_root()
    state = _archived_state(root)
    archived_ids = state[0]
    twins = tuple(n for _sha, n in query.commits_by_id(note.id)) or (note,)
    archived_twins = _archived_among(twins, state)
    note = next((n for n in twins if n not in archived_twins), note)

    related: dict[str, Note] = {}
    for zone in {note.zone1, note.zone2}:
        for n in _notes_touching_zone(zone):
            related[n.id] = n
    related.pop(note_id, None)

    children = tuple(
        sorted(
            (
                n for n in related.values()
                if note_id in n.origin or n.replaces == note_id
            ),
            key=lambda n: n.id,
        )
    )
    cluster = None
    if children:
        cluster = Cluster(
            root=note,
            children=children,
            archived_ids=frozenset(n.id for n in children if n.id in archived_ids),
        )

    return NoteReport(
        note=note,
        generated_at=_now(),
        archived=note in archived_twins,
        cluster=cluster,
    )


def _archive_lines_by_id(pm_root: Path) -> dict[str, ArchiveLine]:
    """``ARCHIVED.md`` lines keyed by id; a missing file gives ``{}``."""
    try:
        lines = indexes.read_archive(pm_root)
    except FileNotFoundError:
        return {}
    return {line.id: line for line in lines}


def _chain_is_superseded(
    note_id: str,
    archive_lines: dict[str, ArchiveLine],
    by_id: dict[str, Note],
    superseded_within_matched: frozenset[str],
) -> bool:
    """True if ``note_id`` has a successor visible in ``by_id``.

    An ``ARCHIVED.md`` "replaced" line decides when present; otherwise a
    ``Replaces`` pointer within the matched set does.
    """
    line = archive_lines.get(note_id)
    if line is not None:
        if line.destination != "replaced":
            return False
        return line.destination_detail in by_id
    return note_id in superseded_within_matched


def _chain_ancestors(head: Note, by_id: dict[str, Note]) -> tuple[Note, ...]:
    """Predecessors of ``head`` along ``Note.replaces``, most recent first.

    Missing ones are fetched with ``query.by_id``; a cycle stops the walk.
    """
    ancestors: list[Note] = []
    seen = {head.id}
    cursor = head
    while cursor.replaces and cursor.replaces not in seen:
        prev = by_id.get(cursor.replaces)
        if prev is None:
            prev = query.by_id(cursor.replaces)
        if prev is None:
            break
        ancestors.append(prev)
        seen.add(prev.id)
        cursor = prev
    return tuple(ancestors)


def _chain_closure(
    note_id: str,
    is_archived: bool,
    archive_lines: dict[str, ArchiveLine],
) -> tuple[bool, str | None]:
    """``(closed, replaced_by)`` for a thread head.

    Live: ``(False, None)``. Archived as "replaced": ``(False, successor_id)``.
    Otherwise archived: ``(True, None)``.
    """
    if not is_archived:
        return False, None
    line = archive_lines.get(note_id)
    if line is not None and line.destination == "replaced":
        return False, line.destination_detail
    return True, None


def _chain_threads(
    matched: tuple[Note, ...],
    archived_ids: frozenset[str],
    archive_lines: dict[str, ArchiveLine],
) -> tuple[ChainThread, ...]:
    """Split ``matched`` into threads: each head with its predecessors hanging below.

    A note replaced by another in the set is never a head.
    """
    by_id = {n.id: n for n in matched}
    superseded_within_matched = frozenset(n.replaces for n in matched if n.replaces)

    threads = []
    for note in sorted(matched, key=lambda n: n.id):
        if _chain_is_superseded(note.id, archive_lines, by_id, superseded_within_matched):
            continue
        closed, replaced_by = _chain_closure(
            note.id, note.id in archived_ids, archive_lines
        )
        threads.append(
            ChainThread(
                head=note,
                closed=closed,
                ancestors=_chain_ancestors(note, by_id),
                replaced_by=replaced_by,
            )
        )
    return tuple(threads)


def build_chain(text: str) -> ChainReport:
    """The chain view of ``text`` (zone or word) for ``search.py --chain``; always full history."""
    root = _repo_root()
    pm_root = notes.pm_root(root)
    archived_ids = indexes.archived_ids(pm_root)
    archive_lines = _archive_lines_by_id(pm_root)

    zones_map = zones_mod.load(_zones_json_path(pm_root))
    resolved_zone = zones_mod.resolve(text, zones_map)
    if resolved_zone is not None:
        matched = _notes_touching_zone(resolved_zone)
    else:
        matched = tuple(note for note, _matched_lines in query.by_word(text))

    return ChainReport(
        query=text,
        generated_at=_now(),
        threads=_chain_threads(matched, archived_ids, archive_lines),
    )
