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

**Why:** first mod in the repo; kit docs live only in the plugin-authoring skill's types file (`declare module 'claude-code/testing'`).
**How to apply:** phases 2-4 of #98 reuse the startSession helper pattern and the scratchpad empty-module trick.
