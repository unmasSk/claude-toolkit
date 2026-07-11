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

### Date-at-import vs date-at-subprocess-invocation rollover (issue #62, fixed 2026-07-11)
A module-level `TODAY = date.today().isoformat()` computed once at test-file
import time WILL diverge from a subprocess-under-test that computes "today"
at its own invocation time, whenever the two moments straddle a (UTC)
midnight — confirmed twice (Yoda locally, CI Windows run 29131458089).
Never hardcode/precompute a date constant for comparison against a live
subprocess write. Fix pattern (no clock mocking needed — less machinery):
capture `date.today().isoformat()` immediately BEFORE and immediately AFTER
the subprocess call, then assert the value written by the subprocess is one
of those 2 candidates — stays strict (exact date, exact heading format), not
relaxed to a substring check. See `_extract_changelog_version_heading()` in
`test_release.py` for the shared regex-based extraction helper used across
all 4 affected tests. General rule: any test asserting a date/timestamp a
subprocess computes independently needs this before/after window, not a
constant computed anywhere earlier in the test process.

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

## Reproducing a write-failure (permissions/disk-full) fallback bug — chmod ordering matters

When a hook's "write a file, fall back on failure" logic has the bug that
the fallback-trigger variable is set to a truthy path *before* the
try/except confirms the write succeeded (so the except branch still leaves
a "we wrote it" signal even though nothing was written), reproduce with:
`os.chmod(parent_dir, 0o500)` (read+execute, no write) applied to the parent
directory **before** the target subdirectory exists — this makes
`os.makedirs(target_subdir, exist_ok=True)` itself raise `PermissionError`
(a subclass of `OSError`), which is what the hook's `except OSError: pass`
catches. Do NOT chmod a directory that already has the target subdirectory
created inside it (e.g. by an installer that already ran) — if the child
directory already exists and is itself still writable, a read-only parent
does not block writes into that already-existing child (Unix write
permission is per-directory, not inherited from ancestors). Always restore
permissions (`os.chmod(dir, 0o700)`) in a `try/finally` around the
subprocess call, before any `tmp_path` teardown tries to remove the tree.
Confirmed in `unmassk-toolkit/tests/test_boot_output.py`
(`TestBootLogWriteFailureFallback`, session 2026-07-04) — needed a
`_no_install` variant of the giant-commit repo builder specifically so
`.claude/.unmassk` did not pre-exist.

## Testing _sanitize_trailer_value() coverage — pick payloads that don't fight Python's own line-splitting

`scan_trailers_memory()` (lib/parsing.py) parses trailer bodies via
`body.splitlines()`, and Python's `str.splitlines()` treats `\r`, `\n`,
`\x0b`, `\x0c`, `\x1c-\x1e`, `\x85`, U+2028, U+2029 ALL as line boundaries —
the exact same set `_sanitize_trailer_value()` targets. Embedding a raw
`\r`/`\n`/U+2028 etc. *inside* a trailer value in a test commit message
therefore gets split by `splitlines()` **before** the sanitizer ever runs,
silently truncating the trailer's parsed value at the control char — the
test ends up not exercising the sanitizer at all, just proving trailer
parsing stops early (a different, uninteresting fact).

**Fix:** use a control sequence the sanitizer strips but that is NOT a line
boundary for `splitlines()` — HTML comment markers (`<!--`/`-->`) or the
`<memory-data>`/`</memory-data>` zone-delimiter tags are ideal: single-line,
survives commit-message round-tripping, and unambiguously proves whether
sanitization ran (`assert "<memory-data>" not in output` and the wrapped
text still present, proving markers were stripped not the content).
Confirmed in `test_boot_output.py` (SEC-HIGH-003 / SEC-MED-004 contract,
session 2026-07-05) for `extract_glossary()`'s missing sanitize call on
Decision/Memo/Remember, and for Next/Blocker's missing sanitize call in
`extract_memory()`.

## Symlink-write vulnerability test pattern (write-through-symlink)

To reproduce a hook that writes a fixed-path runtime file via plain
`open(path, "w")` with no symlink check (SEC-CRIT, e.g. boot-log-latest.txt
/ glossary-cache.json in session-start-boot.py): create a "victim" file
OUTSIDE the repo (in `tmp_path`, sibling to the repo dir, never inside it),
then at the exact runtime-file path the hook would normally write to,
guard with `if os.path.lexists(path): os.remove(path)` (use `lexists`, not
`exists` — `exists()` follows the link and can return False for a broken
symlink, wrongly skipping the cleanup) before `os.symlink(str(victim),
path)`. Run the hook as a normal subprocess, then assert the victim file's
content is UNCHANGED. Confirmed the vulnerability is real by running this
against the unmodified hook (session 2026-07-05): both boot-log-latest.txt
and glossary-cache.json got silently overwritten with hook-generated
content through the symlink — no exception raised, `open(path, "w")`
follows symlinks by default on POSIX.

## Symlink-write vulnerability test pattern, part 2 — bin/ scripts (manifest.json)

Same `lexists`+`remove`+`symlink` pattern as above also applies to
`bin/git-memory-install.py`'s `_create_manifest()` and
`bin/git-memory-upgrade.py`'s inline manifest-write block — both write
`.claude/.unmassk/manifest.json` via plain `open(path, "w")`, confirmed
vulnerable live (session 2026-07-05). Two gotchas specific to these scripts:
1. **install.py**: the symlink must be planted BEFORE running `--auto`, at a
   pre-created `.claude/.unmassk/manifest.json` path (in a repo with no prior
   install) — `_create_manifest()`'s `os.makedirs(unmassk_dir,
   exist_ok=True)` tolerates the dir already existing, so the symlink survives
   up to the `open()` call.
2. **upgrade.py**: the victim file's CONTENT matters, not just its existence.
   `apply_upgrade()` (which does the vulnerable write) is only reached if
   `read_installed_manifest()` first succeeds in parsing the manifest as JSON
   AND `check_upgrade_needed()` finds a real reason (e.g. version mismatch).
   If the victim file is plain text (not valid manifest JSON), the script
   exits early with "no installation to upgrade" — never reaching the write —
   and the test proves nothing about the symlink guard. Fix: write valid
   JSON to the victim file up front, e.g. `{"version": "1.0.0", ...}` (an
   old version), so the real upgrade flow organically reaches
   `apply_upgrade()` and its manifest-write block. Confirmed in
   `test_security_regression.py::TestBugDManifestSymlinkWrite`.

## Control-byte record-injection test pattern (git log `\x1e`/`\x1f` delimiters)

`lib/boot_memory.py`'s `extract_memory()`/`extract_glossary()` parse `git
log --pretty=format:...` output by `str.split()`-ing on the LITERAL control
bytes used as delimiters in the format string itself (`\x1e` = record
separator, `\x1f` = field separator). A commit BODY containing those same
raw bytes is treated as real stream delimiters, letting one real commit
forge an entire fake record (fabricated sha/scope/Decision text) — confirmed
live (session 2026-07-05): a body embedding `\x1e` + `\x1f`-separated fake
fields produced exactly `('(pwned-scope)', 'TOTALLY FORGED DECISION
INJECTED VIA CONTROL CHARS', False)` in `extract_memory()`'s decisions list.
Reproduce with a REAL git commit (`git_cmd(["commit", "--allow-empty", "-m",
subject + "\n\n" + malicious_body], repo)` — raw `\x1e`/`\x1f` python string
chars survive verbatim through argv → git commit → `git log` output, no
escaping needed) and assert via the direct `_extract_memory(repo)` /
`_extract_glossary(repo)` importlib-subprocess helpers (see
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md))
that no entry with the forged scope label appears.

