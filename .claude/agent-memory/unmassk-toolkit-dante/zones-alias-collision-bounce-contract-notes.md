---
name: zones-alias-collision-bounce-contract-notes
description: test_zones_script.py 2026-08-04 follow-up -- alias-collision bounce RED contract (the hole flagged-but-left-open in the prior same-day session), naming-the-alias-owner requirement
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_zones_script.py`, same file as
[zones-script-english-rename-and-duplicate-bounce-notes](zones-script-english-rename-and-duplicate-bounce-notes.md),
same day, follow-up task. That prior session closed "registering an
existing CANONICAL zone name bounces" (`bin/memory/zones.py::_cmd_add`
now checks `args.name in existing` and rebota, 10/10 green, confirmed by
running the file) but explicitly left the ALIAS-collision case out,
flagged in both the module docstring and the report rather than guessed
at. This task closes that flagged hole under an orchestrator decision
(2026-08-04, extending the owner's, revocable) instead of Ultron
guessing at it.

**The bug, confirmed live before writing the test (not assumed):**
`_cmd_add` only checks canonical names. Seed `billing` with alias
`facturacion`, then `zones.py add facturacion --description "..."` ->
`rc=0`, `"✅ facturacion dada de alta — zones.json tiene 2 zonas"` -- a
SECOND zone is created under the name that used to resolve to `billing`.
`zones.resolve("facturacion", ...)` checks canonical names before aliases
(`lib/memory/zones.py::resolve`, read live, not touched this session), so
after the bug, `resolve("facturacion")` returns the NEW zone, not
`billing` -- silent alias hijack, same failure family as the
canonical-name bounce that was just closed.

**New requirement beyond the canonical-name bounce: the rejection must
name the alias's OWNER.** The orchestrator's instruction was explicit
about why this differs from the canonical case: with a canonical-name
collision the user typed a name they can already see in `zones.py list`;
with an alias collision `facturacion` never appears in any listing (only
`billing`'s alias field does), so a bare "ya existe" gives no path
forward. Contract requires BOTH the colliding token (`facturacion`) AND
the owning canonical name (`billing`) to appear in combined stdout+stderr
-- verified as two independent `assert ... in combined_second` checks, not
one combined string match, so a report that names one but not the other
still fails clearly.

**No TEXTOS.md template for this either** -- same grep as the prior
session (`ya existe`/`duplicad`/`alias` combined with zone terms) found
nothing; confirmed again this session with a direct `grep -n -i "alias"
docs/memoria-v2/TEXTOS.md` -- only unrelated Google-workspace-alias
glossary entries, nothing about zone-alias collision. Contract enforces
behavior + the two non-fabricated positive data points, never a
hand-typed rejection sentence.

**Point 3 of the task (own-zone-alias overlap) -- checked, confirmed NOT
a duplicate.** The existing `TestRegisteringAnExistingZoneNameBounces`
test also seeds `billing` with alias `facturacion` (coincidentally, for
an unrelated reason -- it just needed *some* alias present), but it only
re-submits `billing` itself (canonical-name path) a second time. It never
attempts to register `facturacion` as a new zone name. So the new test's
scenario -- colliding against the alias of the one zone already seeded in
that fixture -- was genuinely uncovered, not a re-test of the same
behavior through a different door. Each test has its own isolated
`tmp_repo`, so there's no cross-test seeding to worry about either.

**Extra invariant beyond rc/bytes: `resolve()` after the attempt.** Round
trip checked two ways, both against real production code
(`unmassk-standards §34`): (1) `zones_path.read_bytes()` before/after
byte-identical, same technique as the canonical-name bounce test; (2)
`zones_lib.resolve("facturacion", after_loaded) == "billing"` -- this is
the *actual symptom* the task description centers on (resolve() silently
re-pointing), not just "file didn't change", so it's asserted directly
rather than left implied by the byte-compare.

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_zones_script.py -v`
-> 10 passed (unchanged from the prior session) + 1 failed, real reason
(`assert 0 != 0`, stdout shows the second zone WAS created: `"✅
facturacion dada de alta — zones.json tiene 2 zonas"`), never a generic
collection error. `--collect-only` on the whole `tests/memory` dir ->
293 collected (was 292 before this session's one new test), only this
file's shape changed.

Reference: [zones-script-english-rename-and-duplicate-bounce-notes](zones-script-english-rename-and-duplicate-bounce-notes.md), [zones-contract-notes](zones-contract-notes.md)
