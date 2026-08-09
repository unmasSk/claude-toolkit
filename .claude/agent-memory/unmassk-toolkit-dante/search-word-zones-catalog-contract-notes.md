---
name: search-word-zones-catalog-contract-notes
description: bin/memory/search.py zero-result word search now shows the project's zones catalog before the footer -- tests added after Ultron's implementation, absent-vs-present-empty zones.json parity, zone-path guard
metadata:
  type: project
---

Task 2026-08-09, linear mode (Ultron already implemented, no tests existed):
`bin/memory/search.py::_render_zones_catalog` + `_insert_before_footer` --
when a word search finds zero notes, the script now prints the project's
zones catalog (`zones.render_list()`, same format as `gitmem zones list`)
inserted right before the word report's footer (`report_render.THIN_DIVIDER`
+ "Historia completa..." line), instead of leaving a bare empty header.
Added 6 tests to `tests/memory/test_search_script.py` (script-level,
black-box, `run_memory_script`) covering: zero-result+zones-present (catalog
shows, footer stays last line, catalog comes before footer), zero-result+no
zones.json at all (says "todavía no tiene ninguna zona dada de alta", never
the "zones.json tiene 0 zonas:" count-list format), zero-result+present-but-
empty `{}` zones.json (parity edge case -- same message as absent, per
`zones.load()`'s own documented absent==present-empty collapse), real-match
(catalog never appears, neither variant), and a guard test for the adjacent
ZONE-resolved path (a real zone with zero notes must show its own empty
zone report, never leak the word-search catalog -- these are two separate
branches in `_render_by_query`, the zone branch returns before reaching the
word-branch's catalog logic).

**Round trip technique reused from [[deuda24-search-by-id-contract-notes]]
and the file's own pre-existing round-trip classes:** never hand-type the
expected catalog text or footer line. `expected_catalog` comes from calling
`zones.render_list(zones.load(pm_path/"zones.json"))` in the SAME test
process against the SAME seeded data; `expected_footer_line` comes from
`report_render.render_word(report.build_word(word, False)).splitlines()[-1]`
-- both computed AFTER the script already ran, safe because the footer line
carries no timestamp (only the divider/header lines do), so no
`_normalize_timestamps` dance needed for this particular assertion.

**Fixture added: `zones_lib` (`import_lib_memory_module("zones")`)** --
same pattern as the file's existing `report_lib`/`report_render_lib`/
`format_lib` fixtures. Also added `pm_path` to the file's conftest import
list (already existed in `conftest.py`, just wasn't imported by this test
file yet -- needed to build the absolute `zones.json` path for the
independent `zones.load()` call and for the present-but-empty-`{}` edge
case, which writes the file directly rather than via `seed_zones_json`
(which never writes literal `{}`).

All 20 tests in the file pass (14 pre-existing + 6 new), full suite green
(1030 passed, 2 skipped, no regressions).

Related: [[zones-list-doctor-absent-vs-empty-contract-notes]] (the
`zones.py::_cmd_list` absent-vs-present-empty distinction this task's
zones.json load path also relies on, `zones.render_list()` itself was
extracted from `_cmd_list` for this exact reuse -- see its own docstring);
[[capa5-read-scripts-and-facade-contract-notes]] (this file's original RED
contract, UTC-label round-trip normalization pattern, vacuous-pass
technique this task's positive-content assertions follow).
