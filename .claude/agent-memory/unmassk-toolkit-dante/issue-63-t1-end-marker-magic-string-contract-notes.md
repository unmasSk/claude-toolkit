---
name: issue-63-t1-end-marker-magic-string-contract-notes
description: issue #63 decision 1d623da RED contract — T1-A orphaned-END-marker lie in managed_blocks.py upsert, T1-B needs_upgrade() magic-string "Context Checkpoint Commits" that never existed in prod content; full list of pre-existing tests that assume the magic string and must be reconciled in GREEN, not touched in RED
metadata:
  type: project
---

Contract file: `unmassk-toolkit/tests/test_issue63_t1_end_marker_and_magic_string.py`
(4 tests: 2 RED, 2 non-RED contract locks). Decision 1d623da phases 2
pre-existing T1s (Moriarty round 2 against #63's P1 v2 content gate,
decision 2d56444) into the same batch instead of deferring. Both bugs are
byte-identical on `main` — not introduced by #63, but contradict #63's/the
gate's own stated goals so the decision fixes them here.

**T1-A** (`lib/managed_blocks.py:190` `upsert_managed_blocks()`): only
checks `begin in content`, never `end`. Deleting one block's END line
(merge-conflict resolution, editor auto-fix) leaves BEGIN orphaned — the
begin...end DOTALL regex can't match, `pattern.sub` no-ops, log records
"up-to-date {begin}", `hooks/session-start-crew.py` prints "[crew] All
managed blocks up to date" while the block stays corrupted forever (write
only fires on a diff, never triggered). RED test: real subprocess of
`session-start-crew.py` against a real `--auto`-installed repo, delete
ONLY the END line for block 0, run the hook, assert END count == 1 (not
0) AND `"up to date"` not in combined stdout+stderr — anti-vacuity pairs
content-restoration with the log-lie check so neither alone can pass. Also
asserts BEGIN count stays == 1 (catches a pathological fix that appends a
second full block instead of replacing the orphaned one) and a 2nd run is
a genuine no-op.

**T1-B** (`lib/upgrade_check.py:102` `needs_upgrade()` Check 1): requires
literal `"Context Checkpoint Commits"` inside the block — that string has
**never** existed in real production content (`git log --all -S"Context
Checkpoint Commits"` = 0 hits outside test fixtures). A from-scratch,
100%-canonical `--auto` install with `manifest.version == VERSION` still
gets `needs_upgrade()==True` forever — `trigger_auto_upgrade_if_needed()`
shells out to the full installer on every SessionStart, defeating #63's
own point. RED test: real install, precondition-assert `not
any_block_outdated(content)` and `manifest["version"] == VERSION` (both
must hold from a fresh install), call the real
`lib/upgrade_check.py::needs_upgrade()` via isolated subprocess (same
`_call_needs_upgrade` shape as
[issue-63-t1-manifest-read-hardening-notes](issue-63-t1-manifest-read-hardening-notes.md)'s
`_call_needs_upgrade`), assert `False`. 2 companion contract tests (old
manifest version → True; block body tampered away from canonical, NOT via
the magic string, kept-version → True) are **not RED today** — today's
magic-string Check 1 already returns True for those cases for the WRONG
reason (real install snippet never contains the magic string in the first
place, so it's vacuously True regardless of the tamper). Documented
explicitly as non-RED locks-for-later rather than hidden, same shape as
`test_crew_content_gate_v2.py`'s Test 4 ("may be green already today").
Per instructions, mechanism (compare against real canonical render vs.
some other approach) is deliberately left to Ultron — only observable
`True`/`False` behavior is asserted.

**Pre-existing tests that assume the magic string — NOT touched in this
RED pass (Ultron/GREEN-phase reconciliation list, per explicit
instruction not to fix collateral in a contract-only turn):**
- `tests/conftest.py::neutralize_needs_upgrade_check1()` (~L179-218) — the
  shared helper itself patches CLAUDE.md to insert the literal string so
  Check 1 is neutralized to isolate Check 2. Consumed by
  `tests/test_issue63_manifest_read_hardening.py:122`,
  `tests/test_security_regression.py:1708`,
  `tests/test_upgrade_moved_to_sessionstart.py:117`.
- `tests/test_needs_upgrade_semver.py::make_semver_test_repo()` (~L94-121)
  — re-derives the same patch locally; used by nearly every test in that
  file (`TestNeedsUpgradeSemver`, etc.) to isolate the semver rule (Check
  2) from Check 1.
- `tests/test_needs_upgrade_semver.py::TestNeedsUpgradePreexistingReasons
  ::test_missing_context_checkpoint_still_triggers_upgrade` (~L432-449) —
  asserts DIRECTLY that removing the magic string → True. This test's
  entire premise dies once Check 1 stops keying off that literal.
- `tests/test_control_byte_injection.py` (~L2384),
  `tests/test_user_prompt_skill_router.py` (~L154),
  `tests/test_hardening_recall.py` (~L96-106) — each hand-writes a fake
  "already installed / synced" CLAUDE.md fixture containing the literal
  magic string to make Check 1 evaluate False and isolate unrelated
  behavior under test in that file. Once Check 1 stops trusting the
  literal, these hand-typed fixtures no longer represent genuinely
  canonical content and must be re-derived from `managed_blocks.py`'s real
  render (unmassk-standards §34), not patched with a different literal.

Verification: file alone 2 RED (right reason, confirmed via failure
message: T1-A shows `stdout='[crew] All managed blocks up to date'` with
END count 0; T1-B shows `result=True` against a precondition-verified
canonical+version-matching install) + 2 pass (documented non-RED locks).
Full suite `python3 -m pytest unmassk-toolkit/tests -q` run in background
per this session's convention for the >2min runtime (see
[issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md)) —
0 production files touched (`git status` confirmed only the new test file
is untracked).

See also: [issue-63-p1-v2-content-gate-contract-notes](issue-63-p1-v2-content-gate-contract-notes.md)
(the P1 v2 gate this session's 2 bugs were found attacking — same repo/
install helper shapes reused), [issue-63-t1-manifest-read-hardening-notes](issue-63-t1-manifest-read-hardening-notes.md)
(the `_call_needs_upgrade` isolated-subprocess pattern this file reuses
for T1-B).
