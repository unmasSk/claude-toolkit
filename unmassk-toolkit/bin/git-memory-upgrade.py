#!/usr/bin/env python3
"""
git-memory-upgrade -- Safe upgrade for the git-memory system.

Since the plugin runs from the cache (~/.claude/plugins/cache/), "upgrade"
means: update the CLAUDE.md managed block and manifest at the project root,
and clean up any old-style install files. The plugin itself is updated by
`/plugin install`.

Usage:
  git memory upgrade              # Interactive: shows changes, asks for confirmation
  git memory upgrade --auto       # Non-interactive
  git memory upgrade --dry-run    # Only shows what would change
  git memory upgrade --check      # Only checks if an upgrade is available
  git memory upgrade --json       # JSON output (for Claude consumption)

Exit codes:
  0: Upgrade successful (or nothing to upgrade)
  1: Error
  2: Aborted by user
"""

import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from typing import Any

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import run_git, open_no_follow_symlink, verify_path_within_project, UnsafePathError
from managed_blocks import BLOCKS, all_blocks_present, any_block_outdated
from parsing import sanitize_trailer_value
from version import VERSION


# ── Config ────────────────────────────────────────────────────────────────


# ── Helpers ───────────────────────────────────────────────────────────────

def find_source_root() -> str:
    """Find the git-memory plugin source root."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def find_target_root() -> str:
    """Find the target repo root."""
    code, output = run_git(["rev-parse", "--show-toplevel"])
    if code == 0:
        return output
    return os.getcwd()


# ── Read current state ────────────────────────────────────────────────────

def read_installed_manifest(target: str) -> dict[str, Any] | None:
    """Read the manifest from the current installation.

    Returns:
        Parsed manifest dict, or None if missing or corrupt.
    """
    manifest_path = os.path.join(target, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        # Fallback: check legacy location (pre-v3.8)
        manifest_path = os.path.join(target, ".claude", "git-memory-manifest.json")
        if not os.path.isfile(manifest_path):
            return None
    try:
        # SEC-LOW-NEW-05: never follow a symlink planted at the manifest
        # path — treat it exactly like "no installation to upgrade", never
        # read the target file's content as if it were a real manifest.
        with open_no_follow_symlink(manifest_path, "r") as f:
            data: dict[str, Any] = json.load(f)
            return data
    except (json.JSONDecodeError, OSError):
        return None


# ── Comparison ────────────────────────────────────────────────────────────

def check_upgrade_needed(source: str, target: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Check what needs upgrading at the project level.

    Returns:
        Dict with "needs_update", "reasons", and version info.
    """
    # SEC-MED-NEW-08: the manifest's "version" field is untrusted content —
    # sanitize once here so every downstream consumer (JSON output and every
    # non-JSON print site in main()) gets the safe value, never the raw one.
    raw_installed_version = manifest.get("version", "unknown")
    safe_installed_version = sanitize_trailer_value(str(raw_installed_version))
    result: dict[str, Any] = {
        "needs_update": False,
        "installed_version": safe_installed_version,
        "available_version": VERSION,
        "reasons": [],
        "has_old_install": False,
    }

    # Version mismatch (compared against the raw value — sanitization must
    # never change whether an upgrade is considered needed)
    if raw_installed_version != VERSION:
        result["needs_update"] = True
        result["reasons"].append(f"Version mismatch: {safe_installed_version} → {VERSION}")

    # CLAUDE.md managed blocks outdated or missing
    # barrido finding: never follow a symlink planted at CLAUDE.md — treat
    # it exactly like "CLAUDE.md missing" rather than trusting whatever
    # external file it points at as a real, up-to-date install.
    claude_md = os.path.join(target, "CLAUDE.md")
    claude_md_content = None
    if os.path.isfile(claude_md):
        try:
            with open_no_follow_symlink(claude_md, "r") as f:
                claude_md_content = f.read()
        except OSError:
            claude_md_content = None

    if claude_md_content is not None:
        if not all_blocks_present(claude_md_content):
            result["needs_update"] = True
            result["reasons"].append("CLAUDE.md managed blocks missing (one or more)")
        elif any_block_outdated(claude_md_content):
            result["needs_update"] = True
            result["reasons"].append("CLAUDE.md managed block content outdated")
    else:
        result["needs_update"] = True
        result["reasons"].append("CLAUDE.md missing")

    # Old-style install files at project root
    install_mod = _load_install_module()
    for f in install_mod.OLD_BIN_FILES + install_mod.OLD_HOOK_FILES:
        if os.path.isfile(os.path.join(target, f)):
            result["needs_update"] = True
            result["has_old_install"] = True
            result["reasons"].append("Old-style install files at project root")
            break
    if not result["has_old_install"]:
        if os.path.isdir(os.path.join(target, ".claude-plugin")):
            result["needs_update"] = True
            result["has_old_install"] = True
            result["reasons"].append("Old .claude-plugin/ directory at project root")

    return result


