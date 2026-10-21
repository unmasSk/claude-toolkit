#!/usr/bin/env python3
"""Repair the project-level git-memory files: CLAUDE.md managed block and manifest.

Exit codes: 0 repaired or nothing to repair, 1 a repair failed, 2 aborted by the user.
"""

import argparse
import json
import os
import subprocess
import sys
from typing import Any

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import run_git, open_no_follow_symlink


# ── Helpers ───────────────────────────────────────────────────────────────

def find_source_root() -> str:
    """Find the git-memory plugin source root (where this script lives)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_target_root() -> str:
    """Find the target repo root (cwd's git root)."""
    code, output = run_git(["rev-parse", "--show-toplevel"])
    if code == 0:
        return output
    return os.getcwd()


# ── Diagnosis ─────────────────────────────────────────────────────────────

def diagnose(target: str) -> list[tuple[str, str, str]]:
    """Return the project-level issues as (issue_type, target_name, description) tuples."""
    issues = []

    claude_md = os.path.join(target, "CLAUDE.md")
    if os.path.isfile(claude_md):
        try:
            # A symlinked CLAUDE.md is reported as an issue, never followed.
            with open_no_follow_symlink(claude_md, "r") as f:
                content = f.read()
            if "BEGIN unmassk-toolkit" not in content:
                issues.append(("missing_block", "CLAUDE.md", "Managed block missing in CLAUDE.md"))
        except OSError:
            issues.append(("symlinked_claude_md", "CLAUDE.md", "CLAUDE.md is a symlink (refusing to follow)"))
    else:
        issues.append(("missing_claude_md", "CLAUDE.md", "CLAUDE.md not found"))

    manifest_path = os.path.join(target, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        issues.append(("missing_manifest", "manifest", "Manifest missing"))
    else:
        try:
            # A symlinked manifest is reported as corrupt, never followed.
            with open_no_follow_symlink(manifest_path, "r") as f:
                json.load(f)
        except (json.JSONDecodeError, OSError):
            issues.append(("corrupt_manifest", "manifest", "Manifest corrupt (invalid JSON)"))

    # Old-style install remnants at the project root.
    old_files = [
        "bin/git-memory-doctor.py", "hooks/pre-validate-commit-trailers.py",
        ".claude-plugin/plugin.json",
    ]
    for f in old_files:
        if os.path.isfile(os.path.join(target, f)):
            issues.append(("old_install", f, "Old-style install files at project root"))
            break

    return issues


# ── Repair Actions ────────────────────────────────────────────────────────

def repair_issue(issue_type: str, source: str, target: str) -> bool:
    """Repair one issue_type from diagnose(); True if it was fixed."""
    if issue_type in ("missing_block", "missing_claude_md"):
        from importlib.util import spec_from_file_location, module_from_spec
        install_path = os.path.join(source, "bin", "git-memory-install.py")
        if not os.path.isfile(install_path):
            return False
        spec = spec_from_file_location("install", install_path)
        if spec is None or spec.loader is None:
            return False
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
        mod._update_claude_md(target)
        return True

    elif issue_type in ("missing_manifest", "corrupt_manifest"):
        from importlib.util import spec_from_file_location, module_from_spec
        install_path = os.path.join(source, "bin", "git-memory-install.py")
        if not os.path.isfile(install_path):
            return False
        spec = spec_from_file_location("install", install_path)
        if spec is None or spec.loader is None:
            return False
        mod = module_from_spec(spec)
        spec.loader.exec_module(mod)  # type: ignore[union-attr]

        # Keep the existing manifest's mode when it is readable.
        mode = "normal"
        manifest_path = os.path.join(target, ".claude", ".unmassk", "manifest.json")
        if os.path.isfile(manifest_path):
            try:
                with open_no_follow_symlink(manifest_path, "r") as f:
                    data = json.load(f)
                mode = str(data.get("runtime_mode", "normal"))
            except (json.JSONDecodeError, OSError):
                pass

        mod._create_manifest(target, mode)
        return True

    elif issue_type == "old_install":
        # install --auto cleans up the old files.
        install_script = os.path.join(source, "bin", "git-memory-install.py")
        if os.path.isfile(install_script):
            # Explicit utf-8: the console codec (cp1252 on Windows) can break decoding.
            subprocess.run(
                [sys.executable, install_script, "--auto"],
                capture_output=True, text=True, timeout=30,
                encoding="utf-8", errors="replace",
            )
            return True
        return False

    return False


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: parse args, diagnose issues, and repair."""
    parser = argparse.ArgumentParser(description="Repair git-memory project configuration.")
    parser.add_argument("--auto", action="store_true", help="Non-interactive mode")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be fixed")
    args = parser.parse_args()
    auto = args.auto
    dry_run = args.dry_run

    source = find_source_root()
    target = find_target_root()

    print("=== git memory repair ===")
    print(f"Plugin: {source}")
    print(f"Project: {target}")
    print()

    # Diagnose
    print("Diagnosing...")
    issues = diagnose(target)

    if not issues:
        print("\nNothing to repair — all components healthy.")
        sys.exit(0)

    print(f"\nFound {len(issues)} issue(s):")
    print("─" * 40)
    for _, _, desc in issues:
        print(f"  ❌ {desc}")
    print("─" * 40)

    if dry_run:
        print("\n(dry-run mode — no changes made)")
        sys.exit(0)

    if not auto:
        try:
            answer = input("\nRepair all issues? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(2)

        if answer and answer not in ("y", "yes", "s", "si", "sí", ""):
            print("Aborted.")
            sys.exit(2)

    # Repair
    print("\nRepairing...")
    fixed = 0
    failed = 0

    for issue_type, target_name, desc in issues:
        try:
            if repair_issue(issue_type, source, target):
                print(f"  ✅ Fixed: {desc}")
                fixed += 1
            else:
                print(f"  ❌ Could not fix: {desc}")
                failed += 1
        except Exception as e:
            print(f"  ❌ Error fixing {desc}: {e}")
            failed += 1

    print(f"\nRepair complete: {fixed} fixed, {failed} failed.")

    if failed > 0:
        print("Some issues could not be fixed. Try: /plugin install unmassk-toolkit@unmassk-claude-toolkit")
        sys.exit(1)

    # Run doctor to confirm
    print("\nVerifying with doctor...")
    doctor = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git-memory-doctor.py")
    if os.path.isfile(doctor):
        subprocess.run([sys.executable, doctor], timeout=15)

    sys.exit(0)


if __name__ == "__main__":
    main()
