"""Test suite for sensor_gate.py -- the robotics before/after tolerance-band
gate that proves a command actually moved the robot instead of merely
returning without error. sensor_gate.py already exists (this is a
linear-mode / hardening-style pass, not a test-first contract), so the
EXHAUSTION PROTOCOL runs in full against the real implementation.

Test surface declared before writing (function : branches/edge cases):
  - _is_finite_number: accepts int/float, rejects bool/NaN/Infinity/str/None
    (6 cases) -- private helper, tested directly since the module exposes it
    at module scope and the sibling suite (serial_verify) already reaches
    into module internals the same way.
  - evaluate_gate: before/after None -> commanded_unverified (3 combos);
    invalid_input for non-finite before/after/expected_delta/tolerance (incl.
    the explicit bool exclusion), negative tolerance, negative expected_delta,
    unknown direction (9 cases); direction="increase" pass/boundary/fail/
    overshoot (4); direction="decrease" mirror (4); direction="either"
    pass/both boundaries/overshoot-fails/undershoot-fails/exact-match (6).
  - _median_of_readings: odd count, even count, drops None, drops non-finite,
    empty -> None, all-None -> None, all-non-finite -> None, single value
    (8 cases).
  - _sample_sensor: collects N values via injected callable, exception ->
    None (not raised), samples=0 clamped to 1, samples negative clamped to 1
    (4 cases).
  - run_gate: confirmed via injected fake read_sensor, gate_failed via same,
    actuate always called, no-read_sensor -> commanded_unverified but
    actuate still runs, actuate raises (no sensor) -> actuate_failed,
    actuate raises (with sensor) -> actuate_failed with before already
    sampled, settle_seconds>0 sleeps, settle_seconds=0 skips sleep (8 cases).
  - run_cli: before/after provided computes gate, before/after omitted ->
    commanded_unverified, multiple values median-filtered (3 cases).
  - main: exit 0 on ok, exit 1 on gate_failed, argv=None falls back to
    sys.argv, an unexpected internal exception is caught and reported as
    invalid_input rather than raising (the documented "last-resort guard")
    (4 cases).
  - CLI subprocess (real wiring, no mocks -- the actual `python sensor_gate.py`
    process): confirmed exit 0, gate_failed exit 1, commanded_unverified
    (omitted --before/--after) exit 1, all-NaN --before degrades to
    commanded_unverified via the CLI's own median filter (not invalid_input
    -- verified, not assumed), negative --tolerance -> invalid_input exit 1,
    missing required args -> argparse exit 2, invalid --direction choice ->
    argparse exit 2 (7 cases).

Excluded: `_result` (trivial dict-shape factory, exercised transitively by
every single test's assertions on the returned dict) and `_build_arg_parser`
(trivial argparse wiring, exercised transitively by every CLI-level test).

Declared surface: 7 functions, ~27 branches, ~14 error paths (invalid_input
variants, actuate_failed variants, commanded_unverified variants, argparse
usage errors, main's exception fallback).

No hardware anywhere in this file -- `read_sensor` is always a plain
injected callable, matching the module's own design (it never imports a
driver, so nothing here needs to fake one beyond a function returning a
number).
"""

from __future__ import annotations

import json
import math
import statistics

from conftest import (
    RESULT_KEYS,
    parse_stdout_json,
    run_cli_for,
)