# ── Backup ────────────────────────────────────────────────────────────────

def create_backup(target: str, manifest: dict[str, Any]) -> str:
    """Create a timestamped backup of the current manifest before upgrading.

    Returns:
        Path to the backup file.
    """
    claude_dir = os.path.join(target, ".claude")
    backup_dir = os.path.join(claude_dir, "backups")
    # BUG Y / SEC-CRIT-NEW variant: same os.makedirs()-follows-a-directory-
    # symlink-at-.claude gap as _create_manifest()/apply_upgrade() above,
    # for the backups directory. verify_path_within_project() raises
    # UnsafePathError, which subclasses OSError (git_helpers.py:24) — so it
    # is caught by the SAME `except OSError` in main() that also catches
    # the write below (reject_hardlinks=True, issue #53, decision 51a3c44).
    # Both failure modes share one message-then-clean-degrade path — see
    # main()'s backup step.
    verify_path_within_project(backup_dir, target)
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    version = manifest.get("version", "unknown")
    # SEC-HIGH-NEW-07: the manifest's "version" field is untrusted content —
    # embedding it raw in a filename allows path separators (/, \) to
    # introduce extra path segments, escaping backup_dir via a pre-planted
    # placeholder directory (same "attacker controls the whole repo" model
    # as the manifest-write symlink findings). Strip any path separator
    # before using it in the filename — the value is never used as a
    # standalone path component, so this is sufficient to keep the result
    # inside backup_dir regardless of content. Also run it through the
    # canonical sanitizer (SEC-MED-NEW-08) since backup_path itself is
    # later printed to the terminal — a raw control/ESC byte embedded in
    # the filename would otherwise leak through that print, not just
    # through the manifest's own "version" field.
    safe_version = re.sub(r"[\\/]+", "_", sanitize_trailer_value(str(version)))
    backup_name = f"manifest-v{safe_version}-{timestamp}.json"
    backup_path = os.path.join(backup_dir, backup_name)

    # Cerberus: use the symlink-safe writer consistently, like every other
    # generated-file write in this file, instead of a plain open().
    # reject_hardlinks=True (issue #53, decision 51a3c44): this backup path
    # is toolkit-generated-only, never a legitimate user file, so a hard
    # link here can only be an attack.
    with open_no_follow_symlink(backup_path, "w", reject_hardlinks=True) as f:
        json.dump(manifest, f, indent=2)

    return backup_path


# ── Migration: .claude/ root → .claude/.unmassk/ (v3.7→v3.8) ─────────────

