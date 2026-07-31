"""
`git log` handling in pre-validate-commit-trailers.py.

Two separate things live here, and they must not be confused:

1. **The exemption is real and deliberate.** `git log` is NOT blocked
   today, even for Claude. `BLOCK_DIRECT_GIT_LOG = False` in the hook, and
   the reason is written at that constant: the mandatory alternative
   `bin/git-memory-log.py` ignores `count` when `--all` is passed and
   silently caps at 100 commits, and `agents/gitto.md:239` tells agents to
   use `git log` directly. `TestGitLogIsExemptToday` pins that exemption so
   nobody flips the constant back by accident before the cap is fixed —
   and, just as important, so the exemption stays a written decision
   instead of drifting into folklore.

2. **The regex must stay correct for the day the exemption ends.** BUG C:
   the original pattern `\\bgit\\b.*\\blog\\b` matched any command
   containing the words "git" and "log" anywhere — `cat git.log`,
   `echo 'git log info'`, `git log-remote origin` were all falsely
   blocked. Blocking a legitimate command the user typed is the system
   breaking itself, so that regression stays covered. Because the blocking
   branch is switched off by default, those tests would be vacuous run
   against the shipped constant (every command "passes" when nothing is
   ever blocked). They therefore run the hook with `BLOCK_DIRECT_GIT_LOG`
   forced to True — see `_run_hook_with_log_block_forced_on` — so they
   exercise the regex for real and would go red if the pattern regressed.

Environment note (roadmap FASE 2.2): the marker variable is set/removed
explicitly via conftest.claude_env(), never inherited from the shell that
launched pytest. This file used to fabricate `CLAUDE_CODE=1` — a variable
production never emits — which is precisely why the whole hook could sit
dead for four months under a green suite.
"""

import json
import os
import sys

from conftest import HOOKS_DIR, claude_env, git_cmd, run_script, run_cmd

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


