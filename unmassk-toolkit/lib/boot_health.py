"""
Boot health checks for session-start-boot.py (split out of lib/boot_checks.py,
Cerberus round-6 LOC audit).

Owns the "is the plugin/repo installed correctly?" checks: skill-drift +
installed-version comparison, and doctor/repair runners. lib/boot_checks.py
re-imports these functions by name so lib/boot_render.py and any direct
`boot_checks.<name>()` caller keep resolving unchanged.

Memory v2 cleanup: the GitHub issue-status lookups (check_issue_status(),
_issue_matches_next()) were removed with the rest of the v1 memory system —
they only ever fed the RESUME section's Next: filtering in the now-deleted
lib/boot_memory.py/lib/boot_render.py (see
docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3).

2026-08-05: the v1 boot chain that owned this module (hooks/session-start-boot.py
and its lib/boot_checks.py / lib/boot_git_checks.py / lib/boot_render.py /
lib/boot_migrations.py siblings) was deleted — v2's boot_launcher.py replaced
it and none of those files had a live caller left. This module was NOT
deleted with the rest because lib/cache_sync_check.py:40 still imports
CACHE_BASE_DIR, _latest_version_dir, and _md5_file from it (production path:
bin/git-memory-doctor.py -> cache_sync_check -> here). Everything else that
used to live here (REPO_BASE_DIR, _is_real_repo_source(),
_build_repo_skill_index(), check_skill_drift(), check_version_mismatch(),
run_doctor(), run_repair()) had zero remaining callers once the v1 chain
was gone, so it was removed along with it rather than kept as dead code.

Pure refactor otherwise: the surviving functions are byte-for-byte identical
to before the split.
"""

import hashlib
import os


CACHE_BASE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache", "unmassk-claude-toolkit")


def _md5_file(path: str) -> str:
    """Return MD5 hex digest of a file's content."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _latest_version_dir(plugin_cache_dir: str) -> str | None:
    """Return the path to the latest semver version directory under plugin_cache_dir."""
    try:
        versions = [
            d for d in os.listdir(plugin_cache_dir)
            if os.path.isdir(os.path.join(plugin_cache_dir, d))
        ]
    except OSError:
        return None
    if not versions:
        return None
    # Sort by semver (tuple of ints), fall back to string sort
    def _semver_key(v: str):
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0, 0, 0)
    latest = max(versions, key=_semver_key)
    return os.path.join(plugin_cache_dir, latest)
