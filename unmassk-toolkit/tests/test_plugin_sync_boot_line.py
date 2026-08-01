"""
Tests for the PLUGIN: repo-vs-cache sync line added to the boot STATUS
section (commit fbc2ac5).

New surface under test:
  - lib/cache_sync_check.py:count_repo_cache_drift() — covered separately in
    tests/test_doctor_derived_expectations.py (TestCountRepoCacheDrift),
    alongside its sibling check_repo_cache_sync(). Not repeated here.
  - lib/boot_render.py:_render_plugin_sync_line() — renders that count into
    one of exactly three shapes: a real drift count, an explicit zero, or
    an explicit "not verifiable" (never silence, never "ok" over "unknown").
  - lib/boot_render.py:render_status_section(project_root=...) — the new
    parameter, always threaded into the PLUGIN: line.
  - hooks/session-start-boot.py:350 — the real wiring: main() resolves
    project_root and passes it to render_status_section(). Proven end to
    end via real subprocess runs, not by trusting the source read.

Threat model for this project (CLAUDE.md): the system against itself, not
an external attacker. Every case below is about the system not lying about
its own sync state (silent "ok" when it doesn't know, or a swallowed
exception with no visible trace) — nothing here simulates a malicious actor.
"""

import os
import pathlib
import sys

import pytest

from conftest import HOOKS_DIR, LIB_DIR, git_cmd, run_script

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")
BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import boot_render  # noqa: E402
import cache_sync_check  # noqa: E402


# ── Direct unit tests: boot_render._render_plugin_sync_line() ────────────
#
# Real filesystem (tmp_path) throughout — only cache_sync_check.CACHE_BASE_DIR
# is monkeypatched to point at the fixture, the same pattern already used by
# tests/test_doctor_derived_expectations.py's TestRepoCacheSyncDetectsDrift.

def _build_sync_line_fixture(tmp_path, monkeypatch, repo_files, cache_files, version="1.0.0"):
    project = tmp_path / "toolkit-repo"
    cache = tmp_path / "cache"
    repo_plugin = project / cache_sync_check.PLUGIN_DIR_NAME
    cache_plugin = cache / cache_sync_check.PLUGIN_DIR_NAME / version
    for base, files in ((repo_plugin, repo_files), (cache_plugin, cache_files)):
        for rel, text in files.items():
            path = base / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
    monkeypatch.setattr(cache_sync_check, "CACHE_BASE_DIR", str(cache))
    return str(project)


class TestRenderPluginSyncLineThreeOutcomes:
    """The three cases the design demands — a real count, an explicit
    zero, or an explicit "not verifiable". Silence is never one of them."""

    def test_no_project_root_is_not_verifiable(self):
        line = boot_render._render_plugin_sync_line(None)
        assert line == "PLUGIN: no verificable (project root no disponible)"

    def test_empty_string_project_root_is_also_not_verifiable(self):
        """Edge case: falsy-but-not-None. `if not project_root` must catch
        this the same way it catches None — an empty string is not a real
        root either."""
        line = boot_render._render_plugin_sync_line("")
        assert line == "PLUGIN: no verificable (project root no disponible)"

    def test_ordinary_project_without_toolkit_source_is_not_verifiable(self, tmp_path):
        """Submotive 2: the normal case for any project that is not the
        toolkit repo itself — no unmassk-toolkit/ tree to compare against."""
        project = tmp_path / "some-other-project"
        (project / "src").mkdir(parents=True)

        line = boot_render._render_plugin_sync_line(str(project))

        assert line == "PLUGIN: no verificable (sin repo fuente junto a la cache)"

    def test_real_drift_is_rendered_with_the_actual_count(self, tmp_path, monkeypatch):
        project = _build_sync_line_fixture(
            tmp_path, monkeypatch,
            {"lib/a.py": "new\n", "lib/b.py": "new\n"},
            {"lib/a.py": "old\n", "lib/b.py": "old\n"},
        )

        line = boot_render._render_plugin_sync_line(project)

        assert line == (
            "PLUGIN: 2 ficheros desincronizados (repo vs cache) "
            "-> publica version y ejecuta 'claude plugin update'"
        ), line

    def test_zero_drift_is_rendered_as_an_explicit_zero_not_silence(self, tmp_path, monkeypatch):
        """The design's stated requirement: a visible zero, never nothing."""
        files = {"lib/a.py": "same\n", "hooks/h.py": "same\n"}
        project = _build_sync_line_fixture(tmp_path, monkeypatch, files, dict(files))

        line = boot_render._render_plugin_sync_line(project)

        assert line == "PLUGIN: sincronizado (0 ficheros)"

    def test_comparator_exception_is_fail_open_and_names_the_reason(
        self, tmp_path, monkeypatch
    ):
        """Submotive 3: the comparator itself blows up (corrupted state,
        future bug, anything unforeseen). This must never crash the caller,
        and the swallowed exception must never be silent -- its type name
        is the visible rastro (trace) the design demands."""
        def _boom(_project_root):
            raise RuntimeError("simulated comparator failure")
        monkeypatch.setattr(cache_sync_check, "count_repo_cache_drift", _boom)

        line = boot_render._render_plugin_sync_line(str(tmp_path))

        assert line == "PLUGIN: no verificable (RuntimeError)", line


