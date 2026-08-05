---
name: v1-guard-changeover-2026-08-05-notes
description: v1 memory-system final deletion pass (8 files + boot_health.py reduction) — mixed-file surgery beyond the given list, "reapuntar not borrar" pattern for still-mandatory behavior that moved hooks
metadata:
  type: project
---

Retirement pass after 8 v1 files were deleted outright (session-start-boot.py,
pre-validate-commit-trailers.py, stop-dod-check.py, git-memory-commit.py,
boot_checks.py, boot_git_checks.py, boot_render.py, boot_migrations.py) plus
boot_health.py reduced to 3 survivors (CACHE_BASE_DIR, _md5_file,
_latest_version_dir). See [v1-retirement-batch-notes](v1-retirement-batch-notes.md),
[dead-script-retirement-sweep-notes](dead-script-retirement-sweep-notes.md) for
the earlier rounds of the same migration.

**The orchestrator's own pre-classified list had errors — verify every file by
running it, never trust the category.** `test_plugin_sync_boot_line.py` was
handed to me as "pure v1, delete" but it imports `cache_sync_check` (live)
alongside `boot_render` (dead) — turned out 100% dead anyway (cache_sync_check
was only ever a monkeypatch dependency, its own behavior asserted nowhere in
that file), but I had to actually trace every assertion to be sure, not take
the label at face value. Conversely `test_pre_validate_hook_actually_fires.py`
(handed to me as fully deletable) had a live class
(`TestSuiteDoesNotInheritTheMarkerFromTheShell`) testing conftest.py's own
`run_cmd`/`claude_env` env-removal channel — nothing to do with the dying
hook. Salvaged into `test_conftest_env_removal_channel.py` before the
orchestrator's parallel deletion pass reached that file (lucky timing, not
lucky guessing — I'd already read the file body before the delete-notice
arrived).

**Whole-module deletion (not just function removal) invalidates prior
salvage files too.** `test_boot_git_checks.py` was itself a PRIOR salvage
file (from the #49/#60 freshness retirement, see
[memoria-v2-freshness-retirement-notes](memoria-v2-freshness-retirement-notes.md))
that assumed `lib/boot_git_checks.py` the MODULE would survive with only
specific functions removed. This pass deleted the entire module. Result:
10 of 14 classes in that salvage file died (everything calling
`boot_git_checks.*` directly), but 4 classes
(`TestRunGitEnvKwarg`, `TestRunGitLogStderrOnFailure`,
`TestPosixProcessTreeKillOnTimeout`, `TestWin32ProcessTreeKillOnTimeout`)
only ever called `git_helpers.run_git()` — never touched `boot_git_checks`
at all despite living in that file. Moved verbatim to
`test_git_helpers_run_git.py`. **Lesson: a salvage file's own docstring
claim ("this module survives, only X/Y/Z died") is a snapshot, not a
guarantee — re-verify the base module's existence on every subsequent
retirement pass, don't trust the last salvage file's framing.**

**"Reapuntar, no borrar" — when the orchestrator says a behavior is still
mandatory but its host hook died, the fix is redirecting to the real
successor, never deleting the test.** Two cases this pass:
1. `test_plugin_sync_boot_line.py`'s "explicit zero, never silence" P6
   contract for the PLUGIN: sync line moved from
   `boot_render._render_plugin_sync_line()` (dead, pure function with a
   return value) to `hooks/session-start-crew.py::_print_plugin_sync_check()`
   (print-only, no return value) — redirected via real end-to-end subprocess
   runs (matching this codebase's established convention for testing
   hyphenated hook files, see `test_session_start_crew.py`) into
   `test_crew_plugin_sync_line.py`. A print-only successor with no pure
   function to unit-test directly means the test file HAS to go
   end-to-end; don't force a fake unit-test shape onto it.
2. `test_pre_validate_commit_trailers_git_log.py`'s BUG C regression
   (a naive `\bgit\b.*\blog\b`-style regex blocking `cat git.log`,
   `echo 'git log info'`, `git log-remote origin` — commands that only
   MENTION git/a subcommand word without invoking it) had no successor
   in the literal sense (the new hook, `hooks/customs.py`, doesn't even
   gate on `git log`) but the STRUCTURAL LESSON (position-aware token
   detection, never substring matching) fully transfers to
   `customs.py::_find_commit_creating_statement()`'s own commit/merge/
   rebase/cherry-pick detection. Wrote the equivalent false-positive
   cases (`cat git-commit.log`, `echo 'git commit -m test'`,
   `git log --grep=commit`, `git remote show origin`) against the real
   successor in `tests/memory/test_customs_hook.py`, plus one
   anti-vacuity control (same fixture, a real unrecognized-note commit
   that MUST still block) proving the four approvals aren't just "nothing
   ever blocks in this fixture."

**Before writing new coverage for "does X move to Y", check if it's
already covered live.** `TestGitMemoryCommitPathFlag` in `test_release.py`
tested a `--path` flag on the deleted `bin/git-memory-commit.py`, whose
whole PURPOSE (per its own docstring) was letting `release.py` avoid
`git reset`. Grepped `bin/release.py` and confirmed it no longer calls
that wrapper at all — it calls `notes.write_work()` directly. The exact
behavior contract (no bystander-staged-file leak into the release commit,
bystander stays staged after) was ALREADY covered, green, against the
REAL current mechanism, by `TestBystanderRemainsStaged` in the same file.
Deleted the dead class outright rather than manufacturing a redirect
nobody needed — redirecting is for behavior that's still uncovered
elsewhere, not a reflex for every retired class.

**A "no config value in the exempt set" cleanup can be a no-op that's
still worth doing.** `test_doctor_derived_expectations.py`'s
`DELIBERATELY_UNWIRED` set subtracted 3 hook names from `os.listdir()`'s
result — since those 3 hooks are now genuinely absent from disk (not
merely present-but-unwired, which was the ORIGINAL premise the set was
built for), subtracting them from a set that no longer contains them was
already a harmless no-op — the test passed with or without the fix. Fixed
it anyway because the comment ("siguen en disco a proposito") was
factually false and would mislead the next reader; removed the whole
exemption since nothing needs exempting once the files are gone, not
just unwired.

**Orphaned-but-undeleted shared infra found, not touched.**
`tests/_git_intercept.py` (subprocess.Popen patcher, built for the #60
freshness retirement) has ZERO current callers anywhere in `tests/`
(confirmed via grep for its own module name, `GIT_INTERCEPT_LOG_PATH`,
`make_intercepted_popen` — all empty). Its last consumers
(`test_boot_freshness.py` and siblings) were deleted in an earlier pass
without anyone removing this file too. Not deleted here — wasn't the
task, and "orphaned infra someone might still plan to reuse" is a
judgment call for whoever owns that decision, not a mechanical retirement.

See also [dead-script-retirement-sweep-notes](dead-script-retirement-sweep-notes.md)
for the general "grep every constant the named tests import, not just the
literal names given" technique, and
[gitto-retirement-test-mapping-notes](gitto-retirement-test-mapping-notes.md)
for "read the docstring/plan for the retirement breadcrumb" — both applied
again this pass.
