#!/usr/bin/env python3
"""SessionStart hook: keeps CLAUDE.md's managed blocks current and prints the PLUGIN, UPGRADE and REPO checks."""
import subprocess
import sys
from pathlib import Path

# Make lib/ importable when running from the plugin cache
import os
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402
force_utf8_streams()

from managed_blocks import upsert_managed_blocks  # noqa: E402
from rules_hint import print_rules_hint  # noqa: E402
from git_helpers import claude_md_lock_path, file_lock, open_no_follow_symlink, run_git  # noqa: E402

# Optional incident channel: the real OSError behind a failed CLAUDE.md write is reported there.
try:
    from incidents import report_incident  # noqa: E402
except Exception:  # fail-open: no incident channel is not a reason to fail the boot
    report_incident = None  # type: ignore[assignment]


def find_git_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, encoding="utf-8", timeout=5
        )
        if result.returncode == 0:
            return Path(result.stdout.strip())
    except Exception:
        pass
    return None


def _read_claude_md(claude_md):
    """Return (content, exists); (None, None) means a symlink or undecodable file, to be skipped."""
    if not claude_md.exists():
        return "", False
    try:
        with open_no_follow_symlink(claude_md, "r", encoding="utf-8") as f:
            return f.read(), True
    except (OSError, UnicodeDecodeError):
        return None, None


def _print_plugin_sync_check(git_root: Path) -> None:
    """Print the repo-vs-installed-cache drift line; silent outside the toolkit repo, never raises."""
    try:
        from cache_sync_check import PLUGIN_DIR_NAME, count_repo_cache_drift
        if not (git_root / PLUGIN_DIR_NAME).is_dir():
            return
        summary = count_repo_cache_drift(str(git_root))
    except Exception as e:
        print(f"[crew] PLUGIN: no verificable ({type(e).__name__})")
        return
    if summary is None:
        print("[crew] PLUGIN: no verificable (no hay plugin instalado distinto del repo)")
        return
    count, _descriptions = summary
    if count == 0:
        print("[crew] PLUGIN: sincronizado (0 ficheros)")
    else:
        print(
            f"[crew] PLUGIN: {count} ficheros desincronizados (repo vs cache) "
            "-> publica version y actualiza desde /plugin > marketplace"
        )


def _print_upgrade_check(git_root: Path) -> None:
    """Auto-upgrade the installed manifest when it is behind; always prints one UPGRADE line, never raises."""
    # needs_upgrade() also returns False when there is no manifest, so a missing one is reported separately.
    try:
        from upgrade_check import needs_upgrade, trigger_auto_upgrade_if_needed
        manifest = git_root / ".claude" / ".unmassk" / "manifest.json"
        installed = manifest.is_file()
        pending = needs_upgrade(str(git_root))
    except Exception as e:
        print(f"[crew] UPGRADE: no verificable ({type(e).__name__})")
        return
    if not installed:
        print(
            "[crew] UPGRADE: este proyecto NO tiene el toolkit instalado "
            "(falta .claude/.unmassk/manifest.json)"
        )
        return
    if not pending:
        print("[crew] UPGRADE: manifest al dia, no hace falta actualizar")
        return
    try:
        trigger_auto_upgrade_if_needed(str(git_root))
    except Exception as e:
        print(f"[crew] UPGRADE: fallo al disparar la actualizacion ({type(e).__name__})")
        return
    print("[crew] UPGRADE: disparada (el manifest instalado iba por detras)")


def _print_repo_status_check(git_root: Path) -> None:
    """Print a one-line working-tree status from `git status --porcelain` (5 s timeout)."""
    try:
        code, output = run_git(["status", "--porcelain"], cwd=str(git_root), timeout=5)
    except Exception as e:
        print(f"[crew] REPO: estado no verificable ({type(e).__name__})")
        return
    if code != 0:
        print("[crew] REPO: estado no verificable (git status fallo)")
        return
    changed = output.strip().splitlines()
    if not changed:
        print("[crew] REPO: working tree limpio, sin cambios sin guardar")
    else:
        print(f"[crew] REPO: {len(changed)} ficheros con cambios sin guardar")


def main():
    git_root = find_git_root()
    if not git_root:
        print("[crew] Not a git repo, skipping CLAUDE.md check")
        return

    # The checks run after the block cycle (the upgrade rewrites CLAUDE.md) and always, via finally.
    try:
        _managed_blocks_cycle(git_root)
    finally:
        _print_plugin_sync_check(git_root)
        _print_upgrade_check(git_root)
        _print_repo_status_check(git_root)


def _managed_blocks_cycle(git_root: Path) -> None:
    """Diff CLAUDE.md against the canonical managed blocks and write it only when they differ."""
    claude_md = git_root / "CLAUDE.md"

    # Lock-free check first: an up-to-date repo never takes the lock (it may sit on a read-only mount).
    content, claude_md_exists = _read_claude_md(claude_md)
    if content is None:
        print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping")
        return

    new_content, log = upsert_managed_blocks(content)
    if claude_md_exists and new_content == content:
        print("[crew] All managed blocks up to date")
        return

    # The shared CLAUDE.md lock spans the whole read -> upsert -> write cycle; re-check under it.
    try:
        lock_path = claude_md_lock_path(str(git_root))
        with file_lock(str(claude_md), lock_path=lock_path):
            content, claude_md_exists = _read_claude_md(claude_md)
            if content is None:
                print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping")
                return

            new_content, log = upsert_managed_blocks(content)

            # atomic=True: temp file + os.replace(), so a crash never leaves CLAUDE.md partial.
            if not claude_md_exists:
                with open_no_follow_symlink(claude_md, "w", encoding="utf-8", atomic=True) as f:
                    f.write(new_content)
                print("[crew] Created CLAUDE.md with all managed blocks")
                print_rules_hint(git_root, content, new_content)
                return

            if new_content != content:
                with open_no_follow_symlink(claude_md, "w", encoding="utf-8", atomic=True) as f:
                    f.write(new_content)
                for line in log:
                    print(f"[crew] {line}")
                print_rules_hint(git_root, content, new_content)
            else:
                print("[crew] All managed blocks up to date")
    except OSError as exc:
        # Guarded again: a version-skewed incidents.py may raise, and the boot must not die.
        try:
            if report_incident is not None:
                report_incident("claude-md-write",
                                "los bloques gestionados de CLAUDE.md NO se escribieron",
                                exc=exc)
        except BaseException:
            pass
        print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping write")


if __name__ == "__main__":
    main()
