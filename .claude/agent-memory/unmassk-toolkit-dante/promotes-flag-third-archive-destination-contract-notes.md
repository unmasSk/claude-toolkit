---
name: promotes-flag-third-archive-destination-contract-notes
description: test_note_script_promotes.py RED contract -- the third archive destination ("promoted to <ID>") has a reader but no writer; --promotes wired via bin/gitmem, not note.py direct
metadata:
  type: project
---

Context: `TEXTOS.md` Sec.4 fixes THREE literal `ARCHIVED.md` destinations
(`replaced by <ID>` / `closed: <motivo>` / `promoted to <ID>`). The reader
(`indexes.read_archive` -> `format.parse_archive_line`) already handles all
three in production; the writer only covers two -- `notes.py::replace()`
(line 360, `destination="replaced"`) and `::close()` (line 472,
`destination="closed"`). Nothing ever writes `destination="promoted"`. This
is `spec-sistema-memoria-v2.md` Sec.4's "a `Q` dies ascending" rule with no
implementation. Orchestrator-decided command form, 2026-08-05, symmetric to
`--replaces`: `gitmem note M --zones z1 z2 "..." --promotes Q-007` (or
type `X` for the "falls to discarded" branch).

**Task explicitly said "ejecutando `bin/gitmem`"**, not `note.py` direct --
different from every prior `note.py` contract in this branch
([[note-script-replaces-not-archiving-regression-notes]],
[[note-script-discard-alternatives-flag-contract]]), which all used
`run_memory_script("note.py", ...)`. `bin/gitmem` is real production code
(not RED itself -- `test_gitmem_facade.py`'s "NO EXISTE TODAVIA" docstring
is now stale, the file is fully implemented and green) that dispatches
`gitmem note <rest>` to `note.py <rest>` via bare `subprocess.run`, no logic
of its own. Used `run_gitmem_script()` (`conftest.py:304`, already existed,
unused by any note.py contract until now) instead of `run_memory_script()`.

**Self-inflicted bug caught by actually running the suite, not assumed
red-for-the-right-reason:** first draft of `_promote_args()` returned
`[note_type, "--zones", ...]` without the `"note"` subcommand prefix that
`run_gitmem_script()` requires as `argv[0]` (`bin/gitmem::main()` reads
`argv[0]` to pick the subcommand before dispatching) -- three of four tests
failed with `"gitmem: subcomando desconocido: 'M'"` instead of the intended
`argparse: unrecognized arguments: --promotes`. Fixed by prepending `"note"`
inside the helper. Second bug: the nonexistent-question test read
`indexes.read("MEMOS.md", pm)` as a "before" baseline in a `tmp_repo` where
NO note had ever been written yet -- `indexes.read()` fails loud
(`FileNotFoundError`) on an index file that was never seeded, since
`seed()` only runs inside `write()`/`replace()`/`close()`. Fixed by calling
`indexes.seed(pm)` directly first (the same idempotent production function
`write()` calls internally) to establish the "zero notes" baseline before
the rejected attempt -- not a reimplementation, just priming state the way
a real repo would already have it after any first write.

**Test 3/4 (wrong-type pointer, dangling pointer) never fabricate rejection
text** -- no molde exists in `TEXTOS.md` for a flag that isn't built yet.
Used a structural marker instead: `rejection.py::_render()` always emits
`⛔ {title}` and, when `relaunch` is non-empty, a `Relanza:` section --
common to every real rejection built via `rejection.build()` regardless of
`kind`. Asserting `"⛔" in combined and "Relanza:" in combined` proves "a
real customs rejection happened" without inventing `what`/`options` prose
that only Ultron's real implementation will decide. Confirmed this
correctly stays RED today too: today's failure is a bare `argparse` usage
dump (`note.py: error: unrecognized arguments: --promotes ...`), which has
neither marker -- so even the "wrong target type" test fails for the
right underlying reason (the flag doesn't exist at all yet), not a false
green from a coincidental crash matching the assertion.

**Headline-vocabulary isolation, disclosed not guessed:** `validate_replacement`
only skips its similarity rebound when `note.replaces is not None` -- it has
no knowledge of a hypothetical `note.promotes` field. A promoted answer
naturally restates its question's wording (real `TEXTOS.md` example: "do we
need per-seat pricing?" -> promoted to M-051), which risks tripping the
UNRELATED "overlapping note" rejection and misattributing a failure to
`--promotes`. Same lesson as
[[note-script-discard-alternatives-flag-contract]]'s Jaccard-overlap
incident: picked deliberately unrelated headline pairs per test (zero
shared content words) so a failure can only come from the `--promotes`
path under test.

File: `unmassk-toolkit/tests/memory/test_note_script_promotes.py` (new
file, per task scope -- no other file touched). 4 classes, all RED today
for the single real cause (`argparse: unrecognized arguments: --promotes`):
Q promotes to M in one commit (round-trip via real `indexes.read_archive`,
never hand-typed text), Q falls to X in one commit, `--promotes` at a
non-Q bounces without writing anything, `--promotes` at a nonexistent id
bounces without writing anything. Atomicity (task's point 6) folded into
the same tests rather than a separate class: success path checks all three
pieces (old index, new index, ARCHIVED.md) from one final state; rejection
paths assert full before/after equality across both indices, ARCHIVED.md,
and commit count. Mid-`git`-crash atomicity explicitly out of scope
(disclosed in the file docstring) -- already covered generically by
`write()`/`replace()`/`close()`'s shared restore mechanism, not re-tested
at this CLI acceptance layer.

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_note_script_promotes.py -v`
-> 4 failed (all 4, same root cause, confirmed via stderr text in each).
`--collect-only` -> 4 tests, 0 errors. `py_compile` clean. Full
`tests/memory` suite: 380 passed, 4 failed (only the new ones) --
`git status --porcelain` on `tests/memory/`/`lib/memory/`/`bin/memory/`
confirmed only this new file carries my edits; the `M` markers on
`bin/gitmem`/`lib/memory/utf8.py`/`conftest.py`/`test_conftest_smoke.py`
belong to concurrent colleagues, not this task.

See also: [[notes-replace-close-contract-notes]] (the sibling `replace()`/
`close()` RED contract this one completes the third destination for),
[[note-script-replaces-not-archiving-regression-notes]] (the `--replaces`
CLI wiring this task's `--promotes` is explicitly symmetric to).