**Important control/GUARD case — `\x1f` alone (no `\x1e`) is inert, not
exploitable, and this is NOT a gap to chase:** confirmed empirically that a
payload using ONLY `\x1f` (no `\x1e`) never forges an entry, in either
function, for two independent structural reasons: (1) `str.split(sep,
maxsplit=N)` caps the number of fields regardless of how many extra `\x1f`
occurrences exist in the body — the overflow just gets absorbed into the
last field (harmlessly corrupting the timestamp/body, never creating a new
logical record); (2) `\x1f` (0x1F) is NOT one of the boundary characters
`str.splitlines()` uses (`\n \r \v \f \x1c \x1d \x1e \x85 U+2028 U+2029` —
note `\x1c-\x1e` are boundaries but `\x1f` is one off and is NOT), so a
forged `"Decision: ..."` line embedded via `\x1f` alone can never become the
start of a "line" for `scan_trailers_memory()`'s regex, which requires `^`
at line-start. Write this as an explicit `[GUARD]` test (must stay green
before AND after the fix) alongside the `\x1e` RED tests, rather than
skipping it — it proves the fix is a genuine record-boundary fix, not a
patch of the exact PoC bytes. Do NOT expect this GUARD test to be RED before
Ultron's fix; it already passes today by construction. Confirmed in
`test_boot_output.py::TestControlByteRecordInjection`.

## Git branch name length limits — per-component ceiling from the `.lock` file, not NAME_MAX

A single-path-component branch name (no `/`) fails `git checkout -b` once
it exceeds roughly 250 bytes on APFS (NAME_MAX=255), because git briefly
creates a `<name>.lock` file in `.git/refs/heads/` during the ref update —
the lock suffix (`.lock`, 5 bytes) counts against the same 255-byte
filesystem limit, so the real usable ceiling for a single segment is
`NAME_MAX - 5`, not `NAME_MAX`. To construct a long branch name well beyond
what "usually short" code assumes (for testing byte-budget assumptions),
use a two-segment name with a `/` separator, e.g. `("a"*245) + "/" +
("b"*245)` — each segment stays under the per-component ceiling so
`checkout -b` succeeds, while the total branch name (~491 chars here) is
long enough to expose any code path that embeds the branch name into a
size-bounded string without capping it. Confirmed in
`test_boot_output.py::TestBannerByteBudgetWithLongBranchName` (session
2026-07-04): this pushed a banner from a baseline ~666 bytes to ~1207 bytes,
comfortably proving the >1000-byte budget isn't guaranteed by construction.

## Reproducing sys.modules stub contamination across stably-named lib/ modules

When a test file stubs `sys.modules["git_helpers"]`/`["parsing"]`/`["version"]`
before `exec_module()`-ing a hyphenated hook (the pattern in
`test_migrate_statusline.py::_load_migrate_fn`) and restores them in a
`finally`, that restore does NOT protect any *other* stably-named module
(e.g. `lib/boot_memory.py`, `lib/boot_render.py`, `lib/boot_migrations.py`)
that does a MODULE-LEVEL `from git_helpers import run_git` and gets
first-ever-imported while the stub is installed — Python caches that module
in `sys.modules['boot_memory']` with `run_git` bound to the stub's function
object forever; rebinding `sys.modules['git_helpers']` afterwards doesn't
touch names already bound in `boot_memory`'s own namespace.

Reproduce by running the *existing* stub-and-restore helper (don't reinvent
it) in a **fresh subprocess** — process isolation matters here because the
bug only bites on a module's first-ever import in a process, so the result
must not depend on whether some other test file in the same pytest session
already did a real `import boot_memory` first. Pattern: build a `python3 -c`
snippet that (1) adds `LIB_DIR` and the test file's own directory to
`sys.path`, (2) loads the test file itself via
`importlib.util.spec_from_file_location` under a throwaway name (so its own
`_load_migrate_fn` helper is reachable), (3) calls that helper and the
returned migration function (triggers the contamination), (4) `os.chdir()`
into a real temp repo, (5) does a plain `import boot_memory` (already
cached from step 3) and calls a REAL function that depends on `run_git`
(e.g. `extract_memory()`, `boot_render.get_timeline()`,
`boot_migrations._migrate_untrack_generated_jsons()`).

**Assert on BEHAVIOR, never on `module.run_git is real_run_git` identity.**
The eventual fix (deferring the import into each function body, mirroring
the `parsing` pattern documented at the top of `boot_memory.py`) may remove
`run_git` as a module-level attribute entirely rather than merely rebind
it — an identity-based assertion would then error (AttributeError) instead
of transitioning to green. Test the observable output instead: seed a real
commit with a unique marker (Decision trailer text, commit subject, or a
tracked file matching `git_helpers._GENERATED_JSONS`), then assert the
real function reports that marker. Contaminated (stub `run_git` always
returns `(1, "")`) → the function sees "no commits"/"not tracked" and the
marker never appears; real `run_git` → marker appears (or, for
`_migrate_untrack_generated_jsons()`, the previously-tracked fixture file
becomes untracked — check this ONE assertion back in the *outer*,
uncontaminated test process via a plain `git ls-files`, not inside the
probe subprocess). Confirmed in
`test_migrate_statusline.py::TestSysModulesContaminationRegression`
(session 2026-07-05) — RED against the current (unfixed) module-level
imports, 0 regressions in the file's 5 pre-existing tests.

