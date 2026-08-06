---
name: issue-81-suite-audit-reconfirmation-notes
description: 2026-08-06 re-audit of issue #81's weeks-old 180-test defensible cut — nearly all of it was already resolved by the time of the recheck
metadata:
  type: project
---

## What happened

Issue #81 (opened weeks before 2026-08-06) measured the toolkit's test suite and
found a defensible cut of 180 tests / ~3350 lines: 40 external-attacker-only, 110
tautological (citing a 586-line test file for a 74-line containment-check module),
23 supporting a completed one-time migration, plus ~62 "dudosos" control-byte
sanitizer tests, plus an unconsolidated regression tail (`test_boot_freshness.py` +
`_hardening.py` + `_regression.py`, ~4318 lines).

Re-audited on 2026-08-06 against the live repo (1009 tests, 84 files, 40867 lines
today — the suite roughly tripled since the original count). Result: **almost
nothing from the original cut still exists.**

- **Attacker + migration buckets: 0 tests today**, confirmed by reading all 13
  candidate files (symlink/hardlink/hardening/gate files) in full. Every file
  already carries its own inline "RETIRADO"/"Retirement note" comment dated
  2026-08-02 through 2026-08-06 — the cut had already happened in the normal
  course of work (issue #72 thinning pass, the memoria-v2 migration deleting
  `lib/recall.py`, the v1-gate retirement). What remains in those files is
  dual-purpose (defends a real accidental failure — TOCTOU race, disk
  corruption, interrupted write — not just a hostile actor) or explicitly
  self-declares in its own docstring that it is NOT an attacker scenario.
- **Control-byte sanitizer: only 13 distinct test definitions (23 collected
  pytest items) remain**, all verdict KEEP — `test_parsing_consolidation.py`'s
  `TestSanitizeTrailerValueControlByteContract` (git-commit-trailer corruption,
  not attacker framing, explicitly restored post-#72 for exactly this reason),
  `test_crossplatform_symlink_guard_hardening.py`'s `TestRunGitEncodingUtf8`
  (`text=True` silently rewriting a raw `\r`, same record-forgery class as
  issue #57), and one Moriarty-confirmed regression in
  `tests/memory/test_remove_script.py` (a user's OWN embedded newline in a
  close reason silently split ARCHIVED.md). Down from ~62 historically.
- **Regression tail: 0 lines today.** Not just consolidated — the entire
  lineage is gone. `test_boot_freshness*.py` (3 files) were already retired
  into `test_boot_git_checks.py` per
  [memoria-v2-freshness-retirement-notes](memoria-v2-freshness-retirement-notes.md),
  but a LATER commit (`615f5cc`, "borrado el sistema de memoria anterior y
  retirada su documentacion de obra") deleted `lib/boot_git_checks.py` and
  `test_boot_git_checks.py` too, as part of the full v1-memory-system purge.
  Only stale `__pycache__/*.pyc` bytecode remnants remain on disk (not
  collected by pytest).
- **Tautological bucket: 0 today, and mechanically confirmed** — zero
  `Mock(`/`MagicMock(`/`return_value` occurrences anywhere in the 40867-line
  suite (grepped). The original 586/74-line example most likely pointed at
  `lib/skill_router.py` (70 lines) / `test_user_prompt_skill_router.py` (627
  lines, ~9x ratio) — checked in detail and ruled OUT: it now contains a real
  drift-guard cross-checking two independently-maintained artifacts (a
  hardcoded phrase dict vs. live SKILL.md frontmatter) plus real subprocess
  hook-integration tests, added in a 2026-07 hardening pass. **Ratio alone is
  not a tautology signal** — every other high-ratio file checked this pass
  used real subprocess/git/file I/O or cross-checked independently-computed
  outputs against each other.

## Judgment call worth remembering

`scaffold.py` (3541 lines, largest file in the repo, zero test coverage) was
IN SCOPE at task start (issue #81 flags it as "the real gap") but the owner
pulled it out of scope mid-task via a hot correction: no tests needed for it,
don't even look at it. A sub-agent had already produced a 5-highest-risk-path
analysis for it before the correction landed — that output was discarded,
not delivered, per the correction. If `scaffold.py` coverage comes up again,
start fresh; don't assume the discarded analysis is still wanted or accurate.

## Why this matters for future test-suite audits here

This project's suite gets cleaned up FAST and INCREMENTALLY as normal work
happens (Cerberus/Argus/Moriarty findings get retired inline with dated
comments, not left to rot). A "measure the suite" task here should expect
the ground to have shifted since any prior audit, and should re-verify from
the live repo rather than trust a prior count — even the 40 vs 180 vs 1009
progression in this one issue shows how fast it moves.
