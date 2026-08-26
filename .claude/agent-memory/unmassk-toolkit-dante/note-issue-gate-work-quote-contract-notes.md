---
name: note-issue-gate-work-quote-contract-notes
description: note.py Q/I issue-gate RED contract (D-065/D-066) -- --work no / --issue N / --issue none --quote, two structural CLI gaps found; Round 2 -- post-implementation harness repair across 19 tests in 10 files, all seeding Q/I with no --work
metadata:
  type: project
---

## Round 1 (2026-08-26) -- D-065/D-066 acceptance contract, test-first RED

Context: `unmassk-toolkit/tests/memory/test_note_issue_gate.py` (new file, 18
tests: 9 RED / 9 GREEN by design). Owner decision D-065/D-066 (recovered via
`gitmem search --id D-065`/`D-066`, not paraphrased): saving a `Q` or `I`
note without `--issue` AND without `--work` must bounce with a literal
"measuring stick" question (does closing this note need work -- code,
measuring, building -- or just an answer/decision?) plus three literal
relaunch options: `--work no` (answer only), `--issue N` (work with an
issue, proposed to the owner first, Claude creates it with `gh` on his
yes), `--issue none --quote "<owner's exact phrase>"` (work the owner
declined). D-066 refines: the `--issue none` refusal always needs the
owner's literal quote -- unlike `gitmem rule`'s own `--quote none` escape
hatch (Claude leaving himself a note), **there is no `--quote none` here**:
the no is always the owner's, always cited.

**Two structural CLI gaps found by reading production before writing
tests, not fixed here (limit: tests only):**
1. `bin/memory/note.py::_parse_args` declares `--issue` as `type=int`
   (line 102). The design needs `--issue none` as a literal string
   sentinel, same pattern `--replaces` already uses (no `type=`, distinguished
   from a real id via `args.replaces != "none"` in
   `_handle_write_or_replace`). Today `--issue none` dies in argparse itself
   ("invalid int value: 'none'") before any validator runs.
2. `--work` does not exist as an argparse flag at all yet -- any use, on
   any type, dies with "unrecognized arguments: --work ...".

Both gaps already give `rc != 0` today for accidental reasons; every RED
test in this file asserts the REQUIRED message content too (the measuring
stick text, the word "cita", the word "work" in the type-field rejection),
so none of them pass by coincidence of a non-zero exit code that predates
the real feature.

**Vocabulary check done before writing (not assumed):** `vocabulary.TYPES["Q"]`/
`["I"]` already carry `"issue"` in `allowed_fields` since D-044/D-045 (both
require only `"description"`) -- so "point 4" (`--issue N` alone still
works) and half of "point 6" (issue already legal on all 7 types) are
GREEN controls today, not new RED. `report_render_note.py::_note_fields`
line 96 (`if note.issue is not None:`) also confirmed ALREADY type-agnostic
today -- the M-only gap `test_note_issue_field.py` flagged for Ultron back
in D-044/D-045 round has since been fixed; `search.py --id` round-trips the
issue number for every type today already.

**"Nothing written" proven two ways, not just rc:** commit count
(`git rev-list --count HEAD`) and HEAD sha unchanged before/after every
rejection test in the class-1/2 group; PLUS a same-test follow-up: a valid
seed immediately after the rejected attempt must land as `<T>-001`, never
`<T>-002` -- proves the rejected attempt didn't consume an id from
`ids.next_id()` either (thematically related to
[[notes-py-full-contract-notes]]'s id-reuse incident, R-012, though that one
is about archived-id reuse specifically, a different mechanism).

