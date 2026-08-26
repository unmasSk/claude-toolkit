"""
Git command helpers for unmassk-toolkit.

Thin wrappers around subprocess calls to git. Used by hooks,
CLI scripts to run git commands safely.
"""

import contextlib
import errno
import os
import signal
import subprocess
import sys
import tempfile
import time


# Runtime directory for all generated files — single gitignore entry.
# git-memory-scopes.json is NOT here — it lives in agent-memory (per-project, tracked).
UNMASSK_RUNTIME_DIR = ".claude/.unmassk"

_GENERATED_JSONS = [
    ".claude/.unmassk/",
    # El candado del sistema de memoria. Vive junto a `zones.json` (no bajo
    # `.claude/.unmassk/`, que ya esta ignorado por la linea de arriba)
    # porque protege ese fichero, asi que necesita su propia entrada
    # [2026-08-05: se colo en un commit real de este repositorio antes de
    # que existiera esta linea]. Es basura de funcionamiento: lo crea un
    # proceso un instante y sobra despues.
    #
    # DELIBERADAMENTE ESTRECHO -- nunca un `*.lock` a secas: `Cargo.lock`,
    # `bun.lock`, `package-lock.json` y companyia son dependencias que
    # SI tienen que viajar en git, y dejar de versionarlas rompe las
    # instalaciones reproducibles de cualquier proyecto donde se instale
    # el toolkit.
    ".claude/project-memory/*.lock",
]


class UnsafePathError(OSError):
    """Raised when a project-relative path resolves outside project_root.

    Subclasses OSError so every existing call site that already wraps its
    .claude-touching code in `except OSError` (or the broader
    `except Exception`) fails closed on this automatically — no new except
    clause required at each call site.
    """


def verify_path_within_project(path: str, project_root: str) -> str:
    """Resolve `path` to its canonical real path and verify it stays inside
    `project_root`.

    BUG Y / SEC-CRIT-NEW: every prior symlink guard in this codebase
    (open_no_follow_symlink()) protects only the FINAL path component being
    opened. None of them protect the PARENT directories — if `.claude`
    itself is a symlink (git blob mode 120000) pointing outside the repo,
    os.makedirs()/open() silently follow it and every "safe" write lands
    outside the project instead of being rejected.

    Mirrors the pattern hooks/validate-memory-path.py already uses for the
    same class of bug: os.path.realpath() resolves every symlinked
    component of a path, INCLUDING intermediate components that don't
    exist yet at the final segment (verified: a nonexistent tail appended
    to an already-resolved symlinked parent is left literal, not raising) —
    so this check is safe to call before the target file/directory exists.
    Comparing the resolved path against os.path.realpath(project_root) with
    an exact directory-boundary suffix (not a bare substring) catches a
    symlink at ANY intermediate component, not just the last one.

    Returns the resolved real path when it is safe to use.
    Raises UnsafePathError when `path` escapes `project_root`.
    """
    resolved_root = os.path.realpath(project_root)
    resolved = os.path.realpath(path)
    valid_prefix = resolved_root + os.sep

    # Normalize case on Windows to handle drive-letter case mismatches and
    # case-insensitive filesystem bypasses (mirrors
    # hooks/validate-memory-path.py's existing pattern for the same class
    # of check).
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
    """Ensure .claude/.unmassk/ directory exists and return its path.

    Raises UnsafePathError (a subclass of OSError) if any intermediate
    component of the path — including .claude itself — is a symlink that
    escapes project_root (BUG Y). Callers that already catch OSError (or
    Exception) around this call get the fail-safe "never write outside the
    repo" behavior for free, with no call-site changes needed.
    """
    runtime_dir = os.path.join(project_root, UNMASSK_RUNTIME_DIR)
    verify_path_within_project(runtime_dir, project_root)
    os.makedirs(runtime_dir, exist_ok=True)
    return runtime_dir


# Moriarty: a kill -9 mid atomic-write leaves its tempfile.mkstemp() file
# behind forever -- nothing running inside THIS (now-dead) process can ever
# get a chance to clean up that one orphan (Python's own cleanup paths,
# __exit__()'s finally and close()'s finally, both require live code
# running). Left unswept over many crashes, these accumulate as untracked,
# non-gitignored ".tmp" files at the repo root. One hour is far longer than
# any real write in this codebase takes, while still keeping orphans from
# lingering indefinitely once they're this old.
_ATOMIC_TEMP_ORPHAN_MAX_AGE_SECONDS = 3600  # 1 hour


