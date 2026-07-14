"""Shared fixtures/helpers for the serial_verify.py contract (test-first,
acceptance pass -- serial_verify.py does not exist yet).

Contract pinned by the task (not derived from code, since there is no code
yet):
  - evaluate_lines(lines_iterable, expect, reject_patterns) -> dict
    Pure decision function. No pyserial import needed to test it -- it
    consumes an already-read iterable/list of text lines. The CLI wraps it
    around a real serial port; the tests here exercise evaluate_lines with
    fake line lists (no hardware, no pyserial needed for THAT part).
  - Decision order (matters): (1) any reject pattern anywhere in the stream
    -> ok:false, reason names the pattern -- wins/short-circuits even if the
    expect marker appeared earlier in the stream; (2) else the expect marker
    appears -> ok:true; (3) else (stream ends with neither) -> ok:false,
    reason == "expect marker never seen" (exact wording pinned by the
    contract).
  - Output dict shape (exactly these 4 keys):
    {"ok": bool, "matched_expect": bool, "matched_reject": str|None,
     "reason": str}
  - CLI: `serial_verify.py --port <p> --baud <b> --expect <e> --reject
    "<csv>" --timeout <t>` prints that same dict as JSON to stdout ONLY,
    exit 0 iff ok. An unopenable port must produce a clean ok:false JSON +
    non-zero exit, never a Python traceback.

This is the CONTRACT pass (test-first, before Ultron implements) -- pinned
at acceptance granularity, not the full edge-case/branch sweep. That sweep
(case sensitivity, empty reject list, streaming/early-exit behavior on an
unbounded generator, a real pty-backed CLI round trip, etc.) belongs to the
hardening pass once Ultron has implemented against this contract and there
is real code to measure (EXHAUSTION PROTOCOL applies there, not here).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent
SCRIPT_PATH = SCRIPTS_DIR / "serial_verify.py"

# Expect/reject values taken verbatim from the task's own CLI example --
# not invented, so reusing them across tests is not a fabricated fixture,
# just avoiding retyping the same literals in every test.
EXPECT_MARKER = "BOOT_OK"
REJECT_PATTERNS = ("Guru Meditation", "Brownout", "WDT reset")
REJECT_CSV = ",".join(REJECT_PATTERNS)

# The exact output-dict schema pinned by the task contract. Not derived from
# the (nonexistent) script -- this list IS the contract.
RESULT_KEYS = {"ok", "matched_expect", "matched_reject", "reason"}


def import_module_from(script_path: Path, module_name: str):
    """Load any scripts/*.py file as a module via importlib.util, matching
    this repo's established convention (see
    unmassk-toolkit-python-test-conventions.md) for reaching a script's
    functions directly instead of only asserting on subprocess output.
    Raises FileNotFoundError while serial_verify.py does not exist yet --
    that is the expected RED for this contract pass."""
    spec = importlib.util.spec_from_file_location(module_name, script_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def serial_verify_module():
    """Import serial_verify.py fresh for each test. Fails at fixture setup
    (not at collection) while the script is absent -- isolates the RED
    reason for the evaluate_lines tests to 'script not found', independent
    of the CLI subprocess test below, which fails for its own (also
    legitimate) reason."""
    return import_module_from(SCRIPT_PATH, "serial_verify_under_test")


def run_cli_for(*args) -> subprocess.CompletedProcess:
    """Invoke serial_verify.py as a subprocess: `python serial_verify.py
    *args`. Generic shape shared with other scripts/*.py CLI tests across
    the toolkit (see run-cadquery-stale-output-contract-notes.md)."""
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH), *[str(a) for a in args]],
        capture_output=True,
        text=True,
        timeout=60,
    )


def parse_stdout_json(proc: subprocess.CompletedProcess) -> dict:
    """Parse the ENTIRE stdout as one JSON object -- the contract says the
    CLI 'prints that JSON to stdout only', i.e. stdout IS the JSON, nothing
    else a downstream parser would choke on."""
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
