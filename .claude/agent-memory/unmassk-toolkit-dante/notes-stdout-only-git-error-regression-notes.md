---
name: notes-stdout-only-git-error-regression-notes
description: test_notes.py RED regression -- git_error empty when git's "nothing to commit" failure writes to stdout not stderr; reusable no-op-monkeypatch technique to force a real stdout-only git failure through write()
metadata:
  type: feedback
---

New real-git-failure shape, distinct from the `.git/index.lock` technique
already documented in
[notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md):
git's "nothing to commit, working tree clean" failure writes to **stdout**,
leaves **stderr empty**. `notes.py` returns `git_error=git_result.stderr`
at both call sites (`write()` and `write_work()`) -- against THIS failure
shape, `git_error` comes back as an empty string (not `None`, worse: looks
like success at a glance). Confirmed live with a standalone repro script
before writing the test (`git commit` on an unchanged tracked path,
returncode 1, stdout has the message, stderr `''`).

**Reusable technique to reach this real failure through `write()`, which
normally CAN'T hit it** (every real `write()` call inserts a fresh index
line, so the file always differs from HEAD): commit the seeded index files
as a real baseline first (`git add -A` + commit, so working tree == HEAD),
then `monkeypatch.setattr(notes.indexes, "insert", noop)` so the internal
index-mutation step never touches the file. `git add` then has nothing new
to stage and the real `git commit` that follows fails for real with
"nothing to commit" -- git itself still produced the failure; only the
internal bookkeeping step was neutralized. Same "reach through the real
module attribute" pattern as the existing `notes.gitcmd`/`notes.indexes`
monkeypatches in this file, not a new pattern.

`write_work()` needed no monkeypatch at all: passing an already-committed,
byte-identical path is a completely natural way to reach the same real
failure (e.g. re-running a publish step with nothing changed).

**Probe simplification found here:** once the whole working tree is
byte-identical to HEAD, a real `git commit -m msg` probe reproduces the
identical "nothing to commit, working tree clean" text whether or not a
pathspec is given -- verified live both ways. No need to reconstruct the
exact single pathspec `write()`/`write_work()` used internally; a
plain `git commit -m sonda` after the attempt is enough as the anti-
fabrication (Sec.34) source of truth.

**One test, two surfaces, per orchestrator instruction ("una regresión"):**
bundled `write()` and `write_work()` assertions into a single test
function, same precedent as this file's existing
`test_regression_blank_line_in_folded_field_survives_real_git_commit_and_query`
(bundles by_id/by_zone/by_word checks) -- testing multiple entry points
that share one exact broken line is one regression, not several.

Confirmed RED for the right reason: fails at
`assert result.git_error.strip() != ""` (empty string), before ever
reaching the probe substring assertion. Stable across 3 repeated runs.
Other 9 rows/regressions in the file stayed green. Zero production files
touched (verified via `git status --porcelain -- lib/memory/`: `notes.py`
untracked, never written to this session).

See also: [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)
(the sibling `.git/index.lock`-forcing technique for a real git failure
that DOES fill stderr), [notes-three-critical-regressions-notes](notes-three-critical-regressions-notes.md)
(the `notes.gitcmd`/`notes.indexes` reach-through-real-module-attribute
monkeypatch convention this session reused).
