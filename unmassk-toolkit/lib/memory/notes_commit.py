"""Git mechanics under notes.py: global write lock, index root, stage+commit, best-effort restores and the work commit.

Imports nothing from notes.py; notes.py re-exports these names.
"""

import dataclasses
import hashlib
import os
import re
import tempfile
from pathlib import Path

import gitcmd
import indexes
from model import WriteResult


def lock_resource(root: Path) -> Path:
    """Base path of the global write lock, inside `.git/` so it never shows in `git status`."""
    return Path(root) / ".git" / "memory-notes"


def repo_root() -> Path:
    return gitcmd.repo_root(Path.cwd())


def pm_root(root: Path) -> Path:
    """Return `.claude/project-memory/` under the bare repo root `root`."""
    return Path(root) / ".claude" / "project-memory"


def _path_in_index(path: Path, root: Path) -> bool:
    """True if `path` still has an entry in the git index."""
    result = gitcmd.run(
        ["ls-files", "--error-unmatch", "--", str(path)],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    return result.returncode == 0


def stage_and_commit(message: str, paths: list[Path], root: Path) -> gitcmd.GitResult:
    """`git add --all` the given paths, then commit them; failed results always carry a non-empty stderr.

    Paths absent from both the work tree and the index skip `add` but still go to `commit`.
    If the commit fails after `add`, the staging is undone (best effort).
    """
    # `--all` also records deletions, still limited to the given pathspec.
    addable_paths = [p for p in paths if os.path.exists(p) or _path_in_index(p, root)]
    if addable_paths:
        add_result = gitcmd.run(
            ["add", "--all", "--", *(str(p) for p in addable_paths)],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
        if add_result.returncode != 0:
            return _ensure_nonempty_stderr(add_result)
    commit_result = gitcmd.commit(message, paths, allow_empty=False, cwd=root)
    if commit_result.returncode != 0 and addable_paths:
        # Best effort: unstage what `add` staged; the reported failure stays commit_result.
        gitcmd.run(
            ["reset", "--", *(str(p) for p in addable_paths)],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
    return _ensure_nonempty_stderr(commit_result)


# Fallback when git fails silently (e.g. a pre-commit hook that exits 1 with no output).
_GIT_FAILED_NO_MESSAGE = "git rechazo la operacion sin dar ningun mensaje (revisa hooks de pre-commit)"


def _ensure_nonempty_stderr(result: gitcmd.GitResult) -> gitcmd.GitResult:
    """Fill a failed result's empty stderr with a fallback message; never replace a real one."""
    if result.returncode == 0 or result.stderr:
        return result
    return dataclasses.replace(result, stderr=_GIT_FAILED_NO_MESSAGE)


def restore_index_best_effort(note_id: str, index_name: str, pm: Path) -> None:
    """Remove `note_id`'s line from `index_name` under `pm` after a failed commit; swallows errors."""
    try:
        indexes.remove(note_id, index_name, pm)
    except Exception:
        pass


def restore_snapshot_best_effort(path: Path, original_content: str) -> None:
    """Write `original_content` back to `path`; swallows errors."""
    try:
        gitcmd.atomic_write(path, original_content)
    except Exception:
        pass


def _staged_as_new_before_us(path: Path, root: Path) -> bool:
    """True if `path` is already staged as a new file (status `A`) before write_work() stages it."""
    result = gitcmd.run(
        ["diff", "--cached", "--name-status", "--", str(path)],
        cwd=root,
        timeout=gitcmd.GIT_TIMEOUT,
    )
    return result.stdout.startswith("A\t")


def _content_fingerprint(path: Path) -> str | None:
    """sha256 of the raw bytes of `path` in the work tree, or None if it does not exist."""
    try:
        with open(path, "rb") as fh:
            return hashlib.sha256(fh.read()).hexdigest()
    except FileNotFoundError:
        return None


def _relpath_posix(path: Path, root: Path) -> str:
    """`path` relative to `root`, with `/` separators as git expects."""
    return Path(os.path.relpath(str(path), str(root))).as_posix()


def _git_blob_hash_of_bytes(content: bytes, path: Path, root: Path) -> str | None:
    """Blob hash git would store for `content` at `path` (filters applied, nothing written); None on failure.

    Uses `--path`, never `--no-filters`, so autocrlf normalisation matches what `git add` stores.
    """
    fd, tmp_path = tempfile.mkstemp(prefix=".write_work_verify.", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(content)
        result = gitcmd.run(
            ["hash-object", "--path", _relpath_posix(path, root), tmp_path],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
    return result.stdout.strip() if result.returncode == 0 else None


def _committed_blob_hash(path: Path, root: Path) -> str | None:
    """Blob hash of `path` at HEAD, or None if it cannot be determined."""
    rel = _relpath_posix(path, root)
    result = gitcmd.run(["rev-parse", f"HEAD:{rel}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)
    return result.stdout.strip() if result.returncode == 0 else None


# First line of `git commit` output: `[<branch> <short-sha>] <subject>`; greedy `.+` tolerates spaces in the branch.
_COMMIT_SUMMARY_SHA_RE = re.compile(r"^\[.+\s([0-9a-fA-F]{4,40})\]")


def _own_commit_sha_from_commit_output(commit_stdout: str, root: Path) -> str | None:
    """Full sha of the commit just created, parsed from `git commit` output (never from HEAD); None on failure."""
    first_line = commit_stdout.split("\n", 1)[0]
    match = _COMMIT_SUMMARY_SHA_RE.match(first_line)
    if match is None:
        return None
    short_sha = match.group(1)
    result = gitcmd.run(
        ["rev-parse", f"{short_sha}^{{commit}}"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
    )
    return result.stdout.strip() if result.returncode == 0 else None


def write_work(
    message: str,
    paths: list[Path],
    issue: int | None,
    known_content: list[bytes | None] | None = None,
) -> WriteResult:
    """Commit only `paths` with `message` (plus an `Issue: #N` trailer), under the global lock.

    `known_content`, if given, holds the bytes the caller wrote for each path (same order, None
    when unknown). The commit is refused if a path was staged as new by someone else or changed on
    disk since entry; after committing, paths with known content are checked against HEAD and a
    mismatching commit is undone with an atomic `git update-ref` compare-and-set.
    """
    resolved_paths = [Path(os.path.abspath(str(p))) for p in paths]
    if known_content is not None and len(known_content) != len(paths):
        raise ValueError(
            f"known_content tiene {len(known_content)} elemento(s) pero paths "
            f"tiene {len(paths)} -- tienen que ir en el mismo orden, uno por ruta"
        )
    try:
        entry_fingerprints = {
            path: hashlib.sha256(content).hexdigest() if content is not None else _content_fingerprint(path)
            for path, content in zip(resolved_paths, known_content or [None] * len(paths))
        }
    except OSError as exc:
        return WriteResult(ok=False, note_id=None, rejections=(), git_error=str(exc))
    root = repo_root()
    full_message = message if issue is None else f"{message}\n\nIssue: #{issue}"

    with gitcmd.file_lock(lock_resource(root)):
        for path in resolved_paths:
            if _staged_as_new_before_us(path, root):
                return WriteResult(
                    ok=False,
                    note_id=None,
                    rejections=(),
                    git_error=(
                        f"{path} ya aparecia en el indice de git como fichero nuevo "
                        "antes de esta llamada a write_work() -- otro proceso lo "
                        "'git add'-eo por su cuenta, fuera de este candado; "
                        "'git commit -- <ruta>' relee el arbol de trabajo en el "
                        "instante del commit, asi que comitear ahora podria mentir "
                        "sobre el contenido que este escritor preparo. Se aborta con "
                        "causa en vez de comitear un contenido que no se puede verificar."
                    ),
                )

        changed_since_entry = [
            path
            for path in resolved_paths
            if _content_fingerprint(path) != entry_fingerprints[path]
        ]
        if changed_since_entry:
            changed_list = ", ".join(str(p) for p in changed_since_entry)
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    f"el contenido de {changed_list} cambio en disco entre que esta "
                    "llamada a write_work() empezo y el instante de comitear -- otro "
                    "proceso lo escribio por su cuenta mientras esta llamada seguia en "
                    "curso. Se aborta con causa en vez de comitear un contenido que ya "
                    "no es el que este escritor tenia al arrancar."
                ),
            )

        git_result = stage_and_commit(full_message, resolved_paths, root)

        if git_result.returncode != 0:
            gitcmd.run(
                ["reset", "--", *(str(p) for p in resolved_paths)],
                cwd=root,
                timeout=gitcmd.GIT_TIMEOUT,
            )
            return WriteResult(ok=False, note_id=None, rejections=(), git_error=git_result.stderr)

        # Parsed from this commit's own output, never from HEAD.
        own_commit_sha = _own_commit_sha_from_commit_output(git_result.stdout, root)

        mismatched = []
        for path, content in zip(resolved_paths, known_content or [None] * len(resolved_paths)):
            if content is None:
                continue
            expected_hash = _git_blob_hash_of_bytes(content, path, root)
            actual_hash = _committed_blob_hash(path, root)
            if expected_hash is None or actual_hash is None or expected_hash != actual_hash:
                mismatched.append(path)

        if not mismatched:
            return WriteResult(ok=True, note_id=None, rejections=(), git_error=None)

        mismatched_list = ", ".join(str(p) for p in mismatched)
        base_cause = (
            f"el commit se creo pero {mismatched_list} no lleva el contenido "
            "que este escritor tenia en la mano -- otro proceso lo piso justo "
            "en el instante de comitear ('git commit -- <rutas>' relee el "
            "arbol de trabajo)."
        )

        if own_commit_sha is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    base_cause + " Ademas, no se pudo identificar de forma "
                    "fiable el commit que esta llamada acaba de crear -- no "
                    "se intenta deshacer nada sin esa referencia. Hace falta "
                    "revision manual."
                ),
            )

        # Parent of this exact commit, independent of where HEAD is now.
        parent_result = gitcmd.run(
            ["rev-parse", f"{own_commit_sha}~1"], cwd=root, timeout=gitcmd.GIT_TIMEOUT
        )
        parent_sha = parent_result.stdout.strip() if parent_result.returncode == 0 else None

        if parent_sha is None:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    base_cause + f" El commit {own_commit_sha} es el primero "
                    "del repositorio -- no tiene padre al que volver, asi que "
                    f"no se puede deshacer. El commit corrupto {own_commit_sha} "
                    "SIGUE siendo HEAD de verdad. Hace falta arreglarlo a "
                    "mano: revisar y quitar ese commit."
                ),
            )

        # Atomic compare-and-set: move HEAD to the parent only if it is still our commit.
        cas_result = gitcmd.run(
            [
                "update-ref",
                "-m",
                f"write_work(): deshacer commit corrupto {own_commit_sha}",
                "HEAD",
                parent_sha,
                own_commit_sha,
            ],
            cwd=root,
            timeout=gitcmd.GIT_TIMEOUT,
        )

        if cas_result.returncode != 0:
            return WriteResult(
                ok=False,
                note_id=None,
                rejections=(),
                git_error=(
                    base_cause + " El intento de deshacerlo con 'git "
                    f"update-ref' fallo ({cas_result.stderr}) -- lo mas "
                    "probable es que el historial se moviera entre nuestro "
                    "commit y este intento (otro proceso ajeno ya comiteo "
                    "algo legitimo encima), y por eso NO se toca el "
                    f"historial en absoluto. El commit corrupto "
                    f"{own_commit_sha} sigue siendo alcanzable. Hace falta "
                    "revision manual."
                ),
            )

        # Index sync only; best effort.
        gitcmd.run(["reset", "--mixed", "HEAD"], cwd=root, timeout=gitcmd.GIT_TIMEOUT)

        return WriteResult(
            ok=False,
            note_id=None,
            rejections=(),
            git_error=(
                base_cause + " Se deshizo el commit ('git update-ref', "
                "comparar-y-cambiar atomico sobre HEAD, sin tocar el arbol "
                "de trabajo) y se devuelve ok=False con causa en vez de "
                "mentir con ok=True."
            ),
        )
