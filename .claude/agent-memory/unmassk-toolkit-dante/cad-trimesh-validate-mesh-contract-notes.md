---
name: cad-trimesh-validate-mesh-contract-notes
description: Ground truth about trimesh/STL behavior discovered while writing the validate_mesh.py acceptance contract (unmassk-3d watertight gate) -- load-bearing for any future trimesh-based test
metadata:
  type: feedback
---

Test file: `unmassk-3d/skills/unmassk-3d/scripts/tests/test_validate_mesh.py` +
`conftest.py`. Script under contract: `unmassk-3d/skills/unmassk-3d/scripts/validate_mesh.py`
(watertight-validation gate for 3D-printing STLs, checks: loads, watertight,
normals_consistent, positive_volume, no_degenerate_faces).

**Gotcha: `trimesh.load(path)` MUST use default `process=True` for
`is_watertight` to mean anything on a reloaded STL.** STL has no vertex
indices -- export writes 3 raw vertex positions per triangle (a pure
triangle soup). Loading with `process=False` skips vertex-welding, so even
a perfectly valid, watertight-in-memory box reloads as `is_watertight:
False` (its faces no longer share indices at all). Verified live: same box,
`process=False` -> `is_watertight: False`; `process=True` (trimesh's
default) -> `is_watertight: True`. Any test (or implementation) that loads
an STL with `process=False` for a watertight check is testing the wrong
thing. Always use plain `trimesh.load(path)` (default args) to match what
the real validator must do.

**Gotcha: garbage/unparseable STL input does NOT raise -- it silently
returns an empty `trimesh.Scene` (0 geometry), not a `Trimesh`.** Verified
with a plain text file renamed `.stl` AND with 2000 bytes of random binary
garbage: both `trimesh.load()` calls return `<trimesh.Scene(len(geometry)=0)>`
with no exception. A validator that only checks "did `trimesh.load` throw"
will silently report `loads:true` on garbage input -- this is exactly the
silent-failure class the gate exists to prevent. A nonexistent path is
different: `trimesh.load()` DOES raise `ValueError` for that case. Both
must be caught and turned into `loads:false`; the "empty Scene" case is the
one an implementer is likely to miss since there's no exception to catch.

**Fixture technique: isolate one failing check at a time by choosing the
right box mutation, verified empirically before writing any fixture (not
assumed):**
- Delete one face -> `watertight:false` only (open mesh, hole in shell).
- Reverse ONE face's winding (`faces[0] = faces[0][::-1]`) -> topology
  stays a closed 2-manifold so `watertight:true`, but
  `normals_consistent:false` in isolation; volume stays positive (just
  smaller, since one face contributes with the wrong sign).
- `mesh.invert()` (flips EVERY face consistently) -> stays
  `watertight:true` AND `normals_consistent:true` (consistently flipped is
  still "consistent"), but the shell now faces inward -> `volume` goes
  negative. This is the clean, isolated way to hit
  `positive_volume:false` without touching the other checks -- do NOT use
  a flat/degenerate mesh for this if isolation matters (see next point).
- A flat 2-triangle plane (zero thickness) fails BOTH `watertight` (not a
  closed shell) AND `positive_volume` (0 > 0 is False) simultaneously --
  useful as a deliberate multi-failure fixture to prove the `reasons` list
  reports every failed check, not just the first, but it is NOT an isolated
  single-check fixture.
- **No clean isolated fixture exists for `no_degenerate_faces:false`
  alone**, because STL is index-free: any way of writing a genuinely
  isolated stray degenerate face still produces edges with no matching
  partner face, which also breaks `watertight`. Tried collapsing a vertex
  position onto another's (keeps in-memory topology intact and IS isolated
  pre-export), but after STL export/reload the position-based vertex
  merge on load re-derives totally different topology and `watertight`
  flips to `False` anyway -- STL round-trip destroys any index-based
  isolation trick. Accept the confound: assert both `watertight:false` AND
  `no_degenerate_faces:false` explicitly for this fixture rather than
  pretending it's isolated.

**Pattern: derive expected values from the real dependency, not
hand-typed.** Every fixture builder in `conftest.py` writes the STL, then
immediately reloads it via `trimesh.load(path)` (the same call the script
under test must make) and computes the expected `checks`/`volume` from
that reloaded mesh -- e.g. `expected_volume = reloaded.volume`, not a
hardcoded `1000.0`. This is the general "derive-expected-via-real-codec"
technique (see [encoding-contract-notes](encoding-contract-notes.md)) applied to a
binary geometry format instead of a text codec.

**Contract interpretation pinned in tests (not stated explicitly in the
task, but the only sane reading):** `reasons` is EXACTLY
`sorted(key for key in CHECK_KEYS if not checks[key])` -- asserted via a
shared `_assert_reasons_match_checks()` helper in every test, not just
spot-checked in one. Also pinned: stdout must be ONLY the JSON object
(`json.loads(proc.stdout.strip())` on the whole string, not a substring
scan) -- treats "prints a structured JSON object to stdout" as the sole
stdout contract, catching any stray debug `print()` a naive implementation
might leave in.

**Environment note:** `trimesh`/`manifold3d`/`numpy`/`pytest` are NOT in a
project venv -- this repo has no `.venv`; `pytest`/`numpy` were already
present in the Homebrew-managed global `python3.14` site-packages
(externally-managed environment, PEP 668). Installed `trimesh` and
`manifold3d` with `pip3 install --break-system-packages trimesh
manifold3d` to match that existing pattern rather than creating a new venv
unasked. `manifold3d` ships a `cp314-macosx_11_0_arm64` wheel, no build
needed. Root `pyproject.toml`'s `[tool.pytest.ini_options] testpaths` is
scoped to `unmassk-toolkit/tests` only -- this new CAD test dir is NOT
auto-discovered by a bare `pytest` from repo root; must invoke with an
explicit path (`pytest unmassk-3d/skills/unmassk-3d/scripts/tests/`).
Left `pyproject.toml` untouched (config change, not requested, arguably
Ultron/orchestrator's call).
