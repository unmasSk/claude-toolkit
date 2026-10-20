---
name: plan-pane-mod-test-kit-notes
description: #98 mod tests under `claude plugin test`: kit mechanics, bottom-hook answers, what a test cannot see
metadata:
  type: project
---

Mod tests (`*.test.ts`, kit `claude-code/testing`) for the #98 plan pane, in `unmassk-toolkit/tests/plan-pane/`.

- Run with the UNALIASED binary: `/Users/unmassk/.local/bin/claude plugin test <dir>`. The shell alias adds `--dangerously-skip-permissions` and the subcommand refuses ("not run from this spelling").
- With no `modules` key in hooks/hooks.json the runner stops before any test: "no hooks module to load", exit 1. To see per-test RED, copy the plugin to the scratchpad with an empty `register` module.
- One plugin holds both: `hooks` (settings hooks) and `modules` in the same hooks.json validate clean (`claude plugin validate`, 2.1.287); the 10 unquoted-${CLAUDE_PLUGIN_ROOT} warnings predate the mod.
- The test's `on` is the bottom: every `$` call the plugin makes needs a test hook, which answers `{ value: ... }` (ui.open → `{ value: { isPlaced: true } }`); session.start bottom answers `{ cwd }` directly.
- `$.ui.mount` rejects "no implementation for ui.render" when no plugin hook draws that requestId: catches an open-id vs render-id mismatch.
- A plugin hook that throws is skipped and the chain goes on; the test does NOT fail. Error paths that only throw are invisible: assert on what was recorded beneath.
- Pane id/title are not in the decisions (D-149..D-154): tests stay id-agnostic, mounting the id captured from ui.open.

- A test file imports a sibling helper (`import ... from './plan-kit.ts'`); only `*.test.ts` run.
- The test's `$` has NO `state` noun (`$.state.get` is undefined). Read the module's state by hooking `state.get` beneath it and calling `next(e)`: the answer wraps the read, `{ value: { value, version } }`.
- In the module, `$.state.set(ref, value)` takes two arguments; `{...ref, value}` is refused "value is not JSON data".
- Mounting the same requestId twice on one surface rejects: unmount first.
- Any `$` op with no test bottom (e.g. `tool.register`) makes the plugin hook skip from that line on: an earlier test file without that bottom goes red if the module calls it before the act that file checks.
- Agents: drive `$.agent.spawn({ ..., name })` (bottom answers `{ model, agentId }`) and `$.turn.complete({ agentId, answer, durationMs, isAborted, turnId, reason })`. `mock.clock(on)` in the shared start, since one `$.clock` call without it skips the hook.
- Read the drawing as rows (outermost Text/Button text, descendants joined) and assert by document order; Text takes no `key`.
- Prove the tests can go green on a scratchpad module before reporting RED: it caught three test bugs here.
- Test hooks must be registered BEFORE the test's first `$` call (else TypeError), and one event per test only once ("registered twice"): extra bottoms go before `startSession`.
- To make a module's `$` op fail: a test hook that THROWS is skipped and core answers anyway. Answer `{ deny }` instead, from a toggled hook (`box.isBroken`) registered before startSession, flipped after. That is how the plan tool's `.catch` was reached.
- Engine 2.1.287 `$.tool.register` forwards only name/description/inputSchema: `isDeferred` never reaches the event (read in the binary). A test on it stays red on that engine whatever the mod does.
- Test tool placement through `$.tool.describe({ tool, description, isDeferred: true, provider })` with a `tool.describe` bottom answering `isDeferred: true` (registered before startSession). Add a control tool that must stay deferred (kills a dropped matcher) and assert the bottom's description survives (kills a hook that skips `next`).
- `turn.complete` with `reason: 'refusal'` needs a `refusal: { category, explanation }` field (TurnCompleteRefused). Give stopped turns a non-empty partial answer, else "the answer leaked" mutants survive. Mutants: copy the whole `unmassk-toolkit/` dir to the scratchpad and run `claude plugin test unmassk-toolkit` from there.

- Built-in tool calls (D-156 close gate): `$.tool.call({ tool: 'Bash', command })` reaches the kit's bottom `tool.call` (it records into `fellThrough` and denies "reached the bottom"). So "passed untouched" = fellThrough holds exactly `[['Bash', command]]` and the answer is the bottom's; "refused" = own deny + fellThrough empty. The plugin's classic PreToolUse settings hooks (customs.py…) did not interfere in the test run.
- An event the kit already hooks (state.get) can still get a second test hook if it carries a MATCHER (`on('state.get', PLAN_STATE, ...)`), registered before startSession: no "registered twice". A toggled `{ deny }` there makes the module's `$.state.get` reject and reaches its `.catch` (D-156 fail-closed test).
- Writing a test command that contains `git commit -m` through a Bash heredoc trips the customs hook: put such strings in with the Edit tool.

**Why:** first mod in the repo; kit docs live only in the plugin-authoring skill's types file (`declare module 'claude-code/testing'`).
**How to apply:** phases 2-4 of #98 reuse the startSession helper pattern and the scratchpad empty-module trick.

- Look tests (D-158): the kit never paints ("exercises hooks and modules, never a surface's paint"), so an ellipsis cut is tested as the step Text's `wrap` prop in the truncate family (found via `ui.findAll({ type: 'Text', text })`, which returns `props`), OR a self-cut row ending in '…' within bodyColumns. Glyph-agnostic bar reader: count row `n/m`, segments = non-space glyphs on that row or the row before; filled vs pending compared to each other, never to a fixed glyph.
- Done-mark checks go through a kit helper (`isDoneStep`: first glyph in a set, counter row excluded) so a mark change touches one constant, not every test.
