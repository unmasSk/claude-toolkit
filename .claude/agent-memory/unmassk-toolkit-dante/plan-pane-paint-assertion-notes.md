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
- Duration format (D-162: `45s` / `12m 05s` / `1h 12m`) is pinned in two kit exports, `took(text)` and `DURATION` (moved into plan-kit with `drawn` and `Surface`, 2026-10-20: never re-copy them into a test file), plus literal strings. A running step's time must be weight 'bold' like its label (test in plan-colours). The task row total uses the same formatter. To split format-RED from live-time-RED, run a scratch copy with only `formatDuration` swapped: what stays red is the live tick.
- `rightColumnOf` lives in plan-kit (moved from plan-durations, 2026-10-20); it also returns `node`, so compare `.text`/`.dim`, never toEqual the whole object. Task title-row total tests: plan-task-total.test.ts.
- session-start.test.ts mounts with NO clock bottom: a render that reads `$.clock.now()` on an empty plan skips the hook and breaks it. Read the clock only when a task is running.
- A task total must also tick between steps (no step in progress): the render's `isTicking` gate gives now=0 there; a test with one step done and the next not started kills it.
- To probe the testing kit API: rsync the mod into the scratchpad, add a probe *.test.ts, run `claude plugin test .` from the copy's mod root (a file path is rejected).
