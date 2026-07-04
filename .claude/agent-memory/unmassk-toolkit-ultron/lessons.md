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
