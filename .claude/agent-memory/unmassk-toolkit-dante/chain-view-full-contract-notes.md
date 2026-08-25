---
name: chain-view-full-contract-notes
description: search.py --chain / report.py build_chain full campaign merged from 3 files — original D-056 RED contract, cross-zone lineage-loss regression, superseded-labeled-closed regression (both Moriarty repros on the same underlying bug)
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 2) from 3 separate files that all covered the SAME piece of
code — `bin/memory/search.py --chain` / `lib/memory/report.py::build_chain`/`_chain_threads` — split only by
which session touched it. Rounds 2 and 3 are literally two halves of the SAME bug (a lineage head re-archived
under a different zone pair): Round 2 fixes the lineage disappearing, Round 3 fixes the reappearing head being
mislabeled. Per this project's compaction rule ("varios ficheros sobre UN mismo trabajo... se funden en uno
por tema"). Nothing was cut; each original file's content is reproduced below verbatim under its own heading,
in order. Original filenames (now retired, kept only as history in this note, not on disk):
`d056-lineage-and-chain-view-contract-notes.md`, `chain-view-cross-zone-lineage-loss-regression-notes.md`,
`chain-view-superseded-labeled-closed-contract-notes.md`.

## Round 1 — D-056 RED contract: archived-vs-live marker, two-sided Replaces link, new --chain flag

Two `search.py` render gaps scoped by **D-056** (found via `gitmem search d-056`,
zone `memory/architecture` -- the search-before-assuming step paid off: the
orchestrator's KNOWN map was correct on file locations but the decision note
itself supplied the real "why", useful for judging edge cases). Wrote two new
test files, both fail RED for the right reason (real assertion text absent /
argparse "unrecognized arguments", zero tracebacks), verified with
`python3 -m pytest unmassk-toolkit/tests/memory/test_search_lineage_markers.py
unmassk-toolkit/tests/memory/test_search_chain_view.py -q`.

**Files**: `unmassk-toolkit/tests/memory/test_search_lineage_markers.py` (archived
marker + two-sided Replaces link) and `test_search_chain_view.py` (new `--chain`
flag). Production surface: `bin/memory/search.py::_parse_args`,
`lib/memory/report_render.py` (`_memo_block`/`_restriction_block`/
`_incident_block`/`_decision_block`), `lib/memory/report_render_note.py::
_note_fields` (rule 2 currently excludes Origin/Replaces on purpose -- this
task reverses that exclusion for the Replaces-forward direction only).

**Chosen contract text** (mine to fix in test-first mode, no prior doc dictates
it): archived marker in listings = literal `"archivada"` (reuses existing
vocabulary from `report_render_note.py` header and `_cluster_block` child
status, no new glyph). New note's own `--id` view = literal
`"sustituye a {old_id}"` (mirrors the existing `"nace de {root_id}"` already
used for the Origin direction). List-view return arrow on the new note's own
line = `"(↺ {old_id})"`, visible without `--todo` (it's about the live note's
own line, unrelated to whether archived notes are shown). `--chain` flag:
combines with the existing zone-or-word positional, same pattern as `--todo`.
Struck ancestors wrapped in `"~~...~~"` (markdown convention, readable by both
a person and the LLM reading it, no new emoji). Closed-without-successor
labeled literal `"cerrada"` (reuses `format_lines._ARCHIVE_DESTINATIONS`
vocabulary, `"closed"`). Incident->restriction Origin link in chain view reuses
the literal `"Origin: {id}"` already printed today by
`report_render.py::_restriction_block` -- the edge case this guards against is
a chain view built ONLY from `Replaces` pointers that silently drops the
Origin-born restriction relationship.

**Gotcha, useful for the next agent building this or a sibling contract**:
`remove.py`'s fence-success line uses a DIFFERENT emoji/verb than `note.py`'s
success line -- `"⚠️ {id} guardada — muro nacido de {incident_id}"` vs
`note.py`'s `"✅ {id} guardada"`. `conftest.extract_note_id()` (anchored on the
`✅` emoji) does NOT match the fence line -- needed a local regex
(`r"([A-Z]-\d+)\s+guardada\s+—\s+muro nacido de"`) in the new test file instead.

