"""
Shared git-log date parsing (issue #55 canonicalization).

parse_date() was duplicated byte-for-byte in bin/git-memory-gc.py and
bin/git-memory-doctor.py. Centralized here, following the same
extraction precedent as lib/_symlink_safe_open.py (see
.claude/agent-memory/unmassk-toolkit-ultron/lessons.md's "Shared
fallback for a defensively-imported git_helpers function" entry).
"""

from datetime import datetime, timezone


def parse_date(date_str: str) -> datetime | None:
    """Parse a git log date string.

    Accepts %at (unix epoch, e.g. from `git log --pretty=format:%at`) --
    robust across git versions/locales -- or ISO-8601 (%aI) as a fallback
    for any external/legacy caller. Mirrors lib/boot_git_checks.py's
    time_ago() (issue #55: %aI + fromisoformat() silently degraded to None
    on some git versions).

    Returns:
        Parsed datetime (UTC-aware), or None if parsing fails.
    """
    try:
        if date_str.isdigit():
            return datetime.fromtimestamp(int(date_str), tz=timezone.utc)
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, OSError, OverflowError):
        return None
