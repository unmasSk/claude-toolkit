"""Write, replace and close notes: the note and its index line land in one commit, or neither.

On a git failure or exception the index is restored and the git error is returned.
"""

import dataclasses
import shlex
from collections.abc import Callable
from datetime import datetime, timezone

import format
import gitcmd
import ids
import indexes
import notes_duplicate
import rejection as rejection_
from model import ArchiveLine, IndexLine, Note, Rejection, WriteResult
from notes_commit import (
    lock_resource,
    pm_root,
    repo_root,
    restore_index_best_effort,
    restore_snapshot_best_effort,
    stage_and_commit,
    write_work,
)
# Re-exported for callers such as `bin/memory/note.py`.
from notes_promote import index_with_archived, promote, swap_and_archive  # noqa: F401
from validator import Context, validate_note
from vocabulary import INDEX_FILES, TYPE_INDEX_FILES

_TYPE_TO_INDEX_FILE = TYPE_INDEX_FILES

_ARCHIVE_FILE = "ARCHIVED.md"
assert _ARCHIVE_FILE in INDEX_FILES, (
    "notes.py: _ARCHIVE_FILE ha quedado desincronizado de vocabulary.INDEX_FILES"
)


def write(note: Note, ctx: Context) -> WriteResult:
    """Write `note` and its index line in one commit, or nothing."""
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        index_name = _TYPE_TO_INDEX_FILE.get(note.type)

        if index_name is not None:
            indexes.seed(pm)
            current_index = indexes.read(index_name, pm)
            new_id = ids.next_id(note.type, index_with_archived(current_index, pm))
            candidate = dataclasses.replace(note, id=new_id)
        else:
            # Unknown type: `validate_note` rejects it below.
            candidate = note

        rejections = validate_note(candidate, ctx)
        if rejections:
            return WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None)

        index_line = IndexLine(
            id=candidate.id,
            zone1=candidate.zone1,
            zone2=candidate.zone2,
            headline=candidate.headline,
        )
        indexes.insert(index_line, index_name, pm)

        index_path = pm / index_name
        try:
            message = format.build_message(candidate)
            git_result = stage_and_commit(message, [index_path], root)
        except BaseException:
            restore_index_best_effort(candidate.id, index_name, pm)
            raise

        if git_result.returncode != 0:
            restore_index_best_effort(candidate.id, index_name, pm)
            # `stage_and_commit()` already cleans the staging area.
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=candidate.id, rejections=(), git_error=None)


def refused_alternatives(
    alternatives: tuple[Note, ...], ctx: Context
) -> tuple[tuple[Note, tuple[Rejection, ...]], ...]:
    """Each refused alternative with its rejections; accepted ones count as existing for the next."""
    refused = []
    accepted: tuple[Note, ...] = ()
    for alternative in alternatives:
        seen = dataclasses.replace(ctx, existing_in_zone=ctx.existing_in_zone + accepted)
        found = validate_note(alternative, seen)
        if found:
            refused.append((alternative, found))
        else:
            label = f"(--discard {len(accepted) + 1})"
            accepted += (dataclasses.replace(alternative, id=label),)
    return tuple(refused)


def discard_alternatives(
    decision: Note,
    alternatives: tuple[Note, ...],
    ctx: Context,
    write_decision: Callable[[Note, Context], WriteResult] = write,
) -> tuple[WriteResult, ...]:
    """Write `decision`, then each alternative in its own commit with `origin` set to the decision's id.

    All alternatives are validated first; any refusal returns one result with every rejection.
    """
    rejections = tuple(r for _alt, found in refused_alternatives(alternatives, ctx) for r in found)
    if rejections:
        return (WriteResult(ok=False, note_id=None, rejections=rejections, git_error=None),)

    decision_result = write_decision(decision, ctx)
    if not decision_result.ok:
        return (decision_result,)

    extended_ctx = dataclasses.replace(
        ctx, known_ids=ctx.known_ids | {decision_result.note_id}
    )

    results = [decision_result]
    for alternative in alternatives:
        linked = dataclasses.replace(
            alternative, origin=(decision_result.note_id,) + alternative.origin
        )
        results.append(write(linked, extended_ctx))
    return tuple(results)


