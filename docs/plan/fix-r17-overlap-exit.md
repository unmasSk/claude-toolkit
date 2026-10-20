# R.17 overlap exit Plan (task = R.17, no issue)

**Branch:** main (trunk)
**Procedure:** Full
**Build mode:** test-first
**Base:** e228b8e6
**Created:** 2026-10-20

## Goal
A note of any type that resembles another in its zones can be saved: the overlap rejection offers only exits the type accepts, and every type accepts `--replaces none`.

## Decisions
- D-164: `--replaces none` (coexist) is valid for all seven types; `--replaces <id>` stays D, M and R only. The overlap rejection and its relaunch show only exits and fields the type accepts. Discarded: X-156 (skip the gate for Q, X, I, B), X-157 (X accepts `--replaces <id>`).
- M-164: Bilbo's dead-ends (the gate works; the loop is the relaunch text plus `allowed_fields`).

## Out of scope
- The relaunch of a missing required field dropping `--why`/`--keys` (seen 2026-10-20 on an X).
- Threat model: the system against itself (CLAUDE.md). No hostile input.

## Seam
Yes: a note is written by `gitmem note` and read back by `gitmem search` and the indexes.

## Phases

### Phase 3: Fix
**Files:** modify `unmassk-toolkit/lib/memory/validator.py`, `unmassk-toolkit/lib/memory/vocabulary.py` (or wherever `replaces` is allowed), `unmassk-toolkit/bin/memory/note.py` if the `none` sentinel is handled there; keep `bin/memory/remove.py`'s use of `validate_replacement` working. Tests under `unmassk-toolkit/tests/memory/`.
**Steps:**
- [ ] 3.1 Dante: red tests through `gitmem note` — Q, X, I, B overlapping a note bounce with only exits they accept; each saves with `--replaces none`; `--replaces <id>` on Q/X/I/B still rejected; D/M/R unchanged; the relaunch pasted as printed is accepted (or bounces only on the `...` placeholders); round-trip: the saved note is found by `gitmem search` and the index check stays green; `remove`'s new-fence path unchanged.
- [ ] 3.2 Ultron: code until those tests are green.
- [ ] 3.3 Cerberus and Argus on the diff against the base.
- [ ] 3.4 One fix pass (Cerberus and Argus, 2026-10-20): the overlap relaunch carries `--issue` and `--quote`; no `--work no` beside `--issue N`; the issue-gate relaunch carries `--replaces`, `--why`, `--keys`, `--origin` (R.16, taken in: without it the two rejections ping-pong); `Replaces: none` never shows as `(↺ none)` or `sustituye a none`.

### Phase 4: Final round
- [ ] 4.1 Moriarty.
- [ ] 4.2 Fix what he broke.
- [ ] 4.3 Yoda.
- [ ] 4.4 Fix what he named.

### Phase 5: Close
- [ ] 5.1 Alexandria: docs (the memory skill's field table) and CHANGELOG.
- [ ] 5.2 `python3 -m pytest unmassk-toolkit/tests/memory -q` green.
- [x] 5.3 Save the swarm discard: X-155.
- [ ] 5.4 Commit, push, Status COMPLETED.

## Wave map
- Wave 1: 3.1 → 3.2 → 3.3 → 3.4 (one module, sequential by mode)
- Wave 2: 4.1 → 4.2 → 4.3 → 4.4
- Wave 3: 5.1, 5.2 → 5.4
