"""
Regression tests for pre-validate-commit-trailers.py — Bug C.

BUG C (~line 150): the pattern `re.search(r"\\bgit\\b.*\\blog\\b", command)`
matches on any command where the word "git" and the word "log" appear anywhere,
including as substrings or filenames. Examples that are falsely blocked:

    - "cat git.log"        — "git" is a bare word, "log" is part of filename
    - "echo git log info"  — literal words but inside an echo, not a git call
    - "git log-remote"     — "git" + "log" as prefix of a different subcommand

When CLAUDE_CODE=1 the hook exits 2 ("use the wrapper"), which is WRONG for
these legitimate commands.

Expected behaviour after fix:
    "cat git.log"                   → NOT blocked (exit 0)
    "echo 'git log info'"           → NOT blocked (exit 0)
    "git log-remote origin"         → NOT blocked (exit 0)
    "git log --oneline" (real call) → STILL blocked (exit 2) — no regression

RED contract (these tests MUST fail before the fix, i.e. exit 2 instead of 0):
    - test_cat_git_log_file_not_blocked
    - test_echo_git_log_not_blocked
    - test_git_log_remote_subcommand_not_blocked

GREEN controls (must pass before AND after fix):
    - test_git_log_oneline_is_still_blocked
    - test_git_log_no_args_is_still_blocked
"""

import json
import os
import sys

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script, run_cmd

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-validate-commit-trailers.py")


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


def _run_hook(repo, command, as_claude=True):
    """Invoke pre-validate-commit-trailers.py with a Bash tool_input payload.

    as_claude=True sets CLAUDE_CODE=1, which activates the git-log blocking path.
    Returns (returncode, stdout, stderr).
    """
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    env = {"CLAUDE_CODE": "1"} if as_claude else {}
    rc, stdout, stderr = run_script(HOOK_PATH, repo, env=env, input_text=payload)
    return rc, stdout, stderr


# ── Bug C regression tests — false positives that must NOT be blocked ─────

class TestGitLogFalsePositives:
    """Commands that contain 'git' and 'log' as words but are not `git log` invocations.

    Before the fix: exit 2 (falsely blocked).
    After the fix: exit 0 (not blocked).
    """

    def test_cat_git_log_file_not_blocked(self, tmp_path):
        """'cat git.log' must not be blocked — 'git' is a word but 'log' is in a filename.

        BUG: \\bgit\\b.*\\blog\\b matches 'git' (bare word) and 'log' in 'git.log'.
        EXPECTED after fix: exit 0, command passes through.
        """
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo, "cat git.log")

        assert rc == 0, (
            f"'cat git.log' must NOT be blocked (exit 0). "
            f"Got rc={rc}. stderr={stderr!r}"
        )

    def test_echo_git_log_not_blocked(self, tmp_path):
        """'echo git log info' must not be blocked — it is printing text, not calling git.

        BUG: pattern matches the words 'git' and 'log' anywhere in the command string.
        EXPECTED after fix: exit 0.
        """
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo, "echo 'git log info'")

        assert rc == 0, (
            f"'echo git log info' must NOT be blocked (exit 0). "
            f"Got rc={rc}. stderr={stderr!r}"
        )

    def test_git_log_remote_subcommand_not_blocked(self, tmp_path):
        """'git log-remote origin' must not be blocked — log-remote is a different subcommand.

        BUG: \\blog\\b matches the 'log' prefix of 'log-remote' as a word boundary.
        EXPECTED after fix: exit 0 (only bare 'git log ...' should be blocked).
        """
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo, "git log-remote origin")

        assert rc == 0, (
            f"'git log-remote origin' must NOT be blocked (exit 0). "
            f"Got rc={rc}. stderr={stderr!r}"
        )


# ── Control tests — real git log invocations MUST still be blocked ────────

class TestGitLogRealInvocationsStillBlocked:
    """Real `git log` calls must still be blocked after the fix — no regression."""

    def test_git_log_oneline_is_still_blocked(self, tmp_path):
        """CONTROL: 'git log --oneline' must still be blocked (exit 2) with CLAUDE_CODE=1."""
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo, "git log --oneline")

        assert rc == 2, (
            f"'git log --oneline' must still be blocked (exit 2) after the fix. "
            f"Got rc={rc}."
        )

    def test_git_log_no_args_is_still_blocked(self, tmp_path):
        """CONTROL: bare 'git log' must still be blocked (exit 2) with CLAUDE_CODE=1."""
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo, "git log")

        assert rc == 2, (
            f"Bare 'git log' must still be blocked (exit 2) after the fix. "
            f"Got rc={rc}."
        )

    def test_git_log_not_blocked_without_claude_code(self, tmp_path):
        """CONTROL: without CLAUDE_CODE=1, git log is never blocked (human terminal)."""
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo, "git log --oneline", as_claude=False)

        assert rc == 0, (
            f"Without CLAUDE_CODE=1, git log must not be blocked. "
            f"Got rc={rc}."
        )
