---
name: memoria-v2-fase0-emojis-utf8-contract-notes
description: unmassk-memory (v2) Capa 0 -- lib/memory/utf8.py (GREEN, ya cumple) + lib/memory/emojis.py (RED, no existe) contract tests from PIEZAS.md Sec.5.1/5.2; new `import memory.X` name-collision gotcha and its fix
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_utf8.py` (3 tests, GREEN) and
`test_emojis.py` (3 tests, RED by design) -- one test per row of the "Sus
tests" table in `docs/memoria-v2/PIEZAS.md` Sec.5.1/5.2, literally, no
extra coverage added (explicit instruction for this task, overrides
Dante's usual EXHAUSTION PROTOCOL). Wrote `test_seven_types_have_emoji_and_no_extra`
as ONE test with two assertion groups (not two tests) after an initial
pass over-split row 1 into 2 tests and row 2 into 3 -- caught and
collapsed back to exactly 3 tests total to match the "un test por fila,
ni uno mas" rule.

**New gotcha, distinct from the `tests/memory/__init__.py` conftest
collision already documented in
[memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md):**
`import memory.<x>` (with `lib/` on `sys.path`, reaching `lib/memory/<x>.py`
as a namespace package) collides with `tests/memory/` itself, which is
ALSO a package (has `__init__.py`, required for the conftest fix above).
pytest registers `sys.modules['memory']` -> `tests/memory/` before a test
in that same directory gets to import `lib/memory/<x>.py`, which would
also bind to the name `memory`. Confirmed live: `import memory.utf8`
inside a file under `tests/memory/` fails with
`ModuleNotFoundError: No module named 'memory.utf8'` even though
`lib/memory/utf8.py` exists on disk and is directly importable from a
plain script. **Fix, now in `tests/memory/conftest.py`:**
`import_lib_memory_module(name)` loads `lib/memory/<name>.py` via
`importlib.util.spec_from_file_location(f"lib_memory_{name}", path)` +
`module_from_spec` + `exec_module` -- never touches the `memory` name in
`sys.modules`, so the collision cannot occur. Bonus: `spec_from_file_location`
does NOT check the file exists (`spec` is created either way); the
failure only surfaces at `exec_module()` as `FileNotFoundError` -- this is
exactly the RED signal wanted for a test-first contract against a module
that doesn't exist yet (`emojis.py`), verified live before relying on it.
**Rule going forward for every future `lib/memory/*.py` test file:** use
`from .conftest import import_lib_memory_module` + `import_lib_memory_module("x")`,
never `import memory.x` or `from memory import x`, for as long as both
`tests/memory/` and `lib/memory/` coexist as same-named packages on
different `sys.path` roots.

**RED-fixture technique for "module doesn't exist yet, want N distinct
red results not 1 collection error":** put the `import_lib_memory_module()`
call inside a `@pytest.fixture` (not at module level). A module-level
import failure produces ONE pytest collection error for the whole file
(0 tests shown as collected); wrapping it in a fixture that every test
requests makes each test fail individually at setup (`ERROR at setup of
test_X`), giving a clean 1:1 mapping from contract-table row to reported
red result -- verified live (3 fixture-based `ERROR`s, one per row,
`pytest -v` output).

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory -v` -> 5 passed (2
pre-existing smoke + 3 utf8), 3 errors (emojis, RED as designed).
Full-suite `--collect-only` sanity check: 776 collected / 7 errors, all 7
errors pre-existing v1 drift (`ImportError: cannot import name
'scan_trailers_memory' from 'parsing'` in several `test_*freshness*`/
`test_issue61_*`/`test_parsing_consolidation.py`/
`test_trailer_newline_regression.py` files) -- unrelated to this task,
not touched, confirmed by not having edited any v1 file.

Reference: [memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md), [memoria-v2-fase0-conftest-notes](memoria-v2-fase0-conftest-notes.md)

**Correction (2026-08-02): stale key + accidental-green gotcha in
`test_mappings_are_immutable`.** `CHANNEL_EMOJI`'s real key was renamed
`"context"` -> `"next"` in production (`lib/memory/emojis.py`, decision:
the ⏩ marks the Next, not the context body) but the test still asserted
`emojis.CHANNEL_EMOJI["context"] = "x"` raises `TypeError` -- still green,
for the wrong reason. **Gotcha for any future `MappingProxyType`
immutability test**: `mappingproxy.__setitem__` raises `TypeError` for
ANY key, whether or not it exists in the mapping -- so a mutation-attempt
assertion alone never proves the test is anchored to a real, current
production key; it passes identically against a renamed/invented/deleted
key. Fix pattern: precede each mutation attempt with `assert key in
mapping` so a future rename breaks the RIGHT assertion (the precondition)
instead of silently staying green. Applied to all three mappings in
`test_emojis.py::test_mappings_are_immutable` (`TYPE_EMOJI["D"]`,
`CHANNEL_EMOJI["next"]`, `SECTION_EMOJI["restricciones"]`).
