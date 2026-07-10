---
name: mock-patterns
description: Working mock patterns for Bun test suites (bun:test, ESM, SQLite, WebSocket)
type: project
---

## Database Mock (Bun ESM-safe, chatroom/backend)

Pattern: mock `connection.js` BEFORE imports. Use a persistent in-memory DB for the entire file.

```ts
import { mock } from 'bun:test';
import { Database } from 'bun:sqlite';

const _testDb = new Database(':memory:');
_testDb.exec(`CREATE TABLE IF NOT EXISTS rooms (...); INSERT OR IGNORE INTO rooms ...`);

// MUST be before any import that transitively loads queries.ts
mock.module('./connection.js', () => ({
  getDb: () => _testDb,
}));

// Then import the real query functions
import { insertMessage, getRecentMessages } from './queries.js';
```

Rotate DB per test: use `let currentDb: Database` and replace it in `beforeEach(() => { currentDb = makeDb(); })`. The closure in the mock factory references `currentDb` lazily.

## App Singleton Mock (message-bus.ts broadcast)

`broadcast()` dynamically imports `../index.js` to get the Elysia app. Mock the deep dependency:

```ts
mock.module('../index.js', () => ({
  app: {
    server: {
      publish(topic: string, data: string) { /* capture or no-op */ },
    },
  },
}));
```

DO NOT mock `./message-bus.js` if another test file imports the real `broadcast` function — that will contaminate it.

## Node:fs Mock (agent-registry.ts file-reading path)

```ts
mock.module('node:fs', () => {
  const realFs = require('node:fs');
  return {
    ...realFs,
    existsSync(p: string) { return p === FAKE_DIR ? true : realFs.existsSync(p); },
    readdirSync(p: string) { return p === FAKE_DIR ? fakeFileList : realFs.readdirSync(p); },
    readFileSync(p: string, enc?: string) {
      if (p.startsWith(FAKE_DIR)) return fakeFiles[basename(p)];
      return realFs.readFileSync(p, enc);
    },
  };
});
```

## Config Mock (override env-evaluated constants)

For constants evaluated at import time (like AGENT_DIR), mock the config module or set env before import:

```ts
// Option A: env var before import (works if module reads process.env lazily)
process.env.DB_PATH = '/tmp/test.db';
const { getDb } = await import('./connection.js');

// Option B: mock.module
mock.module('../config.js', () => ({
  ...require('../config.js'),
  AGENT_DIR: '/fake/agents',
}));
```

## Partial Mock of agent-invoker.js (facade module)

When a test file must mock `agent-invoker.js` (because the module under test imports from it),
but other test files rely on the real sanitizePromptContent / pause / resume state:
- Use `require()` inside the mock factory to get real implementations from the split modules.
- Only stub `invokeAgents` / `invokeAgent` (subprocess-spawning paths).

```ts
mock.module('../../src/services/agent-invoker.js', () => {
  const { sanitizePromptContent } = require('../../src/services/agent-prompt.js');
  const sched = require('../../src/services/agent-scheduler.js');
  return {
    invokeAgents: () => {},          // stub — no real subprocess
    invokeAgent: () => {},           // stub — no real subprocess
    pauseInvocations: sched.pauseInvocations,   // real state
    resumeInvocations: sched.resumeInvocations, // real state
    isPaused: sched.isPaused,                   // real state
    clearQueue: sched.clearQueue,               // real state
    sanitizePromptContent,                      // real sanitizer
    scheduleInvocation: sched.scheduleInvocation,
    drainActiveInvocations: sched.drainActiveInvocations,
    drainQueue: sched.drainQueue,
    inFlight: sched.inFlight,
    activeInvocations: sched.activeInvocations,
  };
});
```

NEVER use a simple stub `{ sanitizePromptContent: (s) => s, isPaused: () => false, ... }`
— that replaces the real sanitizer and makes sanitizePromptContent tests fail in the full suite.

## Cross-File Mock Contamination Rule

Bun `mock.module()` persists across test files in the same run. Two rules:
1. If file A mocks `./foo.js`, file B's import of `./foo.js` gets the mock.
2. To avoid contamination: mock the DEEPEST dependency (index.js, not message-bus.js).

## WebSocket Testing (Elysia + bun:test)

```ts
// Spin up real server on port 0
const app = new Elysia().ws('/ws/:roomId', { ... });
await app.listen(0);
const url = `ws://localhost:${app.server!.port}/ws/default`;

// Wait for room_state before doing anything
function openWsReady(url: string, timeoutMs = 2000): Promise<WebSocket> {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(url);
    const t = setTimeout(() => reject(new Error('timeout')), timeoutMs);
    ws.onmessage = (e) => {
      const msg = JSON.parse(e.data);
      if (msg.type === 'room_state') { clearTimeout(t); resolve(ws); }
    };
    ws.onerror = (err) => { clearTimeout(t); reject(err); };
  });
}

