---
name: ops-iac fix lessons
description: Lessons from fixing Critical/High findings in ops-iac scripts
type: project
---

## H-2 symlink fix order matters

When fixing the hardcoded `test_role` symlink in validate_role.sh, `ROLE_NAME` must be computed **before** the heredoc that references it (not after). The original code computed ROLE_NAME after the heredoc. When moving ROLE_NAME earlier, the heredoc can use `${ROLE_NAME}` correctly.

## FAILED=0 initialization

validate_playbook_security.sh and validate_role_security.sh reference `$FAILED` in the final summary (`$FAILED security issue(s)`) but never initialize it. This causes an unbound variable error under `set -u`. Add `FAILED=0` next to `ERRORS=0` and `WARNINGS=0`.

## Python path validation hooks: fail-closed patterns

When writing a Python PreToolUse hook that validates file paths:
- Normalize with `os.path.normpath()` BEFORE any trigger substring check — double-slashes and `..` segments bypass literal checks.
- Use `os.path.realpath()` (not `os.path.abspath()`) on BOTH the target path and git root — realpath resolves symlinks; abspath does not.
- For not-yet-created files, resolve the parent with realpath and append the filename.
- Fail CLOSED when git root is unavailable — return `{"decision": "block"}`, never `{"decision": "approve"}`.
- Wrap the entire `main()` in `try/except` — any unhandled error must also return `{"decision": "block"}`.
- On Windows NTFS, use `os.path.normcase()` on both sides of `startswith` to neutralize drive-letter case mismatches and case-insensitive filesystem bypass.
- Build the valid prefix with `os.path.join(...) + os.sep` (not string concatenation with `/`) so the boundary check is exact.
- Emit `sys.stdout.flush()` after every `json.dump` call.

## set -euo pipefail vs set -e

Bare `set -e` doesn't catch unset variable references (`-u`) or pipeline failures (`-o pipefail`). Always use `set -euo pipefail` in new and existing scripts.

## Elysia 1.4.28: publishToSelf is dead config — self-deliver manually

`publishToSelf: true` in the `.ws()` config compiles with no error but has no effect in Elysia 1.4.28 — the string "publishToSelf" does not appear in any compiled Elysia .js file. `ws.publish()` (and `broadcastSync` which calls it) always excludes the calling socket.

Fix: after every `broadcastSync(roomId, event, ws)` call in a WS handler, add an explicit self-send:
```typescript
ws.send(JSON.stringify({ type: 'new_message', message: safeMessage(msg) }));
```
Apply `safeMessage()` (or `stripSessionId` for the full event envelope) to the self-send — same sanitization that `broadcastSync` applies internally before publishing.

Remove the dead `publishToSelf: true` line — it gives false confidence that self-delivery works.

## React StrictMode: useEffect cleanup cannot return a value

The first draft of the StrictMode WebSocket fix had the cleanup return a cancellation
function (`return () => clearTimeout(timeoutId)`). This is invalid — React cleanup
functions must return `void | undefined`; any return value is silently ignored.

The correct pattern is to store the timer ID in a `useRef` and cancel it at the TOP
of the next effect run, not inside the cleanup itself. See implementation-patterns.md
for the full pattern.

## bun test finds no files from apps/frontend

There are no `.test.ts` / `.spec.ts` files under `chatroom/apps/frontend/src`. Run
`bun test` from the monorepo root (`/Users/unmassk/Workspace/claude-toolkit/chatroom`)
or use `bunx tsc --noEmit` as a type-check fallback from the package directory.

## Pre-existing tsconfig rootDir error in apps/frontend

`chatroom/apps/frontend/tsconfig.json` includes `vite.config.ts` via a glob but
`rootDir` is `src/`, so `tsc --noEmit` always exits 2 with a TS6059 error. This is
pre-existing and unrelated to any edits. Filter it with grep or ignore when scanning
for new errors introduced by a change.

## Elysia WS upgrade() hook ignores return values

Elysia's `upgrade()` hook on `.ws()` routes cannot reject connections — any return value (including `{ status: 403 }` or a `Response`) is silently discarded and the upgrade proceeds regardless. Do not use `upgrade()` for auth/origin checks. Instead:
- Move origin/auth checks to the `open()` handler.
- Call `ws.close()` immediately if the check fails, then `return`.
- Store per-connection state (e.g. connId for rate limiting) in a module-level `Map<ws, data>` keyed by `ws.raw ?? ws` (the raw uWebSockets handle), populated in `open()` and cleaned up in `close()`.
- The `WsData` type (from `ws.data`) cannot carry custom fields set in `upgrade()` — they are not propagated.

## WS name validation blocked legitimate orchestrator (chatroom)

Initial validation for `?name=` query param blocked ALL agent names including `claude`. The test `?name=Claude` returned `NAME_RESERVED`.
Fix: `RESERVED_AGENT_NAMES` excludes `user` and `claude` from the blocked set — only specialist invokable agents (bilbo, ultron, etc.) are blocked to prevent impersonation.
Rule: think about who legitimately connects, not just who to block.

## globSync import location

`globSync` is exported from `node:fs` in Bun (not `node:fs/promises`, not a separate package).
Correct: `import { existsSync, globSync } from 'node:fs'`

## Adding a field to ServerRoomState breaks 3 tests

The `ServerRoomStateSchema` is referenced in 3 test objects (ServerRoomStateSchema tests x2, ServerMessageSchema union test x1). When adding a required field, all 3 need updating. Find with: `grep -n "room_state" packages/shared/src/schemas.test.ts`

## Bun 1.3.11 mock.module() leaks across test files — use DB-state assertions instead

`mock.module('module.js', ...)` replaces that module globally for the entire bun test session. If module A is mocked in test file 1, every subsequent test file that imports module A for real will get the mock instead.

**Safe to mock:** `db/connection.js` (use a unique in-memory DB instance), `index.js` (stub server — no other file needs real behavior).
**NOT safe to mock:** `agent-runner.js`, `message-bus.js` — many other tests need real behavior from these.

**Replacement strategy:** Instead of spying on function calls, query DB state:
- `countSystemMessages(roomId, substring)` → `SELECT COUNT(*) FROM messages WHERE msg_type='system' AND content LIKE ?`
- `getAgentStatus(agentName, roomId)` → `SELECT status FROM agent_sessions WHERE ...`
- Use `ensureAgentSession(agentName, roomId, 'running')` before status-change assertions.

## Bun test order: fire-and-forget invocations leak global scheduler state

`agent-invoker-schedule.test.ts` calls real `invokeAgents('default', new Set(['bilbo']), ...)`, spawning real claude subprocesses. These leave entries in the global `activeInvocations` Map. Tests running after this file that call `drainActiveInvocations()` wait forever (5 s timeout).

**Fix:** In the intervening test file, import and forcibly clear the global state after all tests:
```typescript
import { activeInvocations, inFlight } from '../../src/services/agent-scheduler.js';
afterAll(() => {
  activeInvocations.clear();
  inFlight.clear();
});
```
The orphaned subprocesses complete in the background without affecting test correctness.

**Diagnostic pattern:** When removing a mock.module() to fix a leak, check if the mock was accidentally masking a different isolation bug (e.g., the mock made `doInvoke` undefined → TypeError → quick failure → pending invocations cleaned up). Always run targeted two-file test pairs to find the source of unexpected failures.

## mock.module() alternative: export a _setXForTesting() setter instead

When a test needs to control module-internal state (e.g. a cached registry loaded from disk) but mock.module() would leak and break other test files:

1. Export a `_setXForTesting(value | null)` function from the source module that mutates the private cache variable directly.
2. In the test: call it in `beforeAll` to inject fake data, call it with `null` in `afterAll` to reset.
3. No module replacement → no Bun mock.module() leak.

Example: `agent-registry.ts` exports `_setRegistryForTesting(map | null)`. The reinvoke test uses it to inject a fake registry with all known agents as `invokable: true`, bypassing the disk-reading `buildRegistry()` entirely. Upstream tests that need real `agent-registry.js` behavior are unaffected.

Rule: if the module under test has a module-level cache that varies by environment (disk files, env vars, etc.), prefer a setter over mock.module(). Reserve mock.module() for modules where you want to replace ALL behavior (db connections, server stubs).

## generateId() produces 16-char base64url strings, NOT UUIDs

`generateId()` in `utils.ts` uses `randomBytes(12).toString('base64url')` — 16 characters matching `/^[A-Za-z0-9_-]{16}$/`. These are NOT RFC4122 UUIDs. Zod's `.uuid()` rejects them. When validating cursor/ID fields in schemas, use `.regex(/^[A-Za-z0-9_-]{16}$/)` instead of `.uuid()`. Test IDs must also match this format (16 base64url chars) or Zod schema validation will reject them before the handler runs.

## release_helpers.py: sys.path al importar como módulo desde tests

Cuando un módulo Python importa un hermano (`release_validators`) con un import directo
(no relativo), ese import falla si el módulo se carga como `bin.release_helpers` desde
los tests (el directorio `bin/` no está en `sys.path` del proceso pytest).

Fix: insertar `_BIN_DIR` en `sys.path` al inicio del módulo:
```python
_BIN_DIR_RH = os.path.dirname(os.path.abspath(__file__))
if _BIN_DIR_RH not in sys.path:
    sys.path.insert(0, _BIN_DIR_RH)
```
Este patrón garantiza que funcione tanto como script directo como cuando pytest
lo importa como módulo `bin.release_helpers`.

## React StrictMode: second connect() call kills a CONNECTING socket

StrictMode lifecycle: mount → connect(WS1) → unmount → cleanup(schedules disconnect 100ms) →
remount → clearTimeout(ok) → connect() — but this second connect() hit the old "close existing
socket unconditionally" block and closed WS1 while it was still in CONNECTING state, producing
"WebSocket closed before connection established".

