---
name: deuda24-search-by-id-contract-notes
description: DEUDA.md #24 RED contract (search.py --id shows the zone, not the note) -- git-grep-anchored independent read helper, D-type Origin vocabulary gap found, M/R stops requirement gotcha
metadata:
  type: project
---

Task: RED contract (test-first, before Ultron) for `bin/memory/search.py --id`,
fixing DEUDA.md #24 -- `_render_by_id()` returned
`report_render.render_zone(report.build_zone(note.zone1, True))` (the whole
zone, zone2 ignored, archived forced+unmarked). The fixing molde had just
been dictated by the owner in `TEXTOS.md Sec.2.4` (5 rules) -- before that
session there was no literal text to derive the piece from, which is why the
bug had gone unfixed since day one. Added 8 tests to
`tests/memory/test_search_script.py` (script-level, black-box) -- one class
per molde rule, matching the rest of that file's conventions. All 8 fail
today for the real cause (current output is the zone dump); suite went from
273 green/3 red to 273 green/11 red (8 new + the 3 pre-existing, unchanged
owner-blocked reds in test_context.py/test_gitcmd.py/test_rules.py).

**Independent-read helper for a by-id round trip: git log --grep anchored +
format.parse_message, never query.py.** `search.py --id` internally uses
`query.by_id`, so comparing its output against `query.by_id` again would be
"looking at itself" (forbidden by this project's own rule: a test only
counts if it compares two things written separately). Instead: locate the
commit with `git log --all -E --grep="^\[{note_id}\]" --format=%H` (anchored
to the START of the message so a CHILD commit that only *cites* the id in
`Origin: D-030` never matches), then read `%B` and `%aI` on that sha
separately, and parse the body with `format.parse_message` (the real
production parser, never a regex written for the test). This is the same
pattern `query.py` uses internally (`dataclasses.replace` to swap in the real
author date since `parse_message` stamps a `datetime.now()` placeholder) --
reused here as an *external*, independent verification path. Reusable
verbatim for any future by-id/round-trip contract.

**Real gap found, not invented around: `vocabulary.TYPES["D"].allowed_fields`
has no `"origin"` (only `"replaces"`), but TEXTOS.md's own racimo examples
(Sec.2.1 AND the new Sec.2.4 molde) show a `D` (`D-041`) hanging from another
`D` (`D-030`) via `Origin`.** Verified live: `note.py D ... --origin <id>`
rejects with "Estos campos no existen para el tipo D: origin". This means the
molde's own literal example cannot be constructed through the real write path
today. Did NOT invent a workaround inside production code (not my scope) --
substituted the cluster test's third child with `R` (also `nace de` the root
in the SAME molde example, `R-018`, and R's `allowed_fields` DOES include
`origin`), and documented the substitution + the gap explicitly in the test's
own docstring, reported it to the orchestrator instead of silently routing
around it. Next time a contract needs a D-child-by-Origin, check this gap is
still open before assuming it's buildable.

**Gotcha: `M` and `R` always require `--stops yes|no` answered (the "pain
question") via `note.py`/`seed_note_via_script` -- easy to forget when
seeding a throwaway M/R note for an unrelated assertion.** Missing it doesn't
error at the validator's normal rejection path -- it's checked before
`validate_note()` even runs, in `note.py::main` via
`validator.validate_pain_question`, and prints "⛔ falta una respuesta" with
`rc=1`. D/Q/X/I/B never need it. Caught 3 times in one session seeding
throwaway M notes for zone-line/footer/orphan-cluster assertions.

**No Spanish singular type-name constant exists in production yet
(`vocabulary.py` or anywhere) -- confirmed by grep across
`lib/memory`+`bin/memory`+`tests/memory`.** `vocabulary.TYPES[letter].description`
is the long descriptive line ("se eligió entre opciones"), not a noun.
Confirmed literal singulars, from real text (never invented): `D` ->
"decisión" (TEXTOS Sec.2.4 molde itself), `Q` -> "pregunta", `X` ->
"descarte", `I` -> "incidencia" (all three from TEXTOS Sec.6, point 1). `M`
-> "memo" (same word in Spanish and the spec's own §4 "Nombre" column). `R`
and `B` are NOT literally confirmed anywhere as singular nouns -- only
derived from the section-header plurals ("RESTRICCIONES" ->
"restricción"/"BLOQUEANTES" -> "bloqueante"), used in this contract's B-type
test but flagged in the final report as inferred, not sourced. Whoever
implements the header needs to add this mapping somewhere (likely
`vocabulary.py`) -- it's a new piece the contract exposed, not something to
assume already exists.

**Vacuous-pass caught again on a pure-absence assertion for behavior that
doesn't exist ANYWHERE yet.** `assert "LO QUE CUELGA DE ELLA" not in out` for
an orphan note passed against TODAY's buggy code too, because that title
string doesn't exist in ANY code path yet (not just "correctly absent for
this note" -- absent everywhere, always, pre-fix). Same class of bug as
[[capa5-read-scripts-and-facade-contract-notes]]'s `rc!=0`-only pitfall, one
level up: a negative/absence assertion needs a **sibling positive assertion
tied to the same test's real changed behavior** (here: the note's own
`{id} · memo · vigente` header, which DOES fail pre-fix) so the test's
overall red/green status tracks the real fix, not a string that simply
doesn't exist yet in either world. Always run a "does this assertion alone
distinguish before/after" check on any test whose core claim is an absence.

Related: [[memoria-v2-zonereport-shared-section-notes]] (report.py/
report_render.py seeding-via-real-transaction pattern, reused here via
`seed_note_via_script`); [[capa5-read-scripts-and-facade-contract-notes]]
(same vacuous-pass class, `search.py` contract's first pass).
