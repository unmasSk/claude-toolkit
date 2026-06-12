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

Test file: `unmassk-toolkit/tests/test_boot_tombstones.py`

## Cross-File DB Contamination — historyLimit pattern

Tests that insert rows into `_invokerDb` and assert their presence via `buildPrompt` FAIL in the full test suite run because Bun's `mock.module()` persists: another file's `mock.module('../db/connection.js')` overwrites the closure, so `getDb()` returns a different (empty) DB. Safe workaround: assert only structural envelope (markers, trigger content) — never row content — from tests that don't control the DB mock lifecycle end-to-end.
