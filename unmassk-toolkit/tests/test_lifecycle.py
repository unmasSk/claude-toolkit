"""
Lifecycle tests for doctor, install, and repair.

Runs the install, doctor, break, repair cycle in a shared temporary repo.

NOTE: The plugin runs from the cache (SOURCE_ROOT). Install only creates
CLAUDE.md + manifest at the project root. Doctor checks the plugin cache
for hooks/skills and the project for CLAUDE.md/manifest.

Retirement note (2026-08-02): bin/git-memory-uninstall.py no longer exists
on disk (see docs/memoria-v2/PLAN-CONSTRUCCION.md §5.4, "ya estaban
muertos") -- test_uninstall and test_uninstall_full_local were removed
along with the run_uninstall() helper and the UNINSTALL import, per §9.3
("borrar los tests de cada pieza retirada, a la vez que la pieza").
test_doctor_after_uninstall was left in place unmodified: it already
passed without a real uninstall ever running in this sequence (the dead
script call inside the old test_uninstall failed at its own rc==0
assertion before touching the filesystem, so this test's outcome is
unchanged by the removal).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile

import pytest

from conftest import (
    DOCTOR, INSTALL, REPAIR,
    run_cmd, git_cmd, run_script, run_doctor_json,
)
from version import VERSION


# ── Helpers ────────────────────────────────────────────────────────────

def run_install(cwd, extra_args=None):
    """Run the install script with --auto."""
    return run_script(INSTALL, cwd, ["--auto"] + (extra_args or []))


def run_repair(cwd, extra_args=None):
    """Run the repair script with --auto."""
    return run_script(REPAIR, cwd, ["--auto"] + (extra_args or []))


# ── Module-scoped fixture (sequential tests share one repo) ───────────

@pytest.fixture(scope="module")
def lifecycle_repo():
    """Create a temp git repo for lifecycle tests."""
    path = tempfile.mkdtemp(prefix="lifecycle-test-")
    git_cmd(["init"], path)
    git_cmd(["checkout", "-b", "main"], path)
    run_cmd(["git", "commit", "--allow-empty", "-m",
             "chore: init repo\n\nWhy: initial setup\nTouched: none"], path)
    yield path
    shutil.rmtree(path, ignore_errors=True)


# ── Tests (run in definition order) ───────────────────────────────────


def test_doctor_fresh_repo(lifecycle_repo):
    """Doctor on a fresh repo should find missing CLAUDE.md/manifest."""
    result, rc = run_doctor_json(lifecycle_repo)
    assert result.get("status") != "ok", "Doctor reported 'ok' on fresh repo"

    # Should detect missing CLAUDE.md
    claude_check = next((c for c in result.get("checks", [])
                         if c.get("component") == "CLAUDE.md"), None)
    assert claude_check and claude_check.get("level") in ("error", "warn")


def test_install(lifecycle_repo):
    """Install should create CLAUDE.md and manifest (nothing else)."""
    rc, _, _ = run_install(lifecycle_repo)
    assert rc == 0

    # CLAUDE.md
    with open(os.path.join(lifecycle_repo, "CLAUDE.md"), encoding="utf-8") as f:
        assert "BEGIN unmassk-toolkit" in f.read()

    # Manifest
    with open(os.path.join(lifecycle_repo, ".claude", ".unmassk", "manifest.json"), encoding="utf-8") as f:
        manifest = json.load(f)
        assert manifest["version"] == VERSION

    # Nothing copied to project root (no hooks, skills, bin, lib)
    assert not os.path.isdir(os.path.join(lifecycle_repo, "hooks"))
    assert not os.path.isdir(os.path.join(lifecycle_repo, "skills"))
    assert not os.path.isdir(os.path.join(lifecycle_repo, "bin"))
    assert not os.path.isdir(os.path.join(lifecycle_repo, "lib"))
    assert not os.path.isdir(os.path.join(lifecycle_repo, ".claude-plugin"))


def test_doctor_after_install(lifecycle_repo):
    """Doctor after install should report healthy (no errors)."""
    result, _ = run_doctor_json(lifecycle_repo)
    assert result.get("status") != "error"
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    assert not error_checks


def test_repair_missing_manifest(lifecycle_repo):
    """Break manifest, then repair should fix it."""
    manifest = os.path.join(lifecycle_repo, ".claude", ".unmassk", "manifest.json")

    # Break: remove manifest
    if os.path.isfile(manifest):
        os.unlink(manifest)

    # Doctor detects the problem
    result, _ = run_doctor_json(lifecycle_repo)
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    assert len(error_checks) > 0

    # Repair fixes it
    rc, _, _ = run_repair(lifecycle_repo)
    assert rc == 0
    assert os.path.isfile(manifest), "Manifest not restored"


def test_repair_missing_claude_md_block(lifecycle_repo):
    """Break CLAUDE.md block, then repair should fix it."""
    claude_md = os.path.join(lifecycle_repo, "CLAUDE.md")

    # Break: remove the managed block
    with open(claude_md, encoding="utf-8") as f:
        content = f.read()
    begin = "<!-- BEGIN unmassk-toolkit"
    end = "<!-- END unmassk-toolkit -->"
    begin_idx = content.find(begin)
    end_idx = content.find(end)
    if begin_idx != -1 and end_idx != -1:
        content = content[:begin_idx] + content[end_idx + len(end):]
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(content)

    # Doctor detects the problem
    result, _ = run_doctor_json(lifecycle_repo)
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    assert len(error_checks) > 0

    # Repair fixes it
    rc, _, _ = run_repair(lifecycle_repo)
    assert rc == 0
    with open(claude_md, encoding="utf-8") as f:
        assert "BEGIN unmassk-toolkit" in f.read()


def test_doctor_after_uninstall(lifecycle_repo):
    """Doctor after uninstall should find missing components."""
    result, _ = run_doctor_json(lifecycle_repo)
    assert result.get("status") != "ok"


def test_reinstall(lifecycle_repo):
    """Re-install after uninstall."""
    rc, _, _ = run_install(lifecycle_repo)
    assert rc == 0

    result, _ = run_doctor_json(lifecycle_repo)
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    assert not error_checks


def test_repair_dry_run(lifecycle_repo):
    """Repair --dry-run doesn't change anything."""
    run_install(lifecycle_repo)

    # Break manifest
    manifest = os.path.join(lifecycle_repo, ".claude", ".unmassk", "manifest.json")
    os.unlink(manifest)

    # Dry run should NOT fix it
    run_cmd([sys.executable, REPAIR, "--dry-run"], lifecycle_repo)
    assert not os.path.isfile(manifest), "Dry run repaired the manifest"

    # Real repair should fix it
    run_repair(lifecycle_repo)
    assert os.path.isfile(manifest), "Real repair didn't restore the manifest"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
