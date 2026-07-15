---
name: sensor-gate-contract-notes
description: unmassk-electronics sensor_gate.py (robotics branch) full hardening-pass suite -- linear mode, real code already existed, 69 tests, notable CLI median-filter gotcha
metadata:
  type: project
---

Test files: `unmassk-electronics/skills/electronics-robotics/scripts/tests/test_sensor_gate.py`
+ `conftest.py` (new `tests/` dir, first test infra for the robotics branch).
Module under test: `unmassk-electronics/skills/electronics-robotics/scripts/sensor_gate.py`
(already written when this pass started -- linear mode, not test-first, so
the full EXHAUSTION PROTOCOL ran immediately against real code, unlike
[serial-verify-contract-notes](serial-verify-contract-notes.md)'s acceptance-only
pass 1).

**Shape:** mirrors serial_verify.py's split -- `evaluate_gate(before, after,
expected_delta, tolerance, direction)` is a pure decision function (plain
numbers only, three gate shapes: increase/decrease open-ended-above,
either symmetric ±tolerance band), `_median_of_readings`/`_sample_sensor`/
`run_gate` form the deferred, hardware-free sensor layer (caller injects a
`read_sensor` callable -- never smbus/RPi.GPIO/board/busio/adafruit_*
imported by this module), and `run_cli`/`main` wrap it for the CLI. 69
tests, all pass, real exit code 0 (verified without piping through
tail/head -- pipe swallows the real code, `echo $?` after a pipe reports
the last pipeline stage's code, not pytest's; redirect to a file instead
when you need both output AND the real exit code).

**Genuine gotcha found by testing, not assumed from reading the source:**
the CLI's `run_cli()` runs `_median_of_readings()` on `--before`/`--after`
BEFORE calling `evaluate_gate()`. That median filter silently drops
non-finite readings (NaN/Infinity). So `--before nan` does NOT reach
`evaluate_gate`'s own NaN -> `invalid_input` branch -- the median filter
already reduced it to `None` first, so the CLI reports
`commanded_unverified`, not `invalid_input`. Only `evaluate_gate` called
*directly* (unit-level, bypassing the CLI's own filter) can exercise the
before/after invalid_input branches; via the CLI, only `--tolerance`/
`--expected-delta` (parsed as raw floats, never median-filtered) can reach
`invalid_input`. Wrote the CLI test to assert the VERIFIED behavior
(commanded_unverified) after first assuming invalid_input and being wrong
-- re-run the subprocess before hardcoding an assumption about a
multi-layer pipeline's error path.

**Explicit bool-exclusion in `_is_finite_number`:** the module deliberately
excludes `bool` even though `bool` is an `int` subclass in Python
(`isinstance(True, int)` is `True`) -- `evaluate_gate(True, 6.0, ...)` must
be `invalid_input`, not silently coerced to `1.0`. Worth a dedicated test
whenever a helper does `isinstance(x, (int, float))` for numeric validation
-- the bool-subclass trap is a recurring Python gotcha across this toolkit.

**`time.sleep` mocked, not real:** `run_gate`'s `settle_seconds` path calls
`time.sleep()` for real. Rather than let tests actually sleep (slow +
borderline-flaky under load), used `monkeypatch.setattr(module.time,
"sleep", lambda s: calls.append(s))` and asserted on the captured argument
(0.25, or empty list when settle_seconds=0) -- never asserted on wall-clock
timing itself. All other `run_gate`/`run_cli` tests in this suite pass
`settle_seconds=0` to skip the real sleep entirely and stay fast.

**main()'s "last-resort guard" (bare `except Exception`) tested via
fault-injection:** `main()` wraps `run_cli()` in a try/except that reports
`invalid_input` instead of raising. No real argv this suite could construct
actually triggers that branch (argparse errors raise `SystemExit`, which is
explicitly re-raised, not swallowed) -- so covering it required
`monkeypatch.setattr(module, "run_cli", boom)` to fault-inject a
`RuntimeError`, proving the guard actually catches and reports rather than
crashing. This is the one place in the suite where an internal function
(not just the sensor-read boundary) was swapped out, justified because the
branch is otherwise dead code from the test's vantage point and the
project's own threat model (`CLAUDE.md`: "the system against itself,"
robustness against internal failure is the actual priority here) makes
proving this guard real more valuable than leaving it untested.

**§34.5 real wiring:** `TestCliSubprocessRealWiring` runs the actual
`python sensor_gate.py` subprocess (no mocks) for confirmed/gate_failed/
commanded_unverified/invalid_input/argparse-exit-2 paths -- satisfies "at
least one test must exercise the real wiring end-to-end" beyond the
in-process `sensor_gate_module` fixture tests.

Conventions followed: same `import_module_from`/`run_cli_for`/
`parse_stdout_json` helper shapes as
[serial-verify-contract-notes](serial-verify-contract-notes.md)'s
conftest.py, for consistency across `unmassk-electronics`'s branches
(micro vs robotics) -- each conftest.py is self-contained per plugin
directory, no cross-plugin import.
