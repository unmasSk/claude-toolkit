"""
Regression tests for pre-memory-dedup-gate.py — Bug D.

BUG D (~line 158): `_TRAILER_PATTERN` only matches double-quoted trailer values:

    r'--trailer\\s+"(?:Memo|Remember)=([^"]*)"'

When a caller uses single quotes (`--trailer 'Memo=...'`) the regex does not
match, `trailer_match` is None, and the hook falls through to _allow_passthrough()
without checking for near-duplicates. Near-duplicate memos passed with single
quotes are silently accepted.

This is a real bug because:
  1. Python subprocess / shell expansion can preserve single quotes in the
     command string passed to the Bash tool.
  2. git-memory-commit.py itself may emit single-quoted --trailer arguments
     depending on the shell quoting context.

Expected behaviour after fix:
    --trailer 'Memo=...'     (single quotes) → near-dup IS detected, warns
    --trailer "Memo=..."     (double quotes) → near-dup IS detected (unchanged)
    unquoted  --trailer Memo=...             → near-dup IS detected

RED contract (these tests MUST fail before the fix):
    - test_single_quoted_trailer_near_dup_warns   → currently no warning (passes through)

GREEN controls (must pass before AND after fix):
    - test_double_quoted_trailer_near_dup_still_warns  (existing behaviour)
    - test_unquoted_trailer_near_dup_warns_after_fix   (new, also RED before fix)
"""

import json
import os
import sys

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script, run_cmd

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-memory-dedup-gate.py")


# ── Repo helpers ──────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Minimal git repo with user identity configured."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    """Add a memory commit with optional trailer block."""
    msg = subject if not trailers else subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _seed_memo(repo, text):
    """Commit an existing Memo entry so the dedup gate has something to compare against."""
    _commit(repo, "memo(test): seed entry", f"Memo: {text}")


def _run_hook(repo, command):
    """Invoke pre-memory-dedup-gate.py with a Bash tool_input payload.

    Returns (returncode, parsed_output_dict_or_None, raw_stdout, stderr).
    """
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    rc, stdout, stderr = run_script(HOOK_PATH, repo, input_text=payload)
    try:
        parsed = json.loads(stdout)
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


def _hook_specific(parsed):
    """Return the hookSpecificOutput sub-dict, or {} if absent."""
    if parsed is None:
        return {}
    return parsed.get("hookSpecificOutput", {})


def _has_warning(parsed):
    """True if the hook emitted a permissionDecisionReason (the near-dup warning)."""
    hso = _hook_specific(parsed)
    return bool(hso.get("permissionDecisionReason", ""))


# Shared text for all quote-variant tests — identical content, different quoting
_MEMO_TEXT = "preferir bun sobre node para el backend del proyecto"


# ── Bug D regression tests ────────────────────────────────────────────────

class TestSingleQuotedTrailerNearDupDetection:
    """_TRAILER_PATTERN must match single-quoted trailer values.

    Before the fix: single-quoted --trailer is silently ignored → no warning.
    After the fix: near-duplicate is detected → warning emitted.
    """

    def test_single_quoted_trailer_near_dup_warns(self, tmp_path):
        """A near-dup memo submitted with single quotes must trigger a warning.

        BUG: _TRAILER_PATTERN only matches double quotes.
        EXPECTED after fix: permissionDecisionReason is non-empty (warning issued).
        """
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _MEMO_TEXT)

        # Command uses single quotes — this is the failing case
        command = (
            f"python3 /path/to/git-memory-commit.py memo "
            f"--trailer 'Memo={_MEMO_TEXT}'"
        )

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        assert rc == 0, (
            f"Hook must always exit 0. Got rc={rc}. stderr={stderr!r}"
        )
        assert _has_warning(parsed), (
            f"Single-quoted --trailer 'Memo=...' near-dup must be detected and "
            f"produce a permissionDecisionReason. "
            f"hookSpecificOutput={_hook_specific(parsed)!r}"
        )

    def test_unquoted_trailer_near_dup_warns(self, tmp_path):
        """A near-dup memo submitted without any quotes must also trigger a warning.

        BUG: _TRAILER_PATTERN requires quotes (double or, after fix, single).
        After a complete fix, unquoted values should also be matched.
        EXPECTED after fix: permissionDecisionReason is non-empty.
        """
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _MEMO_TEXT)

        # Command uses no quotes around the trailer value
        command = (
            f"python3 /path/to/git-memory-commit.py memo "
            f"--trailer Memo={_MEMO_TEXT}"
        )

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        assert rc == 0, (
            f"Hook must always exit 0. Got rc={rc}. stderr={stderr!r}"
        )
        assert _has_warning(parsed), (
            f"Unquoted --trailer Memo=... near-dup must be detected. "
            f"hookSpecificOutput={_hook_specific(parsed)!r}"
        )


# ── Control tests — double-quoted path must still work ───────────────────

class TestDoubleQuotedTrailerStillWorks:
    """The existing double-quote path must not regress after the fix."""

    def test_double_quoted_trailer_near_dup_still_warns(self, tmp_path):
        """CONTROL: double-quoted --trailer \"Memo=...\" near-dup must still warn."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _MEMO_TEXT)

        # Command uses double quotes — existing behaviour
        command = (
            f'python3 /path/to/git-memory-commit.py memo '
            f'--trailer "Memo={_MEMO_TEXT}"'
        )

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        assert rc == 0, f"Hook must exit 0. Got rc={rc}."
        assert _has_warning(parsed), (
            f"Double-quoted near-dup must still be detected after fix. "
            f"hookSpecificOutput={_hook_specific(parsed)!r}"
        )

    def test_double_quoted_different_memo_no_warning(self, tmp_path):
        """CONTROL: a genuinely different memo must NOT warn (no false positive)."""
        repo = _make_repo(tmp_path)
        _seed_memo(repo, _MEMO_TEXT)

        different_text = "usar postgres para persistencia porque sqlite no escala en produccion"
        command = (
            f'python3 /path/to/git-memory-commit.py memo '
            f'--trailer "Memo={different_text}"'
        )

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        assert rc == 0, f"Hook must exit 0. Got rc={rc}."
        assert not _has_warning(parsed), (
            f"A genuinely different memo must NOT produce a warning. "
            f"hookSpecificOutput={_hook_specific(parsed)!r}"
        )
