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

from encoding_guard import force_utf8_streams  # noqa: E402
force_utf8_streams()

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

    # Issue #63 (boot simplification, P1 v2 -- decision 2d56444): the gate
    # verifies CONTENT, never manifest.json's "version" field. That field is
    # only a proxy for "an install ran", not "CLAUDE.md's managed blocks are
    # correct right now" -- Moriarty broke the version-only gate with 3 live
    # T1 PoCs (producer stamps version even when the CLAUDE.md write failed;
    # a poisoned block sits untouched next to a version-matching manifest;
    # CLAUDE.md deleted while a matching manifest survives is never
    # recreated). CLAUDE.md is therefore ALWAYS read (existence check comes
    # first, below) and always diffed against the canonical blocks via
    # upsert_managed_blocks(); reading+diffing is cheap and always happens.
    # The only thing ever skipped is the WRITE, and only when the diff is
    # empty (new_content == content) -- Bex's "write the minimum" goal,
    # preserved without trusting any external proxy for content state.
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
        # atomic=True (docs/plan/fix-atomic-claude-md-write.md, T1): writes
        # to a temp file in the same directory + os.replace(), so a crash/
        # kill mid-write can never leave CLAUDE.md empty or partial — see
        # git_helpers._AtomicWriteNoFollowSymlink's docstring.
        if not claude_md_exists:
            with open_no_follow_symlink(claude_md, "w", encoding="utf-8", atomic=True) as f:
                f.write(new_content)
            print("[crew] Created CLAUDE.md with all managed blocks")
            return

        if new_content != content:
            with open_no_follow_symlink(claude_md, "w", encoding="utf-8", atomic=True) as f:
                f.write(new_content)
            for line in log:
                print(f"[crew] {line}")
        else:
            print("[crew] All managed blocks up to date")
    except OSError:
        print("[crew] CLAUDE.md is a symlink, refusing to follow it — skipping write")


if __name__ == "__main__":
    main()