// Rate limit key: use ws.id (Bun built-in), NOT upgrade() return data
// upgrade() return value ({ data: { connId } }) does NOT merge into ws.data
```

## Bun spawn subprocess testing

`Bun.spawn` in agent-invoker.ts spawns real `claude -p` processes. These lines (267-479) are NOT unit-testable. Accept the coverage gap — mark in report as "requires real claude binary".

## Rate Limit Isolation for Route Tests

When testing rate-limited routes (e.g. /invite), do NOT import the real `apiRoutes` — it shares module-level `apiBuckets` state with api.test.ts. Instead, spin up an inline Elysia handler with a local `checkRateLimit` function and a local `Map`. Add a `exhaustBucket(key)` helper that sets `tokens: 0` directly, so 429 tests don't need to fire 20+ real requests.

## Isolated Rate Limit Test Pattern

```ts
const _buckets = new Map<string, { tokens: number; lastRefill: number }>();
function checkRateLimit(key: string): boolean { /* mirror prod logic */ }
function exhaustBucket(key: string): void {
  _buckets.set(key, { tokens: 0, lastRefill: Date.now() });
}
```

## Windows-safe fs Mock (agent-registry-fs.test.ts)

When mocking `node:fs` and checking paths against a fake dir, normalize separators:

```ts
existsSync(p: string): boolean {
  if (p.replace(/\\/g, '/') === FAKE_AGENT_DIR.replace(/\\/g, '/')) return true;
  return realFs.existsSync(p);
},
readFileSync(p: string, enc?: string): string | Buffer {
  const normalP = p.replace(/\\/g, '/');
  const normalDir = FAKE_AGENT_DIR.replace(/\\/g, '/');
  const filename = normalP.replace(normalDir + '/', '');
  if (normalP.startsWith(normalDir) && fakeFiles[filename] !== undefined) {
    return fakeFiles[filename];
  }
  return realFs.readFileSync(p, enc);
},
```

## Fake-Agent Pattern for Fire-and-Forget Tests

When testing `invokeAgents` / `invokeAgent` public API shape, use a name that does NOT
exist in any real agent registry (e.g. `'golden-nonexistent-agent'`). This causes
`doInvoke` to exit immediately via the "Unknown agent" guard without spawning a real
`claude` subprocess. Using a real agent name (like `'bilbo'`) triggers a real subprocess
and can cause `drainActiveInvocations` tests to time out (5s Bun default).

Downstream tests that call `drainActiveInvocations` after invokeAgents: add a
`await tick(80)` before drain to flush any async cleanup from fake-agent early exits.

## Fake ReadableStream for agent-stream.ts tests

To test `readAgentStream` without spawning a real subprocess, build a fake `proc` object:

```ts
// Stdout: empty (signals done immediately)
const emptyStream = new ReadableStream<Uint8Array>({ pull(c) { c.close(); } });

// Stderr: throws on first read (exercises the catch path in readStderr())
const throwingStream = new ReadableStream<Uint8Array>({ pull() { throw new Error('io error'); } });

const proc = {
  stdout: emptyStream,
  stderr: throwingStream,
  exited: Promise.resolve(0),
  pid: 99999,
};
const handle = setTimeout(() => {}, 30_000); // real handle — readAgentStream clears it
const result = await readAgentStream(proc, 'agent', 'roomId', handle);
// result.stderrOutput === '' — readStderr catches and swallows the error
```

Key: `readStderr()` catches any thrown value (Error or non-Error) and sets `stderrOutput = ''`.
The outer `readAgentStream` does NOT propagate the exception — it always returns an AgentStreamResult.

## E2E WS chain test — real wsRoutes + real auth tokens

To test the full upgrade → message → broadcast → invokeAgents chain:

1. mock `db/connection.js` (in-memory SQLite)
2. mock `index.js` (stub `server.publish` for message-bus.broadcast)
3. mock `agent-invoker.js` with partial stub (capture `invokeAgents` calls, real state functions)
4. Spin up `new Elysia().use(wsRoutes)` on port 0 — do NOT import `index.ts` (starts real server)
5. Call `issueToken(name)` to get a real auth token, append `?token=...` to WS URL
6. Bun WS client sends no Origin header → `''` matches WS_ALLOWED_ORIGINS in test mode (NODE_ENV=test adds `''`)

**user_list_update timing**: `registerConnection()` broadcasts `user_list_update` BEFORE
`sendInitialState()` sends `room_state`. Skip `user_list_update` in message collectors.

**invokeAgents signature**: `invokeAgents(roomId, mentions: Set<string>, triggerContent, Map, boolean)` —
the stub receives mentions as a Set but can be spread: `_invokeAgentsCalls.push({ mentions: [...mentions] })`.

## Stop Hook — Freno Duro (decision:block) Pattern

Para Stop hooks que BLOQUEAN (a diferencia de los advisory que solo usan stderr):

```python
# Bloquear: JSON a stdout + exit 0
json.dump({"decision": "block", "reason": "..."}, sys.stdout)
sys.stdout.flush()
sys.exit(0)  # siempre 0 — el bloqueo se comunica vía JSON, no vía exit code

# Permitir: sin output a stdout + exit 0 (o stdout vacío)
sys.exit(0)
```

Invariante de freno duro FAIL-OPEN (contrasta con pre-merge-gate que falla CERRADO):
- Bug del hook → deja pasar (fail-open). Nunca atrapar al usuario sin poder cerrar sesión.
- Config ilegible, binario no encontrado, timeout → todos fail-open.
- Solo bloquea en el camino feliz explícito: config presente + test_command + tests fallidos.

Test de metacaracteres (shell=False vs shell=True):
- Crear fichero centinela que solo existiría si se expande subshell.
- Verificar que el fichero NO existe después de correr el hook.
- Si existe → el hook usa shell=True → inyección confirmada.

```python
sentinel = os.path.join(workdir, "injected.txt")
_write_config(workdir, {"test_command": f"python3 -c pass $(python3 -c \"open('{sentinel}','w').close()\")"})
_run_hook(workdir)
assert not os.path.exists(sentinel), "shell=True detectado — vulnerabilidad de inyección"
```

## Python Pytest — Hook Subprocess Testing Pattern

Hooks under `unmassk-toolkit/hooks/` are tested as subprocesses via `conftest.run_cmd`.
Conftest is in `unmassk-toolkit/tests/conftest.py`. Key helpers:

```python
# Run hook with JSON stdin (mirrors Claude Code's invocation contract):
rc, stdout, stderr = run_cmd([sys.executable, HOOK_PATH], cwd=repo, input_text=json_str)
parsed = json.loads(stdout)
hso = parsed.get("hookSpecificOutput", {})

