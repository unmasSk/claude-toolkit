#!/usr/bin/env python3
"""START-step helper for the electronics-pi branch (see
references/setup.md). The real install runs ON the Raspberry Pi over SSH,
not on this machine -- this script only:

  - checks the LOCAL ssh client is present (shutil.which)
  - without --host: prints the exact command block to run on the Pi and
    exits 0 (there is nothing this machine itself can install)
  - with --host user@pi: runs the on-Pi install over SSH and verifies it
    (`import gpiozero`, `pinctrl -h`), both on the remote host

Never raises -- any ssh/subprocess failure is reported in the JSON summary,
not thrown. No hardware/network probing here decides whether a board is
actually wired correctly -- that's out of scope (see setup.md section 5).

CLI:      python setup_pi_env.py [--host user@pi]
Library:  from setup_pi_env import run_setup; run_setup(host=None) -> dict
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys

SSH_TIMEOUT_SECONDS = 30
INSTALL_TIMEOUT_SECONDS = 600

# The exact on-Pi command block -- kept as one source of truth so both the
# printed instructions (no --host) and the real ssh invocation (--host) run
# identically, matching references/setup.md section 2.
APT_INSTALL_CMD = (
    "sudo apt update && sudo apt install -y python3-gpiozero python3-picamera2 pinctrl"
)
PIP_INSTALL_CMD = "python3 -m pip install --user smbus2 spidev pyserial"
ON_PI_COMMANDS = (APT_INSTALL_CMD, PIP_INSTALL_CMD)

VERIFY_GPIOZERO_CMD = "python3 -c \"import gpiozero; print('gpiozero', gpiozero.__version__)\""
VERIFY_PINCTRL_CMD = "pinctrl -h"


def _ssh_present() -> bool:
    return shutil.which("ssh") is not None


def _manual_block(commands: tuple[str, ...]) -> str:
    lines = ["Run this on the Pi (over SSH), not on this machine:", ""]
    lines.extend(commands)
    return "\n".join(lines)


def _run_ssh(host: str, remote_cmd: str, timeout: int) -> tuple[bool, str]:
    """Run one command on the Pi over ssh. Returns (succeeded,
    output_or_error). Never raises -- subprocess/timeout/connection
    failures are captured and returned as a message instead."""
    try:
        result = subprocess.run(
            ["ssh", host, remote_cmd],
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except Exception as exc:
        return False, f"failed to run ssh {host!r} {remote_cmd!r}: {exc}"
    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip() or "non-zero exit"
        return False, message[-2000:]
    return True, result.stdout.strip()


def run_setup(host: str | None = None) -> dict:
    """Run the full check(+install-over-ssh) pass and return the structured
    summary. Never raises -- every sub-step swallows its own failures."""
    ssh_present = _ssh_present()
    if not ssh_present:
        return {
            "mode": "missing-ssh",
            "ssh_present": False,
            "host": host,
            "commands": list(ON_PI_COMMANDS),
            "ok": False,
            "error": "local ssh client not found on PATH -- cannot reach the Pi",
        }

    if not host:
        return {
            "mode": "no-host",
            "ssh_present": True,
            "host": None,
            "commands": list(ON_PI_COMMANDS),
            "manual_block": _manual_block(ON_PI_COMMANDS),
            "ok": True,
        }

    # --host given: run the real install + verify over ssh. There is no Pi
    # to test this branch against in this environment -- self-verification
    # for this pass covers the no-host and missing-ssh paths only, per the
    # task's explicit scope (no fabricated "success" for a remote run).
    install_ok, install_output = _run_ssh(
        host, f"{APT_INSTALL_CMD} && {PIP_INSTALL_CMD}", INSTALL_TIMEOUT_SECONDS
    )
    gpiozero_ok, gpiozero_output = _run_ssh(host, VERIFY_GPIOZERO_CMD, SSH_TIMEOUT_SECONDS)
    pinctrl_ok, pinctrl_output = _run_ssh(host, VERIFY_PINCTRL_CMD, SSH_TIMEOUT_SECONDS)

    summary = {
        "mode": "remote",
        "ssh_present": True,
        "host": host,
        "commands": list(ON_PI_COMMANDS),
        "install_ok": install_ok,
        "gpiozero_ok": gpiozero_ok,
        "pinctrl_ok": pinctrl_ok,
        "ok": install_ok and gpiozero_ok and pinctrl_ok,
    }
    if not install_ok:
        summary["install_error"] = install_output
    if not gpiozero_ok:
        summary["gpiozero_error"] = gpiozero_output
    if not pinctrl_ok:
        summary["pinctrl_error"] = pinctrl_output
    return summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Pi branch START helper -- runs the real install over SSH."
    )
    parser.add_argument(
        "--host",
        default=None,
        help="user@pi -- if omitted, prints the manual command block only",
    )
    return parser


def main() -> int:
    parser = _build_arg_parser()
    args = parser.parse_args()

    try:
        summary = run_setup(host=args.host)
    except Exception as exc:
        # Last-resort guard: this helper must never crash regardless of the
        # environment it runs in -- report the failure, don't raise it.
        summary = {
            "mode": "error",
            "ssh_present": False,
            "host": args.host,
            "commands": list(ON_PI_COMMANDS),
            "ok": False,
            "error": f"unexpected setup failure: {exc}",
        }
    print(json.dumps(summary, indent=2))
    return 0 if summary["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
