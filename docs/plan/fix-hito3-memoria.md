# Hito 3 memory fixes Plan (task = issue #105)

**Issue:** #105
**Branch:** main (trunk)
**Procedure:** Full
**Build mode:** test-first
**Base:** 69898f54
**Created:** 2026-10-19

## Goal
`gitmem remove`, `note --discard`, replace and promote never lose or leave a note half-retired, and the test suite never writes the owner's real `~/.local/bin/gitmem`.

## Decisions
D-145 (duplicate id → refuse + `--commit`; discard honors replaces/promotes; discards validated first; remove `--replaces`; fake HOME; lifecycle test order-free). Evidence: `.claude/informes/bilbo-2026-10-19-210703-hito3-checks-969f.md`.

## Out of scope
- Preventing duplicate ids (#87, D-116). R-012: ids are never rewritten.
- R.1 (checklist gate and the app's task list) and R.6 (installer commits): pending Bex's decision.
- R.9, R.12: closed without a fix (no real case; R-025).

## Seam
Yes: index files and archive are written and read back by `gitmem search`/boot. Round-trip step 4.1.

## Phases

### Phase 1: remove with a duplicated id, and remove --replaces (#105, R.3)
**Files:** modify `unmassk-toolkit/bin/memory/remove.py`, `unmassk-toolkit/lib/memory/notes.py` (close/replace), `unmassk-toolkit/lib/memory/indexes.py` (remove), `unmassk-toolkit/lib/memory/notes_promote.py` · test `unmassk-toolkit/tests/memory/`
**Steps:**
- [x] 1.1 Dante: red tests — duplicate id refused with the list and nothing touched; `--commit <sha>` archives exactly that one; output says how many were archived; replace/promote refuse a duplicated id; `remove --restriction new --replaces R-x` closes the incident and archives R-x
- [x] 1.2 Ultron: code until 1.1 is green
- [x] 1.3 verify: `python3 -m pytest unmassk-toolkit/tests/memory -q -k "remove or replace or promote"`

### Phase 2: note --discard (R.13, R.7)
**Depends on:** Phase 1 (shares `notes.py`)
**Files:** modify `unmassk-toolkit/bin/memory/note.py`, `unmassk-toolkit/lib/memory/notes.py` (discard_alternatives) · test `unmassk-toolkit/tests/memory/`
**Steps:**
- [x] 2.1 Dante: red tests — `--discard` with `--replaces` archives the old note; with `--promotes` promotes; an invalid discard writes nothing at all
- [x] 2.2 Ultron: code until 2.1 is green
- [x] 2.3 verify: `python3 -m pytest unmassk-toolkit/tests/memory -q -k "discard or note"`

### Phase 3: tests never touch the real HOME (R.2, R.5)
**Files:** modify `unmassk-toolkit/tests/conftest.py`, `unmassk-toolkit/tests/test_lifecycle.py`
**Steps:**
- [x] 3.1 Dante: autouse fake HOME for every test; `test_doctor_after_install` passes run alone
- [x] 3.2 verify: the 14 files from Bilbo's report run with a sentinel `~/.local/bin/gitmem` unchanged; `python3 -m pytest unmassk-toolkit/tests/test_lifecycle.py::test_doctor_after_install -q` green

### Phase 4: round trip
- [x] 4.1 Dante: remove/discard write → `gitmem search` and `rezones --verify` read back the expected state (values from the real read, never typed by hand)

### Phase 5: Moriarty fix pass (D-147)
**Files:** boot/health (G1) · remove.py, notes_duplicate.py (G2) · note.py, notes.py, notes_promote.py, validator.py, validator_pointers.py (G3) · tests under tests/memory
- [x] 5.1 Dante: tests reshaped to D-147 (boot alerts on any duplicated id; no twin-reader tests)
- [ ] 5.2 Ultron G1, G2, G3 in parallel until green
- [ ] 5.3 verify: `python3 -m pytest unmassk-toolkit/tests/memory -q`

## Wave map
- Wave 1: Phase 1, Phase 3 (independent files)
- Wave 2: Phase 2 (after Phase 1: `notes.py`)
- Wave 3: Phase 4