# Or use the _run_hook() helper defined in the test file (wraps run_cmd):
rc, parsed, raw_stdout, stderr = _run_hook(repo, "Task", tool_input_dict)
```

`SOURCE_ROOT` = `unmassk-toolkit/` dir. `HOOKS_DIR` = `unmassk-toolkit/hooks/`. `LIB_DIR` = `unmassk-toolkit/lib/`.

For `recall()` calls in helper functions, pass `_repo_dir=repo` — do NOT use the default (which resolves git root of the real project repo).

### Fail-open invariant pattern (deny/block test)
```python
output_str = json.dumps(json.loads(stdout))
assert "deny" not in output_str.lower()
assert "block" not in output_str.lower()
```

## Python Hook — importlib Direct Import Pattern (not subprocess)

When testing a single function inside a hook file (not the full hook via subprocess),
import with `importlib.util.spec_from_file_location` — avoids the sys.modules collision
risk of `importlib.import_module` and the global pollution of `exec()`.

```python
import importlib.util

HOOKS_DIR = os.path.join(SOURCE_ROOT, "hooks")

def _import_hook(monkeypatch):
    monkeypatch.syspath_prepend(HOOKS_DIR)
    monkeypatch.syspath_prepend(os.path.join(SOURCE_ROOT, "lib"))
    spec = importlib.util.spec_from_file_location("hook_module_name", HOOK_FILE_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
```

Then patch module-level constants AFTER loading:
```python
hook = _import_hook(monkeypatch)
monkeypatch.setattr(hook, "PLUGIN_VERSION", "1.10.0", raising=False)
```

`raising=False` is required when the attribute does not yet exist (pre-implementation, RED tests).

## UserPromptSubmit Hook — "Installed Repo" Fixture Pattern

The `user-prompt-memory-check.py` hook checks `needs_install(root)` and `needs_upgrade(root)`
before reaching the [memory-check] / recall-injection path. Bare `tmp_path` repos fail at
`needs_install` (no CLAUDE.md) and produce `[git-memory-bootstrap]` output instead of
`[memory-check]`. Fix: use `_make_installed_repo()` in tests that need the normal path.

```python
def _make_installed_repo(tmp_path, name="repo"):
    repo = _make_repo(tmp_path, name)
    # 1. CLAUDE.md with both required markers
    with open(os.path.join(repo, "CLAUDE.md"), "w") as f:
        f.write("<!-- BEGIN unmassk-toolkit -->\nContext Checkpoint Commits\n<!-- END unmassk-toolkit -->\n")
    # 2. manifest.json with version == PLUGIN_VERSION (prevents needs_upgrade)
    unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk_dir, exist_ok=True)
    with open(os.path.join(unmassk_dir, "manifest.json"), "w") as f:
        json.dump({"version": _PLUGIN_VERSION}, f)
    # 3. .session-booted flag (already-booted path → [git-memory] root output)
    open(os.path.join(unmassk_dir, ".session-booted"), "w").close()
    return repo
```

`_PLUGIN_VERSION` comes from reading `SOURCE_ROOT/.claude-plugin/plugin.json["version"]`.

Required markers:
- `needs_install`: `"BEGIN unmassk-toolkit"` in CLAUDE.md
- `needs_upgrade` check 1: `"Context Checkpoint Commits"` in managed block, no `"python3 bin/"` 
- `needs_upgrade` check 2: manifest.version == PLUGIN_VERSION → tuple comparison returns False

## UserPromptSubmit Hook — fail-open upgrade monkeypatch pattern

When testing the `try/except` around `subprocess.run` in the upgrade branch, use
`monkeypatch.setattr("subprocess.run", ...)` (module-level, not hook-module-level)
BEFORE calling `hook.main()`. The hook imports `subprocess` lazily inside the try block,
so patching at module level is sufficient.

```python
def _raise_timeout(*args, **kwargs):
    raise subprocess.TimeoutExpired(cmd=args[0], timeout=15)

monkeypatch.setattr("subprocess.run", _raise_timeout)
```

To capture `main()` output for in-process tests, monkeypatch `builtins.print`:

```python
captured = []
monkeypatch.setattr("builtins.print", lambda *a, **kw: captured.append(" ".join(str(x) for x in a)))
try:
    hook.main()
except SystemExit as exc:
    assert exc.code == 0
output = "\n".join(captured)
assert "[memory-check]" in output
```

Always assert both: (1) no exception propagated, (2) `[memory-check]` present in output.
A regression (removing the try/except) would fail condition (1). A regression (wrong output)
would fail condition (2).

## UserPromptSubmit Hook — "needs upgrade" repo fixture

To force `needs_upgrade()` to return True (for testing the upgrade branch), write a CLAUDE.md
with the OLD-STYLE marker `python3 bin/` inside the managed block — this triggers check 1
regardless of manifest version:

```python
with open(os.path.join(repo, "CLAUDE.md"), "w") as f:
    f.write(
        "<!-- BEGIN unmassk-toolkit -->\n"
        "python3 bin/git-memory-install.py\n"
        "<!-- END unmassk-toolkit -->\n"
    )
