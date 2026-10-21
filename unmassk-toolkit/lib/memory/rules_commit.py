"""File and git mechanics of `rules.py`: lock, path, reading `.claude/project-memory/rules.md` and committing it."""

from pathlib import Path

import gitcmd
import notes_commit


# Literal header of the rules file.
_RULES_HEADER = "# RULES — reglas de trabajo (remember). Lo escribe el script. No editar. Si diverge, manda git.\n"


def rules_file_path(root: Path) -> Path:
    """Path of the rules file."""
    return root / ".claude" / "project-memory" / "rules.md"


def lock_resource(root: Path) -> Path:
    """Lock path that serializes concurrent `add()` calls (not other git writers)."""
    return root / ".git" / "memory-rules"


def repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def read_current_rules_content(path: Path) -> tuple[bool, str]:
    """Return `(exists, content)` of the rules file; a missing file yields the bare header."""
    exists = path.exists()
    content = path.read_text(encoding="utf-8") if exists else _RULES_HEADER + "\n"
    return exists, content


def _restore_or_delete_best_effort(
    path: Path, previous_content: str, file_existed_before: bool
) -> None:
    """Best-effort undo after a failed commit: restore the previous content, or delete a file this call created."""
    if file_existed_before:
        notes_commit.restore_snapshot_best_effort(path, previous_content)
        return
    try:
        path.unlink()
    except OSError:
        pass  # already gone; best effort


def commit_or_restore(
    path: Path, previous_content: str, message: str, root: Path, file_existed_before: bool
) -> str | None:
    """Commit `path`; on failure undo the write. Return None on success, else a non-empty stderr."""
    try:
        git_result = notes_commit.stage_and_commit(message, [path], root)
    except BaseException:
        _restore_or_delete_best_effort(path, previous_content, file_existed_before)
        raise
    if git_result.returncode != 0:
        _restore_or_delete_best_effort(path, previous_content, file_existed_before)
        return git_result.stderr
    return None


def read_all() -> str:
    """The whole rules file, or "" if there is none; read under the `add()` lock."""
    root = repo_root()
    with gitcmd.file_lock(lock_resource(root)):
        path = rules_file_path(root)
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")
