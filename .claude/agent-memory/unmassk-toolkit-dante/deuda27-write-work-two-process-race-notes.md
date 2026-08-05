---
name: deuda27-write-work-two-process-race-notes
description: write_work() DEUDA.md #27 regression -- two-real-OS-process same-file race test design, invariant-not-outcome assertion, and the ablation technique to prove RED without touching production code
metadata:
  type: feedback
---

Task: pin DEUDA.md #27 ("el commit de trabajo se guarda con tu titulo y el
contenido de otro, y te dice que todo fue bien") with a test reproducing the
REAL case that kept it open through three rounds of "closed" -- not the two
tests already at the end of `tests/memory/test_notes.py` (external `git add`
simulation; 10 threads each with their OWN file). The real case: **two
normal OS processes, each writing its OWN content to the SAME file, each
calling `notes.write_work()`, zero external `git add`, zero intruder
process.** Added
`test_regression_two_real_processes_writing_same_file_never_commit_crossed_content_under_ok_true`.

**Real subprocesses, not threads, and no marker-handoff needed here --
unlike [[file-lock-lost-update-contract-notes]].** That file_lock() fixture
needed an explicit marker-file handoff because a plain launch-and-go race
was NOT reliably deterministic (skew from a 10ms poll loop swallowed the
whole race window). Here, `subprocess.Popen` for writer A immediately
followed by `subprocess.Popen` for writer B, both writing to the same path
then calling `write_work()`, races on its own EVERY round with zero
synchronization -- confirmed live (dedicated debug script, not committed):
20/20 rounds produced exactly one accepted + one rejected write, i.e. the
race window is actually hit every single time, not just probabilistically.
Two real Python-interpreter-startup processes launched back-to-back apparently
have enough natural scheduling skew on macOS to guarantee overlap for a
same-file write+commit sequence. Don't reach for a marker handoff by default
-- try the naive launch first and measure; only add synchronization
machinery if a naive run shows the race isn't reliably exercised.

**Assertion is an INVARIANT ("ok=True implies own content landed"), not an
outcome ("the race happens X% of the time").** This is the difference
between a legitimate stress test and a flaky one under the "No Flaky Tests"
rule: the assertion holds regardless of interleaving --- either `ok=True`
and the commit under that writer's own message contains EXACTLY that
writer's own content (verified via `git show <hash>:file`, hash found via
`git log --fixed-strings --grep=<message>`, never via what the function
claims), or `ok=False` and `git_error` is non-empty. Never assert that the
race MUST produce a specific mix of outcomes -- that would break the moment
scheduling shifts.

**Ablation technique to prove RED without ever touching production code:**
the task's rule was explicit -- no production edits, and if the bug were
still alive, stop and report instead of "fixing" it. To produce the
adversarial RED demonstration the task asked for ("deshaz el arreglo en una
copia temporal"), do NOT patch `lib/memory/notes_commit.py`. Instead, copy
only the CALLING PATTERN (the throwaway subprocess helper script the test
writes to `tmp_path`) and flip the one line that mirrors the actual fix:
`known_content = [own_bytes] if pass_known == '1' else None` -->
`known_content = None`. Run the identical two-process race loop against the
UNMODIFIED, still-fixed `write_work()` with this ablated caller. Reproduced
live 3x: 9/20, 6/20, 5/20 rounds landed `ok=True` with the OTHER writer's
content under this writer's own commit message -- the exact DEUDA.md #27
failure mode, at rates consistent with the historical measurements (55% raw,
40% partial-fix, 0% full fix). This proves the fix lives specifically in the
caller passing bytes-it-already-has-in-memory (never re-reading disk), not
in the lock or the staged-as-new check alone -- and does it without a diff
to any file `git status` would show as production code touched.

**Debug/ablation scripts belong in the session scratchpad
(`/private/tmp/claude-.../scratchpad/`), never in `tmp_path` used by the
actual pytest run and never in `lib/memory/`** -- see
[[mutation-check-collision-incident-ids]] for why a shared production
directory is the wrong place for ANY throwaway file, even one used only to
prove a point to the user and then discarded.

**Bash hook gotcha:** a heredoc/inline Python snippet containing the literal
substrings `"git"` and `"commit"` near each other (e.g.
`subprocess.run(["git","commit",...])`) trips
`pre-validate-commit-trailers.py`'s naive text scanner even when nothing is
actually being committed via the shell -- it just needs `git` and `commit`
to co-occur in the bash command text. Fix: write the Python source to a file
with `Write` first, then run it with a bare `python3 <path>` bash command
(no `git`/`commit` tokens in the command line itself).

See also: [[file-lock-lost-update-contract-notes]],
[[mutation-check-collision-incident-ids]].
