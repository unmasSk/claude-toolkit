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
    # FIX-1 (Argus SEC-LOW-001): date_str.isdigit() below has no .isdigit
    # attribute on non-str input (None, int, list, ...) -- AttributeError is
    # not in the except tuple, so it would crash instead of degrading to
    # None per this function's own docstring contract. Explicit type guard
    # up front is more readable than adding AttributeError to the except
    # clause, and matches the "Returns ... or None if parsing fails" promise
    # for ANY input, not just malformed strings.
    if not isinstance(date_str, str):
        return None
    try:
        if date_str.isdigit():
            # FIX-2 (Argus SEC-LOW-002): explicit length guard, defense-in-
            # depth ahead of int(date_str) -- not dependent on the
            # interpreter's own int-from-string digit limit
            # (sys.get_int_max_str_digits()). A real unix epoch never needs
            # more than ~12-19 digits (year 9999 is epoch 253402300799, 12
            # digits; a 64-bit signed epoch tops out at 19 digits). 20 gives
            # headroom while still rejecting anything that could never be a
            # real epoch.
            if len(date_str) > 20:
                return None
            return datetime.fromtimestamp(int(date_str), tz=timezone.utc)
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, OSError, OverflowError):
        return None
