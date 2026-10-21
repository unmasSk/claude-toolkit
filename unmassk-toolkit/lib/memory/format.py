"""Build and parse memory commit messages: every build_* has its parse_*, and parsers never raise (None on a foreign line).

Index and archive lines live in format_lines.py and are re-exported here."""

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import emojis
from format_lines import build_archive_line, build_index_line, parse_archive_line, parse_index_line
from model import ContextNote, Note

# ---------------------------------------------------------------------------
# Line folding and escaped lists, shared by subject, body and closing context.
# ---------------------------------------------------------------------------


def _fold_raw(prefix: str, value: str) -> str:
    """Prefix the first line of `value`; each further line gets exactly one leading space (lossless)."""
    parts = value.split("\n")
    out = [f"{prefix}{parts[0]}"]
    out.extend(f" {cont}" for cont in parts[1:])
    return "\n".join(out)


def _fold(label: str, value: str) -> str:
    """Fold `value` as a `Label: ` field."""
    return _fold_raw(f"{label}: ", value)


def _escape_list_item(item: str) -> str:
    """Escape `\\` and `,` so `item` survives the list join/split."""
    return item.replace("\\", "\\\\").replace(",", "\\,")


def _encode_list(items: tuple[str, ...]) -> str:
    return ", ".join(_escape_list_item(item) for item in items)


def _decode_list(text: str) -> tuple[str, ...]:
    """Exact inverse of `_encode_list`, scanning char by char so an escaped `,` is never a separator."""
    items: list[str] = []
    current: list[str] = []
    escaped = False
    i = 0
    while i < len(text):
        ch = text[i]
        if escaped:
            current.append(ch)
            escaped = False
            i += 1
            continue
        if ch == "\\":
            escaped = True
            i += 1
            continue
        if text[i:i + 2] == ", ":
            items.append("".join(current))
            current = []
            i += 2
            continue
        current.append(ch)
        i += 1
    items.append("".join(current))
    return tuple(items)


# ---------------------------------------------------------------------------
# _SubjectParts
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _SubjectParts:
    """The parts of a note commit's subject line."""

    type: str
    id: str
    zone1: str
    zone2: str
    headline: str


# ---------------------------------------------------------------------------
# Subject: "[D-030][product][auth] (emoji) headline", possibly folded.
# ---------------------------------------------------------------------------

_SUBJECT_RE = re.compile(
    r"^\[(?P<id>[A-Z]-\d+)\]\[(?P<zone1>[^\]]+)\]\[(?P<zone2>[^\]]+)\]"
    r"\s+(?P<emoji>\S+)\s+(?P<headline>.+)$",
    re.DOTALL,
)


def build_subject(note: Note) -> str:
    emoji = emojis.TYPE_EMOJI[note.type]
    prefix = f"[{note.id}][{note.zone1}][{note.zone2}] {emoji} "
    return _fold_raw(prefix, note.headline)


def parse_subject(text: str) -> _SubjectParts | None:
    try:
        lines = text.split("\n")
        unfolded_parts = [lines[0]]
        for line in lines[1:]:
            if not line.startswith(" "):
                return None
            unfolded_parts.append(line[1:])
        unfolded = "\n".join(unfolded_parts)

        match = _SUBJECT_RE.match(unfolded)
        if match is None:
            return None
        note_id = match.group("id")
        return _SubjectParts(
            type=note_id.split("-", 1)[0],
            id=note_id,
            zone1=match.group("zone1"),
            zone2=match.group("zone2"),
            headline=match.group("headline"),
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Message: subject + blank line + body fields
# ---------------------------------------------------------------------------

_BODY_FIELD_ORDER = ("Why", "Awaits", "Keys", "Description", "Replaces", "Origin", "Issue", "Quote")
_BODY_FIELD_RE = re.compile(
    r"^(" + "|".join(_BODY_FIELD_ORDER) + r"):[ ]?(.*)$"
)
# Any `Label: ...` at column 0: an unknown field is skipped with its continuations, not the whole note.
_ANY_FIELD_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]*:(?: |$)")

# `Searched` travels as a first `Description:` starting with this mark, so older readers keep the real one.
_SEARCHED_MARK = "Searched: "
_DESCRIPTION_HEAD = "Description: "


def _body_field_line(label: str, note: Note) -> str | None:
    """Return the body line for `label`, or None when the field is absent in `note`."""
    if label == "Why":
        return _fold("Why", note.why) if note.why is not None else None
    if label == "Awaits":
        return _fold("Awaits", note.awaits) if note.awaits is not None else None
    if label == "Keys":
        return _fold("Keys", _encode_list(note.keys)) if note.keys else None
    if label == "Description":
        line = _fold("Description", note.description)
        if note.searched is None:
            return line
        return _fold("Description", _SEARCHED_MARK + note.searched) + "\n" + line
    if label == "Replaces":
        return _fold("Replaces", note.replaces) if note.replaces is not None else None
    if label == "Origin":
        return _fold("Origin", _encode_list(note.origin)) if note.origin else None
    if label == "Issue":
        return f"Issue: #{note.issue}" if note.issue is not None else None
    if label == "Quote":
        return _fold("Quote", note.quote) if note.quote is not None else None
    raise ValueError(f"format.py: campo de cuerpo desconocido {label!r}")  # pragma: no cover


