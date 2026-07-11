"""
One-shot boot migrations for session-start-boot.py (CRB-04 split).

Each function here is a self-contained, idempotent migration that main()
runs unconditionally on every boot; each one no-ops once its condition no
longer holds. Grouped separately from lib/boot_memory.py because these are
one-time repo/settings repairs, not part of the recurring memory-extraction
model.

Issue #63 (boot simplification, point 4): this module used to also own
_migrate_runtime_to_unmassk() and _migrate_untrack_generated_jsons(), both
pre-v1.0.0 (present since 037e0cb, 2026-03-17) and long past due — ~4
months of boots since, no active installation can plausibly still be on the
pre-.unmassk/ layout or have generated JSONs tracked from an old install.
Both are retired from the boot path. _migrate_runtime_to_unmassk's only
remaining home is its near-identical copy in bin/git-memory-upgrade.py
(runs during the explicit `git memory upgrade` path, kept there for very
old installs) — "una regla, un sitio" instead of two independently
maintained copies. _migrate_untrack_generated_jsons had no other caller and
no upgrade-path duplicate, so it is deleted outright, not relocated.
_migrate_stale_context_writer_statusline (2026-06-05, only ~5 weeks old at
the time of this change) is intentionally kept for one more cycle — the
plan's conservative criterion for what counts as "cumplida de sobra".

See lib/boot_memory.py's own module docstring and
tests/test_migrate_statusline.py for why `git_helpers` imports below are
deferred into each function body rather than hoisted to module level — this
module is a real, stably-named module (first `import boot_migrations`
anywhere in a process caches it for that process), and a module-level `from
git_helpers import X` could freeze X to a test's temporary stub forever if
this module's first-ever import happened to land inside that stub's window.
"""

import json
import os
import sys


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
