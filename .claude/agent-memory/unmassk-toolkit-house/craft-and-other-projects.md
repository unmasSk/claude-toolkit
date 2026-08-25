---
name: craft-and-other-projects
description: Diagnostic method that travels — verification laws, the blind spots of the search tools on this machine, Claude Code forensics — plus the mechanism-level findings from agent-chatroom (in chatroom/) and omawaMapas
metadata:
  type: reference
---

Two halves, both outside "the unmassk-toolkit suite is red" (that lives in
[[toolkit-ci-and-tests]]): the method itself, and the concrete mechanisms proven in the two other
projects. Re-verified against the tree on **2026-08-25**.

# The method

## A gate that has never been shown to fire has not been tested

Any gate shaped *"the search returned zero results, therefore the tree is clean"* is only as
strong as what the searcher was willing to look at. Before trusting one, plant a file that MUST
match, in the least-visible place the gate is supposed to cover, and confirm the gate reports it.

## The search tools on this machine lie by default — verified by planting a marker

CONFIRMED 2026-08-23, re-checked 2026-08-25. `grep` here is **not a binary on PATH**: it is a
shell function injected into the profile that re-execs the `claude` binary as
`ARGV0=ugrep … -G --ignore-files --hidden -I --exclude-dir=.git …`. So `--ignore-files` is forced
and **every `.gitignore`d path is invisible**. `which -a grep` shows the function first, then
`/usr/bin/grep` (BSD 2.6.0-FreeBSD, which behaves differently again); `grep --version` reports
ugrep 7.8.4. Proven by planting `unmassk-toolkit/__house_probe__.pyc` (ignored via
`.gitignore:6 *.pyc`) containing a real marker: the wrapped `grep -rn` found nothing,
`--no-ignore-files` found it, `/usr/bin/grep -rn` found it.

**The same blind spot on the git side, for a different reason:** `git grep --untracked` includes
untracked files but NOT ignored ones — `--no-exclude-standard` is the flag that adds them. So
both halves of a "git grep, else fall back to grep" verification agree on a false clean over any
ignored path: build output, `.venv/`, `dist/`, `node_modules/`, generated code — all ordinary
places to have instrumented something.

**Third tell:** BSD `/usr/bin/grep -rn` over a repo root reports `Binary file …/chatroom.db
matches`, so a zero-results gate then fails for a reason unrelated to what it was checking.
`-I` belongs in any such command. All three facts are why THE CLEANUP CHECK in my own card is
shaped the way it is.

## Answer "where does Claude Code persist X?" from the shipped binary, never from docs

CONFIRMED 2026-08-23 by live files plus disassembly of the running version (2.1.241). The CLI on
macOS is a single Mach-O bundle (`~/.local/share/claude/versions/<ver>`, ~325 MB; `~/.local/bin/
claude` is a symlink) with the JS bundle embedded as plain text. It is greppable and it is the
running implementation, so it outranks any documentation.

1. **Never `grep -ao '.\{300\}PATTERN.\{300\}'` on it** — backtracking over 325 MB times out at
   120 s. In Python: read the whole file, `decode('utf-8','replace')`, `data.find(...)` /
   `re.finditer(re.escape(...))`, then slice `data[i-700:i+900]`. Seconds, not minutes.
2. **Anchor on a distinctive literal, not on a concept** — a constant filename (`".lock"`), a
   schema literal (`hook_event_name:Ct("Stop")`), or `transcript_path` for the hook base schema.
3. Names are minified (`Yoe`, `wJ`, `Gt`) but **string literals and zod field names survive
   verbatim**, which is all a contract question needs.
4. **Corroborate against the live artefact** before trusting the read: count real files against a
   known truth (10 `TaskCreate` calls in the transcript ↔ 10 `.json` files). Binary + live files
   agreeing is confirmed; either alone is a hypothesis.

**The two contracts recovered this way (valid for 2.1.241):**
- Hook stdin base schema `{session_id, transcript_path, cwd, prompt_id?}`, and every event is
  that `.and({hook_event_name, …})`, built by one function that also adds `permission_mode`,
  `agent_id`, `agent_type` — so **every hook event carries `session_id`**, Stop and
  SubagentStop included.
- Task board: `~/.claude/tasks/<listId>/<n>.json`, one file per task, `listId =
  CLAUDE_CODE_TASK_LIST_ID || teamName || sessionId`. Writes are `fs.writeFile` under a directory
  `.lock` — **not** an atomic rename, so an unlocked reader can catch a truncated file. Any hook
  reading it must tolerate a JSON parse error.

**Trap: TodoWrite and the Task\* tools are different systems.** Measuring "the board is never
used" by counting `TodoWrite` tool_use is measuring the wrong tool; the board in use is
`TaskCreate`/`TaskUpdate` under `~/.claude/tasks/`. Project memory carries the same correction
(`M-121`, which supersedes `M-119`), plus `M-117`: TodoWrite has been gone since Claude Code
2.1.233 and comes back only behind an env var — so "`~/.claude/todos/` does not exist" is
version-and-config dependent, not a permanent fact.

