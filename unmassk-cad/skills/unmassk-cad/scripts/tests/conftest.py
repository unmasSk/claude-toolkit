"""Shared fixtures for the validate_mesh.py watertight-gate contract.

validate_mesh.py does not exist yet (test-first / RED phase). Every fixture
here generates a deterministic STL on disk (under tmp_path, never a
committed binary blob) using trimesh/numpy directly, and computes its
"expected" checks/volume by loading that same file back through trimesh the
same way the script's contract requires (trimesh.load(path), default
process=True vertex-merge) -- i.e. the expected values are re-derived from
the real dependency, not hand-typed literals. See
CHECK KEYS below for the exact schema the script must emit.

Ground truth confirmed by hand before writing any fixture (see session
notes / Dante memory): STL has no vertex indices, so is_watertight /
is_winding_consistent on a reloaded STL depend on trimesh.load()'s default
vertex-welding (process=True). Loading a text file or random bytes renamed
to .stl does NOT raise -- trimesh.load() returns an empty Scene (0
geometry) instead of a Trimesh. A nonexistent path DOES raise ValueError.
Both must be turned into loads:false by the script, not left to crash or to
silently report loads:true.
"""

from __future__ import annotations

import json
import subprocess
import sys
import importlib.util
from pathlib import Path
from typing import NamedTuple

import numpy as np
import pytest
import trimesh

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SCRIPTS_DIR / "validate_mesh.py"

# The exact check-key schema pinned by the task contract. Not derived from
# the (nonexistent) script -- this list IS the contract.
CHECK_KEYS = (
    "loads",
    "watertight",
    "normals_consistent",
    "positive_volume",
    "no_degenerate_faces",
)


class MeshFixture(NamedTuple):
    """A generated STL file plus the ground-truth expectations for it,
    computed by re-loading the file through trimesh (the real seam), not by
    hand-typed literals."""

    path: Path
    expect_checks: dict
    expect_ok: bool
    expect_reasons: list


def _checks_from_loaded_mesh(mesh: trimesh.Trimesh) -> dict:
    """Compute the checks dict the way the contract defines each check,
    directly from an already-loaded trimesh.Trimesh (loads:true branch)."""
    watertight = bool(mesh.is_watertight)
    normals_consistent = bool(mesh.is_winding_consistent)
    positive_volume = bool(mesh.volume > 0)
    if len(mesh.faces) == 0:
        no_degenerate_faces = False
    else:
        no_degenerate_faces = bool(
            trimesh.triangles.nondegenerate(mesh.triangles).all()
        )
    return {
        "loads": True,
        "watertight": watertight,
        "normals_consistent": normals_consistent,
        "positive_volume": positive_volume,
        "no_degenerate_faces": no_degenerate_faces,
    }


def _reasons_for(checks: dict) -> list:
    return sorted(key for key in CHECK_KEYS if not checks[key])


def _build_fixture_from_mesh(tmp_path: Path, filename: str, mesh: trimesh.Trimesh) -> MeshFixture:
    """Export `mesh` to an STL under tmp_path, then reload it through
    trimesh (default process=True, exactly as the script's contract
    requires) to derive ground-truth expectations from the file that will
    actually be handed to the CLI -- not from the in-memory mesh, which can
    differ from the round-tripped STL (STL has no vertex indices)."""
    path = tmp_path / filename
    mesh.export(path)
    reloaded = trimesh.load(path)  # default process=True, same as script must do
    checks = _checks_from_loaded_mesh(reloaded)
    reasons = _reasons_for(checks)
    return MeshFixture(
        path=path,
        expect_checks=checks,
        expect_ok=all(checks.values()),
        expect_reasons=reasons,
    )


@pytest.fixture
def valid_watertight_mesh(tmp_path) -> MeshFixture:
    """A plain box: watertight, consistent normals, positive volume, no
    degenerate faces. Must PASS every check, ok=True, exit 0."""
    box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    return _build_fixture_from_mesh(tmp_path, "valid_box.stl", box)


@pytest.fixture
def open_mesh(tmp_path) -> MeshFixture:
    """Box with one face deleted: a hole in the shell. Non-manifold/open ->
    watertight:false."""
    box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    box.faces = box.faces[:-1]
    box._cache.clear()
    return _build_fixture_from_mesh(tmp_path, "open_box.stl", box)