class TestIsFiniteNumberHelper:
    """Private helper, reachable directly at module scope -- same pattern
    the sibling suite uses to reach evaluate_lines."""

    def test_accepts_plain_int(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number(3) is True

    def test_accepts_plain_float(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number(3.5) is True

    def test_rejects_bool_despite_bool_being_an_int_subclass(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number(True) is False
        assert sensor_gate_module._is_finite_number(False) is False

    def test_rejects_nan(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number(math.nan) is False

    def test_rejects_infinity(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number(math.inf) is False
        assert sensor_gate_module._is_finite_number(-math.inf) is False

    def test_rejects_non_numeric_string(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number("3.5") is False

    def test_rejects_none(self, sensor_gate_module):
        assert sensor_gate_module._is_finite_number(None) is False


class TestEvaluateGateCommandedUnverified:
    """before is None or after is None -> commanded_unverified, never
    upgraded to confirmed."""

    def test_before_none_is_commanded_unverified(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(None, 6.0, 3.0, 1.0, "decrease")

        assert set(result.keys()) == RESULT_KEYS
        assert result["ok"] is False
        assert result["status"] == "commanded_unverified"

    def test_after_none_is_commanded_unverified(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, None, 3.0, 1.0, "decrease")

        assert result["ok"] is False
        assert result["status"] == "commanded_unverified"

    def test_both_none_is_commanded_unverified(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(None, None, 3.0, 1.0, "either")

        assert result["ok"] is False
        assert result["status"] == "commanded_unverified"

    def test_commanded_unverified_wins_even_with_otherwise_invalid_fields(self, sensor_gate_module):
        # before is None short-circuits BEFORE the invalid_input checks run --
        # a negative tolerance never gets a chance to be flagged.
        result = sensor_gate_module.evaluate_gate(None, 6.0, 3.0, -1.0, "increase")

        assert result["status"] == "commanded_unverified"


class TestEvaluateGateInvalidInput:
    def test_before_nan_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(math.nan, 6.0, 3.0, 1.0, "increase")

        assert result["ok"] is False
        assert result["status"] == "invalid_input"
        assert "before" in result["reason"]

    def test_before_infinity_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(math.inf, 6.0, 3.0, 1.0, "increase")

        assert result["status"] == "invalid_input"
        assert "before" in result["reason"]

    def test_after_nan_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, math.nan, 3.0, 1.0, "increase")

        assert result["status"] == "invalid_input"
        assert "after" in result["reason"]

    def test_expected_delta_nan_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 13.0, math.nan, 1.0, "increase")

        assert result["status"] == "invalid_input"
        assert "expected_delta" in result["reason"]

    def test_tolerance_infinity_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 13.0, 3.0, math.inf, "increase")

        assert result["status"] == "invalid_input"
        assert "tolerance" in result["reason"]

    def test_before_bool_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(True, 6.0, 3.0, 1.0, "increase")

        assert result["status"] == "invalid_input"
        assert "before" in result["reason"]

    def test_before_non_numeric_string_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate("close", 6.0, 3.0, 1.0, "increase")

        assert result["status"] == "invalid_input"
        assert "before" in result["reason"]

    def test_negative_tolerance_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 13.0, 3.0, -0.5, "increase")

        assert result["status"] == "invalid_input"
        assert "tolerance" in result["reason"]

    def test_negative_expected_delta_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 13.0, -3.0, 1.0, "increase")

        assert result["status"] == "invalid_input"
        assert "expected_delta" in result["reason"]

    def test_unknown_direction_is_invalid_input(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 13.0, 3.0, 1.0, "sideways")

        assert result["status"] == "invalid_input"
        assert "direction" in result["reason"]

    def test_invalid_input_never_raises(self, sensor_gate_module):
        # every call in this class already proves this implicitly (an
        # exception would fail the test at call time), this test names the
        # guarantee explicitly for the coverage declaration.
        result = sensor_gate_module.evaluate_gate(object(), 6.0, 3.0, 1.0, "increase")

        assert result["status"] == "invalid_input"


class TestEvaluateGateIncreaseDirection:
    """observed_delta = after - before; passes when
    observed_delta >= expected_delta - tolerance (open-ended above)."""

    def test_exact_expected_delta_passes(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 13.0, 3.0, 1.0, "increase")

        assert result["ok"] is True
        assert result["status"] == "confirmed"
        assert result["observed_delta"] == 3.0

    def test_overshoot_still_passes_open_ended(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 20.0, 3.0, 1.0, "increase")

        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_at_lower_tolerance_boundary_passes(self, sensor_gate_module):
        # observed_delta == expected_delta - tolerance -> the >= boundary
        result = sensor_gate_module.evaluate_gate(10.0, 12.0, 3.0, 1.0, "increase")

        assert result["observed_delta"] == 2.0
        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_just_below_tolerance_boundary_fails(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 11.9, 3.0, 1.0, "increase")

        assert result["ok"] is False
        assert result["status"] == "gate_failed"


class TestEvaluateGateDecreaseDirection:
    """observed_delta = before - after; same open-ended-above threshold,
    opposite sign convention."""

    def test_exact_expected_delta_passes(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 7.0, 3.0, 1.0, "decrease")

        assert result["ok"] is True
        assert result["status"] == "confirmed"
        assert result["observed_delta"] == 3.0

    def test_overshoot_still_passes_open_ended(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 1.0, 3.0, 1.0, "decrease")

        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_at_lower_tolerance_boundary_passes(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 8.0, 3.0, 1.0, "decrease")

        assert result["observed_delta"] == 2.0
        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_just_below_tolerance_boundary_fails(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(10.0, 8.1, 3.0, 1.0, "decrease")

        assert result["ok"] is False
        assert result["status"] == "gate_failed"


class TestEvaluateGateEitherDirection:
    """observed_delta = abs(after - before); passes when
    abs(observed_delta - expected_delta) <= tolerance (symmetric two-sided
    band -- overshoot fails same as undershoot, unlike increase/decrease)."""

    def test_exact_match_passes(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(0.0, 90.0, 90.0, 10.0, "either")

        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_at_positive_boundary_passes(self, sensor_gate_module):
        # abs(observed - expected) == tolerance, the <= boundary
        result = sensor_gate_module.evaluate_gate(0.0, 100.0, 90.0, 10.0, "either")

        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_at_negative_boundary_passes(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(0.0, 80.0, 90.0, 10.0, "either")

        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_overshoot_beyond_tolerance_fails(self, sensor_gate_module):
        # unlike "increase"/"decrease", the either-band is NOT open-ended --
        # turning too far also fails.
        result = sensor_gate_module.evaluate_gate(0.0, 105.0, 90.0, 10.0, "either")

        assert result["ok"] is False
        assert result["status"] == "gate_failed"

    def test_undershoot_beyond_tolerance_fails(self, sensor_gate_module):
        result = sensor_gate_module.evaluate_gate(0.0, 75.0, 90.0, 10.0, "either")

        assert result["ok"] is False
        assert result["status"] == "gate_failed"

    def test_direction_reversed_magnitude_still_matches(self, sensor_gate_module):
        # abs() means a negative swing of the same magnitude also confirms.
        result = sensor_gate_module.evaluate_gate(0.0, -90.0, 90.0, 10.0, "either")

        assert result["ok"] is True
        assert result["status"] == "confirmed"


class TestMedianOfReadings:
    def test_odd_count_returns_true_median(self, sensor_gate_module):
        readings = [10.0, 12.0, 11.0]

        result = sensor_gate_module._median_of_readings(readings)

        assert result == statistics.median(readings)

    def test_even_count_returns_true_median(self, sensor_gate_module):
        readings = [1.0, 2.0, 3.0, 4.0]

        result = sensor_gate_module._median_of_readings(readings)

        assert result == statistics.median(readings)

    def test_drops_none_entries_before_taking_median(self, sensor_gate_module):
        readings = [10.0, None, 12.0, None, 11.0]

        result = sensor_gate_module._median_of_readings(readings)

        assert result == statistics.median([10.0, 12.0, 11.0])

    def test_drops_non_finite_entries_before_taking_median(self, sensor_gate_module):
        readings = [10.0, math.nan, 12.0, math.inf, 11.0]

        result = sensor_gate_module._median_of_readings(readings)

        assert result == statistics.median([10.0, 12.0, 11.0])

    def test_empty_list_returns_none(self, sensor_gate_module):
        assert sensor_gate_module._median_of_readings([]) is None

    def test_all_none_returns_none(self, sensor_gate_module):
        assert sensor_gate_module._median_of_readings([None, None, None]) is None

    def test_all_non_finite_returns_none(self, sensor_gate_module):
        assert sensor_gate_module._median_of_readings([math.nan, math.inf, -math.inf]) is None

    def test_single_usable_value_returns_that_value(self, sensor_gate_module):
        assert sensor_gate_module._median_of_readings([7.5, None, math.nan]) == 7.5


class TestSampleSensor:
    def test_collects_samples_count_values_via_injected_callable(self, sensor_gate_module):
        values = iter([1.0, 2.0, 3.0])

        def fake_read_sensor():
            return next(values)

        readings = sensor_gate_module._sample_sensor(fake_read_sensor, 3)

        assert readings == [1.0, 2.0, 3.0]

    def test_exception_recorded_as_none_not_raised(self, sensor_gate_module):
        def flaky_sensor():
            raise RuntimeError("hc-sr04 glitch")

        readings = sensor_gate_module._sample_sensor(flaky_sensor, 3)

        assert readings == [None, None, None]

    def test_samples_zero_clamped_to_one_call(self, sensor_gate_module):
        calls = []

        def fake_read_sensor():
            calls.append(1)
            return 7.0

        readings = sensor_gate_module._sample_sensor(fake_read_sensor, 0)

        assert len(calls) == 1
        assert readings == [7.0]

    def test_samples_negative_clamped_to_one_call(self, sensor_gate_module):
        calls = []

        def fake_read_sensor():
            calls.append(1)
            return 7.0

        readings = sensor_gate_module._sample_sensor(fake_read_sensor, -5)

        assert len(calls) == 1
        assert readings == [7.0]


class TestRunGate:
    """Orchestrates before -> actuate -> settle -> after -> evaluate. Every
    read_sensor here is an injected fake (no hardware); settle_seconds is
    always 0 unless the test is specifically about the sleep call, to keep
    the suite fast and non-flaky."""

    def test_confirmed_when_injected_readings_move_as_expected(self, sensor_gate_module):
        readings = iter([10.0, 10.0, 10.0, 6.0, 6.0, 6.0])

        def fake_read_sensor():
            return next(readings)

        actuate_calls = []

        def fake_actuate():
            actuate_calls.append(1)

        result = sensor_gate_module.run_gate(
            fake_actuate,
            expected_delta=3.0,
            tolerance=1.0,
            direction="decrease",
            read_sensor=fake_read_sensor,
            samples=3,
            settle_seconds=0,
        )

        assert result["ok"] is True
        assert result["status"] == "confirmed"
        assert len(actuate_calls) == 1

    def test_gate_failed_when_injected_readings_do_not_move_enough(self, sensor_gate_module):
        readings = iter([10.0, 10.0, 10.0, 9.8, 9.8, 9.8])

        def fake_read_sensor():
            return next(readings)

        result = sensor_gate_module.run_gate(
            lambda: None,
            expected_delta=3.0,
            tolerance=1.0,
            direction="decrease",
            read_sensor=fake_read_sensor,
            samples=3,
            settle_seconds=0,
        )

        assert result["ok"] is False
        assert result["status"] == "gate_failed"

    def test_no_read_sensor_is_commanded_unverified_but_actuate_still_runs(self, sensor_gate_module):
        actuate_calls = []

        def fake_actuate():
            actuate_calls.append(1)

        result = sensor_gate_module.run_gate(
            fake_actuate,
            expected_delta=3.0,
            tolerance=1.0,
            direction="increase",
            read_sensor=None,
        )

        assert result["status"] == "commanded_unverified"
        assert actuate_calls == [1]

    def test_actuate_raises_without_read_sensor_is_actuate_failed(self, sensor_gate_module):
        def boom():
            raise RuntimeError("motor stalled")

        result = sensor_gate_module.run_gate(
            boom,
            expected_delta=3.0,
            tolerance=1.0,
            direction="increase",
            read_sensor=None,
        )

        assert result["ok"] is False
        assert result["status"] == "actuate_failed"
        assert "motor stalled" in result["reason"]
        assert result["before"] is None

    def test_actuate_raises_with_read_sensor_keeps_the_before_sample(self, sensor_gate_module):
        def fake_read_sensor():
            return 10.0

        def boom():
            raise RuntimeError("motor stalled")

        result = sensor_gate_module.run_gate(
            boom,
            expected_delta=3.0,
            tolerance=1.0,
            direction="increase",
            read_sensor=fake_read_sensor,
            samples=3,
            settle_seconds=0,
        )

        assert result["status"] == "actuate_failed"
        assert result["before"] == 10.0
        assert result["after"] is None

    def test_settle_seconds_positive_calls_time_sleep_with_that_value(self, sensor_gate_module, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr(sensor_gate_module.time, "sleep", lambda s: sleep_calls.append(s))

        sensor_gate_module.run_gate(
            lambda: None,
            expected_delta=1.0,
            tolerance=1.0,
            direction="increase",
            read_sensor=lambda: 5.0,
            samples=1,
            settle_seconds=0.25,
        )

        assert sleep_calls == [0.25]

    def test_settle_seconds_zero_skips_sleep(self, sensor_gate_module, monkeypatch):
        sleep_calls = []
        monkeypatch.setattr(sensor_gate_module.time, "sleep", lambda s: sleep_calls.append(s))

        sensor_gate_module.run_gate(
            lambda: None,
            expected_delta=1.0,
            tolerance=1.0,
            direction="increase",
            read_sensor=lambda: 5.0,
            samples=1,
            settle_seconds=0,
        )

        assert sleep_calls == []


class TestRunCliUnit:
    """run_cli(argv) called directly (no subprocess) -- fast unit-level
    coverage of the argv -> evaluate_gate wiring."""

    def test_before_and_after_provided_computes_the_gate(self, sensor_gate_module):
        result = sensor_gate_module.run_cli(
            [
                "--before", "10.0",
                "--after", "6.0",
                "--expected-delta", "3.0",
                "--tolerance", "1.0",
                "--direction", "decrease",
            ]
        )

        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_before_and_after_omitted_is_commanded_unverified(self, sensor_gate_module):
        result = sensor_gate_module.run_cli(
            [
                "--expected-delta", "3.0",
                "--tolerance", "1.0",
                "--direction", "increase",
            ]
        )

        assert result["status"] == "commanded_unverified"

    def test_multiple_values_are_median_filtered(self, sensor_gate_module):
        before_values = [10.0, 12.0, 11.0]
        after_values = [6.0, 8.0, 7.0]

        result = sensor_gate_module.run_cli(
            [
                "--before", *[str(v) for v in before_values],
                "--after", *[str(v) for v in after_values],
                "--expected-delta", "3.0",
                "--tolerance", "1.0",
                "--direction", "decrease",
            ]
        )

        assert result["before"] == statistics.median(before_values)
        assert result["after"] == statistics.median(after_values)


class TestMainUnit:
    def test_returns_0_when_ok(self, sensor_gate_module, capsys):
        exit_code = sensor_gate_module.main(
            [
                "--before", "10.0",
                "--after", "6.0",
                "--expected-delta", "3.0",
                "--tolerance", "1.0",
                "--direction", "decrease",
            ]
        )

        assert exit_code == 0
        printed = json.loads(capsys.readouterr().out.strip())
        assert printed["ok"] is True

    def test_returns_1_when_gate_failed(self, sensor_gate_module, capsys):
        exit_code = sensor_gate_module.main(
            [
                "--before", "10.0",
                "--after", "9.8",
                "--expected-delta", "3.0",
                "--tolerance", "1.0",
                "--direction", "decrease",
            ]
        )

        assert exit_code == 1
        printed = json.loads(capsys.readouterr().out.strip())
        assert printed["ok"] is False

    def test_argv_none_falls_back_to_sys_argv(self, sensor_gate_module, monkeypatch, capsys):
        monkeypatch.setattr(
            sensor_gate_module.sys,
            "argv",
            [
                "sensor_gate.py",
                "--before", "10.0",
                "--after", "6.0",
                "--expected-delta", "3.0",
                "--tolerance", "1.0",
                "--direction", "decrease",
            ],
        )

        exit_code = sensor_gate_module.main()

        assert exit_code == 0
        printed = json.loads(capsys.readouterr().out.strip())
        assert printed["ok"] is True

    def test_unexpected_internal_exception_is_caught_not_raised(self, sensor_gate_module, monkeypatch, capsys):
        # the documented "last-resort guard" -- fault-inject run_cli itself
        # (the only way to reach this branch, since run_cli's own code never
        # raises for any argv this suite can construct) to prove main() never
        # lets an unexpected exception propagate as a traceback.
        def boom(argv):
            raise RuntimeError("unexpected parser failure")

        monkeypatch.setattr(sensor_gate_module, "run_cli", boom)

        exit_code = sensor_gate_module.main(["--direction", "increase"])

        assert exit_code == 1
        printed = json.loads(capsys.readouterr().out.strip())
        assert printed["status"] == "invalid_input"
        assert "unexpected parser failure" in printed["reason"]


class TestCliSubprocessRealWiring:
    """Real `python sensor_gate.py` subprocess calls -- the §34.5 "at least
    one test must exercise the real wiring end-to-end" requirement. No
    mocking here at all; this is the actual CLI a user or another script
    would invoke."""

    def test_confirmed_exit_0_json_stdout_no_traceback(self):
        proc = run_cli_for(
            "--before", "10.0", "10.0", "10.0",
            "--after", "6.0", "6.0", "6.0",
            "--expected-delta", "3.0",
            "--tolerance", "1.0",
            "--direction", "decrease",
        )

        assert proc.returncode == 0
        assert "Traceback (most recent call last)" not in proc.stdout
        assert "Traceback (most recent call last)" not in proc.stderr

        result = parse_stdout_json(proc)
        assert set(result.keys()) == RESULT_KEYS
        assert result["ok"] is True
        assert result["status"] == "confirmed"

    def test_gate_failed_exit_1_no_traceback(self):
        proc = run_cli_for(
            "--before", "10.0",
            "--after", "9.5",
            "--expected-delta", "3.0",
            "--tolerance", "1.0",
            "--direction", "decrease",
        )

        assert proc.returncode == 1
        assert "Traceback (most recent call last)" not in proc.stdout
        assert "Traceback (most recent call last)" not in proc.stderr

        result = parse_stdout_json(proc)
        assert result["ok"] is False
        assert result["status"] == "gate_failed"

    def test_omitted_before_and_after_is_commanded_unverified_exit_1(self):
        proc = run_cli_for(
            "--expected-delta", "3.0",
            "--tolerance", "1.0",
            "--direction", "increase",
        )

        assert proc.returncode == 1

        result = parse_stdout_json(proc)
        assert result["status"] == "commanded_unverified"

    def test_all_nan_before_degrades_to_commanded_unverified_via_median_filter(self):
        # --before is parsed to a float list, then run through
        # _median_of_readings BEFORE evaluate_gate ever sees it -- a
        # single NaN reading is dropped by the median filter, leaving
        # before=None. This is NOT evaluate_gate's own invalid_input path
        # (verified against the real subprocess, not assumed from reading
        # the source alone).
        proc = run_cli_for(
            "--before", "nan",
            "--after", "9.0",
            "--expected-delta", "3.0",
            "--tolerance", "1.0",
            "--direction", "increase",
        )

        assert proc.returncode == 1
        result = parse_stdout_json(proc)
        assert result["status"] == "commanded_unverified"
        assert result["before"] is None

    def test_negative_tolerance_is_invalid_input_exit_1(self):
        proc = run_cli_for(
            "--before", "10.0",
            "--after", "9.0",
            "--expected-delta", "3.0",
            "--tolerance", "-1.0",
            "--direction", "increase",
        )

        assert proc.returncode == 1
        result = parse_stdout_json(proc)
        assert result["status"] == "invalid_input"

    def test_missing_required_args_is_argparse_usage_error_exit_2(self):
        proc = run_cli_for("--direction", "increase")

        assert proc.returncode == 2
        assert "usage" in proc.stderr.lower()

    def test_invalid_direction_choice_is_argparse_usage_error_exit_2(self):
        proc = run_cli_for(
            "--expected-delta", "3.0",
            "--tolerance", "1.0",
            "--direction", "sideways",
        )

        assert proc.returncode == 2
        assert "usage" in proc.stderr.lower()
