#!/usr/bin/env python3
"""The execute -> structured-result -> iterate runner (unmassk-cad).

Runs a CadQuery (or build123d) script in a subprocess -- so a broken script
can never crash the runner -- captures its exit status/stdout/stderr, and
if it produced an STL, automatically chains it through the watertight gate
(`validate_mesh.validate_mesh`, imported from the sibling script, never
reimplemented). See references/cad-patterns.md, "The iterate loop": write
script -> run -> structured result -> Claude reads it and self-corrects.

CADQUERY_OUT convention: this runner always sets the environment variable
`CADQUERY_OUT` to the absolute path it expects the STL at, before launching
the script. A script MUST export to that exact path, e.g.:

    import os
    cq.exporters.export(case, os.environ["CADQUERY_OUT"])

If no output path is given on the CLI, the runner defaults `CADQUERY_OUT`
to `<script_stem>.stl` in the current working directory (i.e. running
`case.py` with no second argument expects `case.stl` next to where you ran
the command). This is the only contract between runner and script for
locating the result -- deliberately simpler than scanning the filesystem
for "any new .stl".

CLI:      python run_cadquery.py <cadquery_script.py> [output.stl]
Library:  from run_cadquery import run_cadquery
          run_cadquery(script_path, out_path=None) -> dict
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

# Reuse the existing watertight gate -- never reimplement it here.
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
from validate_mesh import validate_mesh  # noqa: E402

RUN_TIMEOUT_SECONDS = 180


def _resolve_out_path(script: Path, out_path: str | None) -> str:
    if out_path is not None:
        return str(Path(out_path).resolve())
    return str((Path.cwd() / f"{script.stem}.stl").resolve())


def run_cadquery(script_path: str, out_path: str | None = None) -> dict:
    """Execute `script_path` as a subprocess and fold the watertight-gate
    result in if it produced an STL. Never raises -- a missing script, a
    syntax error, a runtime exception, a script that exports nothing, or a
    timeout all resolve to `ran`/`ok` False with a clear `error`, never an
    exception escaping this function or a raw traceback on our own
    stdout/stderr."""
    result: dict = {"ran": False, "error": None, "stl": None, "validation": None, "ok": False}

    script = Path(script_path)
    if not script.is_file():
        result["error"] = f"script not found: {script_path}"
        return result

    resolved_out = _resolve_out_path(script, out_path)
    env = os.environ.copy()
    env["CADQUERY_OUT"] = resolved_out

    try:
        proc = subprocess.run(
            [sys.executable, str(script)],
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT_SECONDS,
            env=env,
            check=False,
        )
    except subprocess.TimeoutExpired:
        result["error"] = f"script timed out after {RUN_TIMEOUT_SECONDS}s"
        return result
    except Exception as exc:
        result["error"] = f"failed to run script: {exc}"
        return result

    result["ran"] = proc.returncode == 0
    if not result["ran"]:
        stderr_tail = proc.stderr.strip()[-2000:]
        result["error"] = stderr_tail or f"script exited with code {proc.returncode}"
        return result

    if not os.path.isfile(resolved_out):
        result["error"] = f"script ran but no STL found at {resolved_out}"
        return result

    result["stl"] = resolved_out
    try:
        result["validation"] = validate_mesh(resolved_out)
    except Exception as exc:
        # validate_mesh() already never raises per its own contract, but
        # guard here too -- a gate failure must never crash the runner.
        result["error"] = f"validation failed to run: {exc}"
        return result

    result["ok"] = bool(result["validation"] and result["validation"].get("ok") is True)
    return result


def _usage_result() -> dict:
    return {
        "ran": False,
        "error": "usage: run_cadquery.py <cadquery_script.py> [output.stl]",
        "stl": None,
        "validation": None,
        "ok": False,
    }


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if not args:
        print(json.dumps(_usage_result()))
        return 1
    script_path = args[0]
    out_path = args[1] if len(args) > 1 else None
    result = run_cadquery(script_path, out_path)
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception:
        # Last-resort guard: the runner must never crash regardless of
        # input, even for a failure run_cadquery() itself did not
        # anticipate.
        print(json.dumps(_usage_result()))
        sys.exit(1)
