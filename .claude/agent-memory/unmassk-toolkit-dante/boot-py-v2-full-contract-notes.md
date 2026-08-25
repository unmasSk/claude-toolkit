---
name: boot-py-v2-full-contract-notes
description: memoria-v2 lib/memory/boot.py rendering + health.py coherence full campaign merged from 4 files — coherence_rules() wiring into AVISOS, 4 Argus regressions, COUNTS label rename, corrupted-git-object isolation
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 2, extended phase 3) from 4 separate files that all
covered the SAME piece of code — `lib/memory/boot.py`'s rendering pipeline and the `health.py`/`report.py`/
`query.py` checks it composes (the CURRENT v2 module, not the deleted v1 `lib/boot_git_checks.py` — confirmed
by reading each file, zero references to that module) — split only by which session touched it. Round 1
(added phase 3) is the founding episode of the exact `health.coherence_rules()` + boot.py AVISOS thread the
later rounds keep extending; confirmed still live today (`health.py:174`, `test_health_rules_coherence_
contract.py` exists). Per this project's compaction rule ("varios ficheros sobre UN mismo trabajo... se
funden en uno por tema"). Nothing was cut; each original file's content is reproduced below verbatim under
its own dated heading. Original filenames (now retired, kept only as history in this note, not on disk):
`health-boot-rule-coherence-wiring-notes.md`, `boot-report-argus-four-regressions-notes.md`,
`boot-open-issues-label-rename-contract-notes.md`, `boot-git-object-corruption-contract-notes.md`.

## Round 1 (2026-08-02, precedes Round 2) — connecting health.coherence_rules() (a watchdog that existed and reached nobody) into model.HealthReport + boot.py AVISOS

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

## Round 2 (2026-08-02) — 4 Argus-confirmed-fixed bugs pinned as regressions (boot.py/report.py/health.py)

Session 2026-08-02, `feat/memoria-v2` branch. Task: pin 4 already-fixed
production bugs with regression tests, `tests/memory/` only -- two other
agents were actively working inside `lib/memory/` at the same time, so no
production file (not even a throwaway edit) could be touched, not even
temporarily. See [capa4-hardening-session-notes](capa4-hardening-session-notes.md)
for the general session context.

## The four bugs and where each test landed

1. **Fresh-project crash** (`boot.build()` + `report.build_zone`/`build_word`):
   `indexes.archived_ids(root)` used to call `read_archive(root)`
   unconditionally, so a project where `ARCHIVED.md` was never created blew
   up with `FileNotFoundError` on the FIRST session. Fixed with an early
   `if not (root / _ARCHIVE_NAME).exists(): return frozenset()`. Tests:
   `test_boot.py::test_a_repo_where_indexes_seed_never_ran_boots_without_crashing`,
   `test_report.py::test_build_zone_on_a_repo_where_indexes_seed_never_ran_does_not_crash`,
   `test_report.py::test_build_word_on_a_repo_with_no_project_memory_directory_at_all_does_not_crash`.

   **Key gotcha**: `notes.write()`/`notes.write_work()`/`context.write()` all
   auto-call `indexes.seed(pm)` internally before writing. So a "genuinely
   fresh, seed never ran" fixture must NOT call any of those either -- just
   a bare `tmp_repo` (git init + initial commit, nothing else) is the only
   state that reproduces the real bug. Every pre-existing "empty memory"
   test in this codebase (`test_empty_memory_shows_explicit_loud_zeros_...`)
   calls `indexes.seed()` first, so none of them actually covered this.

   **Second gotcha (report.py only)**: `zones.add()` needs its destination
   directory to already exist -- `tempfile.mkstemp(dir=dest_dir, ...)`
   raises if `dest_dir` is missing, and `zones.add()` never creates it.
   `build_zone` needs a registered zone (else `ValueError`, a different,
   legitimate flow), so its fresh-project test does `pm_root.mkdir(parents=True)`
   by hand (simulating whatever real flow registers a zone before any note
   is ever written) and registers the zone, but never calls `indexes.seed()`
   -- so the 8 index files + `ARCHIVED.md` still don't exist. `build_word`
   needs no zone at all, so its test uses the truly-empty case: no
   `.claude/project-memory/` directory whatsoever.

