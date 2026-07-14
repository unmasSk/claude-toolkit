#!/usr/bin/env python3
"""START-step installer for unmassk-cad (see references/setup.md).

Installs/verifies the canonical open-source 3D-printing toolset:

  - pip core (auto-installed if missing): cadquery, build123d, trimesh,
    manifold3d -- CAD-as-code + the watertight validation gate.
  - brew apps/CLIs (checked only, never auto-installed -- heavy/interactive):
    uv and blender (required for the Blender MCP), openscad and admesh
    (optional).

Idempotent and safe to re-run: already-present pip packages are never
reinstalled, and a second run against a fully-provisioned environment is a
clean no-op. Never raises -- a missing optional tool, a failed pip install,
or any other setup problem is reported in the summary, not thrown.

CLI:      python setup_cad_env.py
Library:  from setup_cad_env import run_setup; run_setup() -> dict
"""

from __future__ import annotations

import importlib
import json
import shutil
import subprocess
import sys

# pip package name -> the module name used to import it.
PIP_CORE = {
    "cadquery": "cadquery",
    "build123d": "build123d",
    "trimesh": "trimesh",
    "manifold3d": "manifold3d",
}

# Brew-installed CLIs/apps this skill depends on. Checked with shutil.which
# (works on macOS and Linux alike), never installed by this script -- brew
# runs are heavy/interactive and out of scope for an automated gate.
BREW_TOOLS = (
    {"name": "uv", "which": "uv", "install_cmd": "brew install uv", "required": True},
    {
        "name": "blender",
        "which": "blender",
        "install_cmd": "brew install --cask blender",
        "required": True,
    },
    {
        "name": "openscad",
        "which": "openscad",
        "install_cmd": "brew install --cask openscad",
        "required": False,
    },
    {
        "name": "admesh",
        "which": "admesh",
        "install_cmd": "brew install admesh",
        "required": False,
    },
)

PIP_INSTALL_TIMEOUT_SECONDS = 900


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


def check_brew_tools() -> list[dict]:
    """Report (never install) missing brew-managed CLIs/apps. shutil.which
    works identically on macOS and Linux, so this needs no platform branch."""
    missing = []
    for tool in BREW_TOOLS:
        if shutil.which(tool["which"]) is None:
            missing.append(
                {
                    "name": tool["name"],
                    "install_cmd": tool["install_cmd"],
                    "required": tool["required"],
                }
            )
    return missing


def run_setup() -> dict:
    """Run the full check+install pass and return the structured summary.
    Never raises -- every sub-step already swallows its own failures into
    the returned dict."""
    pip_result = check_and_install_pip_core()
    missing_manual = check_brew_tools()
    summary = {
        "installed": pip_result["installed"],
        "already_present": pip_result["already_present"],
        "missing_manual": missing_manual,
        "ok": pip_result["core_ok"],
    }
    if "install_error" in pip_result:
        summary["install_error"] = pip_result["install_error"]
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