def _migrate_runtime_to_unmassk(target: str) -> list[str]:
    """Move legacy runtime files from .claude/ root to .claude/.unmassk/.

    Returns list of migrated file descriptions.
    """
    claude_dir = os.path.join(target, ".claude")

    # SEC-HIGH-005: .claude may be a symlink to an external, pre-existing
    # directory — verify the resolved path stays inside target before
    # creating/moving anything below. apply_upgrade() calls this function
    # without a wrapping try/except (unlike its other steps), and tests call
    # it directly too, so UnsafePathError is caught right here and the
    # migration is simply skipped rather than propagated.
    try:
        verify_path_within_project(claude_dir, target)
    except UnsafePathError:
        return []

    unmassk_dir = os.path.join(claude_dir, ".unmassk")
    # Defense in depth (mirrors _create_manifest()'s pattern further below in
    # this same file): .unmassk itself could independently be a symlink
    # escaping the repo even when .claude (just verified above) is not.
    try:
        verify_path_within_project(unmassk_dir, target)
    except UnsafePathError:
        return []

    migrated = []

    # Map: old path → new path
    migrations = {
        os.path.join(claude_dir, ".glossary-cache.json"): os.path.join(unmassk_dir, "glossary-cache.json"),
        os.path.join(claude_dir, "git-memory-manifest.json"): os.path.join(unmassk_dir, "manifest.json"),
        os.path.join(claude_dir, ".session-booted"): os.path.join(unmassk_dir, ".session-booted"),
    }

    for old_path, new_path in migrations.items():
        if os.path.isfile(old_path):
            os.makedirs(os.path.dirname(new_path), exist_ok=True)
            try:
                # If new path already exists, old is stale — just delete
                if os.path.isfile(new_path):
                    os.remove(old_path)
                else:
                    os.rename(old_path, new_path)
                migrated.append(f"  {os.path.basename(old_path)} → .unmassk/{os.path.basename(new_path)}")
            except OSError:
                pass

    # Migrate scopes to agent-memory if still at old location
    old_scopes = os.path.join(claude_dir, "git-memory-scopes.json")
    if os.path.isfile(old_scopes):
        # Find or create an agent-memory dir for scopes
        agent_mem = os.path.join(claude_dir, "agent-memory")
        # Check if any agent already has scopes
        target_dir = None
        if os.path.isdir(agent_mem):
            for agent_dir in os.listdir(agent_mem):
                candidate = os.path.join(agent_mem, agent_dir, "scopes.json")
                if os.path.isfile(candidate):
                    target_dir = os.path.dirname(candidate)
                    break
        if not target_dir:
            # Default to a generic agent-memory location
            target_dir = os.path.join(agent_mem, "unmassk-crew-bilbo")
        # Defense in depth (same class as claude_dir/unmassk_dir elsewhere in
        # this file): target_dir (agent_mem itself, or one of its per-agent
        # subdirectories found via listdir) could independently be a symlink
        # even when claude_dir is not -- verify before creating/writing.
        try:
            verify_path_within_project(target_dir, target)
        except UnsafePathError:
            return migrated
        os.makedirs(target_dir, exist_ok=True)
        new_scopes = os.path.join(target_dir, "scopes.json")
        if not os.path.isfile(new_scopes):
            os.rename(old_scopes, new_scopes)
            migrated.append(f"  git-memory-scopes.json → agent-memory/.../scopes.json")
        else:
            os.remove(old_scopes)
            migrated.append(f"  git-memory-scopes.json removed (already in agent-memory)")

    return migrated


# ── Apply upgrade ─────────────────────────────────────────────────────────

