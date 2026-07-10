"""
recall — BM25-ranked memory search for unmassk git-memory.

Public interface:
    recall(query, *, limit=8, scope=None) -> str
    recall_relevant(query, *, max_results=RECALL_MAX_RESULTS,
                    floor=RECALL_FLOOR, top_fraction=RECALL_TOP_FRACTION,
                    scope=None, _repo_dir=None) -> str | None

recall() returns a formatted block grouped by type
(DECISIONES / MEMOS / REMEMBER), each entry on its own line.
Returns empty string when no matches are found.

recall_relevant() applies a relevance gate before returning the block:
  - Entries with score <= floor are discarded (noise floor).
  - From the survivors, only entries scoring >= top_fraction * top_score
    are kept (top-fraction window).
  - The result is capped to max_results entries (score desc).
  - Returns None (not empty string) when nothing clears the gate.

Ranking formula (IDF-weighted token overlap):
    score(entry) = sum over matching tokens t of:
        log(1 + N / (df[t] + 1))
    where N = total entries in corpus, df[t] = entries containing t.
    This is a simplified IDF. Rare tokens get high weight; tokens
    that appear in almost every entry contribute nearly nothing.

Scope match bonus:
    When a query token matches a token in the entry's scope (not text),
    the IDF contribution for that token is multiplied by 1.5. This bonus
    is exclusive: a token scored via scope does NOT also add the text-only
    contribution for the same token in the same entry.
"""

import math
import re
import subprocess
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from git_helpers import run_git, GIT_TIMEOUT
from parsing import scan_trailers_memory, parse_scope, normalize, sanitize_trailer_value as _sanitize_canonical
from constants import TOMBSTONE_KEYS, RECALL_KEYS

# ── Constants ──────────────────────────────────────────────────────────

# Maximum query length — guards against oversized inputs.
MAX_QUERY_LEN: int = 2000

# Gate constants for recall_relevant() — exported so callers can introspect defaults.

# RECALL_MAX_RESULTS: caps the number of entries recall_relevant() may return.
# Keep low (3) to avoid flooding Claude's context with marginal matches.
RECALL_MAX_RESULTS: int = 3

# RECALL_FLOOR: absolute noise floor — entries with score <= this are discarded.
# Rationale: the minimum realistic IDF score for a single match in a one-entry
# corpus is log(1 + 1/(0+1)) = log(2) ≈ 0.693.  For a token present in half the
# corpus (df = N/2) the IDF contribution is log(1 + 1/2) ≈ 0.405.  Setting the
# floor at 0.01 sits well below that minimum, so only true zero-scorers and
# floating-point near-zero noise are cut — never a genuine match.
# If you lower this, you risk surfacing unrelated entries.
# If you raise it above ~0.4, you risk hiding single-token matches on small corpora.
RECALL_FLOOR: float = 0.01

# RECALL_TOP_FRACTION: fraction of the top entry's score that all returned entries
# must reach.  0.5 means "at least half as relevant as the best match".
# Raise to tighten the window (fewer, more focused results).
# Lower to widen it (more results, more noise).
RECALL_TOP_FRACTION: float = 0.5

# Maximum number of query tokens after tokenization.
MAX_QUERY_TOKENS: int = 50

# Tombstone and recall keys imported from constants (single source of truth).
_TOMBSTONE_KEYS: tuple[str, ...] = TOMBSTONE_KEYS
_MEMORY_KEYS: tuple[str, ...] = RECALL_KEYS

# Section headers for output.
_SECTION_HEADERS = {
    "Decision": "DECISIONES",
    "Memo": "MEMOS",
    "Remember": "REMEMBER",
}

# Stopwords: common ES + EN words that carry no discriminating signal.
_STOPWORDS: frozenset[str] = frozenset({
    # EN
    "the", "and", "for", "from", "with", "that", "this", "not", "are", "was",
    "have", "has", "had", "its", "can", "will", "all", "but", "been", "use",
    "used", "via", "into", "over", "also", "each", "per", "any", "our", "you",
    "add", "new", "set", "run", "get", "put", "out", "off", "now", "one",
    # ES
    "para", "con", "por", "que", "los", "las", "del", "una", "sin",
    "son", "ser", "sus", "hay", "mas", "pero", "como", "todo",
    "cuando", "donde", "entre", "sobre", "cada", "esto", "esta", "ese", "esa",
})


# ── Text helpers ────────────────────────────────────────────────────────

