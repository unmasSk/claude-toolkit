"""Acceptance contract for validate_mesh.py -- the watertight-validation
gate for STL meshes (unmassk-3d).

TEST-FIRST, contract pass: validate_mesh.py does not exist yet. This suite
defines "done" at acceptance granularity -- CLI behavior (stdout JSON shape,
exit code) and the importable `validate_mesh(path) -> dict` function.
Ultron implements against this contract; these tests must go from RED to
GREEN with no changes to the tests themselves.

Why this gate matters (see unmassk-3d/skills/unmassk-3d/references/
printability.md): a broken STL that silently passes to a slicer is exactly
the silent-failure class this toolkit exists to prevent. Every failure mode
below must be a loud, non-zero-exit, structured-JSON failure -- never a
silent pass and never a raw stack-trace crash.
"""

from __future__ import annotations

import json

import pytest

from conftest import (
    CHECK_KEYS,
    SCRIPT_PATH,
    import_validate_mesh_module,
    parse_stdout_json,
    run_cli,
)


def _assert_reasons_match_checks(parsed: dict) -> None:
    """The contract's reasons field is "[<failed-check strings>]" -- assert
    it is EXACTLY the set of check keys whose value is False, nothing more,
    nothing less."""
    checks = parsed["checks"]
    expected_reasons = sorted(key for key in CHECK_KEYS if not checks[key])
    assert sorted(parsed["reasons"]) == expected_reasons


def _assert_full_schema(parsed: dict) -> None:
    """Assert every top-level field the contract specifies is present with
    the right type -- never hand-pick a subset of the schema to check."""
    assert set(parsed.keys()) == {"ok", "checks", "reasons", "volume"}
    assert isinstance(parsed["ok"], bool)
    assert isinstance(parsed["checks"], dict)
    assert set(parsed["checks"].keys()) == set(CHECK_KEYS)
    for key in CHECK_KEYS:
        assert isinstance(parsed["checks"][key], bool), (
            f"checks[{key!r}] must be a real JSON boolean, got {parsed['checks'][key]!r}"
        )
    assert isinstance(parsed["reasons"], list)
    for reason in parsed["reasons"]:
        assert isinstance(reason, str)
        assert reason in CHECK_KEYS
    assert isinstance(parsed["volume"], (int, float))


class TestScriptExists:
    """Baseline: the script must exist as a real, executable file before
    any CLI test can mean anything. Kept as its own test so a missing
    script fails with an unambiguous message instead of a generic
    subprocess/JSON error."""

    def test_validate_mesh_script_exists(self):
        assert SCRIPT_PATH.exists(), (
            f"validate_mesh.py not found at {SCRIPT_PATH} -- "
            "not implemented yet (expected RED before Ultron implements)"
        )