**Round-trip technique for the quote (unmassk-standards Sec.34):** since no
`Note.quote` field or commit trailer label exists in production yet (`format.py::
_body_field_line` only knows `Why`/`Awaits`/`Keys`/`Description`/`Replaces`/
`Origin`/`Issue` -- confirmed by reading, `quote` isn't among them), the test
picks a single distinctive quote sentence (no shared words with the
headline/description, same discipline as `test_note_script_promotes.py`) and
asserts it appears VERBATIM in both the real `git log -1 --pretty=%B` commit
message AND in `search.py --id` output -- proves the round trip without
inventing a trailer label Ultron hasn't decided yet.

**Fake-gh technique reused as-is** from
[[note-py-script-full-contract-notes]] Round 7 (own local `_fake_gh_dir`/
`_env_with_fake_gh`, `path_without_real_gh()` PATH-sanitizing, Windows skip
marker) -- only needed for the "point 4" control class, since `--issue none`
never reaches `gh` at all (same bypass mechanism `--replaces none` already
uses for `validate_replacement`).

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_note_issue_gate.py -v`
-> 9 failed (all for the declared reason, confirmed reading each traceback:
`rc==0` where a rejection was required, or the required message text absent
from a structural CLI-error stdout/stderr) / 9 passed (4 "issue N already
works" + 5 "other five types unaffected", both honestly labeled as controls
in the file, not RED padding). Full `tests/memory` suite with the new file:
607 passed + 9 RED + 1 skipped + 1 unrelated error
(`test_zones_script.py::TestListDistinguishesAbsentFromEmptyZonesJson`,
confirmed pre-existing and order-dependent -- passes alone, and the run
without this new file is clean at 598 passed/1 skipped/0 errors).
`git status --porcelain` before/after: only this one new file touched.

Reference: [[note-py-script-full-contract-notes]] (Round 7, the `--issue`
opening this gate builds on top of; the fake-gh technique).

## Round 2 (2026-08-26, same day) -- Ultron shipped the gate, harness repair across 10 files

Context: Ultron implemented the gate from Round 1's contract (18/18 green).
The gate broke 19 PRE-EXISTING tests across 10 files, all one root cause
(Ultron's own finding, verified): the shared seeder
`conftest.py::seed_note_via_script` had no `work`/`quote` params, so every
Q/I seeded through it with no `--issue` hit the new gate cold.

**Fix shape, decided once and applied everywhere:** added `work=None`/
`quote=None` to `seed_note_via_script` (only appended to `args` when given
-- no silent default `--work no`, which would have weakened any FUTURE
test that wants to exercise the gate's rejection on purpose through this
shared helper). Local per-file helpers that build their own `note.py`/
`gitmem note` args by hand (`_seed_i`, `_write_i`, `_write_note`,
`_seed_question`, `_seed_incident`, three of them) got the same
`--work`/`work=` threading individually -- no second shared helper
introduced, matching this suite's existing convention of local per-file
seed helpers (see Round 1 above and
[[note-py-script-full-contract-notes]]).

**Went through all 19 one at a time before touching anything, per the
orchestrator's explicit ask ("decide con criterio") -- none of the 19 was
exercising the issue-gate itself.** Every one seeds a Q/I purely as setup
for an UNRELATED mechanism under test (archived-key-zone duplicate parity,
archived-similarity bypass, empty-keys-never-collide fence gate, the
seven-types smoke test, `--promotes`, the pain/overlap relaunch-amnesia
cycle, fence atomicity, the restriction question, chain-view edge cases,
DEUDA #24's search regression) -- confirmed by reading each failure's
assertions, not assumed from the file name. Threading `--work no` at
exactly those call sites (never a blanket default) keeps every one of
those tests still proving what it always proved, with the gate now
satisfied as an inert precondition.

**10 files touched, 1 shared + 9 local fixes:**
`conftest.py` (shared `seed_note_via_script`),
`test_customs_archived_key_zone_duplicate_parity.py` (`_seed_i`, all 6
call sites via one shared local helper),
`test_note_archived_similarity_bypass.py` (`_write_i`),
`test_note_exact_key_zone_duplicate_gate.py` (`_write_note` gained
`work=`, threaded at only the 2 call sites that seed type `I` -- the other
14 call sites in that file are type `M`, untouched),
`test_note_script.py` (`TestCreatesAllSevenNoteTypesForReal`'s inline
seven-type table, `Q`/`I` rows only),
`test_note_script_promotes.py` (`_seed_question`),
`test_relaunch_command_answer_amnesia.py` (`_seed_existing_similar_note`,
one call site -- the M under test itself needs no `--work`, only the Q
seeded as its overlap trigger did),
`test_remove_incident_close_fence_atomicity.py` (`_seed_incident`),
`test_remove_incident_close_question.py` (`_seed_incident` -- the file's
OTHER seed call, `test_closes_directly_without_any_restriction_question`'s
parametrized M/D table, was never affected: no Q/I row in it),
`test_search_chain_view.py` (2 of its ~12 `seed_note_via_script` call
sites -- the two chain-view edge-case classes that seed type `I`; the
rest of the file's calls were already unaffected, confirmed by running the
file green before touching anything else in it),
`test_search_script.py` (both seeds in the DEUDA #24 reproduction test).

Verification: `python3 -m pytest unmassk-toolkit/tests/memory -q`, run
TWICE as instructed -> both runs identical, `626 passed, 1 skipped` (608
pre-existing + 18 from Round 1's contract), zero failed, zero errors --
the `test_zones_script.py` flake noted in Round 1 did not recur either
time. `git status --porcelain unmassk-toolkit/` after: exactly the 10
files listed plus `conftest.py`, nothing outside `tests/memory/`.

## Round 3 (2026-08-26, same day) -- Moriarty T1: hooks/customs.py bypasses the gate entirely

Context: Moriarty broke the shipped gate (Round 2) in (at least) 4 points;
the coordinator's message was truncated after point 1 (point 2 cut off
mid-sentence at "gitcmd.py:71", points 3/4 never arrived). Per this
project's rule ("una pregunta cada vez... si no esta claro, se pregunta"),
did the one fully-specified point (T1, customs bypass) and stopped --
did not guess at points 2-4's content. New file:
`unmassk-toolkit/tests/memory/test_customs_issue_gate_bypass.py` (5 tests:
2 RED / 3 GREEN by design).

**The bug, confirmed by reading, not assumed:** `hooks/customs.py::
_decide_note()` (~line 683) only calls `validator.validate_note(note,
ctx)` -- never `validator.validate_issue_gate()` (the D-065/D-066 gate
from Round 1/2, real production since the previous pass). `validate_note()`'s
own docstring documents WHY: it deliberately excludes any check that needs
data outside `note`/`ctx` (`validate_pain_question`, `validate_issue`, and
now `validate_issue_gate` too) -- the hook never wired those special-signature
checks for ANY of them, and the issue gate inherited the same gap on day
one instead of anyone closing it for this new gate specifically. Live
repro (confirmed before writing tests): a raw `git commit -m` creating a
well-formed `I` with neither `Issue:` nor `Quote:` in the body -> hook
returns `{"decision": "approve"}`.

**`validate_issue_gate` is pure** (confirmed reading its own docstring --
unlike `validate_issue`, it never calls `gh`) -- no fake-gh technique
needed anywhere in this file, unlike [[note-py-script-full-contract-notes]]
Round 7's `--issue` contract.

**Technique reused as instructed** ("mira `test_customs_archived_key_zone_duplicate_parity.py`"):
same `run_customs_hook`/`HOOK_PATH` locals, same `_commit_command`, same
`model_mod`/`format_mod` fixtures building the EXACT commit message via
`format.build_message()` on a real `model.Note` -- never a hand-typed
string. Pitfall hit and fixed: two of the five candidate headline/description
pairs used an English contraction/possessive apostrophe ("hasn't", "customer's")
which collided with the file's own guard against single quotes in the
commit-command string (`assert "'" not in message`) -- not a production
bug, a test-fixture wording fix (removed the apostrophes).

**5 tests, same RED/GREEN split pattern as every other file in this
series:** RED x2 (I and Q, mirroring D-065/D-066 not distinguishing
between the two gated types) both assert `decision == "block"` PLUS the
literal `_MEASURING_STICK` text and all three literal relaunch options
(same constants as Round 1's contract, cross-checked against
`validator_issue.py`'s real strings -- now in production, confirmed
identical by reading). GREEN x3: parity control via `note.py` (already
rejects, proves something real to preserve), non-gated type (`D`) control
(fix must not touch types outside Q/I), already-answered-gate control (a
raw commit with a real `Issue: #N` must keep approving -- fix must not
overtighten).

