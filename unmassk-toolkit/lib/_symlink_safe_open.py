"""
Shared fallback for open_no_follow_symlink() (Cerberus T3-1).

lib/boot_memory.py and hooks/session-start-boot.py each need
git_helpers.open_no_follow_symlink() but must still import cleanly when
git_helpers is replaced by a minimal test stub that predates this helper
(tests/test_migrate_statusline.py does exactly this). Before this module
existed, both call sites carried a byte-identical local reimplementation
of the same O_NOFOLLOW logic as a fallback — two copies that could drift
apart silently. This module is the single shared implementation; both
call sites import defensively:

    try:
        from git_helpers import open_no_follow_symlink
    except ImportError:
        from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink

This module is never itself stubbed by any test (only "git_helpers",
"parsing", and "version" are), so the fallback import above always
resolves to this real implementation even during a stub window.

Must be kept behaviorally identical to git_helpers.open_no_follow_symlink().
"""

import os


def open_no_follow_symlink_fallback(path: str, mode: str = "w", encoding: str = "utf-8"):
    """Fallback reimplementation — see git_helpers.open_no_follow_symlink() for the
    full rationale (SEC-CRIT-001 write guard, SEC-MED-NEW-02 read guard)."""
    if mode == "r":
        flags = os.O_RDONLY | os.O_NOFOLLOW
        fd = os.open(path, flags)
        return os.fdopen(fd, mode, encoding=encoding)
    flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
    flags |= os.O_APPEND if mode == "a" else os.O_TRUNC
    fd = os.open(path, flags, 0o600)
    return os.fdopen(fd, mode, encoding=encoding)
