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

## release.py — Edge Cases (hardening pass, 2026-06-09)

### Semver numeric ordering
`_semver_tuple` converts to `(int, int, int)` — never string-compare versions.
Test: `1.10.0 > 1.9.0` (accepted), `1.9.0 < 1.10.0` (rejected), `2.0.0 > 1.99.99` (accepted).

### CHANGELOG format precision
After promotion: exactly `"\n\n"` between `## [Unreleased]` and `## [<ver>] - <date>`.
Assert `changelog[idx_unreleased + len("## [Unreleased]"):idx_new_ver] == "\n\n"`.
Previous content must appear verbatim under the new heading. Heading date = `date.today().isoformat()`.

### Missing / malformed files
CHANGELOG absent → `_read_file` → `_die` → exit 1, no traceback.
marketplace.json malformed JSON → `_load_json` → `_die` → exit 1, no traceback.
plugin.json absent → `_preflight` check → `_die` → exit 1.
Assert `"Traceback" not in (stdout + stderr)` for all three.

### --dry-run guarantees beyond "no file mutations"
Also assert: `git diff --cached --name-only` is empty (index untouched).
Also assert: local HEAD unchanged (no git object created).
Pre-flight still runs with --dry-run: invalid semver → exit != 0 even with --dry-run.

### bump-version.py retrocompat
Without `UNMASSK_REPO_ROOT`: resolves via `_FILE_ROOT` (`__file__`-relative). Test with `--list` from a tmp CWD that has no marketplace.json — must succeed and show real PLUGIN_NAME.
With `UNMASSK_REPO_ROOT`: uses override root. Test with fake marketplace in tmp_path — must show fake plugin, NOT real plugin.

## Security Regression Tests — stdin limit / injection / count validation

### BUG A — stdin size limit guards (4 hooks)
GUARD pattern (green now, stays green after fix):
- Build a >600 KB JSON payload (command/prompt padded with spaces).
- Run hook as subprocess via `run_cmd([sys.executable, HOOK_PATH], input_text=payload, timeout=20)`.
- Assert: `rc == 0`, stdout is parseable JSON, decision/permissionDecision matches expected value.
- Do NOT assert "only N bytes processed" — that is Ultron's assertion to add with the limit.
- Hooks affected: pre-merge-gate (decision=approve), pre-task-recall (allow), pre-memory-dedup-gate (allow), validate-memory-path (approve for in-bounds path).

### BUG B — CO_AUTHOR newline injection (bin/git-memory-commit.py)
RED pattern:
- Set `GIT_MEMORY_CO_AUTHOR = "Co-Authored-By: x\nResolved-Next: fake"` in env.
- Run git-memory-commit.py in a temp repo.
- Read commit body via `git log -1 --pretty=format:%B`.
- Assert `"Resolved-Next: fake" not in log_out`.
- Currently FAILS: the injected line appears verbatim in the commit message.
- run_cmd merges env with `{**os.environ, **env_override}` via conftest.run_cmd.

### BUG C — unvalidated count in git-memory-log.py
RED pattern:
- Run `git-memory-log.py -1` and `git-memory-log.py 0` → assert `rc != 0`.
- For -1: also seed a sentinel commit pushed deep; assert sentinel NOT in stdout (full history leaked).
- Currently FAILS: both exit 0 (-1 dumps everything, 0 shows "(no commits found)").
- Control: `git-memory-log.py 5` must exit 0 always (green before and after fix).
- Large count (99999): guard — assert `"Traceback" not in stderr` (must not crash Python).

## WS connectedUsers Tracking
- Integration test server must track connStates + roomConns maps manually (same as production ws.ts)
- Use `publishToSelf: true` on test server for echo tests
- After disconnect: allow ~50ms yield before asserting user is gone from list
- room_state broadcast on connect: use `ws.publish(topic, ...)` (does not send to self with publishToSelf)
- connectedUsers timestamp: assert `!isNaN(new Date(ts).getTime())` — don't check exact value

## "Not truncated" assertions — longest-contiguous-run technique

When a contract requires proving a long payload was copied verbatim (not cut
short) into some larger blob of text, don't hand-type the expected full
string and compare equality (fragile — any unrelated formatting change
breaks it) and don't just do a substring `in` check on the whole marker
(works, but doesn't measure length precisely at the boundary). Instead:
seed the payload with a repeated single character not otherwise common in
the output (e.g. `"Q" * 2200`, `"Z" * 2100` — pick a different char per
field so multiple long fields in the same blob can't be confused with each
other), then scan the output for the longest contiguous run of that
character and assert `run_length == len(payload)`. Natural text (headers,
words, punctuation) essentially never repeats one character thousands of
times in a row, so this is robust to any other content differences and
precisely catches partial truncation (run shorter than expected) without
requiring exact string reproduction.

Used in `unmassk-toolkit/tests/test_boot_output.py` (`_longest_char_run`)
for the session-start-boot.py stdout-truncation-fix contract: a synthetic
context() commit with 2000+ char subject and Next/Decision/Memo/Remember
trailers (each a distinct repeated character) must appear fully intact in
the new fixed-path boot-log file, never in truncated form.

## unmassk-toolkit runtime files — fixed-path convention

Any new generated/runtime file for the plugin belongs under
`.claude/.unmassk/` (see `git_helpers._GENERATED_JSONS` — the whole
directory is already gitignored via `ensure_gitignore()`, so a new file
placed there needs no new `.gitignore` entry). Confirmed for the
boot-log-latest.txt fixed-path file added in the stdout-truncation-fix
contract (session 2026-07-04).

## Importing a hyphenated bin/ script to read its own constants (not just call it)

When a test needs to build an input that exactly matches a script's own
internal format string (e.g. a commit subject assembled as
`f"{EMOJIS[type_]} {type_}({scope}): {message}"` in
`bin/git-memory-commit.py`), don't hardcode the emoji or prefix as a string
literal in the test — that duplicates a source of truth Ultron could change
independently. Instead use the same `importlib.util.spec_from_file_location`
pattern already documented in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
to import the hyphenated script as a module and read its real dict/constant
(e.g. `EMOJIS = _mod.EMOJIS`) directly, then use it to compute boundary-case
lengths. Confirmed safe: `git-memory-commit.py`'s module-level code (EMOJIS
dict, CO_AUTHOR resolution) has no side effects outside `if __name__ ==
"__main__": main()`, so exec_module() is safe to call from a test.
