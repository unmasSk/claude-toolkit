"""
install_inspect -- Phase 1 (state detection) for bin/git-memory-install.py.

Split out of git-memory-install.py (600+ LOC, growing every round with
security guards) to keep the CLI entrypoint under the project's 500 LOC
limit. This module owns "what does the target repo currently look like" —
git repo?, CLAUDE.md managed block?, manifest?, old-style install
leftovers?, commitlint/stale-hooks signals? — with zero writes.

lib/install_apply.py (Phase 3: execution) imports OLD_BIN_FILES and
OLD_HOOK_FILES from here rather than duplicating them, since
_cleanup_old_install() needs the exact same file list inspect() already
uses to detect an old-style install. One-way dependency: install_apply.py
may import from install_inspect.py, never the reverse.
"""

import json
import os
from typing import Any

from git_helpers import run_git, open_no_follow_symlink

# Old-style install files that should be cleaned up from the project root.
# These were copied by the v1 installer but should only live in the plugin cache.
OLD_BIN_FILES = [
    "bin/git-memory", "bin/git-memory-gc.py", "bin/git-memory-dashboard.py",
    "bin/git-memory-doctor.py", "bin/git-memory-install.py",
    "bin/git-memory-repair.py", "bin/git-memory-uninstall.py",
    "bin/git-memory-bootstrap.py", "bin/git-memory-upgrade.py",
]

OLD_HOOK_FILES = [
    "hooks/pre-validate-commit-trailers.py",
    "hooks/post-validate-commit-trailers.py",
    "hooks/precompact-snapshot.py",
    "hooks/stop-dod-check.py",
    "hooks/session-start-boot.py",
    "hooks/user-prompt-memory-check.py",
    "hooks/hooks.json",
]

OLD_LIB_FILES = [
    "lib/__init__.py", "lib/constants.py", "lib/git_helpers.py",
    "lib/parsing.py", "lib/colors.py",
]

OLD_SKILL_DIRS = [
    "skills/git-memory",
    "skills/git-memory-protocol",
    "skills/git-memory-lifecycle",
    "skills/git-memory-recovery",
]  # Keep old dirs listed for cleanup during upgrades


def inspect(target: str) -> dict[str, Any]:
    """Inspect the target repository and detect its current state.

    Checks for git repo, CLAUDE.md managed block, manifest, and old-style
    install files.

    Args:
        target: Path to the target repository root.

    Returns:
        Dict with boolean flags and a suggested install mode.
    """
    report: dict[str, Any] = {
        "is_git": False,
        "has_claude_md": False,
        "has_managed_block": False,
        "has_manifest": False,
        "has_old_install": False,
        "has_commitlint": False,
        "suggested_mode": "normal",
    }

    # Git repo?
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    report["is_git"] = code == 0

    if not report["is_git"]:
        return report

    # CLAUDE.md
    # barrido finding: never follow a symlink planted at CLAUDE.md — treat
    # it exactly like "no CLAUDE.md present" rather than trusting whatever
    # external file it points at.
    claude_md = os.path.join(target, "CLAUDE.md")
    if os.path.isfile(claude_md):
        try:
            with open_no_follow_symlink(claude_md, "r") as f:
                report["has_managed_block"] = "BEGIN unmassk-toolkit" in f.read()
            report["has_claude_md"] = True
        except OSError:
            pass

    # Manifest
    manifest_path = os.path.join(target, ".claude", ".unmassk", "manifest.json")
    report["has_manifest"] = os.path.isfile(manifest_path)

    # Detect old-style install (files copied to project root).
    # Skip if target IS the plugin source repo (has .claude-plugin/plugin.json
    # with our plugin name) — those files are source code, not old install copies.
    is_plugin_source = False
    plugin_json_path = os.path.join(target, ".claude-plugin", "plugin.json")
    if os.path.isfile(plugin_json_path):
        try:
            # 7th audit round (BUG X): never follow a symlink planted at
            # .claude-plugin/plugin.json.
            with open_no_follow_symlink(plugin_json_path, "r") as f:
                pj = json.load(f)
            if pj.get("name") == "unmassk-toolkit":
                is_plugin_source = True
        except (json.JSONDecodeError, OSError):
            pass

    if not is_plugin_source:
        for f in OLD_BIN_FILES + OLD_HOOK_FILES:
            if os.path.isfile(os.path.join(target, f)):
                report["has_old_install"] = True
                break
        if not report["has_old_install"]:
            if os.path.isdir(os.path.join(target, ".claude-plugin")):
                report["has_old_install"] = True

    # Commitlint / CI that might reject trailers
    for ci_file in [".commitlintrc.json", ".commitlintrc.yml",
                    "commitlint.config.js", "commitlint.config.ts"]:
        if os.path.isfile(os.path.join(target, ci_file)):
            report["has_commitlint"] = True
            report["suggested_mode"] = "compatible"
            break

    # Check package.json for commitlint
    pkg_path = os.path.join(target, "package.json")
    if os.path.isfile(pkg_path):
        try:
            # 7th audit round (BUG X): never follow a symlink planted at
            # package.json (commitlint check).
            with open_no_follow_symlink(pkg_path, "r") as f:
                pkg = json.load(f)
            if "commitlint" in pkg.get("devDependencies", {}):
                report["has_commitlint"] = True
                report["suggested_mode"] = "compatible"
        except (json.JSONDecodeError, OSError):
            pass

    # Detect stale hook entries in project .claude/settings.json
    project_settings_path = os.path.join(target, ".claude", "settings.json")
    if os.path.isfile(project_settings_path):
        try:
            # SEC-MED-NEW-13: never follow a symlink planted at settings.json.
            with open_no_follow_symlink(project_settings_path, "r") as f:
                project_settings = json.load(f)
            hooks_data = project_settings.get("hooks", {})
            if hooks_data and isinstance(hooks_data, dict):
                for event_hooks in hooks_data.values():
                    if not isinstance(event_hooks, list):
                        continue
                    for hook_group in event_hooks:
                        hook_list = hook_group.get("hooks", []) if isinstance(hook_group, dict) else []
                        for hook in hook_list:
                            cmd = hook.get("command", "") if isinstance(hook, dict) else ""
                            if cmd and "${CLAUDE_PLUGIN_ROOT}" not in cmd and (
                                "hooks/" in cmd or "bin/" in cmd
                            ):
                                report["has_stale_hooks"] = True
                                break
        except (json.JSONDecodeError, OSError):
            pass

    return report
