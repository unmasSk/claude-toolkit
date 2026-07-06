#!/usr/bin/env python3
"""
SessionStart hook for unmassk-toolkit crew.
Ensures all 5 managed blocks exist in CLAUDE.md.
"""
import subprocess
import sys
from pathlib import Path

# Make lib/ importable when running from the plugin cache
import os
_LIB_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from managed_blocks import upsert_managed_blocks  # noqa: E402
from git_helpers import open_no_follow_symlink  # noqa: E402


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


def main():
    git_root = find_git_root()
    if not git_root:
        print("[crew] Not a git repo, skipping CLAUDE.md check")
        return

    claude_md = git_root / "CLAUDE.md"
    claude_md_exists = claude_md.exists()

    if claude_md_exists:
        try:
            # barrido finding: never follow a symlink planted at CLAUDE.md —
            # same bug class as BUG K (install.py/uninstall.py), a separate
            # call site found via the barrido sweep. open_no_follow_symlink()
            # takes a path-like object fine (os.open() accepts Path via
            # os.fspath()), so we read/write via the file handle instead of
            # pathlib.Path's read_text()/write_text().
            with open_no_follow_symlink(claude_md, "r", encoding="utf-8") as f:
                content = f.read()
        except (OSError, UnicodeDecodeError):
            print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping")
            return
    else:
        content = ""

    new_content, log = upsert_managed_blocks(content)

    try:
        if not claude_md_exists:
            with open_no_follow_symlink(claude_md, "w", encoding="utf-8") as f:
                f.write(new_content)
            print("[crew] Created CLAUDE.md with all managed blocks")
            return

        if new_content != content:
            with open_no_follow_symlink(claude_md, "w", encoding="utf-8") as f:
                f.write(new_content)
            for line in log:
                print(f"[crew] {line}")
        else:
            print("[crew] All managed blocks up to date")
    except OSError:
        print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping write")


if __name__ == "__main__":
    main()
