---
name: boot-git-object-corruption-contract-notes
description: boot.py/health.py/query.py RED contract for a real corrupted .git/objects loose object crashing the whole boot report; the surgical corruption technique that isolates ONLY the rules-coherence check (git log/by_zone keep working); a live Bash-tool safety incident from a failed `cd` running destructive commands against the real repo cwd instead of a scratch repo
metadata:
  type: feedback
---

Session 2026-08-24, `tests/memory/test_boot.py`. Task: pin a KNOWN bug
(Yoda) -- `query.show_file_at_head()`/`query.by_zone()` can raise
`RuntimeError` on a real git failure, and that exception used to climb
uncaught through `health.coherence_rules()` -> `health.build()` ->
`boot.build()`, replacing the ENTIRE boot report with
`bin/memory/boot.py::_leave_a_failure_marker`'s failure banner (Next,
blockers, restrictions, everything -- gone, for a fault in ONE check).

**The surgical corruption technique -- reusable for any future
"real git failure, not simulated" contract in this project:** don't
delete or touch `HEAD`/refs. Resolve the real blob SHA for the file
under test (`git rev-parse HEAD:<relpath>`), locate its loose object
(`.git/objects/<sha[:2]>/<sha[2:]>`), `chmod(0o644)` (loose objects are
written read-only) and overwrite its bytes with garbage. Verified live
in a disposable repo before writing the test: `git cat-file -e
HEAD:<relpath>` (existence-only check) STILL returns `returncode == 0`
after this corruption -- git's `-e` flag apparently doesn't need to
fully inflate the object to answer "does it exist" for a tree-resolvable
path -- while `git show HEAD:<relpath>` (content read) fails for real
with `error: inflate: data stream error (incorrect header check)` /
`fatal: loose object <sha> ... is corrupt`. `git log --oneline` is
UNAFFECTED (log never reads blob content, only commit metadata). This
is exactly the shape of `query.py`'s two-step design
(`_exists_at_head()` via `cat-file -e`, then `show_file_at_head()`'s
`git show` only if existence said yes) -- and exactly why THIS
corruption reaches the `RuntimeError` branch instead of the silent
`_exists_at_head() -> False -> ""` early-return: a corrupted object
still "exists" by the cheap check, so the code proceeds to actually
read it and hits the real failure. A vaguer corruption (deleting the
object file entirely) would have been swallowed silently instead --
picking the RIGHT corruption for the RIGHT crash mattered here.

**Why this test isolates ONLY the rules-coherence check, not the whole
boot pipeline:** corrupting `rules.md`'s blob leaves `git log` (used by
`query.by_zone()`/`by_id()` for every note read, both in `boot.build()`
directly and inside `health.coherence()`) completely untouched -- so a
note seeded AFTER the corruption still writes and renders normally
(restrictions/blockers/COUNTS stay real). Only `health.coherence_rules()`
-> `query.show_file_at_head()` touches that specific blob. This produced
a much sharper contract than "corrupt everything and hope for a generic
warning": the test asserts the OTHER two CHECKS lines (duplicate IDs,
index coherence) stay real and correct, proving the degrade is scoped to
the one check that actually failed, never a blanket "something broke,
who knows what" message.

**Ground truth for the expected git-error text, never hand-typed
[unmassk-standards Sec.34]:** the corruption helper fires its OWN probe
(`git show HEAD:<relpath>` against the just-corrupted object) and
returns that REAL stderr; the test's final assertion takes the last
line of THAT captured text (`real_git_error.strip().splitlines()[-1]`)
and checks it's a substring of the rendered report -- same technique
lineage as [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)'s
"probe fires a second real git op against the same broken state and the
test compares against ITS stderr", generalized from `index.lock` staging
failures to a corrupted loose object.