def _tokenize(text: str) -> set[str]:
    """Return lowercase alphanumeric tokens >=2 chars with at least one letter,
    excluding stopwords.

    The pattern allows tokens like 'BM25', 'v2', 'RS256', 'auth3' that contain
    both letters and digits. Pure-digit strings (e.g. '123') are excluded by
    requiring at least one letter via the lookahead.
    """
    return {
        w.lower()
        for w in re.findall(
            r"(?=[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9]*[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ])"
            r"[a-zA-ZáéíóúüñÁÉÍÓÚÜÑ0-9]{2,}",
            text,
        )
        if w.lower() not in _STOPWORDS
    }


def _sanitize(text: str) -> str:
    """Strip injection characters from a trailer value.

    Delegates to the canonical sanitizer in lib/parsing.sanitize_trailer_value.
    Kept as a private wrapper for backward compatibility with internal callers.
    """
    return _sanitize_canonical(text)


# ── Git scanning ────────────────────────────────────────────────────────

def _scan_commits(repo_dir: str | None = None) -> list[dict]:
    """Scan git log and return all memory entries (Decision/Memo/Remember).

    Scans the full history (--all, no -n cap) so no memory entry is ever
    silently lost. If a cap is ever re-introduced for performance it MUST
    warn to stderr — silent truncation is not allowed.

    Each entry is:
        {kind, scope, label, text, norm}

    Tombstoned entries are excluded. Duplicate normalized texts are
    deduplicated (first occurrence wins, matching extract_memory behavior).

    Args:
        repo_dir: If provided, git is run from that directory (tests).
                  If None, uses current working directory.
    """
    # Filter to commits that contain memory trailers using --extended-regexp --grep.
    # This avoids scanning every code commit in large repos while guaranteeing
    # that NO memory entry is lost (a brute -n cap would silently truncate history).
    # The regex anchors each key at line-start (^) inside the commit body.
    _all_keys = list(_TOMBSTONE_KEYS) + list(_MEMORY_KEYS)
    _grep_pattern = "^(" + "|".join(_all_keys) + "):"
    # SEC-CRIT-NEW-01 pattern (Argus, mirrored from lib/boot_memory.py's
    # extract_memory()/extract_glossary(), issue #57): `-z` (NUL, \x00)
    # record boundaries instead of an embedded \x1e in the
    # --pretty=format string. A commit body CAN contain a literal \x1e
    # byte -- str.split()-ing on it let a single real commit forge an
    # entire fake memory entry (this function's output feeds
    # UserPromptSubmit/PreToolUse hooks, which inject directly into the
    # LLM's context -- highest blast radius of the 6 forgery sites). A
    # commit message can never contain a raw NUL byte, so splitting on
    # \x00 has no forgeable equivalent. \x1f remains the FIELD separator
    # within a single record.
    #
    # Structural fix (issue #57 root-fix round, decision 0682e75): %s
    # (subject) is last in the header, separated from %b (body) by %n
    # (a real newline), not by \x1f. git guarantees %s never contains a
    # literal newline, so the FIRST "\n" in a record reliably separates
    # the header zone (sha\x1fsubject) from the body zone -- a stray
    # \x1f embedded anywhere in the SUBJECT alone (no \x1e, no forged
    # record) used to consume the maxsplit slot meant for the real
    # subject/body boundary, gluing the discarded tail onto the FRONT of
    # the real body and erasing the real trailer. Now any extra \x1f in
    # the subject is simply absorbed into `subject` itself
    # (header.split("\x1f", 1) below), never bleeding into `body`.
    git_args = [
        "log", "--all", "-z",
        "--extended-regexp",
        "--grep=" + _grep_pattern,
        "--pretty=format:%h%s%n%b",
        "--",
    ]

    # breadcrumb #61: transient git failure here used to collapse to an
    # empty [] with zero trace; log_stderr_on_failure leaves a trace, []
    # return value unchanged (see run_git()'s docstring in git_helpers.py).
    code, log_output = run_git(git_args, cwd=repo_dir, log_stderr_on_failure=True)

    if code != 0 or not log_output:
        return []

    tombstones: set[str] = set()
    seen_norms: dict[str, set[str]] = {k: set() for k in _MEMORY_KEYS}
    entries: list[dict] = []

    commits = log_output.split("\x00")

    # Two-pass: first collect tombstones, then entries.
    # Because tombstones may appear AFTER their targets in log order
    # (older commits), we do a full tombstone pass first.
    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        # Structural fix (issue #57 root-fix round, decision 0682e75):
        # the header zone (sha\x1fsubject) ends at the FIRST real "\n" --
        # %n in the format string, never present inside %s itself. Split
        # there first, THEN split the header on \x1f with maxsplit=1 so
        # `subject` (last in the header) absorbs any stray \x1f embedded
        # in it, instead of that byte stealing the split meant for the
        # subject/body boundary.
        header, _, body = entry.partition("\n")
        parts = header.split("\x1f", 1)
        if len(parts) < 2:
            continue
        trailers = scan_trailers_memory(body)
        for key in _TOMBSTONE_KEYS:
            if key in trailers:
                # Apply same sanitize+normalize pipeline as the entry path so
                # tombstone lookup always matches (fixes deception edge case).
                tombstones.add(normalize(_sanitize(trailers[key])))

    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        # Same header/body split as the tombstone pass above — see comment there.
        header, _, body = entry.partition("\n")
        parts = header.split("\x1f", 1)
        if len(parts) < 2:
            continue
        sha, subject = parts[0], parts[1]
        trailers = scan_trailers_memory(body)

        # SEC-CRIT-NEW-04 (issue #57, Task 2b, mirrored from
        # lib/boot_memory.py): `scope` comes straight from the fully
        # attacker-controlled commit subject via parse_scope(), yet it
        # was embedded into `label` (fed straight into _format_block()'s
        # LLM-facing output) with no sanitization — unlike every trailer
        # VALUE in this function, which already goes through _sanitize().
        scope = _sanitize(parse_scope(subject) or "")
        label = f"({scope})" if scope else "(global)"

        for kind in _MEMORY_KEYS:
            if kind not in trailers:
                continue
            text = _sanitize(trailers[kind])
            norm = normalize(text)
            # Decisions are never tombstoned (matches extract_memory() behavior).
            # Memos and Remembers are excluded if their text is tombstoned.
            if kind != "Decision" and norm in tombstones:
                continue
            if norm in seen_norms[kind]:
                continue
            seen_norms[kind].add(norm)
            entries.append({
                "kind": kind,
                "scope": scope,
                "label": label,
                "text": text,
                "norm": norm,
            })

    return entries


