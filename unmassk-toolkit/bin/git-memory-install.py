#!/usr/bin/env python3
"""Configure git-memory for a project: CLAUDE.md managed block, project memory and manifest.

Exit codes: 0 installed, 1 error, 2 aborted by the user.
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

from git_helpers import run_git

# Re-exported: git-memory-repair.py and tests load these names from this module.
from install_inspect import (
    OLD_BIN_FILES, OLD_HOOK_FILES, OLD_LIB_FILES, OLD_SKILL_DIRS, inspect,
)
from install_apply import (
    apply_plan, _cleanup_old_install, _cleanup_stale_settings_hooks,
    _update_claude_md, _create_manifest,
)


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


# ── Phase 2: Plan ─────────────────────────────────────────────────────────

def create_plan(report: dict[str, Any], source: str, target: str,
                mode: str | None = None) -> dict[str, Any]:
    """Build the install plan from inspect()'s report: {"mode", "actions", "skipped", "repo_type"}."""
    plan: dict[str, Any] = {
        "mode": mode or report["suggested_mode"],
        "actions": [],
        "skipped": [],
    }

    if not report["is_git"]:
        plan["actions"].append(("abort", "Not a git repository"))
        return plan

    # Clean up old-style install first
    is_self = os.path.realpath(source) == os.path.realpath(target)
    if report["has_old_install"]:
        if is_self:
            # Self-install: the "old install files" are the plugin's own source.
            plan["skipped"].append(
                "Old-style install cleanup (self-install: plugin source is the project)"
            )
        else:
            plan["actions"].append(("cleanup_old", "Remove old-style install files from project root"))

    if report.get("has_stale_hooks"):
        plan["actions"].append(("cleanup_stale_hooks", "Remove stale hook entries from .claude/settings.json"))

    # CLAUDE.md managed block
    if report["has_managed_block"]:
        plan["actions"].append(("update_claude_md", "Update managed block in CLAUDE.md"))
    else:
        plan["actions"].append(("update_claude_md", "Add managed block to CLAUDE.md"))

    plan["actions"].append(("install_gitmem_launcher", "Install/refresh gitmem launcher in ~/.local/bin (PATH)"))

    plan["actions"].append(("seed_project_memory", "Seed .claude/project-memory/ index files (8 files)"))

    # repo_type is deduced from branches; an existing value in config.json is kept.
    plan["repo_type"] = report.get("deduced_repo_type", "trunk")
    plan["actions"].append((
        "write_config_json",
        f"Write/merge .claude/project-memory/config.json (repo_type deduced: {plan['repo_type']!r}, unless already set)",
    ))

    # Always last: the manifest stamps the version only after every other action succeeded.
    plan["actions"].append(("create_manifest", "Create/update .claude/.unmassk/manifest.json"))

    return plan


# ── Phase 4 & 5: Verify + Health Proof ───────────────────────────────────

def verify(target: str) -> dict[str, Any]:
    """Run git-memory-doctor.py --json; return its parsed output, or a fallback dict on failure."""
    doctor_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git-memory-doctor.py")
    if os.path.isfile(doctor_script):
        # Explicit utf-8: the console codec (cp1252 on Windows) can leave stdout as None.
        result = subprocess.run(
            [sys.executable, doctor_script, "--json"],
            capture_output=True, text=True, timeout=15,
            encoding="utf-8", errors="replace",
        )
        try:
            # TypeError covers a None stdout.
            data: dict[str, Any] = json.loads(result.stdout)
            return data
        except (json.JSONDecodeError, TypeError):
            return {"status": "error", "checks": []}
    return {"status": "unknown", "checks": []}


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: parse args and run the install pipeline."""
    parser = argparse.ArgumentParser(description="Configure git-memory for a project.")
    parser.add_argument("--auto", action="store_true", help="Non-interactive mode")
    parser.add_argument("--mode", dest="mode",
                        choices=["normal", "compatible", "read-only"],
                        default=None, help="Force install mode")
    args = parser.parse_args()
    auto = args.auto
    forced_mode = args.mode

    source = find_source_root()
    target = find_target_root()

    is_self = os.path.realpath(source) == os.path.realpath(target)

    print("=== git memory install ===")
    print(f"Plugin: {source}")
    print(f"Project: {target}")
    if is_self:
        print("(self-install: plugin source is the project)")
    print()

    # Phase 1: Inspect
    print("Phase 1: Inspecting project...")
    report = inspect(target)

    if not report["is_git"]:
        print("Error: not a git repository.", file=sys.stderr)
        sys.exit(1)

    # Phase 2: Plan
    plan = create_plan(report, source, target, forced_mode)

    print(f"\nPhase 2: Installation plan (mode: {plan['mode']})")
    print("─" * 40)
    for _, desc in plan["actions"]:
        print(f"  → {desc}")
    for desc in plan["skipped"]:
        print(f"  ⏭  {desc}")
    print("─" * 40)

    if not auto:
        try:
            answer = input("\nProceed with installation? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(2)

        if answer and answer not in ("y", "yes", "s", "si", "sí", ""):
            print("Aborted.")
            sys.exit(2)

    # Phase 3: Apply
    print("\nPhase 3: Applying...")
    errors = apply_plan(plan, source, target)

    if errors:
        print("\nErrors during installation:", file=sys.stderr)
        for err in errors:
            print(f"  ❌ {err}", file=sys.stderr)
        sys.exit(1)

    print("  Done.")

    # Phase 4: Verify
    print("\nPhase 4: Verifying...")
    doctor_result = verify(target)

    # Phase 5: Health proof
    print("\nPhase 5: Health proof")
    print("─" * 40)
    status = doctor_result.get("status", "unknown")
    checks = doctor_result.get("checks", [])

    for check in checks:
        icon = {"ok": "✅", "warn": "⚠️ ", "error": "❌"}.get(check.get("level", ""), "?")
        print(f"  {icon} {check.get('component', '?')}: {check.get('message', '?')}")

    print("─" * 40)

    if status == "ok":
        print(f"\nInstallation complete. Mode: {plan['mode']}")
    elif status == "warn":
        print(f"\nInstalled with warnings. Mode: {plan['mode']}")
    else:
        print("\nInstalled but verification found issues.")

    sys.exit(0)


if __name__ == "__main__":
    main()
