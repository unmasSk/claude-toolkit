---
name: overlap-exit-every-type-d164-contract-notes
description: R.17/D-164 overlap-bounce exits per type RED contract; relaunch drops --work for Q/I; M relaunch gets --why
metadata:
  type: project
---

R.17 step 3.1 (2026-10-20), test-first, file `tests/memory/test_note_overlap_exit_every_type.py`.

- Overlap gate (`similar.find_overlapping`) ignores type: seed an old note of the SAME type with a near-identical headline + same description, then bounce the new one. Jaccard well over 0.5.
- Every type needs its own pre-gate answer or it bounces earlier: D `--why`, M `--stops no`, R `--stops yes`, Q/I `--work no`, B `--awaits`.
- The overlap relaunch never carries `--work`/`--issue`/`--quote` (carry_answer_flags only does stops/origin/replaces/awaits/keys): a pasted Q/I relaunch bounces on the issue gate. Not R.16 (that is the gate's own relaunch).
- The overlap relaunch puts `--why "..."` on every type, M included: pasting an M relaunch bounces "why not allowed". D-164 "only fields the type accepts" covers it.
- Fill `"..."` holes per flag (presave_searched_fix_support._fill_holes pattern); relaunch lines are only those after the last `Relanza:`.
- Index check = `gitmem rezones --verify` rc 0. remove's fence overlap path is already guarded by test_remove_replaces_guard_contract.py.
- Expected per-type tables (who replaces by id, who takes --why, index file) typed by hand from D-164, never read from vocabulary.TYPES (the code under change).

R.17 step 3.4 (2026-10-20), files `test_note_overlap_relaunch_issue_carry.py`, `test_replaces_none_not_shown_as_pointer.py`.
- Gate order in note.py: pain -> issue gate -> validate_issue (gh) -> validate_note (fields, overlap). A gate bounce never reaches overlap, so `--origin` with a nonexistent id is fine for carry checks.
- Fake `gh` as a pytest fixture returning an env dict (`{"PATH": fake + pathsep + path_without_real_gh()}`); skip win32 module-wide.
- Issue-gate relaunch prints several `gitmem note` lines: assert per line, pick the `--work no` one to paste.
- Zone view renders D/X as clusters with NO `(↺ id)` mark; the word search shows `(↺ id)` for every type. Use word search for the positive control.
- `Issue: #N` and `Quote` show in `search --id`: the round-trip read.

R.17 step 4.2 (2026-10-20), Moriarty fix pass: `relaunch_fidelity_support.py` + 4 test files (`test_*_saves_what_was_given.py`, `test_replaces_none_spelling_and_cluster_child.py`, `test_remove_fence_overlaps_its_own_incident.py`).
- Owner-side rule: relaunch pasted LITERALLY (no `_fill`) must save exactly the first invocation's fields. Expected = mapping of the test's own given args to body fields, never a FILLED constant (Moriarty DECEPTION 2: filler tests hid placeholder saves).
- Read fields from the raw commit body (`git log --format=%B%x1e`); drop the `Description: Searched: ...` line (the --searched answer is stored as a 2nd Description).
- Keys that are words of the headline are dropped at save: pick keys absent from headline.
- Placeholder scan over every body: value `...` or `<...>` = saved hole.
- `_carry_cli_flags` substring check: a headline naming a flag (`--issue`, `--quote`, `--work`, `--promotes`, `--discard`) suppresses the carry.
- Remove fence: drive "the printed way" (run, paste relaunch up to 2 steps) so either fix (no bounce, or a non-self relaunch) passes.
- Mutant copies need `git init` + an empty commit, or every test errors (conftest real-repo guard): run init/commit via python subprocess, the customs hook blocks bash `git commit`.
