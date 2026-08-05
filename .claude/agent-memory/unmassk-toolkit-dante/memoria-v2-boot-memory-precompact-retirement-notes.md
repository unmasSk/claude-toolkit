---
name: memoria-v2-boot-memory-precompact-retirement-notes
description: Retirement of the 22 tests depending on lib/boot_memory.py, lib/recall.py, hooks/precompact-snapshot.py, bin/git-memory-gc.py (all 4 deleted on disk) — vacuous-green detection technique, and read-only verdict on parse_trailers_full()/parse_commit_type()
metadata:
  type: project
---

## What happened

Second retirement pass after [memoria-v2-freshness-retirement-notes](memoria-v2-freshness-retirement-notes.md)
(that one covered `test_boot_freshness*.py` / `test_issue61_*.py`). This pass
targeted a different, more specific 22-test list scoped by Bex ahead of
time, tied to the SAME 4 now-deleted production files
(`lib/boot_memory.py`, `lib/recall.py`, `hooks/precompact-snapshot.py`,
`bin/git-memory-gc.py`).

**Deleted (2 whole files, 11 tests):** `test_boot_tombstones.py` (5),
`test_boot_pending_next_cutoff.py` (6, direct `import boot_memory` ->
`ModuleNotFoundError`, confirms whole file was written against it).

**Surgical class removal (2 files):**
- `test_boot_output.py::TestCrownedEntriesHaveSensibleCaps` (2 tests) —
  rest of file (48 tests) untouched.
- `test_regression_memory_correctness.py::TestBugA_TombstoneOutsideScanDepth`
  (3) + `::TestBugB_PrecompactMissingTombstoneKeys` (4) — `TestBugC_
  ContextDetectionInconsistency` (4 tests, 2 pass/2 fail, unrelated Bug C)
  explicitly kept untouched. Also removed the now-100%-dead helpers only
  Bug A/B used: `_make_bare_repo`, `run_precompact`, `PRECOMPACT_SCRIPT`
  import, `FILLER_COUNT`, `_add_filler_commits` — verified zero remaining
  callers via grep before deleting (TestBugC uses none of them).

