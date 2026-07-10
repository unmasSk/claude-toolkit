---
name: lessons
description: Failed hypotheses and investigation lessons to avoid repeating dead ends
type: feedback
---

## Lesson: Check ALL schema sources, not just schema.sql

When investigating schema-code divergence, check:
1. schema.sql (pg_dump of actual DB)
2. Migration files (may contain CREATE TABLE)
3. supabase_migration.sql (deployment SQL)
4. The migration runner config (Knex, etc.)

In omawamapas, the Knex migration was a no-op stub, and supabase_migration.sql matched schema.sql exactly. This confirmed that the missing tables were never created anywhere.

## Lesson: Zustand v5 + Map state — static analysis has limits

When investigating "Zustand store updates but component doesn't re-render," the code path (Map replacement, selector comparison, memo check) can appear logically correct at every step. Zustand v5 uses `useSyncExternalStore` with `Object.is` comparison on selector results. A new Map reference SHOULD trigger re-render. If static analysis confirms correctness but the bug persists, the issue requires runtime verification:

1. Add `console.error` in the WS message handler to confirm message arrival
2. Use React DevTools profiler to check if the component re-renders
3. Check Network tab WebSocket frames for the expected messages
4. Add Zustand devtools middleware temporarily

Do not spend more than 3 hypotheses on static analysis when the data flow appears correct. Escalate to runtime investigation.

## Lesson: Always check `overflow: hidden` ancestry for invisible elements

Before assuming a React/state bug when a component "doesn't render," inspect whether the DOM element exists but is visually clipped. CSS `overflow: hidden` on ancestors combined with `position: absolute` on the element can make it invisible while React state is entirely correct. Check with browser DevTools element inspector first.

## Lesson: Vite proxy masks connection-refused as slow timeout

When diagnosing "why does the frontend keep retrying against a dead backend," check whether Vite's dev proxy sits between the fetch and the backend. A direct fetch to a dead port gets an immediate ECONNREFUSED. But Vite's http-proxy converts this to a slow TCP timeout (default 75s on macOS). This means:
1. Reconnect backoff math is wrong — each attempt takes far longer than expected
2. Multiple attempts overlap because the previous one hasn't timed out yet
3. Each pending connection consumes sockets and memory in the host process (Electron/Cursor)

Always add explicit `timeout` to Vite proxy config AND AbortController timeouts on fetch calls that may retry.

## Lesson: Debounce guards that check reconnect state are bypassed by reconnect timers

A debounce guard like `if (reconnectAttempts === 0 && ...) return` protects against HMR-triggered fresh connects but is intentionally bypassed by reconnect timer callbacks (which increment reconnectAttempts before calling connect()). When diagnosing "debounce was added but resource exhaustion persists," check whether the reconnect code path bypasses the debounce. The fix must serialize reconnect attempts (abort previous before starting next) rather than just debouncing entry.

## Lesson: Overlapping async operations through a proxy amplify resource consumption

When backoff delay < proxy TCP timeout, multiple reconnect attempts overlap. Each holds resources (sockets, memory) for the full proxy timeout duration. The visible symptom (RAM/CPU spike) is proportional to `min(max_attempts, proxy_timeout / backoff_delay)` simultaneous connections. The fix requires either (a) fast-fail timeouts on the client side or (b) serialization so attempt N+1 waits for N to complete.

## Lesson: `git.cmd`/`.bat` shim is NOT found by `subprocess.Popen(["git"], shell=False)` on Windows — CreateProcess ignores PATHEXT

**Project:** unmassk-toolkit (git-memory boot, #60) · **Seen:** 2026-07-10 · confirmed from CI run 29122808531 (sha 4b10931)

Round 1 diagnosed the extensionless `fake_bin/git` shim as Windows-invisible (correct) and proposed option B: write `fake_bin/git.cmd = @"<sys.executable>" "<fake_git.py>" %*`, on the DOCTRINE that "bare `["git"]` + PATHEXT finds `git.cmd` before `git.exe`". That doctrine was WRONG and cost a full CI round.

Mechanism (documented CreateProcess semantics, NOT verifiable on macOS — POSIX uses execvp): `subprocess.Popen(["git"]+args, shell=False)` on Windows calls `CreateProcess(lpApplicationName=NULL, lpCommandLine="git ...")`. CreateProcess, when the module name has no extension, appends ONLY `.exe` and searches PATH — it does NOT consult PATHEXT. PATHEXT (.CMD/.BAT/...) is a **cmd.exe / shell / `where` / `shutil.which`** concept, NOT a CreateProcess one. CPython's subprocess with shell=False does NOT call `shutil.which`; it hands the bare name to CreateProcess. Therefore `git.cmd` is as invisible as the extensionless `git` — only `git.exe` (or shell=True, or a full path) is resolvable. Empirical proof in the CI run: `git.cmd` was on PATH yet the fake JSONL log stayed empty AND `test_hung_fetch` returned `'fetched'` (real git.exe ran the fetch), giving the same "fake git was never invoked" signature as round 1.

**Rule for this repo:** to intercept `subprocess.Popen(["git"])` (bare, shell=False) on Windows you need one of: (1) a real `git.exe` wrapper on PATH (distlib launcher — fragile), or (2) intercept at the Python layer (wrap `subprocess.Popen` via a `sitecustomize.py` on PYTHONPATH for subprocess-launched hooks, or `monkeypatch.setattr(subprocess,"Popen",...)` for in-process calls). The Python-layer wrap is cross-platform and can retire the PATH shim entirely. NEVER rely on a `.cmd`/`.bat` shim for a bare-name `Popen`.

## Lesson: "Not X" user reports require tracing the actual displayed text, not the code string

When a user reports seeing "NOT RESPONSE", do not grep for that exact string. Trace what text actually renders in each UI component at each step of the flow. The system message "Agent X returned no response." renders through SystemMessage.tsx with formatting applied — the user may paraphrase or truncate what they see. Start from the symptom (what renders visible text) and work backward through the data flow.
