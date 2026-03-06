#!/usr/bin/env python3
"""
Lifecycle Test — Doctor, Install, Repair, Uninstall
====================================================
Tests the lifecycle scripts in a temp repo:
  1. Doctor on fresh repo (reports missing components)
  2. Install (creates all components)
  3. Doctor after install (all healthy)
  4. Break components → Repair fixes them
  5. Uninstall (clean removal, history preserved)
  6. Doctor after uninstall (reports missing)
  7. Install --auto (re-install non-interactive)
  8. Uninstall --full-local (removes generated files too)

Usage: python3 tests/lifecycle-test.py
"""

import json
import os
import subprocess
import sys
import tempfile
import shutil

# ── Config ──────────────────────────────────────────────────────────────────

BIN_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "bin",
)
SOURCE_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DOCTOR = os.path.join(BIN_DIR, "git-memory-doctor.py")
INSTALL = os.path.join(BIN_DIR, "git-memory-install.py")
REPAIR = os.path.join(BIN_DIR, "git-memory-repair.py")
UNINSTALL = os.path.join(BIN_DIR, "git-memory-uninstall.py")


# ── Helpers ─────────────────────────────────────────────────────────────────

def run(cmd, cwd, input_text=None, env=None):
    """Run a command and return (stdout, stderr, returncode)."""
    merged = {**os.environ, **(env or {})}
    result = subprocess.run(
        cmd, capture_output=True, text=True, cwd=cwd,
        input=input_text, env=merged, timeout=30,
    )
    return result.stdout.strip(), result.stderr.strip(), result.returncode


def git(args, cwd):
    out, err, rc = run(["git"] + args.split(), cwd)
    return out, rc


def make_temp_repo():
    """Create a temp git repo."""
    path = tempfile.mkdtemp(prefix="lifecycle-test-")
    git("init", path)
    git("checkout -b main", path)
    # Initial commit with trailers
    run(["git", "commit", "--allow-empty", "-m",
         "chore: init repo\n\nWhy: initial setup\nTouched: none"],
        path)
    return path


def run_doctor_json(cwd):
    """Run doctor --json and return parsed result."""
    out, err, rc = run([sys.executable, DOCTOR, "--json"], cwd)
    try:
        return json.loads(out), rc
    except json.JSONDecodeError:
        return {"status": "error", "checks": []}, rc


def run_install(cwd, extra_args=None):
    """Run install with auto mode."""
    args = [sys.executable, INSTALL, "--auto"]
    if extra_args:
        args.extend(extra_args)
    out, err, rc = run(args, cwd)
    return out, err, rc


def run_repair(cwd, extra_args=None):
    """Run repair with auto mode."""
    args = [sys.executable, REPAIR, "--auto"]
    if extra_args:
        args.extend(extra_args)
    out, err, rc = run(args, cwd)
    return out, err, rc


def run_uninstall(cwd, extra_args=None):
    """Run uninstall with auto mode."""
    args = [sys.executable, UNINSTALL, "--auto"]
    if extra_args:
        args.extend(extra_args)
    out, err, rc = run(args, cwd)
    return out, err, rc


# ── Tests ────────────────────────────────────────────────────────────────────

def test_doctor_fresh_repo(cwd):
    """Test 1: Doctor on a fresh repo should find missing components."""
    print("\n── TEST 1: Doctor on Fresh Repo ──")
    errors = []

    result, rc = run_doctor_json(cwd)

    # Should have warnings/errors because nothing is installed
    if result.get("status") == "ok":
        errors.append("Doctor reported 'ok' on a fresh repo with no git-memory installed")
    else:
        print(f"  Doctor status: {result.get('status')} ✓")

    # Check that hooks are reported missing
    hook_check = next((c for c in result.get("checks", []) if c.get("component") == "Hooks"), None)
    if hook_check and "0/4" in hook_check.get("message", ""):
        print(f"  Hooks: correctly reports 0/4 ✓")
    elif hook_check:
        print(f"  Hooks: {hook_check.get('message')}")

    # Check that skills are reported missing
    skill_check = next((c for c in result.get("checks", []) if c.get("component") == "Skills"), None)
    if skill_check and "0/4" in skill_check.get("message", ""):
        print(f"  Skills: correctly reports 0/4 ✓")
    elif skill_check:
        print(f"  Skills: {skill_check.get('message')}")

    return errors


