---
name: render-issue-zone-word-contract-notes
description: Moriarty-found hole -- report_render.py never shows Note.issue on zone/word search (only report_render_note.py --id path did); RED contract for D/I/R types then hardening pass (remaining 4 types, zero-value guard, cluster root-vs-children lock-in)
metadata:
  type: project
---

Task: RED contract only, `unmassk-toolkit/tests/memory/test_report_render_issue_field.py`.
Moriarty confirmed `lib/memory/report_render.py` never references
`note.issue` in any of its seven per-type block functions
(`_restriction_block`, `_blocker_block`, `_decision_block`,
`_memo_block`, `_incident_block`, `_question_block`, `_cluster_block`) --
so `gitmem search <zone>` and `gitmem search <word>` silently drop a
saved issue number, even though `--id` (via
`report_render_note.py::_note_fields`) already shows it correctly for
all seven types since D-044/D-045 (2026-08-22, see
[[note-issue-field-seven-types-contract-notes]]).

**Two independent production gates already closed vs one still open**:
D-044/D-045 already opened `vocabulary.py::TYPES[*].allowed_fields` (all
seven types accept `--issue` now) AND fixed
`report_render_note.py:96`'s type check. This task's gap is a THIRD,
separate site -- `report_render.py` was never touched by that prior
work because it's a different file with its own block functions, one
per note type, none referencing `note.issue`.

**Format fixed by cross-reference, not invented**: `Issue: #{N}`, one
space after the colon (matches `report_render_note.py::_note_fields`
literally), and the same 9-space fixed indent
(`"         Why: ..."`) that `report_render.py`'s own block functions
already use for their second line -- verified letter-by-letter with a
small python script reading `lines[110:155]`, not eyeballed. This keeps
the by-id and by-zone/word surfaces from contradicting each other on
how a commit field looks inside a note's body.

**Test-first acceptance granularity, not exhaustive**: covered 3 of the
7 types as the task explicitly requested (one decision D, one incident
I, one restriction R) across both zone-search and word-search paths (6
red tests) plus 2 guard tests (no orphan `Issue:` label when
`--issue` was never passed, checked on both paths) -- those 2 pass
today already since the guard condition doesn't exist yet to violate.
Did NOT cover blocker/memo/question/X -- acceptance pass, not the
hardening pass; the hardening pass after Ultron implements is where the
other 4 types + `_cluster_block`'s D/X racimo path need coverage.

**Reused `test_note_issue_field.py`'s fake-gh-on-PATH technique**
verbatim in a reduced local copy (only "exists", no "missing" case --
that rejection path already has its own contract in the other file, no
need to duplicate). Did not import the other file's private
underscore-prefixed helpers across test files -- copied the technique,
not the code, since cross-file imports of another agent's private test
helpers create unwanted coupling if that file changes independently.

Result: 6 red for the right reason (issue number absent from
`search.py`'s real stdout, confirmed by reading the actual failure
output, not assumed), 2 green guards. Full `tests/memory` suite: 491
passed, 1 skipped (pre-existing), 6 new red -- zero collateral damage
(`python3 -m pytest unmassk-toolkit/tests/memory -q`).

## Hardening pass (same session, after Ultron implemented)

Ultron closed all seven blocks + `_cluster_block` root. Coordinator
named the exact gaps left open on purpose in the contract pass and
asked to close them, same file, same pattern -- 11 new tests appended
to `test_report_render_issue_field.py` (19 total in the file now, all
green):

- **Remaining 4 types (B, M, Q, X), both search paths** (8 tests) --
  same parametrize-list pattern as the original D/I/R classes, new list
  `_BLOCKER_MEMO_QUESTION_DISCARD` + matching word list. `X` on the
  zone-search side actually exercises `_cluster_block` again (X is a
  `_DECISION_TYPES` member, `report.build_zone` routes D/X through
  `clusters.group`), a single-note cluster (root with no children,
  since no Origin/Replaces links it) -- confirms X's issue survives via
  the racimo path, not just the loose one. On the word-search side X
  goes through `_decision_block` (loose, no `Cluster` object exists for
  `WordChunk.notes` -- see deviation 3 in `report_render.py`'s module
  docstring) -- a genuinely different code path from the zone side.

- **`--issue 0` is not falsy** (2 tests, zone + word) -- `Note.issue:
  int | None`, sentinel is `None` not `0`
  (`validator_issue.py::validate_issue`: `if issue is None: return
  None`, no range check). Guards against a future `if note.issue:`
  regression replacing `if note.issue is not None:` in any block --
  would silently drop issue 0 and no test built only on non-zero
  numbers would ever catch it. Reused `_fake_gh_dir` unchanged (issue
  numbers get `str()`-ed before comparison, `str(0) == "0"` needs no
  special-casing in the fake).

- **Cluster root-vs-children asymmetry locked in** (1 test) -- built a
  REAL two-note cluster via `--origin` (root D with `--issue 7171`,
  child X with `--origin <root_id> --issue 8282`, `clusters.py`
  unions by pointer, never by similarity). Asserted the root's issue
  string appears and the CHILD's issue number string appears NOWHERE
  in the output at all (not just not-as-a-labelled-line) -- proves
  `_cluster_block`'s per-child loop truly never emits a second line for
  any field (not even `Why:`, verified reading the loop: id + headline
  + status + pointer, one line, no field lines) rather than emitting an
  empty/blank Issue line. Needed a NEW helper, `_fake_gh_dir_multi`
  (same technique as `_fake_gh_dir`, accepts a tuple of known-existing
  issue numbers instead of one) -- one `note.py` process per note, both
  processes need the SAME fake `gh` to recognize two different issue
  numbers in the same test.

Full suite after hardening: `python3 -m pytest unmassk-toolkit/tests/memory -q`
-> 508 passed, 1 skipped, 0 failed (497 + 11 new = 508, matches the
coordinator's pre-hardening baseline exactly). Zero production files
touched in either pass.
