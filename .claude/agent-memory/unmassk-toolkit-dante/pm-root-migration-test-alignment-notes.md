---
name: pm-root-migration-test-alignment-notes
description: Aligned test_notes.py/test_health.py/test_boot.py to notes.pm_root(root) after the production index-path fix (raw repo root -> .claude/project-memory/); single-source-of-truth replace_all technique and a stale-docstring trap
metadata:
  type: project
---

2026-08-02, urgent same-day fix. Production (`notes.py`, `health.py`)
moved where the eight index files + `ARCHIVED.md` live: from the bare
repo root to `notes.pm_root(root)` (`<root>/.claude/project-memory/`,
spec Sec.7). Tests that seeded/read index files directly (not through a
function that already composes the path) were left pointing at the old
bare-root location and went RED: 11 tests (7 `test_notes.py`, 4
`test_health.py`), plus `test_boot.py` (written mid-fix, deliberately
with the old convention, still collection-erroring because `boot.py`
doesn't exist).

**The rule that matters, not the diff itself:** functions that take
`root` as an explicit parameter and read the indices *by dentro*
(`health.coherence(root)`, `health.duplicates(root)`) did NOT change —
they already compose `notes.pm_root(root)` internally, so tests keep
passing them the LITERAL bare root, unchanged. Only call sites that
touch index files *directly* (`indexes.seed/insert/remove/archive/
read/read_archive/counts`, or a raw `Path(root) / "MEMOS.md"` read) had
to start passing `notes.pm_root(root)` instead of `root`. Conflating the
two (composing pm_root before calling `health.coherence`) is the
opposite bug — see [[boot-contract-root-vs-pmroot-notes]], which this
session's fix supersedes for `test_health.py` (it now composes
`notes.pm_root(root)` at call sites, not the literal root, for its
*direct* index calls — `health.coherence(root)` itself is untouched).

**Single source, not a hand-copied path**: the owner was explicit —
don't scatter `<root>/.claude/project-memory/` as a literal string or a
locally-reinvented helper across test files. `notes.pm_root(root)` is
already public for this. Where a test function didn't have the `notes`
fixture in its signature yet (some `test_boot.py` rows only needed it
for path composition, no `notes.write()` call), the fix was adding
`notes` to the fixture list, not inventing a parallel constant.

**Mechanical technique that worked well for ~35 call sites across two
files**: since every occurrence of a given pattern (`indexes.seed(root)`,
`_index_line_for(indexes, vocabulary, root,`, `_read_all_eight_files(root,
vocabulary)`, etc.) needed the *identical* transformation everywhere it
appeared, `Edit` with `replace_all: true` on the exact literal substring
was safe and fast — but only after confirming with a scripted grep+ast
scan (checked every occurrence's enclosing `def test_...` signature
contains the `notes` fixture) that no call site was an exception. Ran the
full grep-count-before / grep-count-after check to confirm no stray
occurrence was missed or double-replaced.

**Stale-docstring trap, worth watching for on any similar alignment
task**: `test_boot.py`'s module docstring didn't just use the old
convention in code — it had ~30 lines of prose actively *arguing for*
the old (now-wrong) convention as "the correct form, matching
test_health.py", written before the production fix landed. Fixing only
the code and leaving that prose would mislead the next reader (Ultron,
implementing `boot.py`) into reintroducing the same bug by trusting the
docstring over the code. Rewrote the paragraph to state the current
(fixed) convention and why, rather than deleting it silently.

**Verification discipline**: this session's `conftest.py` has an
autouse fixture (`_guard_against_writing_to_the_real_repo`, see
[[notes-cwd-leak-fix-and-guard-fixture-notes]]) that fails any test
moving the real repo's HEAD — ran the full `tests/memory` suite and
confirmed `git rev-parse HEAD` unchanged before/after
(`010ced6` -> `010ced6`) as an extra check beyond the guard itself.

Result: `test_notes.py` 15/15, `test_health.py` 13/13, full
`tests/memory` suite 132 passed / 5 errors (the 5 are `test_boot.py`,
`FileNotFoundError: lib/memory/boot.py` — expected, not a regression,
`boot.py` doesn't exist yet).
