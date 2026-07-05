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


def ensure_runtime_dir(project_root: str) -> str:
    """Ensure .claude/.unmassk/ directory exists and return its path."""
    runtime_dir = os.path.join(project_root, UNMASSK_RUNTIME_DIR)
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
            with open(gitignore_path) as f:
                existing = f.read()
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
