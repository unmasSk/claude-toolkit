---
name: memoria-v2-freshness-retirement-notes
description: Retirement of the multi-machine boot-freshness (#49/#60) and issue #61 memory-read-path test families on feat/memoria-v2 — what died, what was salvaged, and the new-boot-no-longer-fetches gotcha
metadata:
  type: project
---

## What happened

Memory v2 (`docs/memoria-v2/PLAN-CONSTRUCCION.md` §5.3) deleted
`lib/recall.py`, `lib/boot_memory.py`, `lib/boot_glossary_cache.py` entirely,
removed `boot_git_checks.fetch_memory_ref()`/`render_memoria_stamp()`/
`check_upstream_shares_history()`/`_has_toolkit_memory()`/`_ASKPASS_FAILFAST`,
removed `git_helpers.commits_since_last_consolidation()`, and retired the
`hooks/precompact-snapshot.py` hook and `bin/git-memory-commit.py`'s
`_check_behind_warn_only()`. This broke collection on 5 test files (multi-
machine "boot freshness" #49/#60 was declared out of scope by design — "el
propietario trabaja en una máquina a la vez").

**Retired** (3 files, ~4318 lines): `test_boot_freshness.py`,
`test_boot_freshness_hardening.py`, `test_boot_freshness_regression.py`.
**Salvaged into** `unmassk-toolkit/tests/test_boot_git_checks.py` (34 tests):
everything still exercising `boot_git_checks.get_ahead_behind()`,
`_build_pull_directive_lines()` (both still called from
`render_branch_section()`, part of the boot's non-memory BRANCHES section),
`time_ago()` (still used by `get_timeline()`/`get_remote_branches()`), and
`git_helpers.run_git()`'s `env=` kwarg, `log_stderr_on_failure=` kwarg, and
POSIX/Windows process-group kill-on-timeout (none freshness-specific —
`run_git()` is the general-purpose subprocess wrapper).

**Retired** (2 files, ~1818 lines): `test_issue61_breadcrumbs.py`,
`test_issue61_read_retry_contract.py`. **Salvaged into**
`test_read_retry_contract.py` (17 tests): everything exercising
`git_helpers.run_git_read_retrying()` itself (SEC-HIGH-001 clock-deadline
logic) plus its 3 still-live call sites — `boot_git_checks.get_timeline()`,
`boot_git_checks.get_last_context_time()`, `bootstrap_commits.
scan_recent_commits()` (2 internal calls). `commits_since_last_
consolidation()` is confirmed gone too (grepped, zero hits anywhere) — do
NOT resurrect a test for it without confirming it's back in production
first.

## Judgment calls made (both explicit in the report, not silent)

- `TestDivergenceShowsBothSidesLabeled` (old freshness file) mixed a live
  assertion (`"[1/2 vs upstream]"` ahead+behind indicator) with dead ones
  (remote-labeled memory "Next" item). Rather than drop it wholesale, added
  a new unit test to `TestGetAheadBehind` —
  `test_real_ahead_and_behind_counts_simultaneously` — since NO existing
  test anywhere covered `get_ahead_behind()` with both ahead>0 AND behind>0
  at once. Don't just delete a mixed test outright when the live half plugs
  a real coverage gap — extract it as a new, focused test instead.
- `TestRunGitReadRetryingDeadline` had 4 tests; one
  (`test_hanging_read_bounded_to_one_attempt_at_site_level`) drove through
  `boot_memory.extract_memory()` (dead) purely as an integration proof —
  dropped, kept the other 3 (pure helper-level, no dependency on any
  specific site).

## Gotcha: v2's boot hook no longer fetches at all

`hooks/session-start-boot.py` used to run an unconditional `git fetch
--quiet` before the freshness work even existed, and the v1 freshness
system added its own gated fetch on top. **Both are gone in v2** — the boot
hook never calls `git fetch` anymore. Consequence: any test that drives
"behind" detection through a REAL boot subprocess (not a direct
`get_ahead_behind()` call) must explicitly `git fetch origin` in the test's
OWN setup before invoking the boot hook, or `refs/remotes/origin/<branch>`
stays stale at whatever it was after the last real push from that clone —
`render_branch_section()` will report `[0/0 vs upstream]` even though the
remote has diverged. Bit `TestPullDirective` in the new
`test_boot_git_checks.py` on the first run; fixed by adding the fetch call
to `_setup_behind()`. Same discipline `TestGetAheadBehind`'s own direct-call
tests already used — just wasn't obvious it also applied to the
real-boot-subprocess style tests until this run proved it.

## Confirmed dead code NOT touched (out of scope, flagged only)

`lib/boot_fetch_stamp.py` (357 lines) is fully orphaned — zero importers
anywhere in `lib/`/`bin/`/`hooks/` (confirmed via grep), only referenced in
its own docstring and in comments of files that also got trimmed this pass.
Production code is Ultron's territory, not deleted here — worth a heads-up
next time someone touches that area.

## Verification this pass

`python3 -m pytest unmassk-toolkit/tests --collect-only -q` → 792 collected,
0 errors (was 741 collected + 5 errors). Full real run (`python3 -m pytest
unmassk-toolkit/tests -q`, no pipe, ~161s) → 128 failed, 659 passed, 1
skipped, 4 errors — **zero of those are in the 2 new files** (confirmed via
`grep "^FAILED" | grep -E "test_boot_git_checks|test_read_retry_contract"`,
empty). The 128 failures + 4 errors are pre-existing breakage in OTHER
files never touched this pass (`test_boot_output.py`, `test_managed_
blocks.py`, `test_hardening_recall.py`, `test_user_prompt_skill_router.py`,
`tests/memory/test_vocabulary.py` — the last one is a known test-first RED
contract per [vocabulary-contract-notes](vocabulary-contract-notes.md), not
a regression) — same wider v1→v2 migration debt class, out of scope for
this task, first time the full suite could even collect far enough to
surface them.
