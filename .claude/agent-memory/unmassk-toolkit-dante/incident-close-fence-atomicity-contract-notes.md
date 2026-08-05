---
name: incident-close-fence-atomicity-contract-notes
description: test_remove_incident_close_fence_atomicity.py RED contract -- --restriction new closes the incident even when the fence text is rejected, must become all-or-nothing
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_remove_incident_close_fence_atomicity.py`
(new file, test-first contract pass, acceptance granularity, 2 tests). Owner
decision 2026-08-05: closing an `I-` incident and birthing its fence
(`--restriction new`) are two consecutive acts inside ONE command
(`bin/memory/remove.py`) -- (1) `notes.close()`, irreversible, already in
git; (2) `notes.write()` the fence, which goes through the validator like
any other note. Today, if (2) bounces (headline > 80 chars is the
cleanest case), (1) already happened -- the incident stays closed with no
fence. Required behavior: **all or nothing** -- pre-check that the fence
can be born BEFORE closing anything; if it can't, don't close, and the
rejection says why.

**Real cause, confirmed by running the test, not assumed:** `_guard_restriction_new()`
in `bin/memory/remove.py` (~line 88) only checks `id` starts with `I-`,
`--restriction-text` non-empty, and the incident exists via `query.by_id`
-- it never runs the fence text through `validator.validate_note()`
before touching anything. `main()` calls `notes.close()` unconditionally,
then `_create_fence()` only after. RED test proves it: with a 96-char
fence headline, real stdout was `"✅ I-001 archivada ... ⛔ el titular
tiene 96 caracteres ... ⚠️ I-001 ya quedó cerrada de forma permanente"`
-- the close DID happen, exactly the bug.

**Sibling test file conflict, flagged in the new file's own docstring, not
fixed:** `test_remove_script.py::TestRestrictionNewWarnsThePermanentCloseAndGivesAWorkingRetryCommand`
asserts the OPPOSITE of this new contract (that the close is already
permanent when the fence bounces) -- it currently documents the bug as
correct behavior. Not touched (per task scope: own new file only, no
edits to existing test files with a parallel agent working in the same
dir). Whoever implements the fix (Ultron) will need Cerberus/Yoda to
reconcile that class once this new contract goes green -- it will start
failing for real once the fix lands, and needs a rewrite, not a delete.

**Pre-check mechanism available for Ultron, found while reading, not
invented:** `validator.validate_note(note, ctx) -> tuple[Rejection, ...]`
(`lib/memory/validator.py:152`) is a PURE function -- no git, no file I/O
-- already the exact aggregator `notes.write()` calls internally before
committing (`notes.py:226`). It doesn't need a real assigned `id` to catch
a headline-length rejection (`validate_headline` only looks at
`note.headline`). The fix is almost certainly: build the candidate `Note`
(same one `_create_fence()` already builds) and call
`validator.validate_note(fence, ctx)` in `_guard_restriction_new()`
BEFORE `notes.close()` runs, bouncing early if non-empty.

**One of the two tests is GREEN today, on purpose:**
`TestFenceThatCanBeBornClosesBoth` (valid fence text -> both the close and
the fence really happen) already passes -- that path isn't buggy today,
it's the anchor/regression guard for "must keep working after the fix",
not new RED. Only the headline-too-long test is RED, for the real cause
(verified by reading the actual combined stdout, not assumed from the
exit code alone).

**Full suite after adding the file:** `378 passed, 1 failed` (the new RED,
zero regressions on the pre-existing 377... actually pre-existing count
was 369 before this session's other work landed on top -- always re-read
the real number from the run, don't trust a stale one written here).

**Reconciliation done, 2026-08-05:** the sibling conflict flagged above is
resolved. `TestRestrictionNewWarnsThePermanentCloseAndGivesAWorkingRetryCommand`
in `test_remove_script.py` was retired (deleted, not rewritten) with a
dated comment block in its place -- its scenario (96-char fence headline
via `--restriction new`) is the exact same case this file's
`TestFenceThatCannotBeBornClosesNothing` already covers, just with the
opposite (now-wrong) assertions. Rewriting it would have been a literal
duplicate. One narrow gap the deleted class covered that this file does
NOT: `_fence_retry_command()` / "relanza solo el muro" for the case where
the pre-check passes but the real write fails afterward (e.g. a git
error) -- that path is now untested, flagged in the retirement comment,
not built. Also dropped now-unused imports (`re`, `shlex`,
`extract_note_id`, `run_gitmem_script`, `seed_note_via_script`,
`seed_zones_json`) from `test_remove_script.py` since the retired class
was their only user. `test_remove_script.py` + this file: 8/8 green.

Reference: [incident-close-question-contract-notes](incident-close-question-contract-notes.md)
