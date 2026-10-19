"""
Issue #104 point 2 -- the PLUGIN: sync line is silent where it cannot apply.

hooks/session-start-crew.py::_print_plugin_sync_check() compares the
toolkit's source tree (<project>/unmassk-toolkit/) against the installed
plugin cache. That comparison only means something inside the toolkit's
own repository. In every other project of the owner -- or on a machine
without the toolkit's source -- it used to print

    [crew] PLUGIN: no verificable (sin repo fuente junto a la cache)

on every session start: a line about nothing, in a project where nothing
can be done about it. The owner's contract (#104.2): there, print NO
plugin-sync line at all.

What stays as it was (pinned by test_crew_plugin_sync_line.py, which must
stay green): with the source tree present, the real drift count and the
explicit "sincronizado (0 ficheros)" still print. The silence below is
for the absent source only, never for an in-sync repo.

Every run goes through the real hook, as Claude Code runs it at session
start, with a throwaway HOME (so the real machine's plugin cache is never
read) and a disposable git repo. The anti-vacuity guard in each test: the
hook's last check (REPO:) still prints, so "no PLUGIN line" cannot be
satisfied by a hook that crashed before reaching its checks.

Build mode: test-first (Short). No production code is touched by this file.
"""

import os
import pathlib
import sys

import pytest

from conftest import HOOKS_DIR, git_cmd, run_script

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")

# Written here, not imported: the expected silence is about this prefix,
# whatever the production code calls it.
PLUGIN_LINE_PREFIX = "[crew] PLUGIN:"
REPO_LINE_PREFIX = "[crew] REPO:"


def _make_repo(tmp_path, name="ordinary-project"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _home_env(home_path):
    # expanduser("~") on Windows reads USERPROFILE/HOMEDRIVE+HOMEPATH, not
    # HOME -- redirect all of them so the hook never sees the real cache.
    return {"HOME": str(home_path), "USERPROFILE": str(home_path),
            "HOMEDRIVE": "", "HOMEPATH": str(home_path)}


def _plant_installed_cache(home_path, version="1.0.0"):
    """A real installed plugin cache under the throwaway HOME, with real
    files -- what any machine that installed the toolkit has."""
    cache_plugin = (home_path / ".claude" / "plugins" / "cache"
                    / "unmassk-claude-toolkit" / "unmassk-toolkit" / version)
    for subdir in ("hooks", "lib", "bin"):
        (cache_plugin / subdir).mkdir(parents=True, exist_ok=True)
    (cache_plugin / "lib" / "mod.py").write_text("x = 1\n", encoding="utf-8")
    return cache_plugin


def _plugin_lines(text):
    return [line for line in text.splitlines() if PLUGIN_LINE_PREFIX in line]


class TestOrdinaryProjectPrintsNoPluginLine:
    def test_should_print_no_plugin_line_when_project_has_no_toolkit_source_and_cache_is_installed(
        self, tmp_path
    ):
        """The everyday case: any project of the owner other than the
        toolkit itself, on his machine, where the plugin IS installed."""
        repo = _make_repo(tmp_path)
        home = tmp_path / "fake-home"
        _plant_installed_cache(home)
        assert not (pathlib.Path(repo) / "unmassk-toolkit").exists()

        rc, stdout, stderr = run_script(CREW_HOOK, repo, env=_home_env(home))

        assert rc == 0, f"session-start-crew.py must exit 0. stderr={stderr!r}"
        assert REPO_LINE_PREFIX in stdout, (
            f"anti-vacuity: the hook must reach its checks. stdout={stdout!r}"
        )
        assert _plugin_lines(stdout + stderr) == [], (
            "no plugin-sync line may print in a project without the toolkit's "
            f"source. stdout={stdout!r} stderr={stderr!r}"
        )

    def test_should_print_no_plugin_line_when_machine_has_no_cache_and_no_toolkit_source(
        self, tmp_path
    ):
        """A machine without the toolkit's source and without any installed
        cache under HOME: nothing to compare on either side."""
        repo = _make_repo(tmp_path)
        home = tmp_path / "empty-home"
        home.mkdir()

        rc, stdout, stderr = run_script(CREW_HOOK, repo, env=_home_env(home))

        assert rc == 0, f"session-start-crew.py must exit 0. stderr={stderr!r}"
        assert REPO_LINE_PREFIX in stdout, (
            f"anti-vacuity: the hook must reach its checks. stdout={stdout!r}"
        )
        assert _plugin_lines(stdout + stderr) == [], (
            "no plugin-sync line may print without the toolkit's source. "
            f"stdout={stdout!r} stderr={stderr!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