def _sweep_orphaned_atomic_temp_files(dest_dir: str, basename: str) -> None:
    """Opportunistic best-effort cleanup of abandoned atomic-write temp
    files (Moriarty finding #2): every atomic write is a natural chance to
    sweep whatever ITS OWN naming pattern (prefix=f".{basename}.",
    suffix=".tmp" -- exactly what _AtomicWriteNoFollowSymlink.__init__'s
    own tempfile.mkstemp() call below uses) has left behind from a PRIOR,
    already-dead write to the SAME destination path.

    Age-gated on os.stat().st_mtime > _ATOMIC_TEMP_ORPHAN_MAX_AGE_SECONDS:
    a concurrent writer's temp file is legitimately mid-flight and must
    NEVER be swept out from under it -- age is the only signal available
    to distinguish "abandoned" from "in progress" without a lock.

    Called BEFORE this write's own mkstemp() (see __init__), so the file
    this call itself is about to create can never match its own sweep.

    Best-effort only, deliberately: any failure (permission, the file
    vanishing under us because a genuinely concurrent writer just finished
    normally, dest_dir itself being unreadable) is swallowed -- a cleanup
    sweep must never be the reason a real write fails.
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
    """Write-mode file object returned by open_no_follow_symlink(path, "w",
    atomic=True) -- the fix for the truncate-in-place bug documented in
    docs/plan/fix-atomic-claude-md-write.md (House diagnosis, T1): a plain
    open_no_follow_symlink(path, "w") truncates `path` via O_TRUNC the
    instant os.open() returns, before a single byte of new content is
    written -- a crash/kill/full-disk error anywhere between that open()
    and the write's completion leaves `path` empty or partial.

    This class never touches `path` itself until the write is fully
    complete: `.write()` calls accumulate into a `tempfile.mkstemp()` file
    created in `path`'s OWN directory (so the final os.replace() stays on
    one filesystem/device and is atomic on POSIX and Windows alike --
    os.replace() has been atomic on Windows since Python 3.3). The commit
    (flush + fsync + close + os.replace(tmp, path)) happens ONLY in
    __exit__() when the `with` block exits without an exception. Any
    exception inside the `with` block (or a bypass of __exit__ entirely,
    e.g. a real kill -9) leaves `path`'s ORIGINAL content untouched --
    __exit__()'s exception branch closes and unlinks the temp file so a
    controlled failure (disk full, a caller-raised OSError) never leaves an
    orphaned .tmp file behind; an actual kill -9 can't run any cleanup code
    regardless of implementation, same as it always could not.

    Mirrors the pattern already used by lib/boot_fetch_stamp.py's
    _write_own_stamp() (tempfile.mkstemp(dir=..., ...) + os.replace()),
    centralized here so open_no_follow_symlink(path, "w", atomic=True) is a
    drop-in replacement at any "w"-mode call site with a `with ... as f:
    f.write(...)` shape -- no caller-side restructuring needed.

    Symlink-safe by construction on the destination side even though
    os.replace() itself never follows a symlink at the destination (it
    swaps the directory entry) -- silently turning "a symlink to some
    external file" into "a real file with the new content" without ever
    raising would be the OPPOSITE of this function's existing fail-closed
    behavior for a non-atomic "w" open. To preserve that exact semantics,
    __init__() checks os.path.islink(path) BEFORE creating the temp file or
    writing anything, and raises OSError (errno.ELOOP, the same errno this
    module's symlink rejections already use) if `path` is currently a
    symlink -- the temp file is never created and `path` is never touched.
    (No TOCTOU concern between this check and the eventual os.replace()
    worth closing here: this project's threat model is the system against
    itself, not an attacker racing this check -- see CLAUDE.md.)

    reject_hardlinks is not supported here (unlike the non-atomic branch):
    a fresh tempfile.mkstemp() file always has st_nlink == 1, so checking
    it would be meaningless. This does NOT mean a hard-linked sibling is
    unaffected, though (Moriarty, corrected claim) -- it is the OPPOSITE:
    os.replace() SEVERS the hard link. `path`'s directory entry is
    repointed at the temp file's new inode, so any sibling that shared
    `path`'s old inode keeps that OLD inode (and its st_nlink drops by
    one) -- the sibling is frozen at the pre-write content and stops
    tracking `path` from that write onward. This is inherent to any
    rename-based atomic replace (the exact reason a non-atomic in-place
    O_TRUNC write is the one thing that WOULD corrupt a hard-linked
    sibling, which is what reject_hardlinks exists to prevent on that
    other path) -- not a bug here, but callers must not assume hard-link
    identity survives an atomic write.
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
            # ROB-LOW-004 (Argus): mkstemp() above already created tmp_path
            # (and its fd) before this point. If fdopen() itself raises
            # (bad encoding name, etc.), self._file is never assigned, so
            # neither __exit__() nor close() will ever run to clean up —
            # close the raw fd directly (os.fdopen() never took ownership
            # of it since it raised before returning) and remove the temp
            # file before letting the original exception propagate.
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
                    # ROB-LOW-005 (Argus): close() must run even if
                    # flush()/fsync() raises (e.g. disk full surfacing at
                    # fsync time) -- skipping it on that path would leak
                    # the fd, on top of the write itself already failing.
                    self._file.close()
                # ROB-MED-002 (Cerberus/Argus): os.replace() moves the temp
                # file's OWN inode into place, and tempfile.mkstemp() always
                # creates at 0o600 -- a pre-existing `path` at a looser mode
                # (0o644, etc.) would silently narrow to 0o600 on every
                # atomic write. Preserve the EXISTING file's mode when
                # there is one; a brand-new `path` keeps mkstemp's 0o600
                # default, consistent with every other write-mode call in
                # this module. POSIX-only (os.chmod on Windows doesn't
                # carry the same permission-bit model — best-effort, same
                # posture as this module's other os.chmod() calls, e.g.
                # boot_fetch_stamp.py's _write_own_stamp()).
                if sys.platform != "win32" and os.path.exists(self._path):
                    try:
                        existing_mode = os.stat(self._path).st_mode & 0o777
                        os.chmod(self._tmp_path, existing_mode)
                    except OSError as e:
                        # Moriarty: a silent swallow here left a caller with
                        # no signal that their file just narrowed to 0600
                        # (restrictive FAT32/NFS mount, etc.) -- best-effort
                        # still means "never block the write", but it must
                        # not also mean "never tell anyone".
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
        """Fail-loud on direct use (ROB-MED-003, Argus): calling .close()
        directly instead of exiting a `with` block is a caller bug -- it
        would otherwise abandon the buffered content with no error and no
        cleanup, letting a caller believe an unfinished write had
        succeeded. This closes the temp file, removes it (never leaves an
        orphan), and THEN raises -- unless the write was already committed
        by a normal `with`-block exit (self._committed True), in which case
        this is a harmless no-op close on an already-closed file, matching
        a plain file object's idempotent .close().

        Deliberately raises OSError, not RuntimeError: every write-mode
        open_no_follow_symlink() caller in this codebase already wraps the
        call in `except OSError` (this module's own docstring documents
        "only OSError escapes" as the contract every caller relies on) --
        raising OSError here keeps a direct-close bug inside that same,
        already-handled failure class instead of introducing a new
        exception type callers would need to special-case. The only
        supported way to COMMIT an atomic write is exiting a `with` block
        normally (or calling __exit__(None, None, None) directly).
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
    """Open `path` without following a pre-existing symlink.

    atomic (issue: docs/plan/fix-atomic-claude-md-write.md, T1): opt-in,
    default False -- every existing call site (none of which pass this
    parameter) keeps its EXACT current behavior, zero regression risk. Only
    valid combined with mode="w". When True, returns a
    _AtomicWriteNoFollowSymlink instead of a plain file object -- see that
    class's docstring for the full atomic-write contract (temp file in the
    same directory + os.replace(), never truncates `path` in place). Raises
    ValueError if combined with any mode other than "w" (atomic replace is
    only meaningful for a full-content write, not a read or an append).

    SEC-CRIT-001: several hooks write generated files at fixed, predictable
    paths (.gitignore, boot-log-latest.txt, glossary-cache.json) that fire
    automatically on session start. A malicious repo can commit one of
    those paths as a symlink (git blob mode 120000) pointing outside the
    repo (e.g. at the victim's ~/.bashrc) — blindly following it with a
    plain open(path, "w"/"a") would silently overwrite an arbitrary file
    the instant the victim opens the project.

    SEC-MED-NEW-02: the same symlink applies symmetrically to READS — a
    symlink planted at a cache path (e.g. glossary-cache.json) pointing at
    a file outside the repo would be silently followed by a plain
    open(path), and its content trusted as if it were the real cache.
    mode="r" covers this case with the read-side equivalent guard.

    POSIX: uses O_NOFOLLOW so the open() call itself atomically refuses to
    traverse a symlink at the final path component — no separate
    islink()-then-open() race. Write modes also create new files at 0o600.
    On POSIX this genuinely denies group/other access regardless of
    umask, since 0o600 has no bits for umask to clear. Read mode never
    creates a file (no O_CREAT) and has no mode bits to set.

    Windows (decision 75fdb2f, hybrid "option C"): stdlib has no
    O_NOFOLLOW equivalent, so the guard is built from two checks instead
    of one atomic flag —
      1. os.path.islink(path) BEFORE opening anything. If True, raise
         OSError without ever calling os.open() (Windows detects
         symlink/junction reparse points here since Python 3.8).
      2. A TOCTOU identity check: os.lstat(path) is captured *before* the
         open, os.fstat(fd) is captured *after* it, and their
         (st_dev, st_ino) are compared. A mismatch means the path was
         swapped for a symlink between the check and the open — the fd
         is closed and OSError is raised; it is never returned to the
         caller.
    0o600 on Windows does NOT deny group/other access the way it does on
    POSIX — a file created here inherits the ACL of its containing
    directory instead. That is a Windows filesystem semantic, not a bug
    in this function.
    Known residual (F5, accepted deliberately, not a bug): when `mode`
    creates a new file (O_CREAT semantics, i.e. the file did not exist
    before this call) there is no prior os.lstat() identity to compare
    against, so the TOCTOU race on Windows for a brand-new path is not
    closed atomically without a native API (pywin32/ctypes), which this
    project intentionally does not depend on. The islink() pre-check
    still applies in that case.

    Hard-link guard (F6, issue #53, design decision 51a3c44 — opt-in,
    closes what used to be an accepted residual): a hard link planted at
    `path`, pointing at a file outside the repo, shares device+inode with
    its target, so os.path.islink() reports False for it (it is not a
    reparse point/symlink, just another directory entry for the same
    inode) and POSIX O_NOFOLLOW does not apply either (O_NOFOLLOW only
    rejects a symlink at the final path component, not a second hard link
    to an existing inode) — by construction, a hard link is
    indistinguishable from an ordinary file to both checks above. Passing
    `reject_hardlinks=True` closes this gap: after the fd is open, this
    function checks os.fstat(fd).st_nlink (on the ALREADY-OPEN descriptor,
    never os.stat(path), to avoid a TOCTOU gap between check and open) and
    raises OSError if it is greater than 1, closing the fd first. Default
    is False — every existing call site (none of which pass this
    parameter) keeps its exact current behavior. This must stay opt-in:
    a hard link between git worktrees pointing at the same user file
    (CLAUDE.md, settings.json, package.json, .gitignore, scopes) is a
    legitimate, common setup, not an attack — only call sites that write
    toolkit-generated-only files (boot-log-latest.txt, glossary-cache.json,
    the .session-booted flag, manifest.json, and the upgrade's manifest
    backup) should pass True.

    errors (issue #54, T3): forwarded to os.fdopen()/TextIOWrapper as-is
    (default "strict", the same implicit default open()/fdopen() already
    had before this parameter existed — no behavior change for any
    existing call site, none of which pass this parameter). A write-mode
    caller whose text can legitimately contain a lone surrogate (half of
    a broken Unicode pair — this codebase's git-log record/field decoding
    can produce one via a malformed source, see run_git()'s docstring)
    must pass a non-strict value (e.g. errors="backslashreplace" for a
    clean, always-re-readable-as-strict-UTF-8 escape, or
    errors="surrogatepass" to preserve the raw bytes at the cost of the
    written file no longer round-tripping through a plain strict-UTF-8
    read) so that a bare UnicodeEncodeError — a ValueError subclass, NOT
    an OSError — never escapes this function's write path in violation of
    the "only OSError escapes" contract every existing caller already
    relies on.

    Raises OSError (errno ELOOP on POSIX; errno ELOOP is also used for
    both Windows guard rejections above, for a consistent errno across
    platforms; errno EMLINK for a reject_hardlinks=True rejection, kept
    distinct from ELOOP so the two rejection reasons aren't conflated) if
    `path` is currently a symlink, or — on Windows only — if its identity
    changed between the pre-open check and the open itself, or — when
    reject_hardlinks=True — if the opened file has st_nlink > 1. Callers
    must let that propagate to their existing "never fail the caller's
    larger operation" fallback (or "treat as absent/invalid" for reads),
    never fall back to following the link.
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
            # Defer O_TRUNC: truncating a shared inode before the
            # st_nlink check below would destroy the sibling hard link's
            # content even when the check is about to reject the open
            # outright.
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
    """Windows half of the option-C hybrid guard — see
    open_no_follow_symlink()'s docstring for the full rationale, including
    the `errors` parameter (issue #54, T3).

    Must be kept behaviorally identical to
    _symlink_safe_open._open_no_follow_symlink_windows() (same twin
    relationship as the public functions themselves).
    """
    if os.path.islink(path):
        # ELOOP is reused here (not the literal syscall errno) so that both
        # Windows rejection paths — direct symlink here, and the divergent-
        # identity race below — share one errno with each other and POSIX.
        raise OSError(errno.ELOOP, "Refusing to open a symlink", path)

    # Pre-open identity, only meaningful if the path already exists —
    # a brand-new path (O_CREAT case) has nothing to compare against
    # (see F5 residual in the caller's docstring).
    prior_identity = None
    if os.path.exists(path):
        prior_identity = os.lstat(path)

    if mode == "r":
        fd = os.open(path, os.O_RDONLY)
    else:
        # O_TRUNC is deliberately withheld here: truncating at open() time
        # would destroy the target's contents even if the identity check
        # below goes on to reject the open as a symlink race. For mode
        # "w" the truncate is deferred until after that check passes,
        # via the ftruncate() call further down.
        flags = os.O_WRONLY | os.O_CREAT
        flags |= os.O_APPEND if mode == "a" else 0
        fd = os.open(path, flags, 0o600)

    try:
        if prior_identity is not None:
            post_identity = os.fstat(fd)
            if (post_identity.st_dev, post_identity.st_ino) != (
                prior_identity.st_dev, prior_identity.st_ino,
            ):
                # ELOOP reused again here, matching the direct-symlink
                # rejection above — see the comment on that raise.
                raise OSError(
                    errno.ELOOP,
                    "Refusing to open: file identity changed between the "
                    "pre-open check and the open() call (possible symlink race)",
                    path,
                )
        if reject_hardlinks:
            # Checked on the already-open fd (never os.stat(path)) to keep
            # the same TOCTOU discipline as the identity check above.
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


# Windows-only (see file_lock()'s docstring): the errno msvcrt.locking()
# raises on its LK_LOCK mode once its own internal ~10-attempt/~10s retry
# ceiling is exhausted WHILE THE REGION IS STILL HELD BY SOMEONE ELSE --
# per Microsoft's _locking() documentation this is EDEADLOCK, distinct from
# EACCES (which _locking() uses for its non-blocking LK_NBLCK mode, not the
# LK_LOCK mode used here). This is the ONLY errno file_lock()'s own retry
# loop treats as "still contended, keep trying" -- every other errno (EIO,
# EBADF, a permanently denied EACCES, etc.) is a real failure that will
# never resolve no matter how many times it's retried, and must propagate
# instead of spinning forever (T1-3, Moriarty). getattr() with a sentinel
# default: errno.EDEADLOCK is expected to exist wherever this branch
# actually runs (real Windows), but reading it defensively here means a
# platform where the constant were ever absent degrades to "retry nothing,
# raise on the first failure" rather than crashing on AttributeError.
_MSVCRT_LOCK_CONTENDED_ERRNO = getattr(errno, "EDEADLOCK", None)


@contextlib.contextmanager
def file_lock(target_path: str, lock_path: str | None = None):
    """Cross-process EXCLUSIVE advisory lock serializing a read-modify-write
    against `target_path` -- fix for the lost-update race documented in
    docs/plan/fix-atomic-claude-md-write.md's closing note (memo eae0880):
    open_no_follow_symlink(path, "w", atomic=True) already prevents a CRASH
    mid-write from leaving `target_path` empty or partial, but it does NOT
    prevent two concurrent writers each reading the same content, each
    modifying only their own slice, and whichever os.replace() lands last
    silently discarding the other's change -- no error, no warning.

    `lock_path` (Cerberus anti-pollution finding): the lock file defaults to
    ADJACENT to `target_path` (f"{target_path}.lock") when omitted, but a
    caller may pass an explicit `lock_path` to put it somewhere else
    entirely (e.g. an already-gitignored runtime directory) -- see
    claude_md_lock_path() below for the concrete case this exists for.
    file_lock() itself stays fully generic and has NO CLAUDE.md-specific
    knowledge; `target_path` is only ever used to derive the DEFAULT
    `lock_path` when the caller doesn't supply one, and is otherwise never
    opened, read, or written by this function -- only the caller's own
    `with` body touches it. This is deliberate: two writers racing on the
    same resource must serialize through a THIRD file (created if it does
    not already exist, closed on exit, never unlinked -- meant to be reused
    by every future writer), never through locking the resource itself, so
    a reader that never calls file_lock() is completely unaffected.

    NOT REENTRANT: calling file_lock() a second time on the same
    target/lock path from within a `with file_lock(...):` block that
    already holds it -- even via a nested function call several frames
    down -- deadlocks the process against itself. fcntl.flock()/
    msvcrt.locking() have no re-entrant/RLock-style tracking, and this
    module adds none.

    Blocks until the lock is acquired -- no timeout param, no polling
    contract exposed to the caller. Always released on `with` exit, whether
    the block exits normally or via an exception propagating out of it --
    the exception itself is never swallowed here (yield sits inside
    try/finally on both platform branches, so `contextlib.contextmanager`'s
    own machinery re-raises it through this function unchanged).

    POSIX: fcntl.flock(fd, fcntl.LOCK_EX) -- a native, indefinitely-blocking
    exclusive lock; the kernel does the waiting, no retry loop needed here.

    Windows (honest semantics, NOT a drop-in equivalent of flock's single
    indefinite-blocking syscall -- an earlier version of this docstring
    overclaimed that equivalence): msvcrt.locking(fd, msvcrt.LK_LOCK, 1) has
    no indefinite-block primitive of its own -- each call blocks internally
    for only about 10 seconds, retrying roughly once a second, before
    giving up and raising OSError(errno.EDEADLOCK, ...) if the region is
    still held by someone else. The while loop below is this function's OWN
    outer retry around that -- it re-issues the call, and ONLY re-issues
    it, while the errno is EDEADLOCK (genuine, ongoing contention); any
    OTHER errno (a permanent I/O error, bad descriptor, etc.) is re-raised
    immediately instead of retried, since no amount of retrying changes a
    non-contention failure (T1-3). os.lseek() resets the file position back
    to 0 before both lock and unlock so the exact same 1-byte region is
    always the one being (un)locked, regardless of any position drift.
    UNVERIFIED on this machine (not Windows): the exact errno
    msvcrt.locking() raises for genuine lock contention is taken from
    Microsoft's own _locking() documentation, not exercised against real
    Windows locking behavior here -- CI's windows-latest run is the only
    place that distinction is exercised for real; see
    tests/test_file_lock_regressions.py's own docstring for the same caveat.

    fcntl/msvcrt are imported LAZILY inside their own sys.platform branch --
    same pattern as _open_no_follow_symlink_windows() and every other
    platform split in this module -- so importing git_helpers itself never
    raises ImportError/AttributeError on the platform the branch doesn't
    apply to, and `sys.platform` is read at CALL time (not import time), so
    a test spoofing it after import still takes the intended branch.
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
                        # Still genuinely contended -- msvcrt.locking()'s own
                        # ~10s attempt just expired, not a permanent failure.
                        # Retry (see docstring above).
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
    """Shared `file_lock()` path for every writer that read-modify-writes
    CLAUDE.md's managed blocks (hooks/session-start-crew.py,
    lib/install_apply.py::_update_claude_md())
    -- mutual exclusion between them only works if both pass the
    EXACT same `lock_path` to file_lock(), so this is the single source of
    that path (Exit Gate: one constant, one place).

    Lives under `.claude/.unmassk/` (via ensure_runtime_dir(), which
    creates the directory if missing and applies the same
    verify_path_within_project() symlink guard every other caller of it
    gets) instead of adjacent to CLAUDE.md itself, so the lock file never
    surfaces as a permanent untracked entry in `git status --porcelain` at
    the project root (Cerberus anti-pollution finding) -- `.claude/.unmassk/`
    is already in every managed project's .gitignore (ensure_gitignore()'s
    own _GENERATED_JSONS list).

    Deliberately kept separate from file_lock() itself, which stays a
    fully generic primitive with zero CLAUDE.md-specific knowledge. May
    raise OSError (propagated from ensure_runtime_dir(), e.g. a symlinked
    .claude or a directory creation failure) -- callers are expected to
    handle that exactly like any other file_lock()-adjacent failure (see
    each call site's own try/except).
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
                # 7th audit round (BUG V): never follow a symlink planted at
                # .gitignore for this existing-content read either — the
                # append below is already guarded with open_no_follow_symlink;
                # treat a symlinked path exactly like "no .gitignore present"
                # here too, and let the guarded write fail closed downstream.
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


GIT_TIMEOUT: int = 10  # seconds — single named constant for all git calls


def _win32_kill_tree(proc: subprocess.Popen) -> None:
    """Windows-only counterpart to the POSIX os.killpg() branch above
    (Argus SEC-MED-001, repair round 2): kill `proc`'s WHOLE descendant
    tree on a timeout, not just the direct child.

    Plain Popen.kill() only terminates "git" itself — a hung
    ssh.exe/askpass/credential-helper grandchild survives as an orphan,
    the exact same gap the POSIX branch closes with process groups.
    `taskkill /F /T /PID <pid>` recurses into every descendant of `pid`
    (its OS-native process tree, distinct from and unrelated to the
    CREATE_NEW_PROCESS_GROUP job used at Popen() time — no relationship
    to POSIX process groups). taskkill.exe ships in System32 on every
    supported Windows version, so this stays stdlib+OS-native, no
    pywin32/ctypes dependency.

    Fail-open, same contract as the rest of this function: taskkill being
    missing, erroring, or the process already having exited must never
    raise out of here — degrade to plain proc.kill() (direct child only)
    exactly like the pre-fix behavior, and swallow that too if the process
    is already gone.

    Boundary (Moriarty): `taskkill /F /T /PID` walks the OS-native PID
    parent tree rooted at `proc.pid` — it kills every descendant that is
    still structurally part of that tree. A descendant that has been
    RE-PARENTED away from that tree (e.g. spawned via Task Scheduler
    `schtasks`, WMI `Win32_Process.Create`, or handed off to a Windows
    service) is outside the PID tree by construction and will survive
    this kill. This is an accepted, documented limitation, not a bug:
    the defense here exists to reap a hung *legitimate* git descendant
    (ssh.exe/askpass/credential-helper) on timeout, and that threat model
    doesn't require evading a PID-tree kill. A descendant that actively
    re-parents itself to a system service implies the invoked `git`
    binary is already fully compromised — at that point the attacker has
    arbitrary code execution as this process's user, and no
    process-tree-kill mechanism (POSIX process groups included) would
    have contained it either.

    Cross-ref: reproduced live 2026-07-07 (Moriarty), see
    .claude/agent-memory/unmassk-toolkit-moriarty/attack-patterns.md
    ("Windows Task Scheduler detachment escapes taskkill /T process-tree
    kill") and tests/test_boot_freshness_regression.py::TestWin32ProcessTreeKillOnTimeout.
    """
    try:
        subprocess.run(
            ["taskkill", "/F", "/T", "/PID", str(proc.pid)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        # Expected failure modes only: taskkill.exe missing (FileNotFoundError,
        # an OSError subclass), permission denied, or the 5s guard itself
        # timing out (subprocess.TimeoutExpired, a SubprocessError subclass).
        # Degrade to killing just the direct child, same as the pre-fix
        # behavior on Windows. A real programming bug here (e.g. `proc` not
        # actually a Popen) is NOT one of these — let it propagate instead of
        # masquerading as "taskkill failed".
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
        timeout: Max seconds to wait before killing the process.
        cwd:     Working directory for the git process. None = inherit caller cwd.
        env:     Optional overrides merged over a COPY of the current
                 os.environ (additive — never mutates the real parent
                 environment). None (default) means "inherit ambient env
                 unmodified", identical to every call site that predates
                 this parameter. Used by fetch_memory_ref() (issue #49) to
                 force GIT_TERMINAL_PROMPT=0/neutralized askpass/BatchMode
                 on the boot-time background fetch without touching the
                 rest of the process's environment.
        log_stderr_on_failure: when True and the process exits non-zero,
                 print git's own stderr (truncated) to this process's
                 stderr. Default False preserves the exact pre-existing
                 behavior (stderr silently discarded) for every call site
                 that predates this parameter — a great many callers treat
                 a non-zero exit as an EXPECTED outcome (no upstream
                 configured, detached HEAD, etc.), and printing git's fatal:
                 text for every one of those would be log noise, not a
                 diagnostic. Opt in only where a failure here is a genuine
                 "something we didn't expect" case whose silence previously
                 hid the real cause (House root-cause, issue #61; the two
                 boot_git_checks.py readers involved were retired on
                 feat/memoria-v2 and no longer exist — the lesson stands,
                 don't go looking for them: a future git-level read failure
                 must leave a breadcrumb, not a silent empty result). This is the canonical
                 explanation for the pattern: every other
                 log_stderr_on_failure=True call site in the codebase (and
                 boot_memory.py's two manual-print sites, which can't take
                 this kwarg — see their own short comments) only carries a
                 one-line "breadcrumb #61" pointer back here, not a repeat
                 of this reasoning.

    Returns:
        Tuple of (exit_code, stripped_stdout). Returns (1, "") on any error.
    """
    proc = None
    try:
        merged_env = {**os.environ, **env} if env is not None else None
        # SEC-MED-001 (Argus): subprocess.run's own default TimeoutExpired
        # handling kills only the DIRECT child ("git" itself) — a hung
        # ssh/askpass/credential-helper descendant survives as an orphan and
        # can still pop an interactive credential dialog completely out of
        # context, long after this function has already returned (1, "").
        # start_new_session=True (POSIX only) makes this child the leader of
        # a brand-new process group, so the except-block below can kill the
        # whole tree with os.killpg() instead of just "git".
        #
        # Argus SEC-MED-001 (repair round 2): Windows closes the same gap
        # with a different, OS-native mechanism (no killpg/getpgid
        # equivalent exists there). CREATE_NEW_PROCESS_GROUP here is the
        # Windows counterpart of start_new_session=True — it detaches this
        # child (and whatever it spawns) into its own process group so the
        # except-block's taskkill /T below can address the whole tree by
        # its root PID instead of racing/relying on parent-child bookkeeping
        # shared with this Python process's own console group.
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
        # SEC-CRIT-16 (issue #59, Argus): the previous `text=True,
        # encoding="utf-8"` (no `newline=` kwarg) made Python's own
        # universal-newlines decoding silently translate every raw `\r`
        # (and `\r\n`) in git's stdout into `\n` BEFORE any caller ever saw
        # the string. The caller that made this concrete was a
        # boot_git_checks.py reader splitting one `%h\x1f%s\x1f%at` record
        # per commit on `\n`; it was retired on feat/memoria-v2 and no
        # longer exists, but any reader of that shape hits the same trap
        # — forging a second physical line out of what
        # git itself stored as one, reopening the
        # exact record/field-forgery class the root-fix round already
        # closed for \x1c/\x1d/\x1e. Capturing raw bytes here and decoding
        # manually with bytes.decode() performs NO newline translation at
        # all, so a `\r` git actually wrote is preserved exactly.
        # UnicodeDecodeError (invalid UTF-8) still surfaces the same way it
        # did before and is still caught by the dedicated except clause
        # below — decode failure behavior is unchanged, only the newline
        # handling is.
        stdout = stdout_bytes.decode("utf-8")
        stderr = stderr_bytes.decode("utf-8")
        if log_stderr_on_failure and proc.returncode != 0 and stderr and stderr.strip():
            # Truncated: this is a diagnostic breadcrumb, not a transcript —
            # keep it well short of anything that could carry embedded
            # commit-body content back out (git's own fatal:/error: text
            # never approaches this length in practice).
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
                    # Defensive guard, symmetric with the POSIX branch
                    # below: _win32_kill_tree() already swallows its own
                    # expected failure modes internally (OSError /
                    # SubprocessError, see its own docstring) and falls
                    # back to proc.kill() itself — but this local
                    # try/except ensures run_git()'s "never raises on
                    # timeout" contract still holds even if a future edit
                    # to _win32_kill_tree() raises a different exception
                    # type. Fall back to killing just the direct child,
                    # same as the pre-fix behavior.
                    proc.kill()
            else:
                try:
                    os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
                except (ProcessLookupError, PermissionError, OSError):
                    # Group already gone, or we lack permission to signal it
                    # (e.g. it changed session) — fall back to killing just
                    # the direct child, same as the pre-fix behavior.
                    proc.kill()
            try:
                proc.communicate(timeout=1)  # reap; discard any late output
            except (subprocess.TimeoutExpired, ValueError):
                pass
        print(f"[git_helpers] git {args[0]!r} timed out after {timeout}s", file=sys.stderr)
        return 1, ""
    except UnicodeDecodeError as e:
        # Split from the generic except below on purpose: UnicodeDecodeError
        # is a ValueError subclass, so without this dedicated branch it would
        # collapse into the same (1, "") as any other failure with zero
        # trace. The return stays (1, "") — no caller behavior changes — but
        # a decode failure (git emitted bytes that aren't valid UTF-8) now
        # leaves a diagnostic breadcrumb on stderr instead of vanishing.
        print(
            f"[git_helpers] git {args[0]!r} output was not valid UTF-8 and "
            f"could not be decoded: {e}",
            file=sys.stderr,
        )
        return 1, ""
    except (subprocess.SubprocessError, OSError, ValueError):
        # NOTE: an explicit encoding="utf-8" above means git's own UTF-8
        # output (accents, commit emojis) decodes correctly without relying
        # on PYTHONUTF8/locale defaults. UnicodeDecodeError (a ValueError
        # subclass) is handled separately above so a decode failure is
        # diagnosable instead of silent; every other ValueError still
        # collapses to (1, "") here exactly as before. Left as-is
        # deliberately: every call site already treats (1, "") as "could
        # not get git output" and reacts the same way regardless of cause.
        return 1, ""


# issue #61 (decision e9400db, Opción A): bounded retry for READ-PATH git
# calls only. A transient `git rc!=0` (observed on Ubuntu CI under runner
# load, exit 128) used to collapse straight to the caller's fail-safe empty
# result on the FIRST failure — indistinguishable from "no memory here",
# a silent-loss bug. READ_RETRY_ATTEMPTS is the total number of tries
# (1 initial + up to 2 retries); READ_RETRY_BACKOFF_SECONDS is a short,
# fixed pause between them — no exponential growth, this only needs to
# survive a brief runner hiccup, not a real outage.
READ_RETRY_ATTEMPTS: int = 3
READ_RETRY_BACKOFF_SECONDS: float = 0.1

# SEC-HIGH-001 (Argus, Verify round; broken by Moriarty, fixed here): the
# naive "retry N times" above is unbounded in WALL-CLOCK terms — if git
# HANGS (not a fast rc=128, but a stuck credential prompt/network stall),
# each attempt can burn a full GIT_TIMEOUT (10s) before
# subprocess.communicate(timeout=...) kills it, so 3 attempts could cost
# 3x GIT_TIMEOUT (30s) at one call site alone — enough to blow a 45s hook
# budget and get the whole boot killed before it ever writes its own log,
# the exact silent-loss failure class issue #61 exists to close.
#
# A FIRST fix attempt only checked the remaining budget BEFORE starting a
# new attempt, without capping the DURATION of the attempt actually
# started — Moriarty reproduced a "slow-then-hang" sequence (attempt 1
# genuinely slow at 9.3s, leaving 0.7s of budget — enough to clear the
# "don't start" gate — then attempt 2 hangs for its own full,
# uncapped GIT_TIMEOUT) totaling ~19.4s, ~2x GIT_TIMEOUT: the gate alone
# does not bound total latency, only the attempt COUNT under specific
# timing.
#
# Real fix: READ_RETRY_DEADLINE_SECONDS is a budget for the WHOLE
# sequence (all attempts + backoff combined), and EVERY attempt — not
# just the decision to start one — is capped by explicitly passing
# `timeout=min(remaining_budget, GIT_TIMEOUT)` into that attempt's own
# `run_git_fn(...)` call. An attempt can never run longer than whatever
# budget is left when it starts, so the sequence's total wall-clock time
# is mechanically bounded by READ_RETRY_DEADLINE_SECONDS (~1x
# GIT_TIMEOUT) regardless of how the failures are distributed across
# attempts (all-fast, all-hang, or any slow/hang mix) — not just the
# "first attempt hangs" case the earlier version happened to cover. A
# fast transient (the actual issue #61 CI symptom, sub-second) barely
# touches the budget, so it still gets its full READ_RETRY_ATTEMPTS
# tries with each one's timeout left effectively at GIT_TIMEOUT.
# READ_RETRY_MIN_ATTEMPT_SECONDS is the floor below which a new attempt
# is not worth starting at all (too little budget left for a meaningful
# try) — separate from the per-attempt timeout capping above, both are
# needed together.
#
# KNOWN CONSEQUENCE (accepted, not a bug): `timeout=` is now injected
# unconditionally on every call this helper makes, even for callers that
# never passed it. Several existing test doubles for `run_git` across
# this suite have a FIXED signature with neither `timeout` nor `**kwargs`
# (`def _patched_run_git(args, cwd=None): ...`) — those now raise
# TypeError when exercised through one of the 7 read-retry call sites.
# This is Dante's lane to fix (update those doubles to accept **kwargs),
# not addressed in this file — see the exact list handed off in the
# Verify-round report for issue #61.
READ_RETRY_DEADLINE_SECONDS: float = float(GIT_TIMEOUT)
READ_RETRY_MIN_ATTEMPT_SECONDS: float = 0.5


def run_git_read_retrying(run_git_fn, args: list[str], **kwargs) -> tuple[int, str]:
    """Bounded retry wrapper for a READ-PATH git call — issue #61.

    Calls `run_git_fn(args, **kwargs)` up to READ_RETRY_ATTEMPTS times,
    pausing READ_RETRY_BACKOFF_SECONDS between attempts, and returns as
    soon as one attempt succeeds (exit code 0) — including a genuine
    rc=0-with-empty-output result, which is returned immediately on the
    FIRST attempt and never retried (a real empty history must never be
    confused with a transient git failure). If every attempt fails, the
    last (code, output) pair is returned unchanged — the caller's
    existing fail-safe return value/type is never altered here.

    `run_git_fn` is taken as an explicit parameter (never resolved from
    this module's own `run_git` name) so each call site can pass
    whatever `run_git` reference is bound in ITS OWN namespace at call
    time — a module-level bound name (e.g. recall.py's
    `from git_helpers import run_git`) or a deferred, function-body
    import (e.g. boot_memory.py's/boot_git_checks.py's `from git_helpers
    import run_git` inside the function) both keep working exactly as a
    single unwrapped call would, including test monkeypatching of
    either form.

    Wall-clock deadline (SEC-HIGH-001, see the constants' comment above —
    fixed twice: a first version only gated whether a NEW attempt could
    START, which Moriarty broke with a slow-then-hang sequence). The REAL
    bound enforced here: every attempt's own `timeout` is capped to
    `min(remaining_budget, GIT_TIMEOUT)` where `remaining_budget` is
    whatever is left of READ_RETRY_DEADLINE_SECONDS when THAT attempt
    starts — so no single attempt, whenever it starts, can outlast the
    sequence's own deadline. Combined with the "don't start a new attempt
    below READ_RETRY_MIN_ATTEMPT_SECONDS" gate, total wall-clock time for
    the whole sequence is mechanically bounded to ~READ_RETRY_DEADLINE_SECONDS
    (~1x GIT_TIMEOUT), for ANY distribution of fast/slow/hanging failures
    across attempts — not just "the first one hangs".

    WARN only after giving up (Cerberus, Verify round): if the caller
    passed `log_stderr_on_failure` (either value), it is honored ONLY on
    the LAST attempt actually made — every earlier attempt is called with
    `log_stderr_on_failure=False` regardless of what the caller asked
    for, so a transient failure that RECOVERS on a later attempt never
    prints attempt 1's failure trace as a false alarm. A genuinely
    HANGING git still always leaves its own unconditional
    "timed out after Ns" trace inside run_git() on every attempt that
    hits it, independent of this flag — so a hang is never silent even
    though this suppression applies to it too.

    `timeout` (SEC-HIGH-001 fix): always injected into every attempt's
    kwargs, overriding whatever the caller passed (or the GIT_TIMEOUT
    default) with the per-attempt budget-capped value described above.
    Unlike `log_stderr_on_failure`, this is NOT conditional on the caller
    having supplied it — capping duration is the whole point of the fix,
    so it applies uniformly. KNOWN CONSEQUENCE: `run_git_fn` doubles with
    a fixed signature that doesn't accept `timeout=` (no `**kwargs`
    either) will now raise TypeError — see the constants' comment above
    for the accepted list, fixed separately by Dante.

    READ-PATH ONLY: never wrap a git WRITE (commit, config, push, etc.)
    with this — blindly retrying a write could double-apply a mutation.
    This is a deliberate scope boundary, not an oversight: `run_git()`
    itself stays retry-free for every caller that doesn't opt in here.
    """
    has_warn_kwarg = "log_stderr_on_failure" in kwargs
    want_warn = kwargs.pop("log_stderr_on_failure", False) if has_warn_kwarg else False
    base_timeout = kwargs.pop("timeout", GIT_TIMEOUT)

    deadline = time.monotonic() + READ_RETRY_DEADLINE_SECONDS
    code, output = 1, ""
    for attempt in range(1, READ_RETRY_ATTEMPTS + 1):
        remaining = deadline - time.monotonic()
        if attempt > 1 and remaining <= READ_RETRY_MIN_ATTEMPT_SECONDS:
            break  # not enough wall-clock budget left for another attempt
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
            break  # this attempt alone ate the remaining budget — stop here
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
