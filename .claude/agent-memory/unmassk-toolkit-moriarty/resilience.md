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

## release.py / bin/bump-version.py (2026-06-09)

- Path traversal `../evil` → rejected by PLUGIN_NAME_RE before any filesystem access.
- Uppercase plugin name → rejected by PLUGIN_NAME_RE.
- Empty plugin name → rejected by PLUGIN_NAME_RE.
- `UNMASSK_REPO_ROOT` env set to external repo → release.py overrides it with the correct root; victim repo not mutated.
- 1.9.0 → 1.10.0 semver comparison → _semver_tuple uses int(); (1,9,0) < (1,10,0) correctly.
- 2.0.0 > 1.99.99 comparison → (2,0,0) > (1,99,99) correctly.
- 1.4.0-rc1 vs 1.4.0 (same core) → rejected as "not greater" (correct behavior).
- Working tree check without --allow-dirty → correctly aborts.
- No upstream configured → correctly aborts.
- CHANGELOG absent → correctly aborts with FileNotFoundError message.
- CHANGELOG with whitespace-only [Unreleased] body → correctly aborts.
- Push failure → exits code 2 (VERIFY_FAIL), not 0; local commit preserved; ADVERTENCIA printed.
- Second release same version → rejected as "not greater".
- git fetch fails, push also fails → exits code 2 (not silent); files are mutated locally but that is documented behavior.
- Detached HEAD → correctly aborts (no upstream).
- CRLF CHANGELOG → handled correctly; output is clean; no double-blank-line corruption.
- 10,000-line CHANGELOG → processed in <1s, no timeout.
- Huge version 99999.99999.99999 → accepted as valid (correct: valid semver).
- Concurrent releases (same version, two threads) → one wins (rc=0), other fails at git add (index lock); final state consistent.

## user-prompt-memory-check.py recall injection (2026-06-12)

- Binary stdin (NUL bytes, 0xff, 0x80) → _read_prompt_text() returns None, hook exits 0 cleanly
- latin-1 / Windows-1252 encoded stdin (invalid UTF-8) → swallowed by except Exception
- Lone surrogate \ud800 in JSON → json.loads fails, swallowed, hook exits 0
- BOM prefix on valid JSON → json.loads fails, swallowed, hook exits 0
- JSON with trailing garbage → json.loads fails, swallowed, hook exits 0
- prompt=number/list/object/null/bool → isinstance guard rejects, hook exits 0
- Deeply nested JSON (depth 500, 990) → json.loads handles or fails silently, hook exits 0
- 10MB stdin → _read_prompt_text() truncated at 2000 chars by recall.py, hook exits 0 in <210ms
- Stopwords-only query → _tokenize returns empty set → recall_relevant returns None, no injection
- Punctuation-only query → same as above
- Digits-only query → tokenizer requires at least one letter, no injection
- All-equal-score corpus (6 entries) → top_fraction gate admits all, capped at max_results=3 correctly
- Determinism: tied scores produce identical output across 10 in-process calls AND 5 subprocess calls (stable sort by insertion index)
- 300 commits hook latency: avg 140ms (well under 300ms target)
- Manifest > plugin version: needs_upgrade returns False (no spurious upgrade trigger)
- All manifest edge cases (null, missing, corrupt JSON, non-semver): fail-safe returns False, hook exits 0
- Concurrent first-boot (5 processes, no .session-booted): all exit 0, all emit [memory-check], flag write is idempotent
- Concurrent git commits during hook reads: all hook invocations exit 0, no corruption