## A hook's `updatedInput` cannot be confirmed or denied from the parent transcript

CONFIRMED 2026-07-12, first-party. Two structural facts about
`~/.claude/projects/<proj>/<session>.jsonl`:

1. **Subagent conversations are not in it** (`isSidechain=true` count is 0); subagent I/O goes to
   separate `tasks/<task-id>.output` files. You cannot read a subagent's received prompt there.
2. **The recorded `tool_use.input(Task).prompt` is the model's ORIGINAL, PRE-hook prompt.** The
   hook's `updatedInput` is applied afterwards and is never written back. Across 58 spawns in one
   session the real injected footer appeared in the recorded prompt **0 times**, including for
   agents that demonstrably received it. That is exactly why injection looks like a no-op.

**What actually resolves it:** compare the recorded spawn prompt against what the subagent
ACTUALLY received — cleanest when House itself is the whitelisted subagent and can read its own
live prompt. The delta can only come from the hook, so **injection does propagate**.
**Beware loose grep matches:** an orchestrator quoting the block format as literal task text is a
false positive; anchor on the exact distinctive phrase, and note that `json.dumps` escapes an
em-dash unless `ensure_ascii=False`. And a green test asserting the hook *emits*
`updatedInput.prompt` proves only what the hook emits, never that Claude Code delivers it — an
end-to-end gap no subprocess-level unit test closes.
(The hook of that round, `hooks/pre-task-recall.py`, has since been deleted; the method stands.)

## A signal handed down by another agent is a photograph with a date on it

CONFIRMED 2026-07-19: two "integrity bug" signals sourced from an earlier mapping both described
the PRE-fix state and were already resolved in the committed tree — one was false *now*, the
other named a duplication that had been deleted, not merely unwired. This repo churns via
issue-numbered refactors; a one-to-two-week-old map is often obsolete. **Always read the current
source and `git log` before instrumenting.** The real finding usually shifts to a *different*
mechanism than the one the signal named — in that round the genuine residual gap was write
ATOMICITY (truncate-in-place instead of temp+rename), not the version gate the signal pointed at,
and the codebase already had the atomic idiom in a neighbouring file without applying it there.

## Trace the text that renders, not the string in the code

When a user reports seeing "NOT RESPONSE", do not grep for that literal. Users paraphrase and
truncate what they see, and a component applies formatting on the way out. Start from the symptom
— what visible text renders at each step — and work backward through the data flow.

## Know when static analysis has run out

If every step of a data path reads as logically correct and the bug persists, stop reading and
go to runtime. The 2026-03 instance: a Zustand v5 store using `useSyncExternalStore` with
`Object.is` on selector results, where a new Map reference SHOULD re-render, and every step
checked out. Three hypotheses on static analysis is the ceiling; then instrument the message
handler, profile the component, and read the actual frames on the wire.

# agent-chatroom — lives in this repo at `chatroom/`

Bun + Elysia backend, React/Vite + Zustand frontend. Versions still current on 2026-08-25:
`elysia ^1.4.28`, `zustand ^5.0.12`, `@types/bun ^1.3.10`.

## Bun on Windows: three broken primitives in the same libuv/CreateProcessW layer

CONFIRMED 2026-03-18/25 by empirical testing on Bun 1.3.11.

- **`windowsHide: true` is inversely implemented** — it CREATES a `conhost.exe` console instead
  of suppressing it, for console-subsystem executables (`node.exe`, `claude.exe`); with no flags,
  piped stdio suppresses console allocation on its own. Likely `DETACHED_PROCESS` passed where
  `CREATE_NO_WINDOW` was meant. **Fix applied:** the flag is gone from the source; only a comment
  crediting the diagnosis survives at `apps/backend/src/services/agent-runner.ts:191`.
- **`process.kill(-pid, SIGNAL)`** (negative PID = process group) raises ESRCH on Windows, so any
  orphan-cleanup or group-pause built on it is broken there.
- **`stdin: Uint8Array` may never signal EOF**, so the child reads the prompt, works, and its
  final result event — the last stdout write before exit — can be discarded on forced
  termination. On Unix pipe semantics guarantee the parent still reads it; on Windows they do
  not. Symptom: tool_use events arrive, no agent message follows, "returned no response".
  **Detection:** check whether the subprocess was killed by timeout or exited normally.

**Grandchildren do not inherit any of this:** `claude.exe` internally spawns
`cmd.exe /d /s /c "npx …"` for MCP servers, so even a correct flag would not reach them.
Detect stray consoles with `Get-CimInstance Win32_Process | Where ParentProcessId -eq $PID`.

## WebSocket self-delivery: `ws.publish` excludes the sender, `server.publish` does not

`ws.publish(topic, data)` in Bun/uWebSockets sends to all subscribers EXCEPT the calling socket;
`server.publish` includes it. Elysia's `publishToSelf: true` is inherited from the Bun types but
**not implemented** in v1.4.28. Root cause of "messages not received": a broadcast helper handed
the individual connection where it expected the server instance.
**Detection:** test with two connections — if the other subscriber receives and the sender does
not, this is it. Still worth checking, since the version has not moved.

