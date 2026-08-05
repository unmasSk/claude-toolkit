"""
Regression test [T1]: build_commit_message() must not let a raw CR/LF
embedded inside a --trailer VALUE split that trailer across multiple
PHYSICAL lines.

Bug (Ultron fix, bin/git-memory-commit.py::build_commit_message, see the
"BUG T1 fix" comment at the trailer-emission loop): before the fix, a
value containing a real "\n" (an agent wrote free text with an actual
newline, not an escaped one) was written to the commit message verbatim.
A line-based trailer reader -- one that recognizes a trailer up to its own
physical line -- would stop matching the `Key: value` regex at the embedded
newline, silently dropping the rest of the value. No exception, no warning
-- the reader would just hand back a truncated value and the rest of what
the agent wrote vanished on every future read.

The fix: build_commit_message() now runs `sanitize_trailer_value()`
(already canonical for the read side) on every --trailer value before
writing it, then collapses any resulting run of 2+ spaces (a CRLF pair
produces two substitutions back to back). This guarantees the trailer is
always emitted as ONE physical line, so any line-based reader -- which
splits the body on literal "\n" -- can never lose anything past a
newline that was in the ORIGINAL value: there is no longer a real
newline in the emitted trailer to split on.

Retirement note (memoria-v2 cleanup pass): the original read-side half of
this test called lib/parsing.py::scan_trailers_memory(), which has since
been retired with no direct successor of that exact name. The line-based
full-body scan it used to prove (every "Key: value" line recovered
regardless of position) is still live today in
lib/parsing.py::parse_trailers_full() -- same per-line regex, same
full-body scan, same "no line-based reader ever sees a raw embedded
newline" contract this test protects. Swapped to that live function; the
behavior under test (the generator's one-physical-line guarantee) is
unchanged.

Threat model (per this project's CLAUDE.md / unmassk-standards §34): this
is producer -> consumer data-integrity (the system against itself), not an
external attacker. Producer = build_commit_message() writing a --trailer
value that happens to contain a real newline (e.g. pasted free text).
Consumer = parse_trailers_full() (a line-based trailer reader). Nothing
here simulates malicious input.
"""

import importlib.util
import os
import sys

from conftest import SOURCE_ROOT, BIN_DIR

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from parsing import parse_trailers_full

COMMIT_SCRIPT = os.path.join(BIN_DIR, "git-memory-commit.py")

# Import the hyphenated script directly (not importable via normal
# `import`) -- same technique as test_git_memory_commit_subject_length.py
# -- to reach the real build_commit_message() under test.
_spec = importlib.util.spec_from_file_location("git_memory_commit_under_test_newline", COMMIT_SCRIPT)
_commit_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_commit_mod)
build_commit_message = _commit_mod.build_commit_message


class TestTrailerNewlineNoSilentLoss:
    """One behavior: a real CR/LF embedded inside a --trailer value must
    never split the trailer into multiple physical lines, and
    scan_trailers_memory() must always recover the value in full."""

    def test_trailer_value_with_embedded_newline_survives_build_and_scan_intact(self):
        # ── (1) LF value: built message keeps Memo on ONE physical line ──
        msg = build_commit_message(
            "memo", "deadend/x", "q", None,
            ["Memo=deadend - linea1 IMPORTANTE\nlinea2 NO_DEBE_PERDERSE"],
        )
        lines = msg.split("\n")
        memo_lines = [l for l in lines if l.startswith("Memo:")]
        assert len(memo_lines) == 1, (
            "the Memo value must be emitted on exactly ONE physical line -- "
            f"got {len(memo_lines)} lines starting with 'Memo:': {memo_lines!r}"
        )
        # The line after the subject/blank and before Co-Authored-By must
        # not contain an orphan physical line holding the post-newline
        # fragment on its own (unprefixed) line -- that shape is exactly
        # what let scan_trailers_memory() lose it before the fix.
        body_between = [l for l in lines[1:-2] if not l.startswith("Memo:")]
        assert "NO_DEBE_PERDERSE" not in "\n".join(body_between), (
            "the post-newline fragment must not survive as its own orphan "
            f"physical line: {lines!r}"
        )

        # ── (2) parse_trailers_full() (live line-based trailer reader) ───
        # recovers the COMPLETE value -- nothing after the embedded
        # newline is silently lost, and no raw "\n" remains inside it.
        trailers = parse_trailers_full(msg)
        value = trailers.get("Memo")
        assert value is not None, "parse_trailers_full() must find a Memo trailer at all"
        assert "linea1 IMPORTANTE" in value, f"first half of the value must survive: {value!r}"
        assert "linea2 NO_DEBE_PERDERSE" in value, (
            "second half (past the embedded newline) must NOT be silently "
            f"lost -- this is exactly bug T1. got: {value!r}"
        )
        assert "\n" not in value, f"recovered value must not contain a raw newline: {value!r}"

        # ── (4, anti-vacuity) prove this isn't a trivially-true assert ───
        # Without the fix, scan_trailers_memory() would only ever see the
        # first physical line, i.e. "deadend - linea1 IMPORTANTE" -- line2
        # would not exist in the recovered value at all. Assert the
        # recovered value is strictly longer than that truncated
        # fragment, so a regression that starts losing line2 again would
        # fail this specific assertion, not just the substring check above.
        truncated_at_newline = "deadend - linea1 IMPORTANTE"
        assert len(value) > len(truncated_at_newline), (
            "recovered value must be longer than the pre-fix truncated "
            f"fragment -- got {value!r} (len {len(value)}) vs truncated "
            f"fragment len {len(truncated_at_newline)}; if not longer, "
            "line2 is being lost again"
        )

        # ── (3) CRLF and multiple embedded newlines also survive intact,
        # collapsed to ONE physical line, with no double-space artifacts
        # (a CRLF pair produces two control-byte substitutions back to
        # back -- the fix's collapse step must reduce that run to one
        # space, not leave it doubled).
        crlf_msg = build_commit_message(
            "memo", "deadend/x", "q", None,
            ["Memo=deadend - primera\r\nsegunda parte CRLF"],
        )
        crlf_value = parse_trailers_full(crlf_msg).get("Memo")
        assert crlf_value is not None
        assert "primera" in crlf_value and "segunda parte CRLF" in crlf_value, (
            f"CRLF-split fragments must both survive: {crlf_value!r}"
        )
        assert "  " not in crlf_value, f"CRLF collapse must not leave a double space: {crlf_value!r}"
        assert "\r" not in crlf_value and "\n" not in crlf_value

        multi_msg = build_commit_message(
            "memo", "deadend/x", "q", None,
            ["Memo=uno\ndos\ntres\ncuatro"],
        )
        multi_value = parse_trailers_full(multi_msg).get("Memo")
        assert multi_value is not None
        for fragment in ("uno", "dos", "tres", "cuatro"):
            assert fragment in multi_value, (
                f"fragment {fragment!r} must survive across multiple "
                f"embedded newlines: {multi_value!r}"
            )
        assert "  " not in multi_value, f"no double spaces should remain: {multi_value!r}"
        assert "\n" not in multi_value
