---
name: issue-63-orphaned-end-hardening-round-trip-notes
description: issue #63 final hardening pass on test_issue63_orphaned_end_preserves_user_content.py -- last-block + note-above edge cases, real §34 mtime round-trip, and a live-verified NEW bug found while mutation-checking (body duplicated as dead text on EVERY orphaned-END regen, not just last block -- same class as the already-deferred #64, NOT fixed here)
metadata:
  type: project
---

Follows [issue-63-t1a-orphaned-end-userdata-loss-contract-notes](issue-63-t1a-orphaned-end-userdata-loss-contract-notes.md).
That file's 2 tests were already GREEN against wip 7842668's conservative fix
(`lib/managed_blocks.py` ~L212-237: on an orphaned BEGIN, remove exactly that
one line and reinsert the full canonical block at that position, touching
nothing else). This hardening pass added 3 more tests to the SAME file
(`unmassk-toolkit/tests/test_issue63_orphaned_end_preserves_user_content.py`)
per an explicit task naming 3 gaps + a round-trip check, and found a real
NEW bug along the way via mandatory mutation-checking.

**Mutation-check discipline that mattered here:** don't trust "assertions
pass" as proof a new test discriminates anything. Restored the OLD buggy
mechanism live (`git show 7842668^:...managed_blocks.py`, swap file back
after) and re-ran the new tests against it. 2 of 3 new tests initially
FALSE-PASSED against the known-buggy old code:
- **Last-block test**: old code's "no next_positions" branch appends a
  fresh canonical copy at the very end of the file AND separately strips
  only the orphaned BEGIN line (leaving the old body as dead, unmarked
  leftover text) -- net effect: begin/end counts still land on 1, and the
  note (never touched by either operation) survives. So "note preserved +
  counts==1" doesn't distinguish old from new for THIS position. Fixed by
  asserting POSITION instead: `content_after.index(block["end"]) <
  content_after.index(note)` -- old code relocates the regenerated block to
  the file's end (after the note), new code regenerates in place (before
  it). Verified live both ways before landing the assertion.
- **Note-above test** (BLOCKS[1], note in the gap before its BEGIN):
  genuinely can't discriminate the old mutant -- the old boundary-deletion
  logic only ever searched FORWARD from the orphaned BEGIN, so content
  before a block was never at risk under EITHER mechanism. Documented this
  honestly in the test's own docstring instead of pretending it's a strong
  regression test: kept anyway (per the task's explicit ask) as a
  forward-looking guard against a hypothetical future regression that
  anchors deletion on a "previous block's END" boundary instead.

**Real bug found while designing the last-block assertion (verified live,
NOT fixed -- out of scope, reported only):** the CURRENT (already-shipped,
already-GREEN-tested) conservative fix leaves the orphaned block's ORIGINAL
body text behind as unmarked dead content EVERY time it regenerates an
orphaned-END block -- not just for the last block, reproduced for BLOCKS[0]
(the exact scenario the 2 pre-existing "passing" contract tests already
cover) too. Root cause: `line_end = content.find("\n", start) + 1` only
skips past the orphaned BEGIN's own line; `content[line_end:]` (spliced back
in unchanged) still contains the block's old body, since the corruption
only ever deleted the END line, never the body. The freshly rendered
canonical block is prepended before this leftover, so the body appears
TWICE in the file (once as dead unmarked text, once inside the real
managed block) after every single orphaned-END regeneration. Confirmed via
`content_after.count(block["body"])` == 2 on both HEAD (current, "fixed")
code and the old code, for both the last block and BLOCKS[0]. **Not
asserted against in any test** -- this is the same class of issue the task
itself named as already-reported-by-Ultron and explicitly deferred to
issue #64 ("no cubras la limpieza de las líneas BEGIN huérfanas sobrantes
... candidato de #64"). What's new here: it's not just leftover BEGIN
lines -- it's the FULL block body duplicated, for every orphaned-END
regen, confirmed even in the already-accepted non-last-block scenario.
Worth flagging to Yoda/whoever owns #64 that its scope may be larger than
"stray BEGIN lines."

**§34 round-trip gap closed:** `TestRegeneratedBlockRoundTripNoRewriteOnNextBoot`
combines 2 previously-separate proofs that never ran end-to-end together:
`test_crew_content_gate_v2.py`'s `TestCanonicalContentWithMatchingManifestSkipsRewrite`
proves mtime-preserving no-rewrite but only starting from a FRESH install
(never-corrupted) content; `test_issue63_t1_end_marker_and_magic_string.py`'s
orphaned-END idempotency check proves content-equality across a second run
but never checks mtime (so can't distinguish "genuine no-op" from "rewrote
identical bytes"). New test: real corruption -> real crew-hook regeneration
(boot 1) -> real second crew-hook run (boot 2) -> asserts mtime AND content
both untouched by boot 2, with the 1.1s sleep margin convention already used
elsewhere in this repo for coarse filesystem mtime resolution.

Verification convention reused from
[issue-61-ci-flake-hardening-notes](issue-61-ci-flake-hardening-notes.md):
full suite exit code read from a file after `echo "EXIT_CODE=$?" > file &&
cat file`, never piped through tail/head. Full local run after this pass:
1287 passed, 2 skipped (Windows-only), 0 failed.
