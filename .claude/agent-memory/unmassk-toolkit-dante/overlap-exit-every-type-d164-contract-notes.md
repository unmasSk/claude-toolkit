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
