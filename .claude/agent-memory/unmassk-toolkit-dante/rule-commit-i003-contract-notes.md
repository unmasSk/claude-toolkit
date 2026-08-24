---
name: rule-commit-i003-contract-notes
description: I-003 (2026-08-23) RED contract -- gitmem rule must commit for real or not claim "guardada"; reverses the 2026-08-06 no-commit decision, confirmed by a real owner incident, not a task invention
metadata:
  type: project
---

Contract file: `unmassk-toolkit/tests/memory/test_rule_commit_contract.py` (7
tests: 5 RED today, 2 green-as-regression-pin, for the right reasons in both
cases). Feature: `gitmem rule "<texto>"` must produce a REAL git commit
containing the rule before printing "guardada" -- today (`lib/memory/rules.py`,
2026-08-06 decision) `add()` never touches git at all, one atomic file write
and done. See also [[rule-quote-contract-notes]],
[[gitmem-rule-no-commit-contract-notes]] (the very decision being reversed).

**This is a real, evidenced reversal, not a hallucinated task request.**
Verified via `git log` (EXECUTED, not trusted from the task prompt): commit
`3b6590a` `[I-003][memory][skills] gitmem rule reports success without
committing the rule` followed by `582590c`, both dated 2026-08-23, same day
as this task. The owner filed this as a real incident
(`.claude/project-memory/INCIDENTS.md`), same channel used for every other
real order in this repo's history.

**Resolved same session, second pass:** the coordinator relayed the owner's
explicit confirmation ("la contradicción que señalaste queda resuelta por
el propietario... revoca la decisión de 2026-08-06. Manda lo que él
dice.") and ordered retirement of the class that pinned the old contract.
Retired `test_rule_script.py::TestRuleEndsUpInTheFileNotInAnOwnCommit` (3
tests) with a dated banner citing I-003, same style as the 2026-08-06
`_restore_file_best_effort` retirement precedent in `test_rules.py`.
Coverage check before retiring (no silent loss): 2 of its 3 tests'
value ("rule ends up in the file" / tree state) was already replicated
under the NEW contract by `test_rule_commit_contract.py::
TestGoodRuleEndsUpCommittedForReal::
test_kind_user_creates_exactly_one_commit_and_a_clean_tree`. The 3rd
(`test_a_later_gitmem_work_picks_up_the_pending_rule_line`) had no
new-contract equivalent -- its premise (a pending uncommitted rule line
for `gitmem work` to pick up) stops existing once `gitmem rule` commits by
itself -- and its only OTHER value (generic `work.py --path` commits an
arbitrary given path with real blob content) was independently already
covered by `test_work_script.py::
TestAcceptsAllFlagsWithoutBouncingAndCommitsExactlyGivenPaths::
test_two_paths_and_an_issue_trailer_in_one_call` (verified by reading that
test, not assumed). Retired without replacement, explained in the banner.
`python3 -m pytest unmassk-toolkit/tests/memory -q` after retirement:
524 passed, 1 skipped, 5 failed (the 5 RED-for-the-right-reason contract
tests, unchanged -- Ultron had not finished implementing at time of this
check).

**Closed out, third pass same session:** Ultron finished (`rules.add()`
now commits for real, contract file 7/7 green, confirmed by the
coordinator). Two more stragglers surfaced in files the first task never
named -- both found by the coordinator, not by me re-grepping, a reminder
that a targeted retirement pass should still expect siblings in adjacent
files written by earlier sessions before the reversal:
- `test_rules.py::test_add_writes_the_file_and_creates_no_commit` +
  `test_add_leaves_the_rules_file_as_an_uncommitted_modification` --
  REWRITTEN in place (not just retired): decided these were worth pinning
  at LIBRARY level (`rules.add()` called directly, not through the
  script) because `test_rule_commit_contract.py` only ever exercises the
  contract through `bin/memory/rule.py` as a subprocess -- "add() itself
  commits" was a real gap, not redundant coverage. New names:
  `test_add_creates_exactly_one_real_commit_containing_the_rule` (HEAD
  commit count + `git show HEAD:<path>` blob content) and
  `test_add_leaves_the_rules_file_clean_in_git_status` (`git status
  --porcelain` empty). Banner above them cites I-003 and the exact owner
  words relayed by the coordinator.
- `test_rule_quote.py::TestUserRuleWithQuoteIsSavedWithBothTexts::
  test_a_successful_add_moves_no_head_and_leaves_the_file_uncommitted` --
  RETIRED without replacement: its coverage (kind=user, real `--quote`,
  script-level, HEAD/tree state) was already fully replicated by
  `test_rule_commit_contract.py::TestGoodRuleEndsUpCommittedForReal`
  (both the clean-tree test and the blob/message test use a real quote).
  Also updated this file's own pre-existing "CONTRADICCION DETECTADA...
  reportada, no resuelta" module docstring note (written by an earlier
  session, predating I-003) to mark it resolved rather than deleting the
  trail -- kept the full original reasoning for why it wasn't assumed at
  the time, appended the resolution.

