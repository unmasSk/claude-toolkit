"""
Shared git-log date parsing.

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
    time_ago(): both used to silently degrade to None whenever an older
    git's %aI + fromisoformat() combination failed to parse.

    Returns:
        Parsed datetime (UTC-aware), or None if parsing fails -- including
        non-str input, digit strings absurdly long to be a real epoch, and
        non-ASCII digit strings (str.isdigit() accepts Unicode digits that
        int() would happily parse, but no real `git log %at` call ever
        emits them).
    """
    # date_str.isdigit() below has no .isdigit attribute on non-str input
    # (None, int, list, ...) -- AttributeError is not in the except tuple,
    # so it would crash instead of degrading to None per this function's
    # own docstring contract. Explicit type guard up front is more readable
    # than adding AttributeError to the except clause, and matches the
    # "Returns ... or None if parsing fails" promise for ANY input, not
    # just malformed strings.
    if not isinstance(date_str, str):
        return None
    try:
        # isascii() gate: str.isdigit() also accepts non-ASCII Unicode
        # digits (fullwidth, arabic-indic, devanagari, ...) that int() would
        # happily convert -- but no real `git log %at` call ever emits
        # those, so a non-ASCII digit string here is malformed input, not a
        # valid epoch, and must fall through to the ISO-8601 branch (which
        # will also fail to parse it) rather than be silently accepted.
        if date_str.isascii() and date_str.isdigit():
            # Explicit length guard, defense-in-depth ahead of
            # int(date_str) -- not dependent on the interpreter's own
            # int-from-string digit limit (sys.get_int_max_str_digits()).
            # A real unix epoch never needs more than ~12-19 digits (year
            # 9999 is epoch 253402300799, 12 digits; a 64-bit signed epoch
            # tops out at 19 digits). 20 gives headroom while still
            # rejecting anything that could never be a real epoch.
            if len(date_str) > 20:
                return None
            return datetime.fromtimestamp(int(date_str), tz=timezone.utc)
        dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, OSError, OverflowError):
        return None
