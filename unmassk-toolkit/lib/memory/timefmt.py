"""Format dates: `utc_label` for the exact UTC moment, `ago` for a relative label.

`from_git_seconds` is the single reader of git epoch-second dates."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

_UNKNOWN = "unknown"


def _as_utc(moment: datetime) -> datetime | None:
    if not isinstance(moment, datetime):
        return None
    if moment.tzinfo is None:
        # A naive datetime is taken as UTC.
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def utc_label(moment: datetime) -> str:
    """Return `moment` as "YYYY-MM-DD HH:MM UTC", or "unknown"."""
    utc = _as_utc(moment)
    if utc is None:
        return _UNKNOWN
    return f"{utc:%Y-%m-%d %H:%M} UTC"


def from_git_seconds(raw: str) -> datetime:
    """Return the UTC datetime of a git epoch-seconds value (`%at`, `%(committerdate:unix)`); raises ValueError on bad input."""
    return datetime.fromtimestamp(int(raw), tz=timezone.utc)


def ago(moment: datetime, now: datetime | None = None) -> str:
    """Return a relative English label such as "2 h ago" or "3 days ago", or "unknown"."""
    utc = _as_utc(moment)
    if utc is None:
        return _UNKNOWN
    reference = _as_utc(now) if now is not None else datetime.now(timezone.utc)
    if reference is None:
        return _UNKNOWN

    delta = reference - utc
    if delta < timedelta(0):
        return "in the future"

    seconds = int(delta.total_seconds())
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        return f"{seconds // 60} min ago"
    if seconds < 86400:
        return f"{seconds // 3600} h ago"
    if seconds < 604800:
        days = seconds // 86400
        return "1 day ago" if days == 1 else f"{days} days ago"
    weeks = seconds // 604800
    return "1 week ago" if weeks == 1 else f"{weeks} weeks ago"