def test_install(cwd):
    """Test 2: Install should create all components."""
    print("\n── TEST 2: Install ──")
    errors = []

    out, err, rc = run_install(cwd)
    if rc != 0:
        errors.append(f"Install failed with exit code {rc}: {err}")
        return errors

    print(f"  Install completed (exit 0) ✓")

    # Check hooks exist
    hooks_dir = os.path.join(cwd, "hooks")
    expected_hooks = [
        "pre-validate-commit-trailers.py",
        "post-validate-commit-trailers.py",
        "precompact-snapshot.py",
        "stop-dod-check.py",
    ]
    for hook in expected_hooks:
        if not os.path.isfile(os.path.join(hooks_dir, hook)):
            errors.append(f"Hook not installed: {hook}")
    if not errors:
        print(f"  Hooks: 4/4 installed ✓")

    # Check skills exist
    skills_dir = os.path.join(cwd, "skills")
    expected_skills = ["git-memory", "git-memory-protocol", "git-memory-lifecycle", "git-memory-recovery"]
    for skill in expected_skills:
        if not os.path.isfile(os.path.join(skills_dir, skill, "SKILL.md")):
            errors.append(f"Skill not installed: {skill}")
    if not any("Skill not" in e for e in errors):
        print(f"  Skills: 4/4 installed ✓")

    # Check CLI
    cli = os.path.join(cwd, "bin", "git-memory")
    if os.path.isfile(cli) and os.access(cli, os.X_OK):
        print(f"  CLI: installed and executable ✓")
    else:
        errors.append("CLI not installed or not executable")

    # Check CLAUDE.md
    claude_md = os.path.join(cwd, "CLAUDE.md")
    if os.path.isfile(claude_md):
        with open(claude_md) as f:
            content = f.read()
        if "BEGIN claude-git-memory" in content:
            print(f"  CLAUDE.md: managed block present ✓")
        else:
            errors.append("CLAUDE.md missing managed block")
    else:
        errors.append("CLAUDE.md not created")

    # Check manifest
    manifest = os.path.join(cwd, ".claude", "git-memory-manifest.json")
    if os.path.isfile(manifest):
        with open(manifest) as f:
            data = json.load(f)
        if data.get("version") == "2.0.0":
            print(f"  Manifest: v{data['version']} ✓")
        else:
            errors.append(f"Manifest version wrong: {data.get('version')}")
    else:
        errors.append("Manifest not created")

    # Check hooks.json
    if os.path.isfile(os.path.join(cwd, "hooks.json")):
        print(f"  hooks.json: present ✓")
    else:
        errors.append("hooks.json not created")

    return errors


def test_doctor_after_install(cwd):
    """Test 3: Doctor after install should report healthy."""
    print("\n── TEST 3: Doctor After Install ──")
    errors = []

    result, rc = run_doctor_json(cwd)

    status = result.get("status")
    if status == "error":
        errors.append(f"Doctor found errors after install: {result}")
    else:
        print(f"  Doctor status: {status} ✓")

    # All checks should be ok or warn (no errors)
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    if error_checks:
        for c in error_checks:
            errors.append(f"Doctor error: {c.get('component')}: {c.get('message')}")
    else:
        print(f"  No error-level checks ✓")

    return errors


