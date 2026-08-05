---
name: clusters-contract-notes
description: clusters.py Sec.9.1 RED contract (4 tests) -- pure grouping function, no git needed, Origin-vs-Replaces chain ambiguity resolved by row semantics
metadata:
  type: project
---

`tests/memory/test_clusters.py` -- RED contract for `lib/memory/clusters.py`
(PIEZAS.md Sec.9.1, `group(notes: tuple[Note, ...], archived_ids: frozenset[str])
-> tuple[Cluster, ...]`). Pure function, no git/tmp_repo needed -- simplest
contract in the memoria-v2 series so far (unit tests only, no fixtures beyond
`clusters`/`model`).

**Row-to-mechanism mapping (no literal source, disclosed as assumption in the
test file docstring):** "una cadena de tres notas encadenadas" (row 1) uses an
`Origin`-only transitive chain (A <- B <- C via `origin=(parent.id,)`), NOT
`Replaces`. Reasoning: row 1's failure mode is about FOLDING (same decision
appearing 3x as if distinct), row 3's is specifically about TITLE selection
(newest wins on `Replaces`) with the minimal 2-note case. Keeping them on
different pointer types keeps each row atomic and avoids row 1 being a
redundant superset of row 3. Flagged as an open question in the report since
Sec.9.1 doesn't literally say which pointer type the "chain" uses.

**Cross-module class-identity gotcha, sidestepped entirely this time:** unlike
`query.py`'s `_assert_fields_match` (compares Note fields one by one because
`query.by_id()` returns Note instances built inside a differently-loaded
`model` module), `clusters.group()` tests never construct an "expected"
Cluster/Note and compare with `==`. They only read `.id` (str) and tuples/
frozensets of ids off whatever `clusters.group()` returns. Zero risk of
false-red from `spec_from_file_location` vs flat-`import` class duplication --
cheaper than the `_assert_fields_match` pattern when the module under test is
pure and doesn't round-trip through git. Worth reusing for any future
pure/grouping-only module in this series.

**Row 4 (determinism) verification technique:** call `group()` twice on the
*same* notes with input tuple order reversed, compare snapshots (root id +
child ids in order) of both calls. Two independently-computed outputs
compared to each other -- not tautological (not "call once, assert equal to
itself"). Does NOT catch cross-process nondeterminism from `PYTHONHASHSEED`
randomization (e.g. an internal `set()` iteration) since it's single-process --
flagged as a real but out-of-budget-for-this-pass gap in the report, not
silently ignored.

**Mutation-check outcome (scratchpad only, never touched `lib/memory/`):** a
naive stub that resolves "root" via `find_root` recursion without honoring
"newest wins on Replaces" passed rows 1-2 but correctly FAILED row 3
(`AssertionError: test3 root D-700 -- stub picks oldest not newest`) --
confirms the test discriminates. A corrected stub (superseded-id set based:
root = component member not referenced by any other member's `.replaces`,
tie-break to the empty-`origin` ancestor) passed all 4. Confirms the
union-find-over-Origin+Replaces-pointers approach is a reasonable shape for
Ultron's real implementation, though that's Ultron's call, not mine to
prescribe.

See also [gitcmd-contract-notes](gitcmd-contract-notes.md),
[query-contract-notes](query-contract-notes.md),
[indexes-contract-and-shared-dir-incident-notes](indexes-contract-and-shared-dir-incident-notes.md)
(the "never write mutation-check throwaways into shared lib/memory/" rule,
followed here via `/private/tmp/.../scratchpad`, not `lib/memory/`).
