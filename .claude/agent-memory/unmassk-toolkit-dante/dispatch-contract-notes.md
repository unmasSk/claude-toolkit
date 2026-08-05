---
name: dispatch-contract-notes
description: unmassk-memory (v2) Capa 4 -- lib/memory/dispatch.py (RED, test-first) contract from PIEZAS.md Sec.9.8, 3 rows; office-identifier gap flagged as an open question, not invented silently
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_dispatch.py` (3 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.9.8, same acceptance-granularity
override as [query-contract-notes](query-contract-notes.md)/
[notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md).
Surface: `zone_of(prompt, zones) -> tuple[str,str] | None` and
`content_for(agent, zone) -> str`.

**Open question raised in the task report, not resolved silently:**
`content_for(agent: str, ...)` never fixes what literal strings `agent`
receives -- neither Sec.9.8 nor `hooks/inject.py` (the real caller,
still unbuilt) declare it. Used the seven **Oficio-column strings**
verbatim from `ARQUITECTURA.md` Sec.3 (`Implementador`, `Tests`,
`Diagnóstico`, `Revisores`, `Adversario`, `Juez`, `Explorador`) because
Sec.9.8 itself cites that exact table as content_for's derivation
source -- the most direct citation available, not a guess pulled from
nowhere. Still flagged explicitly as a **guessable implementation
detail**, same class as `test_query.py`'s assumed `git log` subcommand:
if Ultron's real `hooks/inject.py` sends agent code-names instead
(`"Ultron"`, `"Dante"`...), it's a one-line fix to the test file, not a
redesign. `"Revisores"` is one shared string for Argus+Cerberus --
both `ARQUITECTURA.md` Sec.3 and `spec-sistema-memoria-v2.md` Sec.8.2
give them identical content under one row, never two.

**Row 1 design (`test_each_office_receives_exactly_its_own_content`):**
seeds ONE real R, D, I, M(keys=("security",)), and a plain decoy M --
all via real `notes.write()` against a real `tmp_repo`, no fabrication
-- each with a unique headline marker (`MARK_R_ONLY`, `MARK_D_ONLY`,
etc., chosen with zero substring overlap). Then calls
`dispatch.content_for(office, zone)` once per office and asserts, by
marker, presence of what's theirs AND absence of what isn't -- a data
table (`_DISPATCH_MATRIX`) derived directly from `ARQUITECTURA.md`
Sec.3 / spec Sec.8.2 (the two tables agree). A single R/D/I keeps
"vigente"/"la R de la zona" unambiguous without touching
supersession-between-multiple-D logic (out of acceptance-granularity
scope here).

**Row 2 design:** the literal no-zone block is copied verbatim from
`ARQUITECTURA.md` Sec.7 (repeated in PIEZAS.md Sec.9.8) -- compared via
`.strip()` to tolerate an unspecified trailing newline, not because the
wording is uncertain. Looped over all seven office strings (the aviso
must not depend on who receives it) with NO `tmp_repo` -- the contract
itself says this path never reads git, so requiring a repo here would
be over-fabricating a dependency the row doesn't need.

**Row 3 design:** `zone_of(prompt, zones)` -- prompt carries an explicit
`Zone: alpha1/alpha2` line AND, separately in the body, the literal
words `beta1`/`beta2` (a second, real zone pair also given as valid in
`zones`) so that a word-matching fallback alone would resolve to the
WRONG pair if it were allowed to win. Asserts the explicit line's pair
wins. Deliberately does NOT add a fourth test proving the fallback
works in isolation -- not what row 3 asks, and the "una fila = un
test, ni uno mas" rule from `PIEZAS.md` applies here same as every
other Capa 1+ contract in this branch.

Verification command used:
`python3 -m pytest unmassk-toolkit/tests/memory/test_dispatch.py -q` ->
3 errors, all `FileNotFoundError: lib/memory/dispatch.py` -- RED for
the right reason, one per row. `--collect-only` -> 3 tests collected,
zero collection errors. Only file touched: `test_dispatch.py` (new) --
confirmed via `git status --porcelain` (the rest of the wide diff in
this repo belongs to concurrent parallel agents' work, not this task).

Reference: [query-contract-notes](query-contract-notes.md),
[notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md),
[memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)

## Update 2026-08-02: `DeclaredZoneNotFound` hardening -- closed the test gap the module's own docstring flagged as open

After dispatch.py went GREEN, a reviewer round found a real bug: a
declared-but-typo'd `Zone: backedn/frontend` line was silently falling
back to word-matching and resolving to a completely different zone pair
(`('frontend', 'infra')`), contradicting "an explicit line always wins".
Fixed in production by introducing `DeclaredZoneNotFound` (a frozen
dataclass carrying the two RAW, unresolved names) as a third return shape
for `zone_of()`, checked in `content_for()` *before* the `zone is None`
branch. The module's own docstring said explicitly: "ningun test de
test_dispatch.py cubre este camino, es un hueco de test declarado, no
escondido" -- closed with 2 tests added test-first-adjacent (code already
fixed, tests written after, matching the DEUDA.md point-11 "exported, no
test" pattern already seen on `health.plans_unreflected`):

1. `test_declared_zone_that_does_not_resolve_never_falls_back_to_word_matching`
   -- reused the exact repro from the module's own "Revision 2026-08-02"
   docstring paragraph (real zones `backend`/`frontend`/`infra`, declared
   line `Zone: backedn/frontend` with a typo, body ALSO containing the
   real words `frontend`/`infra` so a silent fallback would have a
   plausible wrong answer to land on -- not a straw man). Asserts
   `isinstance(result, dispatch.DeclaredZoneNotFound)` and that
   `.zone1`/`.zone2` are the RAW typo'd strings, never resolved.
2. `test_content_for_declared_zone_not_found_names_the_missing_zone_never_empty`
   -- looped over all 7 offices (same shape as the existing
   `test_missing_zone_yields_the_loud_block_never_an_empty_string`),
   asserting the block is non-empty, is NOT byte-equal to the generic
   `_NO_ZONE_BLOCK` (the two silences must stay visually distinguishable
   -- "declared and wrong" vs "never declared"), and names both raw zone
   strings verbatim.

Both pass GREEN against the already-fixed `dispatch.py` -- no production
touched, confirmed via `git status --porcelain` showing only
`test_dispatch.py` under my edits.
