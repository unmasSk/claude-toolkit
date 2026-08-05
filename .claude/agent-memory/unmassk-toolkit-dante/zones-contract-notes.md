---
name: zones-contract-notes
description: unmassk-memory (v2) Capa 1 -- lib/memory/zones.py (RED, no existe) contract tests from PIEZAS.md Sec.6.2, 5 rows; CRITICAL infra gap found AND FIXED same session -- import_lib_memory_module() now puts lib/memory/ on sys.path so flat sibling imports (PIEZAS Sec.3.3bis convention) resolve
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_zones.py` (5 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.6.2, literally, no extra coverage added
(same explicit test-first acceptance-granularity override as
[vocabulary-contract-notes](vocabulary-contract-notes.md) and
[memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md)).

**CRITICAL infra gap found, reported, then fixed same session (with
explicit one-off permission from the orchestrator to touch
`conftest.py`, normally off limits while teammates write parallel
`tests/memory/*.py` files):** `import_lib_memory_module()` loads each
`lib/memory/*.py` file via `importlib.util.spec_from_file_location`
with a synthetic non-dotted name and no parent package. Probed live:
a throwaway `zones.py` with a plain relative import
(`from .model import Zone`) failed at `exec_module()` with `ImportError:
attempted relative import with no known parent package` instead of the
`FileNotFoundError` a test-first RED contract needs. Since every Capa-1+
file (`zones.py`, `config.py`, `format.py`, `similar.py` -- the other
three being written in parallel this same session) depends on
Capa-0's `model.py`, this would have blocked GREEN for all four the
moment Ultron wrote a real cross-module import, not just for zones.py.

**The fix, and the convention it now codifies (PIEZAS.md Sec.3.3bis,
added same session):** `lib/memory/` modules import each other FLAT --
`from model import Note`, never `from .model import Note` (relative,
breaks -- no package context) and never `from memory.model import Note`
(collides with `tests/memory/`, see
[memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)).
This mirrors what the toolkit already does one level up: `bin/*.py`
scripts do `sys.path.insert(0, .../lib)` then `from parsing import ...`.
`import_lib_memory_module()` (`tests/memory/conftest.py`) now does the
same: inserts `LIB_MEMORY_DIR` at the front of `sys.path` (once, guarded
by `if LIB_MEMORY_DIR not in sys.path`) BEFORE building the spec for the
requested module, so any flat `from model import X` the loaded module
performs during `exec_module()` resolves through the normal import
machinery. The primary module itself is still loaded by explicit file
path (never sys.path lookup), so `FileNotFoundError` for a genuinely
missing module is untouched -- verified live both before and after the
fix, still 5/5 `FileNotFoundError` while zones.py doesn't exist.

**Bonus, discovered after the fix (not a new gotcha, the old one
resolving itself):** the earlier "compare fields, not `==`" workaround
for `Zone` dataclass identity (see below) is no longer strictly
necessary once both the test's `model` fixture and `zones.py`'s own
`from model import Zone` resolve through the SAME `sys.modules['model']`
entry -- same class object either way now. Left the field-by-field
assertion in place anyway (harmless, and still correct if a future
module ever re-imports `model` through a different mechanism).

**Mutation-check for this fix, ROUND 2 -- moved out of `lib/memory/`
entirely, mid-session, after a parallel colleague clobbered a real
in-progress `model.py` there with their own mutation-check throwaway
(unrecoverable, see
[mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)).
The orchestrator banned writing ANY file into `lib/memory/` for
verification purposes, even gated ones. Round 1 (below, kept for
history) DID write throwaway `model.py`/`zones.py` into the real
`lib/memory/` -- safe at the time (verified via `ls` immediately before
each write, nothing collided), but the technique itself is now
retired for this and every future session. **Round 2, the technique
going forward:** build the throwaway `model.py`/`zones.py` pair in the
session scratchpad (an isolated directory, never shared with other
agents), and run a standalone probe that replicates the exact fixed
mechanism (`if lib_dir not in sys.path: sys.path.insert(0, lib_dir)`
then `spec_from_file_location` + `exec_module`) parameterized by an
arbitrary directory instead of the hardcoded `LIB_MEMORY_DIR` constant.
This is strictly a BETTER proof, not just a safer one: it shows the fix
is a general mechanism (works against any directory containing sibling
flat imports), not something that happens to work only because of
something specific to the real `lib/memory/` path. Confirmed both
conditions against the scratchpad copy: a module with a real
`from model import Zone` loads and runs; a genuinely missing module
still raises `FileNotFoundError`, not a different/confusing error.
Then reconfirmed against the REAL (untouched, read-only) `lib/memory/`:
`test_zones.py` still 5/5 `FileNotFoundError` (zones.py genuinely
doesn't exist there), full toolkit `--collect-only` unaffected.

**Verification done for the fix itself, ROUND 1 (historical -- this is
what wrote into the real `lib/memory/`, safely at the time, now
superseded by round 2 above for all future sessions):**
1. `FileNotFoundError` preserved: `pytest test_zones.py -v` (zones.py
   still absent) -> unchanged, 5 errors, `FileNotFoundError`.
2. No process-global contamination: `pytest unmassk-toolkit/tests
   --collect-only -q` before and after the conftest edit -> **815 tests
   collected both times, identical test-ID diff (zero lines), exit 0
   both times**. Also checked no name collision exists between the 19
   planned `lib/memory/*.py` piece names (model, zones, vocabulary,
   emojis, utf8, config, format, similar, gitcmd, ids, indexes,
   rejection, notes, query, context, report_render, boot, validator,
   health) and any file already in `lib/` (v1) -- zero collisions found
   by direct file check. Ran a v1 sample
   (`test_parsing_consolidation.py` + `test_date_parsing_epoch_contract.py`,
   49 tests) for real (not just collected) post-fix -- all pass,
   confirming the `sys.path.insert` didn't just avoid a collection
   error but didn't change v1 runtime import resolution either.
3. Mutation-check with a REAL flat import (not the old
   spec_from_file_location workaround): throwaway `model.py` +
   `zones.py` where `zones.py` does `from model import Zone` for real,
   in the same bash block that deletes both right after. Loaded and
   passed 5/5. Reverted cleanly to 5/5 RED after cleanup.

**Related, now largely moot but kept for history -- dataclass identity
across two loaders:** before the fix, `model.Zone` loaded once by the
test's own `model` fixture and once (indirectly, via the old
`spec_from_file_location` internal-loader trick a throwaway `zones.py`
had to use to work around the broken relative import) were two DIFFERENT
class objects despite identical source -- `@dataclass`-generated `__eq__`
checks `self.__class__ is other.__class__` first, so `Zone(...) ==
Zone(...)` returned `False` even with matching fields. Row 5 compares
`reloaded.name`/`.description`/`.aliases` field-by-field instead of
`reloaded == original` -- kept as the safer pattern for any future
round-trip test in this repo comparing a `model.py` dataclass instance,
even though the specific cause is now fixed.

**Row 4 (concurrency) design:** two real `threading.Thread`s +
`threading.Barrier(2)` calling `zones.add()` at forced-simultaneous start
against the same `tmp_path` file, asserting all three zones (one seeded
before the race, two added during it) survive and no thread raised. No
`sleep`-based race widening (this repo's own
[file-lock-lost-update-contract-notes](file-lock-lost-update-contract-notes.md)
flagged that pattern as flaky elsewhere) -- a `Barrier` gives
deterministic simultaneous start without timing assumptions. The
assertion is deterministic in both directions: correct locking always
passes, no false failures on correct code (the "no flaky tests" rule).

**Row 1-3 data-seeding decision:** none of the three hand-write a
`zones.json` fixture with an assumed on-disk schema -- Sec.6.2 doesn't
fix the JSON shape literally (unlike e.g. `vocabulary.py`'s `FIELDS`,
cited verbatim). Instead every test seeds via `zones.add()` and reads
back via `zones.load()` -- the real producer/consumer pair, never a
hand-typed fixture standing in for one (unmassk-standards SS34).

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory/test_zones.py -v` -> 5
errors, `FileNotFoundError: lib/memory/zones.py`, one per row, RED by
design. Only files touched this session: `test_zones.py` (new) and
`tests/memory/conftest.py` (the flat-import sys.path fix, explicit
one-off permission) -- no other teammate's test file touched.

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md), [memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md)
