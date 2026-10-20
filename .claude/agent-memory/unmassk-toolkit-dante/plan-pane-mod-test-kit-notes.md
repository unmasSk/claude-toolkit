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

**Why:** first mod in the repo; kit docs live only in the plugin-authoring skill's types file (`declare module 'claude-code/testing'`).
**How to apply:** phases 2-4 of #98 reuse the startSession helper pattern and the scratchpad empty-module trick.
