"""Regression + acceptance contract for run_cadquery.py (unmassk-cad).

TEST-FIRST regression pass: a code review found a BLOCKING silent-failure
bug in the current `run_cadquery.py` (see
unmassk-cad/skills/unmassk-cad/scripts/run_cadquery.py:93). This file pins
the CORRECT behavior; Ultron fixes the script to make it green. Only tests
are written here -- the script itself is untouched.

THE BUG: `run_cadquery()` locates its result purely by
`os.path.isfile(resolved_out)` after the script subprocess exits 0. It does
NOT check whether *this run* actually produced that file. When the caller
targets a stable, reused output path (the documented default is
`<script_stem>.stl`, but the bug reproduces with ANY reused explicit path)
and a later script exits 0 without exporting -- a realistic "self-correction"
regression where a script computes geometry but forgets to export it -- the
runner finds the STALE STL left by a PREVIOUS run, validates that instead,
and falsely reports `ok:true`. That is exactly the silent-failure class this
toolkit exists to prevent (see printability.md's "the validation gate" and
run_cadquery.py's own docstring: "a script MUST export to that exact path").

Verified live before writing this file (see
cad-trimesh-validate-mesh-contract-notes.md /
run-cadquery-stale-output-contract-notes.md in Dante's memory): running a
valid exporting script against `out.stl`, then running a script that exits
0 and never calls `cq.exporters.export(...)` against the SAME `out.stl`,
currently returns `{"ran": true, "ok": true, ...}` for the SECOND run too --
the stale file from the first run is silently re-validated and reported as
a fresh success.
"""

from __future__ import annotations

import textwrap

import pytest

from conftest import (
    CHECK_KEYS,
    RUN_CADQUERY_SCRIPT_PATH,
    import_module_from,
    run_cli_for,
)


def _assert_run_cadquery_schema(result: dict) -> None:
    """Assert every top-level field of run_cadquery()'s contract is present
    with the right type -- never hand-pick a subset of the schema."""
    assert set(result.keys()) == {"ran", "error", "stl", "validation", "ok"}
    assert isinstance(result["ran"], bool)
    assert isinstance(result["ok"], bool)
    assert result["error"] is None or isinstance(result["error"], str)
    assert result["stl"] is None or isinstance(result["stl"], str)
    if result["validation"] is not None:
        assert isinstance(result["validation"], dict)
        assert set(result["validation"].keys()) == {"ok", "checks", "reasons", "volume"}
        assert set(result["validation"]["checks"].keys()) == set(CHECK_KEYS)


def _write_script(tmp_path, name: str, body: str):
    """Write a throwaway CadQuery driver script to tmp_path. Never committed
    to the repo -- generated fresh per test."""
    path = tmp_path / name
    path.write_text(textwrap.dedent(body))
    return path


def _valid_exporting_script_body() -> str:
    return """\
        import os
        import cadquery as cq

        box = cq.Workplane("XY").box(10, 10, 10)
        cq.exporters.export(box, os.environ["CADQUERY_OUT"])
        """


def _no_export_script_body() -> str:
    """Exits 0, computes geometry, but never calls cq.exporters.export --
    the exact realistic self-correction regression the bug pins against."""
    return """\
        import cadquery as cq

        box = cq.Workplane("XY").box(10, 10, 10)
        print("computed geometry but forgot to export")
        """


def _syntax_broken_script_body() -> str:
    return "def totally broken syntax(((\n"


def import_run_cadquery_module():
    return import_module_from(RUN_CADQUERY_SCRIPT_PATH, "run_cadquery_under_test")


class TestScriptExists:
    def test_run_cadquery_script_exists(self):
        assert RUN_CADQUERY_SCRIPT_PATH.exists(), (
            f"run_cadquery.py not found at {RUN_CADQUERY_SCRIPT_PATH}"
        )


