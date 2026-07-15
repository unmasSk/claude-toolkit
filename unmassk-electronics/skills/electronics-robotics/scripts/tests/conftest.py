"""Shared fixtures/helpers for the sensor_gate.py test suite.

sensor_gate.py already exists (this is a linear-mode / hardening-style pass,
not a test-first contract pass -- see test_sensor_gate.py's module docstring
for the full EXHAUSTION PROTOCOL surface declaration). Mirrors the shape of
electronics-micro/scripts/tests/conftest.py (import_module_from,
run_cli_for, parse_stdout_json) for consistency across the toolkit's
scripts/*.py test suites -- plugins are isolated from each other, this is a
fresh, self-contained conftest.py, not a cross-plugin import.
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SCRIPTS_DIR / "sensor_gate.py"

# The exact result-dict schema, read verbatim from sensor_gate.py's _result()
# (the single source of truth for every return path). Not invented -- this
# IS what the code already produces.
RESULT_KEYS = {
    "ok",
    "status",
    "reason",
    "before",
    "after",
    "observed_delta",
    "expected_delta",
    "tolerance",
    "direction",
}


def import_module_from(script_path: Path, module_name: str):
    """Load any scripts/*.py file as a module via importlib.util, matching
    this repo's established convention (see
    unmassk-toolkit-python-test-conventions.md) for reaching a script's
    functions directly instead of only asserting on subprocess output."""
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def sensor_gate_module():
    """Import sensor_gate.py fresh for each test -- isolates any module-level
    state (there is none today, but this keeps the fixture safe if that ever
    changes) and matches the sibling serial_verify_module fixture pattern."""
    return import_module_from(SCRIPT_PATH, "sensor_gate_under_test")


def run_cli_for(*args) -> subprocess.CompletedProcess:
    """Invoke sensor_gate.py as a real subprocess: `python sensor_gate.py
    *args`. Generic shape shared with other scripts/*.py CLI tests across
    the toolkit."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        timeout=60,
    )


def parse_stdout_json(proc: subprocess.CompletedProcess) -> dict:
    """Parse the ENTIRE stdout as one JSON object -- the module docstring
    says the CLI 'Prints the result dict as JSON to stdout only', i.e.
    stdout IS the JSON, nothing else a downstream parser would choke on."""
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
