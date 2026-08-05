---
name: id-reuse-regression
description: memoria-v2 capa 5 close-out (2026-08-03) -- pinned the worst bug of the whole build (closed note's id reused by the next write of the same type) with 3 regression tests in test_notes.py; git-show-includes-diff gotcha; only-2-callers-of-ids.next_id verification technique
metadata:
  type: project
---

Session 2026-08-03, `feat/memoria-v2` branch, closing `docs/memoria-v2/PIEZAS.md`
§12bis for capa 5. Task: pin, with tests, the worst bug found in the whole
build so far -- **already fixed** by Ultron in
`unmassk-toolkit/lib/memory/notes.py` (`_index_with_archived()` helper,
point 5 of the module docstring). Never touch `lib/memory/` -- tests only,
in `unmassk-toolkit/tests/memory/test_notes.py` (appended as
`test_regression_*` functions, matching the file's own established
convention for post-fix regressions rather than a new file).

## The bug and the fix

`ids.next_id()` only ever saw the LIVE index. The moment a note got
archived (`close()`, or the "old" side of a `replace()`), its number
dropped out of that view and became free for the next write of the same
type -- write I-001, close it, write again -> I-001 a second time, two
different notes permanently sharing one id in git. Fix: `notes.py`'s
`_index_with_archived(current_index, pm)` unions the live index with
hollow `IndexLine`s for every id in `indexes.archived_ids(pm)` before
calling `ids.next_id()`. Both call sites (`write()` and `replace()`) go
through it. `ids.py` itself never changed -- same signature, still no
file/git access, per PIEZAS.md §7.2.

## The 3 tests added (all in test_notes.py, after the existing
`test_regression_git_error_not_empty_...` block)

1. `test_regression_closing_a_note_never_frees_its_id_for_the_next_write_of_the_same_type`
   -- the exact reported reproduction (write I, close I, write I again),
   asserts distinct ids AND re-reads both real commits independently via
   `format.parse_message(git log -1 --format=%B <sha>)`, comparing that
   against `WriteResult.note_id` -- two things written separately, per
   this project's rule that a test only counts if it compares two
   independently-produced values.
2. `test_regression_replace_also_never_reuses_an_id_archived_in_an_earlier_commit`
   -- same defect, `replace()`'s own call site. Had to use type **M**, not
   I: `replace()` sets `replaces=old_id` on the candidate, and
   `vocabulary.TYPES["I"].allowed_fields` does NOT include `replaces` (only
   D/M/R do) -- validate_fields rejects it. Realistic same-type sequence:
   write memoA, write memoB, close memoB (archives a HIGHER number than
   the one still live), then replace() memoA -- pre-fix, `replace()`'s
   `current_index` (captured as `old_lines`, before `indexes.remove()`)
   only contains memoA itself, so the next number collided with the
   already-archived memoB.
3. `test_regression_counter_stays_per_type_when_an_archived_note_of_another_type_exists`
   -- the row §7.2 already declares ("per type") but never tested with an
   archived note of ANOTHER type mixed in. `_index_with_archived()` unions
   archived ids across ALL types into one tuple; only `ids.next_id()`'s own
   prefix filter keeps them from leaking across types. Close a D, write an
   I right after -> still I-001; write a second D -> D-002, not reusing
   D-001.

## Gotchas

- **`git show -1 --format=%B <sha>` is NOT the same as `git log -1
  --format=%B <sha>`**: `git show` without `--no-patch` appends the full
  diff after the message, so `format.parse_message()` gets extra content
  and returns `None`. The existing file already uses `git log -1
  --format=%B HEAD` for this (row 8, `test_replace_archived_line_says_...`)
  -- I copied `git show` by habit first and both new git-verification
  assertions failed with `parsed is None` until switched to `git log`.
- **`replace()` is not valid for every type**: before picking a type for a
  replace-scenario test, check `vocabulary.TYPES[type_].allowed_fields`
  contains `"replaces"` -- I, X, B do not.
- Confirmed via `grep -rn "next_id"` across `lib/memory/` and `bin/` that
  there is **no third caller** of `ids.next_id()` outside
  `notes.py:write()`/`notes.py:replace()`, both already routed through
  `_index_with_archived()`. `health.py`/`context.py` only import `ids` for
  `find_duplicates`, never `next_id`.

## RED verification technique (same as
[boot-report-argus-four-regressions-notes](boot-report-argus-four-regressions-notes.md),
generalized to 2 call sites in one file)

Copied the whole `lib/memory/` dir to the session scratchpad
(`dante_mutcheck_idreuse/lib_memory_reverted/`), reverted ONLY the two
anchor lines in the copy's `notes.py` (`ids.next_id(note.type,
_index_with_archived(current_index, pm))` -> `ids.next_id(note.type,
current_index)`, same for `replace()`) via a `str.replace()` with an
assert-count-found guard, never touching the real file. Two standalone
scripts (no pytest, `sys.path.insert(0, <scratch_lib_dir>)`, plain flat
imports since these are regular module names) reproduced each scenario
against a real disposable `tempfile.mkdtemp()` git repo: both showed the
reused id against the reverted copy and the distinct id against the real
`lib/memory/`. Scratch copies discarded after verification.

Suite: 236 -> 239 green (`python3 -m pytest unmassk-toolkit/tests/memory -q`).
