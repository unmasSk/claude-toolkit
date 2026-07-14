#!/usr/bin/env python3
"""Firmware serial-assert gate (see references/setup.md) -- the deterministic
fallback for when platformio-mcp's agent_flash_monitor_verify isn't present.

Reads lines from a serial port after a flash and decides boot-ok vs
crash-loop against an expect marker and a set of reject (crash) patterns.
A flash reported "done" when the board is actually crash-looping is exactly
the silent-failure class this gate exists to prevent.

Decision rules (order matters):
  1. Any reject pattern anywhere in the stream -> ok:false, reason names the
     pattern -- wins/short-circuits even if the expect marker appeared
     earlier in the stream (a later crash still fails the gate).
  2. Else the expect marker appears anywhere -> ok:true.
  3. Else the stream ends with neither -> ok:false, reason ==
     "expect marker never seen".

evaluate_lines() is the pure decision function -- no pyserial, no hardware
needed to exercise it (plain line lists/iterables). The CLI wraps it around
a real serial port.

CLI: serial_verify.py --port <p> --baud <b> --expect <e> --reject "<csv>"
     --timeout <t>
Prints the result dict as JSON to stdout only, exit 0 iff ok. An unopenable
port (or any other failure) produces a clean ok:false JSON + non-zero exit,
never a Python traceback.
"""

from __future__ import annotations

import argparse
import json
import sys
import time

DEFAULT_BAUD = 115200
DEFAULT_TIMEOUT_SECONDS = 30.0
# Per-call read timeout on the underlying serial port -- short enough that
# the overall --timeout budget is checked frequently, long enough not to
# busy-loop.
SERIAL_READ_TIMEOUT_SECONDS = 1.0


def evaluate_lines(lines_iterable, expect, reject_patterns) -> dict:
    """Pure decision function -- consumes an already-available iterable of
    text lines (list, generator, or a real serial stream wrapped by the CLI
    layer below). No pyserial import required to exercise this function.

    A reject match short-circuits (returns immediately, without pulling any
    further items from the iterable) since it is decisive on its own. An
    expect match does NOT short-circuit -- a reject pattern appearing later
    in the same stream still overturns an earlier expect match, so the loop
    must keep draining until either a reject is found or the iterable ends.
    """
    matched_expect = False
    for line in lines_iterable:
        if expect in line:
            matched_expect = True
        for pattern in reject_patterns:
            if pattern in line:
                return {
                    "ok": False,
                    "matched_expect": matched_expect,
                    "matched_reject": pattern,
                    "reason": f"reject pattern matched: {pattern} (line: {line!r})",
                }

    if matched_expect:
        return {
            "ok": True,
            "matched_expect": True,
            "matched_reject": None,
            "reason": "expect marker matched, no reject pattern seen",
        }

    return {
        "ok": False,
        "matched_expect": False,
        "matched_reject": None,
        "reason": "expect marker never seen",
    }


def _iter_serial_lines(port: str, baud: int, timeout: float):
    """Real pyserial line reader -- the port layer that evaluate_lines()
    itself never needs to know about. Imports pyserial lazily (only when
    this generator is actually driven), so importing this module for the
    pure decision function needs no pyserial at all. Raises whatever
    pyserial/OSError the open or read produces; the CLI layer catches it."""
    import serial  # deferred: only the CLI/port layer needs pyserial

    ser = serial.Serial(port, baud, timeout=SERIAL_READ_TIMEOUT_SECONDS)
    deadline = time.monotonic() + timeout
    try:
        while time.monotonic() < deadline:
            raw = ser.readline()
            if not raw:
                continue  # per-read timeout with no data yet -- keep polling
            yield raw.decode("utf-8", errors="replace").rstrip("\r\n")
    finally:
        ser.close()


def _parse_reject_csv(csv_str: str) -> list[str]:
    return [p.strip() for p in csv_str.split(",") if p.strip()]


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Firmware serial-assert gate: boot-ok vs crash-loop."
    )
    parser.add_argument("--port", required=True, help="serial device path, e.g. /dev/ttyUSB0")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--expect", required=True, help="marker substring that means boot-ok")
    parser.add_argument(
        "--reject",
        default="",
        help="comma-separated crash-indicator substrings, e.g. 'Guru Meditation,Brownout'",
    )
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    return parser


def run_cli(argv=None) -> dict:
    """Parse args, read the real serial port, and run evaluate_lines() over
    it. Never raises -- any failure to open/read the port becomes a clean
    ok:false result dict instead of propagating."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    reject_patterns = _parse_reject_csv(args.reject)

    if not args.expect.strip():
        # An empty/whitespace-only expect marker makes `expect in line`
        # trivially true on the very first line -- the gate would report
        # ok:true regardless of a crashed board. That is exactly the
        # silent-failure class this gate exists to prevent, so treat it as
        # a usage error instead of a pass.
        return {
            "ok": False,
            "matched_expect": False,
            "matched_reject": None,
            "reason": "--expect must be a non-empty marker, got an empty/whitespace-only value",
        }

    try:
        lines = _iter_serial_lines(args.port, args.baud, args.timeout)
        return evaluate_lines(lines, args.expect, reject_patterns)
    except Exception as exc:
        return {
            "ok": False,
            "matched_expect": False,
            "matched_reject": None,
            "reason": f"failed to read serial port {args.port!r}: {exc}",
        }


def main(argv=None) -> int:
    try:
        result = run_cli(argv)
    except SystemExit:
        # argparse's own --help / bad-args exit -- not a crash, let it pass.
        raise
    except Exception as exc:
        # Last-resort guard: this gate must never crash regardless of the
        # environment it runs in -- report the failure, don't raise it.
        result = {
            "ok": False,
            "matched_expect": False,
            "matched_reject": None,
            "reason": f"unexpected failure: {exc}",
        }
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