def _payload(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _run_hook(repo, command, as_claude=True):
    """Invoke the hook exactly as shipped (BLOCK_DIRECT_GIT_LOG untouched).

    Returns (returncode, stdout, stderr).
    """
    return run_script(
        HOOK_PATH, repo, env=claude_env(as_claude), input_text=_payload(command)
    )


# Driver that loads the hook as a module, flips the log-blocking switch ON,
# and runs main() — so the regex under test is the real one in the shipped
# file, only the feature flag differs. exec_module() runs module-level code
# only (main() is guarded by __name__ == "__main__"), and the hook reads its
# payload from stdin, which the guard never touches.
_FORCE_LOG_BLOCK_DRIVER = '''
import importlib.util
import sys

spec = importlib.util.spec_from_file_location("prehook_under_test", sys.argv[1])
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
assert mod.BLOCK_DIRECT_GIT_LOG is False, (
    "driver expected the shipped default to be False; if the constant is "
    "already True, TestGitLogIsExemptToday is the test that should be "
    "failing, not this one"
)
mod.BLOCK_DIRECT_GIT_LOG = True
try:
    mod.main()
except SystemExit as exc:
    sys.exit(exc.code if exc.code is not None else 0)
'''


def _run_hook_with_log_block_forced_on(tmp_path, repo, command):
    """Run the real hook with BLOCK_DIRECT_GIT_LOG forced to True.

    Keeps the BUG C regex regression tests honest while the feature flag is
    off: without this, every one of them would pass simply because nothing
    is ever blocked.
    """
    driver = tmp_path / "_force_log_block_driver.py"
    driver.write_text(_FORCE_LOG_BLOCK_DRIVER, encoding="utf-8")
    return run_cmd(
        [sys.executable, str(driver), HOOK_PATH],
        repo,
        env=claude_env(True),
        input_text=_payload(command),
    )


# ── The exemption, as shipped ─────────────────────────────────────────────

class TestGitLogIsExemptToday:
    """`git log` passes through, on purpose, even for Claude.

    If someone flips BLOCK_DIRECT_GIT_LOG back to True without fixing
    git-memory-log.py's 100-commit `--all` cap first, these go red and say
    why.
    """

    def test_git_log_oneline_is_not_blocked(self, tmp_path):
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook(repo, "git log --oneline")

        assert rc == 0, (
            "`git log --oneline` must pass through: the exemption is "
            "deliberate (BLOCK_DIRECT_GIT_LOG = False) because "
            "bin/git-memory-log.py silently caps at 100 commits with --all "
            "and agents/gitto.md:239 instructs agents to use git log "
            f"directly. Got rc={rc}, stderr={stderr!r}"
        )

    def test_bare_git_log_is_not_blocked(self, tmp_path):
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook(repo, "git log")

        assert rc == 0, (
            "bare `git log` must pass through — same deliberate exemption. "
            f"Got rc={rc}, stderr={stderr!r}"
        )

    def test_exemption_is_not_an_accident_of_a_dead_marker(self, tmp_path):
        """The exemption must hold because the flag is off, not because the
        hook failed to recognise the environment.

        Without this control the two tests above would pass just as well on
        a hook that no longer detects Claude at all — which is exactly the
        four-month failure this phase exists to kill. `git commit` in the
        SAME invocation environment must still be blocked.
        """
        repo = _make_repo(tmp_path)

        log_rc, _, _ = _run_hook(repo, "git log --oneline")
        commit_rc, _, commit_stderr = _run_hook(repo, 'git commit -m "x"')

        assert log_rc == 0, f"git log should be exempt, got rc={log_rc}"
        assert commit_rc == 2, (
            "`git commit` must be blocked in the same environment that let "
            "`git log` through — otherwise the exemption above proves "
            f"nothing about the hook being alive. Got rc={commit_rc}, "
            f"stderr={commit_stderr!r}"
        )


# ── BUG C: the regex must not block commands that merely mention git/log ──

class TestGitLogRegexHasNoFalsePositives:
    """Commands containing 'git' and 'log' as words but which are not
    `git log` invocations.

    Run with BLOCK_DIRECT_GIT_LOG forced ON — the regex is what is under
    test, not the feature flag.
    """

    def test_cat_git_log_file_not_blocked(self, tmp_path):
        """`cat git.log`: 'git' is a bare word, 'log' is part of a filename."""
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook_with_log_block_forced_on(
            tmp_path, repo, "cat git.log")

        assert rc == 0, (
            f"'cat git.log' must NOT be blocked (exit 0). Got rc={rc}. "
            f"stderr={stderr!r}"
        )

    def test_echo_git_log_not_blocked(self, tmp_path):
        """`echo 'git log info'` prints text, it does not call git."""
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook_with_log_block_forced_on(
            tmp_path, repo, "echo 'git log info'")

        assert rc == 0, (
            f"'echo git log info' must NOT be blocked (exit 0). Got rc={rc}. "
            f"stderr={stderr!r}"
        )

    def test_git_log_remote_subcommand_not_blocked(self, tmp_path):
        """`git log-remote origin` is a different subcommand."""
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook_with_log_block_forced_on(
            tmp_path, repo, "git log-remote origin")

        assert rc == 0, (
            f"'git log-remote origin' must NOT be blocked (exit 0). "
            f"Got rc={rc}. stderr={stderr!r}"
        )

    def test_real_git_log_is_blocked_when_the_flag_is_on(self, tmp_path):
        """Anti-vacuity control for the three tests above.

        With the flag forced on, a genuine `git log` MUST be blocked —
        otherwise the three exit-0 results prove only that the driver
        failed to turn the feature on.
        """
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook_with_log_block_forced_on(
            tmp_path, repo, "git log --oneline")

        assert rc == 2, (
            "with BLOCK_DIRECT_GIT_LOG forced True, a real `git log` must "
            f"be blocked (exit 2). Got rc={rc}, stderr={stderr!r}"
        )

    def test_git_log_never_blocked_for_a_human_even_with_the_flag_on(self, tmp_path):
        """No CLAUDECODE in the environment → the hook never blocks anything."""
        repo = _make_repo(tmp_path)

        driver = tmp_path / "_force_log_block_driver.py"
        driver.write_text(_FORCE_LOG_BLOCK_DRIVER, encoding="utf-8")
        rc, _, stderr = run_cmd(
            [sys.executable, str(driver), HOOK_PATH],
            repo,
            env=claude_env(False),
            input_text=_payload("git log --oneline"),
        )

        assert rc == 0, (
            "a human terminal (CLAUDECODE removed from the environment) "
            f"must never be blocked. Got rc={rc}, stderr={stderr!r}"
        )
