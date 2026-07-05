"""
Git command helpers for unmassk-toolkit.

Thin wrappers around subprocess calls to git. Used by hooks,
CLI scripts to run git commands safely.
"""

import os
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


def open_no_follow_symlink(path: str, mode: str = "w", encoding: str = "utf-8"):
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

    Uses O_NOFOLLOW so the open() call itself atomically refuses to
    traverse a symlink at the final path component — no separate
    islink()-then-open() race. Write modes also create new files at 0o600
    (no group/other access) regardless of umask, since 0o600 has no bits
    for umask to clear. Read mode never creates a file (no O_CREAT) and
    has no mode bits to set.

    Raises OSError (errno ELOOP on POSIX) if `path` is currently a
    symlink — callers must let that propagate to their existing
    "never fail the caller's larger operation" fallback (or "treat as
    absent/invalid" for reads), never fall back to following the link.
    """
    if mode == "r":
        flags = os.O_RDONLY | os.O_NOFOLLOW
        fd = os.open(path, flags)
        return os.fdopen(fd, mode, encoding=encoding)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_APPEND if mode == "a" else os.O_TRUNC
    fd = os.open(path, flags, 0o600)
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


def run_git(
    args: list[str],
    timeout: int = GIT_TIMEOUT,
    cwd: str | None = None,
) -> tuple[int, str]:
    """Run a git command and return (exit_code, stdout).

    Args:
        args:    Git subcommand and arguments (e.g. ["log", "--oneline"]).
        timeout: Max seconds to wait before killing the process.
        cwd:     Working directory for the git process. None = inherit caller cwd.

    Returns:
        Tuple of (exit_code, stripped_stdout). Returns (1, "") on any error.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True, text=True, timeout=timeout,
            cwd=cwd,
        )
        return result.returncode, result.stdout.strip()
    except subprocess.TimeoutExpired:
        print(f"[git_helpers] git {args[0]!r} timed out after {timeout}s", file=sys.stderr)
        return 1, ""
    except (subprocess.SubprocessError, OSError, ValueError):
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
            for line in output.splitlines():
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
    except Exception:
        return 0  # fail-safe: never crash the boot


def is_git_repo() -> bool:
    """Check if we're in a git repository."""
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def is_shallow_clone() -> bool:
    """Check if the repository is a shallow clone."""
    code, output = run_git(["rev-parse", "--is-shallow-repository"])
    return code == 0 and output == "true"
