"""Git subprocess wrappers and symlink-safe, atomic and locked file helpers for unmassk-toolkit."""

import contextlib
import errno
import os
import signal
import subprocess
import sys
import tempfile
import time


# Runtime directory for all generated files: one gitignore entry.
UNMASSK_RUNTIME_DIR = ".claude/.unmassk"

_GENERATED_JSONS = [
    ".claude/.unmassk/",
    # Memory-system lock files only; never a bare `*.lock` (Cargo.lock, bun.lock must stay tracked).
    ".claude/project-memory/*.lock",
]


class UnsafePathError(OSError):
    """A project-relative path resolves outside project_root (an OSError, so `except OSError` catches it)."""


def verify_path_within_project(path: str, project_root: str) -> str:
    """Return the real path of `path`, raising UnsafePathError if it resolves outside `project_root`.

    Resolves symlinks in every component, parents included; safe before the target exists.
    """
    resolved_root = os.path.realpath(project_root)
    resolved = os.path.realpath(path)
    valid_prefix = resolved_root + os.sep

    # Case-insensitive comparison on Windows.
    if sys.platform == "win32":
        compare_resolved = os.path.normcase(resolved)
        compare_root = os.path.normcase(resolved_root)
        compare_prefix = os.path.normcase(valid_prefix)
    else:
        compare_resolved = resolved
        compare_root = resolved_root
        compare_prefix = valid_prefix

    if compare_resolved == compare_root or compare_resolved.startswith(compare_prefix):
        return resolved
    raise UnsafePathError(
        f"Refusing to use path '{path}': it resolves to '{resolved}', "
        f"which escapes the project root '{resolved_root}' — likely via a "
        f"symlinked intermediate directory (e.g. .claude itself)."
    )


def ensure_runtime_dir(project_root: str) -> str:
    """Create .claude/.unmassk/ if missing and return its path; UnsafePathError if it escapes the project."""
    runtime_dir = os.path.join(project_root, UNMASSK_RUNTIME_DIR)
    verify_path_within_project(runtime_dir, project_root)
    os.makedirs(runtime_dir, exist_ok=True)
    return runtime_dir


# Atomic-write temp files older than this are orphans of a killed process.
_ATOMIC_TEMP_ORPHAN_MAX_AGE_SECONDS = 3600  # 1 hour


def _sweep_orphaned_atomic_temp_files(dest_dir: str, basename: str) -> None:
    """Best-effort removal of stale `.{basename}.*.tmp` files left in `dest_dir` by dead atomic writes.

    Only files older than _ATOMIC_TEMP_ORPHAN_MAX_AGE_SECONDS go, so a live writer's temp file is kept;
    errors are swallowed.
    """
    prefix = f".{basename}."
    suffix = ".tmp"
    try:
        candidates = os.listdir(dest_dir)
    except OSError:
        return
    now = time.time()
    for name in candidates:
        if not (name.startswith(prefix) and name.endswith(suffix)):
            continue
        candidate = os.path.join(dest_dir, name)
        try:
            age = now - os.stat(candidate).st_mtime
            if age > _ATOMIC_TEMP_ORPHAN_MAX_AGE_SECONDS:
                os.unlink(candidate)
        except OSError:
            pass  # gone already, permission denied, or a live race — leave it