Fix in ws-store.ts `connect()`: guard before the close block —
```typescript
if (socket && (socket.readyState === WebSocket.CONNECTING || socket.readyState === WebSocket.OPEN)) {
  const currentRoom = get().roomId;
  if (currentRoom === roomId) {
    return; // Already connecting/connected — don't recreate
  }
}
```
Only close the existing socket when it is for a different room or is in CLOSING/CLOSED state.
The original `socket.onclose = null; socket.close(); socket = null` block stays intact beneath
the guard for the different-room case.

## reinvoke_from_context invokable check must use static registry, not runtime registry

`buildRegistry()` in `agent-registry.ts` starts all agents with `invokable: false` and only
sets `invokable: true` when the agent's `.md` file exists in `AGENT_DIR` AND has at least one
non-banned tool. In CI (Ubuntu, no `~/.claude/...` directory), `AGENT_DIR` resolves to a
non-existent path, so ALL agents end up with `invokable: false`.

`handleReinvokeFromContext` was checking `!agentConf.invokable` — this is the wrong source of
truth. The fix: check `AGENT_BY_NAME.get(name)?.invokable` (the static shared registry) instead.
The static registry is canonical and environment-independent. Tool availability for the actual
spawn is validated later by `doInvoke`.

The `_setRegistryForTesting()` pattern in `ws-control-handlers-reinvoke.test.ts` is a workaround
for this same issue — it injects a fake registry with `invokable: true`. The golden test
`ws-handlers-golden.test.ts` did NOT use this workaround and relied on the real registry,
exposing the CI failure.

Rule: for "is this agent name valid?" checks in WS handlers, use `AGENT_BY_NAME` from
`@agent-chatroom/shared`. For "can it run right now?" (tool config, model, etc.) use `getAgentConfig()`.

## unmassk-toolkit Crown retraction: per-scope "newest crown resolved" tracker, not per-commit filter

Implementing `Retract-Crown: <hash>` in `unmassk-toolkit/hooks/session-start-boot.py`
(`extract_memory()` / `extract_glossary()`), the naive fix —
`is_crown = (Crown == kind) and (sha not in retracted_hashes)` computed independently
per commit — passes the single-crown case but fails multi-crown re-consolidation: if
scope X has older crown A and newer crown B, and B gets retracted, the existing
"crown beats non-crowned entry" replace loop lets A resurface as active, which the
spec (and `test_crown_retraction.py::test_11`) explicitly forbids — retracting the
active crown must fall back to fully uncrowned, never to an older superseded crown.

Fix: track a per-scope, per-kind "already resolved" set (`crown_decision_resolved`,
`crown_memo_resolved`). Since `git log` without `--reverse` yields newest-first, the
FIRST Crown-carrying commit encountered per scope is the only retraction candidate —
mark the scope resolved right there and decide `is_crown` once; any older Crown
commit for that scope found afterward is ignored outright (never re-enters the
replace logic), regardless of the first one's retraction status. Collect
`Retract-Crown` target hashes in a separate up-front pass over the same commit range
(retraction always targets a chronologically older commit, so a forward pass over
the full range is simplest and order-independent).

Flagged in advance by Dante's design notes:
`.claude/agent-memory/unmassk-toolkit-dante/crown-retraction-design-notes.md`.

## test_release.py: 9 pre-existing failures unrelated to unmassk-toolkit changes

`tests/test_release.py::TestT25TimeoutExpired`, `TestT26NoDuplicateStderr`,
`TestT27DieNoReturn`, and all of `TestPromoteChangelogUnit` (6 tests) fail with
`ModuleNotFoundError: No module named 'bin.release_helpers'` — confirmed via
`git stash` that this happens identically on unmodified `main`, regardless of
what else changed. Root cause is a `sys.path`/import-order issue when
`test_release.py` runs in certain orders, not a regression. When running the
full suite, expect "707 passed, 9 failed" as the clean baseline for these
specific tests — don't spend time chasing them as caused by an unrelated fix.

**Addendum (2026-07-06, feat-boot-freshness Task 2):** the SAME 9-failure
count can shift which file it "appears" to come from depending on what
else is in the run. `pytest unmassk-toolkit/tests -q
--ignore=tests/test_boot_freshness.py` reproduced the documented 9
`test_release.py` failures exactly (twice, before and after a same-session
refactor). But `pytest unmassk-toolkit/tests -q` (the whole suite,
`test_boot_freshness.py` included) showed "9 failed, 875 passed" with ALL
9 failures coming from `test_boot_freshness.py`'s genuinely-still-RED
Task 3/4/5 acceptance tests and ZERO `test_release.py` failures — same
`sys.path`/import-order flake, just resolved the other way by a different
collection order. Rule: when verifying a diff, check the pre-existing-
failure COUNT (9) as the invariant, not which specific file the summary
attributes them to on a given run — and run the suite both ways at least
once (whole suite, and target file isolated from the rest) before
concluding "0 regressions."

## Issue #55 adversarial round: a Dante contract test can be self-contradictory even when RED-before-fix looks legitimate

`tests/test_date_parsing_epoch_contract.py::TestBootstrapJsonDateFieldReadableForPresentation::test_recent_commit_date_is_not_a_raw_digit_string` (BUG-3, Moriarty) asserts, on the SAME variable `got_date` with no reassignment in between:
1. `assert got_date == real_epoch` (a "setup sanity" check — `real_epoch` is asserted pure-digit by its own producer, `_real_epoch_of_head()`)
2. `assert not got_date.isdigit()` (the actual contract)

These two assertions are mutually exclusive for ANY string value — `got_date` cannot simultaneously equal a pure-digit string and not be all-digits. Confirmed via `bin/git-memory-bootstrap.py:96,122`: `commits = scan_recent_commits(); output["commits"] = commits` passes the dict through unmodified, no transformation layer exists between `scan_recent_commits()`'s epoch-string `"date"` field and the `--json` output — and a SIBLING test in the same file (`TestBootstrapCommitsDateFieldContract::test_recent_commit_date_should_be_epoch_not_iso`) requires that exact same field to STAY a raw epoch string when `scan_recent_commits()` is called directly. Since `--json` surfaces that dict unmodified, satisfying one test's contract (epoch) necessarily violates the other's (not-digit) — and even a presentation-layer-only transform (copy the dict, convert only the `--json` output's date to ISO, leave `scan_recent_commits()` itself untouched) still fails BUG-3's own first assertion, because THAT test's `got_date` is read from the very `--json` output being transformed.

Verified empirically: after implementing FIX-1/2/4/5/6 (all straightforward), reran BUG-3 alone — same "contract not yet met" failure at the SECOND assert, unchanged, exactly as before any code was touched. This is not something a production code change can fix.

Rule: when a test's two assertions on the same untouched variable are logically incompatible, don't try transformation tricks (copy-before-serialize, separate presentation field, etc.) to satisfy both — verify the contradiction algebraically first (can ANY value satisfy both lines?), then STOP and report instead of guessing at production code. Escalate with the exact two conflicting assertions cited, plus a concrete resolution suggestion (e.g., "add a new `date_display`/`date_iso` key for the readable value, keep `date` as the raw epoch, update BUG-3's test to check the new key" — but don't implement that yourself if it requires editing Dante's test file in test-first mode).

## Issue #55: migrating parse_date() from %aI+fromisoformat to %at+epoch requires making `now` tz-aware too, at every call site