## SIGSTOP pauses the parent only, and the completion path overwrites the paused state

CONFIRMED 2026-03-21 by runtime test (`ps` showed state `T`). The mechanism works; three separate
bugs sat on top of it: (1) children (MCP servers) stay in state `S` — a process-group signal is
needed, which is why `detached: true` mattered; (2) the timeout runs on wall clock and ignores
the pause, so a 4-minute pause eats 4 of the 5 available minutes; (3) the completion handlers set
Done/Error unconditionally without checking pause state, so status flips back on its own.
**Detection when a control button "does nothing" but the handler demonstrably ran:** is the
process really `T`? are the children stopped? does the timeout fire while paused? does the
completion path check pause state?

## One causal family: React-managed side effects + Vite proxy + Electron terminal → OOM

Four findings from 2026-03-21 that are one chain, not four bugs.

- **The Vite dev proxy masks connection-refused as a slow timeout.** A direct fetch to a dead
  port gets an immediate ECONNREFUSED; through `http-proxy` it becomes a TCP timeout (75 s
  default on macOS). Reconnect backoff maths silently becomes wrong.
- **Overlapping async operations through that proxy amplify resource use.** When backoff delay <
  proxy timeout, attempts overlap; each holds sockets and memory for the full timeout. The RAM/CPU
  spike is proportional to `min(max_attempts, proxy_timeout / backoff_delay)`. Fix is fast-fail
  timeouts on the client, or serialization (abort N before starting N+1).
- **A debounce guard that inspects reconnect state is bypassed by the reconnect timer**, which
  increments the attempt counter before calling connect. If "debounce was added and exhaustion
  persists", this is why: debouncing the entry point is not serializing the work.
- **HMR cascades amplify a side effect owned by `useEffect`.** Backend dies → proxy loses upstream
  → HMR fires → React remounts → effect restarts the connection → it fails → store updates →
  re-render → loop. **Fix: decouple the connection lifecycle from React** — a module-level
  singleton owns connect/reconnect and hooks are passive subscribers, plus a circuit breaker.
- **Where the RAM actually goes:** `concurrently` pipes all child stdio; the flood lands in
  Cursor/VS Code's xterm.js, which retains ALL scrollback in the Electron renderer heap with no
  bound; `pino-pretty` ANSI colouring inflates each line. On ≤16 GB this OOMs.
  **Fix applied:** `chatroom/package.json` `dev` now runs `concurrently --kill-others-on-fail`,
  so killing one process no longer leaves reconnect-looping survivors.

## Before blaming React state for an invisible element, check the clipping ancestry

An absolutely-positioned dropdown inside a container that lacks `position: relative` resolves its
containing block to a distant ancestor with `overflow: hidden`, and renders outside the clip —
present in the DOM, invisible on screen, state entirely correct. Especially common after
refactoring `<input>` to `<textarea>` or reorganising a component hierarchy: the containment
context moves and the positioning CSS does not.
**Check in order:** the element's `position: absolute` → its immediate parent's `position:
relative` → any `overflow: hidden` between parent and containing block.
**Fix applied:** `apps/frontend/src/styles/components/ChatInput.css:5` now carries
`position: relative`.

## `mock.module()` in bun:test leaks into the global module registry

CONFIRMED 2026-03-24 on bun 1.3.11. `mock.module()` replaces entries in the module cache shared
by every test file in the thread, so file A's stub is what file B imports, even though B wanted
the real implementation. **Symptoms:** capture arrays stay empty, DB queries return 0 rows
despite functions that insert, tests pass in isolation and fail in the suite, and ONE file breaks
all the others. **Confirm with** `bun test $(ls tests/**/*.test.ts | grep -v <suspect>)` — 0
failures proves it. **Fix:** the polluting file must not `mock.module()` a module other files
import for real behaviour; mock the individual functions, or inject the dependency.

# omawaMapas

## Phantom tables: code written against a schema that was never migrated

Recorded 2026-03-15. **UNVERIFIED since** — omawaMapas is a separate repository (present at
`~/Workspace/omawaMapas`) that I did not open during the 2026-08-25 compaction pass, so the list
of affected tables below is a photograph of that date, not current state.

Code referenced tables absent from `schema.sql` and from every migration: singular/plural
mismatches (`usuarios` vs `usuario`, `inventario` vs `inventario_amianto`) and six with no
`CREATE TABLE` anywhere (`layer_permissions`, `spatial_layers`, `supervisor_municipio`,
`operador_municipio`, `capa`, `eventos`). `schema.sql` was a `pg_dump` of the real database; the
modules had been authored by agents against an aspirational future state.

**The durable half — check ALL schema sources before concluding a table is missing:**
(1) `schema.sql`, (2) migration files, which may hold their own `CREATE TABLE`, (3) any
deployment SQL, (4) the migration runner's config. In that project the initial Knex migration was
a **no-op stub** and the deployment SQL matched `schema.sql` exactly, which is what proved the
tables had never been created anywhere. **Detection:** grep `FROM`/`JOIN`/`INTO` + table name,
then diff against the `CREATE TABLE` set.