class TestValidScriptBaseline:
    """Happy path: a script that actually exports a valid box must report
    ran:true, ok:true, a passing nested validation, and exit 0."""

    def test_cli_reports_ok_true_and_exits_zero(self, tmp_path):
        script = _write_script(tmp_path, "valid_case.py", _valid_exporting_script_body())
        out = tmp_path / "case.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, script, out)
        import json

        parsed = json.loads(proc.stdout.strip())
        _assert_run_cadquery_schema(parsed)
        assert parsed["ran"] is True
        assert parsed["ok"] is True
        assert parsed["error"] is None
        assert parsed["stl"] == str(out.resolve())
        assert parsed["validation"]["ok"] is True
        assert parsed["validation"]["volume"] == pytest.approx(1000.0)
        assert proc.returncode == 0

    def test_cli_stderr_is_clean(self, tmp_path):
        script = _write_script(tmp_path, "valid_case.py", _valid_exporting_script_body())
        out = tmp_path / "case.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, script, out)
        assert "Traceback" not in proc.stderr

    def test_import_run_cadquery_returns_matching_dict(self, tmp_path):
        script = _write_script(tmp_path, "valid_case.py", _valid_exporting_script_body())
        out = tmp_path / "case.stl"
        mod = import_run_cadquery_module()
        result = mod.run_cadquery(str(script), str(out))
        _assert_run_cadquery_schema(result)
        assert result["ran"] is True
        assert result["ok"] is True
        assert result["validation"]["ok"] is True


class TestStaleOutputMustNotBeSilentlyRevalidated:
    """THE regression. A second script run against the SAME output path
    that exits 0 but does not export must NOT inherit the first run's
    stale STL as if it were fresh output.

    This test intentionally performs two sequential runs against one
    fixture-scoped tmp_path within a SINGLE test function -- this is not
    order-dependent test pollution (Hard Rules ban shared state ACROSS
    test functions); it is the only way to demonstrate a stale-file bug at
    all, since the bug only exists as a property of a real run-then-rerun
    sequence against the same path.
    """

    def test_import_second_run_without_export_reports_ok_false(self, tmp_path):
        out = tmp_path / "case.stl"
        mod = import_run_cadquery_module()

        # Step 1: baseline -- a script that DOES export. Establishes a
        # real STL at `out` and confirms the runner is otherwise healthy.
        valid_script = _write_script(tmp_path, "valid_case.py", _valid_exporting_script_body())
        first = mod.run_cadquery(str(valid_script), str(out))
        assert first["ran"] is True
        assert first["ok"] is True
        assert first["validation"]["ok"] is True
        assert out.is_file()

        # Step 2: a DIFFERENT script, targeting the SAME out path, that
        # exits 0 but performs no export at all -- the realistic
        # self-correction regression. The stale STL from step 1 is still
        # on disk, untouched, at this exact path.
        no_export_script = _write_script(
            tmp_path, "no_export_case.py", _no_export_script_body()
        )
        second = mod.run_cadquery(str(no_export_script), str(out))

        assert second["ran"] is True, "the second script itself exits 0, that part is correct"
        # THE KEY ASSERTION -- currently FAILS against the buggy
        # run_cadquery.py, which finds the stale file via a bare
        # os.path.isfile() check and reports ok:true for a run that
        # produced no fresh output at all.
        assert second["ok"] is False, (
            "must NOT silently re-validate the stale STL left by a "
            "previous run at the same path -- the second script never "
            "exported anything"
        )
        assert second["error"] is not None, (
            "a run that falls back to a stale/no-fresh-output STL must "
            "say so, never resolve to a silent False with no explanation"
        )

    def test_cli_second_run_without_export_exits_non_zero(self, tmp_path):
        out = tmp_path / "case_cli.stl"

        valid_script = _write_script(tmp_path, "valid_case.py", _valid_exporting_script_body())
        first_proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, valid_script, out)
        assert first_proc.returncode == 0
        assert out.is_file()

        no_export_script = _write_script(
            tmp_path, "no_export_case.py", _no_export_script_body()
        )
        second_proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, no_export_script, out)

        import json

        parsed = json.loads(second_proc.stdout.strip())
        assert parsed["ok"] is False, (
            "CLI must report ok:false for a run against a stale output "
            "path where nothing fresh was exported"
        )
        # THE KEY EXIT-CODE ASSERTION -- currently FAILS (returns 0)
        # against the buggy code, since main() does
        # `return 0 if result["ok"] else 1` and result["ok"] is
        # (incorrectly) True today.
        assert second_proc.returncode != 0


