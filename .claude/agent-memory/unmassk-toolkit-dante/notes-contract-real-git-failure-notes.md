---
name: notes-contract-real-git-failure-notes
description: lib/memory/notes.py (PIEZAS.md Sec.8.1) RED contract, the transaction piece "where the system can corrupt itself" -- .git/index.lock pre-creation as a real git-commit-failure technique, and the existing_in_zone=() trick that neutralizes similar.py cross-talk between test notes
metadata:
  type: feedback
---

Test-first contract pass for `unmassk-toolkit/lib/memory/notes.py`
(`unmassk-toolkit/tests/memory/test_notes.py`, 6 RED tests, PIEZAS.md
Sec.8.1's exact 6-row table, no more). This is the piece PIEZAS.md calls
"donde el sistema se puede corromper a si mismo": the rule under test is
"nota + linea de indice viajan en el mismo commit, o ninguna de las dos".

**Real git-commit-failure technique (rows 2/3), reusable for any future
"commit fails, verify recovery" contract in this repo:** pre-create
`.git/index.lock` (empty file) inside the target repo BEFORE calling the
function under test. Real git's own lock acquisition (`O_CREAT|O_EXCL`
semantics) then refuses with a genuine `fatal: Unable to create
'<repo>/.git/index.lock': File exists.` on ANY subsequent git operation
that touches the index (`add`, `commit`, ...) in that repo -- no need to
break file permissions or mess with git identity config. Clean up in a
`finally` (contextmanager `_forced_git_index_lock`) so the temp repo
never leaks a stuck lock across tests. For row 3 (verify the propagated
error is the REAL git message, not fabricated per unmassk-standards
Sec.34): fired a SECOND real `git commit` (a "probe") against the same
locked repo, immediately after the function-under-test's own attempt,
and asserted the probe's first stderr line is a substring of
`result.git_error` -- the expected value comes from the real git binary
in this same run, never hand-typed.

**`validator.validate_replacement` only ever compares against
`ctx.existing_in_zone` (a static tuple the caller supplies), never
against the live index or any note committed earlier in the same test
run.** This means multiple notes written by the same test (rows 4 and 6:
discard_alternatives's 2 alternatives, 6 concurrent writers) can safely
reuse near-identical headlines/descriptions without ever triggering a
"parecido, falta --replaces" rejection from each other -- as long as the
shared `Context` fixture keeps `existing_in_zone=()`. Confirmed by
reading `similar.find_similar()`'s signature: it takes `existing` as an
explicit parameter, never re-reads anything. Saved real design time:
almost over-engineered unique-vocabulary headlines per note before
noticing this.

**Discovering which of the 7 live index files (DECISIONS.md, MEMOS.md,
...) a given type maps to is NOT assumed anywhere in the tests --
discovered live instead.** PIEZAS.md's contract for `notes.py`/`indexes.py`
never states the type-letter-to-filename mapping as a fixed table (it's
implied only by naming convention), so `_index_line_for(indexes_mod,
vocabulary_mod, root, note_id)` scans all 7 non-ARCHIVED.md files via
`indexes.read()` and returns whichever one contains the id. Reused
across rows 1, 2 (baseline snapshot of ALL 7 files, not just the
type-relevant one -- stronger test, catches a stray write to the WRONG
file too), 4, and 6.

**`Note.id` placeholder convention for pieces where the callee assigns
the real id internally:** PIEZAS.md Sec.8.1's own "El orden de write es
el contrato" states id-assignment happens INSIDE `write()` ("candado ->
identificador -> validar -> ..."), after the caller hands over the
`Note`. Since `model.Note.id` is a required field with no default, the
test factory passes `id=""` as an explicit, documented placeholder, and
every assertion about the real id is derived from `WriteResult.note_id`
-- never from the input placeholder. This makes the tests correct
regardless of whether Ultron's `write()` ends up respecting or ignoring
the caller-supplied id.

**Fixture-order-for-RED convention (already established by
test_gitcmd.py/test_validator.py, reconfirmed here):** when the module
under test (`notes`) is requested as the literal FIRST parameter in a
test function's signature, and every other fixture it needs
(`model`/`config`/`validator`/`indexes`/`format_mod`/`vocabulary`) is
already in production (won't raise), pytest resolves `notes` first and
the `FileNotFoundError` on `lib/memory/notes.py` surfaces cleanly, per
test, never masked by a sibling dependency's own missing-file error.
Verified live: all 6 tests error individually citing `notes.py` by name,
never `model.py`/`indexes.py`/etc.

See also: [file-lock-lost-update-contract-notes](file-lock-lost-update-contract-notes.md)
(the v1 file_lock() concurrency-test lineage this session's row-6
concurrent-writers test descends from) and
[gitcmd-contract-notes](gitcmd-contract-notes.md) (the v2 sibling piece
whose own row-2 "dos procesos se serializan" thread pattern this test
file's row 6 directly reuses).
