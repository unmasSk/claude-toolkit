"""Promote a question (Q) to a memo (M) or a discard (X), archiving the Q as "promoted".

Also holds `swap_and_archive()`, shared with `notes.replace()`.
"""

import dataclasses
from datetime import datetime, timezone
from pathlib import Path

import format
import gitcmd
import ids
import indexes
import notes_duplicate
import rejection as rejection_
from model import ArchiveLine, IndexLine, Note, Rejection, WriteResult
from notes_commit import lock_resource, pm_root, repo_root, restore_snapshot_best_effort, stage_and_commit
from validator import Context, validate_note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

_TYPE_TO_INDEX_FILE = TYPE_INDEX_FILES
_ARCHIVE_FILE = "ARCHIVED.md"
assert _ARCHIVE_FILE in INDEX_FILES, (
    "notes_promote.py: _ARCHIVE_FILE ha quedado desincronizado de vocabulary.INDEX_FILES"
)


def index_with_archived(current_index: tuple[IndexLine, ...], pm: Path) -> tuple[IndexLine, ...]:
    """`current_index` plus an empty line per archived id, so `ids.next_id` never reuses one."""
    archived = indexes.archived_ids(pm)
    return current_index + tuple(
        IndexLine(id=archived_id, zone1="", zone2="", headline="")
        for archived_id in archived
    )


def swap_and_archive(
    old_id: str,
    old_index_name: str,
    new: Note,
    ctx: Context,
    *,
    destination: str,
    link_replaces: bool,
    pre_check=None,
    also_replaces: str | None = None,
) -> WriteResult:
    """Retire `old_id`, write `new` under a fresh id and archive the old note: one commit, or nothing.

    `pre_check(pm)` runs inside the lock before any index is touched; `also_replaces` is a second live
    note archived as "replaced" in the same commit.
    """
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        indexes.seed(pm)

        if pre_check is not None:
            rejection = pre_check(pm)
            if rejection is not None:
                return WriteResult(ok=False, note_id=None, rejections=(rejection,), git_error=None)

        old_index_path = pm / old_index_name
        old_index_snapshot = old_index_path.read_text(encoding="utf-8")
        old_lines = indexes.read(old_index_name, pm)
        old_line, duplicate = notes_duplicate.pick(
            old_id, old_lines, None, notes_duplicate.remove_relaunch(old_id)
        )
        if duplicate is not None:
            return WriteResult(ok=False, note_id=None, rejections=(duplicate,), git_error=None)
        indexes.remove(old_id, old_index_name, pm, only=old_line)
        if old_line is None:  # cannot happen: same lock since the read
            raise RuntimeError(f"inconsistencia interna: {old_id!r} se retiro de {old_index_name}")

        index_name_new = _TYPE_TO_INDEX_FILE.get(new.type)
        if index_name_new is not None:
            same_file = index_name_new == old_index_name
            current_index = old_lines if same_file else indexes.read(index_name_new, pm)
            new_id = ids.next_id(new.type, index_with_archived(current_index, pm))
            candidate = dataclasses.replace(
                new, id=new_id, replaces=(old_id if link_replaces else new.replaces)
            )
        else:  # unknown type: validate_type rejects it below
            candidate = dataclasses.replace(new, replaces=old_id) if link_replaces else new

        rejections = validate_note(candidate, ctx)
        if rejections:
            restore_snapshot_best_effort(old_index_path, old_index_snapshot)
            return WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None)

        # index_name_new is not None here: validate_type would have rejected it.
        new_index_path = pm / index_name_new
        snapshots = {old_index_path: old_index_snapshot}
        snapshots.setdefault(new_index_path, new_index_path.read_text(encoding="utf-8"))
        archive_path = pm / _ARCHIVE_FILE
        snapshots[archive_path] = archive_path.read_text(encoding="utf-8")

        def _restore_all() -> None:
            for path, text in snapshots.items():
                restore_snapshot_best_effort(path, text)

        retired_line = None
        if also_replaces is not None:
            try:
                retired_line, duplicate = _retire_live(also_replaces, pm, snapshots)
            except BaseException:
                _restore_all()
                raise
            if duplicate is not None:
                _restore_all()
                return WriteResult(ok=False, note_id=None, rejections=(duplicate,), git_error=None)

        new_line = IndexLine(
            id=candidate.id, zone1=candidate.zone1, zone2=candidate.zone2,
            headline=candidate.headline,
        )
        indexes.insert(new_line, index_name_new, pm)

        today = datetime.now(timezone.utc).date()
        indexes.archive(
            ArchiveLine(
                date=today, type=old_id.split("-", 1)[0], id=old_id,
                zone1=old_line.zone1, zone2=old_line.zone2, headline=old_line.headline,
                destination=destination, destination_detail=candidate.id,
            ),
            pm,
        )
        if retired_line is not None:
            indexes.archive(
                ArchiveLine(
                    date=today, type=also_replaces.split("-", 1)[0], id=also_replaces,
                    zone1=retired_line.zone1, zone2=retired_line.zone2,
                    headline=retired_line.headline,
                    destination="replaced", destination_detail=candidate.id,
                ),
                pm,
            )

        touched = list(snapshots)

        try:
            message = format.build_message(candidate)
            git_result = stage_and_commit(message, touched, root)
        except BaseException:
            _restore_all()
            raise

        if git_result.returncode != 0:
            _restore_all()
            for path in touched:
                gitcmd.run(["reset", "--", str(path)], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=candidate.id, rejections=(), git_error=None)