```

Keep the manifest.json present and version-equal so only check 1 triggers (not check 2).
This isolates the upgrade path from the install path.

## Boot Tombstone Test — Glossary-Path Fixture Pattern

To test that a tombstoned note does NOT reappear via the glossary merge in
`session-start-boot.py`, the fixture must push the original note BEYOND `SCAN_DEPTH=30`
so `extract_memory()` cannot see it, then add the tombstone within the window.

```python
FILLER_COUNT = 35  # > SCAN_DEPTH=30

def _make_installed_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])
    return repo

def _add_filler_commits(repo, count=FILLER_COUNT):
    for i in range(count):
        git_cmd(["commit", "--allow-empty", "-m", f"chore(pad): filler commit {i}"], repo)

# 1. Add the note
git_cmd(["commit", "--allow-empty", "-m", f"🧠 remember(user): ...\n\nRemember: {note_text}"], repo)
# 2. Push beyond SCAN_DEPTH
_add_filler_commits(repo)
# 3. Add tombstone (inside window — extract_memory() sees it)
git_cmd(["commit", "--allow-empty", "-m", f"♻️ chore(gc): gc\n\nResolved-Remember: {note_text}"], repo)
```

The note_text in both commits must be IDENTICAL so normalize() produces the same key.
Use a unique token (e.g. `xyzretired`) to detect reappearance unambiguously.

**Variant: tombstone also outside window (Bug A T1)**  
To test the stricter case where BOTH note AND tombstone are pushed beyond SCAN_DEPTH=30,
add TWO filler batches: one after the note, one after the tombstone.

```python
# 1. note
# 2. _add_filler_commits (35+)  → note exits window
# 3. tombstone
# 4. _add_filler_commits (35+)  → tombstone exits window
```

Both are still within the 500-commit glossary range. extract_memory() sees neither;
the tombstone must still suppress the glossary entry. Test file:
`unmassk-toolkit/tests/test_regression_memory_correctness.py` (TestBugA).

## Precompact Snapshot — has_content guard

`precompact-snapshot.py` only prints the snapshot when `has_content=True`:
`pending OR blockers OR decisions OR memos OR last_context`.  
`remembers` alone do NOT trigger `has_content`.  
When testing Remember behaviour in precompact, add a Decision commit as anchor
to ensure the snapshot is emitted:

```python
git_cmd(["commit", "--allow-empty",
         "-m", "🧭 decision(api): use REST\n\nDecision: REST over GraphQL xyzanchor"], repo)
# Then add remember + tombstone commits
# Verify anchor in output first (setup assertion)
assert "xyzanchor" in output, "Test setup error: snapshot not emitted"
```

Without the anchor, the snapshot is silently skipped and the test passes vacuously.

Test file: `unmassk-toolkit/tests/test_regression_memory_correctness.py` (TestBugB).

## Cross-File DB Contamination — historyLimit pattern

Tests that insert rows into `_invokerDb` and assert their presence via `buildPrompt` FAIL in the full test suite run because Bun's `mock.module()` persists: another file's `mock.module('../db/connection.js')` overwrites the closure, so `getDb()` returns a different (empty) DB. Safe workaround: assert only structural envelope (markers, trigger content) — never row content — from tests that don't control the DB mock lifecycle end-to-end.

## SessionStart hook — subprocess invocation (no stdin)

`session-start-crew.py` takes no stdin — it is a pure SessionStart hook that
reads `CLAUDE.md` from the git root. Invoke via `run_script(HOOK_PATH, repo)`
with NO `input_text`. The `cwd` IS the repo root (hooks call
`git rev-parse --show-toplevel` to find CLAUDE.md).

```python
def _run_hook(repo):
    return run_script(HOOK_PATH, repo)
```

## PostToolUse hook — exit_code must be cast with try/except

`post-validate-commit-trailers.py` receives `tool_output.exit_code` which can be
a non-int (string word, list) from exotic tool outputs. The correct pattern is:

```python
try:
    if exit_code is not None and int(exit_code) != 0:
        sys.exit(0)
except (ValueError, TypeError):
    pass  # treat as success / fail-open
