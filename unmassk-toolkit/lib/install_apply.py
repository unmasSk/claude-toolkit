"""
install_apply -- Phase 3 (execution) for bin/git-memory-install.py.

Split out of git-memory-install.py (600+ LOC, growing every round with
security guards) to keep the CLI entrypoint under the project's 500 LOC
limit. This module owns "actually change something on disk": cleaning up
old-style install remnants, removing stale hook entries, writing the
CLAUDE.md managed block, and creating the manifest.

Imports OLD_BIN_FILES/OLD_HOOK_FILES/OLD_LIB_FILES/OLD_SKILL_DIRS from
lib/install_inspect.py rather than duplicating them — inspect() and
_cleanup_old_install() must agree on exactly which files count as an
old-style install. One-way dependency: this module may import from
install_inspect.py, never the reverse.
"""

import json
import os
import shutil
from datetime import datetime
from typing import Any

from git_helpers import ensure_gitignore, open_no_follow_symlink, verify_path_within_project
from managed_blocks import BLOCKS, upsert_managed_blocks
from version import VERSION

from install_inspect import OLD_BIN_FILES, OLD_HOOK_FILES, OLD_LIB_FILES, OLD_SKILL_DIRS


def apply_plan(plan: dict[str, Any], source: str, target: str) -> list[str]:
    """Execute the installation plan.

    Args:
        plan: Output from create_plan().
        source: Plugin source root directory.
        target: Target repository root directory.

    Returns:
        List of error messages. Empty list means all actions succeeded.
    """
    errors = []

    for action, description in plan["actions"]:
        try:
            if action == "abort":
                return [description]
            elif action == "cleanup_old":
                _cleanup_old_install(target, source)
            elif action == "cleanup_stale_hooks":
                _cleanup_stale_settings_hooks(target)
            elif action == "update_claude_md":
                _update_claude_md(target)
            elif action == "create_manifest":
                _create_manifest(target, plan["mode"])
        except Exception as e:
            errors.append(f"{action}: {e}")

    return errors


def _cleanup_old_install(target: str, source: str) -> None:
    """Remove files from old-style installs that copied to project root.

    Only removes files we recognize as git-memory managed files.
    Never removes user files or directories that contain non-managed files.
    """
    is_self = os.path.realpath(source) == os.path.realpath(target)
    if is_self:
        return

    removed = []

    # Remove individual managed files
    for f in OLD_BIN_FILES + OLD_HOOK_FILES + OLD_LIB_FILES:
        path = os.path.join(target, f)
        if os.path.isfile(path) or os.path.islink(path):
            # BUG AH / SEC-CRIT-002 sibling: "bin"/"hooks"/"lib" at the
            # project root may themselves be a symlink to an external,
            # pre-existing directory that happens to contain a real file
            # matching one of these fixed names — verify the resolved path
            # stays inside target before unlinking, mirroring the guard the
            # ".claude/hooks"/".claude/skills" rmtree section below already has.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            os.unlink(path)
            removed.append(f)

    # Remove old skill directories
    for d in OLD_SKILL_DIRS:
        path = os.path.join(target, d)
        if os.path.isdir(path) and not os.path.islink(path):
            # Same guard class as the fixed-name file loop above: an
            # intermediate component of `d` (e.g. "skills") may itself be a
            # symlink to an external, pre-existing directory — verify the
            # resolved path stays inside target before rmtree.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            shutil.rmtree(path)
            removed.append(d + "/")
        elif os.path.islink(path):
            # SEC-LOW-001: sibling of the rmtree branch above — an
            # intermediate component of `d` can equally be a symlink when
            # `path` itself resolves to a symlink; same guard, same reason.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            os.unlink(path)
            removed.append(d)

    # Remove old-style plugin.json at repo root (NOT .claude-plugin/ which may contain marketplace.json)
    old_plugin_json = os.path.join(target, "plugin.json")
    if os.path.isfile(old_plugin_json):
        os.remove(old_plugin_json)
        removed.append("plugin.json")

    # Remove old .claude/hooks and .claude/skills symlink directories
    for subdir in ["hooks", "skills"]:
        path = os.path.join(target, ".claude", subdir)
        if os.path.isdir(path):
            # SEC-CRIT-002: .claude may be a symlink to an external,
            # pre-existing directory (old-install shape reproduced there by
            # coincidence) — verify the resolved path stays inside target
            # before rmtree, or this destroys an unrelated directory outside
            # the project.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            # Only remove if it contains symlinks (our old install pattern)
            entries = os.listdir(path)
            all_symlinks = all(os.path.islink(os.path.join(path, e)) for e in entries) if entries else True
            if all_symlinks:
                shutil.rmtree(path)
                removed.append(f".claude/{subdir}/")

    # Clean up __pycache__ left by our old scripts, then try to remove empty dirs
    for d in ["bin", "hooks", "skills", "lib"]:
        path = os.path.join(target, d)
        if os.path.isdir(path):
            # BUG AI: same symlinked-parent risk as the fixed-name unlink
            # loop above, but larger blast radius — shutil.rmtree() on
            # __pycache__ deletes a whole external subtree, not one file.
            try:
                verify_path_within_project(path, target)
            except OSError:
                continue
            pycache = os.path.join(path, "__pycache__")
            if os.path.isdir(pycache):
                shutil.rmtree(pycache)
            try:
                os.rmdir(path)  # Only succeeds if empty
            except OSError:
                pass

    if removed:
        print(f"  Cleaned {len(removed)} old-style install files/directories")


