---
name: issue-63-p1-v1-retirement-notes
description: issue #63 P1 v1-gate test retirement (decision 2d56444) — redundant-vs-reframe judgment call, and the cross-file cascade found by diffing Ultron's WIP instead of trusting the task brief's file list
metadata:
  type: project
---

Retirement pass for the v1 "manifest.version gate" contract, once decision
2d56444 replaced it with the v2 content-based gate (see
[issue-63-p1-v2-content-gate-contract-notes](issue-63-p1-v2-content-gate-contract-notes.md)).
Two judgment calls worth keeping for next time a contract reversal needs
test cleanup:

**1. Redundant vs. reframe — pick redundant when a harder case already
subsumes the easier one.** `test_crew_manifest_version_gate.py` had 3
classes. `TestManifestVersionMatchSkipsRewrite` directly contradicted the
new contract (retire, no debate). `TestManifestVersionMismatchStillRegenerates`
was trickier: its OUTCOME (regenerate) still holds true under v2, so it
doesn't "fail" — but it duplicates a strictly harder scenario already in
`test_crew_content_gate_v2.py` (poisoned block + MATCHING version still
regenerates is a superset of stale block + MISMATCHED version, since v2
doesn't check version at all). Retired as redundant rather than reframed —
reframing would have produced a permanently-weaker duplicate test with no
incremental coverage. `TestManifestAbsentOrCorruptStillRegenerates` was kept
untouched: missing/corrupt manifest robustness is not covered anywhere else
and stays true regardless of which gate design is running.

**2. Always diff the production file under WIP before trusting the task
brief's file list — a deleted function breaks tests that were never named.**
The task named only `test_crew_manifest_version_gate.py` for retirement, but
step 3's mandated grep (`_manifest_version_matches` across tests/) surfaced
`test_issue63_manifest_read_hardening.py`, which calls that function BY NAME
via a subprocess probe for unrelated T1 security hardening (SEC-T1-001
RecursionError, SEC-T1-002 dir-symlink bypass) on the manifest READ itself —
nothing to do with the skip/regenerate semantics. Running `git diff --
hooks/session-start-crew.py` against Ultron's uncommitted WIP confirmed the
function was deleted ENTIRELY (not just stopped being called for gating) —
so those 2 classes would have thrown `AttributeError`, not a semantic
assertion failure, once his GREEN landed. Extended the retirement to those 2
classes in that second file (leaving the boot_health/upgrade_check classes
in the same file untouched — different production files, unaffected by
Ultron's WIP). Lesson: "verify no other test assumes X" tasks should include
reading the implementer's live diff, not just grepping test literals — a
whole-function deletion is a stronger and more urgent signal than a
behavior/contract change, because it produces errors, not just wrong
assertions.

Both retirements documented via extended module docstrings in the files
themselves (not just here) so a future reader hits the "why" inline instead
of only in memory.
