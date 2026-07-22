---
name: issue-61-gc-race-fixture-corruption-notes
description: issue #61 reabierto — House root cause (git gc --auto fork race on Ubuntu CI corrupts massive-commit fixtures), conftest-level fix + fsck probe pattern
metadata:
  type: project
---

## Root cause (House, confirmed byte-for-byte)

Different from every earlier #61 round (all about tests swallowing rc /
not retrying). This one is real on-disk fixture corruption: massive
`git commit`/`git fetch` loops (200-510 commits) auto-trigger
`git gc --auto`. On Ubuntu CI, `gc.autoDetach` forks that gc into the
background, racing the object-DB under ext4 + the runner's parallel I/O —
occasionally losing a reachable parent commit object. A later
`git log --all --grep=...` (recall/consolidation) then dies rc=128
("Could not read <sha>" / "Failed to traverse parents of commit <sha>").
The 3 read-retries from the earlier #61 round can never recover this,
since the wrapper just re-reads the same already-broken repo 3 times.
Windows never reproduces (can't fork gc); macOS-local never reproduces
(no repack mid-loop). commit-graph was investigated and ruled out.

## Fix shape: config injection at the ONE chokepoint, not per-fixture

`_GC_DISABLE_ENV` dict in `unmassk-toolkit/tests/conftest.py` (right
after `_DEFAULT_GIT_IDENTITY_ENV`), merged into `run_cmd()`'s env at
lowest precedence: `{**identity_defaults, **_GC_DISABLE_ENV, **os.environ,
**(env or {})}`. Uses `GIT_CONFIG_COUNT=3` + `GIT_CONFIG_KEY_n`/
`GIT_CONFIG_VALUE_n` (git >= 2.31, confirmed on Apple Git 2.50.1) for
`gc.auto=0` (kills the trigger from both `git commit` and `git fetch`),
`gc.autoDetach=false`, `maintenance.auto=false` — belt and suspenders in
case something else ever triggers a gc for real, it must run in
foreground, not forked.

**Why this covers the whole #61 family for free**: every fixture builder
checked (`test_recall.py::_make_repo`/`_commit`, `test_consolidation_
trigger.py::_make_bare_repo`/`_commit_empty`, `test_drift.py::build_
history` and all its `gen_*` helpers) routes through `git_cmd()` →
`run_cmd()` — confirmed by grep + read, not assumed. No fixture in this
family bypasses `run_cmd` with its own raw `subprocess.run`. This is the
same "single chokepoint" pattern already used for the git-identity fix
(see [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)'s
"hermetic-runner git identity" entry) — confirmed no test file sets
`gc.auto`/`GIT_CONFIG_COUNT` itself (grepped clean), so no coexistence
tracking (like `_REPOS_WITH_EXPLICIT_GIT_IDENTITY`) was needed — always
inject unconditionally.

## fsck probe pattern — fail loud if it ever reappears

New `assert_repo_integrity(repo, context="")` helper in conftest.py:
`git fsck --connectivity-only`, assert rc==0, message prefixed literally
with "fixture corrupto (objeto ausente)" plus rc/stdout/stderr. Wired in
right after building history, BEFORE the test's main assertion, at 3
sites: `test_consolidation_trigger.py::test_07_long_history_counts_
correctly` (300 commits), `test_recall.py::TestFullHistoryHorizon::
test_entry_beyond_500_commits_is_found` (510-commit pad), and
`test_drift.py::drift_repo` fixture itself (module-scoped, 200 commits —
covers `test_deep_search` and every other test sharing that fixture in
one call instead of repeating the probe per-test).

**Mutation-checked live** (not just written): built a throwaway healthy
repo — probe passes. Then manually deleted a reachable parent commit's
loose object file (`.git/objects/<sha[:2]>/<sha[2:]>`) after a 2nd
commit, confirming `assert_repo_integrity` raises with the exact expected
message AND real `git fsck` diagnostic text ("broken link from commit...
missing commit...") — reproduces House's exact failure shape. Also
confirmed live that the 3 injected git configs actually take effect
inside a `run_cmd`-spawned subprocess (`git config --get gc.auto` →
`'0'`, etc.), not just present in the env dict unused.

## Honesty caveat — local green does NOT validate the fix

The bug is Ubuntu-CI-only (fork-based gc race under parallel I/O
pressure); it has never reproduced on this local macOS box. Running
`test_consolidation_trigger.py test_recall.py test_drift.py test_
hardening_recall.py` green locally (101/101, real exit code 0, all 4
files individually green too) proves the fix doesn't regress anything —
it does NOT prove the fix actually prevents the CI-only corruption. That
can only be confirmed by an actual Ubuntu-CI run of the full suite.
`test_hardening_recall.py` was checked and correctly excluded from the
fsck-probe sites — its own commit loops never exceed `range(3)`, not part
of the massive-history family.
