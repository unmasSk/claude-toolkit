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
