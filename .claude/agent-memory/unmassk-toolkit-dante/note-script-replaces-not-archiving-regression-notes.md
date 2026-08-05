---
name: note-script-replaces-not-archiving-regression-notes
description: test_note_script.py 2026-08-04 (same session, second contract) -- note.py --replaces <ID> never calls notes.replace(), old note stays live forever alongside the new one; --replaces none sentinel control stays green
metadata:
  type: project
---

Context: same file/session as
[note-script-alias-not-resolved-regression-notes](note-script-alias-not-resolved-regression-notes.md),
second bug in the same batch, landed as a follow-up message mid-task (both
fixes go to Ultron in one pass). `note.py` and `notes.py::replace()` both
already exist and are in production; this is a regression test for a
confirmed bug, not a pre-implementation contract.

**The bug:** `bin/memory/note.py::main()` (line 168) unconditionally calls
`notes.write(candidate, ctx)`, never `notes.replace(new, old_id, ctx)` --
even when `--replaces <ID>` is a real note id. `notes.write()` writes
`candidate.replaces` into the commit body (`format.build_message` folds
`Replaces:` in whenever `note.replaces is not None`) but has ZERO knowledge
of archiving -- it only ever inserts a new index line, never removes one.
Result: `--replaces D-001` on a new D reports success with a real new id
(`D-002`), and `DECISIONS.md` keeps BOTH `D-001` and `D-002` live forever,
`ARCHIVED.md` stays empty -- two contradicting live decisions, exactly what
`notes.py::replace()`'s own docstring names as the failure it exists to
prevent ("que la sustitucion quede a medias: dos notas vigentes diciendo lo
contrario"). Same family as the alias bug in the same session: success
reported, memory silently corrupted (contradictory, not lost this time).

**`--replaces none` is a real sentinel, not `None`.** `note.py`'s argparse
(`--replaces`, `default=None`) does NOT special-case the literal string
`"none"` -- when the user passes `--replaces none`, `Note.replaces` becomes
the STRING `"none"`, which is `is not None` in Python. Two places already
treat this specially, confirmed by reading (not assumed): `validator.py::
validate_replacement` checks `note.replaces is not None` to skip the
"overlapping note" rejection (so `"none"` bypasses it same as a real id),
and `validator_pointers.py:91` explicitly excludes `note.replaces != "none"`
from the dangling-pointer check. So `"none"` already flows correctly through
today's `write()`-only path (nothing gets archived, both notes stay live,
by construction of `write()` never touching removal/archival) -- this is
exactly why the task's required control test needs to be a **positive
green** proving the fix doesn't accidentally start treating `"none"` as a
real id and archiving something.

**Two test classes, mirroring the two behaviors:**
1. `TestReplacesArchivesTheOldNoteInTheSameCommit` -- seed a D (`D-001`, no
   `--replaces`), then a second D with `--replaces D-001` (RED today).
   Asserts, all via real readers, never hand-typed text: (a) exactly ONE new
   git commit for the second call (`_git_commit_count` before/after, already
   in the file) -- proves the "single commit" contract of `replace()`, not
   just eventual consistency across two commits; (b) `indexes.read
   ("DECISIONS.md", pm)` -- `old_id` NOT in the live id set, `new_id` IS;
   (c) `indexes.read_archive(pm)` -- `old_id` present with
   `.destination == "replaced"` and `.destination_detail == new_id`,
   compared against the REAL `ArchiveLine` fields the real parser
   (`format.parse_archive_line`, via `indexes.read_archive`) returns, never
   a hand-typed "replaced by D-002" string. `TEXTOS.md` Sec.4's three
   literal destinations (`replaced by <ID>` / `closed: <motivo>` /
   `promoted to <ID>`) map 1:1 to `ArchiveLine.destination` values
   (`"replaced"`/`"closed"`/`"promoted"`) -- confirmed by reading
   `indexes.py::archive()`, which builds the line via
   `format.build_archive_line(placeholder, line.destination,
   line.destination_detail)`.
2. `TestReplacesNoneSentinelStillLetsBothNotesCoexist` -- seed two D's, the
   second with `--replaces none` explicitly. Confirmed GREEN today (no fix
   needed for this path) -- both ids stay in `indexes.read("DECISIONS.md")`,
   `indexes.read_archive(pm)` returns empty. This is the anti-regression
   guard: Ultron's fix (branch on `args.replaces` being a real id vs.
   `None`/`"none"` to decide `write()` vs. `replace()`) must not flip this
   green to red.

**Not touched, per explicit orchestrator instruction:**
`discard_alternatives` -- PIEZAS.md Sec.10 documents `note.py` calling it
too (found by the OTHER agent's boundary test,
`test_boundary.py::test_every_public_symbol_has_a_real_importer`), but it's
a different flow and explicitly out of scope for this task ("no quiero
mezclarlo con esto. Solo --replaces").

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_note_script.py -v`
-> 9 passed (7 pre-existing + 1 new `--replaces none` control), 3 failed (2
pre-existing alias-RED, unchanged, + 1 new `--replaces` RED). The new RED's
real failure: `AssertionError: la vieja (D-001) tiene que salir del indice
VIGENTE... assert 'D-001' not in {'D-001', 'D-002'}` -- both truly present,
not a collection/import error. `tests/memory --collect-only`: 313 total (was
311 after the alias session's 3 tests, +2 more this round).

Reference: [note-script-alias-not-resolved-regression-notes](note-script-alias-not-resolved-regression-notes.md), [capa5-scripts-red-contract-notes](capa5-scripts-red-contract-notes.md)
