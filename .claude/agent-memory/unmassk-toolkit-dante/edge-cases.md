---
name: omawamapas-search-edge-cases
description: Recurring edge cases for search module — LIKE injection, RBAC, parameterized SQL, pagination
type: project
---

## LIKE Pattern Injection (escapeLikePattern)
Three special chars to escape: `%` (wildcard), `_` (single-char wildcard), `\` (escape char).
Order matters: escape `\` FIRST, then `%`, then `_`.
Test: `%_\` -> `\%\_\\`
Double-application is NOT idempotent — `%` -> `\%` -> `\\\%`. Test this explicitly.
Adversarial payloads: `\%`, `\_`, `\\\`, `%_\%_\` (sequences of all three).

## Parameterized Query Assertions
SQL injection test pattern:
1. Assert payload is NOT in the SQL string
2. Assert escaped version of payload IS in the params array
3. Assert SQL contains `$\d+` placeholders

SQL injection payloads confirmed covered:
- `'; DROP TABLE municipio; --`
- `' OR '1'='1`
- `' UNION SELECT * FROM usuario --`
- `1; DELETE FROM inventario`
- `' AND 1=1 --`
- `test\\'; DROP TABLE --`

## ParamBuilder snapshot() for COUNT vs DATA
COUNT params = `pb.snapshot()` before adding relevance params.
DATA params = `pb.params()` which includes relevance + limit + offset added after snapshot.
This split is critical — asserting on COUNT params[0] for LIKE term, but DATA params[-2]/[-1]
for limit/offset.

## RBAC Roles (omawamapas)
Roles: `Coordinador`, `Supervisor`, `Operador`, `Tecnico`, `Municipio`, `Ciudadano`
User search access: only `Coordinador`, `Supervisor`, `Operador` (from SEARCH_USER_ACCESS_ROLES)
Inventory RBAC:
  - Coordinador: no restriction
  - Supervisor: subquery via `supervisor_municipio WHERE usuario_id = $N`
  - Operador: subquery via `operador_municipio` + `i.usuario_id` (userId appears TWICE in params)
  - Tecnico: `i.usuario_id` + `SELECT municipio_id FROM usuario` (userId appears TWICE)
  - Municipio: `SELECT municipio_id FROM usuario WHERE id = $N`
  - Unknown/Ciudadano: `1 = 0` (deny-all)

## Pagination Edge Cases
- offset = (page - 1) * limit
- Assert: `dataParams[-2]` = limit, `dataParams[-1]` = offset
- Zod caps page at 10000 (confirmed: `9999999` rejected)
- Large page (999999) produces large offset but stays within INT4_MAX

## INT4 Overflow Protection
PostgreSQL INT4_MAX = 2_147_483_647
municipioId, layerId capped at INT4_MAX by Zod schema
Test both INT4_MAX (accept) and INT4_MAX+1 (reject)

## Empty Term Behavior
When term is empty string: no LIKE condition added to SQL.
Assert: `countParams` does not contain any value starting with `%`.

## WS Identity / Name Resolution (chatroom ws.ts)
- `resolveConnectionName` is NOT exported → inline a copy in the test file (same pattern as rate-limit helper)
- Reserved names: all AGENT_BY_NAME keys EXCEPT 'user' and 'claude'
- Check is case-insensitive: 'BILBO', 'Ultron', 'Dante' all rejected
- Empty string and whitespace-only → 'user' (not null)
- NAME_RE: `/^[a-zA-Z0-9_-]{1,32}$/` — spaces, `!`, `@` all rejected
- 'user' and 'claude' explicitly allowed despite being in AGENT_BY_NAME
- Import `AGENT_BY_NAME` from `@agent-chatroom/shared` to derive reserved names dynamically (never hardcode)

## Context Overflow Detection (agent-invoker.ts)