## Manifest.json symlink-read + version-field sanitization (check_version_mismatch)

`lib/boot_render.py:check_version_mismatch()` reads
`.claude/.unmassk/manifest.json` with plain `os.path.isfile()` + `open()`
(no `open_no_follow_symlink()` guard, unlike `boot_memory.py`'s
`_read_glossary_cache()`) AND embeds the manifest's `"version"` field
unsanitized into the STATUS section's upgrade-suggestion line. Two
independent, separately-testable bugs on the same function:

1. **Symlink read guard**: call `check_version_mismatch()` directly via a
   throwaway subprocess (`importlib.util.spec_from_file_location` on
   `lib/boot_render.py` under a synthetic name, `os.chdir()` into the repo,
   no stub involved — this is a clean isolated call, not the contamination
   pattern above). Plant a symlink at the manifest path
   (`os.path.lexists()` + `os.remove()` + `os.symlink()`, see
   `test_security_regression.py::_plant_symlink`) pointing at a victim JSON
   file with a distinctive `"version"` value (e.g.
   `"0.0.1-SYMLINK-VICTIM"`). Assert the return value is `None` OR does not
   contain the victim's version — i.e. a symlink must be treated exactly
   like "no manifest present," never followed. RED today: the function
   follows the symlink and returns a warning string embedding the victim's
   version.
2. **Content sanitization**: with a REAL (non-symlinked) manifest whose
   `"version"` field is `"<!--evil--><memory-data>PWNED</memory-data>"`,
   run a full boot and check the STATUS section of the boot-log file for
   the raw markers — same `<!--`/`-->`/`<memory-data>` payload convention
   as the trailer-sanitization tests above, and same reasoning: this is the
   5th of 5 sites (SEC-CRIT-NEW-04) where a value skips
   `sanitize_trailer_value()` that Decision/Memo/Remember already receive.

For `bin/git-memory-upgrade.py:read_installed_manifest()`'s equivalent
symlink-read bug, don't write a new direct-call helper — drive it through
the real CLI (`git-memory-upgrade.py --auto --check --json`, matching the
existing `UPGRADE`/`run_script` pattern already used for BUG D's
manifest-*write* symlink tests in the same file) and assert on the
JSON `status`/`installed_version` fields: the vulnerable path reports
`"status": "update_available"` with the victim's version; the fixed path
must report `"status": "error"` (exit 1, "No installation to upgrade. Use:
git memory install") — proving the symlink was treated as a missing
manifest, not silently followed. Confirmed in
`test_security_regression.py::TestBugECheckVersionMismatchManifestSymlinkRead`
/ `TestBugEUpgradeReadInstalledManifestSymlinkRead` (session 2026-07-05).

## Path-traversal PoC via a value embedded MID-STRING in a filename (not a standalone path component) — needs a pre-created placeholder dir

When a vulnerable filename is built as `f"prefix{attacker_value}-suffix.json"`
(the attacker value is glued onto a literal prefix, not passed to
`os.path.join()` as its own component), a naive PoC using
`attacker_value = "../../../etc/passwd"` will NOT actually escape the
intended directory and will NOT prove the bug — it just raises
`FileNotFoundError`. Reason: real `open()`/`os.open()` path resolution is
strict left-to-right component-by-component; the FIRST path segment is
always `prefix` + (everything in `attacker_value` up to its first `/`), and
that combined name (e.g. `"manifest-v.."`) is a literal, ordinary filename —
NOT the special `".."` component — so the kernel needs it to exist as a real
directory before it can traverse through it. It won't exist, so the open
fails with ENOENT before any traversal happens. Confirmed empirically (both
manually with a bare Python repro and via the real CLI) for
`bin/git-memory-upgrade.py:create_backup()`'s
`f"manifest-v{version}-{timestamp}.json"`.

**To make the PoC real:** pre-create that placeholder directory yourself in
the test (`os.makedirs(os.path.join(backup_dir, "manifest-vX"))` for
`version = "X/../../../../PWNED-MARKER"`) — this mirrors a realistic
attacker who controls the *whole repo* (same threat model as the existing
symlink tests: they can commit both the malicious manifest.json AND an
arbitrary placeholder directory in the same malicious commit). With the
placeholder present, the traversal resolves for real and the write lands
outside the intended directory — confirmed landing exactly at the
grandparent-of-grandparent of the backup dir (repo/.claude/backups → up 1 to
cancel the placeholder segment + up 3 more to clear repo/.claude/backups →
lands at the tmp_path level, sibling of the repo). Assert on the *absence*
of any file matching the marker anywhere outside the intended dir (e.g.
`os.listdir(str(tmp_path))` for the marker substring), not on an exact
expected path — the escape depth is fragile to get exactly right and the
important invariant is "never escapes," not "escapes to this exact spot."
Confirmed in
`test_security_regression.py::TestBugGUpgradeBackupPathTraversal` (session
2026-07-05, SEC-HIGH-NEW-07).

## "Make the PoC real" also applies to conditional writes gated on content match, not just path traversal

Same lesson as the path-traversal note below, different shape: when a
vulnerable write only happens if some earlier parse/match against the
victim's content succeeds (e.g. `remove_claude_md_block()` in
`bin/git-memory-uninstall.py` only calls `open(claude_md, "w")` if at least
one of the 5 managed-block regexes actually matched — `removed_any` stays
False and the function returns early otherwise), a victim file containing
arbitrary/unrelated text (e.g. `"SENSITIVE ORIGINAL CONTENT"`) never
reaches the write path at all — the test passes GREEN today, but for the
wrong reason (proves nothing about the symlink guard, same trap as a naive
path-traversal PoC). Confirmed empirically in session 2026-07-05: an initial
version of this test used plain sentinel text as the victim's content and
passed even against the unguarded code, until the victim was swapped for a
REAL, valid CLAUDE.md (harvested by running the real installer once in a
throwaway/same repo and reading back its output) that genuinely contains a
BEGIN/END managed block — only then did `removed_any` become True, the
write path execute, and the test go RED as expected. Rule: whenever a write
is gated behind "did parsing/matching the current content find something,"
build the victim content from the real producer of that shape (a genuine
install, a real config schema) rather than typing a plausible-looking
string by hand — same root cause as fabricated-fixture risk (unmassk-standards
§34), just appearing inside a security PoC instead of a round-trip test.

## needs_upgrade() Check 1 must be neutralized before any test targets Check 2 (manifest read)