def _parse_fields(body_lines: list[str], field_re: re.Pattern) -> dict[str, str] | None:
    """Group body lines into `{Label: value}`, skipping unknown fields; None on a stray line."""
    fields: dict[str, str] = {}
    current_label: str | None = None
    current_parts: list[str] = []
    skipping = False

    for line in body_lines:
        match = field_re.match(line)
        if match is not None or _ANY_FIELD_RE.match(line):
            if current_label is not None:
                fields[current_label] = "\n".join(current_parts)
            current_label = match.group(1) if match is not None else None
            current_parts = [match.group(2)] if match is not None else []
            skipping = match is None
        elif line.startswith(" ") and (current_label is not None or skipping):
            current_parts.append(line[1:])
        else:
            return None

    if current_label is not None:
        fields[current_label] = "\n".join(current_parts)

    if not fields:
        return None
    return fields


def _parse_body_fields(body_lines: list[str]) -> dict[str, str] | None:
    return _parse_fields(body_lines, _BODY_FIELD_RE)


def _take_searched(body_lines: list[str]) -> tuple[str | None, list[str]]:
    """Split off the marked `Description:` as `(searched, rest)`, only when another `Description:` follows."""
    starts = [i for i, line in enumerate(body_lines) if line.startswith(_DESCRIPTION_HEAD)]
    head = _DESCRIPTION_HEAD + _SEARCHED_MARK
    if len(starts) < 2 or not body_lines[starts[0]].startswith(head):
        return None, body_lines
    first = starts[0]
    end = first + 1
    while end < len(body_lines) and body_lines[end].startswith(" "):
        end += 1
    parts = [body_lines[first][len(head):]] + [line[1:] for line in body_lines[first + 1:end]]
    return "\n".join(parts), body_lines[:first] + body_lines[end:]


def build_message(note: Note) -> str:
    subject = build_subject(note)
    body_lines: list[str] = []
    for label in _BODY_FIELD_ORDER:
        line = _body_field_line(label, note)
        if line is not None:
            body_lines.append(line)

    return subject + "\n\n" + "\n".join(body_lines)


def parse_message(text: str) -> Note | None:
    try:
        lines = text.split("\n")

        # The subject runs to the blank line, folded continuations included.
        idx = 1
        while idx < len(lines) and lines[idx].startswith(" "):
            idx += 1
        if idx >= len(lines) or lines[idx] != "":
            return None

        subject = parse_subject("\n".join(lines[:idx]))
        if subject is None:
            return None

        searched, body_lines = _take_searched(lines[idx + 1:])
        fields = _parse_body_fields(body_lines)
        if fields is None or "Description" not in fields:
            return None

        keys = _decode_list(fields["Keys"]) if "Keys" in fields else ()
        origin = _decode_list(fields["Origin"]) if "Origin" in fields else ()
        issue = int(fields["Issue"].strip().lstrip("#")) if "Issue" in fields else None

        return Note(
            type=subject.type,
            id=subject.id,
            zone1=subject.zone1,
            zone2=subject.zone2,
            headline=subject.headline,
            description=fields["Description"],
            timestamp=datetime.now(timezone.utc),
            why=fields.get("Why"),
            keys=keys,
            origin=origin,
            replaces=fields.get("Replaces"),
            awaits=fields.get("Awaits"),
            issue=issue,
            quote=fields.get("Quote"),
            searched=searched,
        )
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Index and archive lines: re-exported above from `format_lines.py`.
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Closing context: "[NEXT] (emoji) headline", optional Keys, one prose Context field.
# ---------------------------------------------------------------------------

_CONTEXT_MARKER = emojis.CHANNEL_EMOJI["next"]
_NEXT_PREFIX = f"[NEXT] {_CONTEXT_MARKER} "

_CONTEXT_BODY_FIELD_ORDER = ("Keys", "Context")
_CONTEXT_BODY_FIELD_RE = re.compile(
    r"^(" + "|".join(_CONTEXT_BODY_FIELD_ORDER) + r"):[ ]?(.*)$"
)


def build_context_message(ctx: ContextNote) -> str:
    lines = [_fold_raw(_NEXT_PREFIX, ctx.headline), ""]
    if ctx.keys:
        lines.append(_fold("Keys", _encode_list(ctx.keys)))
    lines.append(_fold("Context", ctx.context))
    return "\n".join(lines)


def parse_context_message(text: str) -> ContextNote | None:
    """Parse a session-closing context; None when `text` is not one (Context is required)."""
    try:
        lines = text.split("\n")
        if not lines or not lines[0].startswith(_NEXT_PREFIX):
            return None

        idx = 1
        while idx < len(lines) and lines[idx].startswith(" "):
            idx += 1
        if idx >= len(lines) or lines[idx] != "":
            return None

        headline_lines = [lines[0][len(_NEXT_PREFIX):]]
        headline_lines.extend(line[1:] for line in lines[1:idx])
        headline = "\n".join(headline_lines)

        fields = _parse_fields(lines[idx + 1:], _CONTEXT_BODY_FIELD_RE)
        if fields is None or "Context" not in fields:
            return None

        keys = _decode_list(fields["Keys"]) if "Keys" in fields else ()

        return ContextNote(
            headline=headline,
            context=fields["Context"],
            keys=keys,
            timestamp=datetime.now(timezone.utc),
        )
    except Exception:
        return None
