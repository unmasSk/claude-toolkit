---
name: note-script-alias-not-resolved-regression-notes
description: test_note_script.py 2026-08-04 -- Moriarty T1 regression, alias used at write time is never resolved to canonical, note vanishes from its own zone index
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_note_script.py`, already GREEN
(9 tests, both `note.py` and `search.py` real and in production -- despite
the task framing this as "test-first, RED before Ultron", both scripts
already existed with a live bug; this session's contract is a **regression**
test for a Moriarty-confirmed failure, not a pre-implementation contract).
See [zones-alias-collision-bounce-contract-notes](zones-alias-collision-bounce-contract-notes.md)
for the sibling bug in `zones.py add` (registering a NEW zone under an
existing alias) -- this session's bug is different: writing a NOTE using an
already-valid alias.

**The bug (Moriarty T1, 2026-08-04, reproduced live by the orchestrator
before assigning this task):** `bin/memory/note.py::_build_candidate()`
(lines ~118-119) puts `args.zones[0]`/`[1]` straight into
`Note.zone1`/`zone2`, never calling `zones.resolve()`. Meanwhile
`lib/memory/validator_zones.py::_validate_zone_name()` correctly accepts an
alias as a valid zone name (`zones_.resolve(name, zones) is not None`).
Result: `note.py M --zones prod checkout ...` (where `prod` is `product`'s
alias) reports `rc=0`, `"✅ M-001 guardada"` -- but the index line gets
written with `zone1="prod"` (the raw alias), not the canonical name. The
note becomes permanently invisible to `search.py` by EITHER the alias or
the canonical name -- confirmed live: `search.py product` and
`search.py prod` both return the real "CERO NOTAS" block
(`report_render._CERO_NOTAS = "⚠  C E R O   N O T A S"`, letter-spaced --
a naive `assert "CERO" in out` does NOT catch this, false-green trap flagged
explicitly by the orchestrator). Same failure family as the write-loss bug
in capa 1 (silent memory loss, all green, no error) -- this project's
declared single threat model.

**Fixture gap closed locally, not in conftest.py.** `seed_zones_json()`
(conftest.py) writes `"aliases": []` always -- can't seed a zone WITH an
alias. Added `_seed_zones_with_alias(repo, {canonical: [aliases]})` as a
private helper INSIDE `test_note_script.py` (task explicitly scoped writes
to this one file; conftest.py is shared, off limits without an explicit
one-off grant like the one in
[zones-contract-notes](zones-contract-notes.md)). Same pattern as
`seed_zones_json`: JSON literal matching `zones.py::_serialize`'s real
on-disk shape, never invoking `zones.add()` (its lock mechanics aren't
under test here).

**Detection technique, never a hand-typed expected string:** read the note
back through the REAL index reader (`indexes.read(name, pm)`, same
`_find_by_zone_and_headline` helper the file already had) and assert
`line.zone1 == "product"` (the canonical name) -- not a string search over
raw file content. Round-trip invariant added beyond the index check: after
the write, `zones.resolve("prod", zones.load(pm/"zones.json")) == "product"`
-- proves the write didn't also corrupt `zones.json` itself, isolating the
bug to the note-write path only. Then the actual user-facing symptom
(search never finds it) verified via TWO independent `search.py` subprocess
calls (by canonical name, by alias) both asserting the real note id
(`extract_note_id`, conftest.py) appears in stdout.

**Two tests, mirrored for the two zone slots** (`Note.zone1`/`zone2` are
separate fields, `_build_candidate` could plausibly have an asymmetric bug):
alias in slot 1 (`product`/`prod`, matches Moriarty's exact repro) and alias
in slot 2 (`billing`/`facturacion`, mirrors the first). A third test,
`TestControlWithCanonicalNamesStillWorksAsBaseline`, seeds and searches with
plain canonical names only (`seed_zones_json`, no alias) -- confirms the
write+search path works today WITHOUT the alias variable, so if the two
alias tests ever failed for a different reason (e.g. `search.py` itself
broken), the control would catch that distinction instead of misattributing
everything to alias resolution. No fourth test added despite an available
temptation ("what if the SAME name is alias in one call and canonical in
another") -- explicit owner instruction this session: "no añadas de más...
no queden tests de cosas que el código nunca hará."

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_note_script.py -v`
-> 8 previously-green tests unchanged + 1 new green control + 2 new RED,
both failing at `assert name == "MEMOS.md" and line is not None` with
`assert (None == 'MEMOS.md')` -- the note truly isn't found under the
canonical name, not a collection/import error. Full `tests/memory` suite:
308 passed, 1 pre-existing unrelated failure in `test_boundary.py` (a
different in-progress agent's new file, orphaned-symbol audit, untouched by
this session) -- confirmed NOT caused by this change (same failure, same
count, before touching `test_note_script.py`). `--collect-only`: 311 total
(was 309 before this session's 2 new tests... actually +2 net after 1 new
control test also counted -- 3 new test functions added this session).

Report to orchestrator included an explicit open question (per task ask):
where the real fix belongs -- `note.py::_build_candidate()` should resolve
`args.zones[0]`/`[1]` through `zones.resolve()` before building `Note`
(script-side), OR `validator.py`/`validator_zones.py` should have
`validate_zones` RETURN the canonical pair somehow instead of just
approving/rejecting (would change `validate_zones`'s signature/contract,
bigger blast radius) -- flagged as Ultron/owner's call, not decided here.

Reference: [zones-alias-collision-bounce-contract-notes](zones-alias-collision-bounce-contract-notes.md), [zones-script-english-rename-and-duplicate-bounce-notes](zones-script-english-rename-and-duplicate-bounce-notes.md), [capa5-scripts-red-contract-notes](capa5-scripts-red-contract-notes.md)
