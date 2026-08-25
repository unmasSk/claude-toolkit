---
name: d056-lineage-and-chain-view-contract-notes
description: D-056 RED contract (test-first, before Ultron) for search.py list/lineage rendering -- archived-vs-live marker, two-sided Replaces link, and a new --chain view
metadata:
  type: project
---

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