`hooks/user-prompt-memory-check.py::needs_upgrade()` ORs two independent
triggers: Check 1 (`"python3 bin/" in block or "Context Checkpoint Commits"
not in block`, stale CLAUDE.md markers) and Check 2 (manifest.version vs
PLUGIN_VERSION, read via `open_no_follow_symlink()`). A freshly installed
repo's CLAUDE.md managed block never contains the literal string "Context
Checkpoint Commits" (that text lives in the full skill payload, not the
minimal installed snippet) — so Check 1 fires `True` on every real install,
short-circuiting `or` before Check 2 (and its manifest read) is ever
reached. Any test that plants a symlink or a version mismatch at
`manifest.json` to prove something about Check 2 will pass GREEN even
against the unguarded code if Check 1 alone already made `needs_upgrade()`
return `True` for the wrong reason — same "PoC not real" trap as the
path-traversal/conditional-write notes below.

**Fix:** call `neutralize_needs_upgrade_check1(repo)` (in `conftest.py`,
shared helper — extracted from `test_needs_upgrade_semver.py`'s
`make_semver_test_repo()`) right after installing, before planting any
symlink/version fixture. It patches the managed block in-place: strips
`"python3 bin/"` and appends `"Context Checkpoint Commits"` if absent, so
Check 1 is definitively `False` and only Check 2 can drive the result.
Confirmed this was the actual bug in
`test_security_regression.py::TestBugMNeedsUpgradeManifestSymlinkRead` — the
symlink guard fix (Ultron, `open_no_follow_symlink()` on the manifest read)
was correct; the test just never reached it before this fix (session
2026-07-05).

## Barrido (full sweep) technique: grep for the vulnerable call shape across sibling files, don't trust the named sites as exhaustive

