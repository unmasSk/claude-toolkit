#!/usr/bin/env python3
"""
git-memory-doctor -- Health check for the git-memory system.

Checks plugin files (in cache), CLAUDE.md managed block, manifest, and
version.

The plugin runs from the plugin cache. This script checks both:
- Plugin files: hooks, skills, bin, lib (at the plugin root / cache)
- Project files: CLAUDE.md managed block, manifest (at the git repo root)

Usage:
  git memory doctor              # Full diagnostic
  git memory doctor --json       # Machine-readable JSON output
  git memory doctor --silent     # Exit code only (0=healthy, 1=issues)

Exit codes:
  0: All checks pass (or warnings only)
  1: Errors found (broken components)
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
# TRANSIENT_HOOKS and HOOK_COMMAND_RE are re-exported through this import on
# purpose: hooks.json is parsed in exactly one place (lib/hooks_doc.py), which
# both this health check and the SKILL.md generator read, so the doctor and the
# documentation can never disagree about what is declared.
from hooks_doc import TRANSIENT_HOOKS, HOOK_COMMAND_RE, hook_filenames, compare_hooks_doc  # noqa: F401


# ── Config ────────────────────────────────────────────────────────────────

# Hooks and skills are DERIVED, never listed by hand. A hand-written list
# drifts the moment a hook is added and nobody remembers to update it here:
# it sat at 5 entries while hooks.json declared 12, so the doctor reported
# "5/5 in plugin cache" in green over 7 hooks it never looked at. A derived
# list cannot desynchronise from its own source.

# ── Helpers ───────────────────────────────────────────────────────────────

def find_plugin_root() -> str:
    """Find the plugin root (where this script lives in the cache).

    Returns:
        Absolute path to the plugin root directory.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_project_root() -> str:
    """Find the project root (git repo root of cwd).

    Returns:
        Absolute path to the project root, or cwd if not in a git repo.
    """
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
    """Derive the hook filenames the install is expected to ship.

    Source of truth is hooks/hooks.json -- the same file Claude Code reads to
    decide what to run -- so this list is exactly as long as the set of hooks
    actually declared. Transient probes (TRANSIENT_HOOKS) are excluded.

    The parse itself lives in lib/hooks_doc.py, shared with the generator of
    SKILL.md's hook table; two parsers of the same file would be two chances
    to disagree about it.

    Returns:
        Sorted list of hook filenames, or None if hooks.json is missing,
        unreadable or not valid JSON. None means "cannot verify" and must be
        reported as such, never collapsed into an empty expectation that
        would trivially pass.
    """
    return hook_filenames(plugin_root)


def expected_skills(plugin_root: str) -> list[str] | None:
    """Derive the skill names the install is expected to ship.

    Source of truth is the skills/ directory itself: every directory shipped
    there is a skill and must carry a SKILL.md. Hand-listing three of them
    left the other seven unchecked.

    Returns:
        Sorted list of skill directory names, or None if skills/ cannot be
        listed at all (reported as "cannot verify", not as "none expected").
    """
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
    """Check that all expected hook files exist in the plugin cache.

    Returns:
        Tuple of (found hook names, missing hook names).
    """
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
    """Check that all expected skill directories contain a SKILL.md file.

    Returns:
        Tuple of (found skill names, missing skill names).
    """
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
    """Check that bin/git-memory exists in the plugin cache.

    Returns:
        Tuple of (ok, status_message).
    """
    cli_path = os.path.join(plugin_root, "bin", "git-memory")
    if not os.path.isfile(cli_path):
        return False, "not found"
    return True, "ok"


def check_hooks_json(plugin_root: str) -> bool:
    """Check that hooks/hooks.json exists in the plugin cache."""
    return os.path.isfile(os.path.join(plugin_root, "hooks", "hooks.json"))


