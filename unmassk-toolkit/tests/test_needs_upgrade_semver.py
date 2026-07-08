"""
Contract tests (test-first / RED) for the semver version-sync rule in needs_upgrade().

These tests define the new behaviour to be implemented in
hooks/user-prompt-memory-check.py::needs_upgrade().

DESIGN CONTRACT (do not re-design — only implement until these pass):
  1. needs_upgrade() returns True when manifest.version < PLUGIN_VERSION (code).
  2. The comparison is real semver (numeric by component), NOT lexicographic string
     comparison.  "1.10.0" > "1.9.0" must be True.
  3. No downgrade: manifest.version > PLUGIN_VERSION → False (never force-upgrade
     when installed plugin is newer than the code running).
  4. Equal versions → False.
  5. Fail-safe for missing / corrupt / unreadable manifest → False.
     Reason: if the manifest is absent or unreadable, needs_install() already
     handles the "not installed" path.  Returning True here would cause an infinite
     upgrade loop on every session start because the manifest is never successfully
     written before the next hook fires.  Silence is safer than a boot-time loop.
  6. No infinite loop: after a sync that brings manifest.version == PLUGIN_VERSION,
     the next call must return False for this reason (the semver rule must not
     re-trigger after a successful upgrade).
  7. Pre-existing upgrade reasons (stale CLAUDE.md block markers) continue to work.
     The new rule ADDS to needs_upgrade(); it does not replace the old logic.

Manifest location (relative to project root):
    .claude/.unmassk/manifest.json  →  {"version": "<semver>", ...}

PLUGIN_VERSION source:
    lib/version.py::VERSION  (reads from .claude-plugin/plugin.json at plugin root)
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import INSTALL, git_cmd, run_script, SOURCE_ROOT

# ── Import the hook under test ────────────────────────────────────────────────
# needs_upgrade() lives in hooks/user-prompt-memory-check.py.
# We import it as a module by adding hooks/ to sys.path temporarily.
# We do NOT use sys.modules manipulation — we add to sys.path and import directly
# (monkeypatch.syspath_prepend keeps the insertion isolated to the test session).

HOOKS_DIR = os.path.join(SOURCE_ROOT, "hooks")
HOOK_MODULE_NAME = "user_prompt_memory_check"
HOOK_FILE = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")


def _import_hook(monkeypatch):
    """
    Import hooks/user-prompt-memory-check.py as a module.

    We use importlib so we can give the file a clean module name without
    colliding with anything in sys.modules from other test files.
    Uses monkeypatch to prepend hooks/ and lib/ to sys.path so the hook's
    own imports (git_helpers, etc.) resolve correctly.
    """
    import importlib.util

    monkeypatch.syspath_prepend(HOOKS_DIR)
    monkeypatch.syspath_prepend(os.path.join(SOURCE_ROOT, "lib"))

    spec = importlib.util.spec_from_file_location(HOOK_MODULE_NAME, HOOK_FILE)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_installed_repo(tmp_path, name="repo"):
    """Create a temp git repo with git-memory fully installed."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    subprocess.run(["git", "init", repo], capture_output=True)
    subprocess.run(
        ["git", "-C", repo, "commit", "--allow-empty", "-m", "init"],
        capture_output=True,
    )
    run_script(INSTALL, repo, ["--auto"])
    return repo


