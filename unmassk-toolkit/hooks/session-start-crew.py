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


def find_git_root():
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5
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

    if claude_md.exists():
        content = claude_md.read_text(encoding="utf-8")
    else:
        content = ""

    new_content, log = upsert_managed_blocks(content)

    if not claude_md.exists():
        claude_md.write_text(new_content, encoding="utf-8")
        print("[crew] Created CLAUDE.md with all managed blocks")
        return

    if new_content != content:
        claude_md.write_text(new_content, encoding="utf-8")
        for line in log:
            print(f"[crew] {line}")
    else:
        print("[crew] All managed blocks up to date")


if __name__ == "__main__":
    main()