class _AtomicWriteNoFollowSymlink:
    """Atomic writer returned by open_no_follow_symlink(path, "w", atomic=True).

    Writes go to a temp file in `path`'s directory, moved over `path` with os.replace() only on a
    clean `with` exit; on an exception `path` keeps its original content. Refuses a `path` that is
    a symlink (ELOOP). The existing file mode is preserved on POSIX. os.replace() breaks hard
    links: a hard-linked sibling keeps the old content.
    """

    def __init__(self, path: str, encoding: str, errors: str):
        if os.path.islink(path):
            raise OSError(errno.ELOOP, "Refusing to open a symlink", path)
        dest_dir = os.path.dirname(os.path.abspath(path)) or "."
        basename = os.path.basename(path)
        _sweep_orphaned_atomic_temp_files(dest_dir, basename)
        fd, tmp_path = tempfile.mkstemp(dir=dest_dir, prefix=f".{basename}.", suffix=".tmp")
        try:
            self._file = os.fdopen(fd, "w", encoding=encoding, errors=errors)
        except BaseException:
            # fdopen() failed: close the raw fd and remove the temp file.
            try:
                os.close(fd)
            except OSError:
                pass
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
        self._path = path
        self._tmp_path = tmp_path
        self._committed = False

    def write(self, data: str) -> int:
        return self._file.write(data)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        try:
            if exc_type is None:
                try:
                    self._file.flush()
                    os.fsync(self._file.fileno())
                finally:
                    # Close even when flush/fsync raised.
                    self._file.close()
                # Keep the existing file's mode (mkstemp creates 0o600); POSIX only.
                if sys.platform != "win32" and os.path.exists(self._path):
                    try:
                        existing_mode = os.stat(self._path).st_mode & 0o777
                        os.chmod(self._tmp_path, existing_mode)
                    except OSError as e:
                        # Best-effort, but never silent.
                        print(
                            f"[git_helpers] WARNING: could not preserve permissions "
                            f"for {self._path!r} — new content written, mode stays "
                            f"0600: {e}",
                            file=sys.stderr,
                        )
                os.replace(self._tmp_path, self._path)
                self._committed = True
            else:
                self._file.close()
        finally:
            if not self._committed:
                try:
                    os.unlink(self._tmp_path)
                except OSError:
                    pass  # already gone, or never fully created — nothing to clean up
        return False  # never swallow the caller's exception

    def close(self) -> None:
        """Discard the temp file; raise OSError unless the write was already committed by `with`.

        Commit only by leaving the `with` block normally.
        """
        try:
            self._file.close()
        finally:
            if not self._committed:
                try:
                    os.unlink(self._tmp_path)
                except OSError:
                    pass
        if not self._committed:
            raise OSError(
                errno.EBADF,
                "close() called directly on an atomic writer without going "
                "through 'with' -- the write was abandoned, never "
                "committed; use 'with open_no_follow_symlink(path, \"w\", "
                "atomic=True) as f: ...' instead",
                self._path,
            )


def open_no_follow_symlink(
    path: str,
    mode: str = "w",
    encoding: str = "utf-8",
    reject_hardlinks: bool = False,
    errors: str = "strict",
    atomic: bool = False,
):
    """Open `path` ("r", "w" or "a") without following a symlink at the final component.

    POSIX uses O_NOFOLLOW; Windows checks islink() and that the file identity did not change
    across the open. New files are created 0o600. `atomic=True` (mode "w" only) returns an
    _AtomicWriteNoFollowSymlink. `reject_hardlinks=True` refuses a file with st_nlink > 1 (EMLINK);
    use it only for toolkit-generated files. `errors` is passed to fdopen.

    Raises OSError (ELOOP for a symlink or identity change); callers must not fall back to
    following the link.
    """
    if atomic:
        if mode != "w":
            raise ValueError(f"open_no_follow_symlink(atomic=True) only supports mode='w', got {mode!r}")
        return _AtomicWriteNoFollowSymlink(path, encoding, errors)

    if sys.platform == "win32":
        return _open_no_follow_symlink_windows(path, mode, encoding, reject_hardlinks, errors)

    defer_truncate = False
    if mode == "r":
        flags = os.O_RDONLY | os.O_NOFOLLOW
        fd = os.open(path, flags)
    else:
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        if mode == "a":
            flags |= os.O_APPEND
        elif reject_hardlinks:
            # Defer O_TRUNC until the hard-link check passes.
            defer_truncate = True
        else:
            flags |= os.O_TRUNC
        fd = os.open(path, flags, 0o600)

    if reject_hardlinks:
        try:
            if os.fstat(fd).st_nlink > 1:
                raise OSError(
                    errno.EMLINK,
                    "Refusing to open a hard-linked file (st_nlink > 1); "
                    "reject_hardlinks=True forbids opening a multi-link path",
                    path,
                )
            if defer_truncate:
                os.ftruncate(fd, 0)
        except BaseException:
            os.close(fd)
            raise

    return os.fdopen(fd, mode, encoding=encoding, errors=errors)


def _open_no_follow_symlink_windows(
    path: str, mode: str, encoding: str, reject_hardlinks: bool = False,
    errors: str = "strict",
):
    """Windows branch of open_no_follow_symlink(); keep it identical to
    _symlink_safe_open._open_no_follow_symlink_windows()."""
    if os.path.islink(path):
        # ELOOP on every platform, for one errno across both rejections.
        raise OSError(errno.ELOOP, "Refusing to open a symlink", path)

    # Identity before the open; a new path has none to compare.
    prior_identity = None
    if os.path.exists(path):
        prior_identity = os.lstat(path)

    if mode == "r":
        fd = os.open(path, os.O_RDONLY)
    else:
        # No O_TRUNC: truncate only after the identity check passes.
        flags = os.O_WRONLY | os.O_CREAT
        flags |= os.O_APPEND if mode == "a" else 0
        fd = os.open(path, flags, 0o600)

    try:
        if prior_identity is not None:
            post_identity = os.fstat(fd)
            if (post_identity.st_dev, post_identity.st_ino) != (
                prior_identity.st_dev, prior_identity.st_ino,
            ):
                # Same errno as the direct-symlink rejection.
                raise OSError(
                    errno.ELOOP,
                    "Refusing to open: file identity changed between the "
                    "pre-open check and the open() call (possible symlink race)",
                    path,
                )
        if reject_hardlinks:
            # Checked on the open fd, not the path.
            if os.fstat(fd).st_nlink > 1:
                raise OSError(
                    errno.EMLINK,
                    "Refusing to open a hard-linked file (st_nlink > 1); "
                    "reject_hardlinks=True forbids opening a multi-link path",
                    path,
                )
        if mode == "w":
            os.ftruncate(fd, 0)
    except BaseException:
        os.close(fd)
        raise

    return os.fdopen(fd, mode, encoding=encoding, errors=errors)


