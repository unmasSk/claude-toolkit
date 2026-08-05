---
name: deuda5-cache-sync-recursive-subdirs-contract-notes
description: DEUDA.md #5 RED contract for cache_sync_check.py — _dir_fingerprint() ignores subdirectories, v2's lib/memory and bin/memory invisible to the repo-vs-cache watcher
metadata:
  type: project
---

Test file: `unmassk-toolkit/tests/test_cache_sync_check_recursive_subdirs.py` (new,
separate from the existing `test_doctor_derived_expectations.py`, which already owns
the full flat-directory contract for `check_repo_cache_sync()` / `count_repo_cache_drift()`
— fail-open matrix, "+N more" summarisation, semver tie-break. Do not duplicate that;
this file only covers the nested-subdirectory gap).

**The gap:** `cache_sync_check._dir_fingerprint()` only fingerprints direct-child files
of a compared dir (`if not os.path.isfile(full): continue` — no recursion).
`COMPARED_SUBDIRS = ("hooks", "lib", "bin", "agents")` is flat. Memoria v2 lives entirely
under `lib/memory/` (31 files) and `bin/memory/` (10 scripts) — both invisible to the
watcher today, so editing any v2 module reports "in sync" when it isn't.

**Why 5 tests failed and 2 passed (RED, correct shape):** the 5 detection tests
(edited file in lib/memory, edited file in bin/memory, new-file-only-in-repo nested,
count rising, subdir-is-parent's-only-content) all failed because drift came back `[]`/`0`
instead of non-empty — the right failure, traced straight to the missing recursion.
The 2 edge-case controls (identical nested trees → `[]`, `__pycache__` inside a nested
dir still ignored) **passed already** — that's correct: they assert behavior that must
hold both before AND after the fix, so they double as the fixed version's regression
guard once Ultron implements recursion.

**Fixture gotcha:** `cache_files={}` in the `_build()` helper means the cache_plugin dir
tree is never created at all → `os.path.isdir(cache_plugin)` is False → `_compute_drift()`
returns `None` (fail-open) → the public function returns `None` → iterating it raises
`TypeError`, not an assertion failure. Always give the cache side at least one placeholder
file (e.g. `"lib/memory/other.py": "y = 1\n"`) when the point of the test is "new file only
on the repo side" — otherwise the test fails for the wrong reason (missing cache dir, not
missing recursion). Same footgun exists in the sibling flat-dir tests already in
`test_doctor_derived_expectations.py` (`test_a_file_only_in_the_repo_counts_as_drift` avoids
it the same way, non-empty `cache_files`).

**Test-first mode note:** written at acceptance granularity (5 detection cases + 2 edge
controls), not the full exhaustion protocol — that pass is for the hardening round after
Ultron implements the recursion.

Related: [[boot-report-argus-four-regressions-notes]] (same repo-vs-cache watcher family,
different bug), [[capa5-scripts-red-contract-notes]] (v2 bin/memory scripts this gap makes
invisible).
