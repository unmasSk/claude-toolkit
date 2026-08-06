---
name: zones-list-doctor-absent-vs-empty-contract-notes
description: RED contract (2026-08-06) for two absent-vs-empty masking bugs -- bin/memory/zones.py::_cmd_list and bin/git-memory-doctor.py missing a zones.json check entirely
metadata:
  type: project
---

Two RED contracts written 2026-08-06, test-first mode, no production code touched (task explicitly forbade editing zones.py/health.py/git-memory-doctor.py).

**Fact 1 -- `bin/memory/zones.py::_cmd_list`** (`tests/memory/test_zones_script.py`,
class `TestListDistinguishesAbsentFromEmptyZonesJson`): `zones_lib.load(path)`
collapses `FileNotFoundError` into `{}` (`lib/memory/zones.py::load`,
documented on purpose -- a missing file IS a valid "no zones yet" state).
`_cmd_list()` only ever sees `len(zones_map)`, so it prints the identical
`"zones.json tiene 0 zonas:"` whether the file never existed or exists as
literal `{}`. `lib/memory/health.py::memory_mounted()` (lines ~448-457)
already makes this exact distinction for its own report -- `"zones.json (no
existe)"` vs `"zones.json (existe, pero no tiene ninguna zona dada de
alta)"` -- and the RED test's one content assertion (`"no existe" in out`)
quotes that real production string verbatim, not a fabricated one (§34).
Confirmed RED: 2 of 3 tests fail (the third, "present-but-empty does not
claim absence", already passes today and serves as the anti-vacuity
control).

**Fact 2 -- `bin/git-memory-doctor.py` has zero zones.json awareness**
(`tests/test_doctor_derived_expectations.py`, classes
`TestDoctorNeverMentionsZonesToday` (anti-vacuity control, passes today) and
`TestDoctorChecksZonesJson`): `grep -in "zones" bin/git-memory-doctor.py`
returns 0 matches (the only "zone" substring in the file is `timezone` in a
stdlib import -- caught this false positive before committing to a "zone"
vs "zones" substring search, used "zones" everywhere in the test helper
`_zones_check()`). `check_project_memory_seed()` already distinguishes
three states for the eight index files; this RED contract asks for the
same three-state shape (absent / present-empty `{}` / present with one
real zone) applied to zones.json, wording-agnostic on the component
name/message text (Ultron's call). Confirmed RED: 5 of 6 tests fail.

Both files' PRE-EXISTING tests stayed green after the additions (45 passed,
1 skipped, only the 7 new tests red) -- verified with a combined run of
both files, not just the new classes in isolation.

See [[capa5-read-scripts-and-facade-contract-notes]] for the "wording-
agnostic substring, real production text over fabricated" pattern this
follows, and [[health-boot-rule-coherence-wiring-notes]] for prior
health.py-related RED contracts.