# ── Ranking ─────────────────────────────────────────────────────────────

def _idf_score(entry: dict, query_tokens: set[str], df: dict[str, int], n: int) -> float:
    """Compute IDF-weighted overlap score for one entry.

    Formula: sum of log(1 + N / (df[t] + 1)) for each query token t
    that appears in the entry's text OR scope.

    Scope match gets a 1.5x bonus because scope is usually the most
    specific signal (e.g. "plugin/recall" is more precise than the
    trailer prose). The bonus is exclusive: a token matched via scope
    does NOT also add the plain text-match contribution for the same
    token in the same entry.
    """
    if not query_tokens or n == 0:
        return 0.0

    entry_tokens = _tokenize(entry["text"])
    scope_tokens = _tokenize(entry["scope"])

    score = 0.0
    for token in query_tokens:
        if token not in entry_tokens and token not in scope_tokens:
            continue
        idf = math.log(1.0 + n / (df.get(token, 0) + 1))
        # Scope match is more precise — exclusive 1.5x boost
        if token in scope_tokens:
            score += idf * 1.5
        else:
            score += idf
    return score


def _build_df(entries: list[dict]) -> dict[str, int]:
    """Build document-frequency table: token -> count of entries containing it."""
    df: dict[str, int] = {}
    for entry in entries:
        tokens = _tokenize(entry["text"]) | _tokenize(entry["scope"])
        for token in tokens:
            df[token] = df.get(token, 0) + 1
    return df


# ── Shared scoring core ─────────────────────────────────────────────────

def _score_entries(
    query: str,
    entries: list[dict],
    df: dict[str, int],
    n: int,
) -> list[tuple[float, int, dict]]:
    """Tokenize *query* and score every entry in *entries* against it.

    Returns a list of ``(score, original_index, entry)`` tuples for every
    entry with score > 0, in the order the entries were supplied.
    The ``original_index`` preserves insertion order so callers can break
    ties deterministically (stable sort on the index column).

    Query tokenization and the MAX_QUERY_TOKENS cap are applied here so
    that both ``recall()`` and ``recall_relevant()`` share exactly one
    tokenization path — no divergence risk.

    Returns an empty list when the query produces no tokens or *entries*
    is empty.
    """
    query_tokens = _tokenize(query)
    if not query_tokens:
        return []

    # Cap token count — sorted for deterministic order.
    if len(query_tokens) > MAX_QUERY_TOKENS:
        query_tokens = set(sorted(query_tokens)[:MAX_QUERY_TOKENS])

    scored: list[tuple[float, int, dict]] = []
    for idx, entry in enumerate(entries):
        score = _idf_score(entry, query_tokens, df, n)
        if score > 0.0:
            scored.append((score, idx, entry))
    return scored


# ── Public API ──────────────────────────────────────────────────────────

