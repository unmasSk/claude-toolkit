---
name: issue-63-magic-string-reconciliation-notes
description: issue #63 wip f6d2b7d reconciliation — neutralize_needs_upgrade_check1/make_semver_test_repo rewritten to install real canonical content (managed_blocks.upsert_managed_blocks) instead of hand-typed "Context Checkpoint Commits"; 2 mutation-check gotchas that changed which guard removal actually turns a security test RED
metadata:
  type: project
---

Follow-up to [issue-63-t1-end-marker-magic-string-contract-notes](issue-63-t1-end-marker-magic-string-contract-notes.md)
after Ultron's GREEN (wip f6d2b7d): `lib/upgrade_check.py::needs_upgrade()`
Check 1 now calls `managed_blocks.any_block_outdated(content)` instead of
requiring the literal `"Context Checkpoint Commits"`. 14 tests went RED —
not because behavior regressed, but because the shared fixture helpers
that used to "neutralize" Check 1 by hand-injecting that literal now
actively **poison** it: appending an unrelated string makes the block's
body diverge FROM canonical, so `any_block_outdated()` flips to True
(confirmed live: fresh `--auto` install → `any_block_outdated()==False`
out of the box; append the old literal → `True`).

**Fix pattern (verified, not fabricated per §34):** both
`tests/conftest.py::neutralize_needs_upgrade_check1()` and
`tests/test_needs_upgrade_semver.py::make_semver_test_repo()` now call the
REAL `managed_blocks.upsert_managed_blocks(content)` over CLAUDE.md's
current content and write back the result — the exact same render
production code trusts. Idempotent: no-op on an already-canonical repo
(the common case, since callers always run a real `--auto` install
first), fixes drift on any other repo state. `import managed_blocks` works
directly in any test module once `tests/conftest.py` has run (it inserts
`LIB_DIR` into `sys.path` at module level, before pytest imports test
files) — `test_needs_upgrade_semver.py` still added its own explicit
`LIB_DIR` sys.path guard for clarity/independence rather than relying on
that side effect silently.

**Gotcha 1 — reframing `test_missing_context_checkpoint_still_triggers_upgrade`:**
its old contract ("missing the magic string → True") is dead. First
attempt at the "real replacement" (missing/divergent block → True) tried
removing the ENTIRE `unmassk-toolkit` block — but `needs_upgrade()` has
its own EARLIER fail-safe (`if "BEGIN unmassk-toolkit" not in content:
return False  # needs_install handles this`) that short-circuits before
Check 1 is ever reached, so that version returned False (test failed, but
for a different, informative reason: proved the earlier line, not Check
1). Fix: remove a SECONDARY block instead (`unmassk-protocols`), leaving
the primary block present — genuinely reaches
`any_block_outdated()`'s "begin marker absent" branch for one of the
other 4 blocks. Renamed to `test_missing_secondary_block_still_triggers_upgrade`.
Lesson: when reframing a test around a real oracle function, check ALL
the caller's own early-exit branches first, not just the oracle's
internals — a naive "remove everything" mutation can trip on a guard one
level up the call stack.

**Gotcha 2 — BUG M mutation-check needed BOTH guards removed at once:**
`TestBugMNeedsUpgradeManifestSymlinkRead` and `TestSecT1_002...` both
plant a symlink such that resolving `manifest_path` escapes the project
root. `lib/upgrade_check.py`'s manifest-read path has TWO independent
guards stacked: `verify_path_within_project()` (realpath-based, catches
ANY escaping path incl. a symlink at the final component) and
`open_no_follow_symlink()` (lstat-based, catches a symlink at the final
component specifically). Mutating either ONE alone left both tests GREEN
(the other guard silently covered for it) — false confidence. Only
removing both simultaneously produced true RED
(`assert True is False`, i.e. the exact real-world symptom: spurious
upgrade trigger). Generalizable: when two guards stacked in sequence both
happen to reject the same attack shape, a single-guard mutation check is
not sufficient evidence that either individual guard is load-bearing for
that specific test — must remove all guards that independently cover the
planted attack to get a meaningful RED.

Verification: `python3 -m pytest unmassk-toolkit/tests -q`, real exit
code, run in background per [issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md)'s
convention (>2 min runtime) — never piped to tail/head.
