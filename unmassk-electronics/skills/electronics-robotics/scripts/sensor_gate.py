#!/usr/bin/env python3
"""Robotics sensor gate (see references/sensor-gate.md) -- the deterministic
check for "did the robot actually move", not "did the command return".

The rule this gate exists to enforce: **the command you sent is not evidence;
a sensor reading taken before AND after the action is.** A servo/motor call
that returned without error is not proof anything moved -- read a sensor,
compare before vs. after against the expected change, and only THEN report
the movement confirmed.

    before = read_sensor()          # baseline
    actuate()                       # move / turn / drive
    sleep(settling_time)            # let the physical world catch up
    after = read_sensor()           # the truth
    evaluate_gate(before, after, expected_delta, tolerance, direction)

evaluate_gate() is the pure decision function -- no hardware driver needed to
exercise it (plain numbers only). Unlike the microcontroller branch's
serial_verify.py (one port, one pyserial API), the three sensors this gate
covers (VL53L0X ToF, HC-SR04 ultrasonic, MPU6050 IMU) each use a different
driver API. Rather than pick one and import it, the sensor-read layer is
fully deferred: callers inject a `read_sensor` callable (or, for the CLI,
pass already-taken numeric readings). This module never imports smbus,
RPi.GPIO, board, busio, or any adafruit_* driver.

Gate shapes supported (see references/sensor-gate.md):
  - direction="increase" / "decrease": distance grew/shrank by at least
    expected_delta, allowing `tolerance` of slack for sensor noise (the
    VL53L0X "moved >=3cm closer" pattern). Open-ended above the threshold --
    moving further than required still passes.
  - direction="either": the reading changed by about expected_delta in
    magnitude, within a +/-tolerance band either way (the MPU6050 "turned
    ~90 degrees, within +/-10" pattern). Overshoot fails, same as undershoot.
Tolerances are always a range, never `==` -- see "Tolerances, not equality"
in the reference doc.

No sensor reading available (before or after is None) -> the result is
"commanded_unverified", never "confirmed". A command that was sent is not
allowed to be silently upgraded into a movement that was proven.

*** UNVERIFIED AGAINST REAL HARDWARE ***
The gate LOGIC in this file (comparisons, tolerance bands, median-of-samples
noise filtering) is exercised in simulation only, with plain numbers -- no
physical sensor was involved in writing or checking this module. Integration
with REAL VL53L0X / HC-SR04 / MPU6050 hardware (I2C/GPIO wiring, read timing,
real-world sensor noise, settling time) is UNVERIFIED and must be validated
on an actual device before a gate result produced from live hardware is
trusted. Do not read this file as evidence the gate has been tested
end-to-end on a robot.

CLI: sensor_gate.py --expected-delta <N> --tolerance <T> --direction
     <increase|decrease|either> [--before <v> [<v> ...]] [--after <v> [<v> ...]]
     (note: pass multiple --before/--after values to median-filter noisy
     readings yourself before this gate runs)
Omitting --before/--after entirely (no sensor available) is exactly the
"commanded, unverified" case. Prints the result dict as JSON to stdout only,
exit 0 iff ok. Any failure produces a clean ok:false JSON + non-zero exit,
never a Python traceback.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
import time

DEFAULT_SAMPLES = 3
DEFAULT_SETTLE_SECONDS = 0.5
_DIRECTIONS = ("increase", "decrease", "either")


def _result(
    ok: bool,
    status: str,
    reason: str,
    *,
    before=None,
    after=None,
    observed_delta=None,
    expected_delta=None,
    tolerance=None,
    direction=None,
) -> dict:
    """Single source of truth for the result dict shape -- every return path
    (confirmed, gate_failed, commanded_unverified, invalid_input,
    actuate_failed) produces the same keys so callers never branch on shape."""
    return {
        "ok": ok,
        "status": status,
        "reason": reason,
        "before": before,
        "after": after,
        "observed_delta": observed_delta,
        "expected_delta": expected_delta,
        "tolerance": tolerance,
        "direction": direction,
    }


def _is_finite_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def evaluate_gate(before, after, expected_delta, tolerance, direction) -> dict:
    """Pure decision function -- consumes plain numbers (or None for a
    missing sensor reading). No hardware, no driver import, no callable
    required to exercise this: `evaluate_gate(10.0, 6.5, 3.0, 1.0,
    "decrease")` is a complete, valid call.

    Rules (order matters):
      1. before is None or after is None -> status "commanded_unverified".
         The command may well have been sent; it is never upgraded to a
         confirmed movement without a real sensor reading on both sides.
      2. Any of before/after/expected_delta/tolerance is not a finite
         number (NaN/Infinity rejected), tolerance < 0, expected_delta < 0,
         or direction is not one of "increase"/"decrease"/"either"
         -> status "invalid_input" (never raises).
      3. direction "increase": observed_delta = after - before; passes when
         observed_delta >= expected_delta - tolerance (open-ended above --
         moving further than required still passes).
      4. direction "decrease": observed_delta = before - after; same
         open-ended-above threshold, opposite sign convention.
      5. direction "either": observed_delta = abs(after - before); passes
         when abs(observed_delta - expected_delta) <= tolerance (a
         symmetric two-sided band -- overshoot fails same as undershoot;
         this is the orientation-delta / "changed by ~N" shape).
    """
    # Bound closures over the raw inputs so every early-return below states
    # only its reason -- the shared before/after/expected_delta/tolerance/
    # direction context is filled in once, not repeated at each call site.
    def _early(status: str, reason: str) -> dict:
        return _result(
            False,
            status,
            reason,
            before=before,
            after=after,
            expected_delta=expected_delta,
            tolerance=tolerance,
            direction=direction,
        )

    if before is None or after is None:
        return _early(
            "commanded_unverified",
            "no sensor reading available before and/or after actuation -- "
            "reporting commanded, unverified. A command sent is not evidence "
            "of movement; this is never upgraded to confirmed without a "
            "real sensor reading on both sides.",
        )

    for name, value in (
        ("before", before),
        ("after", after),
        ("expected_delta", expected_delta),
        ("tolerance", tolerance),
    ):
        if not _is_finite_number(value):
            return _early("invalid_input", f"{name} must be a finite number, got {value!r}")

    if tolerance < 0:
        return _early("invalid_input", f"tolerance must be >= 0, got {tolerance!r}")

    if expected_delta < 0:
        return _early(
            "invalid_input",
            f"expected_delta must be >= 0 (it is a magnitude of change; sign "
            f"is encoded by `direction`), got {expected_delta!r}",
        )

    if direction not in _DIRECTIONS:
        return _early("invalid_input", f"direction must be one of {_DIRECTIONS}, got {direction!r}")

    if direction == "increase":
        observed_delta = after - before
        ok = observed_delta >= expected_delta - tolerance
    elif direction == "decrease":
        observed_delta = before - after
        ok = observed_delta >= expected_delta - tolerance
    else:  # "either"
        observed_delta = abs(after - before)
        ok = abs(observed_delta - expected_delta) <= tolerance

    if ok:
        reason = (
            f"observed_delta={observed_delta!r} satisfies expected_delta="
            f"{expected_delta!r} within tolerance={tolerance!r} (direction={direction!r})"
        )
    else:
        reason = (
            f"observed_delta={observed_delta!r} does NOT satisfy expected_delta="
            f"{expected_delta!r} within tolerance={tolerance!r} (direction={direction!r})"
        )

    return _result(
        ok,
        "confirmed" if ok else "gate_failed",
        reason,
        before=before,
        after=after,
        observed_delta=observed_delta,
        expected_delta=expected_delta,
        tolerance=tolerance,
        direction=direction,
    )


def _median_of_readings(readings):
    """Anti-noise helper (sensor-gate.md: "ultrasonic is noisy -- take a
    median of a few reads before asserting"). Pure -- operates on a plain
    list of already-collected numbers. Drops None entries (failed samples)
    and non-finite values before taking the median; returns None if nothing
    usable remains, which flows straight into evaluate_gate's
    commanded_unverified path."""
    usable = [r for r in readings if _is_finite_number(r)]
    if not usable:
        return None
    return statistics.median(usable)


def _sample_sensor(read_sensor, samples: int):
    """Deferred sensor-read layer -- calls the caller-injected `read_sensor`
    callable `samples` times and returns the raw readings. Mirrors how
    serial_verify.py's _iter_serial_lines defers `import serial`: this
    function (and this module) never imports a hardware driver -- the driver
    lives inside whatever callable the caller passes in. A single bad sample
    (exception or non-numeric return) is recorded as None rather than
    aborting the whole read, since HC-SR04 in particular is known to glitch
    on individual pulses."""
    readings = []
    for _ in range(max(1, samples)):
        try:
            readings.append(read_sensor())
        except Exception:
            readings.append(None)
    return readings


def run_gate(
    actuate,
    expected_delta,
    tolerance,
    direction,
    read_sensor=None,
    samples: int = DEFAULT_SAMPLES,
    settle_seconds: float = DEFAULT_SETTLE_SECONDS,
) -> dict:
    """Orchestrates the full before -> actuate -> settle -> after -> evaluate
    pattern from references/sensor-gate.md. `actuate` (a zero-arg callable
    that performs the physical action) is always invoked -- the command is
    always sent; what's gated is whether the OUTCOME gets confirmed.

    read_sensor is an optional zero-arg callable returning a numeric reading
    (or raising/returning something non-numeric, which is treated as a
    failed sample). If read_sensor is None, the action still runs but the
    result is reported commanded_unverified per the "no sensor" rule --
    never upgraded to confirmed.

    Never raises: an exception from `actuate` itself is caught and reported
    as status "actuate_failed" rather than propagating, so this stays safe
    to call from an agent loop that must not crash on a hardware fault.
    """
    if read_sensor is None:
        try:
            actuate()
        except Exception as exc:
            return _result(
                False,
                "actuate_failed",
                f"actuate() raised before any sensor read was possible: {exc}",
                expected_delta=expected_delta,
                tolerance=tolerance,
                direction=direction,
            )
        return evaluate_gate(None, None, expected_delta, tolerance, direction)

    before = _median_of_readings(_sample_sensor(read_sensor, samples))

    try:
        actuate()
    except Exception as exc:
        return _result(
            False,
            "actuate_failed",
            f"actuate() raised: {exc}",
            before=before,
            expected_delta=expected_delta,
            tolerance=tolerance,
            direction=direction,
        )

    if settle_seconds > 0:
        time.sleep(settle_seconds)

    after = _median_of_readings(_sample_sensor(read_sensor, samples))
    return evaluate_gate(before, after, expected_delta, tolerance, direction)


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Robotics sensor gate: before/after tolerance-band check, "
        "never upgrading a sent command to a confirmed movement without a "
        "real sensor reading."
    )
    parser.add_argument(
        "--before",
        type=float,
        nargs="+",
        default=None,
        help="baseline sensor reading(s) taken before actuation; pass "
        "several values to median-filter noisy readings. Omit entirely if "
        "no sensor is available (commanded_unverified).",
    )
    parser.add_argument(
        "--after",
        type=float,
        nargs="+",
        default=None,
        help="sensor reading(s) taken after actuation; same rules as --before.",
    )
    parser.add_argument("--expected-delta", type=float, required=True, dest="expected_delta")
    parser.add_argument("--tolerance", type=float, required=True)
    parser.add_argument(
        "--direction",
        required=True,
        choices=_DIRECTIONS,
        help="increase/decrease: open-ended threshold (>= expected-delta - "
        "tolerance). either: symmetric +/-tolerance band around expected-delta.",
    )
    return parser


def run_cli(argv=None) -> dict:
    """Parse args and run evaluate_gate() over already-taken readings (or no
    readings at all). Never raises -- any parsing/computation failure becomes
    a clean invalid_input/commanded_unverified result instead of propagating."""
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    before = _median_of_readings(args.before) if args.before else None
    after = _median_of_readings(args.after) if args.after else None

    return evaluate_gate(before, after, args.expected_delta, args.tolerance, args.direction)


def main(argv=None) -> int:
    try:
        result = run_cli(argv)
    except SystemExit:
        # argparse's own --help / bad-args exit -- not a crash, let it pass.
        raise
    except Exception as exc:
        # Last-resort guard: this gate must never crash regardless of the
        # environment it runs in -- report the failure, don't raise it.
        result = _result(False, "invalid_input", f"unexpected failure: {exc}")
    print(json.dumps(result))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