def _cleanup_stale_settings_hooks(target: str) -> None:
    """Remove stale hook entries from the project's .claude/settings.json.

    When migrating from old-style installs, the project settings may contain
    hook commands that reference local paths (e.g. python3 hooks/...) instead
    of using ${CLAUDE_PLUGIN_ROOT}. Since the plugin now provides hooks via
    hooks.json, these entries are stale and should be removed.
    """
    settings_path = os.path.join(target, ".claude", "settings.json")

    # BUG Y / SEC-CRIT-NEW: if .claude itself is a symlink pointing outside
    # the repo (not just settings.json — the parent directory), this must
    # be treated as "settings.json is unsafe to touch", never silently
    # read/modified through the symlinked directory. Raises UnsafePathError
    # (subclass of OSError), caught by apply_plan()'s existing
    # `except Exception` around this action — fails the install action
    # instead of touching anything outside the repo.
    verify_path_within_project(settings_path, target)

    if not os.path.isfile(settings_path):
        return

    try:
        # SEC-MED-NEW-13: never follow a symlink planted at settings.json —
        # neither the read nor the write-back should trust/touch whatever
        # external file it points at.
        with open_no_follow_symlink(settings_path, "r") as f:
            settings = json.load(f)
    except (json.JSONDecodeError, OSError):
        return

    if "hooks" not in settings:
        return

    del settings["hooks"]

    with open_no_follow_symlink(settings_path, "w") as f:
        json.dump(settings, f, indent=2)
        f.write("\n")

    print("  Removed stale hook entries from .claude/settings.json")


def _update_claude_md(target: str) -> None:
    """Add or update all 5 managed blocks in CLAUDE.md."""
    claude_md = os.path.join(target, "CLAUDE.md")

    if os.path.isfile(claude_md):
        try:
            # 7th audit round (BUG U): never follow a symlink planted at
            # CLAUDE.md for this read either — the write below is already
            # guarded, but the read must fail closed to "file absent" too.
            with open_no_follow_symlink(claude_md, "r") as f:
                content = f.read()
        except OSError:
            content = "# CLAUDE.md\n\n"
    else:
        content = "# CLAUDE.md\n\n"

    new_content, _ = upsert_managed_blocks(content)

    # SEC-CRIT-NEW-09: never follow a symlink planted at CLAUDE.md — refuse
    # to write through to whatever external file it points at. The caller
    # (apply_plan) already wraps this action in try/except, so raising here
    # is reported as an error rather than crashing the whole install.
    with open_no_follow_symlink(claude_md, "w") as f:
        f.write(new_content)


def _create_manifest(target: str, mode: str) -> None:
    """Create .claude/.unmassk/manifest.json with install metadata."""
    claude_dir = os.path.join(target, ".claude")
    # BUG Y / SEC-CRIT-NEW: os.makedirs() silently follows a directory
    # symlink at .claude (or .claude/.unmassk) that resolves to a real,
    # existing directory outside the repo — every file-level
    # open_no_follow_symlink() guard below is moot if the write lands
    # inside that external directory instead. Verify BEFORE creating
    # anything. Raises UnsafePathError (OSError subclass); apply_plan()'s
    # `except Exception` around this action (and repair.py's per-issue
    # try/except) already fail the calling action closed on this.
    verify_path_within_project(claude_dir, target)
    os.makedirs(claude_dir, exist_ok=True)

    manifest = {
        "version": VERSION,
        "installed_at": datetime.now().isoformat(),
        "runtime_mode": mode,
        "managed_blocks": [
            {
                "file": "CLAUDE.md",
                "begin": b["begin"].replace("<!-- ", "").split(" (")[0].split(" -->")[0],
                "end": b["end"].replace("<!-- ", "").replace(" -->", ""),
            }
            for b in BLOCKS
        ],
        "hook_registrations": [
            "PreToolUse", "PostToolUse", "Stop",
            "PreCompact", "SessionStart", "UserPromptSubmit",
        ],
        "last_healthcheck_at": datetime.now().isoformat(),
    }

    unmassk_dir = os.path.join(claude_dir, ".unmassk")
    # Defense in depth: .unmassk itself could independently be a symlink
    # escaping the repo even when .claude (just verified above) is not.
    verify_path_within_project(unmassk_dir, target)
    os.makedirs(unmassk_dir, exist_ok=True)
    manifest_path = os.path.join(unmassk_dir, "manifest.json")
    # SEC-HIGH-NEW-03 (Argus): symlink-safe write, matching
    # lib/boot_memory.py's existing open_no_follow_symlink() pattern — a
    # pre-planted symlink at this fixed path must not be silently followed
    # and used to overwrite an arbitrary file outside the repo.
    # reject_hardlinks=True (issue #53, decision 51a3c44): manifest.json is
    # toolkit-generated-only, never a legitimate user file, so a hard link
    # here can only be an attack.
    with open_no_follow_symlink(manifest_path, "w", reject_hardlinks=True) as f:
        json.dump(manifest, f, indent=2)

    ensure_gitignore(target)