**Multi-agent concurrency turned this RED test GREEN mid-session, by
design (test-first mode, "Ultron lo arregla en paralelo"):** the first
run (right after writing the test) crashed with the real uncaught
`RuntimeError` from `query.py:281`, confirming RED for the right reason.
A later run (same test, unchanged) passed clean -- `git status
--porcelain` showed `health.py`/`boot.py`/`query.py` had picked up
uncommitted edits mid-session (a new `HealthReport.rule_discrepancies_error`
field, `health.build()` wrapping `coherence_rules()` in `try/except
RuntimeError` exactly like it already did for `plans_unreflected()`, and
`boot._avisos_block()` printing "no se pudo comprobar si las reglas
coinciden con git: <error>" instead of a fabricated "rules match git").
Confirmed the fix landed for real (not a fluke) by rerunning 3x more,
all green, and by reading the actual diff -- Ultron's wording matches
the contract's assertions almost verbatim. **Lesson: in this repo's
current phase (heavy parallel agent activity, several unrelated
in-flight refactors uncommitted at once -- I-003 rules.py split, D-054
textnorm, this git-corruption fix, notes_commit/zones.py consolidation
-- all landed in the SAME working tree during ONE session), `git status
--porcelain -- lib/memory/` before drawing any conclusion about "is this
still red" is mandatory, not paranoia -- the ground under a test can
shift while you're still writing assertions for it.**

**Live safety incident, corrected before any harm -- worth repeating
verbatim for the next session:** the FIRST attempt to build a disposable
corruption-probe repo used `cd "$SCRATCH/.../repo"` followed by several
`git ...` commands with no explicit target, inside a SEPARATE Bash tool
call from the one that created the directory. The `cd` failed silently
("no such file or directory" -- the directory from the prior call never
actually persisted, matching this project's own documented rule that
"Agent threads always have their cwd reset between bash calls"), but the
script kept running anyway and every subsequent `git`/`echo > objpath`
command executed against THIS repo's real `cwd` instead -- including an
attempted `echo -n "garbage" > .git/objects/<sha>/<rest>` targeting the
REAL toolkit's own `rules.md` blob. It failed only because git objects
are written read-only (`chmod 444`) and the write hit `Permission
denied` before any byte changed -- confirmed after the fact with `git
status --porcelain` (only pre-existing dirty files, no diff on
`rules.md`) and `git fsck` (only ordinary dangling objects, no corruption
reported). **Fix applied for the rest of the session and going forward:
never rely on a bare `cd` + subsequent bare `git ...` inside a
disposable-repo script. Use `git -C "$WORK" ...` (or an explicit
absolute path per command) for EVERY git invocation against a scratch
repo, and add an explicit `[ "$(pwd)" = "$WORK" ] || exit 1` guard before
any write that touches `.git/objects` by hand** -- a destructive
operation must name its target explicitly, never trust an implicit `cd`
that might not have taken effect.

**Point 2 of this same task (verify Ultron's notes_commit/notes
consolidation + zones.py split leave the suite untouched) --
confirmed, no isolated "before" run possible:** both refactors were
already applied (uncommitted) in the working tree by the time I reached
this part of the task, done in parallel per instructions -- with no
`git stash`/`reset` allowed on unstaged work, there was no way to get a
true isolated "before" snapshot. Verified instead via: (1) `git diff
--stat` on `tests/memory/test_notes.py` (99 insertions, 0 deletions --
pure addition) and `test_zones.py` (only a D-054-unrelated addition
block + one import line, zero deletions tied to the zones split itself)
-- neither refactor rewrote or removed a single existing test; (2)
`zones.py` shrank 311 lines while three new siblings
(`zones_commit.py`/`zones_load.py`/`zones_query.py`, 130+88+78=296
lines) appeared, consistent with a facade split, not a rewrite; (3) full
suite `1184 passed, 2 skipped, 0 failed` (`unmassk-toolkit/tests -q`,
~150s) both right after and in a repeat run -- stable, not flaky; (4)
`test_boundary.py` (the module public-symbol-surface guard) green,
confirming the split didn't leak or drop a public symbol. One genuine
test-coverage gap WAS found and already closed by someone else in
parallel before I got to it:
`test_notes.py::test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree`
-- the shared `stage_and_commit()` "hook rejects mid-commit, index must
end up fully clean" regression previously had only ONE test in the whole
suite (via `rules.py`), never through `notes.write()`, one of
`stage_and_commit()`'s three other real callers. Its own comment credits
"auditoria de mutaciones, hallazgo real, relayado por el coordinador" --
this was NOT something I needed to add; verified it already existed and
passes.

Verification commands used: `python3 -m pytest
unmassk-toolkit/tests/memory/test_boot.py -k corrupted_git_object -q`
(RED then GREEN, see above); `python3 -m pytest
unmassk-toolkit/tests/memory/test_notes.py
unmassk-toolkit/tests/memory/test_zones.py
unmassk-toolkit/tests/memory/test_boundary.py -q` (62 passed); full
`unmassk-toolkit/tests -q` (1184 passed, 2 skipped).

See also: [notes-contract-real-git-failure-notes](notes-contract-real-git-failure-notes.md)
(the `index.lock` sibling of this same "real git failure, never
simulated" family) and [health-contract-notes](health-contract-notes.md)
(the `gh`-failure isolation precedent `plans_unreflected_error` that
`rule_discrepancies_error` mirrors almost verbatim).
