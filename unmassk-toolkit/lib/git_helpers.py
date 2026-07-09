"""
Git command helpers for unmassk-toolkit.

Thin wrappers around subprocess calls to git. Used by hooks,
CLI scripts to run git commands safely.
"""

import errno
import os
import signal
import subprocess
import sys


# Runtime directory for all generated files — single gitignore entry.
# git-memory-scopes.json is NOT here — it lives in agent-memory (per-project, tracked).
UNMASSK_RUNTIME_DIR = ".claude/.unmassk"

_GENERATED_JSONS = [
    ".claude/.unmassk/",
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


def open_no_follow_symlink(
    path: str,
    mode: str = "w",
    encoding: str = "utf-8",
    reject_hardlinks: bool = False,
):
    """Open `path` without following a pre-existing symlink.

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
    if sys.platform == "win32":
        return _open_no_follow_symlink_windows(path, mode, encoding, reject_hardlinks)

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

    return os.fdopen(fd, mode, encoding=encoding)


def _open_no_follow_symlink_windows(
    path: str, mode: str, encoding: str, reject_hardlinks: bool = False
):
    """Windows half of the option-C hybrid guard — see
    open_no_follow_symlink()'s docstring for the full rationale.

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

    return os.fdopen(fd, mode, encoding=encoding)


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
                 hid the real cause (House root-cause, boot_git_checks.py's
                 get_timeline()/get_last_context_time() — a future git-level
                 read failure must leave a breadcrumb, not a silent empty
                 result).

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
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            cwd=cwd, encoding="utf-8", env=merged_env,
            **popen_kwargs,
        )
        stdout, stderr = proc.communicate(timeout=timeout)
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


_CONSOLIDATION_SENTINEL = 9999  # returned when no context(consolidation) exists


def commits_since_last_consolidation(cwd: str | None = None) -> int:
    """Return the number of commits since the last context(consolidation) commit.

    Scans the full git history (no window limit) for the most recent commit
    whose subject matches context(consolidation) — ONLY that scope. Any other
    context(X) scope is ignored.

    Returns:
        - Number of commits since that SHA (exclusive) up to HEAD.
        - _CONSOLIDATION_SENTINEL (9999) if no context(consolidation) exists
          in history — forces a first-time warning.
        - 0 on any git error (fail-safe: do not alert on broken git).
    """
    try:
        # Find the most recent commit with subject containing "context(consolidation)"
        # Using --grep with --fixed-strings, no -n limit → full history scan.
        # The pattern matches "context(consolidation)" anywhere in the subject line.
        rc, output = run_git(
            ["log", "--all", "--format=%H %s", "--grep=context(consolidation)", "--fixed-strings"],
            cwd=cwd,
        )
        if rc != 0:
            return 0

        # Walk through matches top-to-bottom (most recent first) and pick the
        # first one whose subject actually contains ONLY the consolidation scope.
        consolidation_sha: str | None = None
        if output:
            import re as _re
            _pat = _re.compile(r"context\(consolidation\)", _re.IGNORECASE)
            # issue #57 round 2d (Argus LOW, bullet F): .splitlines() treats
            # \x1c-\x1e (and other Unicode line-boundary bytes) as line
            # boundaries, not just real "\n". A commit whose subject embeds
            # a raw \x1e BEFORE the "context(consolidation)" keyword split
            # this function's own %H %s output line into two fragments,
            # neither of which matched "<sha> <subject with keyword>" --
            # making the real checkpoint invisible and inflating the result
            # to _CONSOLIDATION_SENTINEL. `git log --format=%H %s` output is
            # newline (\n)-delimited only; split on the real character.
            for line in output.split("\n"):
                line = line.strip()
                if not line:
                    continue
                parts = line.split(" ", 1)
                if len(parts) < 2:
                    continue
                sha, subject = parts[0], parts[1]
                if _pat.search(subject):
                    consolidation_sha = sha
                    break  # most recent match

        if not consolidation_sha:
            return _CONSOLIDATION_SENTINEL

        # Count commits from consolidation_sha (exclusive) to HEAD.
        rc2, count_str = run_git(
            ["rev-list", "--count", f"{consolidation_sha}..HEAD"],
            cwd=cwd,
        )
        if rc2 != 0 or not count_str:
            return 0
        return int(count_str)
    except (ValueError, TypeError):
        # Expected failure mode only: `count_str` came back non-numeric
        # (unexpected git output). run_git() itself never raises — it
        # already collapses subprocess/OSError to (1, ""), handled by the
        # rc2 check above. A different exception here would be a real bug
        # in this function's own logic and should surface, not be masked as
        # "0 commits since consolidation".
        return 0  # fail-safe: never crash the boot


def is_git_repo() -> bool:
    """Check if we're in a git repository."""
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def is_shallow_clone() -> bool:
    """Check if the repository is a shallow clone."""
    code, output = run_git(["rev-parse", "--is-shallow-repository"])
    return code == 0 and output == "true"
