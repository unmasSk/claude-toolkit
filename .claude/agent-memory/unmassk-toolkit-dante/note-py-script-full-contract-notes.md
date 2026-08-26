---
name: note-py-script-full-contract-notes
description: bin/memory/note.py full campaign merged from 7 date-split files — zone-alias regression, --replaces archiving regression, --discard wiring, archived-similarity bypass, exact-key-zone duplicate gate, --promotes, --issue seven-types opening
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 2) from 7 separate files that all covered the SAME piece of
code — `bin/memory/note.py` (the note-creation CLI script, its duplicate-detection call graph, and its
archive-destination writers) — split only by which session touched it. Per this project's compaction rule
("varios ficheros sobre UN mismo trabajo... se funden en uno por tema"). Nothing was cut; each original
file's content is reproduced below verbatim under its own dated heading, in chronological order. Original
filenames (now retired, kept only as history in this note, not on disk):
`note-script-alias-not-resolved-regression-notes.md`, `note-script-replaces-not-archiving-regression-notes.md`,
`note-script-discard-alternatives-flag-contract-notes.md`, `note-archived-similarity-bypass-contract-notes.md`,
`note-exact-key-zone-duplicate-gate-contract-notes.md`, `promotes-flag-third-archive-destination-contract-notes.md`,
`note-issue-field-seven-types-contract-notes.md`.

## Round 1 (2026-08-04) — Moriarty T1: zone alias written unresolved, note vanishes from its own index

Context: `unmassk-toolkit/tests/memory/test_note_script.py`, already GREEN
(9 tests, both `note.py` and `search.py` real and in production -- despite
the task framing this as "test-first, RED before Ultron", both scripts
already existed with a live bug; this session's contract is a **regression**
test for a Moriarty-confirmed failure, not a pre-implementation contract).
See [zones-py-full-contract-notes](zones-py-full-contract-notes.md)
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
[zones-py-full-contract-notes](zones-py-full-contract-notes.md)). Same pattern as
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

Reference: [zones-py-full-contract-notes](zones-py-full-contract-notes.md), [zones-py-full-contract-notes](zones-py-full-contract-notes.md), [capa5-scripts-red-contract-notes](capa5-scripts-red-contract-notes.md)

## Round 2 (2026-08-04, same session) — --replaces never calls notes.replace(), old note stays live forever

Context: same file/session as
Round 1 above,
second bug in the same batch, landed as a follow-up message mid-task (both
fixes go to Ultron in one pass). `note.py` and `notes.py::replace()` both
already exist and are in production; this is a regression test for a
confirmed bug, not a pre-implementation contract.

**The bug:** `bin/memory/note.py::main()` (line 168) unconditionally calls
`notes.write(candidate, ctx)`, never `notes.replace(new, old_id, ctx)` --
even when `--replaces <ID>` is a real note id. `notes.write()` writes
`candidate.replaces` into the commit body (`format.build_message` folds
`Replaces:` in whenever `note.replaces is not None`) but has ZERO knowledge
of archiving -- it only ever inserts a new index line, never removes one.
Result: `--replaces D-001` on a new D reports success with a real new id
(`D-002`), and `DECISIONS.md` keeps BOTH `D-001` and `D-002` live forever,
`ARCHIVED.md` stays empty -- two contradicting live decisions, exactly what
`notes.py::replace()`'s own docstring names as the failure it exists to
prevent ("que la sustitucion quede a medias: dos notas vigentes diciendo lo
contrario"). Same family as the alias bug in the same session: success
reported, memory silently corrupted (contradictory, not lost this time).

**`--replaces none` is a real sentinel, not `None`.** `note.py`'s argparse
(`--replaces`, `default=None`) does NOT special-case the literal string
`"none"` -- when the user passes `--replaces none`, `Note.replaces` becomes
the STRING `"none"`, which is `is not None` in Python. Two places already
treat this specially, confirmed by reading (not assumed): `validator.py::
validate_replacement` checks `note.replaces is not None` to skip the
"overlapping note" rejection (so `"none"` bypasses it same as a real id),
and `validator_pointers.py:91` explicitly excludes `note.replaces != "none"`
from the dangling-pointer check. So `"none"` already flows correctly through
today's `write()`-only path (nothing gets archived, both notes stay live,
by construction of `write()` never touching removal/archival) -- this is
exactly why the task's required control test needs to be a **positive
green** proving the fix doesn't accidentally start treating `"none"` as a
real id and archiving something.

