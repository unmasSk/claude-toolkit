---
name: unmassk-toolkit-python-entrypoints
description: unmassk-toolkit/bin and hooks Python entry points -- sys.path/lib import variants and the encoding guard pattern (issue #52)
metadata:
  type: project
---

## Three sys.path-to-lib variants across bin/*.py and hooks/*.py

When touching every entry point in `unmassk-toolkit/bin/*.py` and
`unmassk-toolkit/hooks/*.py` (23 files total, no more no less -- confirmed
by `find unmassk-toolkit/bin unmassk-toolkit/hooks -name '*.py'`), expect
three different header shapes, not one:

1. **Direct insert** (most common):
   `sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))`
   immediately followed by `from X import Y` lines, no guard.
2. **Guarded `_LIB_DIR` insert** (pre-merge-gate.py, pre-task-recall.py,
   session-start-crew.py, pre-memory-dedup-gate.py):
   ```python
   _HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
   _LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
   if _LIB_DIR not in sys.path:
       sys.path.insert(0, _LIB_DIR)
   ```
3. **No lib import at all** (`hooks/validate-memory-path.py` only) --
   fully self-contained script, subprocess-only git access. Any change that
   must apply to "every entry point" (not just the ones already importing
   lib/) needs its own `sys.path.insert` added here, not just a bare
   `from lib_module import X`.

`bin/git-memory-bootstrap.py` and `bin/git-memory-install.py` use variant 1
but with multiple `from X import Y` blocks split across paragraphs (their
own lib submodules bootstrap_tree/bootstrap_deps/... and
install_inspect/install_apply); the shared-lib import block is the FIRST
one, before those.

## Encoding guard (issue #52, T1) -- fail-open UTF-8 stream reconfigure

`lib/encoding_guard.py` exports `force_utf8_streams()`: reconfigures
stdout/stderr to UTF-8 with `errors="replace"`, wrapped in
`try/except (AttributeError, ValueError, OSError)` so the guard itself can
never crash (fail-open contract every hook in this project already
follows). Call it as the FIRST statement after the sys.path-to-lib
mutation, before any other `from lib_module import ...` -- in all three
header variants above. [[lessons]]

Root cause was House's finding: no entry point forced UTF-8, so any
print() of an emoji/arrow crashes with UnicodeEncodeError under a Windows
legacy codepage (reproducible anywhere via `PYTHONIOENCODING=cp1252`).
`tests/conftest.py`'s `run_cmd()` already does the parent-side symmetric
fix (`subprocess.run(..., encoding="utf-8")`) -- don't re-fix that, it's a
test file (Dante's territory).

## No twin/fallback needed for encoding_guard.py

`lib/_symlink_safe_open.py` exists because `tests/test_migrate_statusline.py`
stubs `sys.modules["git_helpers"]`/`["parsing"]`/`["version"]` with minimal
fake modules for one test file, and call sites need a defensive
`try: from git_helpers import X / except ImportError: from
_symlink_safe_open import X_fallback` fallback. Before adding a similar
fallback for any NEW lib/ module, grep `tests/` for
`sys.modules[stub_name]` or `types.ModuleType` to see exactly which module
names get stubbed -- only add a fallback if your new module's name (or a
module it needs) is in that stub set. `encoding_guard.py` is not, so a
direct unconditional `from encoding_guard import force_utf8_streams` is
correct with no defensive fallback.