class TestValidWatertightMeshPasses:
    """Happy path: a plain box must pass every check, ok=True, exit 0."""

    def test_cli_reports_ok_true_and_exits_zero(self, valid_watertight_mesh):
        proc = run_cli(valid_watertight_mesh.path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"] == valid_watertight_mesh.expect_checks
        assert parsed["ok"] is True
        assert parsed["reasons"] == []
        assert parsed["volume"] == pytest.approx(1000.0)
        assert proc.returncode == 0

    def test_cli_stderr_is_clean_on_success(self, valid_watertight_mesh):
        proc = run_cli(valid_watertight_mesh.path)
        assert "Traceback" not in proc.stderr

    def test_import_validate_mesh_function_returns_matching_dict(self, valid_watertight_mesh):
        mod = import_validate_mesh_module()
        result = mod.validate_mesh(str(valid_watertight_mesh.path))
        assert isinstance(result, dict)
        _assert_full_schema(result)
        assert result["checks"] == valid_watertight_mesh.expect_checks
        assert result["ok"] is True
        assert result["reasons"] == []
        assert result["volume"] == pytest.approx(1000.0)


class TestOpenMeshFailsWatertightCheck:
    """Box with a face removed: a hole in the shell. watertight:false,
    every other check stays true, ok=False, non-zero exit."""

    def test_cli_reports_watertight_false(self, open_mesh):
        proc = run_cli(open_mesh.path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"] == open_mesh.expect_checks
        assert parsed["checks"]["watertight"] is False
        assert parsed["ok"] is False
        _assert_reasons_match_checks(parsed)
        assert "watertight" in parsed["reasons"]

    def test_cli_exits_non_zero(self, open_mesh):
        proc = run_cli(open_mesh.path)
        assert proc.returncode != 0

    def test_cli_stderr_is_clean(self, open_mesh):
        proc = run_cli(open_mesh.path)
        assert "Traceback" not in proc.stderr


class TestFlippedNormalsFailsWindingCheck:
    """Box with one face's winding reversed: topology stays a closed
    2-manifold (watertight:true) but normals_consistent:false, isolated
    from the other checks."""

    def test_cli_reports_normals_consistent_false_isolated(self, flipped_normals_mesh):
        proc = run_cli(flipped_normals_mesh.path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"] == flipped_normals_mesh.expect_checks
        assert parsed["checks"]["normals_consistent"] is False
        assert parsed["checks"]["watertight"] is True
        assert parsed["ok"] is False
        _assert_reasons_match_checks(parsed)
        assert parsed["reasons"] == ["normals_consistent"]

    def test_cli_exits_non_zero(self, flipped_normals_mesh):
        proc = run_cli(flipped_normals_mesh.path)
        assert proc.returncode != 0


class TestInvertedVolumeFailsPositiveVolumeCheck:
    """Box with every face inverted: still watertight, still
    winding-consistent, but negative volume -- isolated positive_volume
    failure."""

    def test_cli_reports_positive_volume_false_isolated(self, inverted_volume_mesh):
        proc = run_cli(inverted_volume_mesh.path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"] == inverted_volume_mesh.expect_checks
        assert parsed["checks"]["positive_volume"] is False
        assert parsed["checks"]["watertight"] is True
        assert parsed["checks"]["normals_consistent"] is True
        assert parsed["ok"] is False
        assert parsed["volume"] == pytest.approx(-1000.0)
        _assert_reasons_match_checks(parsed)
        assert parsed["reasons"] == ["positive_volume"]

    def test_cli_exits_non_zero(self, inverted_volume_mesh):
        proc = run_cli(inverted_volume_mesh.path)
        assert proc.returncode != 0


class TestFlatDegenerateMeshFailsMultipleChecks:
    """A flat 2-triangle plane: zero volume AND not a closed shell. Proves
    the reasons list reports EVERY failed check simultaneously, not just
    the first one encountered."""

    def test_cli_reports_both_watertight_and_volume_failures(self, flat_degenerate_mesh):
        proc = run_cli(flat_degenerate_mesh.path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"] == flat_degenerate_mesh.expect_checks
        assert parsed["checks"]["watertight"] is False
        assert parsed["checks"]["positive_volume"] is False
        assert parsed["ok"] is False
        assert parsed["volume"] == pytest.approx(0.0)
        _assert_reasons_match_checks(parsed)
        assert set(parsed["reasons"]) == {"watertight", "positive_volume"}

    def test_cli_exits_non_zero(self, flat_degenerate_mesh):
        proc = run_cli(flat_degenerate_mesh.path)
        assert proc.returncode != 0


class TestDegenerateFaceFailsDegenerateCheck:
    """Watertight box plus one stray zero-area face: no_degenerate_faces
    is false (the primary check this fixture targets); watertight is also
    false as an honest side effect of STL being a pure triangle soup with
    no shared vertex indices -- both are asserted exactly, not hand-waved."""

    def test_cli_reports_no_degenerate_faces_false(self, degenerate_face_mesh):
        proc = run_cli(degenerate_face_mesh.path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"] == degenerate_face_mesh.expect_checks
        assert parsed["checks"]["no_degenerate_faces"] is False
        assert parsed["ok"] is False
        _assert_reasons_match_checks(parsed)
        assert "no_degenerate_faces" in parsed["reasons"]

    def test_cli_exits_non_zero(self, degenerate_face_mesh):
        proc = run_cli(degenerate_face_mesh.path)
        assert proc.returncode != 0


class TestGarbageTextFileNeverCrashesAndReportsLoadFailure:
    """A plain text file renamed .stl. trimesh.load() does NOT raise on
    this (verified: returns an empty Scene) -- the script must actively
    detect that and report loads:false, never silently claim loads:true
    with zero faces, and never crash."""

    def test_cli_reports_loads_false(self, garbage_text_stl):
        proc = run_cli(garbage_text_stl)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"]["loads"] is False
        assert parsed["ok"] is False

    def test_no_other_check_reports_true_when_load_failed(self, garbage_text_stl):
        """A mesh that never loaded cannot honestly claim to be watertight,
        winding-consistent, positive-volume, or free of degenerate faces --
        assert none of those are ever True when loads is False."""
        proc = run_cli(garbage_text_stl)
        parsed = parse_stdout_json(proc)
        other_checks = {k: v for k, v in parsed["checks"].items() if k != "loads"}
        assert not any(other_checks.values()), other_checks

    def test_reasons_includes_loads(self, garbage_text_stl):
        proc = run_cli(garbage_text_stl)
        parsed = parse_stdout_json(proc)
        assert "loads" in parsed["reasons"]

    def test_cli_exits_non_zero(self, garbage_text_stl):
        proc = run_cli(garbage_text_stl)
        assert proc.returncode != 0

    def test_cli_never_prints_a_stack_trace(self, garbage_text_stl):
        proc = run_cli(garbage_text_stl)
        assert "Traceback" not in proc.stderr
        assert "Traceback" not in proc.stdout


class TestNonexistentPathNeverCrashesAndReportsLoadFailure:
    """A path that does not exist. trimesh.load() raises ValueError on
    this (verified) -- the script must catch it, report loads:false, and
    never crash with an unhandled traceback."""

    def test_cli_reports_loads_false(self, nonexistent_stl_path):
        proc = run_cli(nonexistent_stl_path)
        parsed = parse_stdout_json(proc)
        _assert_full_schema(parsed)
        assert parsed["checks"]["loads"] is False
        assert parsed["ok"] is False

    def test_no_other_check_reports_true_when_load_failed(self, nonexistent_stl_path):
        proc = run_cli(nonexistent_stl_path)
        parsed = parse_stdout_json(proc)
        other_checks = {k: v for k, v in parsed["checks"].items() if k != "loads"}
        assert not any(other_checks.values()), other_checks

    def test_reasons_includes_loads(self, nonexistent_stl_path):
        proc = run_cli(nonexistent_stl_path)
        parsed = parse_stdout_json(proc)
        assert "loads" in parsed["reasons"]

    def test_cli_exits_non_zero(self, nonexistent_stl_path):
        proc = run_cli(nonexistent_stl_path)
        assert proc.returncode != 0

    def test_cli_never_prints_a_stack_trace(self, nonexistent_stl_path):
        proc = run_cli(nonexistent_stl_path)
        assert "Traceback" not in proc.stderr
        assert "Traceback" not in proc.stdout


class TestImportableFunctionFailurePath:
    """The importable `validate_mesh(path) -> dict` function must expose
    the same failure contract as the CLI, not just the happy path (already
    covered in TestValidWatertightMeshPasses)."""

    def test_import_reports_watertight_false_for_open_mesh(self, open_mesh):
        mod = import_validate_mesh_module()
        result = mod.validate_mesh(str(open_mesh.path))
        assert isinstance(result, dict)
        _assert_full_schema(result)
        assert result["checks"] == open_mesh.expect_checks
        assert result["ok"] is False

    def test_import_never_raises_for_garbage_input(self, garbage_text_stl):
        mod = import_validate_mesh_module()
        result = mod.validate_mesh(str(garbage_text_stl))
        assert isinstance(result, dict)
        assert result["checks"]["loads"] is False
        assert result["ok"] is False