Signal: `CONTEXT_OVERFLOW_SIGNAL = 'prompt is too long'` (lowercase constant).
Detection: `resultText.toLowerCase().includes(signal) || stderrOutput.toLowerCase().includes(signal)`.
Case variations Claude may emit: all-lowercase, mixed-case (Prompt Is Too Long), all-uppercase (PROMPT IS TOO LONG).
Test all three, plus "embedded in longer string", plus "only in stderrOutput".
DO NOT trigger on partial: 'prompt is too' (without 'long') must return false.

## RESPAWN Delimiters — Sanitize U+2550 box-drawing chars

Delimiters: `\u2550\u2550\u2550\u2550\u2550\u2550 RESPAWN NOTICE \u2550\u2550\u2550\u2550\u2550\u2550`
Regex: `/\u2550{2,}[^\n\u2550]*\u2550{2,}/g` → replaces with `[DELIMITER-SANITIZED]`
Edge cases:
- Single `\u2550` alone must NOT match (requires ≥2)
- Nested double-framing: bracket marker inside a fake U+2550 block — both must be sanitized independently

## peekToken vs validateToken (auth-tokens.ts)

- `peekToken(token)` does NOT delete the token — same token remains valid for subsequent calls
- `validateToken(token)` deletes the token on first success (one-time-use)
- Pattern for testing peekToken non-consumption: call peek twice, both return the name. Then call validateToken — succeeds. Then call validateToken again — returns null (now consumed).

## @everyone Double-Invoke Guard (ws.ts)

Pattern: `const everyoneProcessed = /@everyone\b/i.test(content); const mentions = everyoneProcessed ? new Set() : extractMentions(content);`
Key: `\b` word boundary — `@everyone123` does NOT match (no boundary after 'everyone').
Test with spy: verify `extractMentions` is not called when @everyone present.

## Priority Queue — enqueue() Logic (agent-invoker.ts)

`priority=true` → `unshift()` (front of queue, human-priority)
`priority=false` → `push()` (back of queue, normal)
Multiple priority entries are LIFO at the front (last unshifted = index 0).
Test with inline mirror since `enqueue()` and `pendingQueue` are not exported.

## Auth Tokens — Brute-Force Tracking (auth-tokens.ts)

`recordAuthFailure` is internal — test via public API:
- peekToken / validateToken with unknown tokens call recordAuthFailure internally
- sourceKey: tokens < 8 chars → sentinel 'unknown'; ≥ 8 chars → first 8 chars
- After 10 failures from same prefix → error log (does NOT throw, still returns null)
- Test file: `auth-tokens-brute-force.test.ts`
- Pattern: use `'brute-tf' + suffix` to get consistent prefix 'brute-tf' across calls

## Config Validation Helpers (config.ts)

`requireIntEnv`, `requireEnumEnv`, `stringEnv` are NOT exported.
Test pattern: inline mirror that throws instead of calling process.exit(1).
See `config-validation.test.ts` for complete coverage.
Key edge cases:
- Empty string '' → returns default (same as undefined)
- Float like '3.14' → invalid for requireIntEnv (Number.isInteger check)
- 'NaN', 'Infinity' → invalid (Number() converts but isInteger fails)
- Case-sensitive enum matching: 'DEBUG' is not 'debug'

## recall.py — BM25 Recall Engine Edge Cases

### Tombstone two-pass ordering (non-obvious)
git log is newest-first. GC commit (newer) appears at log position 0; original entry (older) at position 1.
Single-pass would process entry before seeing tombstone — include it erroneously.
Two-pass: first pass collects ALL tombstone values, second pass filters. Order in log is irrelevant.
Test name: `test_gc_commit_before_target_in_log_still_tombstones`.
`_TOMBSTONE_KEYS` = ("Resolved-Next", "Stale-Blocker", "Resolved-Memo", "Resolved-Remember").
`Stale-Blocker` suppresses Memo. `Resolved-Next` does NOT suppress Decision (Decisions are never tombstoned).

### Dedup is per-kind, not cross-kind
`seen_norms` is keyed by kind. Same normalized text in Decision and Remember = two entries (one per section).

