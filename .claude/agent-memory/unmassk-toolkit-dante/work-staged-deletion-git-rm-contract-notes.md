---
name: work-staged-deletion-git-rm-contract-notes
description: gitmem work fails to commit a deletion already staged with git rm -- git add --all sees nothing to stage; contract test RED, root cause in stage_and_commit()
metadata:
  type: project
---

`gitmem work "<msg>" --path <file>` fails when `<file>` is a tracked file whose
deletion was already staged with `git rm` (gone from both index and worktree).

**Root cause** (`lib/memory/notes_commit.py::stage_and_commit()`, line ~188):
runs `git add --all -- <paths>` before `git commit -- <paths>` and returns
whatever the `add` step returns. `--all` already handles an *unstaged*
deletion (`rm file` without `git rm`) -- that was a 2026-08-05 fix, see the
function's own docstring. But when the path is gone from the index too
(already `git rm`'d), the pathspec matches nothing `git add` can see at all,
so `git add --all -- <path>` exits 128 with `fatal: pathspec '<path>' did not
match any files`, and the function returns that failure without ever
attempting the commit. Verified separately: `git commit -- <same path>` alone
(no `git add` in front) exits 0 and records the deletion fine.

**Why:** reported by the orchestrator, reproduced live in a scratch repo
2026-08-22/23. The fix has to distinguish "nothing to add because it's
already staged" from "nothing to add because the pathspec is genuinely
wrong" -- Ultron's job, not written yet.

**How to apply:** RED test lives at
`unmassk-toolkit/tests/memory/test_work_staged_deletion_commit.py`
(`TestWorkCommitsADeletionAlreadyStagedWithGitRm`). Follows the
`run_gitmem_script` + `seed_config_json(repo_type="trunk")` pattern from
[[gitmem-wip-branch-protection-notes]] and the work.py contract in
`test_work_script.py`. Once Ultron fixes `stage_and_commit()`, this test
must go GREEN without touching the unstaged-deletion path (already covered
by production docstring, not by a dedicated test found in this pass -- worth
checking during hardening).
