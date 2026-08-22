---
name: note-issue-field-seven-types-contract-notes
description: RED contract for opening --issue to all seven note types (D-044/D-045); fake-gh-on-PATH technique for subprocess-level gh mocking; two production gates found (vocabulary.py + report_render_note.py)
metadata:
  type: project
---

Task: `--issue` opens from M-only to all seven types (D, M, R, Q, X, I, B) --
D-044/D-045, unmassk-toolkit memory. Test-first, contract pass only (no
production code touched). File:
`unmassk-toolkit/tests/memory/test_note_issue_field.py`.

**Two independent production gates found, not one** -- worth remembering
before assuming "fix vocabulary.py" closes the whole contract:
1. `lib/memory/vocabulary.py::TYPES[<T>].allowed_fields` -- only `"M"` has
   `"issue"`. This is what blocks save for the other six types
   (`validator.validate_fields()` rejects: "Estos campos no existen para
   el tipo <T>: issue").
2. `lib/memory/report_render_note.py:96` -- `if note.type == "M" and
   note.issue is not None:` -- a SECOND, independent type check in the
   renderer `search.py --id` uses. Fixing only #1 leaves `--id` silent
   about the issue number for non-M notes. Two other places that ALREADY
   don't care about type (verified reading the code, not assumed): `gh`
   existence check (`validator_issue.py::validate_issue`, no type branch,
   called unconditionally before the vocabulary gate) and the commit
   trailer writer (`format.py::_body_field_line`, `label == "Issue"` with
   no type condition).

**Fake-gh-on-PATH technique** for subprocess-level `note.py` tests that
need to control `gh issue view` without network: `note.py` runs as a real
child process (`run_memory_script`), so `monkeypatch.setattr(subprocess,
"run", ...)` (the technique `test_health.py::_patch_gh` uses, since
`health.py` runs in-process) cannot reach it. Instead, write an executable
Python script named `gh` into a throwaway dir under `tmp_path` and prepend
it to `PATH` via `run_memory_script(..., env={"PATH": fake_dir +
os.pathsep + os.environ["PATH"]})` (`env` already only *adds* to the
inherited environment, never replaces it). The fake script only needs to
understand `gh issue view <N> --json number`: returncode 0 for "exists"
(stdout content irrelevant -- `_issue_exists` only checks
`returncode == 0`), returncode 1 with the exact marker string
`validator_issue.py::_ISSUE_NOT_FOUND_MARKER` declares
("Could not resolve to an issue or pull request...") for "missing". This
mirrors gh's real output shape, doesn't replicate `validator_issue.py`'s
own logic -- same justification `unmassk-standards` Sec.34.5 gives for any
mock of an external/non-deterministic dependency.

**One test class in the contract is honest about NOT being red today**:
the "issue doesn't exist -> rejected" check already works uniformly
across all seven types right now, because `validate_issue()` never
branches on `note.type` -- it's called before the vocabulary gate, not
after. Wrote it anyway (task explicitly asked, and it's a real regression
guard against a future reordering), but labelled it clearly as a guard,
not a red case, in both the test docstring and the delivery report.
Don't force a green guard test to look red just to match a blanket
"everything must fail today" instruction -- report the actual state.

**Pitfall avoided**: manual ad-hoc reproduction outside pytest (a scratch
git repo + running `note.py` by hand) tripped a stray GLOBAL
`core.hooksPath` pointing at a *different* unrelated repo on this
machine (`claude-git-memory/.git/hooks`), rejecting the commit with a
customs-hook message that has nothing to do with this task. pytest's own
`tmp_repo` fixture does NOT hit this (confirmed: the existing suite
passes fine through the same `run_memory_script` machinery) -- the
interference is purely an artifact of manual shell reproduction, not a
real signal. Lesson: trust the project's own test harness over ad-hoc
manual reproduction when the two disagree; don't spend budget chasing
what turns out to be unrelated machine-local git config.

Result: 7 tests red for the right reason (6 types x accept-and-trailer,
1 round-trip via `search.py --id`), 10 green (M baseline + 7-type
not-found guard + 2 scope-creep guards). Full `tests/memory` suite:
482 passed, 1 skipped (pre-existing), 7 new red -- zero collateral
damage.