Verification: `python3 -m pytest unmassk-toolkit/tests/memory/test_customs_issue_gate_bypass.py -v`
-> 2 failed (both `'approve' == 'block'`, the real bypass, not a
collection/import error) / 3 passed. Full `tests/memory` suite with the
new file: 629 passed + 2 RED + 1 skipped, zero collateral damage.
`git status --porcelain unmassk-toolkit/` before/after: only this one new
file touched (no `lib/`/`bin/`/`hooks/` edits, per the task's explicit
limit).

**Open, waiting on the coordinator:** points 2 ("un \r dentro de --quote
se corrompe al releer... gitcmd.py:71", cut off), 3, and 4 of Moriarty's
4-point break were never received in full -- not written here, not
guessed at.

Reference: [[note-py-script-full-contract-notes]] (fake-gh technique,
not needed here); Round 1/2 above (the gate this bypass sits on top of).

## Round 4 (2026-08-26, same day) -- points 2/3/4 arrived complete; coordinator flagged a collision on point 1 mid-task

Context: a NEW Dante instance (this one) got the full 4-point message
this time. Point 1 (customs bypass) was already covered by Round 3's
`test_customs_issue_gate_bypass.py` (2 RED/3 GREEN, still standing) --
mid-task the coordinator sent an explicit collision warning: another
Dante pass had already claimed point 1, do NOT touch that file or
`test_note_issue_gate.py`. Complied: verified via `git status --porcelain`
that neither file appears in this round's diff, reduced scope to points
2/3/4 only, one new file each (three new files total, none overlapping
Round 3's).

**Point 2 (T1) -- `\r` embedded in `--quote`, followed by a space, loses
a real character on round trip.** File:
`unmassk-toolkit/tests/memory/test_note_quote_carriage_return_round_trip.py`
(7 tests: 1 RED / 6 GREEN). Root cause chain, confirmed reading three
files before writing anything:

1. `format.py::_fold_raw` (`format.py:117-126`) folds on `"\n"` only --
   a lone `\r` (no adjacent `\n`) never triggers folding, so the commit
   body ends up with ONE physical line containing a raw `\r` mid-content
   (`"Quote: texto con CR\r dentro"`).
2. `gitcmd.py::run()` (`gitcmd.py:78-92`) reads git's stdout with
   `subprocess.run(..., text=True, encoding="utf-8", errors="replace")`,
   no way to pass `newline=""` through the high-level `subprocess.run`
   text-mode API -- universal-newline translation converts ANY `\r`
   (mid-line or not) to `\n` on decode, splitting that one physical line
   into two: `"Quote: texto con CR"` / `" dentro"`.
3. `format.py::_parse_fields` (`format.py:296`) treats a line starting
   with a single space as a folded continuation and strips that leading
   space (`line[1:]`) to undo real folding -- it cannot tell this
   accidental split from a real one, so the space that was genuine
   content (the character right after the `\r` in the original) gets
   eaten as if it were the continuation marker. Net loss: neither the
   `\r` nor the space that followed it survive; `Quote` ends up
   `"...CR\ndentro"` instead of `"...CR\r dentro"`.

Round-trip via `query.by_id()` (imported in-process via
`import_lib_memory_module`, called with `os.chdir()` into `tmp_repo` --
same `_cwd` context-manager pattern already fixed in `test_report.py`/
`test_notes.py`, since `query.by_id()` reads `Path.cwd()` with no `root`
param) -- an INDEPENDENT channel from what `note.py` itself already
parsed to print its own confirmation. A second test reads the SAME
commit via `git log --pretty=%B` captured in **binary** mode (no
`text=True`) to prove the `\r` genuinely survives inside the git object
itself -- isolates "lost at write" from "mistranslated at read", both
needed since the bug is specifically a READ-side translation, not a
write-side loss.

**Five non-corrupting controls fixed as regression, GREEN today,
verified live before writing:** accented/ñ text, an embedded emoji,
literal double-quote marks, a real `\n`-only multi-line quote (no `\r`),
and text starting with a real field label (`"Description: ..."`) --
`_parse_fields`'s single-leading-space rule already handles the last one
correctly today because a REAL fold always re-adds exactly one leading
space to a continuation line, and `field_re.match()` is checked BEFORE
the "starts with space" branch, so a folded continuation can never be
mistaken for a new field start. Plain CRLF (`\r\n`, no trailing space)
was tried live too and also loses its `\r` on readback, but was
DELIBERATELY left out of the file -- the task's control list named five
specific survivors, not CRLF, and generalizing scope beyond what was
asked risks the "casos de laboratorio" trap; flagged here instead for
whoever picks this up next.

**Point 3 (T2) -- `--issue none` silently resolves to "absent" for
D/M/R/X/B.** File:
`unmassk-toolkit/tests/memory/test_note_issue_none_regression_other_types.py`
(6 tests: 5 RED / 1 GREEN control). Root cause: `_issue_arg` now accepts
the `"none"` sentinel for ANY type (the Round 1 structural CLI gap,
closed generically for all seven types, not just Q/I) but
`validate_issue_gate`'s `note.type not in ("Q", "I")` branch only checks
`work is not None` -- it never looks at `issue` at all in that branch,
so `issue == "none"` sails through, `_build_candidate` resolves it to
`candidate.issue = None` (indistinguishable from "never gave --issue"),
and `validate_issue(candidate, None)` short-circuits with "nothing to
check". Live repro before writing: `note.py D --why "..." --issue none`
saves `D-001` with `rc == 0` today. Pinned properties instead of guessed
prose (Ultron hasn't written the fix) -- same technique as
[[customs-py-full-contract-notes]] Round 2's corrupt-file rejection:
`rc != 0`, no commit/HEAD movement, and the word "issue" present in the
combined output. GREEN control: a REAL `--issue N` (fake-gh technique,
local helper, `_skip_on_windows` reused for the same CI incident as
`test_note_issue_gate.py`) still saves fine outside Q/I -- confirms the
fix target is specifically the `"none"` sentinel, not `--issue` itself.

**Point 4 (bajo) -- `--issue N` + `--work no` together on a Q/I is a
silent contradiction.** File:
`unmassk-toolkit/tests/memory/test_note_issue_and_work_no_contradiction.py`
(6 tests: 2 RED / 4 GREEN). Root cause: `validate_issue_gate`'s own
docstring says its three checks are "todas independientes entre si" --
literally true, and that's the gap: `issue is None and work is None`
(the D-065 check) is false when `issue` is a real int, and `issue ==
"none"` (the D-066 check) is false when `issue` is an int too, so the
combination trips neither. Live repro (fake-gh confirming the issue
number exists, to isolate this from `validate_issue`/`gh issue view`,
a different concern already covered by
`test_note_issue_gate.py::TestIssueNAlonePassesThroughTheExistingValidator`):
`note.py Q --issue 4242 --work no ...` saves `Q-001` with `rc == 0`
today. Same pinned-properties technique as point 3 (rc != 0, no
write, both words "issue" and "work" present). Two GREEN controls:
`--issue N` alone still saves (parametrized skip-on-windows, same
fake-gh technique), `--work no` alone still saves (no gh dependency at
all, no skip needed).

**Full suite verification, run once with all three new files plus
Round 3's untouched file:** `python3 -m pytest unmassk-toolkit/tests/memory -q`
-> `10 failed, 640 passed, 1 skipped` -- 2 pre-existing RED (Round 3's
point 1, untouched, confirmed still failing for its own reason) + 8 new
RED across the three new files (1 + 5 + 2, matching the RED/GREEN split
declared above) + 640 passed (629 baseline + 11 new GREEN controls: 6 +
1 + 4). Zero collateral damage on any pre-existing test.
`git status --porcelain unmassk-toolkit/tests/memory/` before finishing:
exactly the three new files, `test_customs_issue_gate_bypass.py` and
`test_note_issue_gate.py` absent from the diff -- confirmed the
collision boundary held.

Reference: [[gitcmd-contract-notes]] (the `text=True` subprocess
convention this bug exploits, same module); [[format-py-full-contract-notes]]
(`_fold_raw`/`_parse_fields`, the folding contract this bug lives
inside); [[customs-py-full-contract-notes]] (the pinned-properties
wording technique for a rejection whose prose doesn't exist yet).

## Round 5 (2026-08-26, same day) -- BREAK 1's real fix broke 1 pre-existing test, same class as Round 2's 19

Context: Ultron shipped BREAK 1's fix (`_decide_note()` now also calls
`validate_issue_gate(note, note.issue, None)`, appending its rejection
to whatever `validate_note()` already found). One pre-existing test broke:
`test_customs_archived_key_zone_duplicate_parity.py::
TestCustomsHookDoesNotBlockAgainstAnArchivedKeyZoneDuplicate::
test_git_commit_with_same_keys_as_an_archived_incident_is_approved` --
its raw commit (built by the file's own `_commit_message_for_new_note`
helper) has no `Issue:`/`--work`, so once the gate applies it blocks on
the measuring-stick rejection BEFORE ever reaching the archived-duplicate
logic under test, even though `validate_note()` itself found nothing
(archived correctly filtered).

**Why only 1 test and not the file's other 3** (same helper, same
missing issue field): `_decide_note()` joins BOTH rejection sources
(`validate_note()` + `validate_issue_gate()`) with `"\n\n"` rather than
short-circuiting on the first -- the file's other two hook tests
(`TestCustomsHookStillBlocksAgainstALiveKeyZoneDuplicate`,
`TestCustomsHookOvercorrectionGuardNamesTheLiveCandidateNotTheArchivedOne`)
already expect `"block"` and only assert that a specific id string
APPEARS in the combined reason -- the duplicate-rejection half still
names that id regardless of the gate's half being appended alongside it,
so those two stayed green by accident of the join, not because they
were unaffected. Only the ARCHIVED-duplicate test (expects `"approve"`)
had no rejection text to hide behind.

**Fix: `issue=4242` threaded through `_commit_message_for_new_note`'s
existing `**`-style optional param, only at that one call site** -- not
`--work` (the coordinator's own message hedged this exactly: "o su
equivalente"). `--work`/`--issue none` are CLI-only sentinels, never
persisted (`_decide_note()`'s own docstring says this explicitly: a raw
`git commit -m` never carries either); the only way a raw commit can
satisfy `validate_issue_gate` is a REAL `Issue: #N` trailer, which
resolves to `note.issue = int`, tripping neither of the gate's two
checks (`issue is None and work is None` / `issue == "none"`). Doesn't
weaken the archived-duplicate assertion at all -- `issue` is orthogonal
to `existing_in_zone` filtering.

Verification: `python3 -m pytest unmassk-toolkit/tests/memory
unmassk-toolkit/tests/hooks -q` -> `704 passed, 1 skipped`, zero red.
`git status --porcelain` after: exactly the one file, no other diff.
