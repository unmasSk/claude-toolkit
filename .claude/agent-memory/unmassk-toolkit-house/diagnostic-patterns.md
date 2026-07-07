---
name: diagnostic-patterns
description: Recurring root cause patterns found during investigations in omawamapas and related projects
type: reference
---

## Pattern: CI Runner Has No Git Identity → Test Helpers Silently Swallow `git commit` Failure

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-07-07

Mass boot/memory test failures on GitHub Actions (ubuntu + windows, Python 3.10) with symptoms of "memory content never reaches the boot log": REMEMBER/DECISIONS/TIMELINE sections missing, glossary-cache.json never created (FileNotFoundError), 2200-char giant-commit payload absent, branch-scoped items missing, sanitization tests failing — all *content-absent*, no crashes.

**Root cause:** CI runners have NO git identity (no global/system `user.name`/`user.email`) and git's auto-detect yields `runner@...(none)`, which git rejects → `git commit` exits 128 with "Author identity unknown / unable to auto-detect email address". Test helpers call commits via a `git_cmd`/`run_cmd` wrapper that RETURNS `(rc, out, err)` but callers ignore rc. So the fatal commit is swallowed, the repo ends up with an unborn HEAD (zero commits), and boot (read-only) produces empty output → every content assertion fails with a confusing "missing" symptom instead of a clear git error.

**Why it doesn't reproduce on macOS:** macOS git auto-detects a hostname-based identity (`user@host.local`) and commits succeed (rc=0). Nullifying `GIT_CONFIG_GLOBAL`/`SYSTEM` alone does NOT reproduce — macOS still auto-detects.

**Faithful local reproduction of the CI condition:**
```
printf '[user]\n\tuseConfigOnly = true\n' > /tmp/fakegitconfig
GIT_CONFIG_GLOBAL=/tmp/fakegitconfig GIT_CONFIG_SYSTEM=/dev/null python3 -m pytest tests/test_boot_output.py -q
```
`useConfigOnly=true` with no identity forces git to refuse auto-detection → `git commit` fatal, exactly like the runner. Confirming the fix direction: add `GIT_AUTHOR_NAME/EMAIL` + `GIT_COMMITTER_NAME/EMAIL` env vars → suite goes green under the same fatal config.

**Test-only vs production:** This is a TEST defect, not a production bug. Production commit path (`bin/git-memory-commit.py::_do_commit`) also sets no identity, BUT it checks `returncode != 0` and exits 1 with a loud error — a real user without git identity fails visibly, not silently. Fixing the runner ENV (adding `git config --global user.email` in the workflow) would mask the real defect (helpers ignoring git rc) and is the wrong layer.

