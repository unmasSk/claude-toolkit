# Plan pane Plan (task = issue #98)

**Issue:** #98
**Branch:** main (trunk)
**Procedure:** Short (D-155; was Full)
**Build mode:** test-first
**Base:** c81f1d08
**Created:** 2026-10-20

## Goal
A mod shipped with the toolkit draws, in a right side pane of the desktop app, the current task whole (issue or plain request, phases, steps), ticking each step as it ends, with the agents only under the step in progress.

## Decisions
D-149 (own mod, gate reads the same list later), D-150 (whole task plus each agent's work), D-151 (layout: task, phases, steps; agents only in the step in progress; finished steps fold to a tick with their rounds), D-152 (work with no issue is a plain task titled by the request), D-153 (a finished task stays until the next starts, then folds to one line), D-154 (pane first, gate second). Research: M-159, M-161; Bilbo reports `bilbo-2026-10-20-120000-live-plan-mods-7c3e.md`, `bilbo-2026-10-20-071205-checklist-gate-map-959a.md`.

## Out of scope
- Delivery 2: the checklist gate reading this list (R.1), its own plan after this one.
- #84 (timings shown at the next boot).
- Mods run with the owner's permissions, unsandboxed: nothing in the mod runs processes or touches the network.

## Seam
Yes: what the model sends to the mod's plan tool is kept in the mod's state and read back by the pane's drawing. Round-trip step 4.1.

## Phases

### Phase 1: the mod loads and opens an empty pane
**Files:** create the mod (manifest, hooks module, types contract) inside `unmassk-toolkit/`, or as its own plugin of the marketplace if one plugin cannot hold both settings hooks and a hooks module (decided by `claude plugin validate`, recorded as a decision)
- [x] 1.1 Dante: test that the module registers and the pane opens on `session.start`
- [x] 1.2 Ultron: skeleton until green; `claude plugin validate` clean
- [x] 1.3 verify: `claude plugin test <mod>` green

### Phase 2: the plan tool and the pane
**Depends on:** Phase 1
- [x] 2.1 Dante: tests for a plan tool the model calls (whole task: title, issue or none, phases, steps; and step status changes) and for the drawn tree (D-151, D-152)
- [x] 2.2 Ultron: tool, state and drawing until green
- [x] 2.3 verify: `claude plugin test <mod>` green

### Phase 3: agents in the step in progress
**Depends on:** Phase 2
- [x] 3.1 Dante: tests that each agent launched while a step is in progress shows under it with result and time, fix rounds counted, and disappears when the step ends (D-151)
- [x] 3.2 Ultron: agent tracking until green
- [x] 3.3 verify: `claude plugin test <mod>` green

### Phase 4: finished tasks and the round trip
**Depends on:** Phase 3
- [x] 4.1 Dante: round trip — plan tool input → state → drawn tree, expected values from the real read; a finished task folds to one line when the next starts (D-153)
- [x] 4.2 Ultron: fold until green

### Phase 5: Claude uses it
**Depends on:** Phase 2
- [ ] 5.1 Orchestrator: core and flow tell Claude to send every multi-step task to the pane before starting and to tick each step as it ends; show Bex the diff
- [ ] 5.2 verify through the owner's door: a fresh desktop session doing a real task shows it in the pane, step by step

## Wave map
- Wave 1: Phase 1
- Wave 2: Phase 2
- Wave 3: Phase 3, Phase 5 (independent files)
- Wave 4: Phase 4
