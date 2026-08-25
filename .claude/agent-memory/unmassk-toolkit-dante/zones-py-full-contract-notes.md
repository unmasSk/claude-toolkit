---
name: zones-py-full-contract-notes
description: lib/memory/zones.py + bin/memory/zones.py + git-memory-doctor.py's zones-check, full campaign merged from 5 date-split files — original §6.2 contract, English rename + duplicate bounce, alias-collision bounce, doctor check_project_zones() added, absent-vs-empty doctor gap
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 2, extended phase 3) from 5 separate files that all
covered the SAME piece of code — `lib/memory/zones.py` / `bin/memory/zones.py`, plus `bin/git-memory-doctor.py`'s
zones.json awareness (Round 4, added phase 3: same code area Round 5 already treats as joint territory,
confirmed by re-reading both — `check_project_zones()` still lives at `bin/git-memory-doctor.py:306` today) —
split only by which session touched it. Per this project's compaction rule ("varios ficheros sobre UN mismo
trabajo... se funden en uno por tema"). Nothing was cut; each original file's content is reproduced below
verbatim under its own dated heading, in chronological order. Original filenames (now retired, kept only as
history in this note, not on disk): `zones-contract-notes.md`,
`zones-script-english-rename-and-duplicate-bounce-notes.md`, `zones-alias-collision-bounce-contract-notes.md`,
`doctor-zones-check-retirement-notes.md`, `zones-list-doctor-absent-vs-empty-contract-notes.md`.

## Round 1 (2026-08-02) — zones.py §6.2 original RED contract + the cross-module-import infra fix

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

## Round 2 (2026-08-04) — CLI rename alta/listar/buscar → add/list/find, duplicate-zone bounce