def make_semver_test_repo(tmp_path, name="repo"):
    """
    Create an installed repo whose CLAUDE.md satisfies ALL pre-existing
    upgrade conditions (no stale markers), so needs_upgrade() can only
    return True via the new semver rule.

    Context: a freshly installed repo may not contain 'Context Checkpoint
    Commits' in the managed block (the text lives in the full skill payload,
    not in the minimal CLAUDE.md snippet).  This means the pre-existing
    condition '"Context Checkpoint Commits" not in block' fires as True,
    making some semver tests pass for the wrong reason.

    We patch the managed block to contain both required strings so the
    old conditions are definitively False, leaving only semver as the trigger.
    """
    repo = make_installed_repo(tmp_path, name)

    claude_md_path = os.path.join(repo, "CLAUDE.md")
    with open(claude_md_path, encoding="utf-8") as f:
        content = f.read()

    # Locate the managed block.
    begin = content.find("BEGIN unmassk-toolkit")
    end = content.find("END unmassk-toolkit")

    if begin != -1 and end != -1:
        block = content[begin:end]
        patched_block = block

        # Ensure old-style marker is NOT present (it would trigger upgrade).
        patched_block = patched_block.replace("python3 bin/", "")

        # Ensure the required string IS present (its absence triggers upgrade).
        if "Context Checkpoint Commits" not in patched_block:
            patched_block = patched_block + "\nContext Checkpoint Commits\n"

        content = content[:begin] + patched_block + content[end:]
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)

    return repo