### Scope match (1.5x) outranks text-only match
Token in scope → score × 1.5. Token in text only → score × 1.0.
Test: entry A with token in scope > entry B with same token only in text, same df.

### limit clamping
`if limit < 1: limit = 1` — tested with limit=0 and limit=-5, both clamp to exactly 1 result.

### _sanitize() injection chars
`\n`, `\r` → space. `<!--`, `-->` → empty string. Entry still appears — content sanitized, not dropped.

### Malformed trailer keys
`scan_trailers_memory` regex: `[A-Z][a-z]+(?:-[A-Z][a-z]+)*` — lowercase key (`decision:`) or missing colon → silently skipped.

### Empty corpus variants
1. Repo with non-memory commits only → returns "".
2. Repo with only Resolved-* tombstone commits (no Decision/Memo/Remember) → returns "".

## pre-task-recall.py Hook Edge Cases

`_normalize_agent(subagent_type)`: `rsplit(":", 1)[-1].strip().lower()`.
- `""` → `""` → not in whitelist → passthrough
- `"ULTRON"` → `"ultron"` → whitelisted
- `"unmassk-toolkit:Ultron"` → `"ultron"` → whitelisted
- `"  ultron  "` → `"ultron"` (strip) → whitelisted
- `"TOOLKIT:Bilbo"` → `"bilbo"` → NOT whitelisted

`updatedInput` = `dict(tool_input)` with only `prompt` overwritten. ALL other keys (model, description, max_turns, nested objects) survive verbatim.

Footer structure: `original_prompt + _FOOTER_HEADER + memory_block + _FOOTER_TAIL`.
- `_FOOTER_HEADER` starts with `"\n\n---\n"`, `_FOOTER_TAIL` = `"\n---"`.
- `updated_prompt.endswith("\n---")` → True always when injected.
- `updated_prompt.count("---") >= 2` → True always when injected.

stdin edge cases that must all fail-open (allow, exit 0, no traceback):
- `""` (empty), `"not json"`, `'["array"]'`, `"null"`, `'{{{invalid'`

### Long prompt — query truncation does not truncate the prompt (T3 gap closed)
`recall()` caps its internal BM25 query to `MAX_QUERY_LEN = 2000` chars when the prompt is very long, but the hook passes the FULL original prompt to `_build_prompt()`. The query truncation is a search guard only; it has no effect on `updatedInput.prompt`.

Test pattern:
- Seed a distinct token (e.g. `xqzlongprompttoken`) that appears within the first 2000 chars of the prompt → survives truncation → recall returns a hit → injection fires.
- Build prompt with `seed_token + " " + (padding_unit * 200)` → deterministic, ≈12 000 chars.
- Assert `updated_prompt.startswith(prompt)` (full original, not 2000-char slice).
- Assert `len(updated_prompt) > len(prompt)` (footer was appended, not a replacement).
- Assert `"MEMORIA DEL PROYECTO"` present and prompt ends with `"\n---"`.

## Windows git bare repo — clone default branch mismatch

`git init --bare` on Windows defaults HEAD to `master`. If the source repo uses `main`,
cloning the bare repo produces "warning: remote HEAD refers to nonexistent ref" and the
clone has no checked-out branch — causing `git push origin main` from the clone to fail
with "src refspec main does not match any".

Fix: always pass `-b main` to `git init --bare` when the source uses `main`.

Affected: any test that creates a bare remote and then clones from it to simulate a
second contributor pushing ahead (e.g. the "local behind remote" preflight scenario).

## WS connectedUsers Tracking
- Integration test server must track connStates + roomConns maps manually (same as production ws.ts)
- Use `publishToSelf: true` on test server for echo tests
- After disconnect: allow ~50ms yield before asserting user is gone from list
- room_state broadcast on connect: use `ws.publish(topic, ...)` (does not send to self with publishToSelf)
- connectedUsers timestamp: assert `!isNaN(new Date(ts).getTime())` — don't check exact value
