---
name: boot-report-argus-four-regressions
description: memoria-v2 boot.py/report.py/health.py -- 4 Argus-confirmed-fixed bugs turned into regression tests (fresh-project crash, gh-failure isolation, phantom-fence naming, open_issues label), plus the scratch-copy mutation-check technique used when lib/memory is off-limits
metadata:
  type: project
---

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