2. **gh-failure isolation** (`health.build()` / `boot.build()`):
   `plans_unreflected()` correctly raises `RuntimeError` when `gh` fails
   (already tested: `test_health.py::test_gh_failure_raises_instead_of_reporting_all_clear`)
   -- but that test only proves the LOW-level function raises. It does NOT
   prove the exception is caught one level up. `health.build()` now wraps
   the call in `try/except RuntimeError`, sets `plans_unreflected=()` and
   `plans_unreflected_error=str(exc)`. New test:
   `test_boot.py::test_boot_survives_a_real_gh_failure_and_shows_it_as_a_warning_line`
   -- drives it end-to-end through `boot.build()`/`boot.render()`, asserts
   `plans_unreflected_error is not None`, and asserts the AVISOS block shows
   "no se pudo comprobar..." naming the real issue number, never a silent
   `()`. No gh mock needed: a `tmp_repo` with no GitHub remote makes
   `gh issue view` fail for real, instantly, no network (same technique
   `test_health.py` row 7 already established).

3. **Phantom fence** (corrupted `ARCHIVED.md` line resurrects a restriction):
   `indexes.read_archive()` silently discards any line
   `format.parse_archive_line()` can't parse (by design, documented
   behavior, not itself a bug). If that line belonged to a properly
   archived note, the note's id drops out of `archived_ids()`, so
   `boot.build()` shows it again as a live restriction -- with NO warning,
   by construction, unless something else catches it. What actually catches
   it: `health.coherence()`'s existing 3-set-difference
   (`git_ids - index_ids - archived_ids`) already, as an EMERGENT property
   (not a dedicated code path written for this exact case), includes the
   note's id as "existe en git pero falta en el indice" once its archive
   line becomes unreadable -- because it's simultaneously not in any live
   index (properly removed) and not in `archived_ids` (corrupted). Test:
   `test_boot.py::test_avisos_names_the_specific_note_when_an_archived_lines_separator_becomes_unparseable`
   -- archives a restriction for real (`indexes.remove()` + `indexes.archive()`,
   same two-step pattern as `test_health.py`'s false-alarm regression),
   corrupts the literal separator `"  →  "` -> `"  ->  "` (the exact
   token `format_lines.build_archive_line` uses -- read it from the real
   written file, never hardcode a fabricated line), and asserts the note id
   shows up in `summary.health.index_discrepancies` AND in the rendered
   AVISOS block.

   **No dedicated fix commit for this exact scenario exists** -- it's
   covered by the general discrepancy engine's correctness, not a targeted
   patch. Mutation-checked by neutralizing `coherence()`'s discrepancy tuple
   to `()` in a scratch copy and confirming the test's core assertion
   (`any(note_id in d for d in ...)`) goes false — see the mutation-check
   section below.

4. **`open_issues` mislabeling**: the count was always "local, un-archived
   acta-de-plan notes carrying `issue`" -- NEVER a real GitHub query -- but
   the boot screen used to render it under the label "issues abiertas",
   which lies (an acta archived for routine cleanup makes a real open issue
   vanish from the count; an acta never archived keeps counting after the
   real issue closed). **Fix is textual only** (`_recuentos_block()` in
   `boot.py` now prints "planes con acta ....." instead of "issues
   abiertas ...."); the calculation is intentionally unchanged and
   documented as an accepted design gap (`boot.py` module docstring, the
   `open_issues` paragraph) -- a second real `gh` round-trip was explicitly
   rejected as redundant cost for a number nobody asked to be GitHub-backed.
   Test: `test_boot.py::test_recuentos_label_says_planes_con_acta_not_issues_abiertas`
   -- writes an acta with `issue=47`, asserts the OLD label is absent and
   the new one is present, archives the acta, asserts the count drops to 0
   locally (proving it never touched GitHub) and the new label persists.

## Mutation-check technique when production is off-limits (concurrent agents)

CLAUDE.md forbade touching `lib/memory/` at all during this task (two other
agents were mid-edit there). To prove none of the 4 new tests were
decorative (unmassk-standards discipline, not §34 -- this is "does the test
actually pin the fix", a different check), the fix was reverted in
**scratch copies**, never the real files:

```
cp lib/memory/*.py  <scratchpad>/dante_mutcheck_4bugs/bug{1,2,3,4}/
# hand-edit ONE anchor per bug's copy (python str.replace with an
# assert-anchor-found guard, so a silent no-op edit fails loud)
```

Then a small standalone script per bug (`sys.path.insert(0, .../bugN)`,
plain `importlib`-free `import boot`/`health`/etc since these are normal
module names, not hyphenated hook scripts) reproduces the exact scenario
the pytest test builds, against a REAL throwaway `tempfile.mkdtemp()` git
repo (never mocked git) and asserts the reverted code fails the way the
original bug failed (crash for bugs 1/2, missing discrepancy for bug 3,
old label present for bug 4). All 4 confirmed RED against their reverted
copies; all 4 pytest tests confirmed GREEN against the real, unmodified
`lib/memory/`. Scratch copies discarded after verification, never
committed, never touched the real files even transiently.

This is the same spirit as
[issue-57-fence-a2-close-contract-notes](issue-57-fence-a2-close-contract-notes.md)'s
"build a scratch copy with the fix deleted" pattern, generalized to a batch
of 4 unrelated bugs in one sitting instead of one.

## Argus scripts as a starting point, not a substitute

The task handed off 6 pre-written `argus_*.py` repro scripts in the
scratchpad (`argus_fresh_project_crash.py`, `argus_boot_gh_crash.py`,
`argus_phantom_fence.py`, `argus_open_issues_lie.py`, plus two unrelated to
this task: `argus_mute_rules_watchman.py`, `argus_health_archive_test.py`,
`argus_rules_crash_test.py`, `argus_rules_newline_test.py` -- belonged to a
different, parallel Ultron/Cerberus/Argus round on `rules.py`/`health.py`
coherence_rules, not this task's 4 bugs). Running the 4 relevant ones first
against the REAL `lib/memory/` confirmed each fix already works and showed
the exact shape of the fixed output (e.g. `verify_phantom2.py`, a variant
of `argus_phantom_fence.py` with `boot.render()` added, showed the
restriction reappearing in `summary.restrictions` AND being named in
`index_discrepancies` in the SAME run -- that's what told me bug 3's "fix"
is naming, not suppression, before writing a single test line). The scripts
are throwaway repro tools, not tests themselves -- don't copy their asserts
verbatim into pytest; they don't follow this repo's `tmp_repo`/`_cwd`/
`make_note`/`make_context` fixture conventions and don't get cleaned up.

## Round 3 (D-044/D-045) — boot.py COUNTS label rename after --issue opened to all seven types

Task: bounded contract change, tests-only. `--issue` was just opened from
M-only to all seven note types (D-044/D-045). Consequence: `boot.py`'s
COUNTS block label "plans with a record" (`boot.py:381`, `open_issues`
computed at `boot.py:215` as distinct issue numbers across live/unarchived
notes) no longer describes what the number measures — an incident (I) or
a discard (X) with `--issue` now also counts, not just a memo (M) acta.

**What changed**: renamed
`test_boot.py::test_recuentos_label_says_planes_con_acta_not_issues_abiertas`
to `test_recuentos_label_says_issues_with_a_live_note_not_issues_abiertas`.
Swapped the two positive assertions from `"plans with a record" in
rendered` to `"issues with a live note" in rendered` (before AND after
archiving). Updated docstring and failure messages to explain the new
reason.

**What did NOT change, on purpose**: the negative assertion `"issues
abiertas" not in rendered` — this is Argus's 2026-08-02 invariant (the
number never asks GitHub, can lie "0" with a real open issue or "1" with
one closed months ago) and stays untouched in both before/after blocks.
Also untouched: the archive-then-recount-to-0 mechanic itself (still
`indexes.remove()` + `indexes.archive()`, still checks `open_issues == 0`
locally without touching GitHub) — this test still seeds only an M-type
note with `issue=47`, since the seven-type opening (`--issue` on other
types) is a SEPARATE contract (`test_note_issue_field.py`, see
[[note-issue-field-seven-types-contract-notes]]) not yet implemented in
production. Confirmed RED for the right reason: production still prints
`plans with a record`, assertion fails on the new label string, not on
`open_issues` count or the "issues abiertas" guard.

Verified: `unmassk-toolkit/tests/memory` — 488 passed, 1 skipped, 1 failed
(this test, RED as intended). No production file touched.

**Reminder to self**: nearly overwrote an unrelated existing memory file
(`pending-next-cutoff-contract-notes.md`) with a Write() typo/placeholder
mid-task — caught immediately via `git diff --stat`, restored with `git
checkout HEAD -- <path>` (safe: file was clean/tracked, no uncommitted
work lost) before writing this note under its own correct filename.
Always `git status`/`git diff` an agent-memory file right after any Write
to it, before moving on.

## Round 4 (2026-08-24) — a real corrupted .git/objects loose object must not crash the whole boot report

Session 2026-08-24, `tests/memory/test_boot.py`. Task: pin a KNOWN bug
(Yoda) -- `query.show_file_at_head()`/`query.by_zone()` can raise
`RuntimeError` on a real git failure, and that exception used to climb
uncaught through `health.coherence_rules()` -> `health.build()` ->
`boot.build()`, replacing the ENTIRE boot report with
`bin/memory/boot.py::_leave_a_failure_marker`'s failure banner (Next,
blockers, restrictions, everything -- gone, for a fault in ONE check).

**The surgical corruption technique -- reusable for any future
"real git failure, not simulated" contract in this project:** don't
delete or touch `HEAD`/refs. Resolve the real blob SHA for the file
under test (`git rev-parse HEAD:<relpath>`), locate its loose object
(`.git/objects/<sha[:2]>/<sha[2:]>`), `chmod(0o644)` (loose objects are
written read-only) and overwrite its bytes with garbage. Verified live
in a disposable repo before writing the test: `git cat-file -e
HEAD:<relpath>` (existence-only check) STILL returns `returncode == 0`
after this corruption -- git's `-e` flag apparently doesn't need to
fully inflate the object to answer "does it exist" for a tree-resolvable
path -- while `git show HEAD:<relpath>` (content read) fails for real
with `error: inflate: data stream error (incorrect header check)` /
`fatal: loose object <sha> ... is corrupt`. `git log --oneline` is
UNAFFECTED (log never reads blob content, only commit metadata). This
is exactly the shape of `query.py`'s two-step design
(`_exists_at_head()` via `cat-file -e`, then `show_file_at_head()`'s
`git show` only if existence said yes) -- and exactly why THIS
corruption reaches the `RuntimeError` branch instead of the silent
`_exists_at_head() -> False -> ""` early-return: a corrupted object
still "exists" by the cheap check, so the code proceeds to actually
read it and hits the real failure. A vaguer corruption (deleting the
object file entirely) would have been swallowed silently instead --
picking the RIGHT corruption for the RIGHT crash mattered here.

**Why this test isolates ONLY the rules-coherence check, not the whole
boot pipeline:** corrupting `rules.md`'s blob leaves `git log` (used by
`query.by_zone()`/`by_id()` for every note read, both in `boot.build()`
directly and inside `health.coherence()`) completely untouched -- so a
note seeded AFTER the corruption still writes and renders normally
(restrictions/blockers/COUNTS stay real). Only `health.coherence_rules()`
-> `query.show_file_at_head()` touches that specific blob. This produced
a much sharper contract than "corrupt everything and hope for a generic
warning": the test asserts the OTHER two CHECKS lines (duplicate IDs,
index coherence) stay real and correct, proving the degrade is scoped to
the one check that actually failed, never a blanket "something broke,
who knows what" message.

