#!/usr/bin/env python3
"""START-step installer for the electronics-micro branch (see
references/setup.md). Mirrors the shape of unmassk-3d's
setup_cad_env.py (pip-core install + report-only CLI checks + a real
verify step, all folded into one never-raising JSON summary).

Installs/verifies the microcontroller toolset:

  - pip core (auto-installed if missing): platformio (provides `pio`) and
    pyserial -- the build/flash/monitor engine and the fallback
    serial_verify.py gate's dependency.
  - CLI tools (checked only via shutil.which, never auto-installed):
    `pio` (should land on PATH once platformio is pip-installed -- checked
    separately since a pip exit-code 0 doesn't guarantee the entry point
    resolved), and `node`/`npx` (npx is how platformio-mcp runs; reported
    if missing, never installed here -- installing Node is out of scope).
  - Verify: `pio --version` actually runs (not just "pip says it's there").

Idempotent and safe to re-run: already-present pip packages are never
reinstalled, and a second run against a fully-provisioned environment is a
clean no-op. Never raises -- a missing optional tool, a failed pip install,
or any other setup problem is reported in the summary, not thrown.

CLI:      python setup_micro_env.py
Library:  from setup_micro_env import run_setup; run_setup() -> dict
"""

from __future__ import annotations

import importlib
import json
import platform
import shutil
import subprocess
import sys

# pip package name -> the module name used to import it. pyserial's import
# name ("serial") differs from its pip/PyPI name -- this is the one place
# that distinction has to be made explicit.
PIP_CORE = {
    "platformio": "platformio",
    "pyserial": "serial",
}

# CLI tools checked with shutil.which (works on macOS and Linux alike).
# `pio` is provided by the PIP_CORE install above and only checked here as
# a real-entry-point verification; node/npx are never installed by this
# script (heavy/out of scope) -- only reported if missing.
CLI_TOOLS = (
    {
        "name": "pio",
        "which": "pio",
        "install_cmd": "python3 -m pip install --user platformio",
        "required": True,
    },
    {
        "name": "node",
        "which": "node",
        "install_cmd": "brew install node",
        "linux_note": (
            "install Node.js via your OS package manager (apt/dnf/pacman/etc.), "
            "e.g. 'sudo apt install -y nodejs npm'"
        ),
        "required": True,
    },
    {
        "name": "npx",
        "which": "npx",
        "install_cmd": "brew install node",
        "linux_note": "npx ships with Node.js -- install Node via your OS package manager",
        "required": True,
    },
)

PIP_INSTALL_TIMEOUT_SECONDS = 900
PIO_VERSION_TIMEOUT_SECONDS = 30


def _import_ok(module_name: str) -> bool:
    try:
        importlib.import_module(module_name)
        return True
    except Exception:
        return False


def _pip_install_command(packages: list[str]) -> list[str]:
    """Match this environment's existing pip invocation style: `pip3
    install --break-system-packages ...` (no venv here, externally-managed
    Homebrew Python / PEP 668). Falls back to `python -m pip` if `pip3`
    itself is not on PATH, so the script still works rather than crashing."""
    if shutil.which("pip3"):
        return ["pip3", "install", "--break-system-packages", *packages]
    return [sys.executable, "-m", "pip", "install", "--break-system-packages", *packages]


def _pip_install(packages: list[str]) -> tuple[bool, str]:
    """Run the pip install for `packages`. Returns (succeeded, error_message
    or '' on success). Never raises -- any subprocess failure (missing pip,
    timeout, network error) is captured and returned as a message instead."""
    if not packages:
        return True, ""
    cmd = _pip_install_command(packages)
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=PIP_INSTALL_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:
        return False, f"failed to run {' '.join(cmd)}: {exc}"
    if result.returncode != 0:
        return False, result.stderr.strip()[-2000:] or result.stdout.strip()[-2000:]
    return True, ""


