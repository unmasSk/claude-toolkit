---
name: incident-close-question-contract-notes
description: test_remove_incident_close_question.py RED contract -- closing an I- incident without --restriction must ask (TEXTOS.md Sec.1.10), never crash with raw argparse; M/D close directly with no question
metadata:
  type: project
---

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
[rejection-relaunch-command-ast-crosscheck-notes](rejection-relaunch-command-ast-crosscheck-notes.md))
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

Reference: [rejection-relaunch-command-ast-crosscheck-notes](rejection-relaunch-command-ast-crosscheck-notes.md)
