---
name: work-issue-validation-gap-contract-notes
description: work.py --issue N RED contract (Argus gap) -- unlike note.py, work.py never calls gh at all; infra-failure-must-still-commit-with-a-warning is the item that's genuinely red, not just the reject-when-missing item
metadata:
  type: feedback
---

Task: pin, in RED, that `bin/memory/work.py` accepts `--issue N` and
writes the `Issue: #N` trailer but never validates the number against
`gh` (unlike `note.py`, which calls `validator.validate_issue()` ->
`validator_issue.py::_issue_exists`). Owner's design decision, already
fixed before any test was written: infra failure (gh unreachable/not
installed/answers something else) must NOT block the work commit --
degrade with a visible stderr warning; a real "issue does not exist"
answer from `gh` MUST reject with zero new commit. File:
`unmassk-toolkit/tests/memory/test_work_issue_field.py`.

**Ran the file before trusting my own prediction of what's red --
the actual split surprised me.** My first-draft docstring assumed items
2 ("existing issue passes"), 3 ("infra failure still commits, with a
warning") and 4 ("no --issue changes nothing") were all vacuously green
today, since `work.py` calls `gh` for nothing at all yet. Running the
suite showed 3 failed, not 1: item 3's "commit still happens" half IS
green today (nothing blocks anything), but its "warns visibly on
stderr" half is genuinely RED -- `work.py` never prints anything about
`gh` today, so `err` is always `""`. Item 3's two sub-assertions live in
the SAME test (task explicitly asks for "se guarda... avisando" as one
requirement), so the test as a whole is red even though half its
assertions were already true. **Lesson: don't infer red/green from
reading code alone when a test bundles multiple assertions -- run it and
report the real split, then correct the docstring to match**, exactly
the "honesty" pattern from [[note-issue-field-seven-types-contract-notes]]
but one level more granular (per-assertion, not just per-test).

**Two distinct infra-failure shapes, both from the task's own wording**
("gh falso que salga con error distinto del 'no existe', o que no esté
en el PATH"): wrote both as separate tests, not one.
- `gh` not on PATH: implemented via `_path_without_gh()` -- filters the
  REAL inherited `PATH` down to directories that do NOT contain a `gh`
  file, rather than replacing `PATH` with something fixed or empty.
  Emptying `PATH` entirely would also remove `git` (`/usr/bin/git` on
  this machine, separate from `/opt/homebrew/bin/gh` -- verified live
  with `which git`/`which gh`/`ls /opt/homebrew/bin`), which
  `write_work()` needs for the commit itself to succeed -- a naive
  "no PATH" env would make the whole test fail for the wrong reason
  (git not found), not the reason under test (gh not found). Filtering
  by directory CONTENT (`os.path.isfile(os.path.join(d, "gh"))`), not by
  a hardcoded path, keeps this portable across machines.
- `gh` present but answers something else: same fake-gh-on-PATH
  technique as [[note-issue-field-seven-types-contract-notes]], extended
  with a third `mode="unrelated_error"` (stderr text without
  `validator_issue.py::_ISSUE_NOT_FOUND_MARKER`, e.g. a rate-limit
  message) alongside the existing `exists`/`missing` modes -- one
  generator function, one `mode` argument, reused across all fake-gh
  needs in this file including a `call_log` param for the "gh must never
  be invoked without --issue" test (asserts the log file was never
  created, not just that the outcome happened to be fine).

**`run_memory_script`'s `env=` only ADDS to inherited env by default
(dict.update), but a key you DO set replaces that key's value
entirely** -- confirmed via the existing conftest docstring, then relied
on this for `_path_without_gh()` (`env={"PATH": _path_without_gh()}`
fully replaces `PATH`, not appended-and-therefore-ineffective).

Result: 5 tests, 3 red for the right reason (bogus-issue reject +
both infra-failure warning halves), 2 green guards (existing-issue
trailer, no-issue-flag-never-calls-gh). Full `tests/memory` suite:
510 passed (508 baseline + 2 new green guards), 3 new red, 1 skipped --
zero collateral damage, confirmed by re-running the whole suite, not
just the new file.

See also: [[note-issue-field-seven-types-contract-notes]].
