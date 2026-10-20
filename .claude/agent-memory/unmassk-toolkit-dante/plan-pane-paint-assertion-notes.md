---
name: plan-pane-paint-assertion-notes
description: plan-pane tests read Text paint via plan-kit leavesOf; weight is kept apart from bold
metadata:
  type: project
---
- plan-kit.ts `leavesOf` gives each text run a Paint {color, bold, weight, dim}. `bold` folds bold/semibold; `weight` is the raw Text prop, never derived from `bold` (owner: `bold: true` draws semibold and reads as not bold).
- Assert a label's look with `paintAt(rowOf(tree, title).leaves, title)` + toMatchObject; a "not X" field check goes in its own expect (toMatchObject cannot negate).
- One assertion per owner correction per test: two corrections in one test hide the second red behind the first.
- Run: `claude plugin test unmassk-toolkit` (bun-style runner, ~1 s).
- Live redraw (D-162): `ui.drawn()` on a mounted pane returns the cached frame; it re-renders only after a state change or a mod-requested redraw. `session.clock.advance` drives the mod's `$.clock.every/sleep/after` (mock.clock holds them); `ui.advance` does NOT move `clock.now`. So "ticks on its own" = keep one mount, advance the session clock, read drawn() twice.
- Agents under a step leave the pane once that step is done: read an agent row before ticking its step.
- To probe the testing kit API: rsync the mod into the scratchpad, add a probe *.test.ts, run `claude plugin test .` from the copy's mod root (a file path is rejected).