def _format_block(entries: list[dict]) -> str:
    """Format a list of memory entries into a grouped string block.

    Groups entries by kind in canonical order (Decision / Memo / Remember),
    each under its section header [DECISIONES] / [MEMOS] / [REMEMBER].
    Returns the joined string (never empty — callers must ensure entries is non-empty).
    """
    groups: dict[str, list[dict]] = {k: [] for k in _MEMORY_KEYS}
    for entry in entries:
        groups[entry["kind"]].append(entry)

    lines: list[str] = []
    for kind in _MEMORY_KEYS:
        bucket = groups[kind]
        if not bucket:
            continue
        lines.append(f"[{_SECTION_HEADERS[kind]}]")
        for entry in bucket:
            lines.append(f"  {entry['label']} {entry['text']}")

    return "\n".join(lines)


def recall(
    query: str,
    *,
    limit: int = 8,
    scope: str | None = None,
    _repo_dir: str | None = None,
) -> str:
    """Search git memory and return a ranked, deduplicated block.

    Args:
        query:     Natural-language search query.
        limit:     Maximum number of entries in the output (default 8).
        scope:     Optional scope filter (e.g. "plugin/recall"). When given,
                   only entries whose scope starts with this prefix are returned.
        _repo_dir: Internal — override git working directory for tests.

    Returns:
        Formatted string grouped by type (DECISIONES / MEMOS / REMEMBER).
        Empty string if no matches.
    """
    # Guard: empty or whitespace-only query — skip git entirely.
    if not query.strip():
        return ""

    # Guard: cap query length to prevent oversized input abuse.
    if len(query) > MAX_QUERY_LEN:
        query = query[:MAX_QUERY_LEN]

    if limit < 1:
        limit = 1

    entries = _scan_commits(repo_dir=_repo_dir)
    if not entries:
        return ""

    # Optional scope filter
    if scope:
        scope_lower = scope.lower()
        entries = [e for e in entries if e["scope"].lower().startswith(scope_lower)]
        if not entries:
            return ""

    df = _build_df(entries)
    n = len(entries)

    scored = _score_entries(query, entries, df, n)
    if not scored:
        return ""

    # Sort by score descending, then stable by insertion order (original index).
    scored.sort(key=lambda x: (-x[0], x[1]))

    # Cap to limit
    top = [entry for _, _, entry in scored[:limit]]

    return _format_block(top)


def recall_relevant(
    query: str,
    *,
    max_results: int = RECALL_MAX_RESULTS,
    floor: float = RECALL_FLOOR,
    top_fraction: float = RECALL_TOP_FRACTION,
    scope: str | None = None,
    _repo_dir: str | None = None,
) -> str | None:
    """Search git memory and return a block only when entries clear the relevance gate.

    The gate (applied in order):
      1. Discard entries with score <= floor (noise floor).
      2. Compute top_score = max score of survivors; if none → None.
      3. Keep only entries with score >= top_fraction * top_score.
      4. Sort by score desc (stable), cap to max_results.
      5. If the final list is empty → None; otherwise the formatted block.

    Args:
        query:        Natural-language search query.
        max_results:  Maximum entries returned (default RECALL_MAX_RESULTS=3).
        floor:        Absolute noise floor; entries with score <= this are dropped.
        top_fraction: Fraction of top score that surviving entries must reach.
        scope:        Optional scope prefix filter (same semantics as recall()).
        _repo_dir:    Internal — override git working directory for tests.

    Returns:
        Formatted string block (str) or None.
    """
    # Guard: empty or whitespace-only query.
    if not query.strip():
        return None

    # Guard: cap query length.
    if len(query) > MAX_QUERY_LEN:
        query = query[:MAX_QUERY_LEN]

    if max_results < 1:
        max_results = 1

    entries = _scan_commits(repo_dir=_repo_dir)
    if not entries:
        return None

    # Optional scope filter — same logic as recall().
    if scope:
        scope_lower = scope.lower()
        entries = [e for e in entries if e["scope"].lower().startswith(scope_lower)]
        if not entries:
            return None

    df = _build_df(entries)
    n = len(entries)

    # Score all entries via shared core (tokenization + IDF scoring).
    scored = _score_entries(query, entries, df, n)
    if not scored:
        return None

    # Step 1: discard noise (score <= floor).
    above_floor = [(s, i, e) for s, i, e in scored if s > floor]
    if not above_floor:
        return None

    # Step 2: top score from survivors.
    top_score = max(s for s, _, _ in above_floor)

    # Step 3: apply top-fraction window.
    threshold = top_fraction * top_score
    within_window = [(s, i, e) for s, i, e in above_floor if s >= threshold]
    if not within_window:
        return None

    # Step 4: sort by score desc, stable by original insertion index.
    within_window.sort(key=lambda x: (-x[0], x[1]))
    top = [e for _, _, e in within_window[:max_results]]

    # within_window is non-empty and max_results >= 1, so top is always non-empty here.
    return _format_block(top)
