#!/usr/bin/env python3
"""git-memory-doctor -- health check of the plugin cache files and the project's memory setup.

Usage: git memory doctor [--json | --silent]. Exit 0 if healthy or warnings only, 1 on errors.
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from typing import Any

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import run_git, open_no_follow_symlink, verify_path_within_project
from parsing import sanitize_trailer_value
from version import VERSION
from cache_sync_check import check_repo_cache_sync
# TRANSIENT_HOOKS and HOOK_COMMAND_RE are re-exported on purpose.
from hooks_doc import TRANSIENT_HOOKS, HOOK_COMMAND_RE, hook_filenames, compare_hooks_doc  # noqa: F401


# ── Helpers ───────────────────────────────────────────────────────────────

def find_plugin_root() -> str:
    """Plugin root: the parent of this script's bin/ directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_project_root() -> str:
    """Git repo root of the cwd, or the cwd if not in a repo."""
    code, git_root = run_git(["rev-parse", "--show-toplevel"])
    if code == 0 and git_root:
        return git_root
    return os.getcwd()


# ── Checks ────────────────────────────────────────────────────────────────

def check_git_repo() -> bool:
    """Verify we're in a git repository."""
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    return code == 0


def expected_hooks(plugin_root: str) -> list[str] | None:
    """Hook filenames declared in hooks/hooks.json, or None if it cannot be read."""
    return hook_filenames(plugin_root)


def expected_skills(plugin_root: str) -> list[str] | None:
    """Skill directory names under skills/, or None if it cannot be listed."""
    skills_dir = os.path.join(plugin_root, "skills")
    try:
        entries = os.listdir(skills_dir)
    except OSError:
        return None
    return sorted(
        name for name in entries
        if not name.startswith((".", "_"))
        and os.path.isdir(os.path.join(skills_dir, name))
    )


def check_hooks(plugin_root: str, expected: list[str]) -> tuple[list[str], list[str]]:
    """Split the expected hooks into (found, missing) in the plugin cache."""
    hooks_dir = os.path.join(plugin_root, "hooks")
    found = []
    missing = []
    for hook in expected:
        path = os.path.join(hooks_dir, hook)
        if os.path.isfile(path):
            found.append(hook)
        else:
            missing.append(hook)
    return found, missing


def check_skills(plugin_root: str, expected: list[str]) -> tuple[list[str], list[str]]:
    """Split the expected skills into (found, missing SKILL.md)."""
    skills_dir = os.path.join(plugin_root, "skills")
    found = []
    missing = []
    for skill in expected:
        skill_file = os.path.join(skills_dir, skill, "SKILL.md")
        if os.path.isfile(skill_file):
            found.append(skill)
        else:
            missing.append(skill)
    return found, missing


def check_cli(plugin_root: str) -> tuple[bool, str]:
    """Check that bin/git-memory exists. Return (ok, status message)."""
    cli_path = os.path.join(plugin_root, "bin", "git-memory")
    if not os.path.isfile(cli_path):
        return False, "not found"
    return True, "ok"


def check_hooks_json(plugin_root: str) -> bool:
    """Check that hooks/hooks.json exists in the plugin cache."""
    return os.path.isfile(os.path.join(plugin_root, "hooks", "hooks.json"))


