---
name: note-exact-key-zone-duplicate-gate-contract-notes
description: test_note_exact_key_zone_duplicate_gate.py RED contract -- same-keys+same-zone exact-match gate missing from validate_replacement (Jaccard alone misses it, 0.227 < 0.5); empty-keys-never-matches guard; remove.py fence structurally can never carry keys; BREAK 2 (Moriarty) -- zone pair compared positionally, not as a set
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_note_exact_key_zone_duplicate_gate.py`
(7 tests: 2 RED, 5 GREEN controls/invariants) -- test-first contract pass,
acceptance granularity, for a NEW gate the orchestrator asked for: "mismas
claves + misma zona -> rechaza pidiendo `--replaces`", independent of the
existing Jaccard-based `similar.find_similar`.

**Mapping correction confirmed by reading, not assumed:**
`lib/memory/similar.py::_tokens`/`_jaccard` ALREADY folds headline +
description + why + keys into one Jaccard number, and `find_similar`
ALREADY hard-filters on `zone1`+`zone2` both. So the missing piece isn't
"add keys/zone to the comparison" -- it's a DISTINCT exact-match gate:
two live notes sharing the same key SET in the same zone pair, with
headlines/descriptions dissimilar enough that Jaccard stays under
`vocabulary.SIMILARITY_THRESHOLD` (0.5). Verified live before writing
any test (replicated `_tokens`/`_jaccard` inline against textnorm): the
core test's headline/description pair scores Jaccard = 0.227 -- well
under threshold, proving today's detector genuinely misses this case,
not that the test picked a lucky borderline value.

**Two RED / five GREEN, same mixed pattern as
[note-archived-similarity-bypass-contract-notes](note-archived-similarity-bypass-contract-notes.md):**
1. RED -- same 3 keys (same order), distinct low-Jaccard headlines, same
   zone pair -> today saves cleanly (`rc==0`, `M-002 guardada`); must
   bounce naming the old id and mentioning `--replaces`.
2. RED -- same keys, SHUFFLED order -- fixes "conjunto" (SET) semantics
   literally from the orchestrator's correction wording, catches a naive
   `tuple ==` implementation that a `frozenset ==` one wouldn't trip on.
3. GREEN control -- same zone, keys share zero words -> must stay clean
   (gate is about keys, not just zone).
4. GREEN control -- same keys, different `zone2` (same `zone1`) -> must
   stay clean (same "vary only zone2" technique as
   [similar-contract-notes](similar-contract-notes.md) row 3, catches a
   shallow zone1-only filter).
5. GREEN control -- old note closed via `gitmem remove` first -> new
   note with the same keys must still enter clean, reusing the archived
   bypass mechanism already fixed for the Jaccard gate.
6. GREEN control, explicitly labeled as a MANDATORY guard, not spec
   coverage padding -- two notes with `keys=()` (the common case: most
   notes never pass `--keys`) in the same zone must NEVER bounce on
   "same key set". An empty-set match would break the second note in
   any zone nobody keys, which is the majority case in this repo. Same
   principle `similar.py::_jaccard` already applies to an empty
   vocabulary (returns 0.0, never "identical").
7. GREEN control via the SECOND call site, `remove.py --restriction
   new` (`_build_fence_context()`/`_guard_restriction_new()`, same
   `validate_note()`/`validate_replacement()` machinery as `note.py`).
   **Structural finding, reported not fixed:** `_build_fence_candidate()`
   (`remove.py:100-112`) never sets `keys` on the fence `Note` -- there
   is no `--keys` flag on `remove.py::_parse_args()` at all (`grep -n
   keys bin/memory/remove.py` -> zero lines). So a true positive of this
   new gate is structurally impossible through the fence path today;
   the only fixable claim there is the same empty-keys-never-matches
   invariant, which this test locks down (two keyless fences, same
   zone, distinct texts, both must land).

**Verification command:** `python3 -m pytest
unmassk-toolkit/tests/memory/test_note_exact_key_zone_duplicate_gate.py
-v` -> 2 failed / 5 passed. Both failures show `rc_new == 0` with a real
`✅ M-002 guardada` stdout (RED for the right reason: gate absent, not
an import/collection error). `git status --porcelain` before/after
confirms only this one new test file touched.

**2026-08-25 addendum -- BREAK 2 (Moriarty), fila 8, new RED, same file:**
same file extended with `TestSameKeysZonesSwappedStillBounces` -- the
duplicate gate's zone-pair check is POSITIONAL, not a set. Confirmed by
reading (not assumed) both call sites in `similar.py`: `find_similar`
(~line 98) and `_find_exact_key_match` (~lines 133-135) both do `if
note.zone1 != candidate.zone1 or note.zone2 != candidate.zone2:
continue` -- swap `zone1`/`zone2` between two notes with the same key
set and both comparisons read "different" even though the pair is the
same. Reproduced live before writing the test, standalone script against
a disposable repo through `bin/gitmem` (never in-process): `note M
--zones gamma delta ...` then `note M --zones delta gamma ...`, same
keys `(ansible, terraform)`, low-Jaccard headlines (verified 0.1395 <
0.5 by replicating `_tokens`/`_jaccard` inline) -- both landed with
`rc==0`, two live ids. Owner decision: the zone pair is a SET for this
gate specifically -- same principle row 2 already fixed for keys,
applied to zones now. Does NOT touch how zones are stored/resolved
anywhere else in the system. Verification: `python3 -m pytest
unmassk-toolkit/tests/memory/test_note_exact_key_zone_duplicate_gate.py
-v` -> 1 failed (the new row, for the right reason: `rc_new==0` with a
real `✅ M-002 guardada`) / 7 passed (all prior rows/controls intact,
nothing broken). `git status --porcelain` before/after: only this one
test file touched.

Reference: [similar-contract-notes](similar-contract-notes.md), [validator-contract-notes](validator-contract-notes.md), [note-archived-similarity-bypass-contract-notes](note-archived-similarity-bypass-contract-notes.md)
