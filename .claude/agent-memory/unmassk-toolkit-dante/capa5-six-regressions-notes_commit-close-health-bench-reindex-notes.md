---
name: capa5-six-regressions-notes_commit-close-health-bench-reindex
description: 6 regression tests for capa-5 hardening (2026-08-03) -- notes_commit.py path/cleanup, close.py permanent-close warning, health.py bench safety, bench.py attack-5 candidate check, reindex.py delegating to health.rebuild_plan(); pre-commit-hook cleanup technique; a real bug FOUND (not fixed) in close.py's retry command
metadata:
  type: project
---

Session 2026-08-03, `feat/memoria-v2` branch, step 5 of PIEZAS.md Sec.12bis
(hardening pass after Ultron's fixes). Six already-fixed production bugs,
one regression test each, `tests/memory/` only. All 6 confirmed RED-before
via scratch-copy mutation-check (pattern from
[boot-py-v2-full-contract-notes](boot-py-v2-full-contract-notes.md)),
GREEN-after against real code. Suite: 230 -> 236, all green.

## New reusable technique: pre-commit hook to force "add succeeded, commit
failed" without blocking add

`.git/index.lock` blocks BOTH `git add` and `git commit` -- useless for
testing "staging area cleanup after a failed commit" (nothing ever gets
staged). A `.git/hooks/pre-commit` script that always `exit 1` lets `git
add` complete normally and makes `git commit` abort AFTER staging -- the
only real-git way to reach the "something is staged but the commit never
happened" state without touching production code. Used to regression-test
`notes_commit.py::write_work()`'s new `git reset -- <path>` cleanup
(`test_work_script.py::TestFailedCommitLeavesNoStagedLeftovers`).

## Round-trip test caught a REAL bug that was NOT part of the six --
reported, not fixed

Testing hallazgo 3 (`close.py --restriction new`'s "cierre ya es
permanente" warning + exact retry command), the round-trip discipline
(never hand-type the expected value -- execute the printed command for
real, per §34) surfaced that `_fence_retry_command()`
(`bin/memory/close.py:118-131`) is missing TWO fields that `note.py`'s
real CLI requires for a fresh R note: `--stops yes` (the pain-question
customs check, `validator.validate_pain_question`) and `--description
"..."` (`vocabulary.TYPES["R"].required_fields`). `_create_fence()`, a few
lines above in the same file, fills both when writing the fence directly
via `notes.write()` (`description=args.restriction_text`, and it never
asks the pain question since it bypasses `note.py`'s CLI-level check
entirely) -- but the retry-command STRING it prints for a human to copy
does not replicate either field. Confirmed live: running the literal
printed command fails first with "falta una respuesta", and even after
adding `--stops yes` by hand, fails a second time with "Faltan campos
obligatorios ... description". Not fixed (out of scope, Ultron's job) --
the test adds both missing flags itself with an inline comment explaining
why, so the rest of the command (zones, `--origin`, headline) can still be
verified end-to-end, and reports the finding via code comment + this
memory + the final report to the orchestrator. **General lesson: a
round-trip test that actually executes the "exact command" a script
prints, instead of only checking its text contains the right substrings,
finds gaps that message-content assertions never would.**

## Other five, briefly

- **notes_commit.py `stage_and_commit`/`write_work`** (two separate
  hallazgos, one shared test scenario): `git add` anchored to `root` but
  `gitcmd.commit()` inheriting the ambient cwd meant a relative pathspec
  typed from a subdirectory could stage/commit the WRONG file at the repo
  root. Test scenario: root `app.py` modified-uncommitted, distinct `sub/
  app.py` untracked, commit from `cwd=sub` with `--path app.py` (relative).
  Mutation-check reverting just `write_work`'s absolute-path resolution
  (keeping the `cwd=root` fix in `stage_and_commit`) reproduced a WORSE
  failure mode than the original docstring's "commit fails, wrong file
  stays staged" -- the commit actually SUCCEEDED, silently baking the
  root's uncommitted dirty content into a real commit under the wrong
  path. Second, separate scenario/test for the cleanup-on-failure half of
  the same fix (see pre-commit-hook technique above).
- **health.py `_run_bench_safely()`**: `build()` used to call `bench.run()`
  unprotected; now wrapped. RED proof done in-process (no scratch copy
  needed): `monkeypatch.setattr(health.bench, "run", raiser)`, then assert
  the RAW call (`health.bench.run()`) still raises (proves the mock is
  real) while `health.build()` does not propagate and reports the reason
  in `bench_failures`.
- **bench.py attack 5**: `ok` used to only check that the rejection named
  the bad zone, never that a REAL candidate zone was actually offered
  (Sec.14 fila 5 has two halves in "se da por bueno si"). Old fixture only
  had one zone ("bench") with no close match to the ghost typo, so the
  second half could never even be demonstrated. Mutation-check confirmed
  the old code's `ok` stayed `True` even with zero real candidates in
  `zones` -- a vigilante that claimed "caught" without checking everything
  it promised.
- **reindex.py `_rebuild()` now delegates to `health.rebuild_plan()`**
  instead of reimplementing the cross-check inline. Test independently
  hand-applies the SAME plan (`health.rebuild_plan()`'s return value) onto
  a scratch COPY of the 8 index files (via `indexes.insert()`/`remove()`,
  never reusing `reindex.py`'s own loop) and diffs byte-for-byte against
  what the real script (subprocess) left on disk. Mutation-check: dropping
  just the `to_remove` half of `_rebuild()`'s loop left an orphan index
  line behind that the hand-applied plan correctly removed -- exactly the
  kind of drift a reimplemented (vs. shared) cross-check invites.
