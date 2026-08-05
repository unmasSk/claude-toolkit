---
name: health-boot-rule-coherence-wiring-notes
description: RED contract wiring health.coherence_rules() into model.HealthReport + boot.py AVISOS (Cerberus finding, "mute watchdog"); plus GREEN coverage of the pre-existing report_render.render() dispatcher alias (0 tests -> 3)
metadata:
  type: project
---

Two-part task, both tests-only, on `unmassk-toolkit/tests/memory/`:

## Part 1 -- connecting a watchdog that exists and reaches nobody

Cerberus finding: `health.coherence_rules(root)` (5 tests, green, see
[health-contract-notes](health-contract-notes.md) Update section) detects a
real silent-loss failure mode but is a dead end -- `model.HealthReport`
declares 4 fields with no slot for its 2 numbers, `health.build()` excludes
it on purpose (own docstring says so), `boot.py` never paints it. Same
pattern that already cost this branch dearly in layer 1 (green tests while
the system broke itself).

**4 RED tests added, one per row the orchestrator specified** (this
project's convention: "una fila = un test, ni uno mas"):

1. `test_health.py::test_health_report_carries_the_real_rule_coherence_numbers`
   -- `HealthReport` carries the rule numbers.
2. `test_boot.py::test_avisos_block_paints_rule_coherence_alongside_the_other_two_checks`
   -- boot paints it in AVISOS, next to the other two checks.
3. `test_boot.py::test_avisos_block_shows_the_real_rule_count_when_everything_is_fine`
   -- speaks even when everything's fine, with the real number (3 rules
   seeded, not 1, so the number can't coincide with a default).
4. `test_boot.py::test_a_rule_line_deleted_by_hand_is_shown_as_a_warning_at_boot_end_to_end`
   -- the row that matters most: a real lost rule (file line deleted by
   hand, commit intact) makes boot say so, end to end, and boot still
   completes (doesn't throw).

**Field names -- decided here, not sourced from any doc** (PIEZAS.md
Sec.5.3's `HealthReport` still shows only 4 fields as of this session; the
owner was away, task said "decide with what's in front of you and annotate"):
`rule_commits: int` / `rule_lines: int`, matching `coherence_rules(root) ->
tuple[int, int, tuple[str,...]]`'s own signature comment ("commits de
regla, lineas, discrepancias") and mirroring the existing `index_lines`/
`git_notes` naming (file-side first, git-side second) with a `rule_`
prefix to disambiguate from the note-coherence pair now that there are two.
If Ultron picks different names, only the two `summary.health.rule_*`
assertion lines need to change per test, never the whole test -- same
"solo la comprobacion puntual cambia" escape hatch this branch already
uses for undecided formats.

**AVISOS line text -- also undecided in TEXTOS.md Sec.3.1 (that row
doesn't exist there yet)**, so assertions check substrings/symbols/real
numbers rather than a fixed literal: presence of "reglas", the correct
symbol (✓ when coherent, ⚠ when not), and the real `rule_lines`/
`rule_commits` values as strings inside the AVISOS block -- never a full
hand-typed line. Documented the suggested format (mirroring the existing
`{lineas} lineas / {notas} notas` index line, swapping "indices"->"reglas"
and "notas"->"commits") directly in the test module docstring as a
decision, not a requirement.

**Gotcha that produced a false-RED on the first run:** all 4 new tests
initially failed with `FileNotFoundError: indice inexistente, seed() no
corrio` instead of the intended `AttributeError` -- `health.build()` (and
therefore `boot.build()`) also calls `coherence()`/`duplicates()`
internally, which need the 7 vigente indexes seeded via
`indexes.seed(notes.pm_root(root))` even though this task's own scenario
only cares about `rules.md`. Every test that calls `health.build()`/
`boot.build()` needs that seed call FIRST, even when seeding rules only --
confirmed live before trusting the final RED reason (re-ran after adding
the seed calls, got the intended `AttributeError: 'HealthReport' object
has no attribute 'rule_commits'` in all 4).

## Part 2 -- report_render.render(), 0 tests on already-green code

Same DEUDA.md point-11 shape as `health.plans_unreflected()`/
`coherence_rules()` before their own tests existed: `report_render.render()`
is a 4-line type-dispatch alias (`isinstance(r, ZoneReport) ->
render_zone(r)`, `WordReport -> render_word(r)`, else `raise TypeError`),
already in production, exists only because
`vocabulary.FIELDS["why"]/["description"].reader == "report_render.render"`
(singular) while the real surface is two functions. `test_report_render.py`
already existed with 10 tests but every one of them called
`render_zone`/`render_word` directly, never the alias itself -- the
module's own header docstring is now stale ("report_render.py NO EXISTE
TODAVIA") since a colleague finished it mid-branch; the file is green.

**3 tests added, GREEN from the first run, full branch coverage of a
3-branch function:** dispatch-to-`render_zone` (asserted via output
equality against calling `render_zone` directly on the same real
`ZoneReport`, not by re-checking content already covered by the other 10
tests), dispatch-to-`render_word` (same technique), and the error path
(`render(object())` -> `pytest.raises(TypeError)`, the one branch nothing
else in the file exercised).

Verification: `python3 -m pytest unmassk-toolkit/tests/memory -q` -> 140
passed, 4 failed (the 4 intentional RED tests, all `AttributeError:
'HealthReport' object has no attribute 'rule_commits'`) -- confirmed the
baseline 137 are all still green (137 + 3 new green report_render tests =
140). `git status --porcelain` confirmed only `test_health.py`/
`test_boot.py`/`test_report_render.py` touched, all already untracked
before this session (branch convention: nothing here is committed) -- no
`lib/memory/` file written.

Related: [health-contract-notes](health-contract-notes.md),
[boot-contract-root-vs-pmroot-notes](boot-contract-root-vs-pmroot-notes.md),
[capa4-hardening-session-notes](capa4-hardening-session-notes.md).
