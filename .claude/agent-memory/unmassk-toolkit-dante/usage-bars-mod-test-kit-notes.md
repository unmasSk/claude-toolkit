---
name: usage-bars-mod-test-kit-notes
description: D-165/D-166 usage-bars band tests: kit gotchas for AbovePrompt, session.measure, $.store and a simulated next session
metadata:
  type: project
---

Tests in `unmassk-toolkit/tests/usage-bars/` (kit `usage-kit.ts`, imports leavesOf/shapesOf from `../plan-pane/plan-kit.ts`).

- `hooks.json` `modules` takes ONE entry per plugin (`claude plugin validate` refuses a second): a second mod is imported and registered from the existing module. A new `$.state` key must be declared in the manifest's types contract (`plan-pane-state.d.ts`) or validate fails.
- A test's bottom `ui.render` must return a tree element: `null` is "not a tree element" and the mount rejects. Use `{ type: 'Box', props: {}, children: [] }` as "the engine draws nothing".
- The test's `$` raises `$.session.measure(e)` but needs a bottom echoing `{ changed: e.changed }`; the test's `$` has NO `session.usage` (the mod's call is answered by a bottom `{ value: usage }`).
- `$.store` bottom: own in-memory Map (records writes, toggles a deny) instead of `mock.store`, answering `{ value }`.
- plan-pane's 1 s `clock.every` caps `clock.advance` at 10,000 waits per call: keep an advance to about 2 h.
- `console.log` in a test prints nothing: probe by putting the value in an expect message.
- Next session simulated: matcher hooks `state.get {plugin}` answer `{ value: { value: undefined, version: 0 } }` while a flag is on, and `state.set {plugin}` turns the flag off; the store is kept or cleared. The "nothing stored -> nothing drawn" test kills a module-variable implementation.
- The band is read as a stream of leaves: block = label to next label; percent = first `N %`; terminal fill = cells equal to the first cell; desktop fill from rects (track + fill, or one rect per cell).

**Why:** first AbovePrompt mod in the repo; each gotcha cost a probe run.
**How to apply:** reuse for any band/measure mod; prove green on a scratch candidate before reporting RED.
