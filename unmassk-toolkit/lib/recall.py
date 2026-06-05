"""
recall — BM25-ranked memory search for unmassk git-memory.

Public interface:
    recall(query, *, limit=8, scope=None) -> str

The returned string is a formatted block grouped by type
(DECISIONES / MEMOS / REMEMBER), each entry on its own line.
Returns empty string when no matches are found.

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
from parsing import scan_trailers_memory, parse_scope, normalize
from constants import TOMBSTONE_KEYS, RECALL_KEYS

# ── Constants ──────────────────────────────────────────────────────────

# Maximum query length — guards against oversized inputs.
MAX_QUERY_LEN: int = 2000

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

    Removes:
    - Newlines and carriage returns (\\n, \\r)
    - Unicode line/paragraph separators (U+2028, U+2029)
    - Vertical tab and form feed (\\x0b, \\x0c)
    - HTML comment markers (<!-- and -->)
    """
    text = re.sub(r"[\r\n  \x0b\x0c]", " ", text)
    text = text.replace("<!--", "").replace("-->", "")
    return text.strip()


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
    git_args = [
        "log", "--all",
        "--pretty=format:%h\x1f%s\x1f%b\x1e",
    ]

    code, log_output = run_git(git_args, cwd=repo_dir)

    if code != 0 or not log_output:
        return []

    tombstones: set[str] = set()
    seen_norms: dict[str, set[str]] = {k: set() for k in _MEMORY_KEYS}
    entries: list[dict] = []

    commits = log_output.split("\x1e")

    # Two-pass: first collect tombstones, then entries.
    # Because tombstones may appear AFTER their targets in log order
    # (older commits), we do a full tombstone pass first.
    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f", 3)
        if len(parts) < 3:
            continue
        body = parts[2]
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
        parts = entry.split("\x1f", 3)
        if len(parts) < 3:
            continue
        sha, subject, body = parts[0], parts[1], parts[2]
        trailers = scan_trailers_memory(body)

        scope = parse_scope(subject) or ""
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


# ── Public API ──────────────────────────────────────────────────────────

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

    query_tokens = _tokenize(query)
    if not query_tokens:
        return ""

    # Cap token count after tokenization.
    if len(query_tokens) > MAX_QUERY_TOKENS:
        query_tokens = set(list(query_tokens)[:MAX_QUERY_TOKENS])

    df = _build_df(entries)
    n = len(entries)

    scored: list[tuple[float, dict]] = []
    for entry in entries:
        score = _idf_score(entry, query_tokens, df, n)
        if score > 0.0:
            scored.append((score, entry))

    if not scored:
        return ""

    # Sort by score descending, then stable by insertion order
    scored.sort(key=lambda x: x[0], reverse=True)

    # Cap to limit
    top = [entry for _, entry in scored[:limit]]

    # Group by kind in canonical order
    groups: dict[str, list[dict]] = {k: [] for k in _MEMORY_KEYS}
    for entry in top:
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
