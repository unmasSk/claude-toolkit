"""Apply a `health.rebuild_plan()` to the real indexes and commit it in one commit, all-or-nothing.

When the repaired files already match HEAD there is nothing to commit, and that counts as success."""

from pathlib import Path

import gitcmd
import indexes
from model import IndexLine, Note, WriteResult
from notes_commit import lock_resource, restore_snapshot_best_effort


def _build_message(
    to_insert: tuple[tuple[Note, str], ...], to_remove: tuple[tuple[str, str], ...]
) -> str:
    """Return the repair commit message, naming every reinserted and removed id."""
    parts = []
    if to_insert:
        parts.append("reinsertadas: " + ", ".join(note.id for note, _target in to_insert))
    if to_remove:
        parts.append("retiradas: " + ", ".join(note_id for note_id, _name in to_remove))
    return "rezones: reparación de índices (" + "; ".join(parts) + ")"


def apply_rebuild_plan(
    to_insert: tuple[tuple[Note, str], ...],
    to_remove: tuple[tuple[str, str], ...],
    pm: Path,
    root: Path,
) -> WriteResult:
    """Apply the plan to the indexes in `pm` under the global lock and commit it.

    On any git failure or exception every touched file is restored from its snapshot; an empty plan is a no-op."""
    touched_names = {target for _note, target in to_insert} | {name for _note_id, name in to_remove}
    if not touched_names:
        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)

    with gitcmd.file_lock(lock_resource(root)):
        touched_paths = {
            pm / name: (pm / name).read_text(encoding="utf-8") for name in touched_names
        }
        path_args = [str(p) for p in touched_paths]

        def _restore_all() -> None:
            for path, original in touched_paths.items():
                restore_snapshot_best_effort(path, original)

        def _reset_staged() -> None:
            gitcmd.run(["reset", "--", *path_args], cwd=root, timeout=gitcmd.GIT_TIMEOUT)

        try:
            for note, target in to_insert:
                indexes.insert(
                    IndexLine(
                        id=note.id, zone1=note.zone1, zone2=note.zone2, headline=note.headline
                    ),
                    target,
                    pm,
                )
            for note_id, name in to_remove:
                indexes.remove(note_id, name, pm)

            add_result = gitcmd.run(["add", "--", *path_args], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
            if add_result.returncode != 0:
                _restore_all()
                return WriteResult(
                    ok=False, note_id=None, rejections=(), git_error=add_result.stderr
                )

            diff_result = gitcmd.run(
                ["diff", "--cached", "--quiet", "--", *path_args],
                cwd=root, timeout=gitcmd.GIT_TIMEOUT,
            )
            if diff_result.returncode == 0:
                # Already identical to HEAD: nothing to commit, nothing to lose.
                return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)
            if diff_result.returncode != 1:
                _restore_all()
                _reset_staged()
                return WriteResult(
                    ok=False, note_id=None, rejections=(), git_error=diff_result.stderr
                )

            message = _build_message(to_insert, to_remove)
            git_result = gitcmd.commit(message, list(touched_paths), allow_empty=False, cwd=root)
        except BaseException:
            _restore_all()
            _reset_staged()
            raise

        if git_result.returncode != 0:
            _restore_all()
            _reset_staged()
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)