```

Always wrap `int(exit_code)` in try/except in PostToolUse hooks — fail-open on
uncastable values.

## Simulating a not-yet-written Windows code branch from any host OS (no real Windows, no symlink privilege needed)

To contract-test a future `if sys.platform == "win32":` branch before it
exists (test-first pass), patch the GLOBAL singleton attributes the branch
will read — `monkeypatch.setattr(sys, "platform", "win32")`,
`monkeypatch.setattr(os.path, "islink", lambda p: True)`,
`monkeypatch.setattr(os, "lstat", ...)` / `monkeypatch.setattr(os, "fstat",
...)`. Because every module does a plain `import os` / `import sys`, they
all share the same module objects — patching the global attribute once
affects every importer, including modules not yet written. This works
identically whether the test process is real Windows or POSIX CI, and needs
zero real symlink privilege. For `os.lstat`/`os.fstat`, a duck-typed stub
class exposing only `.st_dev`/`.st_ino` is enough — no need to construct a
real `os.stat_result`.

To verify a rejected-path guard "closes the fd, never leaks it" once that
logic exists: wrap `os.open`/`os.close` with spy functions that record every
real fd before delegating to the real implementation, call the target inside
`pytest.raises(OSError)`, then assert `closed_fds == opened_fds` afterward.
Confirmed in `unmassk-toolkit/tests/test_crossplatform_symlink_guard.py`
(Windows/macOS/Linux compat fix, Task 1, session 2026-07-06): `os.O_NOFOLLOW`
does not exist on Windows, so ALL of these tests are RED today via an
unhandled `AttributeError` from the twin functions' unconditional reference
to it — `pytest.raises(OSError)` does not catch `AttributeError`, so it
propagates as the (correct) failure signal without any extra assertion
needed.

For the one thing that genuinely CANNOT be mocked (real kernel-level
O_NOFOLLOW enforcement on a real symlink): use a `real_symlink_capable`
fixture that attempts a real `os.symlink()` in `tmp_path` and calls
`pytest.skip(...)` if it raises `OSError` (confirmed: `[WinError 1314]` on a
Windows box without Developer Mode / SeCreateSymbolicLinkPrivilege) — never
fake kernel symlink-following behavior with a mock and call it equivalent.

## Fake `git` executable on PATH — SUPERSEDED (issue #60 close-out round 2, session 2026-07-10)

**This whole PATH-shimming technique (the POSIX shim below AND the
`git.cmd`/`fake_git.py` Windows variant that used to follow it) is
retired for `lib/git_helpers.py:run_git()`'s exact call shape,
`subprocess.Popen(["git"] + args, shell=False)`.** House confirmed: on
Windows, CreateProcess's PATH search for an extensionless name like "git"
only ever tries appending ".exe" — PATHEXT-based fallback (.COM/.BAT/
.CMD/...) is a cmd.exe behavior, never consulted by CreateProcess
directly. So NEITHER a bare `git` file NOR a `git.cmd` wrapper is ever
found this way; the real git.exe elsewhere on PATH silently wins instead
(confirmed root cause of two separate real Windows CI failures: run
29110579481 for the bare-file shim, then run 29122808531 for the
git.cmd attempt). Replaced by directly patching `subprocess.Popen` itself
(`unmassk-toolkit/tests/_git_intercept.py`, see the new entry below this
one) — invocation-path-independent, no PATH/PATHEXT resolution involved
at all, one shared implementation for both a real boot subprocess AND an
in-process direct call. Kept below for historical context only — do not
copy this pattern for any NEW `subprocess.Popen(["git", ...])`
interception need; use `_git_intercept.make_intercepted_popen()` instead.

To contract-test that a hook's `subprocess.run(["git", ...])` call passes a
specific hardened `env` (e.g. `GIT_TERMINAL_PROMPT=0`, `GIT_SSH_COMMAND` with
`BatchMode=yes`) or respects a short timeout, don't rely on real network
behavior (dead ports, unreachable hosts) — sandboxed test environments may
not allow arbitrary outbound sockets, and real-network timing is inherently
flaky. Instead, write a fake `git` executable (a `#!/usr/bin/env python3`
script literally named `git`, `chmod 0o755`) into a scratch dir, prepend that
dir to `PATH` for the subprocess call under test. The fake script:
1. Logs every invocation (`sys.argv[1:]` + `dict(os.environ)`) to a JSONL
   file — this captures the EXACT env the real subprocess call received,
   which is otherwise unobservable from the test process.
2. Passes through to the REAL git binary (resolved via `shutil.which("git")`
   *before* prepending the fake dir, then baked into the fake script as a
   literal string) for every subcommand except the one under test — so the
   rest of the pipeline (rev-parse, log, branch, status, a doctor subprocess
   that itself calls git) keeps working unmodified.
3. Optionally hangs (`time.sleep(N)`) only for the intercepted subcommand,
   to exercise a timeout deterministically without any real network hang.