class TestSyntaxBrokenScript:
    """A script with a syntax error: the sub-script itself fails loudly,
    but run_cadquery.py's OWN stdout/stderr must stay clean JSON -- the
    sub-script's traceback text is data (inside result["error"]), never a
    raw traceback escaping onto the runner's own stderr."""

    def test_cli_reports_ran_false_ok_false(self, tmp_path):
        script = _write_script(tmp_path, "broken_case.py", _syntax_broken_script_body())
        out = tmp_path / "broken_out.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, script, out)
        import json

        parsed = json.loads(proc.stdout.strip())
        _assert_run_cadquery_schema(parsed)
        assert parsed["ran"] is False
        assert parsed["ok"] is False
        assert parsed["error"] is not None
        assert parsed["stl"] is None
        assert parsed["validation"] is None

    def test_cli_exits_non_zero(self, tmp_path):
        script = _write_script(tmp_path, "broken_case.py", _syntax_broken_script_body())
        out = tmp_path / "broken_out.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, script, out)
        assert proc.returncode != 0

    def test_cli_own_stderr_has_no_raw_traceback(self, tmp_path):
        """The BROKEN SCRIPT's SyntaxError text is expected data inside the
        JSON error field -- what must NOT happen is run_cadquery.py's own
        process crashing and leaking a traceback onto ITS stderr."""
        script = _write_script(tmp_path, "broken_case.py", _syntax_broken_script_body())
        out = tmp_path / "broken_out.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, script, out)
        assert "Traceback" not in proc.stderr

    def test_no_fresh_output_file_created(self, tmp_path):
        script = _write_script(tmp_path, "broken_case.py", _syntax_broken_script_body())
        out = tmp_path / "broken_out.stl"
        run_cli_for(RUN_CADQUERY_SCRIPT_PATH, script, out)
        assert not out.exists()


class TestMissingScriptPath:
    """A script path that does not exist: a clean, structured error, never
    a crash."""

    def test_cli_reports_clean_error(self, tmp_path):
        missing = tmp_path / "does_not_exist.py"
        out = tmp_path / "missing_out.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, missing, out)
        import json

        parsed = json.loads(proc.stdout.strip())
        _assert_run_cadquery_schema(parsed)
        assert parsed["ran"] is False
        assert parsed["ok"] is False
        assert parsed["error"] is not None
        assert parsed["stl"] is None
        assert parsed["validation"] is None

    def test_cli_exits_non_zero(self, tmp_path):
        missing = tmp_path / "does_not_exist.py"
        out = tmp_path / "missing_out.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, missing, out)
        assert proc.returncode != 0

    def test_cli_stderr_is_clean(self, tmp_path):
        missing = tmp_path / "does_not_exist.py"
        out = tmp_path / "missing_out.stl"
        proc = run_cli_for(RUN_CADQUERY_SCRIPT_PATH, missing, out)
        assert "Traceback" not in proc.stderr

    def test_import_reports_clean_error(self, tmp_path):
        missing = tmp_path / "does_not_exist.py"
        out = tmp_path / "missing_out.stl"
        mod = import_run_cadquery_module()
        result = mod.run_cadquery(str(missing), str(out))
        _assert_run_cadquery_schema(result)
        assert result["ran"] is False
        assert result["ok"] is False
        assert result["error"] is not None
