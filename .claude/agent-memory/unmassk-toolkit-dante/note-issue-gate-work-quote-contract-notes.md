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
