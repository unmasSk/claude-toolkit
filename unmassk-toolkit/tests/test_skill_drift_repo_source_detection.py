"""
Acceptance contract (test-first, RED) for issue #63 point 3 -- boot
simplification plan (docs/plan/refactor-boot-simplification.md), Bilbo's
map (.claude/agent-memory/unmassk-toolkit-bilbo/boot-simplification-63-map.md
section 3).

Confirmed bug (Bilbo, not a designed behavior): lib/boot_health.py:52
computes `REPO_BASE_DIR = dirname(dirname(dirname(abspath(__file__))))`.
That arithmetic is only correct when the running code is a real dev-repo
checkout (3 dirname()s land on <GIT_ROOT>, which genuinely contains
<plugin-dir>/skills/). In PRODUCTION -- any project that installed the
plugin from the marketplace cache -- the module instead runs from
`~/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/<version>/
lib/boot_health.py`, and the same 3 dirname()s land on
`.../unmassk-claude-toolkit/unmassk-toolkit` -- the plugin's OWN cache
folder, whose children are VERSION directories, not plugin directories.
check_skill_drift() then builds its "repo source of truth" index by
scanning that folder as if it held sibling plugins, indiscriminately
picking up whatever SKILL.md happens to live under any cached version
directory (including a totally different cached plugin, since
`repo_index.get(skill_name)` never checks which plugin a skill came from)
-- producing drift warnings that mean nothing, in every project that never
had the toolkit's source checked out at all.

NEW CONTRACT (decision 0f5af98 + Bilbo's map, section 3 -- exact source-
detection mechanism is Ultron's implementation choice, this file asserts
only OBSERVABLE BEHAVIOR):
  - A pure cache layout (no real toolkit source repo present) -> the boot
    briefing must show ZERO drift warnings, even with >=2 cached versions
    of unmassk-toolkit present and content differing between cached
    plugins.
  - The real dev-repo (this repo, a genuine git checkout with real source)
    with an actually-planted drift -> the warning must still fire. The fix
    must not silence genuine drift in the one place the check is actually
    useful.

Fixture design note (determinism): to avoid the SAME pre-existing
dict-overwrite race that IS the reported bug (`_build_repo_skill_index()`
iterates `os.listdir()` in filesystem-dependent order, so which cached
version "wins" for a given skill_name is not guaranteed across hosts/
filesystems), the RED reproduction below plants the mismatched content
under a SEPARATE cached "decoy" plugin folder rather than a second
version of unmassk-toolkit itself. This is the same root cause
(REPO_BASE_DIR resolving to a cache-version-listing directory instead of
real repo source, and repo_index not being scoped to a single plugin) and
reproduces 100% deterministically regardless of directory-listing order --
confirmed by manual trace of _build_repo_skill_index()/check_skill_drift()
before writing this fixture, not assumed. A second, identical-content
unmassk-toolkit version directory is included anyway to keep the ">=2
cached versions" shape of the reported production scenario, without it
being what drives the deterministic assertion.

Canal real: every assertion below runs the actual hook as a subprocess
against a real directory tree (either a full copy of this plugin's own
source for the pure-cache case, or the genuine in-place hook for the
dev-repo case) -- no mocking of check_skill_drift() or its helpers.

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity only -- no exhaustive branch coverage here.

NO production code is touched by this file. Only tests.
"""

import os
import shutil
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")
REAL_SKILLS_DIR = os.path.join(SOURCE_ROOT, "skills")

# Any real skill shipped by this plugin works; unmassk-core is small and stable.
TARGET_SKILL = "unmassk-core"

DECOY_CONTENT = "# DECOY\n\nDeliberately different cached content, never the real skill body.\n"
DRIFTED_CACHED_CONTENT = "# DRIFTED\n\nGenuinely stale cached content for the real dev-repo case.\n"

BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")


def _real_skill_md(skill_name=TARGET_SKILL):
    path = os.path.join(REAL_SKILLS_DIR, skill_name, "SKILL.md")
    assert os.path.isfile(path), f"fixture precondition: {path} must exist"
    return path


# ── Repo / boot helpers ─────────────────────────────────────────────────


