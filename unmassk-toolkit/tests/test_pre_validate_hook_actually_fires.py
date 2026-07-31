"""
Does this hook ever actually fire? (roadmap FASE 2.3)

`pre-validate-commit-trailers.py` was inert from v1.0.0 to 2026-07-29 — four
months — because it read `CLAUDE_CODE` while Claude Code exports
`CLAUDECODE`. Nothing caught it: seven test files stayed green because
`conftest.check_hook_msg()` fabricated the same wrong variable. Hook and
fixture agreed with each other and disagreed with the only thing that
matters, the real environment.

That is a silent failure of the worst kind — a gate that reports success by
never running — so this file tests the one thing none of the other seven
did: that the hook's trigger condition matches what production actually
emits, rather than what the test suite decided to hand it.

Two complementary angles, because neither alone is enough:

- `TestFiresUnderTheRealEnvironment` — no fabricated input at all. It runs
  the hook against this process's own inherited environment. When pytest is
  launched from inside Claude Code, that environment IS the producer, and
  the hook must block. It skips, loudly, when run anywhere else: the real
  producer is unreachable there and faking it would recreate the exact bug.
- `TestDeadMarkerNamesDoNotTrigger` — runs everywhere, including CI. It
  pins the negative half: the retired `CLAUDE_CODE` name must NOT gate the
  hook. If someone reintroduces it (or reverts to it), this goes red on
  every machine.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import CLAUDE_ENV_VAR, HOOKS_DIR, claude_env, git_cmd, run_cmd

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-validate-commit-trailers.py")

# The name the hook used to read, and which production never sets. Kept
# here only so a test can prove it is inert.
RETIRED_MARKER = "CLAUDE_CODE"

DIRECT_COMMIT = 'git commit -m "probe"'


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _payload(command):
    return json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})


def _run_hook_raw(repo, command, env):
    """Run the hook with a fully explicit environment (no run_cmd merge).

    conftest.run_cmd() inherits os.environ and layers defaults on top, which
    is right for the rest of the suite but wrong here: these tests are about
    exactly which variables are present, so the environment is built
    literally and passed to subprocess as-is.
    """
    result = subprocess.run(
        [sys.executable, HOOK_PATH],
        input=_payload(command), capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=repo, timeout=15, env=env,
    )
    return result.returncode, result.stdout, result.stderr


class TestFiresUnderTheRealEnvironment:
    """The producer is the shell that launched pytest — nothing is faked."""

    def test_direct_git_commit_is_blocked_by_the_real_environment(self, tmp_path):
        if CLAUDE_ENV_VAR not in os.environ:
            pytest.skip(
                f"{CLAUDE_ENV_VAR} is absent from this process's environment, "
                "so the real producer is not reachable here — reported as "
                "not verified rather than substituted with a fabricated "
                "variable, which is the failure mode this file exists for. "
                "Run the suite from inside Claude Code to exercise it."
            )
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook_raw(repo, DIRECT_COMMIT, dict(os.environ))

        assert rc == 2, (
            "the hook did not fire under the REAL environment of the process "
            f"running these tests ({CLAUDE_ENV_VAR}="
            f"{os.environ[CLAUDE_ENV_VAR]!r} is present). A gate that never "
            "triggers in production while its own tests are green is exactly "
            f"the four-month dead hook this test exists to detect. rc={rc}, "
            f"stderr={stderr!r}"
        )

    def test_wrapper_invocation_still_passes_under_the_real_environment(self, tmp_path):
        """Same real environment, but the command already uses the wrapper —
        it must pass. Proves the block above is a decision about the command,
        not the hook rejecting everything."""
        if CLAUDE_ENV_VAR not in os.environ:
            pytest.skip(f"{CLAUDE_ENV_VAR} absent — real producer unreachable here")
        repo = _make_repo(tmp_path)

        rc, _, stderr = _run_hook_raw(
            repo,
            'python3 /x/bin/git-memory-commit.py fix scope "probe"',
            dict(os.environ),
        )

        assert rc == 0, (
            "a command already going through git-memory-commit.py must pass "
            f"through untouched. rc={rc}, stderr={stderr!r}"
        )


class TestDeadMarkerNamesDoNotTrigger:
    """Runs on every machine, CI included."""

    def test_retired_underscore_name_alone_does_not_gate_the_hook(self, tmp_path):
        """`CLAUDE_CODE=1` with no `CLAUDECODE` must NOT block.

        This is the fabricated environment the suite used to build for
        itself. If it ever blocks again, the hook has been reverted to
        reading a variable production does not emit.
        """
        repo = _make_repo(tmp_path)
        env = {k: v for k, v in os.environ.items() if k != CLAUDE_ENV_VAR}
        env[RETIRED_MARKER] = "1"

        rc, _, stderr = _run_hook_raw(repo, DIRECT_COMMIT, env)

        assert rc == 0, (
            f"{RETIRED_MARKER}=1 (the retired, never-emitted name) must not "
            "gate this hook — only the live "
            f"{CLAUDE_ENV_VAR} marker may. rc={rc}, stderr={stderr!r}"
        )

    def test_live_name_alone_does_gate_the_hook(self, tmp_path):
        """Anti-vacuity twin of the test above: the same repo, the same
        command, the ONLY difference being which variable name is set."""
        repo = _make_repo(tmp_path)
        env = {k: v for k, v in os.environ.items() if k != RETIRED_MARKER}
        env[CLAUDE_ENV_VAR] = "1"

        rc, _, stderr = _run_hook_raw(repo, DIRECT_COMMIT, env)

        assert rc == 2, (
            f"{CLAUDE_ENV_VAR}=1 must block a direct `git commit`. Without "
            "this the previous test would pass on a hook that blocks "
            f"nothing at all. rc={rc}, stderr={stderr!r}"
        )

    def test_neither_name_set_never_blocks(self, tmp_path):
        """A human terminal. Explicit removal, not inheritance."""
        repo = _make_repo(tmp_path)

        rc, _, stderr = run_cmd(
            [sys.executable, HOOK_PATH], repo,
            env={CLAUDE_ENV_VAR: None, RETIRED_MARKER: None},
            input_text=_payload(DIRECT_COMMIT),
        )

        assert rc == 0, (
            "with no Claude marker in the environment the hook must never "
            f"block. rc={rc}, stderr={stderr!r}"
        )

    def test_empty_string_marker_counts_as_absent(self, tmp_path):
        """`CLAUDECODE=""` is not Claude.

        The hook uses `bool(os.environ.get(...))`, so an exported-but-empty
        variable must read as absent. Pinned because the removal channel in
        conftest.run_cmd() and any future `env -u`-style plumbing both
        depend on empty-vs-missing being treated the same way.
        """
        repo = _make_repo(tmp_path)
        env = {k: v for k, v in os.environ.items() if k != RETIRED_MARKER}
        env[CLAUDE_ENV_VAR] = ""

        rc, _, stderr = _run_hook_raw(repo, DIRECT_COMMIT, env)

        assert rc == 0, (
            f'{CLAUDE_ENV_VAR}="" must be treated as absent. rc={rc}, '
            f"stderr={stderr!r}"
        )


class TestSuiteDoesNotInheritTheMarkerFromTheShell(object):
    """The fixture channel itself, not the hook (roadmap FASE 2.2).

    `conftest.run_cmd()` inherits the whole ambient environment. If a test
    that means "run as a human" simply omits the variable, its result
    depends on where the suite is run — measured: 5 failures inside Claude
    Code vs 4 under a clean shell, and neither was the answer. These two
    tests pin the removal channel that makes the suite give one answer
    everywhere.
    """

    def test_none_value_removes_an_inherited_variable(self, tmp_path):
        repo = _make_repo(tmp_path)
        probe = tmp_path / "probe.py"
        probe.write_text(
            "import os, sys\n"
            "sys.stdout.write(repr(os.environ.get('DANTE_PROBE_VAR')))\n",
            encoding="utf-8",
        )
        os.environ["DANTE_PROBE_VAR"] = "inherited"
        try:
            _, present, _ = run_cmd([sys.executable, str(probe)], repo)
            _, removed, _ = run_cmd(
                [sys.executable, str(probe)], repo, env={"DANTE_PROBE_VAR": None})
        finally:
            os.environ.pop("DANTE_PROBE_VAR", None)

        assert present == "'inherited'", (
            "control: run_cmd is expected to inherit ambient variables — if "
            f"it no longer does, this test's premise is stale. Got {present!r}"
        )
        assert removed == "None", (
            "env={'VAR': None} must REMOVE the variable from the child, not "
            f"pass the string 'None'. Got {removed!r}"
        )

    def test_claude_env_false_removes_the_marker(self, tmp_path):
        repo = _make_repo(tmp_path)
        probe = tmp_path / "probe.py"
        probe.write_text(
            "import os, sys\n"
            f"sys.stdout.write(repr(os.environ.get({CLAUDE_ENV_VAR!r})))\n",
            encoding="utf-8",
        )

        _, as_human, _ = run_cmd(
            [sys.executable, str(probe)], repo, env=claude_env(False))
        _, as_claude, _ = run_cmd(
            [sys.executable, str(probe)], repo, env=claude_env(True))

        assert as_human == "None", (
            f"claude_env(False) must remove {CLAUDE_ENV_VAR} even when the "
            "shell that launched pytest exports it — otherwise every "
            '"runs as a human" test in the suite means something different '
            f"on the owner's machine than on CI. Got {as_human!r}"
        )
        assert as_claude == "'1'", (
            f"claude_env(True) must set {CLAUDE_ENV_VAR}=1. Got {as_claude!r}"
        )
