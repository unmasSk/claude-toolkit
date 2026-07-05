"""
Glossary cache I/O for session-start-boot.py (further split of boot_memory.py).

Owns the on-disk glossary cache (.claude/.unmassk/glossary-cache.json) that
lets extract_glossary()'s full-history scan be skipped on most boots: project
root resolution, cache path, cache read (with staleness/schema/HEAD checks),
cache write, and the cached-or-fresh entry point extract_glossary_cached().

Split out of lib/boot_memory.py (which had grown to 524 lines, over the
project's 500-line limit): this module is "glossary CACHE I/O", a distinct
theme from boot_memory.py's own remaining "commit-history parsing" theme
(extract_memory, extract_glossary, _crown_replace, _sanitize_trailer_value).
One-way logic dependency: extract_glossary_cached() calls extract_glossary()
from boot_memory on a cache miss (deferred, function-body import — see the
NOTE below on why). boot_memory.py additionally re-exports this module's 5
names at its own bottom, for backward compatibility with a test that loads
lib/boot_memory.py directly (see that file's tail for the full rationale) —
that re-export is a test-compatibility shim, not a real logic dependency.
"""

import json
import os
from datetime import datetime, timezone

try:
    # SEC-CRIT-001 / SEC-MED-NEW-02: symlink-safe reader/writer for
    # glossary-cache.json. Imported defensively: tests/test_migrate_statusline.py
    # stubs out git_helpers with a minimal fake module that predates this
    # helper, and this module must still import cleanly against that stub
    # (it is imported transitively by session-start-boot.py even when only
    # _migrate_stale_context_writer_statusline() is under test).
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink
try:
    # SEC-HIGH-003: reuse the canonical .claude/.unmassk/ creation helper
    # (verify_path_within_project() chokepoint) instead of a bare
    # os.makedirs() that silently follows a symlinked .claude parent.
    # Imported defensively for the same reason as open_no_follow_symlink
    # above — tests/test_migrate_statusline.py stubs git_helpers with a
    # minimal fake module that predates this helper.
    from git_helpers import ensure_runtime_dir
except ImportError:
    ensure_runtime_dir = None

# NOTE: `extract_glossary` is imported from boot_memory INSIDE
# extract_glossary_cached()'s function body (below), not here at module
# level. tests/test_security_regression.py's BUG AO probe loads
# lib/boot_memory.py directly via spec_from_file_location under a throwaway
# module name (not the real "boot_memory"), then relies on boot_memory.py's
# own backward-compat re-export of this module's 5 glossary-cache names (see
# the bottom of boot_memory.py) for `mod._write_glossary_cache` to resolve.
# If this module imported `boot_memory` at its own top level, that re-export
# would force a second, fresh execution of boot_memory.py under the real
# module name while THIS module is still mid-import — a genuine circular
# import (ImportError: cannot import name ... from partially initialized
# module). Deferring the import into the one function that actually calls
# extract_glossary() avoids that: this module's top-level code never touches
# boot_memory, so no cycle is ever entered during a plain module-level load.
GLOSSARY_CACHE_TTL = 86400  # 24 hours


_project_root_cache: str | None = None


def _get_project_root() -> str | None:
    """Get project root, cached for the process."""
    from git_helpers import run_git

    global _project_root_cache
    if _project_root_cache is None:
        code, root = run_git(["rev-parse", "--show-toplevel"])
        _project_root_cache = root if code == 0 and root else ""
    return _project_root_cache or None


def _glossary_cache_path() -> str | None:
    """Return path to .claude/.unmassk/glossary-cache.json, or None if no project root."""
    root = _get_project_root()
    if not root:
        return None
    return os.path.join(root, ".claude", ".unmassk", "glossary-cache.json")


def _read_glossary_cache() -> dict | None:
    """Read glossary cache if fresh. Returns None if stale or missing."""
    from git_helpers import run_git

    path = _glossary_cache_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        # SEC-MED-NEW-02: symlink-safe read, symmetric with
        # _write_glossary_cache()'s existing open_no_follow_symlink() guard —
        # a symlink planted at this path (pointing outside the repo) must be
        # rejected exactly like "no valid cache", not silently followed.
        with open_no_follow_symlink(path, "r") as f:
            cache = json.load(f)
        # Check staleness
        generated = cache.get("generated_at", "")
        if generated:
            gen_dt = datetime.fromisoformat(generated)
            if gen_dt.tzinfo is None:
                gen_dt = gen_dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - gen_dt).total_seconds()
            if age > GLOSSARY_CACHE_TTL:
                return None
        # Check schema_version
        if cache.get("schema_version") != 1:
            return None
        # Check that decisions are 3-element lists
        decisions = cache.get("decisions", [])
        if decisions and len(decisions[0]) != 3:
            return None
        # Check HEAD match
        code, head_sha = run_git(["rev-parse", "HEAD"])
        if code != 0:
            return None
        if cache.get("head_sha") != head_sha:
            return None
        return cache
    except (json.JSONDecodeError, OSError, ValueError, KeyError):
        return None


def _write_glossary_cache(glossary: dict) -> None:
    """Write glossary cache to .claude/.unmassk/glossary-cache.json."""
    from git_helpers import ensure_gitignore, run_git

    root = _get_project_root()
    path = _glossary_cache_path()
    if not path:
        return
    code, head_sha = run_git(["rev-parse", "HEAD"])
    if code != 0:
        return
    # tombstones is a set — serialize as sorted list for JSON stability
    raw_tombstones = glossary.get("tombstones", set())
    cache = {
        "schema_version": 1,
        "head_sha": head_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decisions": glossary.get("decisions", []),
        "memos": glossary.get("memos", []),
        "remembers": glossary.get("remembers", []),
        "tombstones": sorted(raw_tombstones),
    }
    try:
        # SEC-HIGH-003: .claude may be a symlink to an external directory —
        # ensure_runtime_dir() verifies the resolved path stays inside root
        # before creating anything. Fall back to the old bare os.makedirs()
        # only when the import itself failed (test-stub window).
        if ensure_runtime_dir is not None and root:
            ensure_runtime_dir(root)
        else:
            # Fallback when ensure_runtime_dir couldn't be imported (stub or
            # stale git_helpers.py without it) -- ensure_runtime_dir's own
            # verify_path_within_project() protection must be replicated
            # here explicitly, or this branch silently loses the
            # parent-directory-symlink guard. Deferred import, same reason
            # as ensure_runtime_dir's own defensive import above.
            from git_helpers import verify_path_within_project
            cache_dir = os.path.dirname(path)
            if root:
                verify_path_within_project(cache_dir, root)
            os.makedirs(cache_dir, exist_ok=True)
        with open_no_follow_symlink(path, "w") as f:
            json.dump(cache, f, indent=2)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        if root:
            ensure_gitignore(root)
    except OSError:
        pass


def extract_glossary_cached() -> dict:
    """Extract glossary, using cache if available."""
    from boot_memory import extract_glossary

    cached = _read_glossary_cache()
    if cached:
        return {
            "decisions": cached.get("decisions", []),
            "memos": cached.get("memos", []),
            "remembers": cached.get("remembers", []),
            "tombstones": set(cached.get("tombstones", [])),
        }
    glossary = extract_glossary()
    _write_glossary_cache(glossary)
    return glossary
