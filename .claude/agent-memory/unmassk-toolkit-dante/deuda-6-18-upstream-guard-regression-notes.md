---
name: deuda-6-18-upstream-guard-regression-notes
description: DEUDA.md #6/#18 — restored check_upstream_shares_history() guard regression test, and the "copy whole relative-path subtree, disable with if False" mutation-check technique for hooks that resolve lib/ via __file__-relative sys.path.insert
metadata:
  type: project
---

Session 2026-08-02. Task: restore the ONLY lost coverage for `check_upstream_
shares_history()` (`unmassk-toolkit/lib/boot_git_checks.py:361`) after
`test_boot_freshness_regression.py` was retired whole with the memory v2
cleanup — the function itself and its two live call sites in `hooks/
session-start-boot.py`'s `main()` (the PULL DIRECTIVE line and the BRANCHES
section) had already been re-fixed by Ultron; only the test net was missing
(DEUDA.md #6 = the bug, #18 = the missing test). No production code touched
in this pass — test-only, added to `tests/test_boot_git_checks.py` (the file
that already salvaged the rest of the live coverage from the retired file).

**Fixture, reused almost verbatim from the retired file**: a fresh, unrelated
`git init --bare` + one clone + N commits naturally shares ZERO history with
another repo — no orphan-branch trick needed for the E2E scenario (only the
direct-unit "no common ancestor" case still uses `git checkout --orphan`,
because that one needs the SAME repo to hold both sides). Repointing an
EXISTING remote's URL (`git remote set-url origin <foreign_bare>`) rather
than creating a new remote is deliberate — it keeps `branch.main.remote`/
`.merge` tracking config coherent, reproducing the exact misconfiguration
`check_upstream_shares_history()` exists to catch (`@{u}` resolves, fetch
succeeds, zero shared history). Since memory v2 removed the boot hook's own
`git fetch` entirely (DEUDA #17), the test must `git fetch origin` explicitly
after the repoint — otherwise the stale tracking ref from before the
repoint still resolves to shared history and the scenario never reproduces.
Two assertions key off literal strings confirmed (via `grep`) to be produced
by exactly ONE call site each in the whole codebase: `` "git pull" `` (only
inside `_build_pull_directive_lines()`'s clean-tree branch) and
`"BRANCHES ("` (only inside `render_branches_section()`'s header line) — see
[edge-cases.md](edge-cases.md)'s marker-uniqueness family of gotchas for why
this matters (a loose substring can pass vacuously if it's echoed elsewhere).

**New reusable technique — proving a RED-without-the-fix result for a hook
whose `sys.path.insert(0, ...)` is computed `__file__`-relative (so a bare
copy of the hook file alone can't find its `lib/`), without ever touching
the real committed file**: `rsync -a --exclude=.git
unmassk-toolkit/ <scratchpad>/mutation_check/unmassk-toolkit/` (whole
subtree, preserves the `hooks/../lib/` relative depth the hook's own
`sys.path.insert` computes from `os.path.dirname(os.path.dirname(__file__))`),
edit ONLY the scratch copy's `hooks/session-start-boot.py` (replaced the
guard's `if upstream_ref and check_upstream_shares_history(...) is False:`
with `if False:  # MUTATION-CHECK: ...`), then `cd
<scratchpad>/mutation_check && python3 -m pytest
unmassk-toolkit/tests/test_boot_git_checks.py -q -k "..."` — pytest picks up
the copy's own `conftest.py` automatically (all `SOURCE_ROOT`/`LIB_DIR`/
`HOOKS_DIR` constants are `__file__`-relative to conftest.py itself), so
every fixture (`_setup_freshness_repo`, `run_script`, etc.) transparently
resolves inside the scratch copy with zero test-file changes needed. This
mirrors this project's [[unmassk-standards]] mutation-check convention
(write a broken variant, confirm the test kills it, discard the variant) but
extends it to a case where the "variant" is a whole relative-path-dependent
subtree, not a single importable module — the existing `tmp_path`/scratchpad
single-file pattern in [mock-patterns.md](mock-patterns.md)'s HARD RULE
section doesn't cover this shape.

**Confirmed result**: with the guard disabled, `test_unrelated_upstream_
shows_neither_pull_nor_branches` failed for exactly the predicted reason —
captured stdout showed `PULL DIRECTIVE: local is 2 commit(s) behind —
propose \`git pull\`...` AND `BRANCHES (origin):\n  main (current): ...
chore: foreign lineage commit 1...` (the foreign repo's own branch, listed
as if it belonged to this project) — reproducing DEUDA.md #6's live repro
almost verbatim. All 7 sibling tests (the 3 direct-call
`check_upstream_shares_history()` tests + the legit-upstream positive
control) stayed green under the same mutation — confirms the kill is
precise (only the wiring broke, not the function itself, and the negative
control wasn't a false accomplice). Scratch copy discarded after
verification (session scratchpad, never committed); real repo files
confirmed untouched via `git status --porcelain -- unmassk-toolkit/lib
unmassk-toolkit/hooks` showing no new diff from this pass (pre-existing
uncommitted memoria-v2 WIP in `lib/`, `hooks/`, `bin/` was already present
before this task and deliberately left alone — see [[unmassk-standards]] and
the orchestrator's explicit git-safety instruction this session: no stash/
reset/checkout, this file's own edits only, via the Edit tool).

Final real-file verification: `python3 -m pytest
unmassk-toolkit/tests/test_boot_git_checks.py -q` → 41 passed, 1 skipped
(pre-existing Windows-only `TestWin32ProcessTreeKillOnTimeout`, unrelated),
exit 0.