**Correct fix layer:** centralize a deterministic git identity for tests — set `GIT_AUTHOR_*`/`GIT_COMMITTER_*` in the shared `run_cmd` merged env in `conftest.py` (applies to every git subprocess regardless of cwd, makes tests hermetic vs the runner's global config). `_make_repo_no_install` already did per-repo `git config user.email/name` (its tests passed); the many helpers that forgot (`make_repo_with_giant_commit`, `make_repo_with_memory`, conftest `tmp_repo`/`installed_repo`, and ~5 other test files) are the blast radius — hence centralize rather than patch each helper.

## Pattern: PYTHONUTF8=1 Masks Windows cp1252 Encoding Defects ("works on my Windows box")

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-07-06

When auditing Windows portability, a machine can report `locale.getpreferredencoding(False) == 'utf-8'` while `locale.getencoding() == 'cp1252'`. That split is the tell that **Python UTF-8 mode is active** (`sys.flags.utf8_mode == 1`, driven by `PYTHONUTF8=1` in the environment). Under UTF-8 mode, `open()` without `encoding=` and `subprocess(..., text=True)` without `encoding=` both default to UTF-8 — so encoding bugs do NOT reproduce on that machine. On a DEFAULT Windows install (no PYTHONUTF8), the same calls default to cp1252 and break: git/gh UTF-8 output (accents, commit emojis) becomes mojibake, and undecodable multi-byte sequences raise `UnicodeDecodeError` — a subclass of `ValueError`, so a wrapper catching `(SubprocessError, OSError, ValueError)` swallows it into a silent failure.

**Detection:** `python -c "import sys,locale;print(sys.flags.utf8_mode, locale.getpreferredencoding(False), locale.getencoding())"`. If utf8_mode=1 with preferred=utf-8 but getencoding=cp1252 → encoding findings are LATENT, not absent. Report them as real defects masked by env config, and do NOT conclude "encoding is fine on Windows" from a single UTF-8-mode box.

**Also confirmed here:** `os.O_NOFOLLOW` — `hasattr(os,'O_NOFOLLOW')` is `False` on win32 (Python 3.11), so any `os.open(..., O_NOFOLLOW)` raises `AttributeError` (NOT `OSError`, so `except OSError` guards do not catch it). An `ImportError`-based fallback to a second copy of the same helper gives zero protection when both copies reference the missing flag. `os.chmod(p,0o600)` / `os.open(p,flags,0o600)` are near-no-ops on Windows (only the read-only bit maps) — any "0o600 = no group/other access regardless of umask" guarantee in the code is FALSE on Windows.

## Pattern: pytest sys.modules Stub Leak Across Test Files (Bare ModuleType Poisons Real Import)

**Project:** unmassk-toolkit (git-memory)
**First seen:** 2026-06-09

A test that stubs a shared module by inserting a bare `types.ModuleType` into `sys.modules` — and only restores `sys.path` in its `finally` (not `sys.modules`) — leaves the stub registered for the entire pytest process. pytest runs all files in one process with a shared `sys.modules`, so a later test that does a real `from <module> import <symbol>` resolves to the stub.

**Concrete instance:** `test_migrate_statusline.py` `_load_migrate_fn()` did:
```python
for stub_name in ("git_helpers", "parsing", "version"):
    if stub_name not in sys.modules:   # guard: only stub if absent
        stub = types.ModuleType(stub_name)
        stub.run_git = ...             # but NOT GIT_TIMEOUT
        sys.modules[stub_name] = stub
try: spec.loader.exec_module(mod)
finally: sys.path[:] = saved          # restores sys.path, NOT sys.modules
```
The stub `git_helpers` survives. Later `test_recall.py` → `from recall import recall` → `recall.py` line 33 `from git_helpers import run_git, GIT_TIMEOUT` resolves to the stub, which lacks `GIT_TIMEOUT`.

**Signature error:** `ImportError: cannot import name 'GIT_TIMEOUT' from 'git_helpers' (unknown location)`. The "(unknown location)" is the tell: a synthetic `ModuleType` has no `__file__`/`__spec__`, so Python reports its origin as unknown — proof the import resolved to a hand-built stub, not the real `lib/git_helpers.py`.

**Detection:**
1. Test passes in isolation, fails in full suite (classic shared-global-state signature).
2. Bisect: `pytest <earlier_file> <failing_file>` for each alphabetically-earlier file until the pair reproduces.
3. The error names a module "from (unknown location)" → look for a test that builds that module via `types.ModuleType(...)` and assigns into `sys.modules`.
4. Check the stub's `finally`: does it restore `sys.modules` or only `sys.path`?
5. The `if stub_name not in sys.modules` guard means the stub is also non-deterministic — whether it leaks depends on whether the real module was imported first by an earlier test.

**Fix pattern (test isolation, not production code):**
- The polluting test must restore `sys.modules` for every name it stubbed. Snapshot the prior entry (or absence) and restore in `finally`, OR use `monkeypatch.setitem(sys.modules, name, stub)` (auto-reverts), OR an autouse fixture that snapshots/restores `sys.modules` + `sys.path` around each test.
- Do NOT "fix" this by making recall.py tolerate a missing GIT_TIMEOUT — that masks the leak and weakens the real import contract.

## Pattern: Schema-Code Divergence (Phantom Tables)

**Project:** omawamapas
**First seen:** 2026-03-15

Code references tables that do not exist in schema.sql or any migration file. Root cause: code was written against an aspirational/planned schema that was never migrated into the database. The schema.sql is a pg_dump of the ACTUAL database; the code was authored (likely by AI agents during audit rounds) assuming tables that would exist in a future state.

**Detection:** grep for FROM/JOIN/INTO + table name, then verify against schema.sql CREATE TABLE statements.

**Affected tables (as of 2026-03-15):**
- `usuarios` (code uses plural; DB has singular `usuario`)
- `layer_permissions` (no CREATE TABLE anywhere)
- `spatial_layers` (no CREATE TABLE anywhere)
- `supervisor_municipio` (no CREATE TABLE anywhere)
- `operador_municipio` (no CREATE TABLE anywhere)
- `inventario` (code uses short form; DB has `inventario_amianto`)
- `capa` (no CREATE TABLE anywhere)
- `eventos` (no CREATE TABLE anywhere)

**Key insight:** The initial Knex migration (`20250507162238_initial_schema_setup.ts`) is a no-op stub (empty up/down). All schema was created via raw SQL (supabase_migration.sql or direct pg_dump). Code modules were built by audit agents without verifying against actual DB state.

## Pattern: ws.publish vs server.publish in Elysia/Bun (Self-Delivery)

**Project:** agent-chatroom
**First seen:** 2026-03-18

`ws.publish(topic, data)` in Bun/uWebSockets sends to all topic subscribers EXCEPT the calling socket. `server.publish(topic, data)` sends to ALL subscribers including the sender. Elysia's `publishToSelf: true` in `.ws()` config does NOT work in v1.4.28 — the option is inherited from Bun types but not implemented by Elysia.

**Root cause:** `broadcastSync()` received `ws` (individual connection) as its `server` parameter, calling `ws.publish()` which by uWebSockets design excludes the sender. The sender never receives their own message back.

**Detection:** When "messages not received" in WS system, check whether publish originates from individual socket or server instance. Test with 2 connections — if other subscriber receives but sender does not, this is the pattern.

## Pattern: Windows CMD Flash from Child-of-Child Process Spawning

**Project:** agent-chatroom
**First seen:** 2026-03-18

`windowsHide: true` in Bun.spawn v1.3.11 is **inversely implemented** on Windows. Instead of suppressing console windows, it CREATES them. Tested empirically:

| Executable | windowsHide: true | No flags | conhost.exe? |
|---|---|---|---|
| node.exe | conhost CREATED | No conhost | BUG |
| claude.exe | conhost CREATED | No conhost | BUG |
| cmd.exe | No conhost | No conhost | No diff |

**Root cause:** When `windowsHide: true` is passed, Bun's libuv integration on Windows passes incorrect `CreateProcessW` flags (likely `DETACHED_PROCESS` instead of `CREATE_NO_WINDOW`), causing console subsystem executables to allocate a new console via `conhost.exe`. Without the flag, piped stdio naturally suppresses console allocation.

**Also found:** `process.kill(-pid, 'SIGTERM')` (negative PID for process group kill) does NOT work on Windows in Bun 1.3.11 (ESRCH error). The FIX 16 orphan cleanup pattern is broken on Windows.

**Secondary factor:** `claude.exe` internally spawns `cmd.exe /d /s /c "npx ..."` for MCP servers. Even if `windowsHide` worked correctly, these grandchild processes would not inherit the flag.

**Detection:** Use `Get-CimInstance Win32_Process | Where ParentProcessId -eq $PID` to check for `conhost.exe` children.

**Fix:** Remove `windowsHide: true` (it does the opposite of what's intended). Remove `detached: true` (process group kill is broken on Windows anyway). Replace orphan cleanup with `proc.kill()` direct call with timeout. The piped stdio (`stdout: 'pipe', stderr: 'pipe'`) already prevents console window creation without any additional flags.

## Pattern: Missing `position: relative` on Dropdown Anchor (CSS Clipping)

**Project:** agent-chatroom
**First seen:** 2026-03-21

Absolutely-positioned dropdown (`.mention-dropdown`) renders inside a container (`.chat-input`) that lacks `position: relative`. The dropdown's containing block falls through to a distant ancestor (`.chat`) that has `position: relative; overflow: hidden`. The dropdown positions itself relative to `.chat` and ends up outside its clipping bounds -- invisible to the user.

**Detection:** When a dropdown "should render but doesn't appear," check:
1. The dropdown's `position: absolute` CSS
2. Whether its immediate parent has `position: relative`
3. Whether any ancestor between parent and containing block has `overflow: hidden`

**Key insight:** The React state and DOM are correct (the element exists in the DOM tree). The issue is purely CSS positioning. DevTools element inspector will show the element exists but is positioned outside visible bounds. This pattern is especially common when refactoring from `<input>` to `<textarea>` or reorganizing component hierarchy -- the CSS containment context changes but the dropdown positioning CSS is not updated.

## Pattern: HMR Cascade Amplification of React-Managed Side Effects

**Project:** agent-chatroom
**First seen:** 2026-03-21

When a side effect (WebSocket, fetch, timer) is managed inside a React `useEffect`, Vite HMR cascades can create unbounded amplification loops. The trigger: backend dies -> Vite proxy loses upstream -> HMR update fires -> React remounts component tree -> `useEffect` restarts the side effect -> side effect fails (backend still down) -> triggers Zustand state updates -> React re-renders -> HMR detects changes -> loop repeats.

**Key factors:**
1. Side effect initiated in `useEffect` (coupled to React lifecycle)
2. Vite dev proxy forwarding to the backend (proxy errors trigger HMR)
3. Each attempt creates Zustand state transitions that trigger re-renders
4. Debounce/backoff guards bypassed during reconnect cycles
5. StrictMode cleanup delays (100ms) designed for double-mount, not rapid HMR

**Detection:** When an Electron host (Cursor, VS Code) shows extreme RAM/CPU after a backend process stops, check whether the frontend has React-lifecycle-managed connections to that backend. Look for `useEffect` + `connect()` patterns in root-level components.

**Fix pattern:** Decouple connection lifecycle from React. Run connect/reconnect as a module-level singleton. React hooks should be passive subscribers (read status), not active controllers (trigger connections). Add circuit breakers on repeated failures.

## Pattern: Concurrently Piped Output -> Electron Terminal OOM

**Project:** agent-chatroom
**First seen:** 2026-03-21

When `concurrently` runs multiple dev processes (backend, frontend, bridge) WITHOUT `--kill-others-on-fail`, killing one process leaves others alive. Surviving processes that have reconnect logic to the dead process produce sustained stderr/stdout floods. Concurrently pipes all child stdio (`['pipe', 'pipe', 'pipe']` in spawn.js). The output flows into Cursor/VS Code's Electron terminal (xterm.js), which retains ALL scrollback in V8 renderer memory without bounds. On machines with <= 16GB RAM this triggers OOM.

**Causal chain:**
1. Backend killed -> concurrently keeps bridge + frontend alive (no --kill-others)
2. Bridge: 20 reconnect attempts, each logging to console.error
3. Frontend: 10 reconnect attempts through Vite proxy (5s timeout per attempt)
4. Vite proxy: logs its own errors for each failed upstream connection
5. Health check loop (10s interval) continues producing proxy errors indefinitely
6. pino-pretty ANSI colorization inflates per-line memory footprint
7. xterm.js scrollback buffer retains everything in Electron renderer heap

**Detection:** When an Electron IDE (Cursor, VS Code) shows extreme RAM after killing a child process in a `concurrently` managed terminal, check: (a) does the concurrently script use --kill-others? (b) do surviving processes have reconnect loops to the dead process? (c) how many console.error/warn calls per reconnect cycle?

**Fix pattern:** Add `--kill-others-on-fail` to the concurrently dev script. Reduce reconnect attempt counts for dev environments. Cap or silence intermediate reconnect log output.

## Pattern: Status Overwrite After Async Subprocess Completion

**Project:** agent-chatroom
**First seen:** 2026-03-21
**Updated:** 2026-03-21 (runtime verification)

SIGSTOP DOES freeze the `claude` process (confirmed: `ps` shows state `T` on PID). However, SIGSTOP does NOT propagate to child processes (MCP servers). And the completion path unconditionally overwrites Paused status.

**Three compounding failures:**
1. **SIGSTOP only stops the parent** — `process.kill(pid, 'SIGSTOP')` targets only the `claude` process. Its children (MCP servers spawned via `npm exec`) remain in state `S` (running). To stop the entire process group: `process.kill(-pid, 'SIGSTOP')` (negative PID = process group signal). This works because `detached: true` gives `claude` its own process group.
2. **Timeout ignores pause** — `makeTimeoutHandle` runs on wall-clock time (5 min). If the agent is paused for 4 minutes, only 1 minute of actual work time remains before the timeout kills it. No mechanism pauses or extends the timeout during SIGSTOP.
3. **Completion path overwrites status** — `handleAgentResult`, `handleFailedResult`, `handleEmptyResult` in `agent-result.ts` and `agent-stream.ts` unconditionally set status to Done/Error without checking `isAgentPaused()`. When the subprocess eventually completes (after SIGCONT, or after timeout kill), status flips from Paused to Done.

**Detection:** When a control button "doesn't work" but the system message confirms the handler ran, check: (a) `ps -o state` on the process — is it actually `T`? (b) are child processes also stopped? (c) does the timeout fire while paused? (d) does the completion path check pause state?

**Key insight:** The SIGSTOP mechanism fundamentally works (confirmed by runtime test). The real bugs are: missing process-group signal, no timeout suspension during pause, and unconditional status overwrite on completion.

## Pattern: bun:test mock.module() Global Leak Across Test Files

**Project:** agent-chatroom
**First seen:** 2026-03-24

`mock.module()` in bun 1.3.11 affects the **global module registry**, not just the declaring test file. When file A mocks `../../src/services/agent-runner.js` with a stub, file B (which imports the real `agent-runner.js` and has its own mock.module for different modules) gets file A's stub instead of the real implementation.

**Root cause:** bun test runs all test files in the same thread with a shared module cache. `mock.module()` replaces entries in this shared cache. Once replaced, ALL subsequent imports of that module path resolve to the mock, regardless of which test file does the importing.

**Symptoms:**
- Mock capture arrays (`_publishCalls`, `_broadcasts`) stay empty
- DB queries return 0 rows despite functions that insert data
- Tests pass in isolation but fail in full suite
- One specific test file causes ALL other mock-dependent tests to fail

**Detection:**
1. Run failing test file in isolation -- if it passes, this is the pattern
2. Binary search: `bun test fileA.test.ts fileB.test.ts` to find the poisoning file
3. Check if the poisoning file mocks a module that OTHER test files import directly (not just transitively)
4. The poisoning file's mock.module replaces the real implementation; downstream files get the stub

**Key test:** `bun test $(ls tests/**/*.test.ts | grep -v <poisoning-file>)` -- if 0 failures, confirmed.

**Fix pattern:** The poisoning test file must NOT use `mock.module()` on modules that other test files import for real behavior. Options:
1. Mock at a higher level (mock the functions, not the module)
2. Use dependency injection so the test can pass stubs without `mock.module`
3. Restructure so the poisoning test uses `jest.fn()`/`mock()` on individual functions rather than replacing entire modules

## Pattern: Bun.spawn stdin:Uint8Array EOF Not Signaled on Windows (Lost Result Event)

**Project:** agent-chatroom
**First seen:** 2026-03-25

When `Bun.spawn` is called with `stdin: Uint8Array` on Windows, the write end of the stdin pipe may not be properly closed after all bytes are written. The subprocess (`claude`) receives the prompt data but never gets an EOF signal on stdin. Combined with the lack of `detached: true` on Windows (disabled due to Bun 1.3.11 bugs), this creates a cascading failure:

1. `claude` CLI reads the prompt from stdin (agent starts working, tool_use events flow)
2. Agent completes tool use and prepares its response
3. The result event is the LAST stdout write before process exit
4. On Windows, forced process termination (timeout kill via `proc.kill()`) or abnormal exit may discard unflushed stdout pipe data
5. The stdout reader sees `done: true` without the result event
6. `handleEmptyResult` fires, posting "Agent X returned no response."

**Key distinction from Unix:** On Unix, pipe semantics guarantee all written data is readable by the parent even after process exit. On Windows, this guarantee does not hold for forced termination. Additionally, on Unix `detached: true` + process group kill (`process.kill(-pid, 'SIGTERM')`) allows graceful shutdown; on Windows, only `proc.kill()` is available.

**Detection:**
1. Agent tool_use events arrive (visible in chat as ToolLine items) but no agent message follows
2. System message "Agent X returned no response." appears
3. Only reproducible on Windows, not Mac/Linux
4. Check pino logs for the `handleEmptyResult` path being hit with `hasResult: false`
5. Check whether the subprocess was killed by timeout vs exited normally

**Compounding factors:**
- `windowsHide: true` bug (already documented above) — shows Bun 1.3.x has systemic Windows CreateProcessW issues
- `process.kill(-pid)` ESRCH on Windows — shows process group management is broken
- These are all in the same Bun libuv/Windows-API integration layer

**Fix approach:** Use `-p` flag with a stdin-fallback pattern: pass a short marker via `-p` and the full prompt via stdin, OR pipe through a shell wrapper that explicitly closes stdin after writing, OR detect the empty-result-after-tool-use condition and retry with `-p` arg directly (truncated to Windows limits).