# ── render_status_section(project_root=...) wiring ────────────────────────

class TestRenderStatusSectionThreadsProjectRoot:
    """render_status_section() is a real function on the boot critical path
    (calls the real doctor via subprocess) -- called directly here, not
    mocked, so this is the real function, just not routed through the full
    session-start-boot.py process (that's the end-to-end class below)."""

    def test_default_project_root_is_none_and_renders_not_verifiable(self):
        """Old callers on this exact signature (e.g. the existing banner-
        probe helper in tests/test_boot_output.py, which still calls
        boot.render_status_section() with zero args) must keep getting a
        line, not a crash or a missing PLUGIN: entry."""
        lines, _status, _detail = boot_render.render_status_section()

        plugin_lines = [line for line in lines if line.startswith("PLUGIN:")]
        assert plugin_lines == ["PLUGIN: no verificable (project root no disponible)"]

    def test_explicit_project_root_reaches_the_plugin_line(self, tmp_path):
        """A real project_root, with no toolkit source tree, flows all the
        way through render_status_section() into the PLUGIN: line -- proving
        the parameter is threaded, not just defaulted."""
        project = tmp_path / "some-other-project"
        (project / "src").mkdir(parents=True)

        lines, _status, _detail = boot_render.render_status_section(str(project))

        plugin_lines = [line for line in lines if line.startswith("PLUGIN:")]
        assert plugin_lines == ["PLUGIN: no verificable (sin repo fuente junto a la cache)"]

    def test_plugin_line_is_present_exactly_once_and_always_appended(self, tmp_path, monkeypatch):
        """The PLUGIN: line must render unconditionally -- not folded away
        by, or hidden behind, any other STATUS content (version warning,
        skill drift warnings)."""
        project = _build_sync_line_fixture(
            tmp_path, monkeypatch, {"lib/a.py": "new\n"}, {"lib/a.py": "old\n"})

        lines, _status, _detail = boot_render.render_status_section(project)

        plugin_lines = [line for line in lines if line.startswith("PLUGIN:")]
        assert len(plugin_lines) == 1, lines
        assert plugin_lines[0] == (
            "PLUGIN: 1 ficheros desincronizados (repo vs cache) "
            "-> publica version y ejecuta 'claude plugin update'"
        )

    def test_boot_survives_a_comparator_exception_and_the_reason_stays_visible(
        self, tmp_path, monkeypatch
    ):
        """The fail-open requirement proven at the level that matters: the
        real boot-path function (render_status_section(), not just the
        private helper) must return normally -- never propagate -- and the
        STATUS lines it returns must still name what went wrong."""
        def _boom(_project_root):
            raise ValueError("simulated: disk fell over mid-comparison")
        monkeypatch.setattr(cache_sync_check, "count_repo_cache_drift", _boom)

        # No exception must escape this call -- that IS "boot survives".
        lines, status, _detail = boot_render.render_status_section(str(tmp_path))

        assert status in ("ok", "warn", "error"), (
            "render_status_section() must still return a real status, not blow up"
        )
        plugin_lines = [line for line in lines if line.startswith("PLUGIN:")]
        assert plugin_lines == ["PLUGIN: no verificable (ValueError)"], (
            "the swallowed exception must still be named in the STATUS output"
        )