When Argus names N confirmed sites of a bug class and asks for a full sweep
of siblings, `grep -n "manifest.json\|manifest_path\|open(manifest"
bin/git-memory-*.py` (or the equivalent shape for the specific vulnerable
pattern) across every file in the same directory, then manually trace each
hit to confirm it's a genuine instance (read-only vs write, whether the
value ever reaches a print/filename/comparison). This found two additional
real sites Argus's SEC-MED-NEW-08/SEC-LOW-NEW-05 list didn't name:
`bin/git-memory-repair.py:diagnose()` (silently trusts a symlinked manifest
as valid — zero issues reported, so `git memory repair` never fixes it) and
`bin/git-memory-bootstrap.py:check_existing_memory()` (both the symlink-read
gap AND an unsanitized version-print, the latter reaching terminal via
`classify_findings()`'s finding `"text"` field → `format_human()`). Always
empirically verify a sweep-discovered site with a live repro (build a real
tmp repo, run the actual script, inspect real output) before writing the
test — reasoning about the code alone led to an initially-wrong assumption
here (see the path-traversal note above) that only got caught by testing.
Confirmed in `test_security_regression.py::TestBugIRepairDiagnoseTrustsSymlinkedManifest`
/ `TestBugJBootstrapManifestSymlinkAndVersionLeak` (session 2026-07-05).

## BUG Y class (`.claude` itself a symlinked parent) has more sites than the
## chokepoint's first 3 verified scenarios — sweep by call shape, not by name

`lib/git_helpers.py`'s `verify_path_within_project()`/`ensure_runtime_dir()`
chokepoint (added for BUG Y, confirmed correct for 3 scenarios in
`TestBugYClaudeDirSymlinkBypassesAllGuards`) does NOT automatically protect
every `.claude`-touching call site — it only helps where a site is actually
routed through it. Argus/Cerberus found 5 more unmigrated sites in the same
audit round (session 2026-07-05), tests written test-first as
`TestBugZ...` / `TestBugAA...` / `TestBugAB...` / `TestBugAC...` /
`TestBugAD...` (letters exhausted at Y, continued AA/AB/... not "Z2" etc.):

1. **`_cleanup_old_install()` (install.py) / `remove_old_install_files()`
   (uninstall.py)** — most severe, DESTRUCTIVE: both do
   `shutil.rmtree(target/.claude/hooks_or_skills)` with zero guard. If
   `.claude` symlinks to an external dir whose `hooks/`/`skills/` subdir
   contains only symlinks (real old-install shape — `all_symlinks` check
   passes), the external directory gets destroyed outright. PoC helper
   `_make_symlink_farm(dir_path, subdir_name)` builds that exact shape
   (dangling symlink targets are fine, only `os.path.islink()` is checked).
   `install.py` needs `has_old_install=True` first — trivially triggered by
   dropping any one `OLD_HOOK_FILES` path (e.g. `hooks/session-start-boot.py`)
   at the real project root (unrelated to the `.claude` symlink);
   `uninstall.py` calls its version unconditionally, no gating needed.
2. **`_write_glossary_cache()`** (`lib/boot_memory.py`) — unguarded
   `os.makedirs(os.path.dirname(path), exist_ok=True)`. Reachable via the
   real `session-start-boot.py` subprocess (`extract_glossary_cached()` runs
   on every boot) — same driving pattern as `TestBugY`'s boot-hook test.
3. **`.session-booted` flag's parent dir** (`user-prompt-memory-check.py`)
   — `open_no_follow_symlink()` on the flag file itself only guards the
   FINAL component (fixed for BUG L); the `os.makedirs(runtime_dir,
   exist_ok=True)` one line above it is unguarded. To reach this branch the
   hook needs `needs_install(root) == False` first (checks CLAUDE.md content
   only, unrelated to the manifest) — run `INSTALL --auto` once before
   planting the symlink: `update_claude_md` runs before `create_manifest` in
   `apply_plan()`, so CLAUDE.md's managed block gets written even though
   `create_manifest` is correctly rejected by the BUG Y guard when `.claude`
   is already a symlink at install time.
4. **`_migrate_runtime_to_unmassk()`** — duplicated near-identically in
   `lib/boot_migrations.py` (runs every boot via `run_preboot_migrations()`)
   and `bin/git-memory-upgrade.py` (runs inside `apply_upgrade()`). Both
   have zero `git_helpers` import, so no sys.modules stub-contamination risk
   — safe to call directly via the `spec_from_file_location` + `exec_module`
   probe pattern with the real `project_root`, no subprocess-chain needed.
   Trigger condition: a legacy file (`git-memory-manifest.json`,
   `.glossary-cache.json`, `.session-booted`, or `git-memory-scopes.json`)
   present at wherever `.claude` resolves to.
5. **doctor.py's healthcheck-timestamp rewrite** (lowest severity, optional)
   — `open_no_follow_symlink()` already guards the FINAL manifest.json
   component (BUG F fix), but a REAL (non-symlink) manifest.json sitting
   inside an externally-resolved `.claude` still gets its
   `last_healthcheck_at` silently rewritten — O_NOFOLLOW never objects
   because the final component genuinely isn't a symlink, only an
   intermediate directory is. Proves the parent-symlink gap is orthogonal to
   (and not fixed by) every prior final-component guard.

**Lesson for any future `.claude`-parent-symlink sweep**: grep for
`os.makedirs(` and `shutil.rmtree(` (not just `open(`) across `bin/`,
`hooks/`, `lib/` — the destructive/creating operations are the ones that
follow a symlinked intermediate directory silently; `open_no_follow_symlink()`
call sites are already covered by the BUG D-X sweep and are a red herring for
this specific bug class unless the *directory containing* the opened file is
itself unguarded. All 7 tests written test-first (contract before Ultron's
fix), confirmed RED against the live, unmodified code and 0 regressions in
the file's other 56 tests. See
`test_security_regression.py::TestBugZCleanupOldInstallDestroysExternalClaudeDir`
onward.

## BUG Y class, round 9 (session 2026-07-05) — `os.remove()`/`os.unlink()` sites also need `verify_path_within_project()`, not just `open()`/`makedirs()`/`rmtree()`

Two more independent auditors (Cerberus + Argus) each found the same 3 sites
in the same round, extending the round-8 lesson above: the "grep for
`os.makedirs(`/`shutil.rmtree(`" sweep still misses plain `os.unlink()`/
`os.remove()` delete call sites, which are just as vulnerable to a
symlinked-parent `.claude` as the create/destroy ops already found. Written
test-first as `TestBugAE`/`TestBugAF`/`TestBugAG` in
`test_security_regression.py` (continuing straight after `AD` — do not
restart the letter sequence per round):

1. **`remove_manifest()`** (`bin/git-memory-uninstall.py:152-155`) —
   `safe_remove()` → `os.unlink()`, zero `verify_path_within_project()`, while
   its sibling `remove_old_install_files()` in the *same file* already has
   the guard (added in the round-8 sweep, line ~211). Confirmed RED: the real
   external manifest.json is deleted outright when `.claude` symlinks to a
   directory that already contains one. Direct-call test (no CLI
   confirmation flow needed) via the same `importlib.util.spec_from_file_location`
   + `exec_module` pattern as `_call_migrate_runtime_to_unmassk_upgrade`.

2. **`check_manifest()`** (`bin/git-memory-doctor.py:278-296`) — already uses
   `open_no_follow_symlink()` (fixed for BUG F), which only protects the
   FINAL `manifest.json` component. When `.claude` itself is the symlinked
   parent and the external dir already has a REAL (non-symlink)
   `manifest.json`, `open_no_follow_symlink()` has nothing to object to — the
   read succeeds and the external "version" field leaks verbatim into
   `git memory doctor --json`'s "checks" array. This is a **confidentiality**
   finding distinct from `TestBugAD`'s write-back-timestamp finding on the
   *same* underlying gap — AD proves the file's bytes are unmodified, AF
   proves its content must also never reach stdout. Both are needed; neither
   subsumes the other.

3. **`run_preboot_migrations()`** (`hooks/session-start-boot.py:196-202`) —
   `os.remove(booted_flag)` with **zero guard of any kind** (not even
   `open_no_follow_symlink()`), unlike every other site in this bug family.
   Runs on **every SessionStart**, unconditionally, no user/agent action
   required. Note this is NOT the "final component is a symlink" shape
   (`os.remove()`'s own unlink-not-follow-target semantics already protect
   against that for free, no fix needed there) — it is the BUG Y
   parent-symlink shape: the REAL file sits behind a symlinked `.claude`, and
   `os.remove()` deletes it because path *resolution* (not the final
   unlink call) walks through the symlinked intermediate directory. Tested
   by calling `run_preboot_migrations(project_root)` directly (isolates step
   0 from the already-guarded later migration steps in the same function —
   `_migrate_runtime_to_unmassk()` already has `verify_path_within_project()`
   per the BUG AC fix, confirmed by reading `lib/boot_migrations.py` before
   writing this test, so the full-boot-subprocess pattern used by
   `TestBugYClaudeDirSymlinkBypassesAllGuards` would have been redundant
   noise here).

All 3 confirmed RED against live, unmodified code; 9 pre-existing
`test_release.py` failures (unrelated, documented above) plus 797 passed —
0 regressions from this file's other 63 pre-existing tests.

**Findings reported but NOT turned into new tests, with rationale (Cerberus
structural findings, not new security sites):**
- `plan["skipped"]` in `bin/git-memory-install.py` is initialized (line 234)
  and read in a dead `for desc in plan["skipped"]:` loop (line ~546) but
  never `.append()`-ed anywhere in the file (confirmed via grep) — pure
  dead-code cleanup, not a test gap. Ultron can safely delete the loop, or
  decide the list should actually be populated somewhere; either way no test
  is owed here since there is no behavior to pin.
## os.path.islink() calls os.lstat() internally on Windows — spy on the right layer

When spying on `os.lstat`/`os.fstat` to prove `_open_no_follow_symlink_windows()`
(`lib/git_helpers.py`, twin `lib/_symlink_safe_open.py`) skips the identity
check for a brand-new path (no `os.path.exists()` match, the F5/O_CREAT
case), a naive spy that patches `os.lstat` and then calls the real
`os.path.islink(path)` will see ONE spurious call — confirmed empirically
(Windows, Python 3.11): `ntpath.islink()`'s own implementation calls
`os.lstat()` under the hood. A strict `assert lstat_calls == []` fails for
the wrong reason (it's islink's internal plumbing, not the guard's own
explicit `if os.path.exists(path): prior_identity = os.lstat(path)` line).
Fix: `monkeypatch.setattr(os.path, "islink", lambda p: False)` FIRST, so the
spy only ever observes the guard's own call. A loose truthy check
(`assert lstat_calls`, no exact-emptiness assertion) doesn't need this fix
since one extra call doesn't change truthiness — only exact-count/exact-empty
assertions are exposed to this gotcha. Confirmed in
`test_crossplatform_symlink_guard_hardening.py::TestNewFileOCreatSkipsIdentityCheck`
(hardening pass, session 2026-07-06).

## Moriarty T1 theater fix: in-process round-trip tests of `run_git()`'s `encoding="utf-8"` kwarg are false-green under ambient PYTHONUTF8=1 — force PYTHONUTF8=0 in a child process

`test_run_git_round_trips_utf8_accents_and_emoji_through_real_git`
(`test_crossplatform_symlink_guard_hardening.py`) originally ran `git
commit` + `git_helpers.run_git(["log", ...])` in-process and compared to
the literal `subject` used to create the commit — a genuine round-trip
(§34-compliant, no fixture), but Moriarty proved it doesn't actually pin
`run_git()`'s explicit `encoding="utf-8"` kwarg: this dev machine's ambient
`PYTHONUTF8=1` silently forces UTF-8 decoding process-wide, so the test
stayed green even with the kwarg deleted from `subprocess.run(...)`. Same
root cause already documented for `open_no_follow_symlink()` in
`TestEncodingIndependentOfPythonUtf8Env`
(`test_crossplatform_symlink_guard.py:422`) — same fix applies to
`run_git()`.

**Fix:** run the real round-trip (real `git commit`, real `git log` via
`run_git()`) inside a **child subprocess** with `PYTHONUTF8=0` forced and
`PYTHONLEGACYWINDOWSFSENCODING` popped from env, so a missing `encoding=`
kwarg falls back to the locale's ANSI codepage (cp1252) instead of being
masked. The child imports the REAL `lib/git_helpers.py` (via
`sys.path.insert(0, LIB_DIR)`), calls `run_git()`, and prints the result as
`json.dumps({...})` with the default `ensure_ascii=True` — this keeps the
parent↔child pipe pure ASCII (all non-ASCII \uXXXX-escaped) so a mangled
*console* codepage in the test harness itself can never masquerade as a
mangled *file*-decode round-trip. Keep the accented/emoji `subject` OUT of
the child's `-c` argv entirely (only ASCII paths like `tmp_repo`/`LIB_DIR`
are embedded) — it stays in the parent process and is only compared
against the child's decoded-back JSON at the end.