def write_manifest(repo, version, extra=None):
    """Write .claude/.unmassk/manifest.json with the given version string."""
    manifest_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(manifest_dir, exist_ok=True)
    data = {"version": version, "runtime_mode": "normal"}
    if extra:
        data.update(extra)
    with open(os.path.join(manifest_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(data, f)


def read_manifest_version(repo):
    """Read back the version from manifest.json."""
    manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
    with open(manifest_path, encoding="utf-8") as f:
        return json.load(f)["version"]


# ── Tests: semver comparison rule ────────────────────────────────────────────


class TestNeedsUpgradeSemver:
    """
    needs_upgrade() must apply semver comparison between manifest.version
    and PLUGIN_VERSION.  These tests all expect the NEW behaviour that does
    not yet exist in the production code — they must start RED.
    """

    def test_manifest_older_than_code_returns_true(self, tmp_path, monkeypatch):
        """
        manifest.version < PLUGIN_VERSION → needs_upgrade() returns True.

        Core case: installed plugin lags behind the code in the cache.

        Uses make_semver_test_repo so the CLAUDE.md block satisfies the
        pre-existing conditions; only the semver rule can trigger True here.
        """
        repo = make_semver_test_repo(tmp_path)
        # Force manifest to a version that is definitely lower than any real release.
        write_manifest(repo, "0.0.1")

        hook = _import_hook(monkeypatch)
        assert hook.needs_upgrade(repo) is True

    def test_manifest_newer_than_code_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.version > PLUGIN_VERSION → needs_upgrade() returns False.

        No downgrade: if the installed plugin is newer than the running code,
        do not trigger an upgrade (the code is older, not the install).
        """
        repo = make_semver_test_repo(tmp_path)
        # Write a very high version number.
        write_manifest(repo, "999.0.0")

        hook = _import_hook(monkeypatch)
        assert hook.needs_upgrade(repo) is False

    def test_manifest_equal_to_code_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.version == PLUGIN_VERSION → needs_upgrade() returns False.

        Identical versions mean everything is in sync; no action needed.
        """
        from version import VERSION

        repo = make_semver_test_repo(tmp_path)
        write_manifest(repo, VERSION)

        hook = _import_hook(monkeypatch)
        assert hook.needs_upgrade(repo) is False

    def test_semver_not_lexicographic_minor_bump(self, tmp_path, monkeypatch):
        """
        Semver comparison must be numeric, not string-based.

        "1.9.0" < "1.10.0" numerically.  String comparison gives the wrong
        answer ("1.9.0" > "1.10.0" lexicographically because "9" > "1").

        Scenario: manifest is at 1.9.0, code is at 1.10.0.
        needs_upgrade() must return True (manifest is behind).

        This test can only pass if the implementation uses numeric comparison.

        Implementation contract: needs_upgrade() must read its "code version"
        from a module-level constant PLUGIN_VERSION so the test can patch it.
        Ultron must define:  PLUGIN_VERSION = VERSION  at module level in the hook.
        """
        repo = make_semver_test_repo(tmp_path)
        write_manifest(repo, "1.9.0")

        # Load the hook, then patch PLUGIN_VERSION before calling needs_upgrade().
        # This pattern requires Ultron to expose PLUGIN_VERSION as a module-level
        # constant so monkeypatch.setattr can reach it.
        hook = _import_hook(monkeypatch)
        monkeypatch.setattr(hook, "PLUGIN_VERSION", "1.10.0", raising=False)

        # Numeric: 1.9 < 1.10 → True
        assert hook.needs_upgrade(repo) is True

    def test_semver_not_lexicographic_reverse(self, tmp_path, monkeypatch):
        """
        Complement of the minor-bump test: manifest at 1.10.0, code at 1.9.0.

        Numerically manifest > code → False (no downgrade).
        String comparison would give the wrong True.
        """
        repo = make_semver_test_repo(tmp_path)
        write_manifest(repo, "1.10.0")

        hook = _import_hook(monkeypatch)
        monkeypatch.setattr(hook, "PLUGIN_VERSION", "1.9.0", raising=False)

        # Numeric: 1.10 > 1.9 → manifest is newer than code → False
        assert hook.needs_upgrade(repo) is False


# ── Tests: fail-safe cases ────────────────────────────────────────────────────


class TestNeedsUpgradeFailSafe:
    """
    When the manifest is absent, corrupt, or has an unparseable version,
    needs_upgrade() must return False (not raise, not trigger a loop).

    Default safe = False.
    Reason (see module docstring): returning True here causes an infinite
    upgrade loop because the manifest is never written before the next hook
    fires.  Silence is the safe choice.
    """

    def test_manifest_absent_returns_false(self, tmp_path, monkeypatch):
        """
        No manifest file at all → False.

        needs_install() handles the "not installed" path; we must not
        double-trigger from here.
        """
        repo = make_semver_test_repo(tmp_path)
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        if os.path.isfile(manifest_path):
            os.remove(manifest_path)

        hook = _import_hook(monkeypatch)
        # Must not raise; must return False.
        result = hook.needs_upgrade(repo)
        assert result is False

    def test_manifest_corrupt_json_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.json contains invalid JSON → False (no exception escapes).
        """
        repo = make_semver_test_repo(tmp_path)
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            f.write("{ this is not valid json !!!")

        hook = _import_hook(monkeypatch)
        result = hook.needs_upgrade(repo)
        assert result is False

    def test_manifest_missing_version_key_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.json is valid JSON but has no "version" key → False.
        """
        repo = make_semver_test_repo(tmp_path)
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"runtime_mode": "normal"}, f)  # no "version" key

        hook = _import_hook(monkeypatch)
        result = hook.needs_upgrade(repo)
        assert result is False

    def test_manifest_unparseable_version_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.json has a "version" value that is not a valid semver string
        (e.g. "not-a-version") → False (no exception escapes).
        """
        repo = make_semver_test_repo(tmp_path)
        write_manifest(repo, "not-a-semver-string")

        hook = _import_hook(monkeypatch)
        result = hook.needs_upgrade(repo)
        assert result is False

    def test_manifest_empty_version_string_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.json has version = "" → False (no exception escapes).
        """
        repo = make_semver_test_repo(tmp_path)
        write_manifest(repo, "")

        hook = _import_hook(monkeypatch)
        result = hook.needs_upgrade(repo)
        assert result is False

    def test_manifest_null_version_returns_false(self, tmp_path, monkeypatch):
        """
        manifest.json has version = null (JSON null, Python None) → False.

        Distinct from "version key absent" and from version = "":
        - Key absent  → .get("version") returns None via default.
        - version = "" → truthiness guard catches empty string.
        - version = null → JSON null deserialises to Python None; a truthiness
          guard catches it, but a strict isinstance(v, str) guard would need to
          handle it separately.

        A regression in the order of guards (e.g. calling .split(".") on None
        before the truthiness check) would raise AttributeError instead of
        returning False.  This test pins that contract.
        """
        repo = make_semver_test_repo(tmp_path)
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump({"version": None}, f)  # produces {"version": null} in JSON

        hook = _import_hook(monkeypatch)
        result = hook.needs_upgrade(repo)
        assert result is False


