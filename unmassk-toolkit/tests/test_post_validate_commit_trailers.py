"""
Regression tests for post-validate-commit-trailers.py — Bug A.

BUG A (~line 183): `int(exit_code)` is called without try/except.
When `exit_code` is a non-numeric string (e.g. "zero") this raises
ValueError; when it is a list (e.g. [0]) it raises TypeError.
Both crash the hook and it exits 1 instead of 0.

Because this is a PostToolUse hook it MUST be fail-open: exit 0 always,
even on unexpected input.

Expected behaviour after fix:
    exit_code non-parseable as int  → treat as "not a failure", continue
    exit_code is a list             → same: fail-open, continue
    (no change to the happy path where exit_code is a real int or "0")

RED contract (these tests MUST fail before the fix):
    - test_exit_code_string_word_is_fail_open   → currently crashes → rc != 0
    - test_exit_code_list_is_fail_open          → currently crashes → rc != 0
"""

import json
import os
import sys

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script, run_cmd

HOOK_PATH = os.path.join(HOOKS_DIR, "post-validate-commit-trailers.py")


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


def _run_hook(repo, payload_dict):
    """Invoke post-validate-commit-trailers.py with JSON stdin.

    Returns (returncode, raw_stdout, stderr).
    """
    payload = json.dumps(payload_dict)
    rc, stdout, stderr = run_script(HOOK_PATH, repo, input_text=payload)
    return rc, stdout, stderr


# ── Bug A regression tests ────────────────────────────────────────────────

class TestExitCodeNonNumericIsFailOpen:
    """PostToolUse hook must exit 0 even when exit_code cannot be cast to int.

    Before the fix: `int(exit_code)` raises ValueError / TypeError → exit 1.
    After the fix: non-parseable exit_code is treated as fail-open → exit 0.
    """

    def test_exit_code_string_word_is_fail_open(self, tmp_path):
        """exit_code="zero" (word, not digit) must not crash the hook.

        BUG: int("zero") raises ValueError → hook exits 1.
        EXPECTED after fix: hook exits 0 (fail-open).
        """
        repo = _make_repo(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m test"},
            "tool_output": {"exit_code": "zero"},
        }

        rc, stdout, stderr = _run_hook(repo, payload)

        assert rc == 0, (
            f"PostToolUse hook must exit 0 (fail-open) when exit_code='zero' "
            f"(non-numeric string). Got rc={rc}. stderr={stderr!r}"
        )

    def test_exit_code_list_is_fail_open(self, tmp_path):
        """exit_code=[0] (list, not int/str) must not crash the hook.

        BUG: int([0]) raises TypeError → hook exits 1.
        EXPECTED after fix: hook exits 0 (fail-open).
        """
        repo = _make_repo(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m test"},
            "tool_output": {"exit_code": [0]},
        }

        rc, stdout, stderr = _run_hook(repo, payload)

        assert rc == 0, (
            f"PostToolUse hook must exit 0 (fail-open) when exit_code=[0] "
            f"(list, not int/str). Got rc={rc}. stderr={stderr!r}"
        )

    def test_exit_code_zero_integer_still_continues(self, tmp_path):
        """CONTROL: exit_code=0 (happy path) must still reach the commit-check logic.

        This test verifies the happy path is not broken by the fix.
        The hook will not find a valid conventional commit (the last commit is
        the bare 'init'), so it exits 0 anyway — what matters is it does NOT
        crash.
        """
        repo = _make_repo(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m test"},
            "tool_output": {"exit_code": 0},
        }

        rc, stdout, stderr = _run_hook(repo, payload)

        assert rc == 0, (
            f"Happy-path (exit_code=0) must not crash. Got rc={rc}. "
            f"stderr={stderr!r}"
        )

    def test_exit_code_string_zero_still_continues(self, tmp_path):
        """CONTROL: exit_code="0" (numeric string) must also work after the fix."""
        repo = _make_repo(tmp_path)
        payload = {
            "tool_name": "Bash",
            "tool_input": {"command": "git commit -m test"},
            "tool_output": {"exit_code": "0"},
        }

        rc, stdout, stderr = _run_hook(repo, payload)

        assert rc == 0, (
            f"exit_code='0' (string digit) must not crash. Got rc={rc}. "
            f"stderr={stderr!r}"
        )
