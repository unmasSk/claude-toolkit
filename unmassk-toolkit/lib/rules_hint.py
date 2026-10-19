"""The session-start line that tells Claude to read the owner's rules now.

Used by hooks/session-start-crew.py after it rewrites CLAUDE.md's managed
blocks.
"""
from pathlib import Path

from managed_blocks import BLOCKS

# D-131: the toolkit block's own @import line, so the hint below names
# exactly what the import loads.
RULES_IMPORT = next(
    (ln.strip() for ln in BLOCKS[0]["body"].splitlines() if ln.startswith("@")), None)


def print_rules_hint(git_root: Path, old_content: str, new_content: str) -> None:
    """Claude Code reads CLAUDE.md before this hook rewrites it: when this
    start is the one that adds the import, the rules would only arrive next
    session -- so tell Claude to read them now. Silent when the import was
    already there (loaded at launch) or the rules file does not exist."""
    if not RULES_IMPORT or RULES_IMPORT in old_content or RULES_IMPORT not in new_content:
        return
    rules = RULES_IMPORT[1:]
    if (git_root / rules).is_file():
        print(f"[crew] READ NOW, before replying: {rules} whole -- the owner's rules. "
              "CLAUDE.md's import of it was just added and only loads next session.")
