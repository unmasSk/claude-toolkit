---
name: boot-slim-report-89-contract-notes
description: #89 step 4.1 boot slimming RED contract — restrictions headline-only + pointer, one line per OPEN issue via the single gh call; GitHub double needs every selected field configured
metadata:
  type: project
---

2026-10-19, test-first RED for `lib/memory/boot.py` render (#89 4.1).

- Contract pinned by WHICH issue numbers appear in COUNTS, how often, order,
  and what is absent — never the label or per-issue title text (owner's
  example was Spanish mock-up; wording undecided). Helpers live in
  `tests/memory/boot_issue_state_support.py` (`patch_gh`, `counts_section`,
  `lines_naming_issue`, `issue_numbers_in`, `restrictions_section`).
- "Discarded notes out" = type X; "closed out" = `state` from the same
  `gh api graphql` call `health_plans.plans_unreflected()` makes (R-025).
  Notes with `issue` write the `Issue: #N` trailer, so that one call
  already names every issue the boot lists.
- Gotcha: when production adds a field (`state`, `title`) to the GraphQL
  selection, every hand-built issue record in other tests (test_health
  `_gh_graphql_completed`, test_ci_skip_marker, stub `_issue`) must carry
  it. `gh_graphql_fake._issue` now exits 2 "configured without X" instead
  of a KeyError deep in the code under test.
- Seed with in-process `notes.write` BEFORE `patch_gh`: the patched gh
  only answers `api graphql`, an `issue view` would be "unsupported".
- Phase 4 fix pass (2026-10-19): `test_boot_slim_report_fix_pass.py`.
  A number the fake does not hold = a PR / transferred issue (null alias,
  NOT_FOUND, rc 1). Contract changed: one missing number must not sink
  the batch, so `test_boot_deadline_contract` "missing" test now expects
  the other plans counted. Pin "only the missing one flagged" without
  wording: every ⚠ line in COUNTS must name the missing #N.
- Teardown errors seen once in `test_boot_step2_moriarty_fix_pass.py`
  hang/overrun tests under a batched run; not reproducible alone.
- `all(...)` over a warnings list is vacuous when the list is empty — pin the count (exactly one COUNTS warning naming the missing #N) or the dropped-warning mutant survives.
- Mutant copies of tests/memory need a bare `git init` at the copy root (no first revision needed): conftest's real-repo guard runs rev-parse with cwd='' otherwise. Creating a revision there is blocked by customs anyway.
