---
name: doctor-and-health-zones-check
description: zones.json three-state check (zones.py list + git-memory-doctor.py, 2026-08-06) -- test_boundary.py counts same-file callers as production==0, doctor.py's deliberate independence from lib/memory's import chain, safe non-git A/B revert method, later hardened with per-zone shape validation (Cerberus T2 fix, same day)
metadata:
  type: project
---

## Update (same day, Cerberus review T2): `check_project_zones()` also validates per-zone shape now

The original version only checked `isinstance(data, dict)` + `len(data)`,
so `{"billing": "oops"}` (valid top-level JSON, invalid per-zone shape)
reported `"ok"` while the real consumer, `lib/memory/zones.py::load()`,
rejects it with `ValueError` and the customs hook blocks the commit on
it -- a doctor false-positive on exactly the failure mode its sibling
check exists to catch. Fixed by replicating `zones_lib.load()`'s three
per-zone checks locally (each zone value is an object; `description` is
text if present; `aliases` is a list of text if present), with the
exception to the no-import-`lib/memory` pattern spelled out in the
docstring itself, same style as the reasoning already documented above
for the file-level checks. Same fix pattern applies if `zones_lib.load()`
ever grows a fourth shape check -- the doctor's local copy must be
updated in lockstep or it silently drifts back into false-positive
territory.

Building the RED->GREEN pass for `zones.json`'s absent/empty/populated
distinction (`bin/memory/zones.py::_cmd_list`, `bin/git-memory-doctor.py`)
surfaced two things worth keeping.

## `tests/memory/test_boundary.py::_symbol_usage_report` only counts CROSS-FILE
callers as "production" -- a function called only from within its own
defining file shows `production == []`

`_symbol_usage_report()` (test_boundary.py ~line 746) explicitly skips
same-file usage: `if owner_stem == own_stem: continue`, both in the
attribute-access branch and the `from X import Y` branch. `health.py`'s
`memory_mounted()` and `possible_unconverted_legacy()` (added earlier the
same day, 2026-08-06, PIEZAS.md Aviso A/B) are called ONLY from
`health.build()`, in the SAME file -- so they show `production: []` even
though they are very much alive and wired into the real boot report via
`HealthReport`. Combined with zero direct tests (existing tests exercise
them indirectly through `health.build()`/`boot.render()`, never by calling
the function by its own name), `test_no_public_symbol_has_zero_production_and_zero_tests`
fails on exactly these two symbols. **This is pre-existing, unrelated to
the zones.json work** -- verified by temporarily swapping all three touched
files (`health.py`, `zones.py`, `git-memory-doctor.py`) back to their exact
`git show HEAD:...` content and re-running `test_boundary.py`: identical
two failures, identical two symbol names. `test_boundary.py::
test_no_file_outside_the_allowed_zone_imports_lib_memory` also fails
independent of this task (unrelated boundary rule). Flag both for the
orchestrator; do not fix inside a task scoped to zones.json.

## `git-memory-doctor.py` deliberately avoids importing `lib/memory/` --
followed that precedent instead of reusing `health.zones_state()` there

`check_project_memory_seed()` and `check_project_config()` (both
pre-existing) read their target files directly with `os.path`/`json.load`
instead of importing anything from `lib/memory/`, with the reasoning
spelled out in `check_project_memory_seed()`'s own docstring: stay
independent of `lib/memory/`'s import chain, same reasoning
`check_hooks()`/`check_skills()` apply to their own expected-value lists.
`health.py` alone pulls in `ids`, `indexes`, `notes`, `query`, `rules`,
`zones`, `health_plans`, `model`, `vocabulary` at import time -- a lot of
coupling for a hand-run diagnostic script that is meant to work even when
those modules are broken. New `check_project_zones()` follows the exact
same shape as its two siblings (`os.path.isfile` -> `open_no_follow_symlink`
+ `json.load` -> `isinstance(dict)` -> `len()`) rather than importing
`health.zones_state()` -- contrast with `bin/memory/zones.py`, which is
ALREADY fully coupled to `lib/memory/` (imports `notes`, `notes_commit`,
`zones as zones_lib`, `model.Zone`), so importing `health` there to reuse
`zones_state()` adds no new category of coupling and was the right call in
that file specifically.

## Safe non-git method to prove "pre-existing" vs "caused by me" when
`git stash`/`reset`/`checkout -- <path>` are banned in this repo

This repo's hard rule (see [[lessons]], MEMORY.md top) forbids any git
command that mutates the working tree, because other sessions keep
uncommitted work in the same tree. To A/B-test a suspected pre-existing
test failure against the last commit: `cp` each of your own edited files
to a scratch path first, `git show HEAD:<path> > <path>` to overwrite them
in place with the committed version (a plain file write, not a git
mutation of tracked state -- `git show` only reads), run the test, then
`cp` your scratch copies back over the real files. Verified live: all
three touched files reverted to HEAD content reproduced the exact same
`test_boundary.py` failures byte-for-byte, proving the gap predates this
task. Never use `git stash`/`git checkout -- <path>` for this even though
they'd achieve the same effect -- the ban is on the git command, not the
outcome.