**Verified as Moriarty would**: built a scratch copy of `git_helpers.py`
with the `encoding="utf-8"` kwarg deleted, pointed a throwaway duplicate
script's child subprocess at that scratch copy — confirmed RED with the
exact mojibake Moriarty predicted
(`'ðŸ”§ ... corazÃ³n, seÃ±al, aÃ±o ...'`). With the real, unmodified
`lib/git_helpers.py` (kwarg present): GREEN. Scratch copy discarded after
verification, never committed.

## FIXED (was DISCOVERED-not-fixed-by-Dante): fd leak in `_open_no_follow_symlink_windows()` when `os.fstat(fd)`/`os.ftruncate()` raises — plus a second finding, deferred-truncate-before-check

`lib/git_helpers.py:200-218` / `lib/_symlink_safe_open.py:80-98` (identical
in both twins). Originally reported as two separate gaps found during the
2026-07-06 hardening pass, both now fixed by Ultron in the same commit:

1. **fd leak on os.fstat() raising** — `os.close(fd)` used to be reachable
   only from inside the `if (dev,ino) mismatch` branch, no try/finally
   around `post_identity = os.fstat(fd)` itself. Originally pinned as
   `@pytest.mark.xfail(strict=True, ...)` in
   `TestFstatFailureFdLeak::test_fstat_raises_still_closes_the_fd` (Dante's
   report, not fix — Absolute Prohibition #4).
2. **Destructive truncate-before-check (Argus SEC-MED-NEW-03)** —
   `os.ftruncate(fd, 0)` used to run unconditionally at open() time for
   mode="w", BEFORE the lstat/fstat identity check could reject a TOCTOU
   race — so a rejected race still destroyed the victim's real content even
   though the caller correctly saw an OSError.

**Fix (both twins)**: `os.ftruncate(fd, 0)` is now called only AFTER the
identity comparison passes, and both the comparison and the ftruncate call
are wrapped in one `try: ... except BaseException: os.close(fd); raise`
block — any post-open failure (fstat raising, ftruncate raising, or a
detected mismatch) now closes the fd before propagating, and truncation
never happens before the identity check clears.

**Test changes (session 2026-07-06, hardening-pass update after Ultron's
fix)**: removed the `xfail(strict=True)` marker from
`TestFstatFailureFdLeak` (now a normal green regression pin — the fix made
it XPASS(strict), which is a hard FAILED, forcing exactly this update).
Added `TestDeferredTruncateOnIdentityMismatch` (new class, same file):
mocks `os.lstat`/`os.fstat` to diverge (dev,ino), spies on `os.ftruncate` to
assert zero calls, and asserts the target file's real on-disk content
survives untouched — proving the destructive truncate never fires when the
TOCTOU check is about to reject the open. Both new/updated tests
parametrized across `TWIN_FUNCS`. 45 passed, 4 skipped (pre-existing
POSIX-real-symlink skips), 0 failed, 0 xpass in
`test_crossplatform_symlink_guard.py` + `test_crossplatform_symlink_guard_hardening.py`.

- `lib/git_helpers.py:verify_path_within_project()` (lines ~56-60) doesn't
  call `os.path.normcase()` before the prefix comparison, unlike
  `hooks/validate-memory-path.py` (line 108-109) which does. Real gap
  (Windows case-insensitive-filesystem bypass), but a dedicated test on this
  macOS/Linux-only test suite would have to mock `os.path.normcase`/
  `sys.platform` to fake case-insensitivity — that only proves the mock
  behaves as configured, not real OS behavior (see this project's own "Mock
  Verification" rule against tests whose only assertion is that a mock
  returned what you told it to). Recommendation: Ultron applies the
  `normcase()` fix for consistency with `validate-memory-path.py`, no
  dedicated test — mirrors how the Windows bare-repo branch-mismatch gap
  earlier in this file was handled (documented, not test-guarded, since this
  suite doesn't run on Windows).

## Test-input text that echoes back into output can make a keyword assertion pass vacuously — audit marker names against every regex they're near

When a test writes a commit message / file / marker string that a script
under test PRINTS BACK VERBATIM (confirmation lines like
`bin/git-memory-commit.py`'s `_print_commit_result()` echo the commit
`message` argument), and the same test then does `re.search(r"<keyword>",
combined_output)` to prove some NEW feature added that keyword to the
output, the assertion can pass today — before the feature exists — purely
because the test's OWN input text happened to contain the keyword. Caught
live in `test_boot_freshness.py`'s write-path warn-only test (Task 1 test
8): the commit message was `"proceed despite being behind"`, and the
regex checking for a new "behind" warning matched the echoed message
itself, making a RED-should-be test pass GREEN for the wrong reason before
any warning logic existed. Same root cause hit a second time in the same
file: `INCIDENT_NEXT_MARKER = "INCIDENT-REMOTE-NEXT-..."` and
`b_remote_marker = "B-REMOTE-NEXT-MARKER"` both contained the substring
"REMOTE", which a `re.search(r"remot", line, re.IGNORECASE)` check (meant
to prove a NEW remote-provenance LABEL was added next to the marker) would
match on the marker's own name alone, regardless of whether the label
existed.

**Fix / prevention**: before writing an assertion `re.search(r"<kw>",
text)`, grep every string LITERAL the test itself writes into that same
commit/file/env (commit messages, trailer values, marker constants,
filenames) for that keyword (case-insensitive) and rename any collision.
Prefer marker names built from a scope name + a short random-looking
suffix (e.g. `"B-NEXT-MARKER-77c2"`) that avoids every word the test's own
regexes search for. This is a variant of the codebase's existing "make the
PoC real" / anti-fixture-fabrication family of gotchas — the bug isn't in
what's asserted, it's in the test's own input data secretly satisfying the
assertion. Always run the new test once against UNMODIFIED (pre-fix)
production code and confirm every physical test method is genuinely RED,
not just the file as a whole — running with `-x` can hide a vacuously
green test sitting after a real failure.

## get_ahead_behind() — non-numeric rev-list tokens raise instead of failing open (BUG, reported not fixed)

`lib/boot_git_checks.py:get_ahead_behind()` parses `git rev-list
--left-right --count HEAD...<upstream>` output by splitting on whitespace
and doing `int(parts[0]), int(parts[1])` with NO try/except, even though
the very next line already has a safe `return 0, 0, upstream_ref` fallback
for the "wrong token COUNT" case (e.g. 1 or 3 tokens). A response with
exactly 2 tokens that aren't valid integers (confirmed via monkeypatching
`git_helpers.run_git` to return `(0, "abc def")` for that one call, real
git untouched otherwise) raises an uncaught `ValueError` instead of hitting
that same fallback. Since this function is called from
`render_branch_section()` and (issue #49) from `session-start-boot.py`'s
`main()` with no enclosing try/except at either site, this is a fail-open
violation that can crash the entire boot. Pinned as `xfail(strict=True)` in
`test_boot_freshness_hardening.py::TestGetAheadBehind::test_non_numeric_
rev_list_output_should_fail_open_but_raises` — will flip to a hard failure
the moment Ultron wraps the `int()` conversion in the same pattern, forcing
a test update (remove the marker) rather than silently staying green.

## Windows fake-`git` process-tree kill test — CreateProcess ignores Popen's `env=` for executable SEARCH; must mutate the real process PATH instead

Closing the two Windows-only gaps in `test_boot_freshness_regression.py`
(`_win32_kill_tree`/taskkill, and `_ASKPASS_FAILFAST == "cmd /c exit 1"`)
that were previously documented as "no Windows machine available" —
session 2026-07-07, first real Windows box for this suite.

**Platform quirk confirmed empirically (not in any doc, easy to get
wrong)**: on POSIX, `execvpe`/`subprocess.Popen(["cmd"], env={"PATH":
fake_dir, ...})` resolves the executable using the `env` dict passed in —
this is exactly what the existing POSIX fake-git-on-PATH pattern relies
on. On Windows, `CreateProcess` (which is what `Popen(["git"]+args,
shell=False)` compiles down to when no `executable=` is given) resolves
the bare command name using the CALLING process's OWN live PATH
environment block — the `env=` kwarg only populates the CHILD's
environment AFTER the executable has already been found and started. So
`git_helpers.run_git(["fetch"], env={"PATH": fake_bin + ...})` is a
silent no-op for redirecting which "git" runs on Windows: the real
system git still executes, and a naive test assuming POSIX semantics
gets a fast, wrong-looking pass/fail (confirmed: got `rc=128` "unable to
access... getaddrinfo() thread failed to start" from the REAL git,
looking like a plausible network failure, not "wrong git ran").

**Fix for Windows tests that need a fake `git` on PATH**: use
`monkeypatch.setenv("PATH", fake_bin + os.pathsep + os.environ.get("PATH",
""))` (or plain `os.environ["PATH"] = ...` with manual restore) on the
TEST process itself before calling the function under test — this
mutates the real live env block `CreateProcess`'s search consults. The
`env=` kwarg passed to `run_git`/`Popen` is still useful (and still
production-faithful) for populating the CHILD's own environment (e.g.
`PYTHONPATH` below), just not for the executable search itself.