@pytest.fixture
def flipped_normals_mesh(tmp_path) -> MeshFixture:
    """Box with a single face's winding reversed. Topology stays a closed
    2-manifold (watertight:true) but winding is inconsistent across faces
    -> normals_consistent:false, isolated from the other checks (volume
    stays positive, just smaller, since one face contributes negatively)."""
    box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    faces = box.faces.copy()
    faces[0] = faces[0][::-1]
    box.faces = faces
    box._cache.clear()
    return _build_fixture_from_mesh(tmp_path, "flipped_normals_box.stl", box)


@pytest.fixture
def inverted_volume_mesh(tmp_path) -> MeshFixture:
    """Box with EVERY face inverted (mesh.invert()): still watertight, still
    winding-consistent (consistently flipped), but the shell now faces
    inward -> negative volume. Isolated, clean case for
    positive_volume:false alone."""
    box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    box.invert()
    return _build_fixture_from_mesh(tmp_path, "inverted_box.stl", box)


@pytest.fixture
def flat_degenerate_mesh(tmp_path) -> MeshFixture:
    """A flat 2-triangle plane (zero thickness): zero volume (0 > 0 is
    False) and not a closed shell. Exercises MULTIPLE simultaneous check
    failures (watertight:false AND positive_volume:false) to prove the
    "reasons" list reports every failed check, not just the first one."""
    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [1.0, 1.0, 0.0],
            [0.0, 1.0, 0.0],
        ]
    )
    faces = np.array([[0, 1, 2], [0, 2, 3]])
    flat = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return _build_fixture_from_mesh(tmp_path, "flat.stl", flat)


@pytest.fixture
def degenerate_face_mesh(tmp_path) -> MeshFixture:
    """A watertight box PLUS one stray zero-area face (a face that repeats
    one of the box's own vertices). The stray face's edges are not shared
    by any other face, so this ALSO breaks watertight:false as an honest
    side effect (STL is pure triangle soup, not indexed geometry -- there
    is no way to add a truly isolated degenerate face to a closed shell
    without altering its topology). This fixture is the contract's
    "degenerate case" bullet, isolating no_degenerate_faces:false as one of
    the (possibly several) failed checks."""
    box = trimesh.creation.box(extents=[10.0, 10.0, 10.0])
    verts = box.vertices.copy()
    faces = box.faces.copy()
    degenerate_face = np.array([faces[0][0], faces[0][0], faces[0][1]])
    new_faces = np.vstack([faces, degenerate_face])
    mesh = trimesh.Trimesh(vertices=verts, faces=new_faces, process=False)
    return _build_fixture_from_mesh(tmp_path, "degenerate_face_box.stl", mesh)


@pytest.fixture
def garbage_text_stl(tmp_path) -> Path:
    """A plain text file renamed .stl. trimesh.load() does NOT raise on
    this -- it silently returns an empty Scene (0 geometry). The script
    must detect that and report loads:false, never loads:true with zero
    faces."""
    path = tmp_path / "garbage.stl"
    path.write_text(
        "this is not an stl file, just plain text\n"
        "padded with more lines so it is not trivially empty\n"
        "and a few more bytes of nonsense content here\n"
    )
    return path


@pytest.fixture
def nonexistent_stl_path(tmp_path) -> Path:
    """A path that is never created. trimesh.load() raises ValueError on
    this. The script must catch it and report loads:false, never crash."""
    return tmp_path / "does_not_exist.stl"


def run_cli(stl_path) -> subprocess.CompletedProcess:
    """Invoke validate_mesh.py exactly per its CLI contract:
    `python validate_mesh.py <path-to-STL>`."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), str(stl_path)],
        capture_output=True,
        text=True,
        timeout=60,
    )


def parse_stdout_json(proc: subprocess.CompletedProcess) -> dict:
    """Parse the ENTIRE stdout as one JSON object -- the contract says the
    script "prints a structured JSON object to stdout", i.e. stdout IS the
    JSON, not JSON plus extra debug prints a downstream parser would choke
    on."""
    __tracebackhide__ = True
    try:
        return json.loads(proc.stdout.strip())
    except json.JSONDecodeError as exc:
        pytest.fail(
            "stdout was not a single parseable JSON object.\n"
            f"cmd exit code={proc.returncode}\n"
            f"stdout={proc.stdout!r}\n"
            f"stderr={proc.stderr!r}\n"
            f"json error={exc}"
        )


def import_validate_mesh_module():
    """Load validate_mesh.py as a module via importlib.util, matching this
    repo's established convention (see
    unmassk-toolkit-python-test-conventions.md) for reaching a script's
    functions directly instead of only asserting on subprocess output."""
    spec = importlib.util.spec_from_file_location("validate_mesh_under_test", SCRIPT_PATH)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
