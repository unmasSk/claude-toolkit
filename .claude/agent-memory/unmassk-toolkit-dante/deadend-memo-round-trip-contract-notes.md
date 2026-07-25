---
name: deadend-memo-round-trip-contract-notes
description: Round-trip fidelity test for Memo:deadend/<subsystem> (single-line trailer survives parse_trailers()+recall() intact, body prose does not) — GREEN, substrate confirmed sound
metadata:
  type: project
---

Task (2026-07-25): write ONE round-trip fidelity test proving the
dead-end-memory design decision holds — `memo(deadend/<subsystem>)` stored
as a single physical `Memo:` trailer line survives intact through
`lib/parsing.py::parse_trailers()` (validation-time, bottom-up) and
`lib/recall.py::recall()` (Bilbo-facing, via `scan_trailers_memory()`
internally). Cerberus's finding driving this: the commit BODY never
survives to recall — `_format_block()` only ever emits `trailers[kind]`
(the trailer VALUE), and both trailer scanners stop at the first
non-trailer line. Design depends entirely on that one line round-tripping
byte-for-byte.

**Result: GREEN, for the right reason.** Wrote
`unmassk-toolkit/tests/test_deadend_memo_round_trip.py`
(`TestDeadendMemoRoundTripFidelity::test_deadend_memo_line_survives_parse_and_recall_intact`),
one test function, three assertion groups:
1. `parse_trailers()` on a realistic one-line deadend value (`; `-joined
   ruled-out clauses, backtick-quoted symbols, `@<sha>` anchor) returns it
   byte-for-byte, not truncated at the first `;`/`-`/`|`/backtick.
2. `recall(query, scope="deadend/auth", _repo_dir=repo)` returns that same
   full line intact in its output.
3. Negative control: prose placed only in the commit BODY (above the
   trailer block, in the SAME commit) via a nonce never appears in
   `recall()`'s output — proves the body genuinely doesn't leak, not just
   "there was nothing there to leak."

Verified not vacuous with a standalone sanity check (outside pytest):
confirmed `parse_trailers()` actually DISTINGUISHES a full value from a
truncated-at-first-`;` value (`"deadend - a; b; c"` != `"deadend - a"`) —
proves the equality assertion isn't trivially true regardless of what
parse_trailers returns.

**Reusable technique for this test's shape:** put realistic explanatory
prose ABOVE the trailer block, separated by a blank line, in the SAME
commit as the trailer under test (not a second unrelated commit) — this is
a stronger negative control than an unrelated commit with no trailer at
all, because it exercises the actual claim ("this commit's own prose
doesn't leak"), not the trivial claim ("a commit with no trailer produces
no entry").

See also [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
for the shared `_make_repo`/`_commit`/git identity fixture patterns reused
here (same shape as `tests/test_recall.py`).
