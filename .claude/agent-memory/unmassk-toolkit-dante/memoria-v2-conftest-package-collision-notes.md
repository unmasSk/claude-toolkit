---
name: memoria-v2-conftest-package-collision-notes
description: unmassk-toolkit tests/ + tests/memory/ conftest.py sys.modules collision — __init__.py fix + relative-import follow-up, CLOSED (770 tests, 9 known v1 errors)
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/conftest.py` (v1) and `unmassk-toolkit/tests/memory/conftest.py` (v2)
both register in `sys.modules` as bare module `conftest` when neither directory is a package —
pytest's rootless-conftest import inserts each conftest's directory into `sys.path` and imports it
as `conftest`; whichever loads second wins the `sys.modules['conftest']` slot, breaking every v1
`test_*.py` that does `from conftest import ...` (55 collection errors instead of 9, 77 tests
collected instead of 768).

**Hypothesis tested (2026-08-02):** create `tests/memory/__init__.py` only (NOT `tests/__init__.py`).
Reasoning: making `tests/memory` a package should make its conftest register as `memory.conftest`,
leaving `tests/conftest.py` alone as `conftest`, so they stop competing.

**Result: half confirmed, half broken — do NOT treat as a finished fix.**

- v1 side: WORKS EXACTLY AS PREDICTED. `tests --collect-only` goes from 55→9 v1 errors, 77→768 v1
  tests collected. Ran `test_upgrade.py`, `test_boot_tombstones.py`, `test_crown.py` for real (not
  just collected) — all three import their correct `tests/conftest.py`, no ImportError. (They do
  have pre-existing unrelated assertion failures — crown/tombstone logic bugs, nothing to do with
  this fix.)
- v2 side: BREAKS. `tests/memory/test_conftest_smoke.py` itself does `from conftest import run_git`
  at module level, relying on the SAME implicit "no `__init__.py` → my directory's conftest becomes
  bare `conftest`" trick that caused the original collision. Once `tests/memory/` is a package, its
  own conftest becomes `memory.conftest`, but the smoke test's `from conftest import run_git` still
  resolves to whatever is ALREADY in `sys.modules['conftest']` — which is v1's `tests/conftest.py`
  (loaded earlier in the same collection pass) — and that module has no `run_git`. Net: overall
  collect-only goes to 768 tests + 10 errors (not the targeted 770 + 9); `pytest tests/memory -q`
  no longer collects at all (0 passed, was 2 passed before the `__init__.py` was added).

**Symmetric trap:** the exact mechanism that un-collides v1 (directory → package → conftest gets a
dotted name) simultaneously breaks any test file in that same directory that imports its sibling
conftest via the bare `from conftest import ...` idiom instead of a relative/explicit import. A fix
that only adds `tests/memory/__init__.py` cannot both keep v1 untouched AND keep v2's own
bare-`conftest` import working — those two constraints are in direct tension.

Left `tests/memory/__init__.py` in place (empty) per the task's own instruction to create it for
verification; did NOT create `tests/__init__.py`; did not touch `tests/conftest.py` or any
production code; did not attempt an alternative fix — reported and stopped as instructed.

**Follow-up (2026-08-02) — CLOSED.** Fixed the symmetric trap noted above: changed
`tests/memory/test_conftest_smoke.py`'s own `from conftest import run_git` to
`from .conftest import run_git` (relative import within the now-package `tests/memory`).
Nothing else touched (not `tests/conftest.py`, not `tests/memory/conftest.py`, not the
`__init__.py`). Verified: `pytest tests/memory -q` → 2 passed; `pytest tests --collect-only -q`
→ 770 tests collected, 9 errors (768 v1 + 2 memory; same 9 known v1 collection errors, none new).
Pattern for future v2 test files in `tests/memory/`: import sibling `conftest.py` with the
relative form (`from .conftest import X`), never bare `from conftest import X` — bare form
will silently resolve to whichever `conftest` module loaded first into `sys.modules['conftest']`
(currently v1's `tests/conftest.py`).

Reference: [conventions.md](conventions.md), [edge-cases.md](edge-cases.md)
