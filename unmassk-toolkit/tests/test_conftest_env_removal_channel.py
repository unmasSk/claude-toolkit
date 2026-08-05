"""
tests/conftest.py's run_cmd()/claude_env() removal channel (roadmap FASE
2.2) — a `value is None` in the `env=` dict means REMOVE that variable from
the child, not "leave it unset"/"pass the string None".

Salvaged from tests/test_pre_validate_hook_actually_fires.py (2026-08-05):
that file's other two classes (TestFiresUnderTheRealEnvironment,
TestDeadMarkerNamesDoNotTrigger) ran hooks/pre-validate-commit-trailers.py
via subprocess — that hook was deleted outright with the rest of the v1
memory system, and every one of those tests either failed outright or
passed VACUOUSLY (the missing-script FileNotFoundError coincidentally
produces the same rc the "hook blocks" assertions expected — confirmed live
before this retirement: 2 of those "passing" tests were proven vacuous by
temporarily pointing HOOK_PATH at a real, always-succeeding no-op script,
which flipped them red for the wrong reason). This class never touched that
hook at all — it tests conftest.py's own run_cmd()/claude_env() plumbing
directly (via a throwaway probe script this test writes itself), which is
shared, live infrastructure used by the whole suite. Moved verbatim into
this dedicated, honestly-named file instead of dying with its old home.

Build mode: n/a (salvage move, linear). No production code is touched by
this file.
"""

import os
import sys

from conftest import CLAUDE_ENV_VAR, claude_env, git_cmd, run_cmd


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


class TestSuiteDoesNotInheritTheMarkerFromTheShell(object):
    """The fixture channel itself, not any hook (roadmap FASE 2.2).

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
