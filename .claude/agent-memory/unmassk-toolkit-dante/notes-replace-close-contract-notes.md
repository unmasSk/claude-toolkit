---
name: notes-replace-close-contract-notes
description: lib/memory/notes.py replace()/close() RED contract (PIEZAS.md Sec.8.1, filas 7-11, DEUDA.md punto 10) -- reused indexes.archive()/read_archive() already in production, and the pytest.raises(Exception)-vacuously-catches-NotImplementedError trap
metadata:
  type: feedback
---

Context: `notes.py`'s `replace()`/`close()` were declared (Superficie,
PIEZAS.md Sec.8.1) but always raised `NotImplementedError` on purpose --
the original 6-row "Sus tests" table explicitly excluded them ("esas
seis, ni una mas"). The owner later appended 5 new rows to that same
table (2026-08-02) once the source texts closed the gap DEUDA.md punto 10
claimed was open (spec Sec.5's two retirement paths, TEXTOS.md Sec.4's
three literal archive-destination forms, PIEZAS's own "un solo commit"
line). Task: write exactly those 5 rows as RED tests in the SAME file
(`test_notes.py`), touching no production code -- same acceptance-
granularity discipline as every other test-first contract pass in this
branch.

**The archive machinery was ALREADY built and green** --
`indexes.archive(line, root)` (writes `ArchiveLine` to ARCHIVED.md via
`format.build_archive_line`) and `indexes.read_archive(root)` (parses it
back via `format.parse_archive_line`, recognizing exactly the 3 literal
forms `replaced by <ID>` / `closed: <motivo>` / `promoted to <ID>`) were
both already in production from the Capa 2 indexes.py contract pass. This
meant the 5 new tests could assert against the REAL reader
(`indexes.read_archive` -> `ArchiveLine.destination`/`.destination_detail`)
instead of hand-typing the archive line's literal text -- no fabricated
ground truth needed for the round-trip half of the contract (§34). Added
one small local helper, `_archive_line_for(indexes_mod, root, note_id)`
(linear scan over `read_archive()` for the matching id), and
`_read_all_eight_files(root, vocabulary_mod)` -- the existing
`_read_all_index_contents` (rows 1-6) deliberately EXCLUDES ARCHIVED.md
because plain `write()` never touches it; `replace()`/`close()` do, so the
"nothing changed on failure" checks (rows 10/11) needed a sibling that
includes all 8 files.

**Real trap caught by re-running the suite after writing, not assumed:**
row 11's "unknown id bounces" test used `pytest.raises(Exception)`
(generic, matching the note in indexes.py's own precedent that `remove()`
already raises `ValueError` for an id not present in its file). That
passed VACUOUSLY today -- `NotImplementedError` (what the stub actually
raises, unconditionally) IS an `Exception`, so the bare `pytest.raises`
context manager exited cleanly for the wrong reason, and the test went
green while the other 4 new tests were correctly red. **Fix: capture
`exc_info` and assert `not isinstance(exc_info.value, NotImplementedError)`
right after each `pytest.raises` block.** This flips the test to fail
loud, for the right reason, while the function is still a stub, and will
correctly pass once Ultron's real implementation raises anything OTHER
than `NotImplementedError` for a genuinely nonexistent id. General rule
for this repo: whenever a RED contract test's own passing condition is
"any exception was raised" against a target that is CURRENTLY a
universal-raise stub, that assertion is vacuously satisfied by the stub
itself -- always add the `not isinstance(..., NotImplementedError)`
(or whatever the stub's exact exception type is) guard so the test is
provably red for the intended reason, not by coincidence. Confirmed by
running the file before AND after the fix: before, `5 failed, 10 passed`
(row 11 silently green); after, `5 failed, 10 passed` -- same headline
count, but the failure log for row 11 now shows the intended
`AssertionError` about `NotImplementedError`, not silence.

**Realistic-usage decision disclosed in the test file itself (not
guessed silently):** rows 7/8 (successful `replace()`) set
`new_note.replaces = old_id` and pass `known_ids=frozenset({old_id})` to
`make_context()`, because `validator.validate_pointers` (already in
production) rejects any `note.replaces` not present in `ctx.known_ids`,
and spec Sec.5 describes the real caller contract as "el relanzamiento
con `--replaces M-041` escribe la nueva con su puntero". Without this,
the test would prove the pointer-rejection path, not `replace()` itself.
Row 11 (nonexistent id) deliberately leaves `new_note.replaces = None`
(default) to isolate the "old_id not found anywhere" failure from the
unrelated pointer-validation failure.

**Type-letter-from-id assumption for row 11:** used `"M-999999"` /
`"I-999999"` (a real vocabulary letter, absurdly high counter) rather
than a malformed id -- since `Note.id` embeds its type letter by
convention (`"M-021"`), this is the faithful "genuinely nonexistent
identifier" case the row describes, not a "malformed id" case (a
different, untested scenario).

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_notes.py -v`
-> 5 failed (all 5 new rows, all `NotImplementedError` or the
`not isinstance(..., NotImplementedError)` guard tripping on it) / 10
passed (6 original rows + 3 fixed regressions + 1 red regression,
untouched). `--collect-only` -> 15 tests, 0 collection errors.
`py_compile` clean. `git status --porcelain` on `tests/memory/` and
`lib/memory/` confirmed only `test_notes.py` carries my edits -- the `M`
markers on `utf8.py`/`conftest.py`/`test_conftest_smoke.py` in the same
status output belong to concurrent colleagues, not this task.

See also: [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)
(the `.git/index.lock` forcing + git-probe techniques rows 10 reuses
verbatim), [notes-three-critical-regressions-notes](notes-three-critical-regressions-notes.md)
(the `notes.gitcmd`/`notes.indexes` module-attribute monkeypatch
technique, not needed here but same file), [indexes-contract-and-shared-dir-incident-notes](indexes-contract-and-shared-dir-incident-notes.md)
(`indexes.archive()`/`read_archive()`'s own contract, reused read-only
here, never reimplemented).
