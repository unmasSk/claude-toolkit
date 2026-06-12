#!/usr/bin/env python3
"""
UserPromptSubmit hook -- bootstrap + memory capture reminder.

Fires on every user message. Two responsibilities:
1. If git-memory is not configured: tell Claude to install it
2. If configured: remind Claude to boot (if not done) + check for memory-worthy content

Exit codes:
    0: Always (never blocks user input).
"""

import json
import os
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))

from git_helpers import is_git_repo, run_git
from version import VERSION as PLUGIN_VERSION

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


def _parse_semver(version_str) -> tuple[int, int, int] | None:
    """Parse a semver string into a (major, minor, patch) tuple of ints.

    Returns None if the input is not a string, is empty, or cannot be parsed
    as semver. Only strings with exactly three numeric components (X.Y.Z) are
    accepted; anything else returns None. Pre-release suffixes are not
    supported and will cause a parse failure (returns None).
    """
    if not isinstance(version_str, str) or not version_str:
        return None
    parts = version_str.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def needs_upgrade(root: str) -> bool:
    """Check if the CLAUDE.md managed block has outdated content OR the
    installed manifest version is older than PLUGIN_VERSION.

    Upgrade triggers (union — any one is enough):
      1. Old-style CLAUDE.md block markers (stale hardcoded bin/ paths or
         missing 'Context Checkpoint Commits').
      2. manifest.version < PLUGIN_VERSION (numeric semver comparison).

    Fail-safe: if the manifest is absent, corrupt, missing the 'version'
    key, or has an unparseable version string → False (not True).
    Returning True on a broken manifest would cause an infinite upgrade loop
    because the manifest is never written before the next hook fires.
    """
    claude_md = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return False  # needs_install handles this
    with open(claude_md) as f:
        content = f.read()
    if "BEGIN unmassk-toolkit" not in content:
        return False  # needs_install handles this

    # ── Check 1: Old-style markers in the managed block ──────────────────
    begin = content.find("BEGIN unmassk-toolkit")
    end = content.find("END unmassk-toolkit")
    if begin == -1 or end == -1:
        return False
    block = content[begin:end]
    if "python3 bin/" in block or "Context Checkpoint Commits" not in block:
        return True

    # ── Check 2: Semver comparison — manifest.version < PLUGIN_VERSION ───
    try:
        manifest_path = os.path.join(root, ".claude", ".unmassk", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        # manifest.get("version", "") guards against a missing key, but JSON
        # null still arrives as None here. _parse_semver tolerates non-str input.
        manifest_version = manifest.get("version", "")
        manifest_tuple = _parse_semver(manifest_version)
        if manifest_tuple is None:
            return False  # fail-safe: unparseable or empty version
        code_tuple = _parse_semver(PLUGIN_VERSION)
        if code_tuple is None:
            return False  # fail-safe: PLUGIN_VERSION itself is broken
        return manifest_tuple < code_tuple
    except Exception:
        return False  # fail-safe: missing file, bad JSON, any I/O error


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
