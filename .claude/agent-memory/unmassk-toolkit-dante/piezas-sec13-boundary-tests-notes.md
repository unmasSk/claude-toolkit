---
name: piezas-sec13-boundary-tests-notes
description: PIEZAS.md Sec.13 boundary tests (tests/memory/test_boundary.py) — AST import-graph technique, real red finding, re-export resolution
metadata:
  type: project
---

Wrote `unmassk-toolkit/tests/memory/test_boundary.py` (2026-08-04) implementing the
three "puerta 3" tests from `docs/memoria-v2/PIEZAS.md` Sec.2/Sec.13 (NOT the
4th mermaid-vs-`ARQUITECTURA.md` test — that's a separate task, depends on a
doc this one doesn't touch). 9 tests: 3 real contract checks + 6 self-verification
("prueba de fuego") tests proving each detector fires on a planted violation in
`tmp_path`, per the project's `§34`-style anti-vacuity rule.

**Real result, verified by running, not assumed:** test 1 (outside→inside) and
test 2 (inside→outside) pass clean against the real repo — the v2 separation
already holds in practice. **Test 3 (symbol-level "nada exportado sin
importador") is genuinely RED — 19 public symbols with zero real production
importer** (`boot.blockers_section`, `format.build_subject`/`parse_subject`/
`SubjectParts`, `gitcmd.LockNotReentrantError`, `health.coherence_rules`/
`duplicates`, `indexes.counts`, `notes.discard_alternatives`/`replace`,
`query.is_unborn_branch`, `report_render.render`, five `validator.validate_*`,
`vocabulary.FieldSpec`/`TypeSpec`). Left red on purpose — owner's explicit
instruction was "no lo ajustes para que pase". Full per-symbol root-cause is in
the test's own docstring (each one verified by reading the real call site, not
guessed): almost all are "used only inside their own defining module" (an
orchestrating public function like `validate_note()`/`build_message()`/
`health.build()` composes several other public-but-never-externally-imported
siblings) — legitimate design in some cases, dead/misdocumented in at least one
(`notes.replace`/`discard_alternatives`: PIEZAS.md Sec.10 documents `note.py`
as calling them; the real `bin/memory/note.py` only calls `notes.write`).

**Technique — real import-graph via AST, not grep, not hand list:**
[[unmassk-toolkit-python-test-conventions]] already established the
`import_lib_memory_module()` load-by-content-hash pattern (conftest.py) for
*executing* lib/memory code in tests. This task needed the opposite: read
(never execute) every production `.py` file's `Import`/`ImportFrom` AST nodes.
Precedent style copied from `test_query.py::_git_history_call_sites` (AST over
grep specifically because several files *cite* code in their own docstrings to
explain a past fix — a text grep would misfire on the prose, `ast.walk` never
does since it only sees real syntax nodes).

**The one real trap in this technique — one-hop re-export resolution.** A naive
"does any OTHER file directly `from stem import symbol`" check produces false
positives: `format.py` deliberately re-exports `format_lines.py`'s four
build/parse functions under the same flat name (`from format_lines import
build_index_line, ...`), and the only real consumer (`indexes.py`) reaches them
as `format.build_index_line(...)`, never `format_lines.build_index_line(...)`.
Without resolving that chain, all four `format_lines` functions show as
"orphaned" — a genuine false positive that would have discredited the whole
gate. Fix: `_resolve_owner(stem, symbol, definer_info, depth)` walks
`from_imports` chains (depth-capped at 8) until it hits the module that
actually *defines* the symbol via `FunctionDef`/`ClassDef`, not just re-imports
it. Verify this specific case with a dedicated positive-AND-negative-control
pair of `tmp_path` tests (one proving a genuine orphan IS caught, one proving a
legitimate one-hop re-export is NOT flagged) — a single "catches a planted
violation" test is not enough for a resolver this can silently over-trigger.

**Also learned:** don't try to *really import* (`importlib`) production
consumer scripts to resolve identities — `hooks/boot_launcher.py` has
unguarded top-level code (`sys.stdin.read()`, `subprocess.run(...)`,
`sys.exit(0)`, no `if __name__ == "__main__":`) that would hang/side-effect a
test process. Stayed 100% AST (read, never exec) for every production
consumer file for this reason, not just for style.

See also [[unmassk-toolkit-python-test-conventions]] for the conftest loader
this file deliberately does NOT use (it reads text, it doesn't need the
module objects).

## 2026-08-04 follow-up — exception list rejected mid-task, replaced with a two-branch metric

Owner asked to except `indexes.counts` from the orphan gate (it has zero
production callers but 3 `test_health.py` tests use it as a §34 second-opinion
oracle for `health.coherence()`). Built a hand-written `ORACLE_EXCEPTIONS` table
+ re-verification mechanism (each row names what it verifies, re-checked by AST
against the declared test file every run, two fire tests proving a stale row
falls back to red). **Orchestrator interrupted mid-task and reversed the whole
approach before I finished** — see [[dante-owner-metric-over-allowlist-feedback]]
for the general lesson. Reverted the exception-table edit by hand (file was
untracked, no `git checkout` possible) back to the exact original content, then
rebuilt around the owner's design instead.

**What shipped instead:** `_symbol_usage_report()` computes, per public symbol,
two independent counts — `production` (files outside `tests/memory/` that
import/call it, reusing the same `_resolve_owner` one-hop re-export logic as
the module/symbol orphan detectors) and `tests` (test **functions**, not
files — counted once per function even if used multiple times in its body).
Only rule that fails the suite: `production == 0 and tests == 0`. `production
== 0` with `tests >= 1` prints in a watch-list table but does not fail.

**Test-branch AST trap, specific to this codebase's convention:** tests never
do `import indexes` — every `lib/memory/` module is a pytest fixture matching
the stem name (`@pytest.fixture def indexes(): return
import_lib_memory_module("indexes")`, redefined per test file). So the
test-branch detector doesn't look for `Import`/`ImportFrom` nodes in test
files at all — it looks at each `def test_*(...)` function's **parameter
names** (`params & stem_set`) and then, inside that function's body only,
`ast.Attribute` nodes shaped `param.symbol`. A module-level `import widget` in
a test file (not fixture-based) would NOT be counted — verified none of the 25
test files in `tests/memory/` do this; documented as a known limit in the
test's own docstring rather than silently handled.

**Visibility requirement, solved without touching conftest.py:** owner
required the two-column table to print "aunque el test pase" — a `print()`
alone is swallowed by pytest's capture in `-q`/non-verbose runs, and this repo
had already been burned once by a silent checker ("indistinguible de uno que
no se ejecuta"). Fix: `capsys.disabled()` inside the test body writes straight
to the real terminal, bypassing capture entirely, regardless of pass/fail or
verbosity flags. Avoided a `pytest_terminal_summary` conftest hook on purpose
— the task's write scope was locked to `test_boundary.py` only, and hooks only
fire from `conftest.py`/plugins, not arbitrary test modules.

**Finding requested by the owner, confirmed by rerunning the new report against
the real repo:** of the 15 red symbols, only 3 have `production == 0` **and**
`tests >= 1` — i.e. are genuinely in the same "second opinion" situation as
`indexes.counts` (not just "has some test"): `indexes.counts` (3 tests),
`health.coherence_rules` (11 tests — `test_boot.py` calls it directly and
compares against `summary.health.rule_commits`/`rule_lines` from
`boot.build()`), `health.duplicates` (1 test — same file, compares against
`summary.health.duplicate_ids`). The other 4 with `tests >= 1`
(`validator.validate_headline`/`validate_fields`/`validate_replacement`/
`validate_distillation`, 1–3 tests each in `test_validator.py`) are *not*
second-opinion oracles — they're direct behavior tests of the function's own
return value, no independent producer↔consumer comparison. The remaining 8
are truly dead (`production == 0`, `tests == 0`): `format.build_subject`/
`parse_subject`/`SubjectParts`, `gitcmd.LockNotReentrantError`,
`query.is_unborn_branch`, `validator.validate_type`, `vocabulary.FieldSpec`/
`TypeSpec` — this is the real, current RED, left red on purpose (owner's
instruction still stands).

## 2026-08-04 round 2 — the test-branch detector itself was lying (fixture alias blind spot)

Owner ran the table above and caught a self-inflicted bug: the test-branch
counter matched `params & stem_set` — the test function's **parameter name**
had to equal the module's **stem** literally. But `format.py` can never be
received under its own name in any test file: `format` shadows Python's
built-in function, so every consumer aliases it (`fmt` in
`test_format.py`/`test_query.py`, `format_mod` in
`test_customs_hook.py`/`test_notes.py`, `format_lib` in
`test_search_script.py`). Consequence: **every symbol of `format.py` showed
"0 tests" unconditionally**, even though `test_format.py:380/387/393` call
`fmt.build_subject(...)`/`fmt.parse_subject(...)` for real. This is a
structural blind spot, not "3 missing tests" — any module received under an
alias anywhere would be invisible to this branch, forever.

**The fix reads the alias from the same source that declares it — the test
file's own AST — never a guessed heuristic.** Every module-alias fixture in
this codebase (verified across all 25 test files, zero exceptions) follows
one exact shape: a bare `@pytest.fixture`-decorated, no-arg, top-level
function whose single statement is `return
import_lib_memory_module("<stem>")`. New helper `_fixture_stem_aliases(tree,
stem_set)` walks `tree.body` for that shape and returns `{fixture_name:
stem}`. The test-branch loop then resolves each `test_*` parameter through
that map (`param_to_stem`) instead of intersecting raw parameter names
against `stem_set`, and feeds the **resolved stem** (not the raw param name)
into `_resolve_owner()` — the bug was that the old code passed
`sub.value.id` (the local/aliased name) straight into the owner-resolution
function that expects a real stem.

**Verified both directions with dedicated `tmp_path` fire tests** (owner's
explicit ask: "demuéstrame que cuenta un módulo con apodo" + the symmetric
"que un símbolo que de verdad no toca ningún test siga contando cero"):
`test_two_branch_report_resolves_a_module_received_under_an_alias` plants a
`lib_memory/format.py` + a `test_format.py` with the exact real-world shape
(`@pytest.fixture def fmt(): return
import_lib_memory_module('format')`) and asserts the symbol is found;
`test_two_branch_report_does_not_over_count_an_untouched_symbol_in_an_aliased_module`
plants a **second, untouched** symbol in the *same* aliased module and
asserts it still reads zero — guards against the fix over-firing and
flagging the whole module as "touched" once any one alias resolves.

**Real-repo effect, confirmed by rerunning against the actual codebase (not
assumed):** exactly 2 of the 15 watch-list rows were **false** before this
fix — `format.build_subject` and `format.parse_subject` both silently read
"0 tests" when the true value was "1" each
(`test_format.py::test_emoji_after_brackets_enforced`). `format.SubjectParts`
stayed at 0 tests correctly — genuinely untested, and `test_format.py`'s own
docstring (lines 20–23) already admits this ("ningún test construye ni
inspecciona un SubjectParts"), so it was never a detector bug. Verdict
unchanged: still 6 genuinely dead symbols (`format.SubjectParts`,
`gitcmd.LockNotReentrantError`, `query.is_unborn_branch`,
`validator.validate_type`, `vocabulary.FieldSpec`, `vocabulary.TypeSpec`) —
down from 8 before the fix, purely because 2 rows were wrong, not because
the bar moved. Also noted in passing (unrelated to this fix):
`boot.blockers_section` no longer appears in the table at all — it was
renamed `_blockers_section` (private) by other work the same day, so it fell
out of the "public symbol" scope entirely.

**A second, distinct blind spot was found but deliberately NOT fixed**
(reported to the owner instead of silently expanding scope — "one thing at a
time, ask before new work"): the test-branch loop only scans `tree.body`
(module top level) for `test_*` functions. **14 of the 25 test files define
their tests as methods inside a `class Test...:` block**, and those methods
live inside the `ClassDef`'s body, never `tree.body` — completely invisible
to this counter, same as `format.py` was. Checked it doesn't change today's
verdict (none of the 6 truly-dead symbols' only real test usage lives inside
a class-based file — the closest case, `test_search_script.py`, is 100%
class-based and does call `report_render_lib.render_zone`/`render_word`, but
the actual dead symbol is `report_render.render`, a different name it never
calls) — but it's a live gap the owner should decide whether to fix next.
Also noted: `test_utf8.py` uses a third, completely different pattern —
module-level `utf8 = import_lib_memory_module("utf8")` (no fixture, no
per-test parameter, referenced as a closure) — harmless today since no
`utf8.py` symbol is on the red list, but it means a third code path exists
that this detector's test-branch still can't see.

## 2026-08-04 round 3 — the two gaps flagged as "declared limits" in round 2 got promoted to fixed, because the detector is leaving the branch

Owner decided this file becomes `unmassk-toolkit/bin/dead-code.py` — ships to
every project, not just this repo. That changes the bar: a "declared limit"
that's harmless *in this repo today* (verified: none of the 6 truly-dead
symbols' only real test lives inside a class) is not acceptable in a tool
that travels, because the next repo won't be this lucky. Both gaps named in
round 2's docstring got fixed in the same file, same session:

1. **Class-based tests invisible** — orchestrator independently confirmed
   14/36 files group tests in `class Test...:`. New `_iter_test_functions(tree)`
   walks `tree.body`, and for each `ast.ClassDef` also yields its `test_*`
   methods as `("ClassName::method_name", node)` — matching pytest's real
   node-id format so table rows stay human-readable. `self` is explicitly
   stripped from the parameter set before fixture resolution (it can never
   collide with a real stem, but the owner called it out by name in the ask,
   so it's handled by name, not by accident).
2. **Module-level variable without a fixture** (`test_utf8.py`'s own
   pattern, `utf8 = import_lib_memory_module("utf8")` at module scope) — new
   `_module_level_stem_aliases(tree, stem_set)` matches that exact literal
   shape (single-name `ast.Assign` at `tree.body` level, value is
   `import_lib_memory_module("<stem>")`). Its results are merged into every
   test's alias map in the file (a module var is visible everywhere via
   closure, unlike a fixture param) — `dict(module_var_to_stem);
   .update(param_to_stem)` so a same-named local param still wins, matching
   real Python scoping.

**Anti-over-count discipline, forced by the owner's explicit fear** ("no
puede empezar a contar como probado algo que solo se menciona de pasada" —
seeing far more code once classes are in scope must not turn a blind spot
into a lie): each new pattern got the same two-test pair as the alias fix —
one `tmp_path` fixture proving a touched symbol IS counted, one proving a
**second, untouched symbol in the same class/file** stays at zero (guards
specifically against "resolves one alias in the file → marks the whole
module as tested", which is the shape a lazy fix would take).

**Manual spot-check requested by the owner** ("ve al test que ahora dice que
los prueba, y compruébalo con tus ojos") — read the real call site, not just
trusted the detector's own output, for 3 symbols whose test count changed
with this round's fix: `utf8.force_utf8_streams` — real call at
`test_utf8.py:82` (`TestForceUtf8StreamsIdempotent::
test_calling_twice_keeps_utf8_and_does_not_raise`, via the module-level
`utf8` var); `report_render.render_zone`/`report.build_zone` — real call at
`test_search_script.py:187` (`TestZoneQueryMatchesTheRealProducerRoundTrip::
test_zone_report_equals_report_render_render_zone_for_real`,
`report_render_lib.render_zone(report_lib.build_zone(...))`, both class-method
fixture params); `zones.load` — real call at `test_zones_script.py:161`
(`TestTwoConcurrentRegistrationsDoNotClobberEachOther::
test_two_zones_py_processes_registering_different_zones_at_once`,
`zones_lib.load(zones_path)`). All three are genuine calls on the result,
not an incidental mention — confirms the fix widened *visibility*, not
*criteria* (the "touched" rule — a real `ast.Attribute` access with `Load`
context — never changed across all three rounds of this file).

**Effect on the red-symbol table: none, verified by rerunning, not assumed.**
The 15-row watch list (`production == 0`) is byte-identical before and after
round 3 — the 14 class-based files and `test_utf8.py`'s pattern add test
coverage to plenty of symbols, but every one of those symbols already had
real `production >= 1`, so they were never in the watch list to begin with.
**This is a fact about this repo's current shape, not about the fix** — the
whole reason round 3 exists is that the next project this tool ships to
won't get that same luck for free.

Full suite after round 3: `python3 -m pytest unmassk-toolkit/tests/memory -q`
→ 319 passed (4 new fire tests added this round), 1 failed — same
intentional red as before (`test_no_public_symbol_has_zero_production_and_zero_tests`,
6 genuinely dead symbols, left red on purpose, unchanged by either round).
