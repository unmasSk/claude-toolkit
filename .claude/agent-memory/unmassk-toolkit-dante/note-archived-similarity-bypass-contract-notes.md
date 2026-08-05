---
name: note-archived-similarity-bypass-contract-notes
description: test_note_archived_similarity_bypass.py 2026-08-05 -- query.by_zone() includes archived notes, so a CLOSED note wrongly blocks a similar new note (worse for I type, --replaces isn't even an allowed field there); RED via bin/gitmem facade, not bin/memory scripts directly
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_note_archived_similarity_bypass.py`
(4 tests, 3 RED / 1 GREEN control by design) -- one test per point of the
task's own 4-point contract, literal, same test-first acceptance-granularity
override as every other contract file in this project. Only file touched
this session (`git status --porcelain` confirmed before/after -- everything
else untracked/modified in the tree belongs to parallel teammates' work,
none touched).

**The bug, confirmed by reading, not assumed:** `lib/memory/query.py::
by_zone()` (line 236-245) returns everything `_all_notes()` parses out of
git history -- live AND archived (closed/replaced/promoted) notes alike,
with zero filtering against the live index or `ARCHIVED.md`.
`bin/memory/note.py::_build_context()` (line 133) passes that straight
through as `Context.existing_in_zone`, and `validator.py::
validate_replacement()` (line 371-426) uses it whole to decide "esto pisa
a algo que ya esta escrito" -- a note closed months ago still counts as a
live collision. Worse for type `I`: `vocabulary.TYPES["I"].allowed_fields
== frozenset({"description", "why", "keys"})` (verified reading
`vocabulary.py`) -- `replaces` isn't even a legal field for an incidencia,
so the rejection's own "la sustituye  --replaces <id>" exit is an exit the
system would itself reject if taken literally.

**Executed via `bin/gitmem` (the facade), never `bin/memory/*.py`
directly** -- explicit task instruction ("ejecutando bin/gitmem"). Used
`run_gitmem_script` from `conftest.py` (already existed, already used by
`test_gitmem_facade.py`) instead of `run_memory_script`. `gitmem note`/
`gitmem remove` dispatch by path to `bin/memory/note.py`/`remove.py`
without adding logic of their own (`gitmem`'s own docstring, verified by
`TestAddsNoLogicOfItsOwn` in that sibling file) -- exercising the facade
IS exercising the real user path, not a shortcut.

**Similarity guaranteed without depending on `similar.py`'s exact
formula:** every "old"/"new" pair in this file shares LITERALLY IDENTICAL
headline+description -- Jaccard = 1.0, far above
`vocabulary.SIMILARITY_THRESHOLD` (0.5). No test here counts words by
hand or assumes a borderline case survives a future threshold tweak.

**Four tests, mapped 1:1 to the task's own four contract points:**
1. `TestClosedNoteDoesNotBlockASimilarNewNote` -- write M, close it via
   `gitmem remove <id> "<reason>"` (no `--restriction` needed -- that flag
   only gates `I`-type closes, `remove.py::main()` branch checks
   `args.id.startswith("I-")`), write a second identical M in the same
   zone pair. **RED today**: `rc_new == 0` fails, real rejection text
   shown citing the closed note as a live candidate.
2. `TestLiveNoteStillBlocksASimilarNewNote` -- same pair, first note
   left OPEN. **Control, GREEN today** (already correct behavior) --
   confirms the fix in point 1 has something real to preserve, not just
   an assertion that happens to pass by accident.
3. `TestIncidentClosedThenReopenedEndToEnd` -- the task's literal I-014
   story: I opened, closed via `gitmem remove <id> "<reason>" --restriction
   no` (I-type DOES need the restriction flag --
   `validator.validate_incident_close_question` fires otherwise), a
   second similar I months later. **RED today**, same failure shape as
   point 1, plus asserts the archived line's `destination == "closed"`
   and `destination_detail` equals the real close reason (via
   `indexes.read_archive`, never hand-typed), and that the live index
   (`INCIDENTS.md`) holds ONLY the new id.
4. `TestArchivedNoteIsIgnoredButALiveDuplicateStillBlocks` -- the
   overcorrection guard: seed old-A (closed) AND live-B (same text,
   written with `--replaces none` so its own alta doesn't collide with
   still-visible-today A), then attempt a third identical note. Asserts
   the rejection names B (live) and does **not** name A (archived).
   **RED today** for the precise reason a naive "just stop blocking
   entirely" fix would still pass: today's rejection names BOTH ids,
   proving the current bug isn't "some blocking" but "blocking against
   the wrong set."

**`--replaces none` sentinel needed for note B in test 4, same mechanism
already documented in
[note-script-replaces-not-archiving-regression-notes](note-script-replaces-not-archiving-regression-notes.md):**
`validate_replacement` returns `None` immediately whenever
`note.replaces is not None`, regardless of value -- without this, B's own
creation would bounce against still-archived A under today's bug, and the
test would never reach the actual scenario it exists to check.

Verification: `python3 -m pytest
unmassk-toolkit/tests/memory/test_note_archived_similarity_bypass.py -v`
-> 3 failed / 1 passed, all three failures show the real rejection text
(candidate ids, real `⛔` prefix) as the cause, not a collection/import
error -- RED for the right reason. `--collect-only`: 4 tests, matches the
4-point contract exactly, zero extra coverage added.

Reference: [note-script-replaces-not-archiving-regression-notes](note-script-replaces-not-archiving-regression-notes.md), [query-contract-notes](query-contract-notes.md), [validator-contract-notes](validator-contract-notes.md)