def test_repair(cwd):
    """Test 4: Break components, then repair should fix them."""
    print("\n── TEST 4: Break + Repair ──")
    errors = []

    # Break: delete a hook
    hook_path = os.path.join(cwd, "hooks", "pre-validate-commit-trailers.py")
    if os.path.isfile(hook_path):
        os.unlink(hook_path)
        print(f"  Broke: deleted pre-validate hook")

    # Break: delete a skill
    skill_dir = os.path.join(cwd, "skills", "git-memory-protocol")
    if os.path.isdir(skill_dir):
        shutil.rmtree(skill_dir)
        print(f"  Broke: deleted git-memory-protocol skill")

    # Break: delete manifest
    manifest = os.path.join(cwd, ".claude", "git-memory-manifest.json")
    if os.path.isfile(manifest):
        os.unlink(manifest)
        print(f"  Broke: deleted manifest")

    # Verify doctor detects problems
    result, rc = run_doctor_json(cwd)
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    if error_checks:
        print(f"  Doctor detects {len(error_checks)} error(s) ✓")
    else:
        errors.append("Doctor didn't detect broken components")

    # Run repair
    out, err, rc = run_repair(cwd)
    if rc != 0:
        errors.append(f"Repair failed with exit code {rc}: {err}")
        return errors

    print(f"  Repair completed (exit 0) ✓")

    # Verify everything is fixed
    if os.path.isfile(hook_path):
        print(f"  Hook restored ✓")
    else:
        errors.append("Repair didn't restore deleted hook")

    skill_file = os.path.join(cwd, "skills", "git-memory-protocol", "SKILL.md")
    if os.path.isfile(skill_file):
        print(f"  Skill restored ✓")
    else:
        errors.append("Repair didn't restore deleted skill")

    if os.path.isfile(manifest):
        print(f"  Manifest restored ✓")
    else:
        errors.append("Repair didn't restore manifest")

    return errors


def test_uninstall(cwd):
    """Test 5: Uninstall should remove components but preserve git history."""
    print("\n── TEST 5: Uninstall (safe mode) ──")
    errors = []

    # Count commits before uninstall
    out_before, _ = git("rev-list --count HEAD", cwd)

    out, err, rc = run_uninstall(cwd)
    if rc != 0:
        errors.append(f"Uninstall failed with exit code {rc}: {err}")
        return errors

    print(f"  Uninstall completed (exit 0) ✓")

    # Hooks should be gone
    hooks_dir = os.path.join(cwd, "hooks")
    if os.path.isdir(hooks_dir) and os.listdir(hooks_dir):
        errors.append("Hooks directory still has files after uninstall")
    else:
        print(f"  Hooks removed ✓")

    # Skills should be gone
    skills_dir = os.path.join(cwd, "skills")
    if os.path.isdir(skills_dir) and os.listdir(skills_dir):
        errors.append("Skills directory still has files after uninstall")
    else:
        print(f"  Skills removed ✓")

    # CLI should be gone
    cli = os.path.join(cwd, "bin", "git-memory")
    if os.path.exists(cli):
        errors.append("CLI still exists after uninstall")
    else:
        print(f"  CLI removed ✓")

    # CLAUDE.md should NOT have managed block
    claude_md = os.path.join(cwd, "CLAUDE.md")
    if os.path.isfile(claude_md):
        with open(claude_md) as f:
            content = f.read()
        if "BEGIN claude-git-memory" in content:
            errors.append("CLAUDE.md still has managed block after uninstall")
        else:
            print(f"  CLAUDE.md block removed ✓")

    # Manifest should be gone
    manifest = os.path.join(cwd, ".claude", "git-memory-manifest.json")
    if os.path.exists(manifest):
        errors.append("Manifest still exists after uninstall")
    else:
        print(f"  Manifest removed ✓")

    # Git history should be preserved
    out_after, _ = git("rev-list --count HEAD", cwd)
    if out_before == out_after:
        print(f"  Git history preserved ({out_after} commits) ✓")
    else:
        errors.append(f"Git history changed: {out_before} → {out_after}")

    return errors


def test_doctor_after_uninstall(cwd):
    """Test 6: Doctor after uninstall should find missing components."""
    print("\n── TEST 6: Doctor After Uninstall ──")
    errors = []

    result, rc = run_doctor_json(cwd)

    # Should report errors (everything is gone)
    if result.get("status") == "ok":
        errors.append("Doctor reported 'ok' after uninstall")
    else:
        print(f"  Doctor status: {result.get('status')} (expected) ✓")

    return errors


