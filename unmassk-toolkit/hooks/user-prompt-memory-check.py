#!/usr/bin/env python3
"""
UserPromptSubmit hook -- bootstrap + memory capture reminder.

Fires on every user message. Two responsibilities:
1. If git-memory is not configured: tell Claude to install it
2. If configured: remind Claude to boot (if not done) + check for memory-worthy content

Exit codes:
    0: Always (never blocks user input).
"""

import os
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))

from git_helpers import is_git_repo, run_git

# Plugin root — derived from this script's location in the cache.
# hooks/user-prompt-memory-check.py → go up one level → plugin root.
PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))


def get_project_root() -> str | None:
    """Get the git repo root, or None."""
    code, toplevel = run_git(["rev-parse", "--show-toplevel"])
    return toplevel if code == 0 else None


def needs_install(root: str) -> bool:
    """Check if git-memory CLAUDE.md managed block is present."""
    claude_md = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return True
    with open(claude_md) as f:
        return "BEGIN unmassk-toolkit" not in f.read()


def needs_upgrade(root: str) -> bool:
    """Check if the CLAUDE.md managed block has outdated content.

    Detects old-style instructions that reference hardcoded paths like
    'python3 bin/' instead of dynamic paths from hook output.
    """
    claude_md = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return False  # needs_install handles this
    with open(claude_md) as f:
        content = f.read()
    if "BEGIN unmassk-toolkit" not in content:
        return False  # needs_install handles this
    # Old-style markers: hardcoded bin/ paths in the managed block
    begin = content.find("BEGIN unmassk-toolkit")
    end = content.find("END unmassk-toolkit")
    if begin == -1 or end == -1:
        return False
    block = content[begin:end]
    return "python3 bin/" in block or "Context Checkpoint Commits" not in block


def main() -> None:
    """Print hook output for Claude to process."""
    if not is_git_repo():
        sys.exit(0)

    root = get_project_root()
    if not root:
        sys.exit(0)

    # Case 1: git-memory not installed yet — tell Claude to install
    if needs_install(root):
        print(
            "[git-memory-bootstrap] Git-memory plugin is active but NOT configured. "
            "BEFORE doing anything else:\n"
            f'1. Run: python3 "{PLUGIN_ROOT}/bin/git-memory-install.py" --auto\n'
            '2. Use the Skill tool with skill="unmassk-core" (TOOL CALL, not bash)\n'
            '3. Use the Skill tool with skill="unmassk-gitmemory" (TOOL CALL, not bash)\n'
            f'4. Read CALIBRATION.md: Read tool on {PLUGIN_ROOT}/skills/unmassk-gitmemory/CALIBRATION.md\n'
            "5. Show the user a boot summary from the SessionStart output above.\n"
            "DO NOT greet the user first. Install and boot FIRST.\n"
            "DO NOT SKIP ANY STEP."
        )
        sys.exit(0)

    # Case 1.5: Installed but CLAUDE.md managed block is outdated — auto-upgrade
    if needs_upgrade(root):
        import subprocess
        install_script = os.path.join(PLUGIN_ROOT, "bin", "git-memory-install.py")
        subprocess.run(
            [sys.executable, install_script, "--auto"],
            capture_output=True, text=True, cwd=root, timeout=15,
        )

    # Case 2: Installed — check if session already booted
    lines = []
    booted_flag = os.path.join(root, ".claude", ".unmassk", ".session-booted")
    session_booted = os.path.isfile(booted_flag)

    if not session_booted:
        # First message — force skill loading
        lines.append(
            f"[git-memory-boot] Plugin root: {PLUGIN_ROOT}\n"
            "MANDATORY — Do these steps NOW before responding to the user:\n"
            '  Step 1: Use the Skill tool with skill="unmassk-core" (TOOL CALL, not bash)\n'
            '  Step 2: Use the Skill tool with skill="unmassk-gitmemory" (TOOL CALL, not bash)\n'
            f'  Step 3: Read CALIBRATION.md: Read tool on {PLUGIN_ROOT}/skills/unmassk-gitmemory/CALIBRATION.md\n'
            "  Step 4: Show the user a boot summary from the SessionStart output above\n"
            "DO NOT SKIP ANY STEP. DO NOT GREET THE USER BEFORE COMPLETING ALL STEPS."
        )
        # Create the flag so subsequent messages don't repeat this
        try:
            runtime_dir = os.path.join(root, ".claude", ".unmassk")
            os.makedirs(runtime_dir, exist_ok=True)
            open(booted_flag, "w").close()
        except OSError:
            pass
    else:
        # Already booted — just plugin root for reference
        lines.append(f"[git-memory] root: {PLUGIN_ROOT}")

    # Memory capture check — always present, covers all memory commit types.
    # Default is RESTRAINT, not capture: the reminder must lower the push to save,
    # not amplify it. The brake (near-dup gate) is the net; this is the belt.
    lines.append(
        "[memory-check] Before saving: is this memory-worthy? Save ONLY if it clears ALL of: "
        "(1) durable — still true next session, not a one-off; "
        "(2) non-derivable — not already in the code or git-log; "
        "(3) not already captured. "
        "FIRST check existing memory: if a memo/remember already covers this, do NOT add another — "
        "if it's a correction, RETIRE the old one with a Resolved-Memo/Resolved-Remember tombstone "
        "instead of stacking a new entry. "
        "Systemic/process rules belong in the loaded skill, NOT in memory. "
        "If in doubt, or it's just thinking out loud → do nothing. Silence beats noise."
    )

    print("\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    main()
