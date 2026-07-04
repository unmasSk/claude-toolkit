"""
One-shot boot migrations for session-start-boot.py (CRB-04 split).

Each function here is a self-contained, idempotent migration that main()
runs unconditionally on every boot; each one no-ops once its condition no
longer holds. Grouped separately from lib/boot_memory.py because these are
one-time repo/settings repairs, not part of the recurring memory-extraction
model.
"""

import json
import os
import sys

from git_helpers import ensure_gitignore, run_git


def _migrate_runtime_to_unmassk(project_root: str) -> None:
    """Move legacy runtime files from .claude/ root to .claude/.unmassk/ (v3.7→v3.8)."""
    claude_dir = os.path.join(project_root, ".claude")
    unmassk_dir = os.path.join(claude_dir, ".unmassk")
    migrations = {
        ".glossary-cache.json": "glossary-cache.json",
        "git-memory-manifest.json": "manifest.json",
        ".session-booted": ".session-booted",
    }
    for old_name, new_name in migrations.items():
        old_path = os.path.join(claude_dir, old_name)
        if os.path.isfile(old_path):
            os.makedirs(unmassk_dir, exist_ok=True)
            new_path = os.path.join(unmassk_dir, new_name)
            try:
                if os.path.isfile(new_path):
                    os.remove(old_path)
                else:
                    os.rename(old_path, new_path)
            except OSError:
                pass
    # Migrate scopes to agent-memory
    old_scopes = os.path.join(claude_dir, "git-memory-scopes.json")
    if os.path.isfile(old_scopes):
        agent_dir = os.path.join(claude_dir, "agent-memory", "unmassk-crew-bilbo")
        os.makedirs(agent_dir, exist_ok=True)
        new_scopes = os.path.join(agent_dir, "scopes.json")
        try:
            if os.path.isfile(new_scopes):
                os.remove(old_scopes)
            else:
                os.rename(old_scopes, new_scopes)
        except OSError:
            pass


def _migrate_untrack_generated_jsons(project_root: str) -> None:
    """Retrocompat: untrack generated JSONs that older installs committed."""
    from git_helpers import _GENERATED_JSONS
    tracked = []
    for entry in _GENERATED_JSONS:
        full_path = os.path.join(project_root, entry)
        code, _ = run_git(["ls-files", "--error-unmatch", full_path])
        if code == 0:
            tracked.append(full_path)
    if tracked:
        # CRB-08: best-effort by design — this is a one-shot retrocompat
        # migration for older installs, and boot must never fail because of
        # it. If `git rm --cached` fails (e.g. permissions, index lock held
        # by another process), the files simply stay tracked and the next
        # boot retries the same migration; there is nothing else safe to do
        # here without risking the boot-must-never-fail contract.
        code, _ = run_git(["rm", "-r", "--cached", "--"] + tracked)
        if code == 0:
            ensure_gitignore(project_root)


def _migrate_stale_context_writer_statusline() -> None:
    """One-time migration: remove or restore a statusLine left by old context-writer.py.

    Users who installed the old version have a statusLine.command in
    ~/.claude/settings.json pointing at context-writer.py (now deleted).
    This migration runs once per boot and is idempotent.

    Logic:
      - If settings.json has a statusLine.command containing "context-writer":
          (a) If ~/.claude/.git-memory-original-statusline exists and is non-empty,
              restore that value as the new statusLine.command.
          (b) Otherwise, remove the statusLine key entirely.
          (c) In both cases, delete the backup file.
      - If no context-writer statusLine is present, do nothing.
      - Any exception is silently swallowed — boot must never fail — but a
        one-line trace goes to stderr first (CRB-05) so an unexpected
        failure here isn't completely invisible.
    """
    try:
        claude_dir = os.path.join(os.path.expanduser("~"), ".claude")
        settings_path = os.path.join(claude_dir, "settings.json")
        backup_path = os.path.join(claude_dir, ".git-memory-original-statusline")

        if not os.path.isfile(settings_path):
            return

        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                settings = json.load(f)
        except (json.JSONDecodeError, OSError):
            return

        status_line = settings.get("statusLine", {})
        current_cmd = status_line.get("command", "") if isinstance(status_line, dict) else ""

        if "context-writer" not in current_cmd:
            return  # Nothing to migrate

        # Determine replacement
        backup_content = ""
        if os.path.isfile(backup_path):
            try:
                with open(backup_path, "r", encoding="utf-8") as f:
                    backup_content = f.read().strip()
            except OSError:
                pass

        if backup_content:
            # Restore the original command with a complete statusLine structure
            settings["statusLine"] = {"type": "command", "command": backup_content, "padding": 0}
        else:
            # No backup — remove the stale key entirely
            settings.pop("statusLine", None)

        try:
            with open(settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
                f.write("\n")
        except OSError:
            return

        # Remove backup file regardless of which branch was taken
        try:
            os.remove(backup_path)
        except FileNotFoundError:
            pass

    except Exception as e:
        # CRB-05: boot must never fail due to this migration — the design is
        # intentional and unchanged — but leave a one-line breadcrumb instead
        # of swallowing the exception type completely silently.
        print(
            f"[session-start-boot] BOOT-WARNING: {type(e).__name__} in "
            "_migrate_stale_context_writer_statusline",
            file=sys.stderr,
        )