**Second problem, specific to needing a fake "git" that does real work
on Windows**: `CreateProcess`'s implicit search only auto-appends `.exe`
— it does NOT consider `.bat`/`.cmd` the way `cmd.exe`'s own PATHEXT
-driven resolution does. A `git.bat` dropped on the prepended PATH dir is
silently skipped in favor of the real `git.exe` found later in the
search — confirmed by direct experiment (a `git.bat` printing a sentinel
and exiting 7 was never invoked; real git ran instead). So the fake must
be a genuine PE executable, not a script with a shebang-like batch file.

**Working technique**: copy a REAL python interpreter binary to
`fake_dir/git.exe` — but NOT `sys.executable` directly if the test
process might be running under a venv/poetry env (its `python.exe` is
often a small launcher stub that locates the real interpreter via a
`pyvenv.cfg` file relative to ITS OWN path; copied elsewhere with no
`pyvenv.cfg` alongside it, the stub fails to start). Use
`os.path.join(sys.base_exec_prefix, "python.exe")` instead — always the
base, non-venv install regardless of what venv is active, safe to copy
and relocate. Then set `PYTHONPATH` (via the real `env=` kwarg, which DOES
work for child-env population) to a directory containing a
`sitecustomize.py` that does the real fake-git logic (spawn a real
grandchild via `subprocess.Popen([sys.executable, "-S", "-c", "import
time; time.sleep(60)"])`, write its pid to a file, `time.sleep(60)`
itself). This works because Python's `site` module imports
`sitecustomize.py` during interpreter STARTUP — before it ever attempts
to open `argv[1]` ("fetch", the git subcommand) as a script file — so
the hijack fires unconditionally, with no valid python script needing to
exist on disk at all. The `-S` flag on the grandchild's own invocation is
required to stop it from ALSO importing the same `sitecustomize.py` and
recursively spawning further "grandchildren."

