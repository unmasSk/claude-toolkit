---
name: memoria-v2-notes-cwd-incident
description: test_notes.py rows 7/8/9/10 seed notes.write() outside _cwd(root) -> real repo pollution (70+ garbage commits on feat/memoria-v2, HEAD landed on one). Never re-run that file until fixed.
metadata:
  type: project
---

2026-08-02, while implementing `notes.replace()`/`notes.close()` (DEUDA
point 10). `unmassk-toolkit/tests/memory/test_notes.py` rows 7, 8, 9, 10
(the new replace/close rows) each do a "seed" call —
`result_old = notes.write(old_note, make_context())` — to create the note
that will later be replaced/closed, and that seed call is written OUTSIDE
the `with _cwd(root):` context manager that every other write in the file
correctly uses. `notes.write()`/`replace()`/`close()` all resolve their
target repo via `gitcmd.repo_root(Path.cwd())` — with no `_cwd(root)`
active, `Path.cwd()` is whatever the pytest process's real cwd is (the
actual `claude-toolkit` checkout), not the test's isolated `tmp_repo`.

**Why: consequence, not theory** — verified in the real repo after running
this suite. `git log` on `feat/memoria-v2` had 70 real commits titled
`[M-0NN][product][notes-test] MARK_ROW7_OLD ...` etc., HEAD was literally
sitting on one of them (`8cf4ddc`), and `MEMOS.md`/`ARCHIVED.md`/
`DECISIONS.md`/etc. existed as untracked files in the real repo root
(`git status` showed them `??`). Boundary: the last real commit before the
pollution starts (in this session) was `1f38104`. This is not a one-time
fluke — every single pytest invocation of this file (by anyone, since the
test was authored) adds ~4-5 more such commits, because rows 7/8/9/10's
seed call runs on every collection.

Downstream effect this caused: `old_id`/`note_id` computed by the seed
call (e.g. `M-070`, derived from the REAL repo's ever-growing index) don't
exist in the test's OWN isolated `tmp_repo` (which the actual
`replace()`/`close()` call correctly targets via `with _cwd(root):`), so
`indexes.remove()` raises `'M-070' no esta en MEMOS.md'` — looks like an
implementation bug but isn't one.

**How to apply:** this is a test-file defect, not an implementation one —
Ultron's own rule ("no toques ningun test, si un test te parece mal, paras
y lo dices") applies. Verified the actual `replace()`/`close()` logic is
correct by reproducing the five contract rows standalone in a throwaway
git repo under the scratchpad (no pytest, no real cwd) — all passed. Do
NOT re-run `pytest tests/memory/test_notes.py` until Dante adds
`with _cwd(root):` around the four seed calls — every run adds more
garbage commits to the real branch. Do NOT `git reset --hard`/rebase to
clean it up unilaterally (see the repo-wide git-safety HARD RULE in
MEMORY.md) — that decision belongs to the owner.

Related, but a different bug: commit `d102eeb` (already in history) is a
prior memo about `lib/memory` index files landing in the repo ROOT instead
of `.claude/project-memory/` per spec §7 — that's a real path-resolution
issue in production code. This incident is different: it's the TEST
process's `Path.cwd()` never being redirected at all for those four
specific calls, so they hit the real repo root regardless of where
indexes.py eventually decides to put files.
