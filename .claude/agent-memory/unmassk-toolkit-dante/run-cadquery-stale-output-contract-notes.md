---
name: run-cadquery-stale-output-contract-notes
description: run_cadquery.py silent-failure regression (stale STL re-validated as fresh success) -- pinned test, live repro steps, generic conftest helpers added for future scripts/*.py CLI+import test files
metadata:
  type: project
---

Test file: `unmassk-3d/skills/unmassk-3d/scripts/tests/test_run_cadquery.py`.
Script under fix: `unmassk-3d/skills/unmassk-3d/scripts/run_cadquery.py`.

**The bug (blocking, found by code review 2026-07-14):** `run_cadquery()`
locates its result purely via `os.path.isfile(resolved_out)` after the
script subprocess exits 0 (`run_cadquery.py:93`). It never checks whether
*this run* produced that file. Reproduced live: run a script that exports a
box to `out.stl` (baseline, `ok:true`), then run a DIFFERENT script
targeting the SAME `out.stl` that exits 0 but never calls
`cq.exporters.export(...)` -- the runner finds the stale file left by the
first run and reports `ok:true` for the second run too. This is the
canonical "system lies to itself" silent failure this toolkit's threat
model (`CLAUDE.md`: "a failure must not pass silently") exists to catch.

**Red assertions (2 of them, both in
`TestStaleOutputMustNotBeSilentlyRevalidated`):** one via the importable
`run_cadquery()` function, one via the CLI/subprocess+JSON path (both
conventions the test suite already uses for `validate_mesh.py`). Confirmed
red for the right reason: `second["ok"]` is `True` when it must be `False`
-- verified with a real two-step sequence inside one test function (a
DELIBERATE exception to the "no order-dependent tests" rule: the whole bug
only exists as a property of a real run-then-rerun sequence against one
path; both steps live inside a single test, no state shared ACROSS test
functions).

**Fix expectation (for Ultron, not built here):** the runner must somehow
distinguish "file existed already" from "file freshly written by this
run" -- e.g. stat the file's mtime before launching the subprocess and
require it to have changed/be newer, or delete `resolved_out` before
launching (fail-loud if delete fails) so a stale leftover can never survive
to be misread as fresh. Whichever approach Ultron picks, this test suite
does not pin the mechanism, only the observable contract (`ok:false` +
non-empty `error` when nothing fresh was exported).

**New generic conftest.py helpers (added without touching the existing
validate_mesh.py-specific ones, so `test_validate_mesh.py` needed zero
changes):** `RUN_CADQUERY_SCRIPT_PATH`, `run_cli_for(script_path, *args)`,
`import_module_from(script_path, module_name)`. These are script-agnostic
versions of `run_cli()` / `import_validate_mesh_module()` (which stay
hardcoded to `validate_mesh.py` for backward compat) -- reuse these two for
any FUTURE `scripts/*.py` CLI+import test file in this project instead of
re-deriving subprocess/importlib boilerplate a third time.

**Environment note:** `cadquery` (2.8.0) is now installed in this env (a
setup script installed it in a parallel track). Cold subprocess import of
`cadquery` alone takes ~1.4s; full `run_cadquery.py` CLI round-trip
(cadquery + validate_mesh + trimesh) comfortably finishes well under the
120s timeout used in `run_cli_for()` (bumped up from the 60s used for the
lighter trimesh-only `validate_mesh.py` tests specifically because of this
overhead).

See also: [cad-trimesh-validate-mesh-contract-notes](cad-trimesh-validate-mesh-contract-notes.md).