def _retire_live(note_id: str, pm: Path, snapshots: dict) -> tuple[IndexLine | None, Rejection | None]:
    """Remove the single live index line of `note_id`, snapshotting its index first."""
    index_name = _TYPE_TO_INDEX_FILE.get(note_id.split("-", 1)[0])
    if index_name is None:
        raise ValueError(f"{note_id!r}: tipo desconocido, ningun indice le corresponde")
    path = pm / index_name
    snapshots.setdefault(path, path.read_text(encoding="utf-8"))
    line, duplicate = notes_duplicate.pick(
        note_id, indexes.read(index_name, pm), None, notes_duplicate.remove_relaunch(note_id)
    )
    if duplicate is not None:
        return None, duplicate
    if line is None:
        raise RuntimeError(f"--replaces {note_id}: no esta vigente en {index_name}")
    indexes.remove(note_id, index_name, pm, only=line)
    return line, None


def _reject_bad_promotes_target(new: Note, question_id: str, pm: Path) -> Rejection | None:
    """None if `question_id` is a live Q, else the Rejection explaining why."""
    relaunch = (
        f'gitmem note {new.type} --zones {new.zone1} {new.zone2} '
        f'"{new.headline}" --description "..." --promotes <ID de una Q real>',
    )
    if question_id.split("-", 1)[0] != "Q":
        what = f"--promotes apunta a {question_id!r}, que no es una pregunta (Q)"
        options = (
            "Solo una pregunta (Q) abierta asciende con --promotes -- a memo si la "
            "respuesta es un hecho, a descarte si es que no [spec Sec.4]. Cita el "
            "identificador de esa Q, nunca el de otro tipo.",
        )
        return rejection_.build(
            kind="promotes_not_a_question", what=what, options=options, command=relaunch
        )

    live_questions = {line.id for line in indexes.read(_TYPE_TO_INDEX_FILE["Q"], pm)}
    if question_id not in live_questions:
        what = f"--promotes cita un identificador que no existe: {question_id}"
        options = (
            "El puntero de --promotes tiene que apuntar a una pregunta (Q) abierta "
            "de verdad, igual que ya exige Replaces/Origin.",
        )
        return rejection_.build(
            kind="promotes_dangling", what=what, options=options, command=relaunch
        )

    return None


def promote(new: Note, question_id: str, ctx: Context) -> WriteResult:
    """Promote live question `question_id` to `new`; a real `new.replaces` is archived in the same commit."""
    replaced = new.replaces if new.replaces not in (None, "none") else None
    return swap_and_archive(
        question_id,
        _TYPE_TO_INDEX_FILE["Q"],
        new,
        ctx,
        destination="promoted",
        link_replaces=False,
        pre_check=lambda pm: _reject_bad_promotes_target(new, question_id, pm),
        also_replaces=replaced,
    )
