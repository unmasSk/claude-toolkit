---
name: memoria-v2-render-d056-lineage-chain
description: D-056 render-lane work (2026-08-25) — archivada/arrow markers in listings, sustituye-a in --id view, --chain flag; circular-import-avoiding 3-way split of report_render.py
metadata:
  type: project
---

D-056 ("memory legibility and integrity batch... el enlace de sustitucion
se ve por un solo lado") closed its render half in one test-first pass:
`tests/memory/test_search_lineage_markers.py` (7 red) +
`test_search_chain_view.py` (2 red), 9/9 green after implementation, zero
regressions in `test_search_script.py`/`test_report_render.py`/
`test_report.py`/`test_clusters.py`/`test_indexes.py` (52/52 total).

**Circular-import trap when splitting a module two tests both call by
attribute.** `test_report_render.py`'s fixture calls BOTH
`report_render.render_zone(...)` AND `report_render.render_word(...)` as
attributes of the SAME module object — so neither can be moved to a new
sibling file and "re-exported back" the way `report_render_note.py` was
split out in the past (that precedent only had ONE function to move,
never called back). Moving `render_word` out and doing
`from report_render_word import render_word` back in `report_render.py`
would need `report_render_word.py` to import the six per-type block
functions FROM `report_render.py` (where `render_zone` still lives) —
a real cycle, forbidden by this codebase's own "import en un solo
sentido" convention (`zones.py`/`zones_query.py` docstring). **Fix: pull
the SHARED dependency (the six block functions:
`restriction_block`/`blocker_block`/`decision_block`/`memo_block`/
`incident_block`/`question_block`, promoted from private to public, plus
a `BLOCK_BY_TYPE` dict) into a THIRD sibling, `report_render_blocks.py`,
imported one-directionally by BOTH `report_render.py` (unchanged
`render_zone`/`render_word` location) and the new `report_render_chain.py`
(for `--chain`).** No cycle, both `render_zone`/`render_word` stay
reachable as `report_render.<name>` for the existing test fixture, and
`report_render.py` dropped from 538 (over the 500-line ceiling after
adding the D-056 markers) to 437 lines with zero behavior change to
either function. Verified live: `python3 -c "import report_render;
print(report_render.render_word)"` resolves fine, no
`ImportError`/`circular import`.

**`ZoneReport`/`WordChunk` needed a new `archived_ids: frozenset[str]`
field to let `report_render.py` mark "archivada" in FLAT tuples
(restrictions/blockers/memos/incidents/questions) — this was a
documented, PRE-EXISTING gap** (`test_report.py`'s own docstring,
"supuesto 4": "`model.ZoneReport` no trae un campo aparte de 'cuales
son archivadas'... eso SI existe para `decisions`
(`Cluster.archived_ids`) pero no para el resto"). Safe to add as a
REQUIRED field with a `= frozenset()` default (defensive, though grep
confirmed `report.py` is the ONLY production constructor of both
classes — no test constructs them directly, they always go through
`build_zone`/`build_word`, so a bare default wasn't even strictly
needed, added anyway for robustness at zero cost).

**"archivada" (listing marker) and "cerrada" (chain-view closed-leaf
label) are DIFFERENT words for the same underlying state on purpose —
don't let one block function's `archived` bool print both.**
`report_render_chain.py` always calls `BLOCK_BY_TYPE[type](note,
NO_MARK, False)` (archived=False, so the block never emits "archivada"),
then manually appends `"  cerrada"` to the first line when
`ChainThread.closed` is true. Passing `archived=True` there would print
the LISTING vocabulary inside the CHAIN view's own vocabulary — same
underlying boolean, two different contracted words in two different
render contexts.

**Chain construction reuses `Note.replaces` directly, NOT
`clusters.group()`'s union-find** — deliberate deviation from the
task's own KNOWN map suggestion, documented and justified: `replaces`
chains are singly-linked (one parent max per note), and
`clusters.group()`'s `children` output sorts by id ASCENDING (oldest
first) — the exact OPPOSITE of what the chain view's test requires
(`out.index(mid_id) < out.index(old_id)`, most-recent-ancestor-first).
Walking backward via `note.replaces` in a simple loop (with a `seen`
cycle guard, defensive — no adversary provokes a replace-cycle on
purpose, but the system must not hang against itself) gives the
required order for free. "Headness" (is this note superseded, so it's
an ancestor not a thread head) prefers `ARCHIVED.md`'s
`ArchiveLine.destination == "replaced"` when available (robust even if
the replacer's headline never matched the search word/zone), falling
back to "some OTHER note in the matched set has `.replaces == this.id`"
only when no archive line exists for that id.

**The incidencia→restriccion `Origin:` link (D-056 caso borde b) needed
ZERO special-casing** — it's simply NOT a `Replaces` pointer, so it
never enters any thread's ancestor walk. The restriction shows up as
its own independent thread head (never superseded), and
`restriction_block` (reused, not reimplemented) already prints
`Origin: {incident_id}` as part of its normal field list. The closed
incident is a second, separate thread head, labeled "cerrada". Both
just need to be present in the SAME matched set (`query.by_word`
already returns full project history regardless of archived status —
verified in `query.py`, so no extra plumbing needed to make both
visible without `--todo`).

See [[lessons.md]] for the general git-safety/bash-hook gotchas that
also applied unchanged this session (none new this time — no
`git commit`-text Bash calls were needed, no test-file edits attempted).

**Regression closed same day (2026-08-25), Moriarty repro,
`test_search_chain_view.py`'s 5th class:** `_chain_is_superseded` used
to trust `ARCHIVED.md`'s `destination == "replaced"` UNCONDITIONALLY —
but a lineage whose live head got re-archived under a DIFFERENT zone
pair (e.g. M-003 replaced by M-004 in `[gamma][delta]`, M-004 never
touching the old `[alpha][beta]`) made the successor invisible to
`_notes_touching_zone(old_zone)`'s single-pass `matched` set, so the
whole lineage vanished from `<old_zone> --chain` (0 threads) even
though `<old_zone> --todo` still showed it. **Fix: read
`ArchiveLine.destination_detail` (documented as "the new note's id" for
`destination == "replaced"`) and only treat a note as superseded when
that successor id is actually present in the current `by_id` (matched)
set** — not just recorded globally in `ARCHIVED.md`. When the successor
isn't visible, the note becomes the head of its own thread (still
labeled "cerrada" via the existing `archived_ids` check) with its own
ancestors walked normally by `_chain_ancestors`. One function signature
changed (`_chain_is_superseded` gained a `by_id` param) — private,
single call-site inside `report.py`, zero external callers (verified:
`build_chain` is the only public entry, called only from
`bin/memory/search.py:174`, unchanged signature). 47/47 green
(5 contract + 42 no-regression: lineage-markers/search_script/
report_render/report/clusters). Reproduced live outside pytest too via
a scratchpad script driving `note.py`/`search.py` as real subprocesses
(same pattern the test file itself uses) — confirmed `search alpha
--chain` now shows the orphaned M-001→M-002→M-003 thread headed by
M-003 (labeled "cerrada") instead of "0 hilos".

**Second same-day regression, closed 2026-08-25 (test-first, Dante's
6th class in `test_search_chain_view.py`):** the fix above made M-003
reappear as a thread head, but `_chain_threads` still labeled it
`closed=note.id in archived_ids` with no memory of *why* it was
archived — so a head that WAS replaced (successor real, just invisible
from this view) printed the same `cerrada` literal as a head with no
successor at all, contradicting `model.ChainThread.closed`'s own
contract ("True = cierre legítimo SIN sucesora"). **Fix: split the
single boolean into `closed: bool` + new `replaced_by: str | None =
None` field on `ChainThread`** (single production constructor,
`report.py::_chain_threads`, keyword-only call — safe to add a
defaulted field, zero other call-sites found via grep). New
`report.py::_chain_closure(note_id, is_archived, archive_lines)`
decides both from `ArchiveLine.destination`: `"closed"` (or archived
with no line — same blind fallback as before the fix, since no source
distinguishes why) → `closed=True`; `"replaced"` → `closed=False,
replaced_by=destination_detail` (the successor's real id), *regardless
of whether that successor is visible in this view* — reaching this
function at all already proves `_chain_is_superseded` let it through
(either no line, or a `"replaced"` line whose successor isn't in
`by_id`). `report_render_chain.py::_note_block` gained an optional
`replaced_by` param: appends literal `sustituida por <id>` instead of
`cerrada` when set — same "never both" invariant, verified by a manual
repro script (see below) showing the real line `M-003 ... sustituida
por M-004` for the cross-zone case, `cerrada` still intact for the
genuine-no-successor incident case (both green, no shared code path
regressed).

**Manual repro technique for a `tmp_repo`-fixture test without touching
any test file:** `conftest.py::tmp_repo` is a *plain function* (not a
pytest generator fixture — no `yield`, just `return repo_path`), so it
can be called directly from a throwaway scratchpad script after
`sys.path.insert(0, ".../tests/memory")` and driving `run_git`/
`seed_note_via_script`/`run_memory_script` exactly like the test does,
with zero pytest machinery and zero risk of a stray file landing in
the tests directory. Confirms real CLI text end to end, not just the
assertion's `in`-check.