def test_reinstall(cwd):
    """Test 7: Re-install after uninstall."""
    print("\n── TEST 7: Re-install ──")
    errors = []

    out, err, rc = run_install(cwd)
    if rc != 0:
        errors.append(f"Re-install failed: {err}")
        return errors

    print(f"  Re-install completed (exit 0) ✓")

    # Quick verify
    result, _ = run_doctor_json(cwd)
    error_checks = [c for c in result.get("checks", []) if c.get("level") == "error"]
    if not error_checks:
        print(f"  Doctor after re-install: no errors ✓")
    else:
        for c in error_checks:
            errors.append(f"Error after re-install: {c.get('component')}: {c.get('message')}")

    return errors


def test_uninstall_full_local(cwd):
    """Test 8: Uninstall --full-local removes generated files too."""
    print("\n── TEST 8: Uninstall --full-local ──")
    errors = []

    # Create a fake generated file
    dashboard = os.path.join(cwd, ".claude", "dashboard.html")
    os.makedirs(os.path.dirname(dashboard), exist_ok=True)
    with open(dashboard, "w") as f:
        f.write("<html>dashboard</html>")

    out, err, rc = run_uninstall(cwd, ["--full-local"])
    if rc != 0:
        errors.append(f"Uninstall --full-local failed: {err}")
        return errors

    print(f"  Uninstall --full-local completed (exit 0) ✓")

    if os.path.exists(dashboard):
        errors.append("Dashboard not removed in full-local mode")
    else:
        print(f"  Generated files removed ✓")

    return errors


def test_repair_dry_run(cwd):
    """Test 9: Repair --dry-run doesn't change anything."""
    print("\n── TEST 9: Repair --dry-run ──")
    errors = []

    # Install first
    run_install(cwd)

    # Break something
    hook = os.path.join(cwd, "hooks", "stop-dod-check.py")
    if os.path.isfile(hook):
        os.unlink(hook)

    # Dry run should NOT fix it
    out, err, rc = run([sys.executable, REPAIR, "--dry-run"], cwd)

    if os.path.isfile(hook):
        errors.append("Dry run actually repaired the hook")
    else:
        print(f"  Dry run didn't change files ✓")

    # Now repair for real
    run_repair(cwd)
    if os.path.isfile(hook):
        print(f"  Real repair restored the hook ✓")
    else:
        errors.append("Real repair didn't restore the hook")

    return errors


# ── Main ──────────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("LIFECYCLE TEST — Doctor, Install, Repair, Uninstall")
    print("=" * 60)

    # Verify scripts exist
    for script, name in [(DOCTOR, "doctor"), (INSTALL, "install"), (REPAIR, "repair"), (UNINSTALL, "uninstall")]:
        if not os.path.isfile(script):
            print(f"ERROR: {name} script not found at {script}")
            sys.exit(1)

    cwd = make_temp_repo()
    print(f"Temp repo: {cwd}")

    try:
        all_errors = []
        all_errors.extend(test_doctor_fresh_repo(cwd))
        all_errors.extend(test_install(cwd))
        all_errors.extend(test_doctor_after_install(cwd))
        all_errors.extend(test_repair(cwd))
        all_errors.extend(test_uninstall(cwd))
        all_errors.extend(test_doctor_after_uninstall(cwd))
        all_errors.extend(test_reinstall(cwd))
        all_errors.extend(test_uninstall_full_local(cwd))
        all_errors.extend(test_repair_dry_run(cwd))

        print("\n" + "=" * 60)
        if all_errors:
            print(f"LIFECYCLE TEST: {len(all_errors)} FAILURE(S)")
            for err in all_errors:
                print(f"  ✗ {err}")
            sys.exit(1)
        else:
            print("LIFECYCLE TEST: ALL PASSED ✓")
            print("  1. Doctor on fresh repo")
            print("  2. Install creates all components")
            print("  3. Doctor after install (healthy)")
            print("  4. Break + Repair")
            print("  5. Uninstall (safe mode)")
            print("  6. Doctor after uninstall")
            print("  7. Re-install")
            print("  8. Uninstall --full-local")
            print("  9. Repair --dry-run")
            sys.exit(0)

    finally:
        shutil.rmtree(cwd, ignore_errors=True)
        print(f"\nCleaned up {cwd}")


if __name__ == "__main__":
    main()