**Third gotcha — `tasklist` output encoding**: `subprocess.run(["tasklist",
"/FI", f"PID eq {pid}"], text=True)` with the DEFAULT (UTF-8) encoding
raises `UnicodeDecodeError` on a non-English Windows locale (confirmed:
Spanish Windows, byte `0xe0`) — `tasklist`'s console output uses the
OEM/ANSI codepage, not UTF-8. Fix: `encoding="oem", errors="replace"` on
the `subprocess.run` call. This is a liveness probe, not a content
assertion, so `errors="replace"` is safe — never let an unrelated
locale-encoding mismatch fail a process-liveness check.

Verified end-to-end manually (outside pytest) before writing the actual
test: fake git.exe hangs, `run_git(timeout=1)` returns `(1, "")` in
~1.2s, grandchild pid written, and dies (confirmed via `tasklist`) within
the 5s polling deadline after `run_git` returns — proving
`_win32_kill_tree()`'s real `taskkill /F /T /PID` genuinely kills the
whole tree, not just the direct "git.exe" child. Classes:
`TestWin32ProcessTreeKillOnTimeout`,
`TestWin32AskpassFailfastResolvesAndExitsNonzero` (the latter needed no
new technique — just `subprocess.run(_ASKPASS_FAILFAST + " " + prompt,
shell=True)`, faithfully reproducing how git invokes a multi-token
GIT_ASKPASS command line on Windows).

## boot_glossary_cache migration — old cache (pre-`origin_sha` field) validity depends on whether an upstream now exists

`_read_glossary_cache()`'s freshness check does
`cache.get("origin_sha") != _resolve_origin_sha(upstream_ref)`. A cache
written before issue #49 added the `origin_sha` field has no such key at
all, so `cache.get("origin_sha")` defaults to `None`. Two genuinely
different outcomes from the SAME old cache, both correct and neither a
crash: (1) if the repo still has no upstream configured when read,
`_resolve_origin_sha(None)` is also `None` — `None == None`, cache stays
VALID (no unnecessary full-history rescan just because the schema grew a
field). (2) if an upstream now resolves to a real sha, `None !=
"<realsha>"` — cache is correctly treated as STALE (returns `None`,
triggering a fresh regenerate-and-write on the next call), never raising
KeyError/crashing. Confirmed empirically both ways — gotcha in the test
setup: `generated_at` must be a FRESH timestamp
(`datetime.now(timezone.utc).isoformat()`), or the pre-existing
`GLOSSARY_CACHE_TTL` (86400s) staleness check fires first and masks
whichever origin_sha behavior the test actually meant to isolate.

## Control-byte record forgery, generalized to 8 sibling sites (issue #57) — forged payload field count must be N-1, not N, or it corrupts instead of forging cleanly

Extends the single-module note above (`extract_memory()`/`extract_glossary()`,
SEC-CRIT-NEW-01) to 8 more `git log --pretty=format:...%x1f...%x1e` call
sites Bilbo inventoried across the repo, each independently vulnerable to
the same "a commit body containing the same \x1e/\x1f bytes forges a fake
record" bug. 6 are full-forgery (record boundary itself forgeable):
`bin/git-memory-gc.py:scan_commits()`,
`bin/git-memory-doctor.py:check_hook_execution()` /
`check_gc_status()` (one git call, two independently-attackable loops —
stale-blocker collection AND Stale-Blocker-tombstone collection; a forged
tombstone can illegitimately SUPPRESS a real, unrelated stale blocker, not
just fabricate a new one), `lib/recall.py:_scan_commits()` (highest blast
radius — feeds LLM context via UserPromptSubmit/PreToolUse),
`lib/bootstrap_commits.py:scan_recent_commits()`,
`hooks/precompact-snapshot.py:extract_memory_from_log()` (also LLM-facing,
printed to stdout after PreCompact). Confirmed all 6 live via real
`git commit --allow-empty`, 2026-07-09. Contract file:
`unmassk-toolkit/tests/test_control_byte_injection.py`.

**Non-obvious construction gotcha — the forged payload must embed exactly
(real-field-count − 1) separators, not more:** each site's `str.split(sep,
maxsplit=K)` produces `K+1` parts. When a hostile record has *one embedded
`\x1e`* splitting the raw output into two chunks, the SECOND chunk (the
forged one) inherits whatever real trailing field the actual commit's
format string emits last (its real `%at`/`%aI` timestamp) — but only if
the forged payload's own field count leaves exactly one slot free for that
real trailing field. Adding one extra fake field (e.g. a bogus epoch
string) beyond that budget shoves the real trailing field into an already-
full last part, producing garbled concatenated text (`"9999999999\n\x1f
1774980550"`) instead of a clean forgery — confirmed empirically: adding a
4th fake field after `Blocker: <text>` in a 4-field format broke the
forged stale-blocker reproduction entirely (`check_gc_status()` returned
zero stale blockers, not the expected forged one) until the extra field
was removed, at which point the forged record cleanly inherited the real
backdated commit's own `%at` (giving the forged entry a fully plausible
`age_days: 100`). When constructing a forgery PoC/test for any N-field
`%x1f`-delimited format, use exactly N-1 embedded `\x1f` in the payload
(fakesha + fake-subject + fake-trailer-text, nothing more for a 4-field
format) — verify live with a scratch probe before trusting the reasoning,
the off-by-one is easy to get wrong by pure inspection.

**2 sibling sites are ALREADY SAFE by construction, no fix needed —
confirmed, not assumed:** `lib/boot_git_checks.py:get_timeline()` /
`get_last_context_time()` have NO `%x1e` in their format at all (one
commit per output line, `%h\x1f%s\x1f%at`, split with `maxsplit=2`), so no
record can ever be forged. A raw `\x1f` embedded in the (fully attacker-
controlled) commit subject can only shift where the subject/date field
boundary falls — but `split(sep, maxsplit=2)` always leaves the git
format's own real pre-date `\x1f` un-consumed and literally embedded in
the resulting date_str (since the subject's injected separator is
consumed as the "2nd split", the real one is never reached), and
`time_ago()`'s `str.isdigit()` + ISO-8601-fallback guards both fail to
parse a string containing a leftover control byte — the result always
degrades to `"unknown"`, never a forged/attacker-chosen date. Verified
live with `git commit -m "feat(x): AAA\x1f9999999999"` → `get_timeline()`
entry ends `"| unknown"`, `get_last_context_time()` on an equivalent
`context(...)` subject → returns `"unknown"` (not `None`, not the forged
epoch). Written as `[GUARD]` tests, not `[ROJO]` — see
conventions.md's "mixed RED/GUARD is expected" note.