# ── End-to-end: hooks/session-start-boot.py:350's real wiring ─────────────
#
# Real subprocess runs of the actual hook, real git repos, real files on
# disk for both "repo" and "cache" sides. HOME is redirected (same pattern
# as tests/test_skill_drift_repo_source_detection.py) so
# lib/boot_health.py's CACHE_BASE_DIR resolves into the fixture instead of
# the real developer machine's plugin cache.

def _make_repo(tmp_path, name="probe-repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _boot_log_path(repo):
    return os.path.join(repo, *BOOT_LOG_REL_PARTS)


def _read_boot_log(repo):
    with open(_boot_log_path(repo), encoding="utf-8") as f:
        return f.read()


def _home_env(home_path):
    # os.path.expanduser("~") on Windows ignores HOME and resolves via
    # USERPROFILE/HOMEDRIVE+HOMEPATH -- redirect all of them so
    # CACHE_BASE_DIR points at the fixture home on every platform (same fix
    # as tests/test_skill_drift_repo_source_detection.py).
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


class TestEndToEndBootWiring:
    """Proves hooks/session-start-boot.py:350 really passes the resolved
    project_root into render_status_section() in a real process -- not just
    that the pure function can do it in isolation (already proven above)."""

    def test_real_drift_count_reaches_the_boot_log(self, tmp_path):
        repo = _make_repo(tmp_path)
        home = tmp_path / "fake-home"

        repo_toolkit_dir = pathlib.Path(repo) / cache_sync_check.PLUGIN_DIR_NAME
        _plant_toolkit_tree(repo_toolkit_dir, {"lib/mod.py": "x = 1\n"})
        cache_plugin = (home / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"
                         / cache_sync_check.PLUGIN_DIR_NAME / "1.0.0")
        _plant_toolkit_tree(cache_plugin, {"lib/mod.py": "x = 2\n"})

        rc, _stdout, stderr = run_script(BOOT_HOOK, repo, env=_home_env(home))
        assert rc == 0, f"boot hook must always exit 0. stderr={stderr!r}"

        content = _read_boot_log(repo)
        assert (
            "PLUGIN: 1 ficheros desincronizados (repo vs cache) "
            "-> publica version y ejecuta 'claude plugin update'"
        ) in content, content

    def test_in_sync_reports_the_explicit_zero(self, tmp_path):
        repo = _make_repo(tmp_path)
        home = tmp_path / "fake-home"

        repo_toolkit_dir = pathlib.Path(repo) / cache_sync_check.PLUGIN_DIR_NAME
        files = {"lib/mod.py": "x = 1\n"}
        _plant_toolkit_tree(repo_toolkit_dir, files)
        cache_plugin = (home / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"
                         / cache_sync_check.PLUGIN_DIR_NAME / "1.0.0")
        _plant_toolkit_tree(cache_plugin, dict(files))

        rc, _stdout, stderr = run_script(BOOT_HOOK, repo, env=_home_env(home))
        assert rc == 0, f"boot hook must always exit 0. stderr={stderr!r}"

        content = _read_boot_log(repo)
        assert "PLUGIN: sincronizado (0 ficheros)" in content, content

    def test_ordinary_project_without_toolkit_source_is_not_verifiable(self, tmp_path):
        """The most common real case: any project that is not the toolkit
        repo itself. No unmassk-toolkit/ tree, no HOME override needed --
        this is what the vast majority of boots against this hook look
        like, and it must never claim "sincronizado"."""
        repo = _make_repo(tmp_path)

        rc, _stdout, stderr = run_script(BOOT_HOOK, repo)
        assert rc == 0, f"boot hook must always exit 0. stderr={stderr!r}"

        content = _read_boot_log(repo)
        assert "PLUGIN: no verificable (sin repo fuente junto a la cache)" in content, content


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