# Errno msvcrt.locking(LK_LOCK) raises while the region is still held; the only one file_lock() retries.
_MSVCRT_LOCK_CONTENDED_ERRNO = getattr(errno, "EDEADLOCK", None)


@contextlib.contextmanager
def file_lock(target_path: str, lock_path: str | None = None):
    """Exclusive cross-process advisory lock on `lock_path` (default `{target_path}.lock`) for a read-modify-write.

    Blocks until acquired and is released on exit; not reentrant (a nested call deadlocks).
    The lock file is created if missing and never removed. POSIX uses fcntl.flock; Windows
    re-issues msvcrt.locking while it reports contention and raises on any other error.
    """
    if lock_path is None:
        lock_path = f"{target_path}.lock"
    fd = os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            while True:
                try:
                    msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
                    break
                except OSError as e:
                    if (
                        _MSVCRT_LOCK_CONTENDED_ERRNO is not None
                        and e.errno == _MSVCRT_LOCK_CONTENDED_ERRNO
                    ):
                        # Still contended: msvcrt's ~10 s attempt expired; retry.
                        continue
                    raise  # permanent failure -- never resolves by retrying
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def claude_md_lock_path(project_root: str) -> str:
    """Shared file_lock() path for every writer of CLAUDE.md's managed blocks, under .claude/.unmassk/.

    May raise OSError from ensure_runtime_dir().
    """
    return os.path.join(ensure_runtime_dir(project_root), "claude_md.lock")


def ensure_gitignore(project_root: str, entry: str | None = None) -> None:
    """Ensure generated JSON files are in the project's .gitignore.

    Args:
        project_root: Path to the project root (where .gitignore lives).
        entry: Single entry to add. If None, adds all _GENERATED_JSONS.
    """
    entries = [entry] if entry else _GENERATED_JSONS
    gitignore_path = os.path.join(project_root, ".gitignore")
    try:
        existing = ""
        if os.path.isfile(gitignore_path):
            try:
                # A symlinked .gitignore reads as absent; the guarded append then fails closed.
                with open_no_follow_symlink(gitignore_path, "r") as f:
                    existing = f.read()
            except OSError:
                existing = ""
        missing = [e for e in entries if e not in existing]
        if not missing:
            return
        block = "\n".join(missing)
        separator = "" if existing.endswith("\n") or not existing else "\n"
        with open_no_follow_symlink(gitignore_path, "a") as f:
            f.write(f"{separator}\n# unmassk-toolkit generated (do not track)\n{block}\n")
    except OSError as e:
        print(f"[unmassk-toolkit] WARNING: could not update .gitignore at {gitignore_path}: {e}", file=sys.stderr)


GIT_TIMEOUT: int = 10  # seconds


def _win32_kill_tree(proc: subprocess.Popen) -> None:
    """Windows: kill `proc` and all its descendants with `taskkill /F /T`, falling back to proc.kill().

    Never raises for a missing taskkill or an already exited process. Re-parented descendants survive.
    """
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        # taskkill missing, denied or timed out: kill the direct child only.
        try:
            proc.kill()
        except OSError:
            pass  # already exited — nothing left to kill


