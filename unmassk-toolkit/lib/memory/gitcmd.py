"""Memory's git layer: run git without losing its message, commit exact paths,
lock files across processes and write files atomically.
"""

import errno
import os
import subprocess
import sys
import tempfile
import threading
from collections.abc import Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

GIT_TIMEOUT = 10  # seconds, for repo_root()/commit(), which take no timeout


@dataclass(frozen=True)
class GitResult:
    """Result of a git call; `stderr` always carries git's full message on failure."""

    returncode: int
    stdout: str
    stderr: str


def _decode_std(value: bytes | str) -> str:
    """Decode raw subprocess output without translating newlines; `str` passes through."""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return value


def run(
    args: Sequence[str], cwd: Path, timeout: int, env: Mapping[str, str] | None = None
) -> GitResult:
    """Run `git <args>` in `cwd` and return its result; never raises.

    A missing git binary returns code 127 and a timeout returns code 124.
    """
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            timeout=timeout,
            # `env` is overlaid on the real environment, never replaces it.
            env={**os.environ, **env} if env else None,
        )
    except subprocess.TimeoutExpired:
        return GitResult(
            returncode=124,
            stdout="",
            stderr=f"git {list(args)!r} no termino dentro de {timeout}s (cwd={cwd})",
        )
    except OSError as e:
        return GitResult(
            returncode=127,
            stdout="",
            stderr=f"no se pudo ejecutar git {list(args)!r}: {e}",
        )
    stdout = _decode_std(proc.stdout)
    stderr = _decode_std(proc.stderr)
    if proc.returncode != 0 and not stderr.strip() and stdout.strip():
        # Some git failures report their reason on stdout only.
        stderr = stdout
    return GitResult(returncode=proc.returncode, stdout=stdout, stderr=stderr)


def repo_root(cwd: Path) -> Path:
    """Return the root of the git repository containing `cwd`; raise RuntimeError if none."""
    result = run(["rev-parse", "--show-toplevel"], cwd=cwd, timeout=GIT_TIMEOUT)
    if result.returncode != 0:
        raise RuntimeError(f"git rev-parse --show-toplevel fallo en {cwd}: {result.stderr}")
    return Path(result.stdout.strip())


def commit(
    message: str, paths: Sequence[Path], allow_empty: bool, cwd: Path | None = None
) -> GitResult:
    """Commit exactly `paths` (required, non-empty), ignoring anything else staged.

    `cwd` defaults to the process cwd. `--cleanup=verbatim` keeps the
    trailing spaces that `format.py` uses inside folded fields.
    """
    if not paths:
        raise ValueError(
            "commit() exige al menos una ruta explicita en `paths` -- un "
            "pathspec vacio commitearia el indice completo, justo lo que "
            "esta funcion existe para evitar"
        )
    args = ["commit", "--cleanup=verbatim"]
    if allow_empty:
        args.append("--allow-empty")
    args += ["-m", message, "--", *(str(p) for p in paths)]
    return run(args, cwd=cwd if cwd is not None else Path.cwd(), timeout=GIT_TIMEOUT)


def commit_empty(message: str) -> GitResult:
    """Make an empty commit with `--cleanup=verbatim` in the process cwd."""
    args = ["commit", "--cleanup=verbatim", "--allow-empty", "-m", message]
    return run(args, cwd=Path.cwd(), timeout=GIT_TIMEOUT)


# --- exclusive cross-process lock, with nesting detection ---

# Paths held by each thread in this process: detects nesting before the OS lock would hang.
_held_locks_guard = threading.Lock()
_held_locks: dict[str, int] = {}

# The only Windows errno that _acquire_platform_lock() retries on.
_MSVCRT_LOCK_CONTENDED_ERRNO = getattr(errno, "EDEADLOCK", None)


class _LockNotReentrantError(RuntimeError):
    """`file_lock()` was nested on the same path in the same thread."""


def _acquire_platform_lock(fd: int) -> None:
    """Take the exclusive OS lock on `fd`, blocking until it is free."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        while True:
            try:
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                return
            except OSError as e:
                if (
                    _MSVCRT_LOCK_CONTENDED_ERRNO is not None
                    and e.errno == _MSVCRT_LOCK_CONTENDED_ERRNO
                ):
                    continue  # lock still contended
                raise
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_EX)


def _release_platform_lock(fd: int) -> None:
    """Release the lock taken by `_acquire_platform_lock()` on `fd`."""
    if sys.platform == "win32":
        import msvcrt

        os.lseek(fd, 0, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(fd, fcntl.LOCK_UN)


def _same_file(fd: int, path: str) -> bool:
    """True if `fd` is still the same inode that `path` names right now."""
    try:
        path_stat = os.stat(path)
    except OSError:
        return False
    fd_stat = os.fstat(fd)
    return (fd_stat.st_dev, fd_stat.st_ino) == (path_stat.st_dev, path_stat.st_ino)


def _acquire_live_lock(lock_path: str) -> int:
    """Open and lock `lock_path`, retrying until the locked inode is the one the path names."""
    while True:
        fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
        try:
            _acquire_platform_lock(fd)
        except BaseException:
            os.close(fd)
            raise
        if _same_file(fd, lock_path):
            return fd
        # Stale inode: the path was removed or recreated meanwhile; retry.
        _release_platform_lock(fd)
        os.close(fd)


def _release_live_lock(fd: int, lock_path: str) -> None:
    """Release the lock and delete `lock_path`.

    POSIX deletes before unlocking; Windows unlocks and closes first,
    because an open file cannot be deleted there.
    """
    if sys.platform == "win32":
        _release_platform_lock(fd)
        os.close(fd)
        try:
            os.unlink(lock_path)
        except OSError:
            pass  # already gone or recreated by another process
    else:
        try:
            os.unlink(lock_path)
        except OSError:
            pass
        _release_platform_lock(fd)
        os.close(fd)


@contextmanager
def file_lock(path: Path):
    """Hold an exclusive cross-process lock on `path` via `<path>.lock`, deleted on release.

    Not reentrant: nesting on the same path in the same thread raises
    `_LockNotReentrantError` instead of hanging.
    """
    abs_path = os.path.abspath(str(path))
    current_thread = threading.get_ident()

    with _held_locks_guard:
        if _held_locks.get(abs_path) == current_thread:
            raise _LockNotReentrantError(
                f"file_lock() ya esta tomado sobre {abs_path!r} por este "
                "mismo hilo -- no es reentrante (PIEZAS.md Sec.7.1, fila 4)"
            )

    lock_path = f"{abs_path}.lock"
    fd = _acquire_live_lock(lock_path)
    with _held_locks_guard:
        _held_locks[abs_path] = current_thread
    try:
        yield
    finally:
        with _held_locks_guard:
            _held_locks.pop(abs_path, None)
        _release_live_lock(fd, lock_path)


def atomic_write(path: Path, content: str) -> None:
    """Write `content` to `path` atomically: temp file, fsync, then `os.replace()`."""
    path_str = str(path)
    dest_dir = os.path.dirname(os.path.abspath(path_str)) or "."
    fd, tmp_path = tempfile.mkstemp(
        dir=dest_dir, prefix=f".{os.path.basename(path_str)}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path_str)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