Final verification (EXECUTED): `python3 -m pytest unmassk-toolkit/tests/memory -q`
→ **528 passed, 1 skipped, 0 failed**. Also ran the 4 rule-related files
together in isolation (38 passed) to confirm the rewrite/retirement
didn't leave anything orphaned. Coordinator had warned of a parallel
session committing to the real repo and a possible "HEAD guardian"
teardown error in the suite -- none occurred (0 failed, clean run), so
nothing needed double-checking beyond confirming the final count.

**Historical precedent surfaced, not reused verbatim:** `rules.py` already
documents (retired 2026-08-06) a rescue mechanism for exactly this failure
mode -- `_restore_file_best_effort`, which reverted/deleted the file on a
failed second-step commit. The new I-003 contract, read literally, only
requires "no success message + real error visible" -- it does NOT require
file rollback. Noted as a design option for whoever implements, not assumed
or tested as a requirement (would be inventing spec beyond what was asked).

**"con su número" (task's point 1) has no referent anywhere in the system.**
Checked `docs/deprecated/memoria-v2/TEXTOS.md` Sec.1.11b (the actual rejection
text, already implemented byte-for-byte in `rule.py::_render_similar_rejection`)
and Sec.1.6 (notes' sibling rejection) -- neither shows a numeric id for a
candidate, both show the full text instead ("ensena las notas candidatas
enteras en vez de sus identificadores"). Rules have no id field at all. Did
NOT invent a numbering scheme to satisfy the literal task wording -- tested
what's actually specified (owner + full text + relaunch instructions),
flagged the mismatch instead of guessing.

**Real git-commit-failure technique reused (not reinvented):** `.git/index.lock`
planted for real before running the script, same pattern as
`test_work_script.py`/`test_next_script.py`/`test_remove_script.py`/
`test_wip_script.py`/`test_notes.py`. Two of the seven tests in this file
pass TODAY even before Ultron touches anything -- verified this is not
vacuous: `test_index_lock_leaves_no_new_commit_behind` and
`test_missing_quote_still_bounces_before_touching_git` both pin invariants
that are already true in production (no git touch on a validation rejection)
and must REMAIN true once commit logic is wired in -- legitimate regression
guards, not RED-for-the-sake-of-RED. Confirmed with `pytest -v`, both listed
PASSED individually, and confirmed all 37 pre-existing sibling tests
(`test_rule_script.py`/`test_rules.py`/`test_rule_quote.py`) still pass
unaffected by adding this file.

**Commit-message assertion grounded in an existing documented constant, not
invented:** `rules.py`'s own docstring fixes "FORMATO DEL COMMIT ... Sec.9.7"
as `[remember][<kind>] <emoji> <texto>` -- literally the same string
production already computes as `subject` (the line written to the file).
Asserted the eventual commit message *contains* this prefix + emoji + text
(substring, not exact-string equality) rather than fabricating an unrelated
message format -- low-risk because it's the module's own pre-existing
documented contract, not a guess.

**Fourth pass, same session: two Cerberus/Argus-confirmed live repros, RED-first (Ultron working in parallel).**
Added two library-level tests (`rules_lib.add()` called directly, not
through the script) to `test_rule_commit_contract.py`:
- `TestFailedCommitLeavesNoStagedLeftovers::
  test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree` --
  plants a real `.git/hooks/pre-commit` with `exit 1` (new helper
  `_forced_pre_commit_hook_rejects`, sibling to `_forced_git_index_lock`)
  AFTER a real seed save, so `git add` succeeds but the commit step
  fails -- the scenario `.git/index.lock` can't reach (that blocks add
  too). Contract: `ok=False`, `git_error` non-empty, `git status
  --porcelain -- rules.md` fully clean (guards the "MM" index/worktree
  desync bug).
- `TestFirstEverRuleWithFailedCommitLeavesNoOrphanFile::
  test_index_lock_on_a_fresh_repo_leaves_no_rules_file_behind` -- fresh
  repo, no `rules.md` yet, `.git/index.lock` forced. Contract: `ok=False`
  and `rules.md` does NOT exist afterward (guards the header-only orphan
  file bug).

**Real gotcha hit while writing test 1, worth remembering:** typing the
literal words for "save a snapshot" directly into Bash inside a scratch
temp repo (to manually verify real git's stdout/stderr split for a
silent `exit 1` hook) gets intercepted by the Bash tool's own guard and
returns a synthetic "esto crea un commit fuera de gitmem" denial -- this
is a TEXT-PATTERN-matched tool-layer safety net on the literal command
string I type, not a real git hook and not execution-tracing: it even
fired once on a `cat >> file <<EOF` heredoc whose PROSE happened to
contain that same two-word phrase, blocking the whole append before
anything was written. It does NOT apply to subprocesses a test file
spawns internally (`gitcmd.py`'s own `subprocess.run([...])` calls run
for real, unblocked -- confirmed, that's how these tests produced real
RED/GREEN results). Lesson: don't try to manually reproduce git
subprocess behavior via that literal phrase in raw Bash in this
environment, and avoid the phrase even in prose/memory notes going
into a Bash heredoc -- use the Edit/Write tool for memory files instead.
Trust the pytest run's real subprocess results for what git actually
does.

Both tests were RED against the code as it stood right after the
previous close-out (empty error text for a silent hook rejection;
header-only orphan file with `.git/index.lock`). Ultron fixed both IN
PARALLEL before I finished writing this report -- rerunning showed all
9/9 green in `test_rule_commit_contract.py`. Fixes landed:
`notes_commit.stage_and_commit()` now runs `git reset -- <paths>` to
undo its own staging when the commit step fails; `rules.py` gained
`_restore_or_delete_best_effort()` (deletes the file instead of writing
a header-only orphan when it didn't exist before) and
`_GIT_COMMIT_FAILED_NO_MESSAGE` (non-empty fallback when git's own
stdout/stderr are both silent). Reported as "already green, Ultron beat
me to it" rather than silently declaring victory as if I'd verified a
red-then-green transition myself.

Final state this session: `python3 -m pytest unmassk-toolkit/tests/memory -q`
-> 530 passed, 1 skipped, 0 failed (528 -> 530, the 2 new tests).

**Fifth pass, same session: Moriarty broke the fix in two places, live repro relayed by the coordinator -- RED-first, Ultron working in parallel again.**
Three separate contracts, three files:

1. **`health.coherence_rules()` resurrection** -- new sibling file
   `test_health_rules_coherence_contract.py` (4 tests, all RED today:
   `AttributeError: module 'health' has no attribute 'coherence_rules'`).
   Retired 2026-08-06 alongside the no-commit decision it was built to
   detect; I-003 undoes the premise, so the function needs to come back.
   Read the HISTORICAL implementation before writing expectations
   (`git show 396e502^:.../health.py`) rather than guessing wording --
   both discrepancy strings ("existe en un commit de regla pero falta
   en el fichero..." / "esta en el fichero de reglas pero no existe en
   ningun commit de regla...") are copied verbatim from that commit, not
   invented. Three scenarios: clean (silent but real counts, same "mute
   check == no check" principle as `coherence()` row 3), a line
   added/edited by hand with no matching commit (both directions of the
   diff), and the exact shape of a killed-mid-write process -- built by
   hand in the seed repo using the SAME write primitive `add()` itself
   uses (`gitcmd.atomic_write`), proven via a real `git status
   --porcelain` read to confirm it's genuinely uncommitted, never
   faked any other way.
2. **External edit lost inside `add()`'s read-write window** -- added to
   `test_rule_commit_contract.py`. Reproduced with a real
   `threading.Event` handshake (no sleep-based race widening, learned
   from [[file-lock-lost-update-contract-notes]]): monkeypatched
   `pathlib.Path.read_text` (filtered by `self.name == "rules.md"`, not
   exact path equality) to signal "read done" and block until a second
   thread -- using RAW `open()`, deliberately bypassing `rules_lib` and
   its lock entirely, simulating a truly oblivious external editor --
   finishes its own write. **Real gotcha hit and fixed**: the FIRST
   version of this test failed for the WRONG reason (`add() nunca llego
   a leer el fichero`, i.e. the patched `read_text` never fired) because
   on a repo with NO `rules.md` yet, `add()`'s `if path.exists()` branch
   never calls `read_text()` at all (it uses the fixed header string
   instead) -- fixed by seeding one real baseline rule first so the
   SECOND `add()` call actually hits the read branch the race depends
   on. Contract: after `add()`, both the external line and add()'s own
   line present in the file AND in the real committed blob (`git show
   HEAD:<path>`) -- confirmed RED for the right reason: the external
   line was silently overwritten, exactly the described bug.
3. **`--quote` never sanitized** -- also in `test_rule_commit_contract.py`.
   A quote containing `\n` is accepted today (`ok=True`) even though it
   physically splits the written line in two, corrupting whatever comes
   after when re-read; an oversized quote (2000 chars, deliberately far
   past the rule text's own 200-char cap) is accepted today with no cap
   at all. Did NOT hardcode an assumed cap value for the oversized case
   (doesn't exist in production yet, Ultron picks it) -- asserted only
   that a real `Rejection` comes back with some digit in
   `title`/`body`, avoiding a fabricated-ground-truth guess per
   unmassk-standards Sec.34. A third test (normal quote still
   saves+commits) added in the SAME file as a regression pin so any
   future sanitization change is forced to keep the happy path green.

**Verified item 4 (previous 9 green stay green) explicitly, not
assumed**: ran `test_rule_commit_contract.py` alone with `-v` after
adding the 3 new tests -- the original 9 all show `PASSED` individually,
only the 3 new ones + the 4 in the new health file are RED. Full-suite
check: `python3 -m pytest unmassk-toolkit/tests/memory -q` ->
**7 failed, 531 passed, 1 skipped** (530 -> 531, the quote-regression
pin is the only new green; the other 6 new tests are the RED contract).

Also added a short pointer comment (not a rewrite) inside
`test_health.py`'s existing 2026-08-06 retirement banner for
`coherence_rules()`, noting the I-003 resurrection and pointing at the
new sibling file instead of touching the retired block itself.


**Sixth pass, same session: mutation-testing audit found a coverage gap,
not a bug -- closed one test in `test_notes.py`, revealed a REAL second
gap along the way.** The shared "commit fails after add already staged
the new content" guard inside `notes_commit.py` (the fix that keeps
`git status` from showing "MM") was pinned by exactly ONE test in the
whole suite, and only via `rules.py`
(`test_rule_commit_contract.py::TestFailedCommitLeavesNoStagedLeftovers`)
-- its other three real callers (`notes.write`/`replace`/`close`) had no
test of their own for this scenario. Added
`test_notes.py::test_commit_rejected_by_pre_commit_hook_leaves_a_fully_clean_tree`,
same seed-then-hook pattern as the rules.py sibling (a real successful
`notes.write()` first to leave one index file committed, THEN a real
`.git/hooks/pre-commit` with `exit 1` planted only for the second call).
Copied the hook-forcing contextmanager into `test_notes.py` itself
(`_forced_pre_commit_hook_rejects`) rather than importing across test
files -- each contract file mounts its own seed repo, no cross-file test
coupling.

**Not born green -- found a real, narrower gap than expected, verified
with a disposable probe script (not by guessing) before trusting it.**
`result.git_error` comes back as `''` (empty string) for `notes.write()`
against a silent (`exit 1`, no output) hook -- the exact I-003 symptom
("ok=False without a visible reason"), because the non-empty fallback
message (`_GIT_COMMIT_FAILED_NO_MESSAGE`) that closed this for `rules.py`
lives LOCALLY inside `rules.py::_commit_or_restore()`, never inside the
shared `notes_commit.py`/`notes.py`, so it never reached `notes.write()`/
`replace()`/`close()`. Confirmed with a throwaway script (python3, ad hoc,
in the scratchpad dir, deleted after) that the OTHER two invariants the
coordinator asked for are already fine for `notes.write()`: index content
byte-identical to before, and `git status --porcelain` on the affected
index file genuinely empty (no "MM") -- the shared `stage_and_commit()`
reset-on-failure fix IS correctly shared and already protects `notes.py`
too. Only the message-visibility half of the contract is red; reported
precisely instead of a vague "still red."

**Full-suite side effect observed, out of scope for this pass, flagged
not silently ignored**: `python3 -m pytest unmassk-toolkit/tests/memory -q`
after this change shows a SECOND failure I did not cause --
`test_boot.py::test_checks_block_never_mentions_rules_after_a_normal_add`
-- confirmed via `git status`/`git diff` that `test_boot.py` itself is
untouched by me; `lib/memory/boot.py` and `lib/memory/health.py` are
modified (Ultron's parallel round-3 work resurrecting
`coherence_rules()`, requested in the previous pass -- see the
`test_health_rules_coherence_contract.py` entry above). That old test
was written specifically for the "coherence_rules retired" world and
will need the same kind of reconciliation Ultron already did once before
(2026-08-06 cascade, documented in
[[gitmem-rule-no-commit-contract-notes]]) once boot.py's CHECKS block
starts mentioning rules again -- not this task's file, not touched here.

Final count this pass: `2 failed, 537 passed, 1 skipped` (one is my new
RED regression test doing its job; the other is Ultron's in-flight
parallel work, unrelated to `test_notes.py`).

**Seventh pass, same session: last red of the suite, and it was mine to fix.**
`test_boot.py::test_checks_block_never_mentions_rules_after_a_normal_add`
pinned the literal pre-I-003 world ("CHECKS never mentions rules") --
Ultron's authorized resurrection of `health.coherence_rules()` (previous
pass) made `boot.py` paint "rules match git"/"rules do not match git"
again in CHECKS, which is the new CORRECT behavior, not a regression.
Rewrote it (banner citing I-003, same style as the other rewrites this
session) as `test_checks_block_shows_rules_match_git_after_a_normal_add`
(a normal committed add -> green "rules match git", no warning) and
added its cheap sibling, `test_checks_block_warns_when_a_rule_line_is_
uncommitted` (a hand-appended orphan line, same `gitcmd.atomic_write`
bypass technique as `test_health_rules_coherence_contract.py` -> "rules
do not match git", naming the orphan text). Checked before writing the
sibling: `test_health_rules_coherence_contract.py` only exercises
`health.coherence_rules()` as an isolated library function, never
`boot.build()`/`boot.render()`'s actual CHECKS text -- no duplication,
different layer (end-to-end render vs. isolated function).

Read `boot.py`'s real render code (lines ~536-546) before asserting
anything, rather than guessing the label text: `rule_numbers =
f"{report.rule_file_lines} lines / {report.rule_head_lines}
committed"`, `"✓  rules match git (...)"` / `"⚠️  rules do not match
git (...)"` -- copied the exact literal strings Ultron's implementation
produces, not invented.

Final verification this session, full suite:
`python3 -m pytest unmassk-toolkit/tests/memory -q` -> **540 passed,
1 skipped, 0 failed**. Also confirmed the OTHER red from two passes ago
(`test_notes.py::test_commit_rejected_by_pre_commit_hook_leaves_a_fully_
clean_tree`, empty `git_error` for a silent hook) is now green on its
own -- Ultron fixed the shared message-visibility gap in the meantime,
verified by re-running that single test in isolation rather than
assuming from the aggregate count.

**Eighth pass, same session: Moriarty broke the resurrection at an edge,
verified the root cause independently before writing a single assertion.**
Coordinator relayed: first-ever rule of a project (`rules.md` written to
disk, never committed at all -- the exact kill-mid-write state) made
`coherence_rules()` raise `RuntimeError` instead of reporting the gap,
because `query.py::show_file_at_head()` only recognized git's "does not
exist in" wording, not the DIFFERENT wording git uses when a path exists
on disk/worktree but was never committed. **Did not trust the relay
blindly** -- reproduced the exact git error with a disposable throwaway
script (subprocess, real repo, deleted after) before writing any test:
confirmed `git show HEAD:<path>` for this exact state returns
`returncode=128`, `stderr="fatal: path '...' exists on disk, but not in
'HEAD'\n"` -- genuinely different wording from the already-handled
marker, exactly as claimed.

Added to `test_health_rules_coherence_contract.py`:
`TestFirstEverRuleNeverCommittedDoesNotCrash` -- two tests: (1)
`coherence_rules()` called directly reports `(0, 1, (<the orphan text
named>,))` instead of raising, with a git-show precondition check
proving the exact failure shape before trusting the rest of the test;
(2) the FULL pipeline (`boot.build()` -> `boot.render()`) doesn't crash
either and paints the normal `"rules do not match git"` warning in
CHECKS, naming the orphan text -- the surface the coordinator said
actually matters (a crash there replaces the WHOLE report with a
failure banner, worse than the original I-003 silence). Both tests were
**already green when run** -- Ultron had already patched `query.py`'s
marker recognition in parallel before I finished; reported as such, not
claimed as a verified red-to-green transition.

**Point 2 ("de regalo si es barato") evaluated, declined, explained in
a comment instead of forced**: every realistic construction of "a
committed `rules.md` that HEAD lost via a weird commit" (`git rm
--cached` + amend, or a `reset --hard` to before the file existed)
reduces to one of the two shapes already covered -- either the exact
"exists on disk, not in HEAD" case just fixed, or the "doesn't exist
anywhere" case `TestRepoWithoutAnyRuleYetDoesNotCrash` already covers.
Wrote this reasoning as a code comment in the test file rather than
manufacturing a third test that would prove nothing new -- matches the
coordinator's own instruction ("si no lo es, dilo y no lo fuerces").

**Documented, did not add, the race boundary for
`TestExternalEditLandingInsideAddIsNeverLost`** (previous pass): checked
that production (`rules.py::add()`) already closes the race via a named
helper called TWICE (`_read_current_rules_content()`, an early read plus
a final reread right before `atomic_write()`), and that my existing
test's `Path.read_text` patch (filtered by `self.name == "rules.md"`)
fires on BOTH calls -- the external write is released during the FIRST
(early) read, so by the time the SECOND (final reread) runs it already
picks up the fresh content. That means my existing test already pins
exactly the CLOSED half of the contract (an edit landing before the
final reread). Added a documentation-only comment block (no new test)
marking the remaining open half -- an edit landing inside the single
final-reread-to-write instant -- as explicitly out of contract, since
closing it would need real filesystem-level compare-and-swap this
project doesn't have or need (single-owner threat model). Followed the
instruction literally: "si tu test actual ya pina justo la mitad
cerrada, di que basta y no añadas nada."

Final verification, full suite: `python3 -m pytest
unmassk-toolkit/tests/memory -q` -> **542 passed, 1 skipped, 0 failed**
(540 -> 542, the 2 new coherence_rules-crash tests; both already
green).

**Ninth pass, same session: latent midnight-crossing flake in an
unrelated test file, fixed at the source, not swept.** Coordinator
reproduced in isolation: `test_search_script.py::
TestByIdRule3BothZonesWithTheNotesOwnWriteDate::
test_both_zones_and_the_real_write_date_share_one_line` compares a
report's `"escrita <date>"` line (always rendered in UTC, house
convention) against `git log --format=%aI`'s first 10 characters --
`%aI` is LOCAL time with offset, so in the 22:00-00:00 UTC window for
any positive-offset timezone (Madrid UTC+2, this exact session:
2026-08-23 UTC / 2026-08-24 local) the naive prefix already rolled to
the next day while the UTC render hadn't. Fixed by parsing the ISO
string with its real offset (`datetime.fromisoformat`,
`.replace("Z", "+00:00")` first) and converting to UTC before
comparing -- did NOT touch production (rendering in UTC is the house
convention, correct as-is). Production untouched, only
`test_search_script.py`.

**Reused an established project idiom instead of inventing one:** the
`.replace("Z", "+00:00")` guard before `fromisoformat` is the SAME
pattern already used project-wide (`health_plans.py`, `context.py`,
`query.py`, documented centrally in `lib/memory/timefmt.py`) because
this repo's CI pins Python 3.10, which cannot parse an ISO "Z" suffix
with `fromisoformat` (support landed in 3.11) -- git's `%aI` legitimately
emits `Z` for a zero-offset commit. Read `timefmt.py` before writing
the fix specifically to avoid reintroducing that already-known,
already-fixed-elsewhere landmine in a NEW place. Verified the fix
actually closes the gap with a throwaway calculation (not just "it
passes right now, because it's not midnight"): fed the exact scenario
(`"2026-08-24T00:30:00+02:00"`, local just past midnight, UTC still on
the 23rd) through both the OLD buggy prefix-slice (`"2026-08-24"`,
wrong) and the NEW conversion (`"2026-08-23"`, correct) side by side.

**Swept the rest of the suite for the same bug shape, found none.**
Grepped every `%aI`/`%ai`/`%cI`/`%ci`/`%ad` occurrence (4 total besides
this one: `test_health.py:762`, `test_context.py:225`, `test_query.py:479`)
and the exact truncation idiom (`[:10]`, only this one occurrence
system-wide) plus every consumer of the rendered `"escrita "` label
(only this file). The other three all force `GIT_AUTHOR_DATE`/
`GIT_COMMITTER_DATE` to an explicit `+00:00` and only assert the
montage produced a `Z`-suffixed commit (a *different*, deliberate
Python-3.10-`Z`-parsing regression test, unrelated to local-vs-UTC
date comparison) -- none of them slice a local-offset date and compare
it against UTC-rendered text. No other instance of this bug found or
fixed.

Final verification: single test green
(`test_both_zones_and_the_real_write_date_share_one_line`), full file
`test_search_script.py` 20/20 green, full suite
`python3 -m pytest unmassk-toolkit/tests/memory -q` -> **542 passed,
1 skipped, 0 failed** (unchanged count from the previous pass -- this
was a fix to an existing test, not a new one).