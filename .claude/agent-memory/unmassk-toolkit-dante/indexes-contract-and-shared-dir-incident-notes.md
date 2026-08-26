---
name: indexes-contract-and-shared-dir-incident-notes
description: unmassk-memory (v2) Capa 2 -- lib/memory/indexes.py (RED, test-first) PIEZAS.md Sec.7.3 5-row contract; a live incident where my own mutation-check wrote into the SHARED lib/memory/ dir mid-session and the coordinator banned that pattern outright
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_indexes.py` (5 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.7.3, literally, no extra coverage added
(same test-first acceptance-granularity override as
[vocabulary-contract-notes](vocabulary-contract-notes.md),
[similar-contract-notes](similar-contract-notes.md),
[config-contract-notes](config-contract-notes.md)).

**INCIDENT, read this first if doing a mutation-check in this repo
again.** My usual mutation-check technique (write a throwaway real
implementation straight into `lib/memory/<name>.py`, run pytest, delete
it) is BANNED for this shared directory from 2026-08-02 onward. Several
colleagues write different `lib/memory/*.py` files in parallel in the
same session; one agent's throwaway silently clobbered another's
in-progress file before I could react (not mine, but the coordinator
caught the pattern and shut it down for everyone). **New rule, no
exceptions:** never write ANY file, temporary or not, into
`lib/memory/` (or any shared production directory colleagues touch
concurrently) for verification purposes. If a mutation-check needs a
real module on disk, build it entirely under a private scratch
directory (session scratchpad, never `/tmp` directly) and redirect the
loader there -- never the shared tree, not even for a second.

**Working technique that replaced it (verified live, safe, reusable):**
`unmassk-toolkit/tests/memory/conftest.py`'s `import_lib_memory_module()`
reads a module-level global `LIB_MEMORY_DIR` to find files. Load
`conftest.py` a second time via `importlib.util.spec_from_file_location`
under a throwaway module name, monkeypatch that loaded copy's
`LIB_MEMORY_DIR` attribute to point at a scratch directory containing
throwaway `.py` files, then call `import_lib_memory_module()` on THAT
copy -- the real `conftest.py` on disk is never opened for writing, and
the real `lib/memory/` is never touched. To run the REAL test functions
against this redirected loader (not just hand-rolled assertions),
load the real `test_indexes.py` the same way, register the two loaded
modules under a synthetic package name in `sys.modules` so its
`from .conftest import import_lib_memory_module` (relative import)
resolves, then call each `test_*` function directly with manually
constructed fixture values (`conftest.import_lib_memory_module(...)`
for `indexes`/`model`/`vocabulary`, a `tempfile.mkdtemp()` for
`tmp_path`). Confirmed both the positive check (throwaway correct impl
-> all 5 pass) and a negative check (broke `seed()` idempotency in the
scratch copy -> `test_seed_twice_does_not_duplicate_or_erase` correctly
raised `AssertionError`, not a wrong-reason error) entirely from
`/private/tmp/.../scratchpad/`, zero writes under `unmassk-toolkit/`.

**Real bug this incident's investigation surfaced, distinct from the
shared-dir rule -- matters for EVERY future `lib/memory/*.py` test that
compares objects returned by a module-under-test against objects built
by a test fixture:** `import_lib_memory_module()` never registers
anything in `sys.modules` and never caches -- every call, even for the
exact same file, returns a BRAND NEW module object with brand-new
classes. A frozen dataclass's generated `__eq__` checks
`self.__class__ is other.__class__` before comparing fields. So if
`indexes.py` (once real) needs to construct `IndexLine`/`ArchiveLine`
internally to return them from `read()`/`read_archive()`, and MY test
independently builds expected `IndexLine`/`ArchiveLine` instances via
its own `model` fixture (`import_lib_memory_module("model")`), those
two objects are NEVER the same class, no matter how correct the
implementation is -- a plain `result == expected` assertion would fail
against a fully correct `indexes.py`. **A parallel colleague already
hit and fixed the identical problem in `test_format.py`** (see that
file's `_assert_fields_match` helper and its docstring, itself citing
`zones-py-full-contract-notes.md` from ANOTHER colleague who found it first in
`test_zones.py`) -- three independent test files in the same session
converged on the same fix. Ported the same pattern into
`test_indexes.py` as `_assert_fields_match`/`_assert_lines_match`
(field-by-field via `dataclasses.fields(expected)`, `assert parsed is
not None` first, tuple-length check before zipping). **Rule for every
future `lib/memory/*.py` test file whose contract returns a `model.py`
dataclass instance (not just receives one, like `similar.py` did):
never compare with bare `==`** -- only tests that merely filter/return
the SAME object references the caller already passed in (no internal
reconstruction) are safe with `==` (confirmed this is why
`similar-contract-notes.md`'s mutation-check never hit this: `similar.py`
returns items straight out of the `existing` tuple, never builds new
`Note`s).

**Row-specific notes:**

- Row 1 (`seed` idempotent) -- `seed()` a project that already has a
  note (via `insert()`), `seed()` again, `read()` must still show
  exactly that one line via `_assert_lines_match`, not `()` (wiped) and
  not two copies (duplicated) -- one tuple-equality-style check covers
  both failure directions in one assertion.
- Row 2 (three archive destination forms) -- the three raw
  `ARCHIVED.md` lines are copied BYTE FOR BYTE out of
  `docs/memoria-v2/TEXTOS.md` Sec.4's own literal example (verified via
  `repr()` on the source file before typing anything, not eyeballed --
  double spaces around `date`/`→` matter and are easy to get wrong by
  hand). Written directly into the file (bypassing a future
  `indexes.archive()`) on purpose: this row tests the READ half of the
  contract against a file that could have been produced by an older
  writer version, not a round trip of the current writer.
- Row 3 (counts computed, never stored) -- `counts(root) ->
  Mapping[str, int]` doesn't fix its key type in PIEZAS Sec.7.3. Assumed
  the key is the same literal filename (`"DECISIONS.md"`) already used
  by `read`/`insert`/`remove`'s `name: str` param -- disclosed as an
  assumption (same discipline as `FieldSpec`/`TypeSpec` in
  vocabulary-contract-notes.md). Proven "never stored" by writing a
  THIRD line directly to the file bypassing `indexes.insert()`, then
  calling `counts()` again and asserting the new total -- a cached
  counter would still show the old figure.
- Row 4 (insert into nonexistent index fails loud) -- `root` directory
  IS created explicitly (`root.mkdir(parents=True)`) but `seed()` is
  never called, isolating "index file missing" from "container
  directory missing" (same isolation discipline as
  config-contract-notes.md's row 3). Asserts both `pytest.raises` AND
  that no half-created file appears afterward.
- Row 5 (round trip, three lines, order + correct index) -- 2 inserts
  into DECISIONS.md + 1 into MEMOS.md, `read()` on each file must
  return exactly its own lines in insertion order -- catches both
  cross-file leakage and insert-N+1-clobbers-insert-N bugs in one test
  (two asserts, same logical round-trip check, per the "one row = one
  test" rule already established for this contract table).

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory/test_indexes.py -v` ->
5 errors, `FileNotFoundError: lib/memory/indexes.py` at fixture setup,
one per row -- RED for the right reason. Full-suite sanity check
(`unmassk-toolkit/tests/memory`, not asked but run to confirm no bleed
into parallel colleagues' files): 29 passed / 15 errors (5 mine +
4 test_gitcmd.py + 3 test_ids.py + 3 test_rejection.py, all belonging
to other colleagues' own in-progress RED contracts, confirmed via
`git status --porcelain` showing only `test_indexes.py` as new from
this task).

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [similar-contract-notes](similar-contract-notes.md), [config-contract-notes](config-contract-notes.md), [memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)

**Second regression added 2026-08-02, Moriarty-confirmed, still RED (fix is
Ultron's, not mine):** `insert(line, name, root)` never validates `name`
against `vocabulary.INDEX_FILES` before touching disk -- it's plain `root /
name`. Sec.7.3's own contract line ("Nadie mas los toca") was never actually
enforced in code. Moriarty's PoC passed `"zones.json"` (real neighbor file in
the same `root` dir, confirmed via `validator.py`'s own rejection text citing
`.claude/project-memory/zones.json`) and `insert()` appended an index line
straight onto valid JSON, corrupting it (`json.load` -> "Extra data") with
**zero exception raised** -- silent corruption, whole suite green. Test added:
`test_insert_into_target_outside_index_files_fails_loud_and_leaves_file_untouched`.
Two-part assertion, both required because raising AFTER writing is still
corruption: (1) `pytest.raises(Exception)` around the call, (2) foreign
file's content byte-for-byte unchanged afterward (plus a semantic
`json.loads(...) ==` re-check as a more-readable secondary signal on the same
fact, not a looser substitute). PoC lived at
`scratchpad/moriarty_indexes/poc_wrong_target.py` -- ran it first, confirmed
`insert() raised an exception? None` / `zones.json valid JSON after: False`
live, before writing the test. Confirmed RED for the right reason
(`DID NOT RAISE`) and zero bleed: `pytest tests/memory -q` -> 1 failed (mine)
/ 72 passed.

**Retired 2026-08-04: row 3's own test
(`test_counts_are_computed_by_reading_never_stored`), because it was the
only thing keeping `indexes.counts()` alive.** Ultron measured zero callers
of `counts()` anywhere in `lib/memory/`, `bin/`, `hooks/` -- not even inside
its own file -- because every real consumer of "notes per type" already
computes it independently by reading git history directly (`boot.py`'s
COUNTS block, `report.py::_by_type`), never touching the index files. Before
deleting, checked whether the test covered any OTHER `indexes.py` behavior
not covered elsewhere in the file: no -- it only exercised `seed`/`insert`
(already covered by rows 1 and 5) plus `counts()` itself. Removed the test
body, left an inline retirement comment where it lived (matching this
repo's established pattern, e.g. `tests/test_file_lock_regressions.py:277`
and `tests/test_drift.py:146`), and trimmed the now-stale "Asuncion
declarada" docstring paragraph (it only existed to disclose `counts()`'s key
type, which no longer applies to any live test) plus the module docstring's
row-3 line. `counts()` itself stays in `lib/memory/indexes.py` for now --
Ultron deletes the function separately, in a later pass. This is the third
same-day occurrence of the pattern "a test exists only to prove an unused
function works" -- see the sibling deadend memo
`deadend/memoria-v1-superficie` for the lesson this generalizes
("ocho tests en verde no demuestran que algo se use"). Full suite after
retirement: `tests/memory -q` -> 308 passed, 1 failed
(`test_boundary.py::test_every_public_symbol_has_a_real_importer`, a
pre-existing unrelated orphan-symbol scan that already lists
`indexes.counts` among its known orphans -- not caused by this change).