# ── Tests: no-loop guarantee ──────────────────────────────────────────────────


class TestNeedsUpgradeNoLoop:
    """
    After a successful sync, the next call to needs_upgrade() must return
    False for the version-sync reason (no infinite upgrade loop).
    """

    def test_no_loop_after_version_sync(self, tmp_path, monkeypatch):
        """
        If manifest.version == PLUGIN_VERSION (post-upgrade state),
        needs_upgrade() returns False — the version-sync rule does not
        re-trigger on the very next hook invocation.
        """
        from version import VERSION

        repo = make_semver_test_repo(tmp_path)

        # Simulate the state immediately AFTER a successful upgrade:
        # manifest is now in sync with the code.
        write_manifest(repo, VERSION)

        hook = _import_hook(monkeypatch)
        # Called once (simulating the next session-start after upgrade).
        assert hook.needs_upgrade(repo) is False

        # Called a second time (another session): still False.
        hook2 = _import_hook(monkeypatch)
        assert hook2.needs_upgrade(repo) is False


# ── Tests: pre-existing upgrade reasons preserved ────────────────────────────


class TestNeedsUpgradePreexistingReasons:
    """
    The new semver rule ADDS a trigger condition.  The old reasons
    (stale CLAUDE.md markers) must continue to fire independently.
    """

    def test_stale_block_still_triggers_upgrade(self, tmp_path, monkeypatch):
        """
        A CLAUDE.md block with the old 'python3 bin/' marker still causes
        needs_upgrade() to return True, regardless of manifest version.
        """
        from version import VERSION

        repo = make_installed_repo(tmp_path)

        # Manifest is in sync (semver rule would say False alone).
        write_manifest(repo, VERSION)

        # Tamper CLAUDE.md to contain the old-style marker.
        claude_md_path = os.path.join(repo, "CLAUDE.md")
        with open(claude_md_path, encoding="utf-8") as f:
            content = f.read()
        content = content.replace("unmassk-toolkit Active", "python3 bin/git-memory-install.py")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)

        hook = _import_hook(monkeypatch)
        # The stale-block detector must still fire.
        assert hook.needs_upgrade(repo) is True

    def test_missing_context_checkpoint_still_triggers_upgrade(self, tmp_path, monkeypatch):
        """
        A CLAUDE.md block missing 'Context Checkpoint Commits' still causes
        needs_upgrade() to return True.
        """
        from version import VERSION

        repo = make_installed_repo(tmp_path)
        write_manifest(repo, VERSION)

        claude_md_path = os.path.join(repo, "CLAUDE.md")
        with open(claude_md_path, encoding="utf-8") as f:
            content = f.read()
        # Remove the 'Context Checkpoint Commits' text from inside the managed block.
        content = content.replace("Context Checkpoint Commits", "Checkpoint Notes")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)

        hook = _import_hook(monkeypatch)
        assert hook.needs_upgrade(repo) is True

    def test_both_conditions_true_still_returns_true(self, tmp_path, monkeypatch):
        """
        When both the semver condition AND the stale-block condition are true,
        needs_upgrade() returns True (union, not intersection).
        """
        repo = make_installed_repo(tmp_path)

        # Manifest is old (semver trigger).
        write_manifest(repo, "0.0.1")

        # Also tamper CLAUDE.md (stale-block trigger).
        claude_md_path = os.path.join(repo, "CLAUDE.md")
        with open(claude_md_path, encoding="utf-8") as f:
            content = f.read()
        content = content.replace("unmassk-toolkit Active", "python3 bin/git-memory-install.py")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write(content)

        hook = _import_hook(monkeypatch)
        assert hook.needs_upgrade(repo) is True


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
