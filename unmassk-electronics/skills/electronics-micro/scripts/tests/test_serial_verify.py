"""Acceptance contract for serial_verify.py -- the deterministic serial-assert
GATE used after a firmware flash to decide boot-ok vs crash-loop, for when
the young platformio-mcp isn't present. A flash reported "done" when the
board is actually crash-looping is exactly the silent-failure class this
toolkit exists to prevent -- the gate must be decisive and must never crash
itself.

TEST-FIRST contract pass: serial_verify.py does not exist yet. These tests
are pinned at ACCEPTANCE granularity -- the behaviors that define "done" per
the task contract -- not the exhaustive branch/edge-case sweep (case
sensitivity, empty reject list, streaming/early-exit on an unbounded
generator, a real pty-backed CLI round trip, etc.). That sweep belongs to
the hardening pass once Ultron has implemented against this contract and
there is real code to measure. Ultron implements until these go from RED to
GREEN with no changes to the tests themselves.

Decision rules pinned (order matters):
  1. Any reject pattern anywhere in the stream -> ok:false, reason names the
     pattern -- wins/short-circuits even if the expect marker appeared
     earlier in the stream.
  2. Else the expect marker appears anywhere -> ok:true.
  3. Else (stream ends with neither) -> ok:false, reason ==
     "expect marker never seen" (exact wording pinned by the contract).

evaluate_lines(lines_iterable, expect, reject_patterns) -> dict is the pure
decision function -- no pyserial, no hardware needed to exercise it (fake
line lists only). The CLI wraps it around a real serial port; only its
unopenable-port failure path is covered here, per the task's explicit scope
for this pass -- a real-port round trip is deferred to the hardening pass.
"""

from __future__ import annotations

from conftest import (
    EXPECT_MARKER,
    REJECT_CSV,
    REJECT_PATTERNS,
    RESULT_KEYS,
    parse_stdout_json,
    run_cli_for,
)


class TestEvaluateLinesDecision:
    """The pure decision function -- fake line lists, no hardware, no
    pyserial import required to exercise it."""

    def test_expect_marker_present_no_reject_is_ok_true(self, serial_verify_module):
        lines = [
            "Booting firmware...",
            "Connecting to WiFi...",
            EXPECT_MARKER,
            "System ready",
        ]

        result = serial_verify_module.evaluate_lines(
            lines, EXPECT_MARKER, list(REJECT_PATTERNS)
        )

        assert set(result.keys()) == RESULT_KEYS
        assert result["ok"] is True
        assert result["matched_expect"] is True
        assert result["matched_reject"] is None
        assert isinstance(result["reason"], str) and result["reason"] != ""

    def test_reject_pattern_present_is_ok_false_and_names_it(self, serial_verify_module):
        crash_pattern = "Guru Meditation"
        lines = [
            "Booting firmware...",
            f"{crash_pattern} Error: Core 0 panic'ed",
            "Rebooting...",
        ]

        result = serial_verify_module.evaluate_lines(
            lines, EXPECT_MARKER, list(REJECT_PATTERNS)
        )

        assert result["ok"] is False
        assert result["matched_reject"] == crash_pattern
        assert crash_pattern in result["reason"]

    def test_reject_after_expect_still_ok_false_crash_wins(self, serial_verify_module):
        crash_pattern = "Guru Meditation"
        lines = [
            EXPECT_MARKER,
            "running fine for a while...",
            f"{crash_pattern} Error: Core 0 panic'ed",
        ]

        result = serial_verify_module.evaluate_lines(
            lines, EXPECT_MARKER, list(REJECT_PATTERNS)
        )

        assert result["ok"] is False
        assert result["matched_reject"] == crash_pattern
        # the expect marker really was seen in this stream -- the reject
        # match must still win over it, not merely coexist unnoticed.
        assert result["matched_expect"] is True

    def test_neither_marker_present_stream_ends_ok_false_never_seen(self, serial_verify_module):
        lines = [
            "some unrelated boot chatter",
            "still nothing relevant here",
            "more noise before the stream ends",
        ]

        result = serial_verify_module.evaluate_lines(
            lines, EXPECT_MARKER, list(REJECT_PATTERNS)
        )

        assert result["ok"] is False
        assert result["matched_expect"] is False
        assert result["matched_reject"] is None
        assert result["reason"] == "expect marker never seen"

    def test_empty_stream_is_ok_false(self, serial_verify_module):
        result = serial_verify_module.evaluate_lines([], EXPECT_MARKER, list(REJECT_PATTERNS))

        assert result["ok"] is False
        assert result["matched_expect"] is False
        assert result["matched_reject"] is None
        assert result["reason"] == "expect marker never seen"


class TestCliUnopenablePort:
    """The CLI wraps evaluate_lines around a real serial port. Per the
    task's explicit scope for this contract pass, only the unopenable-port
    failure path is covered here -- no hardware, no pty round trip (that's
    deferred to the hardening pass)."""

    def test_bogus_port_exits_nonzero_with_clean_json_no_traceback(self):
        proc = run_cli_for(
            "--port", "/nonexistent/tty.does-not-exist",
            "--baud", "115200",
            "--expect", EXPECT_MARKER,
            "--reject", REJECT_CSV,
            "--timeout", "5",
        )

        assert proc.returncode != 0
        assert "Traceback (most recent call last)" not in proc.stderr
        assert "Traceback (most recent call last)" not in proc.stdout

        result = parse_stdout_json(proc)

        assert set(result.keys()) == RESULT_KEYS
        assert result["ok"] is False
        assert isinstance(result["reason"], str) and result["reason"] != ""