def check_claude_md(project_root: str) -> tuple[bool, str]:
    """Check CLAUDE.md for the managed block. Return (present, status message)."""
    claude_md = os.path.join(project_root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return False, "CLAUDE.md not found"
    try:
        with open_no_follow_symlink(claude_md, "r") as f:
            content = f.read()
        if "BEGIN unmassk-toolkit" in content and "END unmassk-toolkit" in content:
            return True, "managed block present"
        return False, "managed block missing"
    except OSError:
        return False, "read error"



def check_gitmem_launcher() -> tuple[str, str]:
    """Check ~/.local/bin/gitmem is installed and on PATH. Return (level, message); never an error."""
    launcher_dir = os.path.join(os.path.expanduser("~"), ".local", "bin")
    launcher_path = os.path.join(launcher_dir, "gitmem")
    if not os.path.isfile(launcher_path):
        return "warn", "not installed at ~/.local/bin/gitmem (run install to create)"

    path_dirs = [p for p in os.environ.get("PATH", "").split(os.pathsep) if p]
    in_path = any(os.path.realpath(p) == os.path.realpath(launcher_dir) for p in path_dirs)
    if in_path:
        return "ok", f"{launcher_path} (~/.local/bin is in PATH)"
    return "warn", (
        f"{launcher_path} exists but ~/.local/bin is not in PATH -- add to "
        'your ~/.zshrc: export PATH="$HOME/.local/bin:$PATH"'
    )


def check_project_memory_seed(project_root: str) -> tuple[str, str]:
    """Check the eight index files in .claude/project-memory/. Return (level, message)."""
    expected = (
        "DECISIONS.md", "MEMOS.md", "RESTRICTIONS.md", "QUESTIONS.md",
        "INCIDENTS.md", "DISCARDED.md", "BLOCKED.md", "ARCHIVED.md",
    )
    pm_dir = os.path.join(project_root, ".claude", "project-memory")
    if not os.path.isdir(pm_dir):
        return "warn", "not found (run install to seed)"
    missing = [f for f in expected if not os.path.isfile(os.path.join(pm_dir, f))]
    if missing:
        return "warn", f"{len(expected) - len(missing)}/{len(expected)} index files present -- missing: {', '.join(missing)}"
    return "ok", f"{len(expected)}/{len(expected)} index files present"


def check_project_config(project_root: str) -> tuple[str, str]:
    """Check config.json and its field types (mirrors `lib/memory/config.py::load()`). Return (level, message)."""
    config_path = os.path.join(project_root, ".claude", "project-memory", "config.json")
    if not os.path.isfile(config_path):
        return "warn", "config.json not found (run install to create)"
    try:
        with open_no_follow_symlink(config_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return "error", f"corrupt: {e}"
    if not isinstance(data, dict):
        return "error", "corrupt: expected a JSON object"
    customs_enabled = data.get("customs_enabled")
    if customs_enabled is not None and not isinstance(customs_enabled, bool):
        return "error", f"corrupt: 'customs_enabled' must be boolean, got {type(customs_enabled).__name__}"
    test_command = data.get("test_command")
    if test_command is not None and not isinstance(test_command, str):
        return "error", f"corrupt: 'test_command' must be text, got {type(test_command).__name__}"
    repo_type = data.get("repo_type")
    if repo_type is not None and not isinstance(repo_type, str):
        return "error", f"corrupt: 'repo_type' must be text, got {type(repo_type).__name__}"
    if repo_type is None:
        return "warn", "present but repo_type not set (defaults to protected 'gitflow')"
    return "ok", f"repo_type={repo_type!r}"


def check_project_zones(project_root: str) -> tuple[str, str]:
    """Check zones.json: absent, empty, or populated, with the same per-zone shape checks as `zones.load()`.

    Non-lowercase names or aliases are a warning, not an error. Returns (level, message).
    """
    zones_path = os.path.join(project_root, ".claude", "project-memory", "zones.json")
    if not os.path.isfile(zones_path):
        return "warn", "zones.json not found (run install to seed, or 'zones add' to register the first zone)"
    try:
        with open_no_follow_symlink(zones_path, "r") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        return "error", f"zones.json corrupt: {e}"
    if not isinstance(data, dict):
        return "error", "zones.json corrupt: expected a JSON object"
    not_normalized: list[str] = []
    for name, fields in data.items():
        if not isinstance(fields, dict):
            return "error", f"zones.json corrupt: zone {name!r} must be a JSON object"
        description = fields.get("description", "")
        if not isinstance(description, str):
            return "error", f"zones.json corrupt: 'description' of zone {name!r} must be text"
        aliases = fields.get("aliases", [])
        if not isinstance(aliases, list) or not all(isinstance(a, str) for a in aliases):
            return "error", f"zones.json corrupt: 'aliases' of zone {name!r} must be a list of text"
        if name != name.lower() or any(a != a.lower() for a in aliases):
            not_normalized.append(name)
    if len(data) == 0:
        return "warn", "zones.json present but no zone registered yet ('zones add' to register one)"
    if not_normalized:
        listed = ", ".join(repr(n) for n in not_normalized)
        return (
            "warn",
            f"zones.json has {len(data)} zone(s) registered, but not lowercase-normalized: "
            f"{listed} -- the system still resolves them fine (names/aliases are matched "
            "case-insensitively), but zones.json itself should be edited by hand to lowercase "
            "them (no 'zones' edit command yet)"
        )
    return "ok", f"zones.json has {len(data)} zone(s) registered"


def check_manifest(project_root: str) -> tuple[dict[str, Any] | None, str]:
    """Read .claude/.unmassk/manifest.json. Return (parsed dict or None, status message)."""
    manifest_path = os.path.join(project_root, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        return None, "not found"
    try:
        verify_path_within_project(manifest_path, project_root)
        with open_no_follow_symlink(manifest_path, "r") as f:
            data = json.load(f)
        return data, "ok"
    except (json.JSONDecodeError, OSError) as e:
        return None, f"corrupt: {e}"


# ── Report ────────────────────────────────────────────────────────────────

def run_doctor(silent: bool = False, as_json: bool = False) -> int:
    """Run every check and print the report. Return 1 if errors were found, else 0."""
    plugin_root = find_plugin_root()
    project_root = find_project_root()
    results = []
    has_errors = False
    has_warnings = False

    # 1. Git repo
    if not check_git_repo():
        results.append(("error", "Git", "not inside a git repository"))
        if as_json:
            print(json.dumps({"status": "error", "checks": [
                {"level": r[0], "component": r[1], "message": r[2]} for r in results
            ]}))
        elif not silent:
            print("Not inside a git repository.")
        return 1

    # 2. Hooks (in plugin cache), expected list derived from hooks.json
    hook_names = expected_hooks(plugin_root)
    if not hook_names:
        # None = unreadable; [] = declares nothing. Either way nothing is verified.
        has_errors = True
        reason = "hooks.json unreadable" if hook_names is None else "hooks.json declares no hooks"
        results.append(("error", "Hooks", f"cannot verify — {reason}"))
    else:
        found_hooks, missing_hooks = check_hooks(plugin_root, hook_names)
        total_hooks = len(hook_names)
        if missing_hooks:
            has_errors = True
            results.append(("error", "Hooks", f"{len(found_hooks)}/{total_hooks} in cache — missing: {', '.join(missing_hooks)}"))
        else:
            results.append(("ok", "Hooks", f"{total_hooks}/{total_hooks} in plugin cache"))

    # 3. Skills (in plugin cache), expected list derived from skills/ on disk
    skill_names = expected_skills(plugin_root)
    if not skill_names:
        has_errors = True
        reason = "skills/ unreadable" if skill_names is None else "skills/ is empty"
        results.append(("error", "Skills", f"cannot verify — {reason}"))
    else:
        found_skills, missing_skills = check_skills(plugin_root, skill_names)
        total_skills = len(skill_names)
        if missing_skills:
            has_errors = True
            results.append(("error", "Skills", f"{len(found_skills)}/{total_skills} in cache — missing SKILL.md: {', '.join(missing_skills)}"))
        else:
            results.append(("ok", "Skills", f"{total_skills}/{total_skills} in plugin cache"))

    # 4. CLI (in plugin cache)
    cli_ok, cli_msg = check_cli(plugin_root)
    if cli_ok:
        results.append(("ok", "CLI", "bin/git-memory in plugin cache"))
    else:
        has_warnings = True
        results.append(("warn", "CLI", f"bin/git-memory {cli_msg}"))

    # 5. hooks.json (in plugin cache)
    if check_hooks_json(plugin_root):
        results.append(("ok", "hooks.json", "present in plugin cache"))
    else:
        has_warnings = True
        results.append(("warn", "hooks.json", "not found in plugin cache"))

    # 5b. Working tree vs plugin cache (toolkit developers only)
    # Warn only. None = check does not apply.
    sync_drift = check_repo_cache_sync(project_root)
    if sync_drift is not None:
        if sync_drift:
            has_warnings = True
            results.append(("warn", "Repo vs cache",
                            "cache is stale, reinstall to run your edits — "
                            + "; ".join(sync_drift)))
        else:
            results.append(("ok", "Repo vs cache", "hooks/, lib/ and bin/ identical"))

    # 5c. references/hooks.md's generated hook table vs hooks.json
    # A documented hook that no longer exists is an error; an undocumented one a warning. None = does not apply.
    doc_verdict = compare_hooks_doc(plugin_root)
    if doc_verdict is not None:
        doc_level, doc_msg = doc_verdict
        if doc_level == "error":
            has_errors = True
        elif doc_level == "warn":
            has_warnings = True
        results.append((doc_level, "Hooks doc", doc_msg))

    # 6. CLAUDE.md (in project root)
    block_ok, block_msg = check_claude_md(project_root)
    if block_ok:
        results.append(("ok", "CLAUDE.md", block_msg))
    else:
        has_errors = True
        results.append(("error", "CLAUDE.md", block_msg))

    # 7. Version
    results.append(("ok", "Version", f"v{VERSION}"))

    # 8. Manifest (in project root)
    manifest, manifest_msg = check_manifest(project_root)
    if manifest:
        safe_version = sanitize_trailer_value(str(manifest.get('version', '?')))
        results.append(("ok", "Manifest", f"v{safe_version}"))
    elif manifest_msg == "not found":
        results.append(("error", "Manifest", "not found (run install to create)"))
        has_errors = True
    else:
        has_errors = True
        results.append(("error", "Manifest", manifest_msg))

    # 9. Stale hooks in project settings.json
    settings_path = os.path.join(project_root, ".claude", "settings.json")
    if os.path.isfile(settings_path):
        try:
            with open_no_follow_symlink(settings_path, "r") as f:
                proj_settings = json.load(f)
            if "hooks" in proj_settings:
                has_stale = False
                hooks_data = proj_settings["hooks"]
                if isinstance(hooks_data, dict):
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
                                    has_stale = True
                                    break
                if has_stale:
                    has_errors = True
                    results.append(("error", "Settings hooks",
                                    "stale local hooks in .claude/settings.json — run install to fix"))
                else:
                    results.append(("ok", "Settings hooks", "clean"))
        except (json.JSONDecodeError, OSError):
            pass

    # 10. gitmem PATH launcher (~/.local/bin/gitmem)
    launcher_level, launcher_msg = check_gitmem_launcher()
    if launcher_level == "warn":
        has_warnings = True
    results.append((launcher_level, "gitmem launcher", launcher_msg))

    # 11. Project memory: eight index files seeded
    pm_level, pm_msg = check_project_memory_seed(project_root)
    if pm_level == "warn":
        has_warnings = True
    results.append((pm_level, "Project memory", pm_msg))

    # 12. Project memory: config.json / repo_type
    cfg_level, cfg_msg = check_project_config(project_root)
    if cfg_level == "error":
        has_errors = True
    elif cfg_level == "warn":
        has_warnings = True
    results.append((cfg_level, "Project config", cfg_msg))

    # 13. Project memory: zones.json
    zones_level, zones_msg = check_project_zones(project_root)
    if zones_level == "error":
        has_errors = True
    elif zones_level == "warn":
        has_warnings = True
    results.append((zones_level, "Project zones", zones_msg))

    # Output
    if as_json:
        status = "error" if has_errors else ("warn" if has_warnings else "ok")
        output = {
            "status": status,
            "version": VERSION,
            "plugin_root": plugin_root,
            "project_root": project_root,
            "checks": [{"level": r[0], "component": r[1], "message": r[2]} for r in results],
        }
        print(json.dumps(output, indent=2))
    elif not silent:
        print("Memory System Status")
        print("─" * 35)
        for level, component, message in results:
            icon = {"ok": "✅", "warn": "⚠️ ", "error": "❌"}[level]
            print(f"{icon} {component}: {message}")
        print("─" * 35)

        if has_errors:
            print("Action: run 'git memory repair' to fix errors")
        elif has_warnings:
            print("Recommendation: review warnings above")
        else:
            print("All systems healthy")

    # Update manifest healthcheck timestamp
    manifest_path = os.path.join(project_root, ".claude", ".unmassk", "manifest.json")
    if os.path.isfile(manifest_path):
        try:
            verify_path_within_project(manifest_path, project_root)
            with open_no_follow_symlink(manifest_path, "r") as f:
                data = json.load(f)
            data["last_healthcheck_at"] = datetime.now().isoformat()
            with open_no_follow_symlink(manifest_path, "w", reject_hardlinks=True) as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    return 1 if has_errors else 0


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: parse args and run the doctor checks."""
    parser = argparse.ArgumentParser(description="Health check for the git-memory system.")
    parser.add_argument("--silent", action="store_true", help="Exit code only")
    parser.add_argument("--json", dest="json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()
    silent = args.silent
    as_json = args.json

    exit_code = run_doctor(silent=silent, as_json=as_json)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
