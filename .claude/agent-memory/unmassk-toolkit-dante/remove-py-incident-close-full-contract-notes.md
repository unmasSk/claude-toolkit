---
name: remove-py-incident-close-full-contract-notes
description: bin/memory/remove.py incident-close feature full campaign merged from 2 files — the missing-flag question contract, then the atomicity fix for a rejected fence
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 2) from 2 separate files that both cover the SAME piece of
code and the SAME feature — `bin/memory/remove.py`'s incident-close question/fence flow — split only by which
session touched it. Round 2 directly follows Round 1: once the question-and-relaunch-command mechanism from
Round 1 existed, Round 2 found and pinned that a rejected fence still left the incident permanently closed
(non-atomic). Nothing was cut; each original file's content is reproduced below verbatim under its own dated
heading. Original filenames (now retired, kept only as history in this note, not on disk):
`incident-close-question-contract-notes.md`, `incident-close-fence-atomicity-contract-notes.md`.

## Round 1 (2026-08-04) — closing an I- incident without --restriction must ask, never crash raw argparse

Context: `unmassk-toolkit/tests/memory/test_remove_incident_close_question.py`
(new file, test-first contract pass, 5 RED). Owner decision 2026-08-04:
closing an incidence without saying whether a fence is born can't be a raw
Python/argparse error -- P5 (`docs/spec-sistema-memoria-v2.md` Sec.2)
requires a rejection with the question + two options + exact relaunch
command. Today `bin/memory/remove.py:53` makes `--restriction` blanket
`required=True` for every type, so both the I-close-without-flag case AND
the M/D-close-without-flag case (which should need NO flag at all) crash
identically with argparse's raw `"the following arguments are required:
--restriction"`.

**All 5 tests confirmed RED for the same real cause** (verified by running
each, not assumed): the raw argparse usage/error text, never a fixture
bug. Full suite re-run after adding the file: `364 passed` (pre-existing,
unchanged) `+ 5` (new, expected RED) `= 369`, zero regressions.

**Seeding gotcha found while writing the M/D non-incident test:** M
requires `--stops no|yes` answered (`validate_pain_question`, TEXTOS.md
Sec.1.6) -- omitting it bounces the SEED itself, not the test's real
target. D requires `--why` as a type-mandatory field (vocabulary.py) --
same trap. Fixed via a per-type `extra_seed_kwargs` dict in the
`pytest.mark.parametrize` rows, both explicitly commented as "ajeno a
este contrato, solo para que la siembra no rebote" -- so a future reader
doesn't mistake these for part of the behavior under test.

**Critical architectural note left in the file's docstring, for
Ultron:** `lib/memory/rejection.py::build()`'s own docstring ALREADY
anticipates this exact rejection -- "el rechazo del cierre de incidencia,
TEXTOS Sec.1.10, ofrece dos [comandos] segun la respuesta" -- meaning the
intended shape is a `validator.py` function returning a `Rejection` via
`rejection_.build(kind=..., command=(cmd_no, cmd_new))`, same pattern as
`validate_similar`/`validate_distillation` in that file. This matters
because `tests/memory/test_rejection_relaunch_commands.py` (see
[relaunch-command-mechanism-notes](relaunch-command-mechanism-notes.md))
AST-scans exactly six files for `command = (...)` / `relaunch = (...)` --
`bin/memory/remove.py` is NOT one of them. If the rejection text is
written by hand inside `remove.py` instead of routed through a
`validator.py` function, the two new relaunch commands dodge that
existing radar test silently. A test file can't force where production
code lives, so this is flagged in the docstring for whoever implements,
not enforced as an assertion.

**Extraction/execution technique -- no relaunch command is ever hand-typed
in the test:** `_extract_relaunch_commands()` regexes `^\s*(gitmem remove
\S+.*)$` over the real combined stdout+stderr, filtered to lines
containing the real note id. `_fill_ellipsis_placeholders()` replaces each
`"..."` placeholder IN ORDER with test text and asserts the count of
placeholders found matches exactly what was expected -- reveals a
command-shape change as an explicit failure instead of a silent
mis-substitution. The `"..."` placeholder choice (not `<motivo>` or
anything else) is not invented -- it matches the established convention
already in production at `validator.py::validate_similar`'s duplicate-note
suggestion (`'"{note.headline}" --why "..." --description "..."
--replaces {first_id}'`). Both extracted commands (`--restriction no` and
`--restriction new --restriction-text ... --why ...`) are then actually
EXECUTED via `run_gitmem_script` (real subprocess, real git commit) and
their effects verified with the real readers (`indexes.read`,
`indexes.read_archive`, `query.by_id`) -- never asserted from the printed
text alone. This also closes the gap DEUDA.md #6.4 flagged: "falta la
prueba de que crear el muro con exito funciona -- solo esta probado el
camino en el que falla" (`test_remove_script.py` only had the
headline-too-long FAILURE path for `--restriction new`; this file adds
the SUCCESS path for both `no` and `new`).

**Fence-id extraction subtlety:** `conftest.py::extract_note_id()`'s regex
only matches the `"✅ {id} guardada"` pattern from `note.py`. When
`remove.py --restriction new` succeeds, `_create_fence()` prints `"⚠️
{fence_result.note_id} guardada — muro nacido de {args.id}"` -- a
different emoji. Reused a local regex (`r"[✅⚠️]\s*([A-Z]-\d+)\s+guardada"`)
instead of the shared helper for this one case.

Reference: [relaunch-command-mechanism-notes](relaunch-command-mechanism-notes.md)

## Round 2 (2026-08-05) — --restriction new must be all-or-nothing: fence rejection must not leave the incident closed

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

Reference: [remove-py-incident-close-full-contract-notes](remove-py-incident-close-full-contract-notes.md)
