---
name: dead-script-retirement-sweep-notes
description: Technique for finding/retiring ALL tests invoking a deleted bin/*.py script, not just the ones named in the task — module-scoped fixture safety, conftest constant cleanup, false-pass gotcha
metadata:
  type: feedback
---

Task named 3 failing tests tied to one deleted script
(`bin/git-memory-uninstall.py`) but explicitly asked to also check the
other 4 scripts §5.4 of `docs/memoria-v2/PLAN-CONSTRUCCION.md` declares
dead (`bin/git-memory` bash alias, `-bootstrap.py`, `-gc.py`,
`-upgrade.py`). **The named 3 were the tip of the iceberg** — a full
`conftest.py`-constant grep (`GC`, `UPGRADE`, `BOOTSTRAP`, `UNINSTALL`
used as whole words, excluding comment prose) found 2 whole dead files
(`test_bootstrap.py`, `test_upgrade.py`) and 5 more individual tests
scattered across `test_integration.py`, `test_atomic_claude_md_write.py`,
`test_file_lock_regressions.py` — none named in the task, all failing
with the identical `rc == 2 / FileNotFoundError` signature. **Lesson:
when a task names "a few tests, and check for more of the same," grep
every constant/path the named tests import, not just the literal test
names given — the report that spawns the task is very rarely exhaustive.**

**Verification-before-deletion discipline that mattered here:** before
retiring anything, confirmed via `git ls-files` that the 5 dead scripts
are genuinely untracked (not mid-deletion by another agent working in the
same repo concurrently) and confirmed `git status --short` showed the
target test files themselves as clean (not being edited by someone else
right now). Both checks are cheap and prevent stepping on concurrent
agent work — this session had ~40 other files modified in the working
tree by parallel agents at the same time.

**Module-scoped-fixture reasoning before deleting a test mid-sequence:**
`test_lifecycle.py`'s `lifecycle_repo` fixture is `scope="module"`, tests
share state and run in file-definition order. Deleting `test_uninstall`
(which sits between `test_repair_missing_claude_md_block` and
`test_doctor_after_uninstall`) looked risky — `test_doctor_after_uninstall`
asserts `status != "ok"`, an assertion that reads as if it depends on a
real prior uninstall having happened. **Resolved by noting the failing
test was already a no-op on the filesystem**: `run_uninstall()` calls the
dead script, `run_script()` returns `rc=2` from a subprocess that raised
`FileNotFoundError` before executing ANY production logic — so the shared
fixture's on-disk state is byte-identical whether the test exists-and-
fails-at-its-own-`assert rc==0`-line, or is deleted outright. Verified by
actually running the file after deletion rather than trusting the
theory — same pass/fail outcome, confirmed. **General rule: before
deleting a test from a sequence sharing mutable fixture state, trace
whether the deleted test's body actually mutated anything before its
failure point — a test that fails at its FIRST assertion, calling a
process that never launched, has zero side effects to lose.**

**Found-but-not-fixed gotcha, reported not touched (respecting "only
retire what's asked"):** `test_managed_blocks.py::TestUninstallFourBlocks
::test_uninstall_preserves_user_content` invokes the same dead
`UNINSTALL` script but never asserts on the returned `rc` — only checks
that user text survives. Since the dead-script call is itself a no-op,
the file is never touched, so the assertion passes for a reason that has
nothing to do with uninstall actually running. Left as-is (not in the
literal failing set, fixing it would be scope creep into test-quality
judgment beyond mechanical retirement) but flagged with a code comment
at the retirement site and in the final report — this is the kind of
"vigilante silencioso" pattern (a check that can never fail is
indistinguishable from no check) worth surfacing even when out of scope.

**Cleanup order that avoided churn:** (1) confirm which test bodies
actually invoke the dead path (grep `run_script(NAME`, `NAME!r` in an
f-string, or a bare path join using the script's literal filename — 3
different call shapes seen across files), (2) delete only those
functions/classes, (3) THEN grep the file's remaining body for the
now-possibly-unused import names (`SOURCE_ROOT`, `UNINSTALL`, `UPGRADE`,
`BOOTSTRAP`, plus any test-local helper like `_manifest_path()`/
`_run_uninstall_auto()` that existed only to serve the deleted test), (4)
finally check the shared `conftest.py` constants themselves for
zero-consumers-left-anywhere-in-tests/ before deleting them there too.
Working top-down (constant before checking usage) causes false "still
needed" conclusions; working bottom-up (usage first, constant last) does
not.

See also: [gitto-retirement-test-mapping-notes](gitto-retirement-test-mapping-notes.md)
(same "read the docstring/plan for the retirement breadcrumb" family, and
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
for the general importlib/subprocess conventions used across this repo's
retirement passes.