def run_git(
    args: list[str],
    timeout: int = GIT_TIMEOUT,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    log_stderr_on_failure: bool = False,
) -> tuple[int, str]:
    """Run a git command and return (exit_code, stdout).

    Args:
        args:    Git subcommand and arguments (e.g. ["log", "--oneline"]).
        timeout: Max seconds to wait before killing the process tree.
        cwd:     Working directory for the git process. None = inherit caller cwd.
        env:     Overrides merged over a copy of os.environ. None = inherit unchanged.
        log_stderr_on_failure: print git's truncated stderr when it exits non-zero. Off by
                 default because many callers expect non-zero exits.

    Returns:
        Tuple of (exit_code, stripped_stdout). Returns (1, "") on any error.
    """
    proc = None
    try:
        merged_env = {**os.environ, **env} if env is not None else None
        # Own process group, so a timeout can kill git's whole tree (ssh, askpass, helpers).
        popen_kwargs = (
            {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP}
            if sys.platform == "win32"
            else {"start_new_session": True}
        )
        proc = subprocess.Popen(
            ["git"] + args,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            cwd=cwd, env=merged_env,
            **popen_kwargs,
        )
        stdout_bytes, stderr_bytes = proc.communicate(timeout=timeout)
        # Decode bytes by hand: no newline translation, a `\r` git wrote is kept.
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
        if log_stderr_on_failure and proc.returncode != 0 and stderr and stderr.strip():
            # Truncated: a breadcrumb, not a transcript.
            print(
                f"[git_helpers] git {args[0]!r} exited {proc.returncode}: "
                f"{stderr.strip()[:300]}",
                file=sys.stderr,
            )
        return proc.returncode, stdout.strip()
    except subprocess.TimeoutExpired:
        if proc is not None:
            if sys.platform == "win32":
                try:
                    _win32_kill_tree(proc)
                except Exception:
                    # Fall back to killing the direct child.
                    proc.kill()
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    # Group gone or not ours: kill the direct child only.
                    proc.kill()
            try:
                proc.communicate(timeout=1)  # reap; discard any late output
            except (subprocess.TimeoutExpired, ValueError):
                pass
        print(f"[git_helpers] git {args[0]!r} timed out after {timeout}s", file=sys.stderr)
        return 1, ""
    except UnicodeDecodeError as e:
        # Decode failures leave a breadcrumb; the return is the same (1, "").
        print(
            f"[git_helpers] git {args[0]!r} output was not valid UTF-8 and "
            f"could not be decoded: {e}",
            file=sys.stderr,
        )
        return 1, ""
    except (subprocess.SubprocessError, OSError, ValueError):
        # Callers treat (1, "") as "no git output" whatever the cause.
        return 1, ""


# Bounded retry for read-path git calls: total tries and fixed pause between them.
READ_RETRY_ATTEMPTS: int = 3
READ_RETRY_BACKOFF_SECONDS: float = 0.1

# Wall-clock budget for the whole retry sequence; each attempt's timeout is capped to what is left.
# No new attempt starts with less than READ_RETRY_MIN_ATTEMPT_SECONDS left.
READ_RETRY_DEADLINE_SECONDS: float = float(GIT_TIMEOUT)
READ_RETRY_MIN_ATTEMPT_SECONDS: float = 0.5


def run_git_read_retrying(run_git_fn, args: list[str], **kwargs) -> tuple[int, str]:
    """Call `run_git_fn(args, **kwargs)` until it exits 0, up to READ_RETRY_ATTEMPTS within READ_RETRY_DEADLINE_SECONDS.

    Returns the first success (an empty rc=0 result included) or the last failure unchanged.
    `timeout=` is always passed to `run_git_fn`, capped to the remaining budget, so it must
    accept it. A caller's `log_stderr_on_failure` applies only to the last attempt.
    Read-path calls only: never retry a git write.
    """
    has_warn_kwarg = "log_stderr_on_failure" in kwargs
    want_warn = kwargs.pop("log_stderr_on_failure", False) if has_warn_kwarg else False
    base_timeout = kwargs.pop("timeout", GIT_TIMEOUT)

    deadline = time.monotonic() + READ_RETRY_DEADLINE_SECONDS
    code, output = 1, ""
    for attempt in range(1, READ_RETRY_ATTEMPTS + 1):
        remaining = deadline - time.monotonic()
        if attempt > 1 and remaining <= READ_RETRY_MIN_ATTEMPT_SECONDS:
            break  # not enough budget left for another attempt
        is_final_attempt = attempt == READ_RETRY_ATTEMPTS
        call_kwargs = dict(kwargs)
        call_kwargs["timeout"] = max(0.1, min(remaining, base_timeout))
        if has_warn_kwarg:
            call_kwargs["log_stderr_on_failure"] = want_warn and is_final_attempt
        code, output = run_git_fn(args, **call_kwargs)
        if code == 0:
            return code, output
        if is_final_attempt:
            break
        if (deadline - time.monotonic()) <= READ_RETRY_MIN_ATTEMPT_SECONDS:
            break  # this attempt used up the budget
        time.sleep(READ_RETRY_BACKOFF_SECONDS)
    return code, output


def is_git_repo() -> bool:
    """Check if we're in a git repository."""
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def is_shallow_clone() -> bool:
    """Check if the repository is a shallow clone."""
    code, output = run_git(["rev-parse", "--is-shallow-repository"])
    return code == 0 and output == "true"
