---
name: issue-63-t1-manifest-read-hardening-notes
description: issue #63 T1 regression tests (Argus SEC-T1-001 RecursionError + SEC-T1-002 dir-symlink bypass) across 3 manifest.json read sites, wip 5c9d012 — vacuity-driven forged-version choice per site, one-time manual mutation-check discipline
metadata:
  type: project
---

Regression file: `unmassk-toolkit/tests/test_issue63_manifest_read_hardening.py`
(7 tests, all real-channel: direct function calls in isolated subprocesses,
never via full-hook `--json`/stdout parsing). Covers 2 vectors × 3 read
sites fixed by Ultron in wip 5c9d012: `hooks/session-start-crew.py::
_manifest_version_matches`, `lib/boot_health.py::check_version_mismatch`,
`lib/upgrade_check.py::needs_upgrade`.

**SEC-T1-001 (RecursionError)**: payload is `"[" * 150000 + "]" * 150000`
(valid JSON, nested empty arrays) — confirmed live to raise `RecursionError`
(not `JSONDecodeError`) via `json.loads()` directly, well below Python's
default recursion limit (1000). A dedicated sanity test
(`TestMaliciousPayloadSanity`) pins this precondition so the other 3 tests
don't silently stop proving anything if a future CPython changes its
nesting-depth guard.

**SEC-T1-002 forged-version choice per site is NOT uniform "high version" —
deriving it wrong makes 2 of 3 sites vacuous.** Each of the 3 functions
compares the manifest's version differently, so a single generic "high
forged version" (the literal shape Ultron's own attack layout note
suggested) would pass identically whether or not `verify_path_within_project()`
guards the read, in 2 of 3 sites:
- `_manifest_version_matches`: checks EQUALITY with `VERSION` → only a
  forged version `== VERSION` can flip the result (False→True) if the
  guard is bypassed. A high/different forged version stays False either
  way — vacuous.
- `check_version_mismatch`: checks INEQUALITY with `PLUGIN_VERSION` → only
  a forged version `!= PLUGIN_VERSION` (e.g. a high/marked string) makes a
  bypass observable (None→a warning string embedding the forged content).
  An equal forged version stays None either way — vacuous.
- `needs_upgrade`: checks `manifest_tuple < code_tuple` (no-downgrade rule)
  → only a forged version LOWER than `PLUGIN_VERSION` makes a bypass
  observable (False→True, a spurious auto-upgrade trigger). A high forged
  version stays False either way — vacuous.

Verified all 3 differentials live via mutation (see below) — each forged
value was confirmed to actually flip the result when the guard line was
removed, not just assumed from reading the comparison logic.

**Mutation-check discipline: one-time manual verification via Bash +
Edit, NOT self-mutating pytest code committed to the suite.** Every prior
`unmassk-toolkit-python-test-conventions.md`/`issue-63-boot-simplification-
contract-notes.md` mutation-check entry describes this as something Dante
DID during the session (patch → run the one relevant test → confirm RED →
restore → `git diff --quiet` → confirm clean), never as permanent
self-patching test code inside the file. Followed the same shape here for
all 6 mutation checks (2 vectors × 3 sites): `Edit` the exact except-clause
or the `verify_path_within_project(...)` call line, run ONLY the affected
test class, confirm `rc=1` for the right reason (RecursionError traceback
in stderr for T1-A; forged value observed in the result for T1-B), `Edit`
back to the original, `git diff --quiet -- <file>` confirmed clean after
every single one of the 6. All 6 reproduced RED for the right reason on
first try — no false negatives.

**upgrade_check.py's `except Exception:` predates this commit — the T1-A
fix for that specific site is a no-op in the diff, but the regression test
is still owed.** Confirmed via `git show 5c9d012^:...upgrade_check.py`:
the broad except was already there before wip 5c9d012 (only
`verify_path_within_project()` is new there, for T1-B). Documented this
explicitly in the test file's class docstring rather than silently
treating it the same as the other two sites, which DID narrow their except
from `(OSError, json.JSONDecodeError)` to `Exception` in this exact commit
(confirmed via the same before/after diff read).

**Verification**: file alone 7/7 (both before and after every mutation
round restored to green), full suite `python3 -m pytest
unmassk-toolkit/tests -q` twice (once foreground with extended timeout,
once background as a cross-check) — both **1272 passed, 2 skipped
(Windows-only baseline), exit 0**, 327s runtime (needs >2min bash timeout,
same caveat as [issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md)).

See also: [issue-63-boot-simplification-contract-notes](issue-63-boot-simplification-contract-notes.md)
(same manifest-gate feature, earlier P1/P2/P3 acceptance contract),
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
(subprocess-isolation discipline for real stably-named modules), [issue-53-hardlink-reject-contract-notes](issue-53-hardlink-reject-contract-notes.md)
(differential-control pairing pattern this session's forged-version choice
generalizes).