def check_and_install_pip_core() -> dict:
    """Check each core pip package by import first (never reinstall what is
    already present), then install only what is missing. Re-verifies each
    installed package actually imports afterward -- a pip exit-code 0 does
    not always mean the module is importable (e.g. wrong interpreter)."""
    already_present = []
    to_install = []
    for pkg, module in PIP_CORE.items():
        if _import_ok(module):
            already_present.append(pkg)
        else:
            to_install.append(pkg)

    installed: list[str] = []
    install_error = None
    if to_install:
        ok, message = _pip_install(to_install)
        importlib.invalidate_caches()
        for pkg in to_install:
            if _import_ok(PIP_CORE[pkg]):
                installed.append(pkg)
        still_missing = [pkg for pkg in to_install if pkg not in installed]
        if still_missing:
            install_error = message or f"still failed to import: {', '.join(still_missing)}"

    core_ok = all(_import_ok(module) for module in PIP_CORE.values())
    result = {
        "already_present": sorted(already_present),
        "installed": sorted(installed),
        "core_ok": core_ok,
    }
    if install_error:
        result["install_error"] = install_error
    return result


def _is_macos() -> bool:
    return platform.system() == "Darwin"


def _missing_cli_entry(tool: dict, is_macos: bool) -> dict:
    """Build the reported entry for one missing CLI tool. `node`/`npx`'s
    'brew install node' hint is macOS-only -- on any other platform,
    reporting that exact command verbatim is a dead end for the user, so
    `install_cmd` is None there and a `note` points at the OS package
    manager instead. `pio`'s install_cmd is a plain pip command and applies
    on every platform, so it never needs the note branch."""
    entry = {"name": tool["name"], "required": tool["required"], "install_cmd": None}
    if is_macos or "linux_note" not in tool:
        entry["install_cmd"] = tool["install_cmd"]
    else:
        entry["note"] = tool["linux_note"]
    return entry


def check_cli_tools() -> list[dict]:
    """Report (never install) missing CLI tools. shutil.which works
    identically on macOS and Linux, so detecting absence needs no platform
    branch -- only the reported install hint does."""
    is_macos = _is_macos()
    missing = []
    for tool in CLI_TOOLS:
        if shutil.which(tool["which"]) is None:
            missing.append(_missing_cli_entry(tool, is_macos))
    return missing


def verify_pio_runs() -> tuple[bool, str]:
    """Run `pio --version` to confirm the CLI actually works, not just that
    pip reported success -- mirrors check_and_install_pip_core()'s own
    re-verify-after-install philosophy, applied to the console-script entry
    point instead of a Python import."""
    if shutil.which("pio") is None:
        return False, "pio not found on PATH"
    try:
        result = subprocess.run(
            ["pio", "--version"],
            capture_output=True,
            text=True,
            timeout=PIO_VERSION_TIMEOUT_SECONDS,
            check=False,
        )
    except Exception as exc:
        return False, f"failed to run 'pio --version': {exc}"
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "pio --version exited non-zero"
        return False, message[-500:]
    return True, ""


def run_setup() -> dict:
    """Run the full check+install pass and return the structured summary.
    Never raises -- every sub-step already swallows its own failures into
    the returned dict. `ok` is true only if the pip core imports AND
    `pio --version` actually runs -- node/npx presence is reported but does
    not gate `ok` (platformio-mcp is a convenience layer, not the gate)."""
    pip_result = check_and_install_pip_core()
    missing_manual = check_cli_tools()
    pio_ok, pio_message = verify_pio_runs()

    summary = {
        "installed": pip_result["installed"],
        "already_present": pip_result["already_present"],
        "missing_manual": missing_manual,
        "ok": pip_result["core_ok"] and pio_ok,
    }
    if "install_error" in pip_result:
        summary["install_error"] = pip_result["install_error"]
    if not pio_ok:
        summary["pio_error"] = pio_message
    return summary


def main() -> int:
    try:
        summary = run_setup()
    except Exception as exc:
        # Last-resort guard: setup must never crash regardless of the
        # environment it runs in -- report the failure, don't raise it.
        summary = {
            "installed": [],
            "already_present": [],
            "missing_manual": [],
            "ok": False,
            "install_error": f"unexpected setup failure: {exc}",
        }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