Context: `unmassk-toolkit/tests/memory/test_zones_script.py`, already existed
GREEN (4 tests) from a prior session against a REAL, already-implemented
`bin/memory/zones.py` (not the usual "script doesn't exist yet" RED). This
task landed two owner decisions (2026-08-04) on the SAME script at once:
subcommands `alta`/`listar`/`buscar` -> `add`/`list`/`find` (no alias, no
grace period), and re-registering an existing zone name must bounce instead
of silently overwriting (real regression reproduced live by the
orchestrator that same session: second `alta` on `billing` wiped the first
one's alias/description, both printed the identical "✅ dada de alta").

**Technique: chained-RED for two decisions landing in one file at once.**
Testing decision 2 (duplicate bounce) requires a *first* successful
registration to bounce against -- but decision 1 (rename) isn't implemented
yet, so seeding through the new `add` verb fails today for a DIFFERENT
reason than the one under test. Resolved by asserting the first call's
`rc == 0` explicitly, with a message naming it as the seed step -- this
makes the test fail today at the seed assertion (real reason: `add` not
recognized), and will only pass once BOTH decisions are real: rename done
AND dedup implemented. No vacuous-pass risk verified two ways: (a) ran the
suite and confirmed every one of the 10 new/changed tests fails for a
distinct, correct reason (`pytest -v`, read every traceback); (b) mentally
walked "rename done, dedup still missing" -- second `add` would then
succeed (rc==0) and overwrite, so `rc_second != 0` and the byte-compare
would both catch it independently. Two independent invariants (rc AND
byte-identity) that don't share a common trivial-pass cause is the pattern
to reach for whenever one RED test has to prove a chain of two behaviors.

**Old-subcommand-retirement test needs a positive check beyond `rc != 0`,
for `alta` specifically (the write path).** `rc != 0` alone can't tell
"argparse rejected an unknown token" from "the write silently half-failed
for some other reason" -- confirmed the real discriminator is whether the
zone shows up via `zones.load()` afterward. For the two read-only old verbs
(`listar`/`buscar`) there's nothing to seed-and-check-absence against, so
the positive signal used instead is argparse's OWN literal echo of the
offending token (`invalid choice: 'listar'`) -- verified live this is
Python's own contract (`argparse` always echoes the bad choice verbatim),
not fabricated project prose, so it's fair game under the "no invented
rejection text" rule even though no project document names this case.

**No TEXTOS.md text exists for "zone already exists"** -- verified by
grep across the whole file for "ya existe"/"duplicad"/"already" combined
with zone-related terms. Sec.1.1 is the *opposite* rejection ("zona que NO
existe"). Contract enforces behavior only (bounces, `rc != 0`, file
byte-identical via `Path.read_bytes()` before/after PLUS
`zones.load()` field-by-field) plus one non-fabricated positive datum (the
real zone name must appear in the combined output) -- never a hand-typed
rejection sentence. Documented explicitly in the file's module docstring
so Ultron doesn't have to re-derive this by searching again.

**Alias-collision case left OUT on purpose.** `zones.resolve()` already
applies aliases when resolving a name to its canonical zone, but no
document and no existing function decides whether registering a NEW name
that collides with another zone's *alias* (not its canonical name) should
also bounce. Flagged in both the test file's docstring and the task report
instead of guessed at -- matches the project's explicit rule (`CLAUDE.md`):
"un hueco puede ser deliberado", fill nothing from personal judgment.

**B22 (2026-08-04) retired concurrency as an in-scope test concern for this
whole project** -- *"dos escrituras a la vez sobre el mismo fichero: no se
dan... trabaja en una sola ventana"*. The task's own instructions echoed
this as a hard boundary ("dos procesos a la vez está descartado. Nada de
eso") for what I should ADD. Left the pre-existing
`TestTwoConcurrentRegistrationsDoNotClobberEachOther` class untouched in
shape (only updated its subcommand string for the rename) rather than
deleting it unilaterally -- it predates B22, is currently exercising real
locking code that's still in production, and deleting an unrelated
passing test outside the two decisions I was scoped to touch is exactly
the kind of unauthorized scope creep this project's CLAUDE.md warns
against ("nada se rellena con criterio propio"). Flagged as a retirement
candidate in the report instead.

Verification command: `python3 -m pytest unmassk-toolkit/tests/memory/test_zones_script.py -v`
-> 10 failed, each for a distinct real reason (read every traceback, no
generic "script not found" catch-all since the script already exists).
`--collect-only` on the whole `tests/memory` dir confirms no other file
touched (292 tests collected, only this file's own tests changed shape).

## Round 3 (2026-08-04, same day) — alias-collision bounce, the hole Round 2 explicitly left open

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

## Round 4 (before 2026-08-06) — check_project_zones() (#13) added to git-memory-doctor.py; the anti-vacuity control that proved the pre-fix gap retired once it closed

`test_doctor_derived_expectations.py` had a `TestDoctorNeverMentionsZonesToday`
class whose single test (`test_no_check_in_the_report_mentions_zones`)
existed purely as an anti-vacuity control: it proved, before Ultron's fix,
that `git-memory-doctor.py` genuinely had zero checks naming zones.json (so
the RED tests below it in `TestDoctorChecksZonesJson` weren't trivially
passing against a doctor that flags everything or nothing).

Ultron added `check_project_zones()` (check #13, `bin/git-memory-doctor.py:283`,
wired into `run_doctor()` at line 536). That made the control's premise false
on purpose — the doctor now DOES mention zones, always. Retired the class
entirely rather than inverting it into "doctor SI menciona zonas", because
`TestDoctorChecksZonesJson::test_a_zones_check_appears_in_the_report_for_every_state`
(parametrized absent/empty/populated) already proves presence for every
state, and `test_a_populated_zones_json_is_reported_ok_not_as_a_problem` is
that class's own anti-vacuity control (proves it isn't always "error"). An
inverse test would have been redundant, not additive.

**Why:** an anti-vacuity control's job is to prove a *pre-fix* gap was real.
Once the fix lands and a proper hardening class already covers the positive
case with its own anti-vacuity control, the pre-fix control has no further
job — keep it only if no equivalent post-fix coverage exists.

**How to apply:** when a "RED encargo" comment block precedes a class that
documents a gap in the present tense ("today X does not Y"), and the gap
closes, don't just delete silently — annotate the block itself
(`[cerrado <date>: ...]`, same style as the `[corregido 2026-08-05: ...]`
annotation already in this file for `EXPECTED_HOOKS`) so the historical
record of why the contract existed survives, then decide retire-vs-invert
by checking whether the surviving hardening class already exercises the
positive case. See [[test-file-self-drift-correction-notes]] for the
broader "stale prose inside test files, annotate don't silently delete"
pattern this follows.

## Round 5 (2026-08-06) — zones.py list + doctor.py: absent-vs-empty zones.json masking (continues Round 4's check_project_zones())

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