**Ground truth for the expected git-error text, never hand-typed
[unmassk-standards Sec.34]:** the corruption helper fires its OWN probe
(`git show HEAD:<relpath>` against the just-corrupted object) and
returns that REAL stderr; the test's final assertion takes the last
line of THAT captured text (`real_git_error.strip().splitlines()[-1]`)
and checks it's a substring of the rendered report -- same technique
lineage as [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)'s
"probe fires a second real git op against the same broken state and the
test compares against ITS stderr", generalized from `index.lock` staging
failures to a corrupted loose object.

**Multi-agent concurrency turned this RED test GREEN mid-session, by
design (test-first mode, "Ultron lo arregla en paralelo"):** the first
run (right after writing the test) crashed with the real uncaught
`RuntimeError` from `query.py:281`, confirming RED for the right reason.
A later run (same test, unchanged) passed clean -- `git status
--porcelain` showed `health.py`/`boot.py`/`query.py` had picked up
uncommitted edits mid-session (a new `HealthReport.rule_discrepancies_error`
field, `health.build()` wrapping `coherence_rules()` in `try/except
RuntimeError` exactly like it already did for `plans_unreflected()`, and
`boot._avisos_block()` printing "no se pudo comprobar si las reglas
coinciden con git: <error>" instead of a fabricated "rules match git").
Confirmed the fix landed for real (not a fluke) by rerunning 3x more,
all green, and by reading the actual diff -- Ultron's wording matches
the contract's assertions almost verbatim. **Lesson: in this repo's
current phase (heavy parallel agent activity, several unrelated
in-flight refactors uncommitted at once -- I-003 rules.py split, D-054
textnorm, this git-corruption fix, notes_commit/zones.py consolidation
-- all landed in the SAME working tree during ONE session), `git status
--porcelain -- lib/memory/` before drawing any conclusion about "is this
still red" is mandatory, not paranoia -- the ground under a test can
shift while you're still writing assertions for it.**

**Live safety incident, corrected before any harm -- worth repeating
verbatim for the next session:** the FIRST attempt to build a disposable
corruption-probe repo used `cd "$SCRATCH/.../repo"` followed by several
`git ...` commands with no explicit target, inside a SEPARATE Bash tool
call from the one that created the directory. The `cd` failed silently
("no such file or directory" -- the directory from the prior call never
actually persisted, matching this project's own documented rule that
"Agent threads always have their cwd reset between bash calls"), but the
script kept running anyway and every subsequent `git`/`echo > objpath`
command executed against THIS repo's real `cwd` instead -- including an
attempted `echo -n "garbage" > .git/objects/<sha>/<rest>` targeting the
REAL toolkit's own `rules.md` blob. It failed only because git objects
are written read-only (`chmod 444`) and the write hit `Permission
denied` before any byte changed -- confirmed after the fact with `git
status --porcelain` (only pre-existing dirty files, no diff on
`rules.md`) and `git fsck` (only ordinary dangling objects, no corruption
reported). **Fix applied for the rest of the session and going forward:
never rely on a bare `cd` + subsequent bare `git ...` inside a
disposable-repo script. Use `git -C "$WORK" ...` (or an explicit
absolute path per command) for EVERY git invocation against a scratch
repo, and add an explicit `[ "$(pwd)" = "$WORK" ] || exit 1` guard before
any write that touches `.git/objects` by hand** -- a destructive
operation must name its target explicitly, never trust an implicit `cd`
that might not have taken effect.

**Point 2 of this same task (verify Ultron's notes_commit/notes
consolidation + zones.py split leave the suite untouched) --
confirmed, no isolated "before" run possible:** both refactors were
already applied (uncommitted) in the working tree by the time I reached
this part of the task, done in parallel per instructions -- with no
`git stash`/`reset` allowed on unstaged work, there was no way to get a
true isolated "before" snapshot. Verified instead via: (1) `git diff
--stat` on `tests/memory/test_notes.py` (99 insertions, 0 deletions --
pure addition) and `test_zones.py` (only a D-054-unrelated addition
block + one import line, zero deletions tied to the zones split itself)
-- neither refactor rewrote or removed a single existing test; (2)
`zones.py` shrank 311 lines while three new siblings
(`zones_commit.py`/`zones_load.py`/`zones_query.py`, 130+88+78=296
lines) appeared, consistent with a facade split, not a rewrite; (3) full
suite `1184 passed, 2 skipped, 0 failed` (`unmassk-toolkit/tests -q`,
~150s) both right after and in a repeat run -- stable, not flaky; (4)
`test_boundary.py` (the module public-symbol-surface guard) green,
confirming the split didn't leak or drop a public symbol. One genuine
test-coverage gap WAS found and already closed by someone else in
parallel before I got to it:
`test_notes.py::test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree`
-- the shared `stage_and_commit()` "hook rejects mid-commit, index must
end up fully clean" regression previously had only ONE test in the whole
suite (via `rules.py`), never through `notes.write()`, one of
`stage_and_commit()`'s three other real callers. Its own comment credits
"auditoria de mutaciones, hallazgo real, relayado por el coordinador" --
this was NOT something I needed to add; verified it already existed and
passes.

Verification commands used: `python3 -m pytest
unmassk-toolkit/tests/memory/test_boot.py -k corrupted_git_object -q`
(RED then GREEN, see above); `python3 -m pytest
unmassk-toolkit/tests/memory/test_notes.py
unmassk-toolkit/tests/memory/test_zones.py
unmassk-toolkit/tests/memory/test_boundary.py -q` (62 passed); full
`unmassk-toolkit/tests -q` (1184 passed, 2 skipped).

See also: [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)
(the `index.lock` sibling of this same "real git failure, never
simulated" family) and [health-contract-notes](health-contract-notes.md)
(the `gh`-failure isolation precedent `plans_unreflected_error` that
`rule_discrepancies_error` mirrors almost verbatim).

## Round 5 (2026-08-26): `BootSummary.issues` field + its COUNTS render, new dedicated file

Linear-mode Verify pass, production already implemented (`model.py`'s
`BootSummary.issues: tuple[Note, ...] = ()`, `boot.py`'s `build()`
computing it and `_recuentos_block()` printing
`f"      - issue #{note.issue}: {note.headline}"` per note, sorted by
`(issue, id)`, D-060/D-064's "Issues" opening-menu row needing to list
them one per line). New file
`tests/memory/test_boot_issues_field.py` (3 tests) rather than
extending `test_boot.py` -- same convention as `test_note_issue_field.py`/
`test_work_issue_field.py`/`test_report_render_issue_field.py`: a new
field/surface around `issue(s)` gets its own file, never folded into the
module's original contract file. All the usual `boot`/`model`/`indexes`/
`notes`/`make_note`/`make_context`/`_cwd` fixtures are DUPLICATED locally
per this project's established rule (repeat per file, never share via
conftest for anything beyond the bare module-import helper) -- confirmed
by checking `test_health_rules_coherence_contract.py` as the precedent
before writing.

**Gotcha caught only by running, not reading**: assumed the line right
after the COUNTS counter would be `❓ OPEN QUESTIONS ....  C E R O` when
there are zero issues. Wrong -- `_named_block()` always prepends its own
leading blank line before any titled block (pre-existing behavior, not
part of this change), so the real sequence is counter -> blank -> the
questions header. First draft asserted `counts_index + 2` directly
against the header text and failed; fixed to assert the blank line at
`+2` and the header at `+3`, with a comment explaining that blank line
is the pre-existing separator, not an "extra line" the contract's item
(2) is about.

**RED-with-broken-logic proof**: reimplementing `_recuentos_block()`
inside the permanent test file was rejected (production logic duplicated
inside a test = banned) exactly like Round 3 of the `gh`-PATH file. Ad
hoc script (scratchpad, never committed) imported the real modules,
`pytest.MonkeyPatch().setattr(boot_mod, "_recuentos_block", <broken>)`
with TWO independent broken variants -- order (`reversed(summary.issues)`
instead of the real sorted tuple) and format (`issue {n}` instead of
`issue #{n}`) -- then called the permanent test's own method object
directly against each. Both went RED through the exact same assertion
(`_issue_lines(rendered) == expected_lines`), and a third unpatched
control run in the same process stayed GREEN afterward, confirming
`mp.undo()` left no residue between the two monkeypatch scenarios.

Verified: new file green ×3 (3/3 each, 9/9 total), together with
`test_boot.py` (17/17), full `tests/memory` suite (598 passed, 1
skipped, no regression from the new fixtures/module-level state). No
production file touched (`git status` on `lib/memory/boot.py`/`model.py`
empty throughout).

## Round 6 (2026-08-26): House's diagnosis, autocrlf reprocessing a corrupted blob on unrelated commits

Windows CI red on
`test_boot_survives_a_real_corrupted_git_object_and_warns_about_the_rules_check`
-- House diagnosed and reproduced byte-for-byte on macOS BEFORE handing
this off: with `core.autocrlf=true` (Git for Windows' default), `git
add` rereads the INDEX blob content of any entry whose `stat` isn't
trustworthy (same-second mtime -- what a fast fixture always produces)
to decide line-ending conversion. The test's own premise comment
("commit de una nota nueva no toca el objeto de rules.md") only holds
without `autocrlf` -- with it, ANY later commit, including one that
never touches `rules.md`, rereads its already-corrupted blob and dies
with the same "inflate: data stream error" the test deliberately
produced. Confirmed T3/no-defect: production already fails loud via
`WriteResult.git_error` -- this is a test-fixture gap, not a `lib/memory/`
bug.

**Cross-checked, not trusted blind**: reproduced the exact failure AND
the exact fix locally (macOS, `core.autocrlf=true` forced on a
throwaway repo) before touching the real test -- 3-way A/B/C script
(no autocrlf: OK: with autocrlf, no exemption: FAILS with House's exact
stderr; with autocrlf + exemption: OK again), plus a standalone check
that `git show HEAD:rules.md` still fails identically AFTER the
exemption (the fix doesn't repair or mask the corruption the test
needs).

**Fix**: `_exempt_path_from_autocrlf_reprocessing(root, relpath)`, new
helper right after `_corrupt_head_blob_for_path` (same natural home),
writes `.git/info/attributes` (never `.gitattributes` -- that's tracked
and would change the REAL behavior R-014 watches) marking `rules.md`'s
relpath `-text`, called in the test body BEFORE `rules.add()` so the
exemption is live from the very first commit onward. `autocrlf` stays
live for every other path -- doesn't mask the class of bug R-014 exists
to catch, only removes this one fixture's false premise.

**Verifying a Windows-only path without Windows, closing the loop both
ways**: `.__wrapped__` unwraps a `@pytest.fixture`-decorated function
for direct calling outside a pytest session (confirmed live: calling
the fixture directly without `.__wrapped__` raises pytest's own
`Failed: Fixture "X" called directly`). Ran the REAL, unmodified test
function (never reimplemented) against a `tmp_repo` built with the same
steps as the real fixture plus `core.autocrlf=true` forced -- passed.
Then a negative control: `pytest.MonkeyPatch` neutralizing
`_exempt_path_from_autocrlf_reprocessing` to a no-op, same autocrlf
scenario -- failed at the EXACT assertion House named ("comprobacion
previa: sembrar una nota real tras la corrupcion"), with the identical
stderr fragment. Proves the exemption specifically, not something else,
is what makes it pass.

Verified: real test green ×3 in the actual repo config (no autocrlf,
matching macOS/Linux CI), `test_boot.py` green ×3 (14/14 each), full
`tests/memory` suite (598 passed, 1 skipped, no regression). Only
`test_boot.py` touched (`git status` confirms). Declared
UNVERIFIED-en-Windows for the real CI run itself (filesystem specifics
of a real Windows runner remain unexercised here) -- the mechanism and
the fix are executed evidence, the actual `windows-latest` pass is not.