Extending the `%at` migration (see the `boot_git_checks.py` entry above) to
the two duplicated `parse_date()` helpers in `bin/git-memory-gc.py` and
`bin/git-memory-doctor.py`, plus the unparsed date field in
`lib/bootstrap_commits.py:scan_recent_commits()`. The naive fix — just swap
`%aI` for `%at` in the `git log --pretty=format:` string and add an
`.isdigit()` branch to `parse_date()` returning
`datetime.fromtimestamp(int(date_str), tz=timezone.utc)` — silently breaks
every downstream age computation: both files compute `now = datetime.now()`
(naive, no tzinfo) and then do `(now - commit["date"]).days`. Subtracting a
naive datetime from a tz-AWARE one raises `TypeError: can't subtract
offset-naive and offset-aware datetimes` at runtime — not caught by the
`except (ValueError, IndexError)` in `parse_date()` itself, since the crash
happens later, in `find_stale_items()`/`check_gc_status()`. Fix: change
`now = datetime.now()` to `now = datetime.now(timezone.utc)` at BOTH call
sites (`git-memory-gc.py`'s `find_stale_items()`, `git-memory-doctor.py`'s
`check_gc_status()`) in the same change, and make `parse_date()`'s ISO-8601
fallback branch also return tz-aware datetimes (mirror `time_ago()`'s `if
dt.tzinfo is None: dt = dt.replace(tzinfo=timezone.utc)` pattern) instead of
the old `.split("+")[0]` (which silently discarded the offset and produced a
naive datetime) — so ALL of `parse_date()`'s return paths agree on
awareness, not just the new epoch branch.

Rule: whenever a `parse_date()`-style helper is migrated to return tz-aware
datetimes, grep the same file for every `datetime.now()` it gets subtracted
against and make that call tz-aware too, in the same commit — a passing
contract test for `parse_date()` in isolation (e.g.
`test_date_parsing_epoch_contract.py`'s `test_parse_date_resolves_real_epoch_string`)
will NOT catch this, since it only calls `parse_date()` directly and never
exercises the subtraction. The end-to-end tests in that same file
(`TestGcStaleBlockerSurvivesOldGit`, `TestDoctorGcStatusSurvivesOldGit`,
which run the real CLI end-to-end and assert on stdout/JSON output) are what
actually catch a naive/aware mismatch — a "helper-only" contract test suite
without at least one full-script-execution test would have shipped this bug
green.

`lib/bootstrap_commits.py`'s `date` field needed only the format-string
swap (`%aI` -> `%at`) with no parsing/awareness fix, since that module never
parses the field — it's stored and returned as a raw string, unconsumed
downstream (confirmed via the contract test module's own docstring, which
flags this as "no parse_date() here at all").

Also: `bin/git-memory-doctor.py:check_hook_execution()` fetches the date
field via the same `git log` call but never consumes it (only `body =
parts[2]` is read) — migrate the format string for DoD consistency but
there's nothing to fix in its (nonexistent) date-parsing logic.

## session-start-boot.py: any new git_helpers.py export needs a defensive import

`tests/test_migrate_statusline.py::_load_migrate_fn` loads `hooks/session-start-boot.py`
via `importlib.util.spec_from_file_location` and replaces `sys.modules["git_helpers"]`
with a hand-written stub `ModuleType` that only defines a fixed, small set of names
(`ensure_gitignore`, `_GENERATED_JSONS`, `run_git`, `is_git_repo`, `GIT_TIMEOUT`,
`commits_since_last_consolidation`). Any *new* name added to `lib/git_helpers.py` and
imported directly (`from git_helpers import new_thing`) at module load time in
`session-start-boot.py` breaks this test file with `ImportError: cannot import name
'new_thing' from 'git_helpers'` — even though `new_thing` exists in the real file,
because the stub shadows it in `sys.modules` during that test's import.

Fix pattern (already used once for `ensure_runtime_dir`, now also for
`open_no_follow_symlink` added while closing SEC-CRIT-001/CRB-01 findings):
```python
try:
    from git_helpers import new_thing
except ImportError:
    def new_thing(...):  # or new_thing = None, if optional
        ...  # local fallback reimplementing the same behavior
```
Do NOT fix this by editing the test's stub (test_migrate_statusline.py is not meant
to be touched for hook feature work) — always make the import defensive on the
hook side instead. Full suite run is the only reliable way to catch this class of
break; `test_boot_output.py`/`test_boot_tombstones.py` alone won't surface it since
they don't stub git_helpers.

## Extracting session-start-boot.py code into lib/ modules: defer `parsing` imports inside functions

When splitting `hooks/session-start-boot.py` logic out into a new stably-named
`lib/*.py` module (done for CRB-04: `lib/boot_memory.py`, `lib/boot_migrations.py`),
a module-level `from parsing import X` in the NEW lib module is unsafe in a way the
original hook file never was.

Why: `hooks/session-start-boot.py` is loaded by tests via
`importlib.util.spec_from_file_location` + `exec_module`, WITHOUT ever inserting it
into `sys.modules` under a stable name — so every test that loads it re-executes its
top-level imports fresh. But a new `lib/boot_memory.py` IS a normal importable module;
the first `import boot_memory` anywhere in the pytest process caches it in
`sys.modules` for the rest of that process. `tests/test_migrate_statusline.py`
temporarily replaces `sys.modules["parsing"]` with a stub (e.g.
`sanitize_trailer_value = lambda s: s`, an identity no-op) while it execs the hook
file to reach `_migrate_stale_context_writer_statusline`. Since the hook file's own
`from boot_memory import ...` triggers boot_memory's FIRST-EVER import DURING that
stub window, `boot_memory`'s module-level `from parsing import sanitize_trailer_value
as _sanitize_canonical` binds to the STUB forever — even after the test's `finally`
block correctly restores `sys.modules["parsing"]`, because the poisoned name lives in
`boot_memory`'s own already-cached namespace, never re-evaluated. Observed effect:
`tests/test_regression_audit_round2.py::TestBootSanitize` (a completely unrelated
test file, run later in file-alphabetical order) started failing — `_sanitize_trailer_value`
stopped stripping U+2028/U+2029/`\x0b`/`\x0c`/`<!--` — only when run as part of the
FULL suite, not in isolation, which is the tell for this exact bug class.

Fix: move `from parsing import ...` from module level into the body of each function
that uses it (`_sanitize_trailer_value`, `_crown_replace`, `extract_memory`,
`extract_glossary` in `lib/boot_memory.py`). A deferred (function-body) import
re-reads `sys.modules["parsing"]` at CALL time, not at the lib module's own
(one-time, cached) import time — by the time any function is actually called, the
stub window has always already closed. This mirrors a pattern already present in
this codebase (`_migrate_untrack_generated_jsons` already did
`from git_helpers import _GENERATED_JSONS` inside the function body, not at module
top) — that precedent should have been a hint from the start.

Rule for future extractions out of `session-start-boot.py`: any new lib module that
consumes `parsing.py` (or any module a test is known to stub — check
`test_migrate_statusline.py`'s stub list) must import those specific names inside
function bodies, not at its own module top level. `git_helpers` names that merely
fail closed (`run_git` stub → `(1, "")`, `ensure_gitignore` stub → no-op) are lower
risk since they don't silently produce wrong-but-plausible output the way an
identity-lambda sanitizer does — but the same hardening is worth applying
proactively if a future test ever calls a `git_helpers`-dependent function
in-process (not via subprocess) after this kind of stub window.

## session-start-boot.py: adaptive stdout budget for the truncation fix

Fixing the harness's ~2KB stdout preview window truncating the `Next:` line
(House's diagnosis: a 1297-byte `context()` subject was enough to blow the
budget): the full detailed briefing must ALWAYS be written to
`.claude/.unmassk/boot-log-latest.txt` (untruncated, regenerated every boot),
but stdout can't unconditionally become a minimal banner — pre-existing tests
(`TestBootSections` etc. in `test_boot_output.py`) assert `STATUS:`, `BRANCH:`,
`RESUME:`, `REMEMBER:`, `DECISIONS:`, `TIMELINE` are present in stdout for
normal-sized repos. Resolution: measure `len(full_text.encode("utf-8"))` and
only swap to the minimal banner (short STATUS/BRANCH lines + pointer to the
log file + "read" instruction) when it exceeds `STDOUT_FULL_INLINE_BUDGET_BYTES
= 6000`. Measured a normal small repo on this dev machine (with real skill-
drift warnings baked in, since `check_skill_drift()` reads the real
`~/.claude/plugins/cache` regardless of which tmp repo is under test) at
~1958 bytes — 6000 gives ~3x margin. A giant single-commit payload (2000+
char subject/trailers) produces ~14KB, comfortably over the threshold. When
writing banner text for a "minimal mode", avoid the bare word `TIMELINE`
entirely (test asserts it's absent with no colon, unlike the other markers
which are checked with a trailing colon) — even mentioning it in prose breaks
the exclusion test.

## git log control-byte record forgery: fix with `-z` (NUL), not a different embedded byte

`lib/boot_memory.py`'s `extract_memory()`/`extract_glossary()` used to split
`git log --pretty=format:...` output on a literal `\x1e` (record separator)
embedded in the format string. Since a commit body CAN legally contain a raw
`\x1e` byte, one real commit could smuggle a full fake record (forged
sha/scope/Decision text) — Argus's PoC. The field separator `\x1f` inside a
record is a different, lower-risk case: a fixed `str.split(sep, maxsplit=N)`
already caps the field count regardless of extra `\x1f`'s, so it's inert on
its own (confirmed with dedicated GUARD tests that must stay green after the
fix too).

Fix: pass `-z` to `git log` (record terminator becomes NUL, `\x00`) and split
on `\x00` instead. A commit message can never contain a raw NUL — git
truncates/rejects it at the object level — so this closes the forgery
class completely, with no size/perf cost. Verified empirically: `git log -z
--pretty=format:'%h\x1f%s\x1f%b\x1f%at'` still uses `\x1f` normally as a
literal byte inside each record; only the between-records separator changes
from a fake `\x1e` embedded in the format string to git's own NUL. No trailing
NUL after the last record — existing "skip empty entries after split" logic
handles this already. Rule for future: whenever record boundaries in `git log
--pretty=format` output must be attacker-proof, prefer `-z` + NUL over any
other embeddable control byte — NUL is the only byte structurally impossible
in a commit message.

## Shared fallback for a defensively-imported git_helpers function: put it in its own tiny module

`open_no_follow_symlink()` (SEC-CRIT-001) is imported defensively in both
`lib/boot_memory.py` and `hooks/session-start-boot.py` because
`tests/test_migrate_statusline.py` stubs `git_helpers` with a minimal fake
module. Before this session, each call site carried its own byte-identical
`except ImportError: def open_no_follow_symlink(...): ...` copy — a duplication
Cerberus flagged (T3-1). Fix: extracted the fallback into
`lib/_symlink_safe_open.py` (a new tiny module, never itself stubbed by any
test — only `git_helpers`/`parsing`/`version` are), and both call sites now do
`except ImportError: from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink`.
Rule: when a defensive-import fallback needs to exist at 2+ call sites because
of a test stub, don't hand-copy it — give it its own tiny module that the
stub doesn't know about, so there's exactly one implementation to keep in
sync with the real one.

## Extending session-start-boot.py's render_* split: boot_render.py needed the same deferred-parsing-import treatment as boot_memory.py

CRB T2-1 moved all 12 `render_*_section()` functions (plus small helpers —
skill drift, branch keywords, time formatting, issue matching, timeline,
relevance partitioning) from `hooks/session-start-boot.py` into a new
`lib/boot_render.py` (hook dropped from 1110 to 298 lines). Since
`boot_render.py` is a real, stably-named module (unlike the hook file, which
tests always load via `spec_from_file_location` + fresh `exec_module`, never
caching it), it's subject to the exact same stale-stub-binding risk documented
above for `lib/boot_memory.py`: `get_timeline()`, `render_remember_section()`,
and `render_memos_section()` needed their `from parsing import parse_scope`
/ `from parsing import normalize` calls deferred into the function body, not
hoisted to module top level, even though no test currently calls
`boot_render`'s functions in-process after a stub window (only via fresh
subprocess). `git_helpers.run_git` and `version.VERSION` stayed as ordinary
module-level imports in `boot_render.py`, mirroring `boot_memory.py`'s own
precedent that "fail-closed" git_helpers names are lower-risk and don't need
deferral.

Also: when moving a function's return tuple, check every place that unpacks
it before assuming a "just move the code" refactor is behavior-neutral —
`render_branch_section()` was returning an unused `behind_n` (T3-2, Cerberus);
removed from the signature and the one unpacking call site in `main()`, and
corrected the docstring, which had claimed `behind_n` was "reused downstream"
when nothing outside the function ever read it.

Before deleting anything from a file being split like this, grep the WHOLE
test suite for `\.functionName` patterns against every module alias a test
uses to `spec_from_file_location`-load the file (not just the literal
variable name `boot` — one file used `_boot_sanitize_mod`, another
`mod`) — some tests reach into the hook module's namespace directly
(`mod._sanitize_trailer_value`, `mod.commits_since_last_consolidation`,
`mod.run_git`, `boot.extract_memory`, `boot.extract_glossary`) even though
those functions are no longer defined in that file, only re-exported via
import. Any of those names accidentally dropped from the hook's own imports
breaks the test with an `AttributeError` that has nothing to do with the
function's actual logic.

## canonical sanitize_trailer_value() didn't strip ESC — extend the single source of truth, don't add a parallel sanitizer

`lib/parsing.py:sanitize_trailer_value()` (aliased as `_sanitize_trailer_value`
in `boot_memory.py`/`boot_checks.py`/`boot_render.py`) stripped `\r\n`,
U+2028/U+2029, `\x0b`/`\x0c`, and HTML/memory-data markers — but NOT `\x1b`
(ESC). A test contract requiring "manifest version field with raw ANSI
escape bytes must never reach stdout unsanitized" (SEC-MED-NEW-08, session
2026-07-05) fails silently if you just pipe the value through the existing
sanitizer without checking what it actually strips byte-for-byte — always
verify with a quick `python3 -c` round-trip before assuming a named
"canonical sanitizer" covers a new threat class. Fix: added `\x1b` to the
character class in `sanitize_trailer_value()` itself (one line), rather than
writing a second sanitizer in each of the 3 call sites (doctor.py,
upgrade.py, bootstrap.py) — grepped all non-test callers first (7 files) to
confirm none of them depend on ESC bytes surviving.

Corollary: when a value gets sanitized for display but is ALSO later
embedded in a filename that gets printed (e.g. `git-memory-upgrade.py`'s
`create_backup()` — the backup path string is echoed to the terminal),
sanitize for terminal-safety at the filename-construction site too, not
just at the original field's read site — a raw control byte can leak
through a completely different print statement than the one guarding the
original field.

## boot_checks.py <- boot_render.py is a strict one-way DAG — moving I/O functions may drag pure helpers along

When Cerberus flags `lib/boot_render.py` for a second round of I/O
extraction into `lib/boot_checks.py` (round 5, session 2026-07-05: moved
`get_timeline()`, `get_last_context_time()`, `render_branch_section()`,
`render_scopes_section()`, `render_consolidation_section()`), check whether
the functions being moved call any PURE helper still defined in
`boot_render.py` (`parse_branch_keywords()`, `time_ago()` in this case).
`boot_checks.py` must never import FROM `boot_render.py` — only the reverse
— so a moved I/O function that calls a pure boot_render.py-only helper
forces you to move that helper too, even though it does no I/O itself.
Before moving, grep every candidate helper's callers across the whole
file — if ALL its callers are also being moved, take the helper with them;
if any caller stays behind, the helper must stay too (would need a genuine
redesign, not just a move).

## needs_upgrade() Check 1 ("Context Checkpoint Commits" marker) is permanently dead on real installs

`hooks/user-prompt-memory-check.py::needs_upgrade()` Check 1 does
`if "python3 bin/" in block or "Context Checkpoint Commits" not in block: return True`.
The phrase "Context Checkpoint Commits" does not exist anywhere in
`lib/managed_blocks.py`'s current template — confirmed by dumping
`upsert_managed_blocks('')`'s output. This means Check 1 returns True for
EVERY real, freshly-installed repo, before Check 2 (the manifest.version
semver comparison) is ever reached. This is known and already worked
around in `tests/test_needs_upgrade_semver.py::make_semver_test_repo()`
(docstring explicitly explains it and patches the block to inject the
literal string so Check 1 is neutralized for its own tests) — it is NOT a
bug to silently fix; changing/removing this condition would contradict
that file's other passing tests. If a new test exercises `needs_upgrade()`
Check 2 (or the manifest read guard) via a plain `run_script(INSTALL, ...)`
install without also neutralizing Check 1 the way `make_semver_test_repo()`
does, it will fail for this unrelated reason, not because Check 2's logic
is wrong. Verified independently (session 2026-07-05, SEC-HIGH-NEW-11): with
Check 1 neutralized per that same helper's pattern and a symlink planted at
manifest.json, the `open_no_follow_symlink()` guard on the manifest read
correctly returns False — proving the guard works; a test that hits this
Check-1 quirk is a test-authoring gap, not an implementation defect. Escalate,
don't patch the check, if this recurs.

## Symlink-guard fix rounds: only session-start-boot.py's transitive imports need the defensive try/except fallback

When applying `open_no_follow_symlink()` across many call sites in one
sweep (SEC-CRIT-001-class findings), only import it defensively
(`try: from git_helpers import open_no_follow_symlink / except ImportError:
from _symlink_safe_open import open_no_follow_symlink_fallback as ...`) in
modules that are transitively imported during `hooks/session-start-boot.py`'s
module load — currently `lib/boot_memory.py`, `lib/boot_migrations.py`,
`lib/boot_render.py`, `lib/boot_checks.py` (the modules
`tests/test_migrate_statusline.py` stubs `git_helpers` around). Every other
call site (`bin/git-memory-{install,uninstall,doctor,repair,upgrade,bootstrap,commit}.py`,
`hooks/{user-prompt-memory-check,stop-dod-gate,session-start-crew}.py`) is
never imported during that stub window, so a plain
`from git_helpers import ..., open_no_follow_symlink` at module top level is
correct and simpler — don't add the defensive fallback there, it's dead
code. Confirmed by checking `session-start-boot.py`'s own import graph
before choosing the pattern for each of 9 new call sites (round 2026-07-05).

`open_no_follow_symlink()` also accepts a `pathlib.Path` for its `path` arg
transparently (it calls `os.open()`, which accepts any `os.PathLike`) — a
hook using `pathlib.Path.read_text()/write_text()` can switch to
`with open_no_follow_symlink(path_obj, "r"/"w", encoding=...) as f: f.read()/f.write(...)`
without converting to `str` first. One caveat: `open_no_follow_symlink()`
has no `errors=` parameter (unlike `Path.read_text(errors="replace")`) —
if the original code relied on lenient decode-error handling, wrap the read
in `except (OSError, UnicodeDecodeError)` to preserve fail-open behavior.

## boot_render.py REMEMBER/DECISIONS/MEMOS section duplication — safe to extract once glossary-merge stays separate

The three `render_*_section()` functions in `boot_render.py` looked
identical at a glance but their glossary-merge step differs meaningfully:
Remembers dedup by normalized TEXT (no scope-uniqueness, no crown-replace);
Decisions dedup by SCOPE with crown-replace; Memos dedup by SCOPE with
crown-replace AND a tombstone check (CRB-01). Do NOT merge that part. The
part that's genuinely identical is everything AFTER the merge: crowned/
normal split (SEC-MED-005 count-eviction bypass), optional branch-relevance
partitioning+capping, header/crowned-line/normal-line formatting, and the
"(N more ...)" trailer message (which differs only in a `more_label`
string fragment and the `--type` argument — parametrize both, don't
hardcode). Extracted as `_render_crowned_capped_section()`, called by all
three after their own distinct merge logic. Full test suite is the only
reliable check that behavior stayed byte-for-byte identical for this kind
of "looks like 3x duplication but isn't fully" refactor.

## verify_path_within_project() rollout: check the call site's exception handling BEFORE deciding catch-vs-propagate

Applying the `verify_path_within_project()` chokepoint (SEC-CRIT-002 /
SEC-HIGH-003/004/005 / SEC-LOW-006, session 2026-07-05: parent-`.claude`-
symlink class) to 5 new call sites, the right error-handling shape at each
site depends entirely on what the CALLER already does, not on the site
itself:
- If the call is already wrapped in a broad `try/except Exception`/`except
  OSError` by its only caller (e.g. `bin/git-memory-doctor.py`'s manifest
  rewrite, already inside `except Exception: pass`), just call
  `verify_path_within_project()` and let `UnsafePathError` (an `OSError`
  subclass) propagate into that existing catch — no new try/except needed.
- If the call site has NO wrapping try/except and boot/the caller must never
  crash (e.g. `lib/boot_migrations.py`'s `_migrate_runtime_to_unmassk()`,
  called from `run_preboot_migrations()` directly; `bin/git-memory-
  upgrade.py`'s copy of the same function, called from `apply_upgrade()`
  directly — unlike that file's OTHER steps which ARE each wrapped), add a
  local `try: verify_path_within_project(...); except UnsafePathError:
  return` INSIDE the function itself. Confirmed necessary here because
  `tests/test_security_regression.py` calls both `_migrate_runtime_to_unmassk`
  copies directly via a subprocess probe that treats any non-zero exit as a
  hard test error (`RuntimeError`), not just an assertion failure — letting
  the exception propagate would have broken the test, not just looked ugly.
- `bin/git-memory-upgrade.py`'s `create_backup()` is the third shape: an
  explicit CLI action with no wrapping try/except where an uncaught
  `UnsafePathError` IS the desired fail-closed outcome (non-zero exit,
  documented in a comment already in that function) — don't add a
  try/except there just for consistency with the other two shapes.

## Loading a lib/*.py module standalone (spec_from_file_location) without lib/ in sys.path breaks its sibling imports

`lib/boot_migrations.py` had zero `git_helpers` imports (module-level or
deferred) before this session — its own test helper's docstring says so
explicitly. Adding a deferred `from git_helpers import
verify_path_within_project, UnsafePathError` inside
`_migrate_runtime_to_unmassk()` would break
`tests/test_security_regression.py`'s
`_call_migrate_runtime_to_unmassk_boot_migrations()` probe, which loads the
module via `importlib.util.spec_from_file_location` in a **fresh
subprocess** (`python3 -c "..."`) that never inserts `lib/` into `sys.path`
(unlike normal execution, where `hooks/session-start-boot.py` always
inserts `lib/` before importing `boot_migrations`). Fix: at the top of the
function, before the import, do the same `sys.path` self-insertion already
used in `bin/release_helpers.py` (see the entry above this one) —
`_lib_dir = os.path.dirname(os.path.abspath(__file__)); if _lib_dir not in
sys.path: sys.path.insert(0, _lib_dir)` — then `from git_helpers import
...`. Works identically whether the module is reached normally (lib/
already on sys.path, no-op) or standalone (adds its own directory, then
`git_helpers.py` resolves as a sibling file). Rule: any NEW git_helpers (or
other sibling-module) import added to a `lib/*.py` file must be checked
against how that file's OWN tests load it — grep the test file for
`spec_from_file_location` + the module's filename before assuming a plain
import will resolve.

## bin/git-memory-bootstrap.py (953 LOC) and bin/git-memory-install.py (600 LOC) split — 2026-07-05

Both files had grown well past the project's 500 LOC convention (bootstrap
was never split across 10 rounds; install grew every round as security
guards were added). Split pattern mirrors `hooks/session-start-boot.py`'s
own precedent (boot_memory/boot_migrations/boot_render/boot_checks):

- `bin/git-memory-bootstrap.py` (953 → 143 LOC) split into 4 sibling
  `lib/` modules with NO cross-imports between them (all are pure functions
  of their arguments, called only from the thin entrypoint):
  `lib/bootstrap_tree.py` (dir walk + SIGNAL_FILES matching),
  `lib/bootstrap_deps.py` (package.json/pyproject/monorepo/CI/existing-install),
  `lib/bootstrap_commits.py` (git history), `lib/bootstrap_report.py`
  (classify_findings/suggest_actions/format_human).
- `bin/git-memory-install.py` (600 → 252 LOC) split into 2 modules with a
  ONE-WAY dependency: `lib/install_apply.py` (Phase 3 execution) imports
  `OLD_BIN_FILES`/`OLD_HOOK_FILES`/`OLD_LIB_FILES`/`OLD_SKILL_DIRS` from
  `lib/install_inspect.py` (Phase 1 detection) rather than duplicating them
  — `inspect()` and `_cleanup_old_install()` must agree on exactly which
  files count as an old-style install. Never the reverse import.

**Before splitting, grep the WHOLE test suite for `mod.attr` patterns**
(same rule as the boot_render.py split lesson above) — this is what
determined which functions/constants had to be re-exported by name (not
`import *`) into the thin entrypoint file:
- `bootstrap.py` needed: `check_existing_memory`, `scan_tree`,
  `detect_monorepo`, `detect_ci_commitlint` (probed directly via
  `importlib.util.spec_from_file_location` in
  `tests/test_security_regression.py`).
- `install.py` needed: `inspect`, `_update_claude_md` (same test file);
  PLUS `OLD_BIN_FILES`, `OLD_HOOK_FILES`, `_cleanup_old_install`,
  `_update_claude_md` (consumed by `bin/git-memory-upgrade.py`'s
  `_load_install_module()` at runtime, not just in tests); PLUS
  `_update_claude_md`, `_create_manifest` (consumed by
  `bin/git-memory-repair.py`'s `repair_issue()`). Missing any one of these
  breaks a DIFFERENT script at runtime, not just a test — check non-test
  callers (`grep -rn "install_mod\.\|_load_install_module"`) in addition to
  tests before finalizing which names to re-export.
- Neither file's tests stub `git_helpers`/`parsing` around
  `spec_from_file_location` loads (only `tests/test_migrate_statusline.py`
  does that, and only for `hooks/session-start-boot.py`) — confirmed via
  `grep -n 'sys.modules\[.git_helpers.\]'` across the whole test dir before
  concluding plain module-level imports (no defensive try/except) were
  safe in the 6 new `lib/bootstrap_*.py` / `lib/install_*.py` modules.

**Dead code found and removed during the bootstrap_tree.py extraction**:
`scan_signal_files()` had a literal `for dirpath in (tree_files): pass  #
Already handled above` loop — zero effect on any variable, confirmed by
inspection. Removed as part of the split (not a behavior change, so no new
test needed) rather than carried forward into the new module.

**Known follow-up, explicitly NOT done this round**: `bin/git-memory-doctor.py`
was already 510 LOC before this session (already over the 500 LOC
convention); a since-added `verify_path_within_project()` security fix
(SEC-HIGH-006, same session) pushed it to 518. Splitting it was out of
scope for the task that prompted this entry — flagged here as a future
candidate, same shape as bootstrap.py/install.py (grown over many rounds
of security-guard additions, never split).

## plan["skipped"] dead-loop in git-memory-install.py: populate, don't delete, when a silent-no-op branch already exists

`bin/git-memory-install.py`'s `main()` had `for desc in plan["skipped"]:
print(...)` — dead forever because `create_plan()` initialized
`plan["skipped"] = []` and never appended to it. Grepped the whole repo
first (`grep -rn '"skipped"'`) — zero test references, safe to change
either way. Chose to populate rather than delete: `create_plan()` already
had a silent no-op branch (`if report["has_old_install"] and not is_self:
append cleanup_old` — when `is_self` is True, nothing happened, no
explanation surfaced). Added the `else: plan["skipped"].append(...)`
branch so the self-install condition is now reported instead of silently
swallowed. Rule: when a dead loop exists BECAUSE a list is never
populated, check whether the surrounding function already has a
"detected a condition but did nothing about it" branch before defaulting
to deleting the loop — populating it can turn a silent gap into
information the plan printout should have shown all along.

## Round 13 (2026-07-05): the `else` branch of a defensive-import fallback silently drops the security guard

Both `hooks/session-start-boot.py::write_boot_log()` and
`lib/boot_memory.py::_write_glossary_cache()` have the shape:
```python
if ensure_runtime_dir is not None:
    ensure_runtime_dir(root)   # calls verify_path_within_project() internally
else:
    os.makedirs(some_dir, exist_ok=True)   # NO guard at all
```
The `else` branch only fires when `ensure_runtime_dir` failed to import
(test stub or a stale `git_helpers.py` missing the function) — but when it
fires, it silently reimplements the unguarded pre-fix behavior, losing
`ensure_runtime_dir`'s internal `verify_path_within_project()` call
entirely. This is a distinct sub-pattern from the "12 rounds" one
(`.claude`/`.unmassk` parent-dir symlink escaping a guard that was never
added) — here the guard EXISTS and is even documented in a comment next to
the `if` branch, but the `else` branch bypasses it. Rule: whenever a
function has an `if guarded_helper_available: guarded_helper() else:
manual_fallback()` shape, check the fallback branch for the same guard
independently — "the guard exists in this file" is not the same as "this
branch calls it."

Also found in the same sweep: `lib/boot_migrations.py::_migrate_runtime_to_unmassk()`
and `bin/git-memory-upgrade.py`'s copy build a THIRD path
(`claude_dir/agent-memory/<agent-name>/`) beyond the `.unmassk` one that
already had defense-in-depth — same fix applies (verify the specific
subdirectory variable right before `os.makedirs`/`os.rename` uses it, not
just the parent `claude_dir`).

An AST-based sweep script (walk `ast.walk()` sorted by lineno, track
variable assignments and `verify_path_within_project()`/`ensure_runtime_dir()`
calls in source order per function) is a decent way to re-run this class of
check, but it has two known blind spots: (1) it can't resolve a path built
from a `for x in SOME_LIST:` loop variable or a `dict.items()` value (the
literal string lives in the list/dict definition, not at the call site,
so pattern-matching the join expression's text misses it — these need a
manual `grep` cross-check of the same file for constants like
`OLD_SKILL_DIRS`/`migrations = {...}`); (2) it can't distinguish
`os.unlink()`/`os.remove()` on a path with NO further path components below
a trusted root (inherently safe — unlink never follows the final symlink,
and there's no intermediate directory to hijack) from the same call several
directories deep (genuinely risky) — it will flag both as "unprotected."
Confirmed false-positive case: `bin/git-memory-uninstall.py:144`'s
`os.unlink(os.path.join(target, "CLAUDE.md"))` where `target` comes
straight from `git rev-parse --show-toplevel` (already resolved, no
attacker-plantable intermediate symlink between `target` and the file) — do
not "fix" sites like this just because the script flags them; verify the
call is actually reachable through an untrusted intermediate directory
first.

## SEC-LOW-001: elif sibling of an already-guarded if branch needs the same guard

`lib/install_apply.py` and `bin/git-memory-uninstall.py` both had, in the
`OLD_SKILL_DIRS` loop: `if os.path.isdir(path) and not os.path.islink(path):
verify_path_within_project(...); shutil.rmtree(path)` (guarded) followed by
`elif os.path.islink(path): os.unlink(path)` (NOT guarded) — the symlink
case is exactly the one where `path`'s parent could itself be a symlink
component, same risk class as the `if` branch right above it. Fix: same
`try: verify_path_within_project(path, target) / except OSError: continue`
added to the `elif` too, in both files (identical pattern, no new test
needed — conceptually already covered by the sibling branch's existing
security-regression tests).

## Cerberus "unify banner language" nitpick can be a genuine dead end — escalate, don't force it (issue #49 repair round, 2026-07-06)

Cerberus flagged that `render_memoria_stamp()`'s output is Spanish
("MEMORIA: remoto...", "sin verificar") while `_build_pull_directive_lines()`'s
output is English ("PULL DIRECTIVE...", "do NOT pull") in the same boot banner —
asked to "unify the language, look at what the rest of the banner uses".
Investigation found BOTH functions have their exact output strings pinned by
Dante's own hardening tests: `TestRenderMemoriaStamp` asserts full-string
EQUALITY in Spanish (`== "MEMORIA: remoto (fetch hace 0s)"` etc., 11
parametrized cases) and `TestBuildPullDirectiveLines` asserts SUBSTRING
presence of exact English phrases ("DIRTY", "do NOT pull", "FIRST action").
Translating either function to match the other necessarily breaks the other
function's already-green hardening tests — there is no single-language change
that satisfies both without editing Dante's test file, which was out of scope
for this repair round. Correct move: do NOT force a fix that breaks tests, and
do NOT silently skip the finding either — implement everything else, then
explicitly report this specific nitpick as blocked/escalated with the exact
conflicting test names, so Yoda/Bex can decide whether to touch the tests.
Rule: when a Cerberus/Argus suggestion's only implementable form contradicts
an ALREADY-GREEN pinned test outside the two files you're allowed to touch,
that's an escalation, not a judgment call to make unilaterally.

**Resolution (same day):** Bex decided English (matching STATUS/BRANCH/RESUME/
DECISIONS/PULL DIRECTIVE, which were already English) — the MEMORIA: stamp in
`lib/boot_git_checks.py:render_memoria_stamp()` became `MEMORY:` /
`fetch skipped` / `last fetch Nh ago, unverified` / `unverified (never synced
with origin)`. Translating it required editing literal-string assertions in
BOTH `TestRenderMemoriaStamp` (hardening file, explicitly authorized) AND 3
substring checks in `test_boot_freshness.py` (the acceptance file) that
Bex's message didn't explicitly name — `"MEMORIA:" in combined` (x3) and
`re.search(r"sin verificar", ...)`. Once a product decision fixes the
language, EVERY literal-string assertion tied to that stamp across the whole
suite needs the same mechanical update, not just the ones in the file the
orchestrator happened to remember. Grep the whole test dir for the old
literal before declaring the mechanical change complete.

## lib/boot_memory.py -> lib/boot_glossary_cache.py split (2026-07-05): a real test forces a documented backward-compat re-export, breaking the "no cycle" instruction textually (but not at runtime)

Splitting the glossary-cache I/O functions (`_get_project_root`,
`_glossary_cache_path`, `_read_glossary_cache`, `_write_glossary_cache`,
`extract_glossary_cached`) out of `boot_memory.py` into a new
`lib/boot_glossary_cache.py` (524 -> 394 + 195 LOC), one test
(`tests/test_security_regression.py::TestBugAOEnsureRuntimeDirFallbackBranchSymlinkedParent::test_write_glossary_cache_does_not_write_outside_repo_via_fallback_branch`)
loads `lib/boot_memory.py` directly via `spec_from_file_location` under a
throwaway module name and calls `mod._write_glossary_cache({})` — this
breaks with `AttributeError` the instant the function moves out, per the
established "grep the whole suite for `mod.attr` before deleting" rule
(see the boot_render.py/bootstrap.py split entries above).

Naive fix (add `from boot_glossary_cache import _write_glossary_cache, ...`
at the bottom of `boot_memory.py`) creates a REAL circular-import crash in
this specific test scenario, because the probe module is never registered
in `sys.modules` under the real name `"boot_memory"` (spec_from_file_location
+ module_from_spec does not do that automatically) — so
`boot_glossary_cache.py`'s own `from boot_memory import extract_glossary`
(if kept at module level) triggers a SECOND, fresh execution of
`boot_memory.py` under its real name, which hits its own bottom
re-export line, finds `boot_glossary_cache` already mid-import in
`sys.modules`, and fails with "cannot import name ... from partially
initialized module."

Fix: defer `from boot_memory import extract_glossary` into the body of
`extract_glossary_cached()` (the only function that needs it) instead of
importing it at `boot_glossary_cache.py`'s module top level. This means
`boot_glossary_cache.py`'s top-level code never touches `boot_memory` at
all, so `boot_memory.py`'s bottom backward-compat re-export
(`from boot_glossary_cache import _get_project_root, _glossary_cache_path,
_read_glossary_cache, _write_glossary_cache, extract_glossary_cached`,
placed after all of boot_memory's own real definitions) can safely run
without ever entering a cycle. Net result: the "no cycle" instruction
holds for the real logic dependency (extract_glossary_cached -> extract_glossary
is one-way and deferred); only a documented test-compatibility shim runs
the other direction, and it's provably safe because of the deferred import.

Caveat found but NOT fixed (out of scope, flagged for Dante): the
backward-compat path means `mod.ensure_runtime_dir = None` (the test's
monkeypatch-after-load technique) no longer affects `_write_glossary_cache`'s
actual behavior, since the function's `__globals__` is now
`boot_glossary_cache`'s namespace, not the probe module's. The test still
passes (the real, non-monkeypatched `ensure_runtime_dir` already guards the
symlinked case correctly), but it no longer exercises the intended fallback
(`else`) branch. Whoever owns this test next should either monkeypatch
`boot_glossary_cache_module.ensure_runtime_dir` instead, or call
`_write_glossary_cache` through a spec-loaded `boot_glossary_cache.py`
directly rather than through `boot_memory.py`'s re-export.

## T2 fix (Moriarty, issue #49): `git merge-base` confirms shared history, but `extract_glossary()`'s `--all` bypasses that check entirely

Fixing the repo-identity-confusion finding (a misconfigured
`branch.<x>.remote/.merge` pointing at a totally unrelated bare repo — zero
shared history — got its crowned Decisions rendered as `[source: remote]`
memory): the obvious fix is `git merge-base HEAD <upstream_ref>` (plain, NOT
`--is-ancestor` — the two sides can be mutually diverged, you only care
whether ANY common ancestor exists) gating `resolve_boot_memory()`'s ref
choice and the `MEMORY:` stamp wording. That alone is NOT enough: verified
empirically (build an alien bare repo, point `origin` at it, `git fetch`,
inspect refs) that `extract_glossary()`'s `git log --all` ALSO walks
`refs/remotes/<name>/*` completely independently of ahead/behind or of
`resolve_boot_memory()`'s own logic — and worse, glossary entries carry NO
`[source: remote]` provenance tag at all, so an unrelated remote's crowned
Decision would render as if it were this project's OWN memory. Always
verify a "confirm before trusting a ref" fix with the actual failing PoC run
through the FULL boot hook (not just the one function you think owns the
bug) — a second code path can independently reach the same untrusted ref
via a completely different git flag (`--all` vs `@{u}` resolution).

Fix pattern: `git log --exclude=refs/remotes/<name>/* --all ...` (the
`--exclude` glob option must precede the ref-selecting `--all`) removes
exactly that remote's refs from the scan without disabling `--all` for
everything else (other local branches/tags legitimately still want deep
scanning). Thread the exclusion as a single explicit parameter
(`exclude_remote`) captured from the ORIGINAL (pre-nulled) upstream ref's
remote name — don't try to derive it from the same nulled `upstream_ref`
variable used for `resolve_boot_memory()`, since by the time you decide to
null that variable for the memory-read decision, you still need the
original remote name for the glossary exclusion.

Validating a value that gets embedded inside a single `--exclude=...` argv
string is a NARROWER problem than validating a value passed as its own
positional argv token: since `subprocess.Popen` never invokes a shell, a
crafted remote name can't "break out" of that one string regardless of
content — the only real risk is glob metacharacters widening the exclude
pattern. An allowlist (`^[A-Za-z0-9._-]+$`) is simpler and safer here than
reusing/duplicating a positional-arg-injection guard from a sibling module
(and reusing one across the module boundary would violate this codebase's
documented one-way DAG: `boot_memory.py` must never import FROM
`boot_git_checks.py`).

When a fix needs to run "once" and feed two decisions that must never
disagree (here: the `MEMORY:` stamp wording AND which ref
`resolve_boot_memory()`/`extract_glossary_cached()` treat as this
project's own), watch for ordering traps in the orchestrating `main()`:
`hooks/session-start-boot.py`'s stamp used to be computed and appended to
`lines` BEFORE `render_branch_section()` (which resolves `upstream_ref`)
even ran. Since `lines` is just a plain list built by sequential
`.append()`/`.extend()` calls, the fix was to reorder the CALL sequence
(compute `render_status_section()`/`render_branch_section()` first, run the
one shared check, THEN build `lines` in the original visual order) rather
than threading a mutable "pending stamp" placeholder through the list.

## Multi-agent repair rounds: `git diff` on a shared file mixes YOUR hunks with concurrent agents' hunks — don't assume the whole diff is yours

During issue #49's boot-freshness repair round (2026-07-07), tasked with
exactly 2 targeted fixes to `lib/git_helpers.py` (symmetric Windows-timeout
guard in `run_git()`'s `TimeoutExpired` handler; honest docstring boundary
on `_win32_kill_tree()`), `git diff -- lib/git_helpers.py` after my 2 edits
showed 4 hunks, not 2 — two OTHER hunks (narrowing `except Exception:` to
`(OSError, subprocess.SubprocessError)` inside `_win32_kill_tree()` itself,
and to `(ValueError, TypeError)` in `commits_since_last_consolidation()`)
were already present, made by a concurrent agent working the same review
round (confirmed via `git status --porcelain`: 16 files dirty across
`lib/`, `tests/`, and 3 other agents' own `.claude/agent-memory/*` dirs —
Cerberus, Dante, Moriarty memory all mid-edit simultaneously). Nothing was
wrong; multi-agent repair rounds legitimately have several agents editing
the same file in parallel on different findings.

Rule: when asked to "report the exact diff" for a task scoped to N specific
changes, don't paste the raw `git diff` output as if all of it is yours.
Identify each hunk against what you actually changed (I know I wrote
exactly 2 edits — cross-check the diff hunk-by-hunk against that mental
list) and call out explicitly which hunks are mine vs. pre-existing/
concurrent. Reporting an unattributed 4-hunk diff for a 2-fix task would
have been misleading even though `git status --porcelain -- <file>` still
correctly shows only that one file as touched.

## Root pyproject.toml has no [project] requires-python — use [tool.mypy] python_version as the min-version signal for CI

(issue #51, .github/workflows/toolkit-ci.yml) The repo root `pyproject.toml`
only has `[tool.pytest.ini_options]` and `[tool.mypy]` sections — no
`[project]` table, so there's no `requires-python` field to read directly.
`[tool.mypy] python_version = "3.10"` is the only declared version signal in
the whole file; used it for `actions/setup-python`'s `python-version` input.
If this file ever gains a real `[project]` table with `requires-python`,
prefer that over the mypy value (mypy's target can drift from the actual
minimum supported version over time; `requires-python` is the authoritative
field once it exists).

Also: `pytest` itself is not declared as a dependency anywhere in the repo
(no `requirements.txt`, no `[project.dependencies]`) — it's assumed present
in the dev environment. CI must `pip install pytest` explicitly; don't skip
this step assuming it's preinstalled on GitHub-hosted runners (it usually
isn't the exact version the local suite was validated against).

Cosmetic non-issue confirmed while validating YAML: `yaml.safe_load()` on
ANY GitHub Actions workflow file (including the pre-existing
`chatroom-ci.yml`) turns the `on:` key into the Python boolean `True` (YAML
1.1 treats bare `on`/`off`/`yes`/`no` as booleans). This is a PyYAML/YAML-spec
quirk, not a workflow bug — GitHub's own parser handles `on:` correctly as
the trigger key. Don't flag it as an error when spot-checking a workflow
file with `python3 -c "import yaml; yaml.safe_load(...)"`.

## boot_git_checks.py: unify on %at (unix epoch), never %aI (ISO-8601), for any git-log date read by time_ago()

CI issue #49 group A (run 28922061708): `get_timeline()`/`get_last_context_time()`
(`lib/boot_git_checks.py`) used `git log --pretty=%h\x1f%s\x1f%aI` + `time_ago()`'s
`datetime.fromisoformat()` branch, while `extract_memory()` (`lib/boot_memory.py`)
already used the robust `%at` (epoch) + `.isdigit()` branch. The two paths agreeing
was accidental, not structural — an older CI runner's git produced an `%aI` string
`fromisoformat()` couldn't parse, silently dropping the `Last: ... | <time_ago>`
suffix (not reproducible locally with git 2.49/Python 3.11; House confirmed the
mechanism, not the exact git-version trigger). Fix: switch both call sites to
`%at`, add explicit `"HEAD"` + trailing `"--"` (matching `extract_memory()`'s own
SEC-CRIT-001 positional-arg-hygiene shape), and let `time_ago()`'s existing
`.isdigit()` branch do the parsing — the two readers now agree by construction,
not by coincidence. Rule: any NEW git-log date read in this codebase should default
to `%at`, never `%aI` — grep for `%aI` before adding one.

**Observability side-fix**: `git_helpers.run_git()` unconditionally discarded
`stderr` (`stdout, _stderr = proc.communicate(...)`), so a future git-level
failure on this same read path would be a silent empty result with zero
breadcrumb. Did NOT make this print unconditionally on every non-zero exit —
run_git's non-zero exit is an EXPECTED outcome at a great many call sites (no
upstream configured, detached HEAD, etc.) and blanket-printing would be log
noise plus a real risk of breaking existing "silent on expected failure" test
assertions (`test_boot_freshness_hardening.py`'s `test_*_is_silent` tests check
`captured.err` for absence of specific words). Instead added an opt-in
`log_stderr_on_failure: bool = False` parameter (default preserves 100% of old
behavior for every pre-existing call site) and only passed `True` from the two
call sites actually being hardened. Pattern for future "surface previously
silent stderr" asks on a widely-shared helper: opt-in parameter, not a global
behavior change.

**Environment note**: this session ran on a shared dev machine with a
DIFFERENT concurrent agent (House, mid-writing its own memory file, plus what
looked like an automated encoding-hardening pass touching many `tests/*.py`
files with `encoding="utf-8"` additions) actively modifying the SAME working
tree at the same time. This produced a transient, self-resolving
`ast.parse()` SyntaxError in `tests/test_security_regression.py` (an orphaned
`, encoding="utf-8"` line from an in-flight edit) that was gone by the next
read moments later — a real race, not a bug to fix. When `git status`/full-
suite pytest shows unexpected dirty test files or a fleeting collection
error you didn't cause, check for concurrent agent activity (other python/
pytest PIDs via `wmic process where "name='python.exe'" get ProcessId,CommandLine`)
before assuming your own change broke something.

## Issue #53 (reject_hardlinks opt-in param): a fixed-signature monkeypatch stub breaks the instant a new opt-in kwarg is activated at its call site

Adding `reject_hardlinks: bool = False` to both `open_no_follow_symlink()`
twins (git_helpers.py / _symlink_safe_open.py) and activating
`reject_hardlinks=True` at 3 toolkit-generated-only call sites
(session-start-boot.py's `write_boot_log()`, boot_glossary_cache.py's read
+ write, user-prompt-memory-check.py's booted_flag) is purely additive for
every call site that keeps calling with the OLD 3-arg shape — confirmed via
the full contract suite (18/18 green) and the full existing symlink-guard
regression suite (65 passed, 64 skipped, zero change). But the full-suite
run still surfaced 2 regressions: `test_boot_output.py`'s
`_run_boot_with_failing_log_write()` helper injects a hand-written
subprocess-script monkeypatch `def _raise_permission_error(path, mode="w",
encoding="utf-8"): raise PermissionError(...)` assigned directly onto
`boot.open_no_follow_symlink`. That stub has a FIXED 3-parameter signature
with no `**kwargs` catch-all — the instant `write_boot_log()` calls it with
a 4th argument (`reject_hardlinks=True`, keyword or positional, doesn't
matter — the stub only declares 3 params total), Python raises `TypeError:
_raise_permission_error() got an unexpected keyword argument
'reject_hardlinks'` INSTEAD of the intended `PermissionError`, which two
tests (`TestBootLogWriteFailureFallback`,
`TestBootLogWriteFailureLogsWarning`) depend on to exercise the "log write
failed" fallback path. Confirmed isolated (grepped the whole test suite for
`.open_no_follow_symlink = ` and `_raise_permission_error` — exactly one
stub, exactly matching the 2 failures) — not a production bug, not a wider
pattern.

Rule: whenever adding a new opt-in parameter to a widely-shared helper and
activating it at specific call sites, grep the WHOLE test suite for
`<helper_name>\s*=\s*` (module-attribute monkeypatch assignment, not just
`mock.patch`/`monkeypatch.setattr` calls) before declaring "zero
regressions" — a hand-rolled stub function with a fixed positional/keyword
signature and no `**kwargs` is invisible to a simple call-site grep and
only surfaces as a `TypeError` deep in a subprocess's stderr. This is
Dante/test-file territory to fix (`def _raise_permission_error(path,
mode="w", encoding="utf-8", **kwargs)` — one line, no assertion changes)
— per test-first mode's "never touch tests, report instead" rule, escalate
this instead of patching it yourself, even though it's a different file
than the actual Dante contract for the issue.

**Follow-up (SEC-HIGH-001, issue #53 extension, session 2026-07-09):** Argus
found 3 MORE manifest.json write call sites missing `reject_hardlinks=True`
— `lib/install_apply.py:276` (`_create_manifest()`), `bin/git-memory-
upgrade.py:362` (`apply_upgrade()`), `bin/git-memory-doctor.py:517`
(healthcheck write-back). Dante's `tests/test_manifest_hardlink_reject.py`
(3 tests, one per site) went RED→GREEN by adding the kwarg to exactly those
3 lines — no other production code needed (the parameter and its
`st_nlink>1` check already existed from the base F6 fix). `bin/git-memory-
doctor.py`'s call site is a read-then-write pair on the same path
(`open_no_follow_symlink(manifest_path, "r")` at line 514, then `"w")` at
517) — only the write got `reject_hardlinks=True`; the read was left
unguarded on purpose, matching Dante's test docstring which explicitly
scoped the read as "a separate, already-unguarded-by-design call site, out
of scope here" (a hard-link read doesn't corrupt the victim, only a write
does). Rule: when a guarded write follows an unguarded read of the same
path, don't guard the read too just for symmetry — check what the contract
test actually exercises before expanding scope. Full suite: 972 passed, 77
skipped, 0 failed after this round (no `test_release.py`-style flake
surfaced this run).

## Issue #57 round 2e: a shared whitespace-tolerant assertion regex can accidentally count the hook's OWN genuine tags, not just a forged one

`tests/test_control_byte_injection.py::TestUserPromptHookFenceShapeInvariantEndToEnd::test_hook_stdout_has_exactly_one_working_fence_close`
uses `_FENCE_SHAPE_RE = re.compile(r"<\s*/?\s*memory-data\s*>", re.IGNORECASE)`
(matches BOTH `<memory-data>` open and `</memory-data>` close) via
`findall()` and asserts `len(matches) <= 1`. But
`hooks/user-prompt-memory-check.py:274-276` always wraps real recall output
in exactly one literal `<memory-data>` ... `</memory-data>` pair — the
hook's OWN genuine wrapper always produces exactly 2 matches for this
shared regex, with zero vulnerability present. Confirmed empirically:
before the structural fix (lib/parsing.py's `sanitize_trailer_value()`),
the forged `</memory-data\x1f>` marker survived and `findall()` returned 3
(open + forged-close + real-close); after the fix (whitespace-tolerant
`<\s*/?\s*memory-data\s*>` fence-removal regex added to
`sanitize_trailer_value()`, see implementation-patterns.md), the forged
marker is correctly neutralized (confirmed in the stdout: "real zorblax
decision text  FAKE SYSTEM..." — double space where the marker used to be)
and the count drops to exactly 2, which is the correct, fully-sanitized
state — but the test's own bound (`<= 1`) can never be satisfied by ANY
correct implementation, since the hook's real wrapper alone is 2 matches.
This is a test-authoring gap (the assertion needed to distinguish "the
hook's own real open+close pair" from "an extra forged one," e.g.
`<= 2` or counting only closing-tag shapes), not a production bug —
verified by reproducing the exact byte-for-byte pre-fix (3 matches) and
post-fix (2 matches) counts via `git stash`/`git stash pop` before
concluding the fix itself was structurally correct. Per test-first mode
rules, did NOT touch the test — escalated with the exact counts instead.
All other 153/154 tests in the file pass, and the full suite (1216 passed,
2 skipped) shows zero other regressions.

## Issue #60 v3: re-base a test's FAILURE-INJECTION TECHNIQUE, never its assertions, when a legitimate identity check invalidates the technique (2026-07-10)

Implementing decision 787b698 (own-stamp identity now includes the real
`git remote get-url` value, not just alias+branch — closes Moriarty's
cross-repo stamp-copy PoC) broke two PRE-EXISTING, non-contract tests that
simulate "the remote breaks" via `git remote set-url origin <bogus-path>`:
`test_boot_freshness.py::TestRateLimitedStampSurvivesRemoteBreakage` and
`test_boot_freshness_hardening.py::test_fetch_failure_returns_failed_with_prior_age`.
Root cause: `git remote set-url` changes the CONFIGURED URL, which under
strict URL identity is itself a mismatch — a different scenario ("remote
reconfigured") than what those tests actually simulate ("the same remote,
now unreachable"). `git remote get-url` never touches the filesystem at
the URL's path; it only reads config. So the fix is to break reachability
WITHOUT changing the configured URL: `shutil.rmtree(bare_remote_path,
ignore_errors=True)` on the local bare-repo directory the URL already
points at, instead of `git remote set-url` to a different nonexistent
path. `git remote get-url` still returns the exact same string (matches
the stamp's stored identity), `git fetch` still fails deterministically
(the directory is gone) — zero assertion changes needed in either test,
only the setup helper's ONE line.

Rule confirmed from a prior round of this SAME issue (see the entry above
this one): in test-first mode, re-basing a NON-contract test's SETUP
MECHANISM (how a scenario is simulated) is in scope for Ultron when a
legitimate design change invalidates that specific technique — this
precedent already existed in this pipeline (commit eb3e554, the v1->v2
GREEN round, edited 3 test files' `os.utime()`-on-FETCH_HEAD seeding to
target the new stamp file instead, with zero assertion changes). What
stays strictly off-limits is: (1) the specific Dante RED contract class
named as protected in the task brief, and (2) any test's ASSERTIONS —
if satisfying the new design requires changing what a test actually
checks (not just how it sets up the scenario), that is a contradiction to
escalate, not silently resolve. Before concluding "this test needs
re-basing," verify algebraically that a same-assertions fix exists (trace
the exact code path the new identity check takes for that setup) — only
then is it a mechanical re-base; if no such fix exists, stop and report
per the earlier entry's rule.

## Two-strictness-level identity check for a locally-written trust stamp (issue #60 v3, decision 787b698)

When a fail-open "own success stamp" file (`.claude/.unmassk/*.json`) needs
an identity check to prevent cross-repo reuse (e.g. copying the file
between two repos that share a common alias/branch convention like
"origin"/"main"), one strict comparison function is not enough if the
SAME identity fields are also useful for a lower-stakes, purely
informational purpose elsewhere. Pattern used in
`lib/boot_fetch_stamp.py`: a shared `_load_own_stamp()` does the
expensive/shared part (symlink-safe read, JSON parse, schema_version
validation) and returns `(data, age)` with NO identity opinion; two thin
callers each apply their own strictness: `_read_own_stamp_age()` (remote +
branch + real URL, ALL must match — the only path allowed to produce a
"rate_limited"/trust-skip-the-real-check result) and
`_read_stamp_age_by_alias_only()` (remote + branch only, deliberately
ignoring URL — used ONLY where the caller's own return status can never
be the trusted/skip-real-check one, so a looser match is safe: it can only
ever improve an already-degraded "unverified, age unknown" message into
"unverified, aged N ago", never grant trust it shouldn't). Document the
asymmetry directly in both functions' docstrings (why the loose one is
safe, and an explicit "do NOT reuse this helper anywhere its result could
feed a rate-limit/trust decision" warning) — this is the kind of
security-relevant design nuance that gets silently violated by future
callers if only implied, not stated.

## run_git's log_stderr_on_failure kwarg breaks several fixed-signature test doubles — use a call-site breadcrumb instead for extract_memory()/extract_glossary()

Issue #61 (House diagnosis, LOW observability): several git_helpers.run_git()
callers collapsed a non-zero git exit code to a silent empty/zero return with
no trace. The precedent fix (boot_git_checks.py's get_timeline()/
get_last_context_time()) is `run_git([...], log_stderr_on_failure=True)` —
run_git itself prints `[git_helpers] git {args[0]!r} exited {rc}: {stderr}`
to stderr when the kwarg is True and rc != 0.

That kwarg is safe to add at most call sites (lib/recall.py's _scan_commits,
lib/git_helpers.py's own commits_since_last_consolidation, lib/
bootstrap_commits.py's scan_recent_commits, hooks/precompact-snapshot.py's
extract_memory_from_log/format_snapshot) — confirmed via full-suite run,
because every test that exercises those functions either calls the REAL
run_git against a real repo, or monkeypatches it with a `**kwargs`-tolerant
signature.

**lib/boot_memory.py's `extract_memory()`/`extract_glossary()` are the
exception.** Four test files (test_crown.py x2, test_boot_output.py x3,
test_crown_retraction.py x1, test_boot_freshness_regression.py x1) load
`session-start-boot.py` in a **fresh subprocess** and monkeypatch
`git_helpers.run_git` with a hand-written stub of the fixed shape
`def _patched_run_git(args, cwd=None): ...` — no `**kwargs` catch-all.
Adding `log_stderr_on_failure=True` to either call in boot_memory.py raises
`TypeError: _patched_run_git() got an unexpected keyword argument` inside
all of those tests (confirmed: 19 of 24 full-suite failures, reproducible,
not a flake). These 4 test files are NOT part of any agent's declared
in-flight edit scope and are off-limits ("no toques tests/") — so the kwarg
approach cannot be used here.

**Fix used instead:** keep the bare `run_git([...])` call (no kwarg) and add
a manual `if code != 0: print(f"[boot_memory] extract_memory(): git log
exited {code}", file=sys.stderr)` immediately after, before the existing
`if code != 0 or not log_output: return {}` gate. Same non-silent-failure
outcome, zero dependency on run_git's signature, so it's immune to any test
double regardless of what kwargs it accepts. `import sys` had to be added to
boot_memory.py's top-level imports (it previously had none).

**Rule:** before adding a new kwarg to a shared `run_git()` (or similar)
call, grep the WHOLE test suite for hand-written stub/monkeypatch functions
of that same name — a fixed positional/keyword signature with no `**kwargs`
will TypeError on any new kwarg, even though the change is 100%
behavior-preserving from the production code's own point of view. Prefer a
call-site-local breadcrumb (no new argument) over a shared-helper kwarg for
call sites proven to be exercised by such stubs.

## git stash conflict when a parallel agent is actively editing the same test files

While iterating on the fix above, `git stash` (to get a clean baseline) then
`git stash pop` failed with "local changes would be overwritten by merge"
on `tests/test_consolidation_trigger.py`, `test_drift.py`, `test_recall.py`
— Dante was running in parallel on those exact 3 files (per the
orchestrator's explicit instruction) and had written NEWER changes to them
during the window the stash was held. Popping blindly risks clobbering
another agent's in-progress work.

**Safe recovery:** do NOT force the pop. Instead
`git checkout stash@{0} -- <only the files you own>` to pull just your own
changes back out of the stash into the working tree (leaves whatever the
other agent has since written to its own files untouched), verify with a
grep for your own marker/comment, then `git stash drop stash@{0}` once
confirmed. Also check the stash for unrelated uncommitted files that existed
before your own edits (in this case a `.claude/agent-memory/.../lessons.md`
from a concurrent House run) — restore those too before dropping, rather
than silently discarding another agent's memory write.

**Rule:** when multiple agents run in parallel and touch the same repo,
avoid `git stash` / `git stash pop` as a "get a clean baseline" trick unless
you're prepared to reconcile file-by-file — `git checkout stash@{0} --
<path>` (selective restore) is safer than a full pop when you don't control
every file that might have changed underneath you.
