# Resilience — Attacks That Held

## recall.py / git-memory-recall.py (2026-06-05)

- Empty string query → returns '(no matches)' cleanly. No crash.
- 10,000-char query → handled in 130ms. No crash. No timeout.
- All-stopword query → returns '(no matches)'. No crash.
- Regex metacharacters as query (`.*`, `[`, `(`) → tokenizer strips them. No re.error.
- Backslash-only query → empty token set, clean '(no matches)'.
- Emoji-only query → empty token set, clean '(no matches)'.
- Unicode non-Latin queries (Arabic, Chinese, Cyrillic) → empty token set, clean result.
- `--flags` passed as query → argparse handles correctly; unrecognized flags = error exit 2.
- limit=0 and limit=-1 via CLI → correctly rejected with error message.
- limit=-5 via API → clamped to 1 by `if limit < 1: limit = 1`. Returns 1 result.
- limit=999999999 → returns all results (Python slice handles it cleanly).
- scope='nonexistent/scope' → returns '(no matches)' cleanly.
- scope='.*' → treated as literal string, no regex execution, no crash.
- scope='' (empty) → treated as falsy, no filter applied (same as scope=None).
- scope case-insensitive matching → works correctly (both sides lowercased).
- Git injection via query string → query never passed to git subprocess. Safe.
- Tombstoned entries do NOT leak into IDF df weights (filtered before _build_df).
- Decisions are never tombstoned — by design and verified in practice.
- Tie-breaking sort → Python's stable sort preserves insertion order deterministically.
- Race conditions → recall() is fully stateless. No shared mutable state.
- Regex ReDoS in _tokenize → character class with no backtracking. Safe.