**Own-block-line isolation technique** (worth reusing): once the return-arrow
`(↺ old_id)` marker exists, `old_id` appears TWICE in output -- once in its
own archived block line, once embedded in the new note's arrow reference.
A plain substring search over lines would collide. Anchor a regex to line
start requiring the compact-block format (`^(?:› |  ){id}  `, from
`report_render.py`'s literal `_MARK`/`_NO_MARK` + two-space separator) to
isolate the note's OWN declarative line from any line that merely references
its id.

Related: [[search-word-zones-catalog-contract-notes]],
[[note-issue-field-seven-types-contract-notes]] (Origin/Issue precedent for
extending a field's visibility across type).

## Round 2 (Moriarty repro) — --chain drops a whole lineage when its head is re-archived under another zone pair

Test-first RED pass (task from orchestrator, Moriarty repro): `--chain`
already exists and is green for the normal cases (single zone pair,
closed-without-successor, Origin link -- see
[[d056-lineage-and-chain-view-contract-notes]]). This is a NEW regression
found on top of that already-shipped feature, not part of the original
D-056 contract.

**Root cause, verified reading `lib/memory/report.py` before writing the
test** (not trusted blind from the orchestrator's KNOWN block):
`build_chain`/`_chain_threads` build their universe with a single
`_notes_touching_zone(zone)` call and only walk backward (`Replaces`)
INSIDE that set. `_chain_is_superseded` marks a note "superseded" purely
from `ARCHIVED.md`'s `destination == "replaced"` line -- it never checks
whether the successor that replaced it is itself in the matched set. So
when a lineage's head gets re-archived under a completely different zone
pair (M-004 replaces M-003 but lives in `[gamma][delta]` instead of
`[alpha][beta]`), M-004 never touches `alpha` and is absent from
`matched`; M-003 (and by the same logic M-002, M-001) are each still
individually marked "superseded" via `ARCHIVED.md`, so `_chain_threads`
skips ALL of them as non-heads and none of them ever become an
ancestor of anything in the set either -- the entire lineage silently
vanishes, `search alpha --chain` reports "0 hilos". `search alpha --todo`
(`report.build_zone(zone, include_archived=True)`) has no such
requirement -- it filters `_notes_touching_zone(zone)` by
type/archived-flag alone, no successor-membership check -- so it still
shows M-001/M-002/M-003 archived, marked `"archivada"`.

**Test written**: new class
`TestChainViewNeverShowsFewerArchivedNotesOfAZoneThanTheOldTodoView` in
`unmassk-toolkit/tests/memory/test_search_chain_view.py`, appended after
the existing four D-056 classes (left untouched, still green -- ran the
whole file: 4 passed / 1 failed, confirms this is a NEW gap, not a
re-break of the shipped contract). Round trip via real processes
(`note.py` four times: M-001, M-002 replaces M-001, M-003 replaces M-002,
all `[alpha][beta]`; M-004 replaces M-003 in `[gamma][delta]`), then both
`search.py alpha --todo` (sanity control -- fails loud with a distinct
message if the lineage isn't even visible there, meaning the seeding
itself is broken) and `search.py alpha --chain` (the real assertion).

**RED confirmed live**: `python3 -m pytest
unmassk-toolkit/tests/memory/test_search_chain_view.py -q` → 1 failed, 4
passed. Failure is a real `AssertionError` (`'M-001' in '...0 hilos...
Ninguna nota de esta zona o palabra tiene cadena que mostrar...'`), zero
traceback -- the right RED, not a fixture/harness break.

**Fix left to Ultron**: `build_chain`'s per-zone `matched` set needs to
also pull in notes reachable by walking a `Replaces` pointer OUT of the
originally matched set (i.e. resolve `cursor.replaces`/successor lookups
against `query.by_id` regardless of zone membership, the same escape
hatch `_chain_ancestors` already uses for an ancestor whose id fell
outside `matched` -- but the missing direction here is FORWARD:
`_chain_is_superseded` needs to know the successor exists as a real note
even when it's not in the zone's own `matched` set, or the design needs a
"lineage tail archived elsewhere" thread of its own). Not my call how to
implement -- report only.

Related: [[d056-lineage-and-chain-view-contract-notes]].

## Round 3 (Moriarty repro, on top of Round 2's fix) — --chain mislabels the reappearing head 'cerrada' (lying)

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
