---
name: memoria-v2-notes-cwd-incident
description: RESOLVED 2026-08-25 (verified file:line) — test_notes.py rows 7/8/9/11 now correctly wrap their seed calls in _cwd(root). Kept for the general lesson on cwd resolution + git-safety response, not as a live warning.
metadata:
  type: project
---

## RESOLVED — verified 2026-08-25, do not treat the warning below as current

The bug this file documents is fixed. Confirmed by reading
`unmassk-toolkit/tests/memory/test_notes.py` directly (not from memory):
the seed `notes.write()` call for row 7 is wrapped in `with _cwd(root):`
at line 909-910, row 8's seed call at line 999-1000, row 9's seed call at
line 1049-1050, and row 11's replace/close-on-unknown-id calls at lines
1207 and 1226 — every write/replace/close call in the file now runs
inside `_cwd(root)`. The historical entry below (kept verbatim for the
lesson, not as a live instruction) describes the bug BEFORE this fix; the
"Do NOT re-run" instruction in it is stale — this specific hazard is
closed. **This does not lift the file's separate, still-valid hard rule
against unscoped `pytest -q`** in this repo — that rule also rests on a
second, independent, still-live hazard (concurrent-session HEAD-move from
other agents' uncommitted work in the same tree), documented in
[lessons.md](lessons.md).

---

## Historical incident (2026-08-02) — kept for the lesson, superseded above

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
