---
name: chain-view-cross-zone-lineage-loss-regression-notes
description: search.py --chain drops an entire archived lineage when its head got re-archived under another zone pair, while --todo (the view it replaces) still shows it -- RED contract added, not yet fixed
metadata:
  type: project
---

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