**Single-function removal:** `test_drift.py::test_gc_tombstones` (1) —
depends on `hooks/precompact-snapshot.py` (confirmed via live run:
`FileNotFoundError` on the hook path). The other 4 tests in that file that
ALSO call `run_snapshot()` (`test_dedup_integrity`, `test_snapshot_budget`,
`test_truncation`, `test_delimiter_collision`) are ALSO broken by the same
missing file but were explicitly out of scope ("solo ese test, los otros 7
se quedan") — did not touch them despite the same root cause, per Bex's
exact scoping. Worth flagging next time: a scoped list can leave known
siblings broken on purpose; don't "fix while I'm in there."

**Already gone before I started:** `test_integration.py::test_gc_real` —
a parallel session (same day, 2026-08-02) had already retired it plus 3
siblings (bootstrap/uninstall/upgrade) with an explicit retirement-note
docstring citing the same PLAN-CONSTRUCCION.md §9.3/§5.4. Zero action
needed; confirmed by grep (function doesn't exist, only named in a
docstring) rather than assuming the task list was stale.

## Vacuous-green detection technique (the part Bex most wanted flagged)

A test asserting **absence** of content (`assert X not in content`) inside
a section that no longer renders AT ALL is trivially true — it proves
nothing, it just happens to agree with reality. Detected this class by
literally RUNNING each target file/test before deleting anything (not by
reading the assertion and guessing):

- `test_boot_tombstones.py`: ran the file standalone → 2 passed / 3 failed
  out of 5. The 2 passers were BOTH "retired-note absent" assertions
  (`test_retired_remember_absent_from_boot_output`,
  `test_retired_memo_absent_from_boot_output`) — REMEMBER/MEMOS sections
  don't exist in v2's boot output at all anymore (confirmed via
  `hooks/session-start-boot.py`'s own module docstring: "the memory
  extraction ... was removed with the rest of the v1 memory system"), so
  "retired note absent" is automatically true for ANY note, retired or not.
  The 3 failures were "active note still present" assertions — those fail
  now because there's no REMEMBER/MEMOS section at all, not because of the
  original tombstone bug.
- `test_boot_output.py::TestCrownedEntriesHaveSensibleCaps`: both tests
  PASSED. Root cause: `content.find("DECISIONS:")` returns `-1` (DECISIONS
  section removed in v2, confirmed via `lib/boot_render.py`'s docstring
  listing DECISIONS among the removed section renderers), so
  `section_text = content[-1:]` (a single trailing character), zero `"👑"`
  substrings possible, `0 <= 20` → pass. The crown-cap contract was never
  exercised even once.
- `TestBugA_TombstoneOutsideScanDepth`: 2/3 passed the same "absence in a
  dead section" way; `TestBugB_PrecompactMissingTombstoneKeys`:
  1/4 passed the same way (`run_precompact()` returns rc=2/empty stdout
  because the script file is gone — "memo absent from empty string" is
  always true).

**General technique for next time**: never trust a green test in a file
whose production dependency is confirmed dead — always run it and read
WHICH assertion direction (presence vs. absence) passed. An "absence"
assertion against a feature that no longer renders is the signature shape
of a false-green; a "presence" assertion against the same dead feature
correctly goes red instead, which is why the same file can show a mix of
both outcomes from the identical root cause.

## Read-only verdict on `parse_trailers_full()` / `parse_commit_type()`
(Bex asked for a testing opinion, not a deletion — `test_parsing_
consolidation.py` 13 tests + `test_trailer_newline_regression.py` 1 test
left untouched)

Grepped every production file (`lib/`, `hooks/`, `bin/`, excluding
`tests/`) for callers of `parse_trailers_full`, `parse_commit_type`, and
even the sibling `parse_trailers` (single-value) — **zero hits outside
their own definitions in `lib/parsing.py`**. The 6 production files that
DO `from parsing import ...` only ever pull `sanitize_trailer_value`,
`parse_scope`, and `suggest_scope_from_paths` — never the two/three
functions in question. `lib/memory/notes.py` (the real v2 note-writing
path) has its own independent trailer/note handling and does not import
`lib/parsing.py` at all. Both docstrings claiming production usage
("Used by validation hooks and CLI scripts" / "Used by dashboard/gc")
are stale — `gc.py` doesn't exist, and no validation hook calls either.

**My opinion as the test writer**: these two functions are the same shape
as the already-documented v1-superficie orphans (`recall.recall_relevant`,
`bin/git-memory-gc.py`, `parsing.parse_trailers` — see
[deadend/memoria-v1-superficie in git-memory]) — real code, real tests,
zero production callers. They die with the v1 system exactly like
`boot_memory.py`/`recall.py` already did; nothing in v2's independent
`lib/memory/` note handling reaches for them. The ONE exception in that
same file is `test_trailer_newline_regression.py`'s single test — it does
NOT protect `parse_trailers_full()` for its own sake; it uses it as a
disposable, deterministic READ-SIDE PROBE in a real producer↔consumer
round-trip against `bin/git-memory-commit.py::build_commit_message()` (a
genuinely live production function) — the round-trip's value survives
even if `parse_trailers_full()` itself has no other caller, because the
thing actually being protected is the WRITE side's one-physical-line
guarantee. If `parse_trailers_full()` is ever deleted, that round-trip
test would need a different read-side probe (or the live git-notes-based
reader in `lib/memory/notes.py`), not a blanket deletion alongside the
other 13+5 orphan-unit tests.

## Verification

Ran each target file standalone before AND after (not just the full
suite) to isolate the effect of my own edits from a large concurrent
session (a parallel agent was mid-repair on boot/parsing/trailer files —
`git status` showed a long list of unrelated `M`/`D` files not part of
this task). Full-suite before/after numbers moved by more than my own
21-test delta because of that concurrent work; the reliable signal was
running exactly the 5 files I touched in isolation (2 deleted, 3 edited)
and diffing their own pass/fail counts against a standalone run of the
same files pre-edit.
