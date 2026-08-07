---
name: zones-lowercase-normalization
description: lib/memory/zones.py + bin/memory/zones.py (2026-08-07) -- zone NAME/alias lowercased everywhere, description untouched; resolve() must not assume its zones dict already came from load()
metadata:
  type: project
---

## What changed

Owner order 2026-08-07: zone **names and aliases** (the dict keys / search
keys) always persist and compare in lowercase. The **description**, and
every other free text in the system (headlines, why, keys, close-session
context, rules), is explicitly OUT OF SCOPE -- stored verbatim. This was a
precision message sent mid-task after the first instructions could have
been read as "normalize the zone" broadly.

Single point for the rule: `zones.normalize(name) -> name.lower()` in
`lib/memory/zones.py`, called from `load()` (normalizes on READ too, so a
pre-existing `zones.json` with an uppercase zone from before this fix
keeps resolving -- not just newly-written data), `resolve()`,
`candidates()`, `add()` (the only writer), and from
`bin/memory/zones.py::_cmd_add` (which also prints a non-silent notice
when the typed name/alias differs from what got persisted -- owner
required this NOT be silent).

## `resolve()` must normalize its OWN `zones` dict argument, not just the input

First implementation only did `name = normalize(name); if name in zones`.
That works in production (`zones` always comes from `load()`/`add()`,
already normalized) but broke `tests/memory/test_remove_script.py`: its
`seed_note` fixture builds `validator.Context(zones=...)` by hand with
`{"closeTest": model.Zone(name="closeTest", ...)}`, never touching
`zones.load()`. A resolve() that trusts the caller's dict is already
normalized will silently reject a real, existing zone whose stored
casing happens to differ.

Fix: iterate `zones.items()` and normalize BOTH the search target and
each `canonical`/alias on the fly, return the dict's actual key (not the
normalized search term) as the canonical name. Case-insensitive
regardless of who built the dict or how. Cross-check any similar
resolve/lookup helper against hand-built `Context`/dict fixtures before
assuming "callers always use the real loader."

## Two collateral test failures -- correct side effect, not a bug

`tests/memory/test_note_script.py::TestCreatesAllSevenNoteTypesForReal`
and `::TestRepoResolvedByProcessCwd` seed zones named `sevenTypes` /
`nestedCwd` (mixed case used only as an arbitrary unique token, unrelated
to the case-normalization feature) via `seed_zones_json()` writing
straight to disk, then run the full `note.py` CLI path
(`_build_context` -> `zones_lib.resolve()`), and finally search the
written index for the literal mixed-case zone2 string. Since the note
now legitimately gets written with the lowercased zone
(`seventypes`/`nestedcwd`), the exact-case search finds nothing. This is
the intended behavior, not a regression -- reported to the orchestrator
per this project's "no toco tests, lo hace Dante" rule, not touched.
Ran the full `tests/memory` directory (455 tests) to confirm these are
the ONLY two casualties.

See also [lessons.md](lessons.md) for the general git-safety and
prior zones.py history (rename batch, health checks).

## Closed the doctor gap, 2026-08-07 -- deliberately duplicated, not imported

`bin/git-memory-doctor.py::check_project_zones()` used to report a
populated `zones.json` as flat "ok" regardless of casing, silent about
a zone left over from before this normalization (or brought in from
another machine). Fixed by adding a THIRD outcome, not just a binary
error/ok: valid-shape zones whose name/alias isn't already lowercase
now report `"warn"` naming which zone(s) and how to fix them by hand
(no `zones` edit command exists yet -- confirmed via
`bin/memory/zones.py::_cmd_add`'s own rebound message).

Decision on independence (owner asked for it explicitly before
touching the file): **duplicated `normalize()` inline as
`name == name.lower()`, did NOT import `zones.py`.** This file already
duplicates `zones.load()`'s three shape checks on purpose, to stay
independent of `lib/memory/`'s import chain (`model.Zone`, `difflib`,
`tempfile`, the `add()` file-lock code) -- importing `zones.py` for a
single `.lower()` would drag all of that in for one line. The
docstring on `check_project_zones()` now spells out the same warning
zones.py's own `normalize()` docstring gives: it's a plain `.lower()`
today, but if it ever grows (whitespace trimming is floated as a
future possibility in `zones.py`), this duplicate silently drifts
unless someone updates it by hand at the same time.
