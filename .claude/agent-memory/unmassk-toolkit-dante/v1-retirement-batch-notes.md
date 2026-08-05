---
name: v1-retirement-batch-notes
description: unmassk-memory v1→v2 retirement batches — collect-only blind spot for in-function imports, mixed-content file criterion
metadata:
  type: project
---

Retiring v1 memory-system test files alongside their deleted production
pieces (git-memory v1 → v2 migration, branch feat/memoria-v2). Orchestrator
sends batches of specific filenames to delete; stop criterion per file is
"does 100% of its content test an already-deleted piece."

**Gotcha — `pytest --collect-only` does not surface in-function imports.**
Files in this codebase's convention (see
[[unmassk-toolkit-python-test-conventions]]) do `from recall import X` or
`from parsing import Y` *inside* helper functions/test methods, not at
module top-level. `--collect-only` only fails on module-level import
errors. A test file that entirely exercises a deleted module (e.g.
`lib/recall.py`) can show **zero** collection errors and still be 100%
dead — the ImportError only fires when the test actually runs. Before/after
collection-error counts are a valid regression check for module-level
breakage, but are NOT proof a batch of files is clean or dirty — read every
file's content, don't infer from collect-only output.

**Mixed-content file criterion (per orchestrator's stop rule).**
A file counts as "mixed" (must NOT be deleted) if ANY test class inside it
exercises a hook/module that still exists on disk, even if other classes in
the same file exercise a deleted one. Two real examples from this batch:
- `test_hardening_recall.py` — `TestFailOpenUpgrade` and
  `TestFailSafeLargeStdin` test live `hooks/session-start-boot.py` +
  `lib/upgrade_check.py` + `hooks/user-prompt-memory-check.py`;
  `TestSanitizeUnicodeSeparators` and `TestRecallRelevantEdgeCases` test
  deleted `lib/recall.py`. Kept whole, flagged live classes in the report.
- `test_user_prompt_recall.py` — despite the "recall" in its filename, it
  tests the *surviving* hook `hooks/user-prompt-memory-check.py` (the
  file's own docstring documents that the per-message recall-injection
  tests were already removed in a prior cleanup, issue #72). 100% live,
  0% dead — kept entirely intact.

**Practical check before trusting a filename's implication:** always verify
the actual deleted-vs-alive file list on disk (`[ -e path ]`) rather than
trusting the batch description or the test file's name/imports at a glance
— a file named `test_X_recall.py` is not proof it tests the deleted `recall`
module.

**Batch 3 — "mixed" also means "same mechanic survives under a renamed
symbol", not just "different test classes for different modules".**
`test_trailer_newline_regression.py` imports the dead `scan_trailers_memory`
(removed from `lib/parsing.py`), so it fails to collect — but its single
test exercises `build_commit_message()` in `bin/git-memory-commit.py`,
which is 100% unchanged (`# BUG T1 fix` comment still there, still does
`sanitize_trailer_value()` + collapse-double-spaces on every `--trailer`
value before writing). The read-side function was renamed/replaced
(`parse_trailers_full`/`parse_trailers`, both still doing the same
split-by-`\n` + per-line regex match `scan_trailers_memory` did), so the
exact truncation bug this regression guards against is still structurally
possible. One indivisible test touching both an alive write-path function
and a renamed read-path function is still "mixed" — kept intact, not
deleted, even though it's a single test method (not multiple classes).
Verify aliveness by reading the current function body for the comment/logic
the test's docstring describes, not just by checking the symbol exists.

`test_parsing_consolidation.py` is the more classic mixed case: 3 of 6 test
classes (`TestParseTrailersFull`, `TestParseCommitTypeWip`,
`TestSanitizeTrailerValueControlByteContract`) test `parse_trailers_full`/
`parse_commit_type`/`sanitize_trailer_value` directly — all three still
exist in `lib/parsing.py` unchanged, even though nothing in prod currently
*calls* `parse_trailers_full`/`parse_trailers` (grep the whole `lib/bin/hooks`
tree, not just callers you expect — a function can be alive-but-uncalled
and still deserve its unit tests). The other 3 classes depend on the dead
`normalize()` and/or `_import_gc()`ing `bin/git-memory-gc.py`, which no
longer exists on disk at all (confirmed `[ -e ... ]`) — v1's whole GC
subsystem was dropped in the v2 split, not just deprioritized.
