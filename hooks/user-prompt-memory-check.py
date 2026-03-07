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
        return "BEGIN claude-git-memory" not in f.read()


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
            f"1. Run: python3 {PLUGIN_ROOT}/bin/git-memory-install.py --auto\n"
            "2. Use the Skill tool with skill=\"git-memory\" to load the memory rules\n"
            f"3. Run: python3 {PLUGIN_ROOT}/bin/git-memory-doctor.py --json\n"
            "4. Run: git log --oneline -20\n"
            "5. Show the user a boot summary.\n"
            "Do NOT greet the user first. Install and boot FIRST.\n"
            "CRITICAL: Step 2 means calling the Skill tool — "
            "this is a tool call, not a bash command."
        )
        sys.exit(0)

    # Case 2: Installed — always remind about boot + memory check
    lines = []

    # Boot reminder on every message (Claude may not have booted yet)
    lines.append(
        f"[git-memory-boot] Plugin root: {PLUGIN_ROOT}\n"
        "If you have NOT yet booted this session, "
        "do ALL of these steps NOW before responding to the user:\n"
        "  Step 1: Use the Skill tool with skill=\"git-memory\" "
        "(this is a TOOL CALL, not a bash command)\n"
        f"  Step 2: Run: python3 {PLUGIN_ROOT}/bin/git-memory-doctor.py --json\n"
        "  Step 3: Run: git log --oneline -20\n"
        "  Step 4: Show the user a boot summary\n"
        "If you already booted this session, skip this."
    )

    # Memory capture check
    lines.append(
        "[memory-check] Evaluate this message: "
        "does it contain a decision, preference, requirement, or anti-pattern? "
        "If yes → propose a decision() or memo() commit. If not → do nothing."
    )

    # Periodic context commit reminder.
    # Count messages via a temp file. Every 20 messages, remind Claude
    # to create a context() commit if it hasn't made one recently.
    counter_file = os.path.join(root, ".claude", ".message-counter")
    msg_count = 0
    try:
        os.makedirs(os.path.dirname(counter_file), exist_ok=True)
        if os.path.isfile(counter_file):
            with open(counter_file) as f:
                msg_count = int(f.read().strip() or "0")
        msg_count += 1
        with open(counter_file, "w") as f:
            f.write(str(msg_count))
    except (ValueError, OSError):
        pass

    if msg_count > 0 and msg_count % 20 == 0:
        # Check if there's a recent context commit (within last 5 commits)
        code, recent = run_git(["log", "-5", "--pretty=format:%s"])
        has_recent_context = False
        if code == 0 and recent:
            for subj in recent.split("\n"):
                cleaned = subj.strip().lstrip("🔧💾📌🧭✨🐛♻️🔥📝🚀 ")
                if cleaned.lower().startswith("context"):
                    has_recent_context = True
                    break
        if not has_recent_context:
            lines.append(
                "[context-reminder] You have exchanged ~20 messages without "
                "creating a context() commit. Create one NOW to checkpoint your work. "
                "Use: git commit --allow-empty -m \"💾 context(<scope>): <summary of current work>"
                "\\n\\nNext: <pending tasks>\\nDecision: <decisions made>\""
                " — Include all relevant trailers so the next session can continue."
            )

    print("\n".join(lines))
    sys.exit(0)


if __name__ == "__main__":
    main()
