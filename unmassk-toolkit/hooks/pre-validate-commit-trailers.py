#!/usr/bin/env python3
"""
Pre-commit git wrapper enforcement hook.

Intercepts direct `git commit` / `git log` invocations from Claude BEFORE
execution and blocks them, forcing use of the git-memory wrapper scripts
(`bin/git-memory-commit.py` / `bin/git-memory-log.py`), which own trailer
content, commit-type, and message validation themselves. Commands that
already use a wrapper, and any command run by a human (no CLAUDE_CODE env),
pass through untouched.

Exit codes:
    0: Allow.
    2: Block (direct git commit/log invocation from Claude).
"""

import json
import os
import re
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from colors import RED, RESET


def main() -> None:
    """Entry point. Reads hook input from stdin and blocks direct git commit/log."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # ── Block direct git commit / git log — force use of wrapper scripts ──
    # Only enforce for Claude (CLAUDE_CODE env set), not humans or tests
    is_claude = bool(os.environ.get("CLAUDE_CODE"))
    uses_wrapper = "git-memory-commit.py" in command or "git-memory-log.py" in command
    if is_claude and not uses_wrapper:
        if re.search(r"\bgit\b.*\bcommit\b", command):
            plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}")
            msg = f"\n{RED}>>> BLOCKED: Use the git-memory commit script instead of git commit directly.{RESET}"
            msg += f"\n{RED}>>> Run: python3 {plugin_root}/bin/git-memory-commit.py <type> <scope> <message> [--trailer KEY=VALUE]...{RESET}"
            print(msg, file=sys.stderr)
            sys.exit(2)
        if re.search(r"(?:^|[;&|]\s*)git(?:\s+-\S+)*\s+log(?:\s|$)", command):
            plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}")
            msg = f"\n{RED}>>> BLOCKED: Use the git-memory log script instead of git log directly.{RESET}"
            msg += f"\n{RED}>>> Run: python3 {plugin_root}/bin/git-memory-log.py [N] [--all] [--type TYPE]{RESET}"
            print(msg, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
