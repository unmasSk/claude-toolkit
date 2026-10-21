"""Build and parse the index line and the archive line; `format.py` re-exports them.
Parsers never raise: they return `None` for a line that is not theirs."""

import re
from datetime import datetime

import emojis
from model import ArchiveLine, IndexLine, Note

# Index line: "[D-030][product][auth] headline" -- no emoji, no date.

_INDEX_LINE_RE = re.compile(
    r"^\[(?P<id>[A-Z]-\d+)\]\[(?P<zone1>[^\]]+)\]\[(?P<zone2>[^\]]+)\]\s+(?P<headline>.+)$"
)


def build_index_line(note: Note) -> str:
    return f"[{note.id}][{note.zone1}][{note.zone2}] {note.headline}"


def parse_index_line(line: str) -> IndexLine | None:
    try:
        match = _INDEX_LINE_RE.match(line)
        if match is None:
            return None
        return IndexLine(
            id=match.group("id"),
            zone1=match.group("zone1"),
            zone2=match.group("zone2"),
            headline=match.group("headline"),
        )
    except Exception:
        return None


# Archive line (ARCHIVED.md): "date  [id][zone1][zone2] emoji headline  →  destination",
# destination being exactly one of "replaced by <ID>" / "closed: <reason>" / "promoted to <ID>".

_ARCHIVE_DESTINATIONS = (
    ("replaced", "replaced by "),
    ("closed", "closed: "),
    ("promoted", "promoted to "),
)

# `phrase` must start with a known destination, so a separator inside the headline
# is never taken for the real one.
_ARCHIVE_PHRASE_ALTERNATION = "|".join(re.escape(prefix) for _, prefix in _ARCHIVE_DESTINATIONS)

_ARCHIVE_LINE_RE = re.compile(
    r"^(?P<date>\d{4}-\d{2}-\d{2})  "
    r"\[(?P<id>[A-Z]-\d+)\]\[(?P<zone1>[^\]]+)\]\[(?P<zone2>[^\]]+)\]"
    r"\s+(?P<emoji>\S+)\s+(?P<headline>.+)  →  "
    rf"(?P<phrase>(?:{_ARCHIVE_PHRASE_ALTERNATION}).+)$"
)


def build_archive_line(note: Note, destination: str, detail: str) -> str:
    emoji = emojis.TYPE_EMOJI[note.type]
    date_str = note.timestamp.date().isoformat()
    # An unknown destination raises KeyError instead of building a plausible line.
    phrase_by_destination = {dest: f"{prefix}{detail}" for dest, prefix in _ARCHIVE_DESTINATIONS}
    phrase = phrase_by_destination[destination]
    return (
        f"{date_str}  [{note.id}][{note.zone1}][{note.zone2}] {emoji} "
        f"{note.headline}  →  {phrase}"
    )


def parse_archive_line(line: str) -> ArchiveLine | None:
    try:
        match = _ARCHIVE_LINE_RE.match(line)
        if match is None:
            return None

        phrase = match.group("phrase")
        destination = None
        detail = None
        for dest, prefix in _ARCHIVE_DESTINATIONS:
            if phrase.startswith(prefix):
                destination = dest
                detail = phrase[len(prefix):]
                break
        if destination is None:
            return None

        note_id = match.group("id")
        date_value = datetime.strptime(match.group("date"), "%Y-%m-%d").date()

        return ArchiveLine(
            date=date_value,
            type=note_id.split("-", 1)[0],
            id=note_id,
            zone1=match.group("zone1"),
            zone2=match.group("zone2"),
            headline=match.group("headline"),
            destination=destination,
            destination_detail=detail,
        )
    except Exception:
        return None
