---
name: memoria-v2-48-red-retirement-notes
description: 8-file, 48-red retirement pass (test_boot_output/test_hardening_recall/test_drift/test_regression_memory_correctness/test_parsing_consolidation/test_migrate_statusline/test_user_prompt_recall/test_encoding_contract) — stray-arg-in-call bug shape, trailer-key-retirement fix, 2 hallazgos left red on purpose
metadata:
  type: project
---

## What happened

Scoped retirement pass (PLAN-CONSTRUCCION.md §9.3) across 8 test files, 48
red tests, tests/-only (no production edits). Verdict split: 44 SE VA/SE
ARREGLADO (now green), 2 explicit HALLAZGO (left red on purpose, reported
file:line, not fixed — that's Ultron's scope). Final state: `pytest
unmassk-toolkit/tests -q --ignore=.../tests/memory` → 2 failed (both
hallazgos), 667 passed, 1 skipped.

## New pattern: "stray extra positional arg" bug shape (test_boot_output.py)

`_render_banner_with_branch()` called `render_boot_banner_lines(...)` with
9 positional args (an extra `""` before `pull_directive_lines`) against a
signature that only accepts 8-9 — `TypeError`. This is DEUDA.md's own
point 9 ("una llamada con un argumento de más las dejó sin cobertura"): a
production signature shrank (a param was dropped) and one caller among
several was never updated. Diagnostic signature: `TypeError: f() takes
from X to Y positional arguments but Z were given` where Z > Y, deep
inside a subprocess-isolated helper (`RuntimeError: helper failed (rc=1):
<the TypeError traceback>` at the outer assert). Fix is test-only (delete
the stray arg) — confirmed test-side by checking the OTHER call sites of
the same production function still work and the function itself is
unchanged/still called correctly elsewhere.

## Confirmed vacuous-green shape (2 more instances, same family as
memoria-v2-boot-memory-precompact-retirement-notes.md)

- `test_boot_output.py::TestGlossaryCache` (3 tests) — asserted PRESENCE of
  `glossary-cache.json` content; genuinely failed (not vacuous) because the
  file is never written anymore (`extract_glossary()` gone from
  session-start-boot.py). Contrast with the ABSENCE-shaped vacuous greens
  already documented elsewhere.
- `test_regression_memory_correctness.py::TestBugC_ContextDetectionInconsistency`
  — 2/4 tests "passed" (kept from a PRIOR pass as "unrelated Bug C, keep
  untouched") but were vacuous: they asserted a marker string is NOT under
  a `RESUME:` "Last:" line — RESUME never renders at all anymore (confirmed
  `get_last_context_time()`/`extract_memory()` don't exist anywhere in
  `lib/`), so "absent from a line that's never emitted" is trivially true.
  ALL 4 tests in the class (both red and the 2 "green") were retired
  together by deleting the whole file — a class can't be half-vacuous;
  once the underlying section is confirmed dead, the passing siblings go
  with the failing ones, not just the red ones on today's list.

## New pattern: comments/docstrings citing a function that's ALREADY gone

`test_migrate_statusline.py::TestSysModulesContaminationRegression` called
`boot_render.get_timeline()`. That function doesn't exist ANYWHERE in
`lib/` (`grep -rn "def get_timeline"` → zero hits) — despite being cited as
still-live in `lib/git_helpers.py` comments (~L852, L901) AND in
`tests/test_boot_git_checks.py` comments (L21, L855, L864). Those comments
are themselves stale/drifted, presumably from a parallel agent's cleanup
pass that removed the function without sweeping its own doc references —
out of scope to fix (not one of the 8 assigned files), only flagged. Lesson:
when a memory note or a code comment names a function as "still live", grep
for `def <name>` before trusting it — comments drift independently of code
in a codebase with several concurrent agents.

Also in that same class: the ORIGINAL contamination targets
(`lib/boot_memory.py`, `lib/boot_render.py`'s module-level `run_git` name)
are BOTH gone (file deleted; `boot_render.py` re-read in full — it now only
imports `cache_sync_check`/`boot_checks`/`version`, no `git_helpers` at
module level at all). The FIX PATTERN this test class was pinning
(deferred, function-local `from git_helpers import run_git`) is already the
codebase's live convention — confirmed all 5 call sites in
`lib/boot_git_checks.py` do it inside function bodies, never at module
level. No live equivalent target to redirect the test at without inventing
new coverage (out of scope for a retirement-only pass) — retired outright.

## New pattern: today's trailer-key retirement (Touched/Resolved-Next/Stale-Blocker)

`lib/constants.py::VALID_KEYS` was cut to `{Issue, Why, Decision, Memo,
Next, Blocker, Remember}` — a same-day owner decision, not organic drift.
`test_parsing_consolidation.py` had 2 tests built on the retired keys:
- one used `Touched` as a filler "valid key" example — swapped for
  `Blocker` (still valid), no semantic loss.
- one (`test_tombstone_keys_are_valid`) asserted `Resolved-Next`/
  `Stale-Blocker` WERE parsed as valid — inverted into
  `test_tombstone_keys_no_longer_valid`, a regression guard that these two
  don't silently creep back into `VALID_KEYS`. Pattern for future
  same-day-retired-config-value fixes: don't just delete the test, flip its
  assertion polarity to guard the new decision if the concept (here:
  "these specific historical keys should stay excluded") still has future
  regression value.

## Practical technique: byte-exact block deletion when Edit's string match fails

`test_hardening_recall.py` embedded LITERAL U+2028/U+2029 characters inside
test bodies (not escapes) — `Read`'s rendered output looked like plain
spaces, so `Edit`'s `old_string` never matched (invisible character
mismatch). Fix: use `Bash`+`python3` to read the file as a line list,
slice by 1-indexed line number confirmed via `grep -n`, and rewrite with
`f.writelines(head)` + `f.write(note)`. Faster and more reliable than
guessing at the invisible-character reproduction once a plain `Edit` fails
on a file known (from `grep -n` class boundaries) to contain non-ASCII
control chars.

## Two HALLAZGOs (same root cause, reported once — not fixed)

`hooks/user-prompt-memory-check.py` `main()` (~L157-205): when
`session_booted=True` (already-booted repo) AND the prompt matches no
skill-router keyword, `lines` stays `[]` and `if lines: print(...)` never
fires — the hook emits **zero stdout**. Two different tests independently
caught this:
- `test_user_prompt_recall.py::TestNoRegression::test_base_output_not_empty`
  — direct empty-stdout assertion.
- `test_encoding_contract.py::TestUserPromptMemoryCheckCp1252::test_valid_stdin_json_exits_zero_with_useful_output`
  — same empty-stdout symptom, observed under a cp1252 env; its
  "git-memory-recall.py"/`_BANNER` expectation (issue #69's "folded into
  the unconditional banner") also confirmed absent everywhere in the hook
  (`grep` zero hits) — the whole always-print mechanism this test's
  contract depended on is gone, not just encoding-unsafe.

Per house rule ("un hallazgo se cuenta una vez"), reported as ONE finding
with two file:line citations, not two separate items. Neither test was
touched — both stay red until Ultron restores an unconditional print (or
the product decision is made that silent-when-nothing-to-say is
intentional and both tests get rewritten, which is NOT this agent's call).