**Two test classes, mirroring the two behaviors:**
1. `TestReplacesArchivesTheOldNoteInTheSameCommit` -- seed a D (`D-001`, no
   `--replaces`), then a second D with `--replaces D-001` (RED today).
   Asserts, all via real readers, never hand-typed text: (a) exactly ONE new
   git commit for the second call (`_git_commit_count` before/after, already
   in the file) -- proves the "single commit" contract of `replace()`, not
   just eventual consistency across two commits; (b) `indexes.read
   ("DECISIONS.md", pm)` -- `old_id` NOT in the live id set, `new_id` IS;
   (c) `indexes.read_archive(pm)` -- `old_id` present with
   `.destination == "replaced"` and `.destination_detail == new_id`,
   compared against the REAL `ArchiveLine` fields the real parser
   (`format.parse_archive_line`, via `indexes.read_archive`) returns, never
   a hand-typed "replaced by D-002" string. `TEXTOS.md` Sec.4's three
   literal destinations (`replaced by <ID>` / `closed: <motivo>` /
   `promoted to <ID>`) map 1:1 to `ArchiveLine.destination` values
   (`"replaced"`/`"closed"`/`"promoted"`) -- confirmed by reading
   `indexes.py::archive()`, which builds the line via
   `format.build_archive_line(placeholder, line.destination,
   line.destination_detail)`.
2. `TestReplacesNoneSentinelStillLetsBothNotesCoexist` -- seed two D's, the
   second with `--replaces none` explicitly. Confirmed GREEN today (no fix
   needed for this path) -- both ids stay in `indexes.read("DECISIONS.md")`,
   `indexes.read_archive(pm)` returns empty. This is the anti-regression
   guard: Ultron's fix (branch on `args.replaces` being a real id vs.
   `None`/`"none"` to decide `write()` vs. `replace()`) must not flip this
   green to red.

