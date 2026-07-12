"""
Regression for issue #64 -- lib/boot_health.py::check_version_mismatch()
(fixed L231-235/263-278 by Ultron).

Bug: the upgrade-suggestion check compared versions as raw strings
(`installed != PLUGIN_VERSION`) instead of semver, so an installed
manifest version NEWER than the running code still produced an "update
available" warning -- backwards. Confirmed PoC: manifest "9.9.9" vs code
"1.19.4" still suggested an update.

Fix: reuse the same numeric semver comparator upgrade_check.needs_upgrade()
already trusts for its own Check 2 (`upgrade_check._parse_semver`), and
only warn when `installed_tuple < code_tuple` (code is genuinely newer).
Fail-safe: an unparseable version on either side suppresses the warning,
same discipline as the rest of this function's broad except-Exception
fallback.

Channel: same isolated-subprocess pattern as
test_issue63_manifest_read_hardening.py's `_call_check_version_mismatch()`
(never in-process -- boot_health/version are real, stably-named modules;
an in-process import risks sys.modules contamination across other test
files in the same pytest session, see
unmassk-toolkit-python-test-conventions.md). Manifest version is written
directly (no symlink trickery needed here -- that's SEC-T1-002's separate
concern, already covered by the sibling file); only the version FIELD of
the real installer-produced manifest.json is substituted per test.

Project scope note: this is a self-inflicted correctness bug (a
misleading upgrade suggestion shown to the same single owner this system
serves), not an attacker scenario -- per this project's CLAUDE.md
threat model, no adversarial framing applies. These tests only prove the
boot hook doesn't lie to the user about upgrade availability, and doesn't
crash on a malformed version string.

Build mode: linear (fix already applied by Ultron in wip covering
L231-235/263-278). Only tests here -- no production code changed.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, INSTALL, git_cmd, run_script

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


# ── Repo helpers (same shape as test_issue63_manifest_read_hardening.py) ──


def _make_installed_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"install --auto failed: {out}\n{err}"
    return repo


def _manifest_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "manifest.json")


def _write_manifest_version(repo, version):
    """Overwrite only the "version" field of the REAL manifest.json the
    installer just produced, preserving every other field. Not a
    fabricated fixture: the manifest itself is the real artifact under
    test (installed_at, runtime_mode, managed_blocks all stay genuine) --
    only the one field this regression targets is substituted."""
    path = _manifest_path(repo)
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)
    manifest["version"] = version
    with open(path, "w", encoding="utf-8") as f:
        json.dump(manifest, f)


def _read_plugin_version():
    """Derive PLUGIN_VERSION from the real source module in a subprocess,
    never hand-typed -- so this file doesn't need updating every time the
    toolkit's own version is bumped by bin/release.py."""
    code = f"import sys; sys.path.insert(0, {LIB_DIR!r}); from version import VERSION; print(VERSION)"
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", timeout=30
    )
    assert proc.returncode == 0, f"could not read PLUGIN_VERSION: {proc.stderr}"
    return proc.stdout.strip()


# ── Direct-call probe, isolated subprocess (see module docstring) ────────


def _call_check_version_mismatch(repo, patch_plugin_version=None):
    # check_version_mismatch() has no params -- derives git root via
    # run_git(["rev-parse", "--show-toplevel"]) off the ambient process
    # cwd, so the subprocess itself is launched with cwd=repo (same
    # convention as test_issue63_manifest_read_hardening.py).
    patch_line = (
        f"boot_health.PLUGIN_VERSION = {patch_plugin_version!r}\n"
        if patch_plugin_version is not None
        else ""
    )
    code = f"""
import sys, json
sys.path.insert(0, {LIB_DIR!r})
import boot_health
{patch_line}result = boot_health.check_version_mismatch()
print(json.dumps({{"result": result}}))
"""
    return subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8",
        cwd=repo, timeout=30,
    )


def _result_or_fail(proc, label):
    assert proc.returncode == 0, (
        f"{label} probe must not crash (fail-safe contract). "
        f"rc={proc.returncode} stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    last_line = proc.stdout.strip().splitlines()[-1]
    return json.loads(last_line)["result"]


# ══════════════════════════════════════════════════════════════════════════
# Exact PoC: installed NEWER than code must never suggest "update".
# Pre-fix, raw string inequality alone triggered the warning branch
# regardless of direction (backwards).
# ══════════════════════════════════════════════════════════════════════════


class TestIssue64InstalledNewerThanCodeSuppressesWarning:
    def test_installed_9_9_9_never_suggests_update(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        _write_manifest_version(repo, "9.9.9")

        proc = _call_check_version_mismatch(repo)
        result = _result_or_fail(proc, "check_version_mismatch")

        assert result is None, (
            "Issue #64: installed version 9.9.9 is newer than PLUGIN_VERSION -- "
            f"must not suggest an update. Got result={result!r} stdout={proc.stdout!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Boundary: installed == PLUGIN_VERSION must not warn either.
# ══════════════════════════════════════════════════════════════════════════


class TestIssue64EqualVersionsSuppressWarning:
    def test_installed_equal_to_plugin_version_returns_none(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        plugin_version = _read_plugin_version()
        _write_manifest_version(repo, plugin_version)

        proc = _call_check_version_mismatch(repo)
        result = _result_or_fail(proc, "check_version_mismatch")

        assert result is None, (
            f"Installed version equal to PLUGIN_VERSION ({plugin_version!r}) must "
            f"not suggest an update. Got result={result!r} stdout={proc.stdout!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Genuine mismatch: code newer than installed MUST still warn (the fix
# must not overcorrect into never warning at all).
# ══════════════════════════════════════════════════════════════════════════


class TestIssue64CodeGenuinelyNewerSuggestsUpdate:
    def test_installed_lower_than_code_suggests_update(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        _write_manifest_version(repo, "0.0.1")
        plugin_version = _read_plugin_version()

        proc = _call_check_version_mismatch(repo)
        result = _result_or_fail(proc, "check_version_mismatch")

        assert result is not None, (
            "Installed version 0.0.1 is genuinely older than PLUGIN_VERSION -- "
            f"must suggest an update. stdout={proc.stdout!r}"
        )
        assert "0.0.1" in result, f"warning must name the installed version. Got {result!r}"
        assert plugin_version in result, f"warning must name PLUGIN_VERSION. Got {result!r}"
        assert "Suggest /plugin update" in result, f"warning must include the CTA. Got {result!r}"


# ══════════════════════════════════════════════════════════════════════════
# Edge cases: unparseable version on either side fails safe to None,
# never crashes and never warns with garbage content.
# ══════════════════════════════════════════════════════════════════════════


class TestIssue64UnparseableVersionFailsSafe:
    def test_unparseable_installed_version_returns_none(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        _write_manifest_version(repo, "not-a-version")

        proc = _call_check_version_mismatch(repo)
        result = _result_or_fail(proc, "check_version_mismatch")

        assert result is None, (
            f"Unparseable installed version must fail-safe to None. "
            f"Got result={result!r} stdout={proc.stdout!r}"
        )

    def test_unparseable_plugin_version_returns_none(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        _write_manifest_version(repo, "1.0.0")  # valid on the installed side

        proc = _call_check_version_mismatch(repo, patch_plugin_version="not-a-version")
        result = _result_or_fail(proc, "check_version_mismatch")

        assert result is None, (
            f"Unparseable PLUGIN_VERSION must fail-safe to None. "
            f"Got result={result!r} stdout={proc.stdout!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