def replace(new: Note, old_id: str, ctx: Context) -> WriteResult:
    """Replace `old_id` with `new` in one commit, archiving the old note as replaced."""
    old_type = old_id.split("-", 1)[0]
    old_index_name = _TYPE_TO_INDEX_FILE.get(old_type)
    if old_index_name is None:
        raise ValueError(f"{old_id!r}: tipo desconocido, ningun indice le corresponde")
    return swap_and_archive(
        old_id, old_index_name, new, ctx, destination="replaced", link_replaces=True
    )


def _reject_close_reason_multiline(note_id: str, reason: str) -> Rejection | None:
    """Rejection if `reason` holds a newline (it would split its ARCHIVED.md line), else None."""
    if "\n" not in reason:
        return None
    what = "el motivo de cierre trae un salto de linea propio"
    options = (
        f'  "{reason}"',
        "",
        "El motivo entra en ARCHIVED.md como una sola linea fisica -- un salto",
        "de linea ahi parte la entrada en dos, o la funde con la linea",
        "siguiente. No se puede guardar tal cual.",
        "",
        "Vuelve a intentarlo con el motivo en una sola linea.",
    )
    command = (f'gitmem remove {note_id} "<motivo sin saltos de linea>"',)
    return rejection_.build(
        kind="close_reason_multiline", what=what, options=options, command=command
    )


def close(
    note_id: str,
    reason: str,
    ctx: Context,
    commit: str | None = None,
    relaunch_for: Callable[[str], str] | None = None,
) -> WriteResult:
    """Close `note_id` in one commit: move it from its index to ARCHIVED.md as "closed: <reason>".

    Rejected before any write when `reason` is multiline, or when several live lines carry
    `note_id` and `commit` does not pick one; `relaunch_for(sha)` builds that relaunch command.
    """
    del ctx  # unused; kept for a uniform signature
    rejection = _reject_close_reason_multiline(note_id, reason)
    if rejection is not None:
        return WriteResult(ok=False, note_id=None, rejections=(rejection,), git_error=None)
    root = repo_root()
    pm = pm_root(root)
    with gitcmd.file_lock(lock_resource(root)):
        indexes.seed(pm)
        note_type = note_id.split("-", 1)[0]
        index_name = _TYPE_TO_INDEX_FILE.get(note_type)
        if index_name is None:
            raise ValueError(f"{note_id!r}: tipo desconocido, ningun indice le corresponde")
        index_path = pm / index_name
        index_snapshot = index_path.read_text(encoding="utf-8")
        lines = indexes.read(index_name, pm)
        if relaunch_for is None:
            relaunch_for = notes_duplicate.remove_relaunch(note_id, shlex.quote(reason))
        line, duplicate = notes_duplicate.pick(note_id, lines, commit, relaunch_for)
        if duplicate is not None:
            return WriteResult(ok=False, note_id=None, rejections=(duplicate,), git_error=None)
        indexes.remove(note_id, index_name, pm, only=line)
        if line is None:  # should not happen
            raise RuntimeError(f"inconsistencia interna: {note_id!r} se retiro de {index_name}")

        archive_path = pm / _ARCHIVE_FILE
        archive_snapshot = archive_path.read_text(encoding="utf-8")
        indexes.archive(
            ArchiveLine(
                date=datetime.now(timezone.utc).date(), type=note_type, id=note_id,
                zone1=line.zone1, zone2=line.zone2, headline=line.headline,
                destination="closed", destination_detail=reason,
            ),
            pm,
        )

        touched = [index_path, archive_path]

        def _restore_all() -> None:
            restore_snapshot_best_effort(index_path, index_snapshot)
            restore_snapshot_best_effort(archive_path, archive_snapshot)

        try:
            git_result = stage_and_commit(f"closed: {reason}", touched, root)
        except BaseException:
            _restore_all()
            raise

        if git_result.returncode != 0:
            _restore_all()
            # `stage_and_commit()` already cleans the staging area.
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=note_id, rejections=(), git_error=None)
