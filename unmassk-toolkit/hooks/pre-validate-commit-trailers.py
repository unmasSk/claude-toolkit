#!/usr/bin/env python3
"""
Pre-commit git wrapper enforcement hook.

Intercepts direct `git commit` invocations from Claude BEFORE execution and
blocks them, forcing use of the git-memory wrapper script
(`bin/git-memory-commit.py`), which owns trailer content, commit-type, and
message validation itself. Commands that already use a wrapper, and any
command run by a human (no CLAUDECODE env), pass through untouched.

Exit codes:
    0: Allow.
    2: Block (direct git commit invocation from Claude).
"""

import json
import os
import re
import shlex
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from colors import RED, RESET

# `git log` stays exempt: its mandatory alternative bin/git-memory-log.py
# ignores `count` when `--all` is passed and silently caps at 100 commits
# (git-memory-log.py:64), so direct `git log` is the only way to see full
# history. Flip back to True once that cap is fixed.
BLOCK_DIRECT_GIT_LOG = False

# Token that names the `git` program itself: bare "git", or a path ending
# in "/git" (any leading directory) — with an optional ".exe" suffix for
# Windows. Anchored on the whole token so "digit", "logit.py" or a filename
# that merely contains the substring never match.
_GIT_PROGRAM_TOKEN_RE = re.compile(r'(?:^|/)git(?:\.exe)?$', re.IGNORECASE)

# Global git options that consume a separate following argument token
# (e.g. `git -C /path commit`), so that path doesn't get mistaken for the
# subcommand. Options passed as `--flag=value` already carry their value in
# the same token and need no extra skip.
_GIT_VALUE_FLAGS = {"-C", "-c", "--git-dir", "--work-tree", "--namespace", "--exec-path"}

# Shell statement separators: a `command` string can chain several
# statements together, and each is checked independently.
_SHELL_STATEMENT_SEPARATORS = (";", "&&", "||", "|")


def _is_direct_git_commit(command: str) -> bool:
    """True only if `command` invokes `commit` as an actual git subcommand
    — `git` as the program, `commit` as the word right after it (global
    options like `-C <path>` or `--git-dir=<path>` may sit in between).

    This is a shape check, not a word search: "git" and "commit" occurring
    anywhere in the text (a file name, a quoted string, a path) no longer
    counts — that was BUG: it blocked reading this very file, a fixture
    script whose text mentioned "commit", and a history count, none of
    which are `git commit` invocations.

    Falls back to the old substring-style check only if the command cannot
    be tokenized at all (unbalanced quotes etc.) — fails closed rather than
    silently letting a real `git commit` through in that edge case.
    """
    try:
        # comments=True: an unquoted '#' starts a shell comment, same as a
        # real Bash invocation — text after it is dead prose, not arguments,
        # so "git commit" appearing only inside a trailing `# ...` comment
        # must not count as an invocation.
        tokens = shlex.split(command, comments=True)
    except ValueError:
        return bool(re.search(r"\bgit\b.*\bcommit\b", command))

    statement = []
    statements = []
    for tok in tokens:
        if tok in _SHELL_STATEMENT_SEPARATORS:
            statements.append(statement)
            statement = []
        else:
            statement.append(tok)
    statements.append(statement)

    for stmt in statements:
        n = len(stmt)
        for i, tok in enumerate(stmt):
            if not _GIT_PROGRAM_TOKEN_RE.search(tok):
                continue
            j = i + 1
            while j < n and stmt[j].startswith("-"):
                flag = stmt[j]
                j += 1
                if flag in _GIT_VALUE_FLAGS and "=" not in flag and j < n:
                    j += 1
            if j < n and stmt[j].lower() == "commit":
                return True
    return False


def main() -> None:
    """Entry point. Reads hook input from stdin and blocks direct git commit."""
    try:
        input_data = json.load(sys.stdin)
    except json.JSONDecodeError:
        sys.exit(0)

    tool_input = input_data.get("tool_input", {})
    command = tool_input.get("command", "")

    # ── Block direct git commit — force use of the wrapper script ─────────
    # Only enforce for Claude (CLAUDECODE env set), not humans or tests.
    # The variable is CLAUDECODE, no underscore — that is what Claude Code
    # actually exports; the previous `CLAUDE_CODE` never matched anything
    # and left this hook inert from v1.0.0 to 2026-07-29.
    is_claude = bool(os.environ.get("CLAUDECODE"))
    uses_wrapper = "git-memory-commit.py" in command or "git-memory-log.py" in command
    if is_claude and not uses_wrapper:
        if _is_direct_git_commit(command):
            plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}")
            msg = f"\n{RED}>>> BLOCKED: Use the git-memory commit script instead of git commit directly.{RESET}"
            msg += f"\n{RED}>>> Run: python3 {plugin_root}/bin/git-memory-commit.py <type> <scope> <message> [--trailer KEY=VALUE]...{RESET}"
            print(msg, file=sys.stderr)
            sys.exit(2)
        if BLOCK_DIRECT_GIT_LOG and re.search(r"(?:^|[;&|]\s*)git(?:\s+-\S+)*\s+log(?:\s|$)", command):
            plugin_root = os.environ.get("CLAUDE_PLUGIN_ROOT", "${CLAUDE_PLUGIN_ROOT}")
            msg = f"\n{RED}>>> BLOCKED: Use the git-memory log script instead of git log directly.{RESET}"
            msg += f"\n{RED}>>> Run: python3 {plugin_root}/bin/git-memory-log.py [N] [--all] [--type TYPE]{RESET}"
            print(msg, file=sys.stderr)
            sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
