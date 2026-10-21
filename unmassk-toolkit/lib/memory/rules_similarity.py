"""Recognise written rule lines and find near-duplicate rules by text."""

import re
from typing import NamedTuple

import textnorm
from rules_commit import read_all
from vocabulary import SIMILARITY_THRESHOLD


_WORD_RE = re.compile(r"\w+", re.UNICODE)

# A written rule line: "[remember][kind] <emoji> <text>".
_RULE_LINE_RE = re.compile(r"^\[remember\]\[(?P<kind>[^\]]+)\]\s+\S+\s+(?P<text>.+)$")


def _tokenize(text: str) -> frozenset[str]:
    """Return the set of normalised words in `text`."""
    return frozenset(_WORD_RE.findall(textnorm.normalize_text(text)))


def _jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Return intersection over union; 0.0 when both sets are empty."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def iter_rule_texts(content: str) -> tuple[str, ...]:
    """Return the text of each rule line in `content`, without its `[remember][kind] emoji` prefix."""
    texts = []
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is not None:
            texts.append(match.group("text"))
    return tuple(texts)


class _RuleMatch(NamedTuple):
    """A `similar_existing()` match: owner kind and rule text."""

    kind: str
    text: str


def _iter_rule_lines(content: str) -> tuple[tuple[str, str], ...]:
    """Like `iter_rule_texts()`, but return `(kind, text)` pairs."""
    lines = []
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is not None:
            lines.append((match.group("kind"), match.group("text")))
    return tuple(lines)


# The quote suffix of a written rule: em dash + guillemets.
_QUOTE_SUFFIX_RE = re.compile(r"^(?P<text>.*) — «(?P<quote>.*)»$")


def strip_quote_suffix(text: str) -> str:
    """Return `text` without its ` — «...»` quote suffix, if any."""
    match = _QUOTE_SUFFIX_RE.match(text)
    if match is not None:
        return match.group("text")
    return text


def find_rule_line(content: str, text: str, kind: str) -> str | None:
    """Return the raw rule line owned by `kind` whose unquoted text equals `text`, or None."""
    for line in content.splitlines():
        match = _RULE_LINE_RE.match(line)
        if match is None:
            continue
        if match.group("kind") != kind:
            continue
        if strip_quote_suffix(match.group("text")) != text:
            continue
        return line
    return None


def remove_rule_line(content: str, matched_line: str) -> str:
    """Return `content` without the first line equal to `matched_line`."""
    kept = []
    removed = False
    for line in content.splitlines(keepends=True):
        if not removed and line.rstrip("\n") == matched_line:
            removed = True
            continue
        kept.append(line)
    return "".join(kept)


def similar_existing(text: str) -> tuple[_RuleMatch, ...]:
    """Return the saved rules whose text is similar to `text`, as `(kind, text)` matches."""
    candidate = _tokenize(text)
    matches = []
    for kind, existing_text in _iter_rule_lines(read_all()):
        # The quote never counts towards similarity nor is returned.
        stripped_text = strip_quote_suffix(existing_text)
        if _jaccard(candidate, _tokenize(stripped_text)) >= SIMILARITY_THRESHOLD:
            matches.append(_RuleMatch(kind, stripped_text))
    return tuple(matches)
