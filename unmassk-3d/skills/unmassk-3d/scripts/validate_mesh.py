#!/usr/bin/env python3
"""Watertight-validation gate for STL meshes (unmassk-3d).

A broken STL that silently passes to a slicer is exactly the silent-failure
class this toolkit exists to prevent. This gate loads a mesh with trimesh
and reports five boolean checks (loads, watertight, normals_consistent,
positive_volume, no_degenerate_faces) as a single JSON object on stdout,
exiting 0 only when every check passes.

The gate must never crash: a missing path, a garbage/text file renamed
.stl, or any other malformed input must resolve to loads:false, never a
raw traceback on stdout or stderr.

CLI:      python validate_mesh.py <path-to-STL>
Library:  from validate_mesh import validate_mesh; validate_mesh(path) -> dict
"""

from __future__ import annotations

import json
import sys

import trimesh

CHECK_KEYS = (
    "loads",
    "watertight",
    "normals_consistent",
    "positive_volume",
    "no_degenerate_faces",
)


def _load_mesh(path: str) -> trimesh.Trimesh | None:
    """Load `path` with trimesh and return a real Trimesh, or None for any
    load failure. trimesh.load() does not raise for a garbage file renamed
    .stl -- it returns an empty Scene (0 geometry) instead -- so a load is
    only considered successful when it is an actual Trimesh with faces.
    A nonexistent path raises ValueError, which is caught here too."""
    try:
        loaded = trimesh.load(path, process=True)
    except Exception:
        return None
    if isinstance(loaded, trimesh.Trimesh) and len(loaded.faces) > 0:
        return loaded
    return None


def validate_mesh(path: str) -> dict:
    """Run the watertight-gate checks against the STL at `path`. Never
    raises -- every failure mode (missing file, unparseable file, a check
    itself misbehaving) resolves to the corresponding check(s) being False,
    never to an exception escaping this function."""
    checks = {key: False for key in CHECK_KEYS}
    volume = 0.0

    mesh = _load_mesh(path)

    if mesh is not None:
        checks["loads"] = True

        # Each derived check gets its OWN try/except. A check that raises
        # must only ever blame itself -- it must never blank or falsely
        # fail a sibling check that was never evaluated (that would
        # corrupt the self-correct signal this gate exists to provide).
        try:
            checks["watertight"] = bool(mesh.is_watertight)
        except Exception:
            pass  # stays False (already its default) -- this check alone

        try:
            checks["normals_consistent"] = bool(mesh.is_winding_consistent)
        except Exception:
            pass

        try:
            volume = float(mesh.volume)
            checks["positive_volume"] = bool(volume > 0)
        except Exception:
            pass

        try:
            # `_load_mesh` already guarantees len(mesh.faces) > 0 for any
            # non-None mesh -- no need to special-case the empty-faces
            # branch here again.
            checks["no_degenerate_faces"] = bool(
                trimesh.triangles.nondegenerate(mesh.triangles).all()
            )
        except Exception:
            pass

    reasons = sorted(key for key in CHECK_KEYS if not checks[key])
    ok = all(checks.values())
    return {"ok": ok, "checks": checks, "reasons": reasons, "volume": volume}


def _failure_result() -> dict:
    return {
        "ok": False,
        "checks": {key: False for key in CHECK_KEYS},
        "reasons": list(CHECK_KEYS),
        "volume": 0.0,
    }


def _usage_result() -> dict:
    """Same shape as _failure_result(), plus an 'error' marker so a no-args
    CLI invocation is distinguishable from a real broken-STL validation
    result (mirrors run_cadquery.py's _usage_result())."""
    result = _failure_result()
    result["error"] = "usage: validate_mesh.py <path-to-STL>"
    return result


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(json.dumps(_usage_result()))
        return 1
    result = validate_mesh(args[0])
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Last-resort guard: the gate must never crash regardless of input,
        # even for a failure validate_mesh() itself did not anticipate.
        print(json.dumps(_failure_result()))
        sys.exit(1)