def apply_upgrade(source: str, target: str, manifest: dict[str, Any], check_result: dict[str, Any]) -> list[str]:
    """Apply the upgrade: update CLAUDE.md, manifest, clean old files.

    Returns:
        List of error messages (empty on success).
    """
    errors = []

    # v3.8 migration: consolidate runtime files into .claude/.unmassk/
    migrated = _migrate_runtime_to_unmassk(target)
    if migrated:
        print("Migrated runtime files to .claude/.unmassk/:")
        for m in migrated:
            print(m)

    install_mod = _load_install_module()

    # Clean up old-style install files
    if check_result.get("has_old_install"):
        try:
            install_mod._cleanup_old_install(target, source)
        except Exception as e:
            errors.append(f"Error cleaning old install: {e}")

    # Update CLAUDE.md managed block
    try:
        install_mod._update_claude_md(target)
    except Exception as e:
        errors.append(f"Error updating CLAUDE.md: {e}")

    # Update manifest
    try:
        mode = manifest.get("runtime_mode", "normal")
        claude_dir = os.path.join(target, ".claude")
        # BUG Y / SEC-CRIT-NEW (same variant as install.py's
        # _create_manifest()): os.makedirs() silently follows a directory
        # symlink at .claude that resolves outside the repo. Verify before
        # creating anything — this whole block is already wrapped in the
        # `except Exception as e: errors.append(...)` a few lines below, so
        # raising here fails this action closed instead of crashing upgrade.
        verify_path_within_project(claude_dir, target)
        os.makedirs(claude_dir, exist_ok=True)

        new_manifest = {
            "version": VERSION,
            "installed_at": manifest.get("installed_at", datetime.now().isoformat()),
            "upgraded_at": datetime.now().isoformat(),
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
        # Defense in depth: .unmassk itself could independently be a
        # symlink escaping the repo even when .claude (just verified) is not.
        verify_path_within_project(unmassk_dir, target)
        os.makedirs(unmassk_dir, exist_ok=True)
        manifest_path = os.path.join(unmassk_dir, "manifest.json")
        # SEC-HIGH-NEW-03 (Argus): symlink-safe write — same guard as
        # git-memory-install.py's _create_manifest() and
        # lib/boot_memory.py's existing open_no_follow_symlink() writers.
        # reject_hardlinks=True (issue #53, decision 51a3c44): manifest.json
        # is toolkit-generated-only, never a legitimate user file, so a hard
        # link here can only be an attack.
        with open_no_follow_symlink(manifest_path, "w", reject_hardlinks=True) as f:
            json.dump(new_manifest, f, indent=2)
    except Exception as e:
        errors.append(f"Error updating manifest: {e}")

    return errors


# ── Internal helpers ──────────────────────────────────────────────────────

_install_mod = None

def _load_install_module() -> Any:
    """Load git-memory-install.py as a module (cached after first call)."""
    global _install_mod
    if _install_mod is not None:
        return _install_mod
    from importlib.util import spec_from_file_location, module_from_spec
    install_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git-memory-install.py")
    if not os.path.isfile(install_path):
        raise FileNotFoundError(f"git-memory-install.py not found at {install_path}")
    spec = spec_from_file_location("install", install_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module spec for {install_path}")
    _install_mod = module_from_spec(spec)
    spec.loader.exec_module(_install_mod)  # type: ignore[union-attr]
    return _install_mod


# ── Main ──────────────────────────────────────────────────────────────────

def main() -> None:
    """CLI entry point. Checks what needs upgrading and applies if confirmed."""
    parser = argparse.ArgumentParser(description="Safe upgrade for the git-memory system.")
    parser.add_argument("--auto", action="store_true", help="Non-interactive mode")
    parser.add_argument("--dry-run", action="store_true", help="Show what would change")
    parser.add_argument("--check", action="store_true", help="Only check if upgrade is available")
    parser.add_argument("--json", dest="json", action="store_true", help="JSON output")
    args = parser.parse_args()
    auto = args.auto
    dry_run = args.dry_run
    check_only = args.check
    as_json = args.json

    source = find_source_root()
    target = find_target_root()

    # Read current state
    manifest = read_installed_manifest(target)
    if manifest is None:
        if as_json:
            print(json.dumps({"status": "error", "message": "No installation to upgrade. Use: git memory install"}))
        else:
            print("Error: no git-memory installation to upgrade.", file=sys.stderr)
            print("Use: git memory install", file=sys.stderr)
        sys.exit(1)

    # Check what needs upgrading
    check_result = check_upgrade_needed(source, target, manifest)

    # --check: only report
    if check_only:
        if as_json:
            print(json.dumps({
                "status": "update_available" if check_result["needs_update"] else "up_to_date",
                "installed_version": check_result["installed_version"],
                "available_version": check_result["available_version"],
                "reasons": check_result["reasons"],
            }))
        else:
            if check_result["needs_update"]:
                print(f"Upgrade available: v{check_result['installed_version']} -> v{check_result['available_version']}")
                for reason in check_result["reasons"]:
                    print(f"  - {reason}")
            else:
                print(f"Already on the latest version (v{check_result['available_version']})")
        sys.exit(0)

    # Full output
    if not as_json:
        print("=== git memory upgrade ===")
        print(f"Plugin: {source}")
        print(f"Project: {target}")
        print()

    if not check_result["needs_update"]:
        if as_json:
            print(json.dumps({
                "status": "up_to_date",
                "installed_version": check_result["installed_version"],
                "available_version": check_result["available_version"],
            }))
        else:
            print(f"Already on the latest version (v{check_result['available_version']}). Nothing to upgrade.")
        sys.exit(0)

    # Show what needs upgrading
    if as_json:
        output = {
            "status": "update_available",
            "installed_version": check_result["installed_version"],
            "available_version": check_result["available_version"],
            "reasons": check_result["reasons"],
        }
        if dry_run:
            output["dry_run"] = True
            print(json.dumps(output, indent=2))
            sys.exit(0)
    else:
        print(f"Installed: v{check_result['installed_version']}")
        print(f"Available: v{check_result['available_version']}")
        print()
        print("Changes needed:")
        for reason in check_result["reasons"]:
            print(f"  - {reason}")
        print()

    if dry_run:
        if not as_json:
            print("(dry-run -- no changes applied)")
        sys.exit(0)

    # Confirmation
    if not auto:
        try:
            answer = input("Apply upgrade? [Y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\nAborted.")
            sys.exit(2)

        if answer and answer not in ("y", "yes", "s", "si", "sí", ""):
            print("Aborted.")
            sys.exit(2)

    # Backup
    if not as_json:
        print("Creating backup...")
    try:
        # reject_hardlinks=True (issue #53, decision 51a3c44) on the backup
        # write means create_backup() can now raise OSError (EMLINK) if a
        # hard link is planted at the backup path. Catch it here — same
        # OSError-handling pattern as apply_upgrade()'s try/except blocks
        # below (a message, then a clean degradation instead of an
        # uncaught crash) — so a hard-link attack fails this command
        # cleanly rather than crashing the whole upgrade.
        backup_path = create_backup(target, manifest)
    except OSError as e:
        errors = [f"Error creating backup: {e}"]
        if as_json:
            print(json.dumps({"status": "error", "errors": errors}))
        else:
            print(f"\n{len(errors)} error(s):")
            for err in errors:
                print(f"  ❌ {err}")
        sys.exit(1)
    if not as_json:
        print(f"  Backup: {backup_path}")

    # Apply
    if not as_json:
        print("Applying upgrade...")
    errors = apply_upgrade(source, target, manifest, check_result)

    if errors:
        if as_json:
            print(json.dumps({"status": "error", "errors": errors}))
        else:
            print(f"\n{len(errors)} error(s):")
            for err in errors:
                print(f"  ❌ {err}")
            print(f"\nBackup available at: {backup_path}")
        sys.exit(1)

    # Verify
    if not as_json:
        print("Verifying...")
    doctor_script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "git-memory-doctor.py")
    if os.path.isfile(doctor_script):
        subprocess.run([sys.executable, doctor_script], capture_output=True, timeout=15)

    if as_json:
        print(json.dumps({
            "status": "upgraded",
            "from_version": check_result["installed_version"],
            "to_version": check_result["available_version"],
            "backup": backup_path,
        }))
    else:
        print(f"\nUpgrade complete: v{check_result['installed_version']} -> v{check_result['available_version']}")
        print(f"  Backup: {backup_path}")

    sys.exit(0)


if __name__ == "__main__":
    main()
