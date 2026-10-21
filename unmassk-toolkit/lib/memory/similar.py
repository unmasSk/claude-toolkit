"""Find existing notes in the same zone pair that overlap a new note.

Works on already-loaded data; the caller (`validator.validate_replacement`) decides what to do.
"""

import re

import textnorm
from model import Note

_WORD_RE = re.compile(r"\w+", re.UNICODE)


def _tokens(note: Note) -> frozenset:
    """Normalized vocabulary of a note: headline, description, why (if any) and keys."""
    parts = [note.headline, note.description]
    if note.why:
        parts.append(note.why)
    parts.extend(note.keys)

    text = textnorm.normalize_text(" ".join(parts))
    return frozenset(_WORD_RE.findall(text))


def _jaccard(a: frozenset, b: frozenset) -> float:
    """Intersection over union; 0.0 when both are empty."""
    union = a | b
    if not union:
        return 0.0
    return len(a & b) / len(union)


def _zone_pair(note: Note) -> frozenset:
    """The note's zone pair as an unordered set, for duplicate checks only."""
    return frozenset((note.zone1, note.zone2))


def find_similar(
    candidate: Note,
    existing: tuple[Note, ...],
    threshold: float,
) -> tuple[Note, ...]:
    """Notes of `existing` in the same zone pair whose Jaccard with `candidate` reaches `threshold`."""
    candidate_words = _tokens(candidate)
    candidate_zones = _zone_pair(candidate)
    matches = []
    for note in existing:
        if _zone_pair(note) != candidate_zones:
            continue
        if _jaccard(candidate_words, _tokens(note)) >= threshold:
            matches.append(note)
    return tuple(matches)


def _find_exact_key_match(
    candidate: Note,
    existing: tuple[Note, ...],
) -> tuple[Note, ...]:
    """Notes of `existing` in the same zone pair with the same non-empty set of (already normalized) keys."""
    candidate_keys = frozenset(candidate.keys)
    if not candidate_keys:
        return ()

    candidate_zones = _zone_pair(candidate)
    matches = []
    for note in existing:
        if _zone_pair(note) != candidate_zones:
            continue
        if frozenset(note.keys) == candidate_keys:
            matches.append(note)
    return tuple(matches)


def find_overlapping(
    candidate: Note,
    existing: tuple[Note, ...],
    threshold: float,
) -> tuple[Note, ...]:
    """Union of `find_similar` and exact key matches, deduplicated by id, similar first."""
    seen: set[str] = set()
    matches: list[Note] = []
    for note in (
        *find_similar(candidate, existing, threshold),
        *_find_exact_key_match(candidate, existing),
    ):
        if note.id not in seen:
            seen.add(note.id)
            matches.append(note)
    return tuple(matches)