def check_claude_md(project_root: str) -> tuple[bool, str]:
    """Check if CLAUDE.md exists and contains the managed block.

    Returns:
        Tuple of (block_present, status message).
    """
    claude_md = os.path.join(project_root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return False, "CLAUDE.md not found"
    try:
        # Never follow a symlink planted at CLAUDE.md — treat it exactly
        # like a read error, never trust the external file's content as
        # the real managed block.
        with open_no_follow_symlink(claude_md, "r") as f:
            content = f.read()
        if "BEGIN unmassk-toolkit" in content and "END unmassk-toolkit" in content:
            return True, "managed block present"
        return False, "managed block missing"
    except OSError:
        return False, "read error"



def check_gitmem_launcher() -> tuple[str, str]:
    """Check ~/.local/bin/gitmem: installed, and whether ~/.local/bin is
    on PATH -- the two failure modes a dead/unreachable launcher has
    [encargo: "Fase 5... tiene que probar cada cosa nueva con su
    ✅/⚠️/❌: el lanzador del PATH (y si el PATH lo ve o no)"].

    Never "error": a missing or unreachable launcher means `gitmem` still
    works via its full cache path, it is only less convenient -- same
    severity class as the existing CLI/hooks.json checks below, which are
    warnings, not errors.

    Returns:
        Tuple of (level, message).
    """
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
    """Check that `.claude/project-memory/`'s eight index files exist
    [encargo: "Fase 5... los ocho indices"]. Expected list is the same
    INDEX_FILES tuple lib/memory/vocabulary.py declares and
    lib/memory/indexes.py::seed() writes -- read directly from disk here
    (a fixed literal, not an import) to keep this check independent of
    lib/memory/'s own import chain, same reasoning check_hooks()/
    check_skills() above already apply to their own expected lists.

    Returns:
        Tuple of (level, message).
    """
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
    """Check `.claude/project-memory/config.json` [encargo: "Fase 5...
    config.json con el tipo deducido"]. A corrupt file is reported as an
    error, not silently skipped -- same fail-loud contract config.py's
    own load() already enforces for every real reader of this file; the
    doctor must not be the one place that quietly looks away from it.

    Deliberate exception to the no-import-lib/memory pattern, same
    reasoning `check_project_zones()` already states for its own file:
    this function replicates, locally and without importing
    `lib/memory/config.py::load()`, the same per-field type contract
    that function enforces (`customs_enabled` must be boolean if
    present; `test_command` must be text if present; `repo_type` must
    be text if present) -- `config.json` with valid top-level JSON but
    a mistyped field (e.g. `{"customs_enabled": "true"}`) passes
    `json.load` and `isinstance(data, dict)` without a problem, yet
    `config.load()` rejects it with `ValueError` and every real reader
    of this file (the customs hook among them) never even gets to run.
    Reporting that state as "ok" here would be the doctor looking away
    from a failure its own real consumer already treats as fatal
    [hallazgo Moriarty T1, 2026-08-06].

    Returns:
        Tuple of (level, message).
    """
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
    """Check `.claude/project-memory/zones.json` -- three real states:
    absent, present-but-empty, present-with-at-least-one-zone [encargo
    2026-08-06: "un install missing zones.json passes every one of its
    checks in green without a word about it" -- `grep -in "zones"
    bin/git-memory-doctor.py` returned zero matches before this check].
    Mirrors the same three-state shape `check_project_memory_seed()`
    already applies to the eight index files, and
    `lib/memory/health.py::memory_mounted()`'s Aviso B for this same
    file.

    Reads the file directly (no import of `lib/memory/`), same
    reasoning `check_project_memory_seed()`/`check_project_config()`
    already apply to their own expected values: this doctor stays
    independent of `lib/memory/`'s own import chain (`health.py` alone
    pulls in `ids`, `indexes`, `notes`, `query`, `rules`, `zones`,
    `health_plans`, `model`, `vocabulary`).

    A corrupt file is reported as an error, same fail-loud contract
    `check_project_config()` already enforces for its own JSON file. A
    populated zones.json is reported "ok", never as a problem.

    Deliberate exception to the no-import-lib/memory pattern stated
    above: this function also replicates, locally and without importing
    `lib/memory/zones.py::load()`, the same three per-zone shape checks
    that function enforces (each zone value must be an object; its
    `description` must be text if present; its `aliases` must be a list
    of text if present) -- `zones.json` with valid top-level JSON but an
    invalid per-zone shape (e.g. `{"billing": "oops"}`) passes
    `json.load` and `isinstance(data, dict)` without a problem, yet
    `zones_lib.load()` rejects it with `ValueError` and the customs hook
    blocks the commit on it. Reporting that state as "ok" here would be
    the doctor looking away from a failure its own real consumer
    already treats as fatal.

    Zone names/aliases are lowercased everywhere since 2026-08-07
    [`lib/memory/zones.py::normalize()`] -- `load()` normalizes on
    READ too, so a `zones.json` written before that order (a zone
    persisted as "Boot", say) still resolves fine in production; it is
    not corrupt. Reporting it as "error" here, or silently as "ok",
    would both be wrong against what the real system does with it: an
    "error" contradicts a file the customs hook and every real reader
    accept without complaint, and a silent "ok" hides a fact the owner
    asked to see (stale casing left over from before the fix, or
    brought in from another machine). So this check reports a THIRD
    thing for this case -- "warn", naming which zone(s) are not
    normalized and how to clean them up by hand (there is no `zones`
    edit command yet, per `bin/memory/zones.py::_cmd_add`'s own rebound
    message for an existing zone).

    This also means duplicating `zones.normalize()` itself, inline as
    `name == name.lower()` below, instead of importing it from
    `lib/memory/zones.py` -- same trade this function already makes for
    the three shape checks above, extended to the one-line rule too:
    importing `zones.py` for a single `.lower()` would still pull in
    `model.Zone`, `difflib`, `tempfile`, and the `add()` file-lock
    machinery, exactly the import chain this function's independence is
    for. `normalize()` is a plain `.lower()` today and nothing else --
    if it ever grows (its own docstring floats trimming whitespace as a
    future possibility), this duplicate needs the same change by hand
    or this check silently drifts from what `zones.py` actually
    resolves. Do not "unify" this by importing `zones.py` without
    re-reading that docstring first.

    Returns:
        Tuple of (level, message).
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
    """Check if .claude/.unmassk/manifest.json exists and is valid JSON.

    Returns:
        Tuple of (parsed manifest dict or None, status message).
    """
    manifest_path = os.path.join(project_root, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        return None, "not found"
    try:
        # .claude may be a symlink to an external directory that already
        # contains a real (non-symlink) manifest.json — the
        # open_no_follow_symlink() guard below only protects against
        # manifest.json ITSELF being a symlink, not a symlinked parent
        # (.claude). Verify the resolved path stays inside project_root
        # BEFORE reading, so an external manifest's fields (e.g. "version")
        # are never read and therefore never leaked into --json output.
        verify_path_within_project(manifest_path, project_root)
        # Never follow a symlink planted at the manifest path — treat it
        # exactly like "no manifest present", never read or trust the
        # target file's content as a real manifest.
        with open_no_follow_symlink(manifest_path, "r") as f:
            data = json.load(f)
        return data, "ok"
    except (json.JSONDecodeError, OSError) as e:
        return None, f"corrupt: {e}"


# ── Report ────────────────────────────────────────────────────────────────

def run_doctor(silent: bool = False, as_json: bool = False) -> int:
    """Run all health checks and produce a diagnostic report.

    Args:
        silent: If True, suppress all output (exit code only).
        as_json: If True, output machine-readable JSON.

    Returns:
        Exit code: 0 if healthy (or warnings only), 1 if errors found.
    """
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
        # None = hooks.json unreadable; [] = readable but declares nothing.
        # Either way nothing is being verified, and saying so out loud is the
        # whole point — a silent "0/0 ✅" is the failure this replaced.
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
    # Every check above looks at the cache, which is what Claude Code
    # actually runs — so they all stay green while an edit in the repo goes
    # unexecuted. Warn, never error: a stale cache costs a reinstall, it does
    # not corrupt anything. None = check does not apply, stay silent.
    sync_drift = check_repo_cache_sync(project_root)
    if sync_drift is not None:
        if sync_drift:
            has_warnings = True
            results.append(("warn", "Repo vs cache",
                            "cache is stale, reinstall to run your edits — "
                            + "; ".join(sync_drift)))
        else:
            results.append(("ok", "Repo vs cache", "hooks/, lib/ and bin/ identical"))

    # 5c. SKILL.md's generated hook table vs hooks.json
    # unmassk-memory is loaded every session, so a hook it describes that
    # no longer exists is not a stale doc — it is Claude asserting a falsehood
    # to the user. That direction is an error; a hook declared but not yet
    # documented only under-informs, so it is a warning. None = does not apply
    # (already covered by the Hooks or Skills check above).
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
        # Sanitize the manifest's untrusted "version" field before
        # embedding it in any printed (non-JSON) report line.
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
            # Never follow a symlink planted at settings.json.
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
            # .claude may be a symlink to an external directory that
            # already contains a real (non-symlink) manifest.json — the
            # O_NOFOLLOW guard below only protects against manifest.json
            # itself being a symlink, not a symlinked parent. Verify the
            # resolved path stays inside project_root before touching it.
            verify_path_within_project(manifest_path, project_root)
            # Never follow a symlink planted at the manifest path — the
            # O_NOFOLLOW guard makes both the read and the write-back
            # atomically refuse to traverse it, so a victim file outside
            # the repo is never read from or written to.
            # reject_hardlinks=True is intentionally NOT passed on this
            # read: `data` is used for nothing except being reserialized
            # and written straight back to this same manifest_path a few
            # lines below, and that write already carries
            # reject_hardlinks=True + O_NOFOLLOW. If manifest_path is a
            # hard link, the write raises and the surrounding
            # `except Exception: pass` discards `data` without ever
            # persisting or otherwise exposing it — so the write is the
            # real enforcement point here, and checking on the read too
            # would be redundant. Contrast with
            # lib/boot_glossary_cache.py:_read_glossary_cache(), whose
            # read result is returned straight to the caller and trusted
            # with NO paired write on a cache hit — there, the read itself
            # must be the enforcement point, which is why it DOES pass
            # reject_hardlinks=True.
            with open_no_follow_symlink(manifest_path, "r") as f:
                data = json.load(f)
            data["last_healthcheck_at"] = datetime.now().isoformat()
            # reject_hardlinks=True (issue #53, decision 51a3c44): manifest.json
            # is toolkit-generated-only, never a legitimate user file, so a
            # hard link here can only be an attack.
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
