---
name: chain-view-superseded-labeled-closed-contract-notes
description: search.py --chain labels a superseded-but-cross-zone-invisible head "cerrada" (lying that the lineage ended) instead of naming its real successor -- RED contract, root cause and fix left to Ultron
metadata:
  type: project
---

Test-first RED pass (task from orchestrator, Moriarty repro, on top of the
already-fixed cross-zone lineage-loss bug -- see
[[chain-view-cross-zone-lineage-loss-regression-notes]]). That earlier fix
made `search alpha --chain` stop dropping a lineage whose head got
re-archived under another zone pair. This task is the OTHER half of the same
bug: the reappearing head is now mislabeled.

**Root cause, verified reading `lib/memory/report.py`/`model.py`/
`report_render_chain.py` before writing the test**: `_chain_threads`
(`report.py:400-408`) sets `closed=note.id in archived_ids` unconditionally
-- it never checks WHY the note is archived. `model.ChainThread.closed`'s own
docstring (`model.py:191`) says `"True = cierre legitimo sin sucesora"`, but
the field gets set to `True` even when `ArchiveLine.destination == "replaced"`
(a real successor exists, it just lives outside the matched zone set --
exactly the case `_chain_is_superseded` already special-cases to keep the
note as head of its own thread instead of vanishing). `report_render_chain.py`
then prints the literal `cerrada` for any `closed=True` head
(`_note_block`, line 61-62), with zero distinction from a genuine
`destination == "closed"` case.

**Test written**: new class
`TestChainViewLabelsASupersededNoteAsReplacedNeverAsClosed` appended to
`unmassk-toolkit/tests/memory/test_search_chain_view.py`, right after the
existing `TestChainViewNeverShowsFewerArchivedNotesOfAZoneThanTheOldTodoView`
(same fixture shape reused: M-001->M-002->M-003 in `[alpha][beta]`, M-004
`--replaces M-003` in `[gamma][delta]`). Both round-tripped via real
processes (`note.py` x4, `search.py --chain`), asserting on `search.py`'s
real stdout.

**Assertion technique -- wording-agnostic, same pattern as
[[deuda17-freshness-disclosure-contract-notes]]**: does NOT hardcode the
exact replacement phrase (Dante doesn't dictate production text choice here,
only the behavior contract) -- asserts the two invariants the task actually
requires: (1) the line containing M-003 never contains `"cerrada"` when a
real successor exists, (2) that same line DOES contain the successor's own
id (M-004), so the label names who replaced it instead of just omitting
"cerrada". Confirmed safe: M-004 never appears elsewhere in `alpha`'s
`--chain` output (it lives in `[gamma][delta]`, out of the matched set), so
`m4 in line` can only be satisfied by a label that actually names it.

**RED confirmed live**: `python3 -m pytest
unmassk-toolkit/tests/memory/test_search_chain_view.py -q` -> 1 failed, 5
passed. Failure is a real `AssertionError` quoting the actual lying line
(`'  M-003  ...  (↺ M-002)  cerrada'`), zero traceback. The pre-existing
control (`TestChainViewCountsAClosedIncidentWithoutASuccessorAsALegitimateEnd`
-- a genuinely closed note with no successor DOES say `cerrada`) stays green,
untouched.

**Fix left to Ultron**: `_chain_threads` needs a THIRD state, not a bool --
either split `ChainThread.closed` into something like
`closed: bool` (true cierre) vs `replaced_by: str | None` (successor id known
but outside the matched set), or replace the bool with an enum/union that
`report_render_chain.py` branches on. `_chain_is_superseded`'s existing logic
(`archive_lines.get(note_id).destination == "replaced"` +
`destination_detail` as the successor id) already computes everything needed
-- it's the same site that decides "does this note stay head of its own
thread", it just currently discards the successor id it already resolved
instead of threading it through to render. Not my call how to implement --
report only.

Related: [[chain-view-cross-zone-lineage-loss-regression-notes]],
[[d056-lineage-and-chain-view-contract-notes]].