def _make_repo(tmp_path, name="throwaway_repo"):
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
    try:
        with open(_boot_log_path(repo), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _run_boot(hook_path, repo, env):
    return run_script(hook_path, repo, env=env)


def _combined_output(hook_path, repo, env):
    rc, stdout, stderr = _run_boot(hook_path, repo, env)
    assert rc == 0, f"boot hook must always exit 0. stderr={stderr!r}"
    return rc, stdout, stderr, stdout + "\n" + _read_boot_log(repo)


# ── Test A: pure cache layout, no real toolkit source -> zero drift ──────


class TestPureCacheLayoutWithoutSourceShowsNoDrift:
    def test_pure_cache_layout_without_toolkit_source_repo_shows_zero_drift_warnings(self, tmp_path):
        home = tmp_path / "prod_home"
        cache_base = home / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"

        # A full, real copy of the running plugin -- this IS what gets
        # executed. Excludes tests/ (irrelevant, large) and __pycache__/.git
        # (never part of a real cache install).
        real_copy = cache_base / "unmassk-toolkit" / "1.0.0"
        shutil.copytree(
            SOURCE_ROOT, real_copy,
            ignore=shutil.ignore_patterns("tests", "__pycache__", ".git"),
        )

        # A second, IDENTICAL-content cached version -- keeps the reported
        # ">=2 cached versions" shape without introducing a second, racy
        # source of drift (see module docstring).
        old_version_skills = cache_base / "unmassk-toolkit" / "0.9.0" / "skills"
        shutil.copytree(REAL_SKILLS_DIR, old_version_skills)

        # Deterministic drift source: an unrelated cached plugin shipping
        # a SKILL.md for the SAME skill name, with different content.
        # repo_index.get(skill_name) is not scoped to a plugin, so this
        # reproduces the bug's root cause (REPO_BASE_DIR resolving to a
        # cache-version-listing directory) without depending on
        # os.listdir() order between two unmassk-toolkit versions.
        decoy_skill_dir = cache_base / "decoy-plugin" / "1.0.0" / "skills" / TARGET_SKILL
        decoy_skill_dir.mkdir(parents=True)
        (decoy_skill_dir / "SKILL.md").write_text(DECOY_CONTENT, encoding="utf-8")

        repo = _make_repo(tmp_path)
        boot_hook_copy = str(real_copy / "hooks" / "session-start-boot.py")
        # os.path.expanduser("~") on Windows ignores HOME and resolves via
        # USERPROFILE (falling back to HOMEDRIVE+HOMEPATH) -- without also
        # redirecting those, CACHE_BASE_DIR resolves to the real runner
        # home instead of this fixture's `home`, and the whole cache-layout
        # scenario silently scans the wrong directory.
        env = {"HOME": str(home), "USERPROFILE": str(home), "HOMEDRIVE": "", "HOMEPATH": str(home)}

        rc, stdout, stderr, combined = _combined_output(boot_hook_copy, repo, env)

        # Scoped to the exact drift-warning text (lib/boot_health.py's own
        # "⚠️ drift: ..." string), not a bare "⚠" -- other, unrelated
        # boot warnings (doctor auto-repair status, memory-accumulation
        # nudges) legitimately use the same emoji and would make a bare
        # "⚠" check fail for the wrong reason.
        assert "drift" not in combined.lower(), (
            "a pure cache layout with no real toolkit source repo must "
            f"produce ZERO drift warnings. combined={combined!r}"
        )


# ── Test B: real dev-repo, genuine drift -> warning still fires ──────────


class TestRealDevRepoStillWarnsOnGenuineDrift:
    def test_dev_repo_with_genuinely_planted_drift_still_warns(self, tmp_path):
        home = tmp_path / "prod_home"
        cache_base = home / ".claude" / "plugins" / "cache" / "unmassk-claude-toolkit"
        version_dir = cache_base / "unmassk-toolkit" / "1.0.0"

        drifted_skill_dir = version_dir / "skills" / TARGET_SKILL
        drifted_skill_dir.mkdir(parents=True)
        (drifted_skill_dir / "SKILL.md").write_text(DRIFTED_CACHED_CONTENT, encoding="utf-8")

        # Sanity: the real repo source and the fabricated cached copy must
        # genuinely differ, or this test would prove nothing.
        with open(_real_skill_md(), encoding="utf-8") as f:
            real_content = f.read()
        assert real_content != DRIFTED_CACHED_CONTENT

        repo = _make_repo(tmp_path)
        # os.path.expanduser("~") on Windows ignores HOME and resolves via
        # USERPROFILE (falling back to HOMEDRIVE+HOMEPATH) -- redirect all
        # of them so CACHE_BASE_DIR points at this fixture's `home` instead
        # of the real runner home, the same fix as Test A above.
        env = {"HOME": str(home), "USERPROFILE": str(home), "HOMEDRIVE": "", "HOMEPATH": str(home)}

        # The REAL, in-place hook -- this process's own file location is a
        # genuine git checkout (this repo), so REPO_BASE_DIR resolves
        # correctly without any copying.
        rc, stdout, stderr, combined = _combined_output(BOOT_HOOK, repo, env)

        assert "drift" in combined.lower(), (
            "a real dev-repo checkout with genuinely planted drift must "
            f"still warn -- source detection must not silence it. combined={combined!r}"
        )
        assert TARGET_SKILL in combined, (
            f"the drift warning must name the drifted skill. combined={combined!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
