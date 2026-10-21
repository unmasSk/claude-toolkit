"""Shared by bin/memory/boot.py and hooks/boot_launcher.py: boot report path,
failure marker and time budgets.
"""

import math
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import gitcmd
import timefmt

# Git-ignored session state, not memory.
_REPORT_DIR = (".claude", ".unmassk")
_REPORT_NAME = "boot-latest.txt"

# Epoch seconds at which the launcher kills boot.py; unset when boot runs by hand.
BOOT_ENDS_AT_ENV = "UNMASSK_BOOT_ENDS_AT"
# Seconds kept after the network steps to read memory and write the report.
_AFTER_NETWORK_RESERVE = 3.0


def report_path(root: Path) -> Path:
    """Path of the boot report in repo `root`; creates nothing."""
    return Path(root).joinpath(*_REPORT_DIR, _REPORT_NAME)


def write_failure_marker(
    root: Path, headline: str, body: str, started: float | None = None
) -> Path | None:
    """Replace the boot report with a dated failure marker and return its path; raises if unwritable.

    With `started` (epoch seconds of the failed boot), a report written after it is
    left alone and None is returned: another session's boot succeeded meanwhile."""
    destination = report_path(root)
    if started is not None:
        try:
            if destination.stat().st_mtime >= started:
                return None
        except FileNotFoundError:
            pass
    destination.parent.mkdir(parents=True, exist_ok=True)
    stamp = timefmt.utc_label(datetime.now(timezone.utc))
    gitcmd.atomic_write(destination, f"⚠️  {headline} — {stamp}\n\n{body}")
    return destination


def env_seconds(name: str, default: float) -> float:
    """Seconds from env var `name`; `default` unless it is a positive finite number."""
    try:
        value = float(os.environ.get(name, ""))
    except ValueError:
        return default
    return value if math.isfinite(value) and value > 0 else default


def network_budget(cap: float) -> float:
    """Seconds for a boot network step: `cap`, cut to the launcher's time left minus the reserve.

    `<= 0` means no time is left: the caller skips the step and says so."""
    try:
        ends_at = float(os.environ.get(BOOT_ENDS_AT_ENV, ""))
    except ValueError:
        return cap
    if not math.isfinite(ends_at):
        return cap
    return min(cap, ends_at - time.time() - _AFTER_NETWORK_RESERVE)
