---
name: note-issue-gate-work-quote-contract-notes
description: note.py Q/I issue-gate RED contract (D-065/D-066) -- --work no / --issue N / --issue none --quote, two structural CLI gaps found
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
