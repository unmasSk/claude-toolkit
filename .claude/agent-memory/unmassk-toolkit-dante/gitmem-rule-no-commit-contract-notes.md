---
name: gitmem-rule-no-commit-contract-notes
description: 2026-08-06 rewrite of the rules.py/rule.py contract from "add() commits" to "add() never commits" (owner order, mirrors gitmem zones add), plus the coherence_rules() retirement contract in boot.py
metadata:
  type: project
---

**Order (owner, 2026-08-06):** `gitmem rule "<texto>"` must NOT create a
commit. It writes the line to `.claude/project-memory/rules.md` and stops --
the file rides along with whatever real commit comes next (`gitmem work`/
`gitmem wip`/`gitmem note`/session close). Same pattern Ultron already
shipped for `gitmem zones add` (verified with HEAD before/after). Neither
`lib/memory/rules.py` nor `lib/memory/health.py` were touched this pass --
test-only, Ultron implements next.

**Files touched (tests only):**
- `unmassk-toolkit/tests/memory/test_rules.py` -- rewrote fila 4
  (`test_commit_and_file_end_up_with_the_same_text` ->
  `test_add_writes_the_file_and_creates_no_commit` +
  `test_add_leaves_the_rules_file_as_an_uncommitted_modification`, HEAD
  before/after + `git status --porcelain` real). **Retired**
  `test_failed_commit_reverts_the_file_to_its_previous_content` and
  `test_failed_first_ever_commit_deletes_the_file_entirely` -- both planted
  a real `.git/index.lock` to force the OLD second-step commit to fail and
  checked `_restore_file_best_effort()`'s rescue; with `add()` never
  reaching a commit step at all, there is nothing left to rescue. Removal
  banner left in place (`RETIRADAS 2026-08-06 [orden del propietario]`,
  same style as `test_remove_script.py`'s 2026-08-05 precedent) instead of
  a silent deletion. **Discrepancy flagged, not silently resolved:** the
  owner's message said "los TRES tests de rescate" but named only two
  mechanisms (revert-on-fail, delete-if-first) and only two matching test
  functions exist anywhere in `test_rules.py`/`test_rule_script.py` (grepped
  `index.lock` across the whole `tests/memory/` tree to confirm) -- reported
  as exactly 2 retired, count discrepancy called out explicitly rather than
  guessing a third.
- `unmassk-toolkit/tests/memory/test_rule_script.py` -- renamed
  `TestRuleEndsUpInBothPlacesForReal` ->
  `TestRuleEndsUpInTheFileNotInAnOwnCommit`, rewrote
  `test_rule_appears_in_the_file_and_in_a_real_git_commit` (its own
  docstring said, quoted literally by the owner, "una regla anadida tiene
  que producir exactamente un commit" -- now split into
  `test_rule_ends_up_in_the_file_and_creates_no_commit` (commit count
  unchanged) + `test_rule_leaves_the_file_as_a_real_uncommitted_change`
  (`git status --porcelain`). Added
  `test_a_later_gitmem_work_picks_up_the_pending_rule_line` (point 3 of the
  order): seeds `repo_type="trunk"` (else `work.py` bounces on main-branch
  protection, same pattern as `test_work_script.py`), adds a rule, then
  runs `bin/memory/work.py "<msg>" --path .claude/project-memory/rules.md`
  as a real subprocess and verifies exactly one new commit, `git status`
  clean afterward, and `git show HEAD:<path>` contains the real rule text
  (blob-level proof, not just working-tree proof).
- `unmassk-toolkit/tests/memory/test_boot.py` -- new
  `test_checks_block_never_mentions_rules_after_a_normal_add`: builds a
  real `BootSummary` via `boot.build()`/`boot.render()` after ONE ordinary
  `rules.add()` call (no manual corruption tricks) and asserts the literal
  string `"rules"` never appears in the CHECKS block. This is deliberately
  the simplest possible scenario -- once `rules.add()` stops committing,
  EVERY normal rule becomes "in the file, not in any rule commit", which is
  exactly what `coherence_rules()` used to flag as a real divergence. Proves
  the retirement is structural, not just "quiet when healthy": today it's
  RED because the line `✓ rules match git (1 lines / 1 commits)` still
  prints (production untouched) -- the new contract requires the mention to
  be absent even when correct, not just non-alarming.

**Explicitly out of scope this pass, flagged in the test file comment
itself (not touched, not silently ignored):** once Ultron actually deletes
`coherence_rules()`/`HealthReport.rule_commits`/`rule_lines`/
`rule_discrepancies`/the CHECKS render lines in `boot.py`, these pre-existing
tests will need reconciliation (retire or rewrite) --
[test_boot.py](../../../unmassk-toolkit/tests/memory/test_boot.py)
`test_avisos_block_paints_rule_coherence_alongside_the_other_two_checks`,
`test_avisos_block_shows_the_real_rule_count_when_everything_is_fine`,
`test_a_rule_line_deleted_by_hand_is_shown_as_a_warning_at_boot_end_to_end`;
`test_health.py`'s five `coherence_rules()` tests (~829-984, ~1112) plus
`test_health_report_carries_the_real_rule_coherence_numbers`; and one
reference in `test_boundary.py` (~904). Not touched this pass because the
owner's explicit "son tuyos" list only named the 4 rules.py/rule_script.py
tests -- retiring ~10 more scattered across 3 files under time pressure
risked a sloppy cut across files not fully audited; better to name the
list than guess at it.

**Gotcha confirmed live:** `bin/memory/work.py --path <rules.md path>`
against TODAY's (unfixed) `rules.add()` fails with git's own "nothing added
to commit but untracked files present" -- not a bug in the test, it's the
correct RED: today `rules.md` is already fully committed by `rule.py`'s own
commit, so there is genuinely nothing pending left for `work.py` to pick
up. Confirms the contract is coherent end-to-end.

**Practical note from the order, worth repeating:** the `gitmem` on `$PATH`
is a launcher pointing at the INSTALLED plugin, not this repo -- use
`python3 unmassk-toolkit/bin/gitmem` (or, as these tests do, the
`run_memory_script`/`run_git` helpers from `tests/memory/conftest.py`,
which already invoke `bin/memory/*.py` directly with the right `cwd`). Not
using the raw `gitmem` launcher anywhere in this pass avoided the extra
commit that tripped up Ultron on the zones.py sibling task.

See also: [scaffold-py-red-contract-notes](scaffold-py-red-contract-notes.md)
for the unrelated same-day scaffold.py task (different module, no overlap).

**Follow-up same day: Ultron's retirement of `coherence_rules()` orphaned 12
tests + 1 surprise, all reconciled.** Once Ultron implemented the contract
above (rules.py never commits, `health.coherence_rules()`/
`_rule_commit_texts()`/`HealthReport.rule_commits`/`rule_lines`/
`rule_discrepancies` all deleted, boot.py's CHECKS lines removed), 12 named
tests + 1 found only by EXECUTING (not grep) broke. Retired (existed solely
to pin `coherence_rules()`, nothing left to prove once it's gone): all 5
`coherence_rules()` scenario tests + `test_health_report_carries_the_real_
rule_coherence_numbers` + `test_coherence_rules_on_a_repo_with_zero_commits_
does_not_crash` in `test_health.py` (7 total, plus their now-orphaned
helpers `_delete_rule_line_by_hand`/`_append_uncommitted_rule_line_by_hand`/
`_zero_commit_repo` and fixtures `rules`/`emojis`); `test_avisos_block_
paints_rule_coherence_alongside_the_other_two_checks` +
`test_avisos_block_shows_the_real_rule_count_when_everything_is_fine` +
`test_a_rule_line_deleted_by_hand_is_shown_as_a_warning_at_boot_end_to_end`
in `test_boot.py` (3, replaced by the `test_checks_block_never_mentions_
rules_after_a_normal_add` I'd already added the same day) plus a 4th,
**`test_avisos_shows_warning_not_checkmark_for_rules_when_counts_match_but_
content_differs`** (~line 1217 pre-cleanup) that was NOT in the owner's
original list -- only surfaced by actually running the file, not grep (the
owner said this explicitly: "la lista de Ultron sale de grep, no de
ejecución, salvo los de test_boot.py"). Retired its orphaned helper
`_swap_rule_line_by_hand` too. **Adapted, not retired:** `test_rules.py::
test_remember_from_a_plain_subfolder_of_the_same_repo_still_works` -- a
`[GUARD]` test proving root-resolution-from-a-subfolder still works, which
remains true; only its READER changed (`git log -1 --format=%s` -- always
green now since HEAD never moves -- swapped for
`rules.rules_file_path(project_root)` read directly, an independent,
stronger proof since it doesn't depend on cwd at all).

**Real discrepancy caught by executing, not trusting the coordinator's
claim (contradicts a "no rompe" statement -- verify before agreeing):**
losing `coherence_rules()` as `rules.rules_file_path()`'s only external
production caller made `test_boundary.py::test_no_public_symbol_has_zero_
production_and_zero_tests` (a general dead-code gate, unrelated to
coherence_rules by design) genuinely FAIL -- `rules.rules_file_path`
dropped to production=0 AND tests=0 (the red case), not just a stale
docstring citation as the coordinator believed. Fixed honestly (not by
weakening the gate): the adapted `[GUARD]` test above already gives it a
real, organically-justified direct test call, which is what flipped it back
to non-red (tests=1). Also fixed the actually-stale docstring citation
(`health.coherence_rules` no longer exists as a symbol at all, dropped
out of the report table entirely) with a dated correction paragraph rather
than rewriting the whole 2026-08-04 snapshot (already stale from unrelated
`remote.*` work, out of scope to re-audit here).

**Lesson for next time a retirement task lands:** always locally re-run
`test_boundary.py`'s dead-symbol/dead-module gates after any production
function is deleted -- a symbol's only external caller disappearing is
exactly the kind of second-order breakage that a coordinator's grep-based
list misses and only real execution catches.