**Not touched, per explicit orchestrator instruction:**
`discard_alternatives` -- PIEZAS.md Sec.10 documents `note.py` calling it
too (found by the OTHER agent's boundary test,
`test_boundary.py::test_every_public_symbol_has_a_real_importer`), but it's
a different flow and explicitly out of scope for this task ("no quiero
mezclarlo con esto. Solo --replaces").

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_note_script.py -v`
-> 9 passed (7 pre-existing + 1 new `--replaces none` control), 3 failed (2
pre-existing alias-RED, unchanged, + 1 new `--replaces` RED). The new RED's
real failure: `AssertionError: la vieja (D-001) tiene que salir del indice
VIGENTE... assert 'D-001' not in {'D-001', 'D-002'}` -- both truly present,
not a collection/import error. `tests/memory --collect-only`: 313 total (was
311 after the alias session's 3 tests, +2 more this round).

Reference: Round 1 above, [capa5-scripts-red-contract-notes](capa5-scripts-red-contract-notes.md)

## Round 3 (2026-08-04) — --discard flag wiring for notes.discard_alternatives()

Task (2026-08-04): `lib/memory/notes.py::discard_alternatives(decision, alternatives, ctx)`
was written and unit-tested but never called from `bin/memory/note.py` — same
orphan-wiring pattern `notes.replace()` had earlier in this branch
(Round 2 above). Owner decision: wire it.

**Flag form decided (Dante's design call, delegated explicitly by the owner):**
`--discard <headline> <why>`, repeatable (`argparse action="append", nargs=2`), same
tier as `--origin`/`--keys`/`--replaces`. Example:

```
note.py D --zones product auth "login with JWT + Google OAuth" \
    --why "sessions do not scale multi-tenant; Google avoids owning passwords" \
    --description "Brainstorm on login options..." \
    --discard "server-side sessions" "sticky routing complicates horizontal scaling" \
    --discard "own password login" "maintaining passwords costs us one incident a year"
```

**Critical gotcha, verified against `vocabulary.py` before writing tests:** the second
value of each `--discard` pair MUST map to `Note.description`, never `Note.why`.
`TYPES["X"].required_fields == frozenset({"description"})` — `why` is optional for X.
If the CLI put the reason into `why` instead, every alternative would be born missing
its one required field and `validator.validate_fields` would reject it every time —
the flag could never save anything. This only surfaces by reading `vocabulary.py`
directly; nothing in `TEXTOS.md` or `PIEZAS.md` states it, and the owner's own boot-output
example (`🚫 X-003 ... └─ mantener contraseñas nos cuesta un incidente al año`) reads like
a "why" semantically but has to land in `description` mechanically.

**Origin is NOT a CLI concern:** `discard_alternatives()` prepends the decision's real id
to each alternative's `origin` internally (`notes.py:292-293`, `dataclasses.replace(alternative,
origin=(decision_result.note_id,) + alternative.origin)`). `note.py` must never pass the
decision id itself via any origin flag for the alternatives — that would duplicate the pointer.
`--discard` intentionally has no third value for origin.

**No literal output molde exists.** Grepped `TEXTOS.md` for `note.py`/`discard` — zero hits.
Tests assert behavior only (exit code, real commit count, real index lines, `Note.origin`/
`Note.description` read back via `query.by_id`, and `clusters.group()` producing the correct
parent/children structure) — never invented screen text.

**Test technique — real producer↔consumer round trip (unmassk-standards §34):** after running
`note.py` as a subprocess, `monkeypatch.chdir(tmp_repo)` then call `query.by_zone()` +
`clusters.group()` **directly in-process** (not via another script) to verify the `Origin`
trailer round-tripped through a real git commit and that clustering (which only groups by
pointers, never similarity) links the alternatives to the decision for real. Same
`monkeypatch.chdir` pattern as `test_query.py` (see [[query-contract-notes]]).

File: `unmassk-toolkit/tests/memory/test_note_script.py` — added 2 tests (1 RED behavioral
contract, 1 GREEN control proving `--discard`'s absence doesn't change plain-decision
behavior). All 12 pre-existing tests stayed green. Unrelated to this task:
`test_boundary.py::test_every_public_symbol_has_a_real_importer` was already RED before this
session's edits (pre-existing orphan-symbol finding, not touched, not caused by this change).

## Round 4 (2026-08-05) — query.by_zone() includes archived notes, a closed note wrongly blocks a new similar one

Context: `unmassk-toolkit/tests/memory/test_note_archived_similarity_bypass.py`
(4 tests, 3 RED / 1 GREEN control by design) -- one test per point of the
task's own 4-point contract, literal, same test-first acceptance-granularity
override as every other contract file in this project. Only file touched
this session (`git status --porcelain` confirmed before/after -- everything
else untracked/modified in the tree belongs to parallel teammates' work,
none touched).

**The bug, confirmed by reading, not assumed:** `lib/memory/query.py::
by_zone()` (line 236-245) returns everything `_all_notes()` parses out of
git history -- live AND archived (closed/replaced/promoted) notes alike,
with zero filtering against the live index or `ARCHIVED.md`.
`bin/memory/note.py::_build_context()` (line 133) passes that straight
through as `Context.existing_in_zone`, and `validator.py::
validate_replacement()` (line 371-426) uses it whole to decide "esto pisa
a algo que ya esta escrito" -- a note closed months ago still counts as a
live collision. Worse for type `I`: `vocabulary.TYPES["I"].allowed_fields
== frozenset({"description", "why", "keys"})` (verified reading
`vocabulary.py`) -- `replaces` isn't even a legal field for an incidencia,
so the rejection's own "la sustituye  --replaces <id>" exit is an exit the
system would itself reject if taken literally.

**Executed via `bin/gitmem` (the facade), never `bin/memory/*.py`
directly** -- explicit task instruction ("ejecutando bin/gitmem"). Used
`run_gitmem_script` from `conftest.py` (already existed, already used by
`test_gitmem_facade.py`) instead of `run_memory_script`. `gitmem note`/
`gitmem remove` dispatch by path to `bin/memory/note.py`/`remove.py`
without adding logic of their own (`gitmem`'s own docstring, verified by
`TestAddsNoLogicOfItsOwn` in that sibling file) -- exercising the facade
IS exercising the real user path, not a shortcut.

**Similarity guaranteed without depending on `similar.py`'s exact
formula:** every "old"/"new" pair in this file shares LITERALLY IDENTICAL
headline+description -- Jaccard = 1.0, far above
`vocabulary.SIMILARITY_THRESHOLD` (0.5). No test here counts words by
hand or assumes a borderline case survives a future threshold tweak.

**Four tests, mapped 1:1 to the task's own four contract points:**
1. `TestClosedNoteDoesNotBlockASimilarNewNote` -- write M, close it via
   `gitmem remove <id> "<reason>"` (no `--restriction` needed -- that flag
   only gates `I`-type closes, `remove.py::main()` branch checks
   `args.id.startswith("I-")`), write a second identical M in the same
   zone pair. **RED today**: `rc_new == 0` fails, real rejection text
   shown citing the closed note as a live candidate.
2. `TestLiveNoteStillBlocksASimilarNewNote` -- same pair, first note
   left OPEN. **Control, GREEN today** (already correct behavior) --
   confirms the fix in point 1 has something real to preserve, not just
   an assertion that happens to pass by accident.
3. `TestIncidentClosedThenReopenedEndToEnd` -- the task's literal I-014
   story: I opened, closed via `gitmem remove <id> "<reason>" --restriction
   no` (I-type DOES need the restriction flag --
   `validator.validate_incident_close_question` fires otherwise), a
   second similar I months later. **RED today**, same failure shape as
   point 1, plus asserts the archived line's `destination == "closed"`
   and `destination_detail` equals the real close reason (via
   `indexes.read_archive`, never hand-typed), and that the live index
   (`INCIDENTS.md`) holds ONLY the new id.
4. `TestArchivedNoteIsIgnoredButALiveDuplicateStillBlocks` -- the
   overcorrection guard: seed old-A (closed) AND live-B (same text,
   written with `--replaces none` so its own alta doesn't collide with
   still-visible-today A), then attempt a third identical note. Asserts
   the rejection names B (live) and does **not** name A (archived).
   **RED today** for the precise reason a naive "just stop blocking
   entirely" fix would still pass: today's rejection names BOTH ids,
   proving the current bug isn't "some blocking" but "blocking against
   the wrong set."

**`--replaces none` sentinel needed for note B in test 4, same mechanism
already documented in
Round 2 above:**
`validate_replacement` returns `None` immediately whenever
`note.replaces is not None`, regardless of value -- without this, B's own
creation would bounce against still-archived A under today's bug, and the
test would never reach the actual scenario it exists to check.

Verification: `python3 -m pytest
unmassk-toolkit/tests/memory/test_note_archived_similarity_bypass.py -v`
-> 3 failed / 1 passed, all three failures show the real rejection text
(candidate ids, real `⛔` prefix) as the cause, not a collection/import
error -- RED for the right reason. `--collect-only`: 4 tests, matches the
4-point contract exactly, zero extra coverage added.

Reference: Round 2 above, [query-contract-notes](query-contract-notes.md), [validator-contract-notes](validator-contract-notes.md)

## Round 5 (2026-08-05, +2026-08-25 addendum) — same-keys+same-zone exact-match gate, zone-pair-as-set

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
Round 4 above:**
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

Reference: [similar-contract-notes](similar-contract-notes.md), [validator-contract-notes](validator-contract-notes.md), Round 4 above

## Round 6 (2026-08-05) — --promotes: the third archive destination had a reader but no writer

Context: `TEXTOS.md` Sec.4 fixes THREE literal `ARCHIVED.md` destinations
(`replaced by <ID>` / `closed: <motivo>` / `promoted to <ID>`). The reader
(`indexes.read_archive` -> `format.parse_archive_line`) already handles all
three in production; the writer only covers two -- `notes.py::replace()`
(line 360, `destination="replaced"`) and `::close()` (line 472,
`destination="closed"`). Nothing ever writes `destination="promoted"`. This
is `spec-sistema-memoria-v2.md` Sec.4's "a `Q` dies ascending" rule with no
implementation. Orchestrator-decided command form, 2026-08-05, symmetric to
`--replaces`: `gitmem note M --zones z1 z2 "..." --promotes Q-007` (or
type `X` for the "falls to discarded" branch).

**Task explicitly said "ejecutando `bin/gitmem`"**, not `note.py` direct --
different from every prior `note.py` contract in this branch
(Round 2 above,
Round 3 above), which all used
`run_memory_script("note.py", ...)`. `bin/gitmem` is real production code
(not RED itself -- `test_gitmem_facade.py`'s "NO EXISTE TODAVIA" docstring
is now stale, the file is fully implemented and green) that dispatches
`gitmem note <rest>` to `note.py <rest>` via bare `subprocess.run`, no logic
of its own. Used `run_gitmem_script()` (`conftest.py:304`, already existed,
unused by any note.py contract until now) instead of `run_memory_script()`.

**Self-inflicted bug caught by actually running the suite, not assumed
red-for-the-right-reason:** first draft of `_promote_args()` returned
`[note_type, "--zones", ...]` without the `"note"` subcommand prefix that
`run_gitmem_script()` requires as `argv[0]` (`bin/gitmem::main()` reads
`argv[0]` to pick the subcommand before dispatching) -- three of four tests
failed with `"gitmem: subcomando desconocido: 'M'"` instead of the intended
`argparse: unrecognized arguments: --promotes`. Fixed by prepending `"note"`
inside the helper. Second bug: the nonexistent-question test read
`indexes.read("MEMOS.md", pm)` as a "before" baseline in a `tmp_repo` where
NO note had ever been written yet -- `indexes.read()` fails loud
(`FileNotFoundError`) on an index file that was never seeded, since
`seed()` only runs inside `write()`/`replace()`/`close()`. Fixed by calling
`indexes.seed(pm)` directly first (the same idempotent production function
`write()` calls internally) to establish the "zero notes" baseline before
the rejected attempt -- not a reimplementation, just priming state the way
a real repo would already have it after any first write.

**Test 3/4 (wrong-type pointer, dangling pointer) never fabricate rejection
text** -- no molde exists in `TEXTOS.md` for a flag that isn't built yet.
Used a structural marker instead: `rejection.py::_render()` always emits
`⛔ {title}` and, when `relaunch` is non-empty, a `Relanza:` section --
common to every real rejection built via `rejection.build()` regardless of
`kind`. Asserting `"⛔" in combined and "Relanza:" in combined` proves "a
real customs rejection happened" without inventing `what`/`options` prose
that only Ultron's real implementation will decide. Confirmed this
correctly stays RED today too: today's failure is a bare `argparse` usage
dump (`note.py: error: unrecognized arguments: --promotes ...`), which has
neither marker -- so even the "wrong target type" test fails for the
right underlying reason (the flag doesn't exist at all yet), not a false
green from a coincidental crash matching the assertion.

**Headline-vocabulary isolation, disclosed not guessed:** `validate_replacement`
only skips its similarity rebound when `note.replaces is not None` -- it has
no knowledge of a hypothetical `note.promotes` field. A promoted answer
naturally restates its question's wording (real `TEXTOS.md` example: "do we
need per-seat pricing?" -> promoted to M-051), which risks tripping the
UNRELATED "overlapping note" rejection and misattributing a failure to
`--promotes`. Same lesson as
Round 3 above's Jaccard-overlap
incident: picked deliberately unrelated headline pairs per test (zero
shared content words) so a failure can only come from the `--promotes`
path under test.

File: `unmassk-toolkit/tests/memory/test_note_script_promotes.py` (new
file, per task scope -- no other file touched). 4 classes, all RED today
for the single real cause (`argparse: unrecognized arguments: --promotes`):
Q promotes to M in one commit (round-trip via real `indexes.read_archive`,
never hand-typed text), Q falls to X in one commit, `--promotes` at a
non-Q bounces without writing anything, `--promotes` at a nonexistent id
bounces without writing anything. Atomicity (task's point 6) folded into
the same tests rather than a separate class: success path checks all three
pieces (old index, new index, ARCHIVED.md) from one final state; rejection
paths assert full before/after equality across both indices, ARCHIVED.md,
and commit count. Mid-`git`-crash atomicity explicitly out of scope
(disclosed in the file docstring) -- already covered generically by
`write()`/`replace()`/`close()`'s shared restore mechanism, not re-tested
at this CLI acceptance layer.

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_note_script_promotes.py -v`
-> 4 failed (all 4, same root cause, confirmed via stderr text in each).
`--collect-only` -> 4 tests, 0 errors. `py_compile` clean. Full
`tests/memory` suite: 380 passed, 4 failed (only the new ones) --
`git status --porcelain` on `tests/memory/`/`lib/memory/`/`bin/memory/`
confirmed only this new file carries my edits; the `M` markers on
`bin/gitmem`/`lib/memory/utf8.py`/`conftest.py`/`test_conftest_smoke.py`
belong to concurrent colleagues, not this task.

See also: [[notes-py-full-contract-notes]] (the sibling `replace()`/
`close()` RED contract this one completes the third destination for),
Round 2 above (the `--replaces`
CLI wiring this task's `--promotes` is explicitly symmetric to).

## Round 7 (D-044/D-045, undated in the original file) — --issue opens from M-only to all seven types

Task: `--issue` opens from M-only to all seven types (D, M, R, Q, X, I, B) --
D-044/D-045, unmassk-toolkit memory. Test-first, contract pass only (no
production code touched). File:
`unmassk-toolkit/tests/memory/test_note_issue_field.py`.

**Two independent production gates found, not one** -- worth remembering
before assuming "fix vocabulary.py" closes the whole contract:
1. `lib/memory/vocabulary.py::TYPES[<T>].allowed_fields` -- only `"M"` has
   `"issue"`. This is what blocks save for the other six types
   (`validator.validate_fields()` rejects: "Estos campos no existen para
   el tipo <T>: issue").
2. `lib/memory/report_render_note.py:96` -- `if note.type == "M" and
   note.issue is not None:` -- a SECOND, independent type check in the
   renderer `search.py --id` uses. Fixing only #1 leaves `--id` silent
   about the issue number for non-M notes. Two other places that ALREADY
   don't care about type (verified reading the code, not assumed): `gh`
   existence check (`validator_issue.py::validate_issue`, no type branch,
   called unconditionally before the vocabulary gate) and the commit
   trailer writer (`format.py::_body_field_line`, `label == "Issue"` with
   no type condition).

**Fake-gh-on-PATH technique** for subprocess-level `note.py` tests that
need to control `gh issue view` without network: `note.py` runs as a real
child process (`run_memory_script`), so `monkeypatch.setattr(subprocess,
"run", ...)` (the technique `test_health.py::_patch_gh` uses, since
`health.py` runs in-process) cannot reach it. Instead, write an executable
Python script named `gh` into a throwaway dir under `tmp_path` and prepend
it to `PATH` via `run_memory_script(..., env={"PATH": fake_dir +
os.pathsep + os.environ["PATH"]})` (`env` already only *adds* to the
inherited environment, never replaces it). The fake script only needs to
understand `gh issue view <N> --json number`: returncode 0 for "exists"
(stdout content irrelevant -- `_issue_exists` only checks
`returncode == 0`), returncode 1 with the exact marker string
`validator_issue.py::_ISSUE_NOT_FOUND_MARKER` declares
("Could not resolve to an issue or pull request...") for "missing". This
mirrors gh's real output shape, doesn't replicate `validator_issue.py`'s
own logic -- same justification `unmassk-standards` Sec.34.5 gives for any
mock of an external/non-deterministic dependency.

**One test class in the contract is honest about NOT being red today**:
the "issue doesn't exist -> rejected" check already works uniformly
across all seven types right now, because `validate_issue()` never
branches on `note.type` -- it's called before the vocabulary gate, not
after. Wrote it anyway (task explicitly asked, and it's a real regression
guard against a future reordering), but labelled it clearly as a guard,
not a red case, in both the test docstring and the delivery report.
Don't force a green guard test to look red just to match a blanket
"everything must fail today" instruction -- report the actual state.

**Pitfall avoided**: manual ad-hoc reproduction outside pytest (a scratch
git repo + running `note.py` by hand) tripped a stray GLOBAL
`core.hooksPath` pointing at a *different* unrelated repo on this
machine (`claude-git-memory/.git/hooks`), rejecting the commit with a
customs-hook message that has nothing to do with this task. pytest's own
`tmp_repo` fixture does NOT hit this (confirmed: the existing suite
passes fine through the same `run_memory_script` machinery) -- the
interference is purely an artifact of manual shell reproduction, not a
real signal. Lesson: trust the project's own test harness over ad-hoc
manual reproduction when the two disagree; don't spend budget chasing
what turns out to be unrelated machine-local git config.

Result: 7 tests red for the right reason (6 types x accept-and-trailer,
1 round-trip via `search.py --id`), 10 green (M baseline + 7-type
not-found guard + 2 scope-creep guards). Full `tests/memory` suite:
482 passed, 1 skipped (pre-existing), 7 new red -- zero collateral
damage.
