"""Boot CHECKS: verify the memory system has not broken itself; repairs nothing.

Each check reports its real numbers even when healthy; a gh or git failure goes to its `_error` field.
"""

from pathlib import Path

import ids
import indexes
import notes
import notes_duplicate
import query
import repo_guard
import rules
import zones
from health_plans import issues_checked, plans_unreflected
from model import ArchiveLine, HealthReport, IndexLine, Note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

_ARCHIVE_FILE = "ARCHIVED.md"

# A new project has a few bootstrap commits with no notes.
_LEGACY_MIN_COMMITS = 8


def _current_index_lines(root: Path) -> tuple[IndexLine, ...]:
    """Note lines of the live indexes (not ARCHIVED.md); a missing index counts as empty."""
    pm = notes.pm_root(root)
    lines: list[IndexLine] = []
    for name in INDEX_FILES:
        if name == _ARCHIVE_FILE:
            continue
        try:
            lines.extend(indexes.read(name, pm))
        except FileNotFoundError:
            continue
    return tuple(lines)


# Public alias used by report.py and boot.py.
current_index_lines = _current_index_lines


def coherence(root: Path) -> tuple[int, int, tuple[str, ...]]:
    """Cross the live indexes against git; return `(lines, notes, discrepancies)`."""
    root = Path(root)
    index_lines = _current_index_lines(root)
    git_notes = query.by_zone(None, None)
    archived_ids = indexes.archived_ids(notes.pm_root(root))

    index_ids = {line.id for line in index_lines}
    git_ids = {note.id for note in git_notes}

    discrepancies = tuple(
        f"{note_id}: existe en git pero falta en el indice"
        for note_id in sorted(git_ids - index_ids - archived_ids)
    ) + tuple(
        f"{note_id}: esta en el indice pero no existe en git"
        for note_id in sorted(index_ids - git_ids)
    ) + tuple(
        f"{note_id}: archivado pero no existe en git"
        for note_id in sorted(archived_ids - git_ids)
    )

    return len(index_lines), len(git_notes), discrepancies


def _head_rules_content(root: Path) -> str:
    """Return rules.md as committed at HEAD, not the working tree copy."""
    relpath = rules.rules_file_path(root).relative_to(root).as_posix()
    return query.show_file_at_head(relpath, root)


def coherence_rules(root: Path) -> tuple[int, int, tuple[str, ...]]:
    """Cross rules.md at HEAD against the working tree, ignoring quotes; return `(head, file, discrepancies)`."""
    root = Path(root)
    head_content = _head_rules_content(root)

    path = rules.rules_file_path(root)
    file_content = path.read_text(encoding="utf-8") if path.exists() else ""

    head_texts = tuple(
        rules.strip_quote_suffix(text) for text in rules.iter_rule_texts(head_content)
    )
    file_texts = tuple(
        rules.strip_quote_suffix(text) for text in rules.iter_rule_texts(file_content)
    )

    head_set = set(head_texts)
    file_set = set(file_texts)

    discrepancies = tuple(
        f"{text}: existe en un commit de regla pero falta en el fichero de reglas"
        for text in sorted(head_set - file_set)
    ) + tuple(
        f"{text}: esta en el fichero de reglas pero no existe en ningun commit de regla"
        for text in sorted(file_set - head_set)
    )

    return len(head_texts), len(file_texts), discrepancies


def _archive_lines(root: Path) -> tuple[ArchiveLine, ...]:
    """Lines of ARCHIVED.md; a missing file is empty."""
    try:
        return indexes.read_archive(notes.pm_root(root))
    except FileNotFoundError:
        return ()


def duplicates(root: Path) -> tuple[str, ...]:
    """Ids that have two or more live index lines."""
    return ids.find_duplicates(_current_index_lines(Path(root)))


def _duplicate_notes(duplicate_ids: tuple[str, ...], root: Path) -> tuple[tuple[str, Note], ...]:
    """Return `(sha, note)` for each live copy of `duplicate_ids` that has a commit."""
    live = _current_index_lines(root)
    pairs: list[tuple[str, Note]] = []
    for note_id in duplicate_ids:
        by_sha = dict(query.commits_by_id(note_id))
        lines = [line for line in live if line.id.lower() == note_id.lower()]
        pairs.extend(
            (sha, by_sha[sha]) for _line, sha in notes_duplicate.with_commits(note_id, lines) if sha
        )
    return tuple(pairs)


def _total_commit_count() -> int:
    """Count commits in the full history; 0 on an empty branch."""
    raw_stdout = query.run_git_log("--pretty=format:%H")
    return sum(1 for record in raw_stdout.split("\0") if record)


