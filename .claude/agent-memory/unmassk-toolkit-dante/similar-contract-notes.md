---
name: similar-contract-notes
description: unmassk-memory (v2) Capa 1 -- lib/memory/similar.py (RED, test-first) contract from PIEZAS.md Sec.6.5, 4 rows; cross-fixture ordering trick when a test needs a second not-yet-existing module (model.py) just to build fixtures
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_similar.py` (4 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.6.5, literally, no extra coverage added
(same test-first acceptance-granularity override as
[vocabulary-contract-notes](vocabulary-contract-notes.md)).

**New pattern: a piece under test needs a *second* not-yet-existing
module just to build its fixtures.** `find_similar(candidate, existing,
threshold)` takes/returns `Note` objects, and `Note` lives in
`lib/memory/model.py` -- also not written yet (a different, unassigned
piece; three other colleagues were writing `zones.py`/`config.py`/
`format.py` tests in parallel, not `model.py`). Built two independent
fixtures, `similar` (no deps) and `make_note` (calls
`import_lib_memory_module("model")` internally, not as a fixture
dependency), and listed `similar` FIRST in every test signature. pytest
instantiates independently-requested fixtures in parameter-declaration
order, so `similar`'s `FileNotFoundError` (the piece actually under
contract) is what gets reported, not `model`'s -- verified live (`pytest
-v` output shows `ERROR at setup` pointing at `lib/memory/similar.py`
missing, in all 4 tests). Rule going forward: when a fixture chain
touches two not-yet-existing modules, put the module under test's own
fixture first in the signature so the RED reason matches the task, not
a coincidental dependency.

**Row 3 test design (cross-zone, the trickiest row):** varied ONLY
`zone2` (`product/auth` vs `product/billing`), kept `zone1` identical
and content (headline/description/why/keys) byte-identical between
candidate and existing. Deliberately narrower than varying both zone
fields -- catches a shallow implementation that only filters by
`zone1` and would wrongly match on `zone2` drift alone. Confirmed this
distinction matters by testing the throwaway fake impl (below) against
it before relying on it.

**Threshold choice:** `_THRESHOLD = 0.5`, not derived from any spec
(none exists -- `threshold` is a caller-supplied float per the
signature). Deliberately not testing boundary values (would be
coverage the task's 4-row cap forbids) -- instead built "near-duplicate"
fixtures sharing almost all text/keys and "distinct" fixtures sharing
zero words/keys, so the test passes under any reasonable similarity
formula, not coupled to Ultron's eventual algorithm choice.

**Satisfiability mutation-check (same technique as
[vocabulary-contract-notes](vocabulary-contract-notes.md)):** wrote a
throwaway `lib/memory/model.py` (matching PIEZAS §5.3's `Note` fields
exactly) + `lib/memory/similar.py` (naive jaccard-on-tokens
implementation, zone-pair filtered) in one bash block, ran the suite (4
passed), then deleted both files + `__pycache__` in the same session
before reporting -- confirmed reversion to RED (`ls lib/memory/` back to
`emojis.py utf8.py vocabulary.py`, 4 ERRORs on `test_similar.py`).

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory/test_similar.py -v` -> 4
errors, all `FileNotFoundError` on `lib/memory/similar.py`, one per row.
Full-suite sanity check (`unmassk-toolkit/tests/memory`, not asked but
run to confirm no bleed into parallel colleagues' files): 11
passed/1 failed(pre-existing vocabulary.py drift, not mine)/12 errors
(similar x4 mine, config x3 + zones x5 belong to the parallel
colleagues' RED contracts, confirmed by file ownership via `git status
--porcelain` showing only `test_similar.py` as new from this task).

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)
