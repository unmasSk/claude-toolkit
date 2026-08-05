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
    # unmassk-gitmemory is loaded every session, so a hook it describes that
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
