"""
The PLUGIN: repo-vs-cache sync line, now printed by
hooks/session-start-crew.py::_print_plugin_sync_check() (P7).

Reapuntado (memoria v2, 2026-08-05): this coverage originally lived in
tests/test_plugin_sync_boot_line.py against lib/boot_render.py::
_render_plugin_sync_line() + hooks/session-start-boot.py's wiring of it —
both retired outright with the rest of the v1 memory system. The BEHAVIOR
this line protects did not go away: it moved to
hooks/session-start-crew.py::_print_plugin_sync_check(), confirmed live by
reading that function. Inside the toolkit's own repo it prints exactly one
of four outcome shapes:
  "no verificable (<ExceptionType>)",
  "no verificable (no hay plugin instalado distinto del repo)",
  "sincronizado (0 ficheros)", or
  "N ficheros desincronizados ... -> publica version y actualiza desde
  /plugin > marketplace".
Outside the toolkit repo (no unmassk-toolkit/ source tree) it prints no
line at all (#104.2, pinned in
test_crew_plugin_sync_line_absent_without_source.py).

Unlike the old boot_render._render_plugin_sync_line(), the crew hook's
version has no pure-function return value to call directly and assert on
— it only ever prints (same convention every other check in
session-start-crew.py already follows, see test_session_start_crew.py).
So this file is end-to-end only: real subprocess runs of the real hook
against a real git repo, real files standing in for the repo/cache trees on
both sides of the comparison (unmassk-standards §34 — no fabricated
producer/consumer values).

Principle protected (P6, per this project's spec): inside the toolkit repo
the sync state is never silent. A real drift count, an explicit zero, or
an explicit "not verifiable" — never nothing. TestZeroDriftIsExplicitNeverSilent below is
the one the owner most wants kept green: an in-sync repo must still print a
visible "sincronizado (0 ficheros)" line, not omit the PLUGIN: line
entirely.

Build mode: n/a (redirect pass, linear). No production code is touched by
this file.
"""

import os
import pathlib
import sys

import pytest

from conftest import HOOKS_DIR, LIB_DIR, git_cmd, run_script

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import cache_sync_check  # noqa: E402


def _make_repo(tmp_path, name="probe-repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _home_env(home_path):
    # os.path.expanduser("~") on Windows ignores HOME and resolves via
    # USERPROFILE/HOMEDRIVE+HOMEPATH -- redirect all of them so
    # boot_health.CACHE_BASE_DIR points at the fixture home on every
    # platform (same fix the retired test_plugin_sync_boot_line.py used).
    return {"HOME": str(home_path), "USERPROFILE": str(home_path),
            "HOMEDRIVE": "", "HOMEPATH": str(home_path)}


def _plant_toolkit_tree(base_path, files):
    """files: dict of "subdir/name.py" -> content, plus guarantees hooks/
    lib/ bin/ all exist even when empty (matches a real plugin layout)."""
    for subdir in ("hooks", "lib", "bin"):
        (base_path / subdir).mkdir(parents=True, exist_ok=True)
    for rel, content in files.items():
        path = base_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


class TestRealDriftReachesTheOutput:
    def test_real_drift_count_reaches_stdout(self, tmp_path):
        repo = _make_repo(tmp_path)
        home = tmp_path / "fake-home"

        repo_toolkit_dir = pathlib.Path(repo) / cache_sync_check.PLUGIN_DIR_NAME
        _plant_toolkit_tree(repo_toolkit_dir, {"lib/mod.py": "x = 1\n"})
        cache_plugin = (home / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"
                         / cache_sync_check.PLUGIN_DIR_NAME / "1.0.0")
        _plant_toolkit_tree(cache_plugin, {"lib/mod.py": "x = 2\n"})

        rc, stdout, stderr = run_script(CREW_HOOK, repo, env=_home_env(home))
        assert rc == 0, f"session-start-crew.py must exit 0. stderr={stderr!r}"

        assert (
            "[crew] PLUGIN: 1 ficheros desincronizados (repo vs cache) "
            "-> publica version y actualiza desde /plugin > marketplace"
        ) in stdout, stdout


class TestZeroDriftIsExplicitNeverSilent:
    """P6: an in-sync repo must still print a visible zero, never omit the
    PLUGIN: line -- this is the specific case the owner wants protected."""

    def test_in_sync_reports_the_explicit_zero(self, tmp_path):
        repo = _make_repo(tmp_path)
        home = tmp_path / "fake-home"

        repo_toolkit_dir = pathlib.Path(repo) / cache_sync_check.PLUGIN_DIR_NAME
        files = {"lib/mod.py": "x = 1\n"}
        _plant_toolkit_tree(repo_toolkit_dir, files)
        cache_plugin = (home / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"
                         / cache_sync_check.PLUGIN_DIR_NAME / "1.0.0")
        _plant_toolkit_tree(cache_plugin, dict(files))

        rc, stdout, stderr = run_script(CREW_HOOK, repo, env=_home_env(home))
        assert rc == 0, f"session-start-crew.py must exit 0. stderr={stderr!r}"

        assert "[crew] PLUGIN: sincronizado (0 ficheros)" in stdout, stdout


# TestOrdinaryProjectIsNotVerifiable lived here: it pinned
# "[crew] PLUGIN: no verificable (sin repo fuente junto a la cache)" for a
# project without the toolkit's source (and read the real machine's HOME).
# Issue #104.2 reversed that contract -- that case now prints NO plugin line.
# The new contract, with a throwaway HOME, is in
# test_crew_plugin_sync_line_absent_without_source.py.



class TestToolkitRepoWithoutInstalledPluginIsExplicitNeverSilent:
    """Cerberus #104.2 F1: inside the toolkit repo, with NO installed plugin
    cache (a fresh machine before installing), the line must still print --
    an explicit "not verifiable", never silence. Catches a refactor that
    reuses the `summary is None` branch to stay quiet."""

    # Written here, not imported from production (owner's wording, #104.2).
    EXPECTED = ("[crew] PLUGIN: no verificable "
                "(no hay plugin instalado distinto del repo)")

    def test_should_print_one_not_verifiable_line_when_source_present_and_no_cache(
        self, tmp_path
    ):
        repo = _make_repo(tmp_path)
        home = tmp_path / "empty-home"
        home.mkdir()
        _plant_toolkit_tree(
            pathlib.Path(repo) / "unmassk-toolkit", {"lib/mod.py": "x = 1\n"}
        )

        rc, stdout, stderr = run_script(CREW_HOOK, repo, env=_home_env(home))

        assert rc == 0, f"session-start-crew.py must exit 0. stderr={stderr!r}"
        plugin_lines = [
            line for line in (stdout + stderr).splitlines()
            if "[crew] PLUGIN:" in line
        ]
        assert plugin_lines == [self.EXPECTED], stdout + stderr


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