To prove an env override actually happened (not just "the value looks
right by accident"), POISON the ambient environment before the call with a
value the hardened code must override (e.g. set `GIT_TERMINAL_PROMPT=1` in
the env passed to the subprocess), then assert the fake git's recorded env
shows the hardened value instead. Without poisoning, a test can pass
vacuously if the hardened code never actually sets the var at all (both
"unset" and "already correct by luck" would go unnoticed).

Windows: a bare extensionless `git` file is NOT resolved as an executable
via PATH lookup the way `subprocess.run(["git", ...])` needs (Windows only
searches PATH for entries with a PATHEXT extension — .COM/.EXE/.BAT/.CMD/
...) — a `subprocess.Popen(["git", ...])` on Windows silently skips the
fake and falls through to the real git.exe elsewhere on PATH. This is NOT
a crash/skip signal — it is a silent OBSERVATION blind spot: the boot
under test behaves correctly against the real git, but the fake's JSONL
call log stays empty, so any assertion on that log (`assert fetch_calls`)
fails for the wrong reason, and any assertion of the OPPOSITE shape
(`assert not fetch_calls`) passes VACUOUSLY (confirmed root cause of a
real Windows CI failure, issue #60 close-out, run 29110579481 — 5 tests
failed on `assert fetch_calls` against an empty log, 2 more were
vacuously green on `assert not fetch_calls`). Portable fix (no
`skipif(win32)` needed): on `sys.platform == "win32"`, write the SAME
Python logging/pass-through body to a `fake_git.py` sidecar file, then
write a `git.cmd` wrapper (`.cmd` IS PATHEXT-resolved) whose one line is
`@"{sys.executable}" "{fake_git_py_path}" %*` — always `sys.executable`
(never a bare `"python"`, which may not exist or resolve to the wrong
interpreter on a given machine), both paths double-quoted (either can
contain spaces). On POSIX, behavior is byte-identical to before (shebang
+ chmod 0o755, no `.cmd`/sidecar).

Confirmed in `unmassk-toolkit/tests/test_boot_freshness.py`
(`_make_fake_git`, feat-boot-freshness contract, session 2026-07-06; made
cross-platform in the issue #60 close-out round, session 2026-07-10) for
the hardened-fetch-env test, the fetch-gate test, and the rate-limit
tests. `tests/test_boot_freshness_hardening.py` imports `_make_fake_git`/
`WINDOWS` from this same module — fix once, both files benefit. See
[feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md).

## Fake `git` that spawns a real grandchild — testing process-group kill without mocking os.killpg

To regression-test that a subprocess wrapper's timeout path (`git_helpers.
run_git`'s `os.killpg(getpgid(pid), SIGKILL)`) kills the WHOLE process
group, not just the direct child, write a fake `git` script (same PATH-
shadowing technique as above) whose body itself calls `subprocess.Popen
(...)` — with NO `start_new_session=True` of its own — to spawn a real
sleeping grandchild (`sys.executable -c "import time; time.sleep(60)"`),
writes the grandchild's pid to a file, then hangs. Because the fake git
was launched by the wrapper under test with `start_new_session=True`, it
already leads a fresh POSIX process group; a child it spawns normally
inherits that SAME group (no explicit setsid needed on either side). Call
the real wrapper with a short `timeout=1`, then poll `os.kill(grandchild_
pid, 0)` for up to ~5s after it returns (`ProcessLookupError` = dead;
`PermissionError` counts as still-alive) to prove the whole tree died —
this observes REAL kernel process-group signal delivery, no `os.killpg`
mock anywhere. Confirmed in
`unmassk-toolkit/tests/test_boot_freshness_regression.py::
TestPosixProcessTreeKillOnTimeout` (session 2026-07-06). POSIX only — the
Windows counterpart (`taskkill /F /T`) has no real-machine way to verify
here; don't substitute a `subprocess.run` mock and call it equivalent (see
[feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)
for the full rationale on why that would be a vacuous test).

## Hardening-pass direct-call testing — when subprocess isolation is NOT needed

Not every real, stably-named `lib/` module function needs the full
subprocess-isolation dance (`_extract_memory()`'s `python3 -c` snippet
pattern above). Three cheaper patterns, all confirmed safe in
`test_boot_freshness_hardening.py` (session 2026-07-06):

1. **Pure functions** (no I/O, no git, no module-level mutable state) —
   import the real module directly at the top of the test file (`import
   boot_git_checks`, `import boot_memory`) and call the function in-process.
   Safe even though these are the same stably-named modules the
   sys.modules-stub-contamination warning above targets, BECAUSE the
   contamination risk only bites module-level `from x import y` bindings
   evaluated once at first import — a pure function with no such imports in
   its own call chain has nothing to go stale.
2. **Functions taking an explicit path param** (e.g. `fetch_memory_ref
   (project_root)`, `_has_toolkit_memory(project_root)`) — call directly
   with a real `tmp_path` repo, no chdir needed at all; the function's own
   `run_git(..., cwd=project_root)` calls already scope everything.
3. **Functions relying on ambient process cwd** (no `cwd=` passed to their
   own `run_git` calls, e.g. `get_ahead_behind(branch)`) — use pytest's
   `monkeypatch.chdir(repo)` fixture, which auto-restores the real cwd after
   the test; safe against cross-test bleed within the same session.

**Gotcha — process-global cache defeats direct calls for one specific
function family:** `lib/boot_glossary_cache.py` has a **module-level
mutable cache**, `_project_root_cache: str | None = None`, set once by
`_get_project_root()` and never invalidated. Any test that calls
`_read_glossary_cache()` / `_write_glossary_cache()` / `extract_glossary_
cached()` directly against a SECOND (different) `tmp_path` repo in the same
pytest process will silently resolve to the FIRST repo's cached root unless
you explicitly reset the global first: `boot_glossary_cache._project_root_
cache = None` before `monkeypatch.chdir(new_repo)` + the call. This is a
lighter fix than `test_security_regression.py`'s full subprocess-per-call
pattern (`_call_write_glossary_cache_fallback`) — reach for the subprocess
version only when the test ALSO needs to patch a defensive-import fallback
(`ensure_runtime_dir = None`) or otherwise needs true process isolation;
for a plain "different repo, different cache file" test, resetting the
global in-process is sufficient and much faster (confirmed: `_resolve_
origin_sha`/`_read_glossary_cache` migration tests, session 2026-07-06).

## Injecting malformed git output to test a fail-open branch (not just non-zero exit)

To exercise a specific parsing branch inside a `lib/` function that calls
`run_git()` MULTIPLE times for different subcommands (so you can't just
monkeypatch the whole function), monkeypatch the single shared
`git_helpers.run_git` attribute with a wrapper that intercepts only the
target subcommand shape (`if args and args[0] == "rev-list" and
"--left-right" in args: return 0, "abc def"`) and delegates everything else
to the REAL `run_git` (saved as `real_run_git = git_helpers.run_git` before
patching). Because the target function does a deferred, function-body
`from git_helpers import run_git`, this takes effect immediately with no
module-reload needed — `monkeypatch.setattr(git_helpers, "run_git", ...)`
auto-restores after the test. This is what found a genuine bug (documented
in [edge-cases.md](edge-cases.md) and
[feat-boot-freshness-contract-notes](feat-boot-freshness-contract-notes.md)):
`get_ahead_behind()`'s `int()` conversion on `rev-list --left-right --count`
output has no try/except, unlike the sibling "wrong token count" fallback
one line below it.

## Forcing a controlled (returncode, stdout, stderr) out of `run_git()` without a real git failure

`lib/git_helpers.py:run_git()` calls `subprocess.Popen(["git"] + args, ...)`
then `proc.communicate(timeout=...)` then reads `proc.returncode`. To test a
branch that only fires on a SPECIFIC exit code + stderr combination (e.g. the
`log_stderr_on_failure` diagnostic-breadcrumb kwarg, issue-driven Cerberus
follow-up, session 2026-07-08) — don't try to make a real git command fail
with a specific stderr string; monkeypatch `subprocess.Popen` itself with a
duck-typed fake:

```python
class _FakeProc:
    def __init__(self, returncode, stdout="", stderr=""):
        self.returncode = returncode
        self.pid = 424242
        self._stdout, self._stderr = stdout, stderr
    def communicate(self, timeout=None):
        return self._stdout, self._stderr

monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: _FakeProc(1, stderr="fatal: x"))
code, out = git_helpers.run_git(["status"], log_stderr_on_failure=True)
```

Patch the `subprocess` module the TEST FILE already imported (`import
subprocess` at file top) — it is the same object in `sys.modules` that
`git_helpers.py`'s own `import subprocess` resolved to, so no need to reach
into `git_helpers.subprocess` specifically. This is the same "patch the
module that owns the callee's globals" principle as the `_write_glossary_
cache()` gotcha in unmassk-toolkit-python-test-conventions.md, just applied
to a stdlib module instead of a project one. Since `run_git()`'s print is
gated by a 4-operand conditional (`log_stderr_on_failure and returncode != 0
and stderr and stderr.strip()`), enumerate all the ways it can flip: flag
True/False/omitted, returncode 0 vs non-zero, stderr empty/whitespace-only/
real text, and the `[:300]` truncation boundary (`"X"*300 in captured.err`
+ `"X"*301 not in captured.err` proves the exact cutoff, not just "some
truncation happened"). Confirmed in
`unmassk-toolkit/tests/test_boot_freshness_hardening.py::
TestRunGitLogStderrOnFailure` (7 tests, all via `capsys` since the print
happens in-process — no subprocess wrapper needed for THIS assertion,
unlike the fake-git-on-PATH pattern above which is for asserting the
*subprocess's own* env/argv).

## Fake `git` that mangles a specific `%`-token to inert literal text — simulating "old git can't expand this directive" without a real ancient git binary

Extends the fake-git-on-PATH pattern above one step further: to reproduce
what happens when an old git release doesn't recognize a specific
pretty-format directive (e.g. `%aI`, ISO-8601 date), rewrite that literal
substring to plain non-`%` text INSIDE any `--pretty=format:` arg before
delegating to the real git binary — since the rewritten text no longer
contains a `%` placeholder, real git emits it verbatim, exactly matching
how an old git emits an unrecognized directive (literally, unexpanded).
This needs no fake-command-logging/hanging machinery, just a 3-line rewrite
loop over `sys.argv[1:]`. Crucially, any OTHER `%` token in the same format
string (e.g. `%at`, unix epoch — much older and universally supported) is
left untouched, so this technique proves a migration fix works: run the
SAME "hostile" PATH against code that has already switched from the
mangled token to the untouched one, and it must produce correct output.
Confirmed in `unmassk-toolkit/tests/test_date_parsing_epoch_contract.py`
(issue #55, session 2026-07-08) reproducing two real degradations end-to-
end: `bin/git-memory-gc.py`'s H2 stale-blocker heuristic
(`if not commit["date"]: continue`) and `bin/git-memory-doctor.py`'s
`check_gc_status()` (both its stale-blocker count and "days since last GC"
figure) silently stop firing when `%aI` can't be expanded, because the
project's own `parse_date()` swallows the resulting `ValueError` to `None`.
Each test runs the real-git control pass FIRST (setup-sanity assertion — a
real backdated commit, via `GIT_AUTHOR_DATE`/`GIT_COMMITTER_DATE` env, must
already trigger the heuristic with unmodified git) before switching PATH to
the mangling fake and asserting the contract still holds.

## Discriminant test to prove a signal moved from file/source X to file/source Y — delete X, assert Y is untouched

When a fix's whole point is "the freshness/state signal must stop coming
from source X (e.g. a file git itself writes as a side effect) and must
come from a new, application-owned source Y instead," a plain "do the
happy-path round trip" test (write via the new mechanism, read it back
immediately) is NOT a real discriminant — it typically already passes
today via the OLD (wrong) mechanism too, since X and Y are both freshly
written at the same moment in the common case. Prove it moved by making
the two sources diverge: after the producing action, **delete or corrupt
X outright** (not age it — genuinely remove it), then re-run the read path
and assert the SAME correct output still comes back. If the code still
secretly depends on X, deleting it flips the observable output (forces a
real recompute / falls back to a different, distinguishable state); if the
signal genuinely lives in Y now, X's disappearance has zero effect.
Confirmed in `test_boot_freshness.py::TestOwnSuccessStampNotFetchHeadMtime::
test_round_trip_own_stamp_survives_fetch_head_deletion` (issue #60
AMENDMENT v2, session 2026-07-10): deleting `.git/FETCH_HEAD` after a real
successful fetch, then re-booting inside the rate-limit window, must still
render "remote (synced ...)" from the new own-stamp source — confirmed RED
against the unfixed code (which forces a real refetch instead, flipping
the status to "fetched"), for exactly the predicted reason.

Companion technique for the SAME family of bug — proving X gets falsely
credited by two independent categories of "ambient touch" the fix must
reject: (a) a FAILED write/side-effect to X (e.g. a failed `git fetch`
still truncates+refreshes `FETCH_HEAD`'s mtime — verified with a bare
shell repro against a nonexistent-path remote BEFORE writing any test,
confirmed real git behavior, not a bug to "fix" in git itself), and (b) a
successful write to X caused by something UNRELATED to the feature (e.g. a
fetch of a totally different, foreign remote, which touches the same
non-per-remote `FETCH_HEAD` file). Both need their own test — a fix that
closes (a) doesn't automatically close (b) and vice versa. See the "Vector
A" / "Vector B" tests in the same class.

## Patching `subprocess.Popen` directly, cross-platform, instead of PATH-shimming "git" — `tests/_git_intercept.py` (issue #60 close-out round 2, session 2026-07-10)

Supersedes the PATH-shim entry above for `lib/git_helpers.py:run_git()`'s
exact call shape (`subprocess.Popen(["git"] + args, shell=False)`; see
that entry for why PATH-shimming can never work here on Windows). Shared
module `unmassk-toolkit/tests/_git_intercept.py` exports
`make_intercepted_popen(real_popen, log_path)`: a Popen-shaped wrapper
that (1) logs every git invocation's `args` (excluding the leading "git"
token — same JSONL shape the old fake-git-on-PATH shim produced, so every
pre-existing `r["args"][0] == "fetch"` assertion needed zero changes) and
`env` actually received, (2) delegates UNCHANGED to the real `Popen` for
everything except one case, (3) for a `git fetch` whose env carries
`FAKE_GIT_FETCH_HANG_SECONDS`, swaps the argv for a REAL
`[sys.executable, "-c", "import time; time.sleep(N)"]` child before
delegating — so `run_git()`'s own `communicate(timeout=...)` and
`os.killpg()`/`_win32_kill_tree()` process-group-kill paths are exercised
against a genuinely hung real process, never synthesized. All other
kwargs (`cwd`, `env`, `stdout`, `stderr`, `creationflags`/
`start_new_session`) pass through untouched, so the killed child is still
the leader of its own process group exactly as before.

Two install vehicles share this one implementation:
1. **Subprocess** (a real boot launched via `tests/conftest.py`'s
   `run_script()`, i.e. `[sys.executable, script]` with no `-S`/`-I`):
   `test_boot_freshness.py::_make_fake_git(tmp_path, log_path)` now
   writes a `sitecustomize.py` (not a `git`/`git.cmd` executable) into a
   scratch dir, self-contained (bakes the absolute `tests/` dir path into
   its own source so it can `import _git_intercept` without any extra
   `sys.path`/`PYTHONPATH` entry beyond itself). The CALLER prepends that
   dir to the child's **`PYTHONPATH`** (never `PATH` — nothing is being
   shadowed anymore) via `_fake_git_env(fake_bin, log_path, extra=None)`,
   which also sets `GIT_INTERCEPT_LOG_PATH` in the child's env. `site`
   imports `sitecustomize.py` automatically at interpreter startup
   (because `run_script()`'s invocation has no `-S`/`-I`), which calls
   `_git_intercept.install_via_env()` — reads `GIT_INTERCEPT_LOG_PATH`
   from `os.environ` and patches `subprocess.Popen` inside the CHILD
   process before `session-start-boot.py`'s own code ever runs.
2. **In-process** (a test calling a `lib/` function directly, e.g.
   `boot_git_checks.fetch_memory_ref()` — no subprocess at all):
   `monkeypatch.setattr(subprocess, "Popen", make_intercepted_popen(subprocess.Popen, log_path))`
   — patches the REAL `subprocess` module's own `Popen` attribute (not
   `git_helpers.subprocess`, not any re-exported reference); works
   regardless of how `git_helpers.py` imported `subprocess` because
   `import subprocess` binds the SAME module object from `sys.modules`,
   and `run_git()`'s `subprocess.Popen(...)` call looks up `.Popen` fresh
   at call time. `pytest`'s `monkeypatch` auto-restores it — no
   `install()`/`uninstall()` bookkeeping needed for this vehicle.
   Confirmed in `test_boot_freshness_hardening.py::TestFetchMemoryRefStates::
   test_hung_fetch_is_bounded_by_timeout_and_returns_failed` (migrated off
   `monkeypatch.setenv("PATH", ...)` this round).

**Populated-log guard for `assert not fetch_calls` tests** — a negative
assertion on the fake-git call log (`assert not fetch_calls`) passes
VACUOUSLY if the interceptor never engaged at all (exactly the blind spot
that caused this whole migration), indistinguishable from a genuine
"correctly skipped" result. Pair every `assert not fetch_calls` with
`assert records` (the log is non-empty overall — the boot always runs
OTHER real git commands regardless of whether it fetches) BEFORE the
narrower fetch-specific check. Verified as a real discriminant, not
decorative, via a live mutation-kill: monkeypatching `_looks_like_git()`
to always return `False` (simulating "interceptor silently never
engages") made all three `assert records`/`assert fetch_calls` guards
fail for exactly the predicted reason (empty log), confirmed byte-for-byte
file restoration afterward via `diff` before re-running the real suite.

**Cross-platform BY CONSTRUCTION, not by a POSIX/Windows branch** — unlike
the old `_make_fake_git()` (which forked into a POSIX shim vs a
`git.cmd`/`fake_git.py` pair based on a `WINDOWS` module constant), the
new `_make_fake_git()` has no platform branch at all: the exact same
`sitecustomize.py`-on-`PYTHONPATH` mechanism, exercised identically on
macOS/Linux/Windows, since `subprocess.Popen` patching never touches OS
executable-resolution machinery. Verification limit (documented, not
silently assumed): local verification here (macOS) exercises this IDENTICAL
code path Windows CI will run — there is no separate Windows branch left
to verify locally. What's still Windows-CI-only: whether `site` truly
imports `sitecustomize.py` from a `PYTHONPATH` entry the same way on a
real Windows Python install (expected per CPython's own `site` module
contract, not previously exercised on a real Windows runner for this
project).