def _possible_unconverted_legacy(total_commits: int, git_notes: int) -> int | None:
    """Return the commit count when there are many commits but no notes, else None."""
    if git_notes == 0 and total_commits > _LEGACY_MIN_COMMITS:
        return total_commits
    return None


def zones_state(zones_path: Path) -> tuple[str, int]:
    """Return `("absent", 0)`, `("empty", 0)` (also when corrupt) or `("populated", zone_count)`."""
    if not zones_path.exists():
        return "absent", 0
    try:
        zone_count = len(zones.load(zones_path))
    except ValueError:
        zone_count = 0
    if zone_count == 0:
        return "empty", 0
    return "populated", zone_count


def _memory_mounted(root: Path) -> tuple[bool, tuple[str, ...]]:
    """Check indexes, zones.json (at least one zone) and config.json; return `(mounted, missing)`."""
    root = Path(root)
    pm = notes.pm_root(root)
    missing: list[str] = []

    missing_indices = tuple(name for name in INDEX_FILES if not (pm / name).exists())
    if missing_indices:
        missing.append(".claude/project-memory/: faltan " + ", ".join(missing_indices))

    state, _zone_count = zones_state(pm / "zones.json")
    if state == "absent":
        missing.append("zones.json (no existe)")
    elif state == "empty":
        missing.append("zones.json (existe, pero no tiene ninguna zona dada de alta)")

    config_path = pm / "config.json"
    if not config_path.exists():
        missing.append("config.json (no existe)")

    return (not missing, tuple(missing))


def rebuild_plan(root: Path) -> tuple[tuple[tuple[Note, str], ...], tuple[tuple[str, str], ...]]:
    """Turn the coherence check into a repair plan for reindex.py; writes nothing.

    Returns `(to_insert, to_remove)`: `(note, file)` missing from the indexes and `(id, file)` absent from git.
    """
    root = Path(root)
    pm = notes.pm_root(root)
    archived = indexes.archived_ids(pm)
    git_notes = {note.id: note for note in query.by_zone(None, None)}

    ids_by_file: dict[str, set[str]] = {}
    for name in INDEX_FILES:
        if name == _ARCHIVE_FILE:
            continue
        try:
            ids_by_file[name] = {line.id for line in indexes.read(name, pm)}
        except FileNotFoundError:
            ids_by_file[name] = set()
    all_index_ids: set[str] = set().union(*ids_by_file.values()) if ids_by_file else set()

    to_insert = tuple(
        (git_notes[note_id], TYPE_INDEX_FILES[git_notes[note_id].type])
        for note_id in sorted(git_notes)
        if note_id not in archived
        and note_id not in all_index_ids
        and git_notes[note_id].type in TYPE_INDEX_FILES
    )
    to_remove = tuple(
        (note_id, name)
        for name, ids_here in ids_by_file.items()
        for note_id in sorted(ids_here)
        if note_id not in git_notes
    )
    return to_insert, to_remove


def build() -> HealthReport:
    """Build the HealthReport the boot renders; check failures go to their `_error` field."""
    root = notes.repo_root()
    index_lines, git_notes, index_discrepancies = coherence(root)
    try:
        rule_head_lines, rule_file_lines, rule_discrepancies = coherence_rules(root)
        rule_discrepancies_error = None
    except RuntimeError as exc:
        rule_head_lines, rule_file_lines, rule_discrepancies = 0, 0, ()
        rule_discrepancies_error = str(exc)
    try:
        unreflected, issue_states, issues_unanswered = issues_checked()
        unreflected_error = None
    except RuntimeError as exc:
        unreflected, issue_states, issues_unanswered = (), (), ()
        unreflected_error = str(exc)

    archived_notes = len(_archive_lines(root))
    duplicate_ids = duplicates(root)

    legacy_commits_suspected = _possible_unconverted_legacy(_total_commit_count(), git_notes)
    _mounted, memory_setup_missing = _memory_mounted(root)

    return HealthReport(
        duplicate_ids=duplicate_ids,
        duplicate_notes=_duplicate_notes(duplicate_ids, root),
        index_lines=index_lines,
        git_notes=git_notes,
        index_discrepancies=index_discrepancies,
        plans_unreflected=unreflected,
        plans_unreflected_error=unreflected_error,
        issue_states=issue_states,
        issues_unanswered=issues_unanswered,
        archived_notes=archived_notes,
        legacy_commits_suspected=legacy_commits_suspected,
        memory_setup_missing=memory_setup_missing,
        rule_head_lines=rule_head_lines,
        rule_file_lines=rule_file_lines,
        rule_discrepancies=rule_discrepancies,
        rule_discrepancies_error=rule_discrepancies_error,
        install_uncommitted=repo_guard.install_left_uncommitted(root),
    )
