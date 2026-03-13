#!/usr/bin/env python3
"""
git-memory-commit — Pretty commit wrapper for git-memory.

Creates a git commit with proper emoji, type, scope, trailers,
and prints a single pretty line for the user.

Usage:
  git-memory-commit.py <type> <scope> <message> [--body TEXT] [--trailer KEY=VALUE]...
  git-memory-commit.py decision auth "usar JWT"
  git-memory-commit.py memo api "preference - siempre async/await" --trailer "Why=equipo lo prefiere"
  git-memory-commit.py feat forms "add date picker" --body "Full body text" --trailer "Why=users need dates" --trailer "Touched=src/forms/"
  git-memory-commit.py context forms "validación completada" --trailer "Next=wire to API"
  git-memory-commit.py wip forms "half-done date picker"

Exit codes:
  0: Commit created
  1: Error
"""

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from git_helpers import run_git

# ── Emoji map ────────────────────────────────────────────────────────────

EMOJIS = {
    "feat": "✨", "fix": "🐛", "refactor": "♻️", "perf": "⚡",
    "test": "🧪", "docs": "📝", "chore": "🔧", "ci": "👷",
    "wip": "🚧", "context": "💾", "decision": "🧭", "memo": "📌",
    "remember": "🧠",
}

# Memory types use --allow-empty
MEMORY_TYPES = {"context", "decision", "memo", "remember"}

_gh_available_cache: bool | None = None

def _gh_available() -> bool:
    """Check if gh CLI is installed and authenticated. Result is cached for the process."""
    global _gh_available_cache
    if _gh_available_cache is not None:
        return _gh_available_cache
    try:
        result = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, text=True, timeout=5,
        )
        _gh_available_cache = result.returncode == 0
    except (FileNotFoundError, OSError):
        _gh_available_cache = False
    return _gh_available_cache


def _auto_create_issue(next_text: str) -> str | None:
    """Try to create a GitHub issue from a Next: trailer text.

    Returns '#N' issue reference if successful, None otherwise.
    Only runs if gh CLI is available and the text has no existing #ref.
    """
    if "#" in next_text:
        return None  # Already has an issue reference
    if not _gh_available():
        return None
    try:
        result = subprocess.run(
            ["gh", "issue", "create", "--title", next_text, "--label", "next", "--body",
             f"Auto-created from git-memory Next: trailer.\n\nSource: `Next: {next_text}`"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            # gh issue create prints the URL, extract issue number
            url = result.stdout.strip()
            # URL format: https://github.com/owner/repo/issues/42
            match = re.search(r"/issues/(\d+)", url)
            if match:
                return f"#{match.group(1)}"
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass
    return None


def _auto_close_issue(issue_ref: str) -> None:
    """Try to close a GitHub issue referenced in a Resolved-Next: trailer.

    Silently degrades if gh CLI is unavailable.
    """
    match = re.search(r"#(\d+)", issue_ref)
    if not match:
        return
    if not _gh_available():
        return
    try:
        subprocess.run(
            ["gh", "issue", "close", match.group(1), "--comment",
             "Resolved via git-memory Resolved-Next: trailer"],
            capture_output=True, text=True, timeout=15,
        )
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        pass

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"
RED = "\033[91m"

CYAN = "\033[36m"

TYPE_COLORS = {
    "decision": YELLOW, "memo": BLUE, "context": GREEN,
    "remember": CYAN,
    "feat": MAGENTA, "fix": MAGENTA, "refactor": MAGENTA,
    "perf": MAGENTA, "test": MAGENTA, "docs": MAGENTA,
    "chore": MAGENTA, "ci": MAGENTA, "wip": DIM,
}


def build_commit_message(type_: str, scope: str, message: str,
                         body: str | None, trailers: list[str]) -> str:
    """Build the full commit message with emoji, subject, body, trailers."""
    emoji = EMOJIS.get(type_, "")
    subject = f"{emoji} {type_}({scope}): {message}"

    parts = [subject]

    if body or trailers:
        parts.append("")  # blank line after subject

    if body:
        parts.append(body)

    if trailers:
        if body:
            parts.append("")  # blank line between body and trailers
        # Process trailers with auto-issue creation
        for t in trailers:
            key, _, value = t.partition("=")
            if key == "Next":
                issue_ref = _auto_create_issue(value)
                if issue_ref:
                    value = f"{value} {issue_ref}"
            elif key == "Resolved-Next":
                _auto_close_issue(value)
            parts.append(f"{key}: {value}")

    # Co-author
    parts.append("")
    parts.append("Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>")

    return "\n".join(parts)


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretty git commit for git-memory")
    parser.add_argument("type", help="Commit type (feat, fix, decision, memo, context, wip, ...)")
    parser.add_argument("scope", help="Scope (auth, api, forms, ...)")
    parser.add_argument("message", help="Commit message (subject line)")
    parser.add_argument("--body", default=None, help="Commit body text")
    parser.add_argument("--trailer", action="append", default=[], dest="trailers",
                        help="Trailer in KEY=VALUE format (repeatable)")
    parser.add_argument("--push", action="store_true", help="Push after commit")
    args = parser.parse_args()

    type_ = args.type
    if type_ not in EMOJIS:
        print(f"{RED}{BOLD}Error{RESET}: unknown type '{type_}'. Valid: {', '.join(sorted(EMOJIS))}", file=sys.stderr)
        sys.exit(1)

    # Build message
    msg = build_commit_message(type_, args.scope, args.message, args.body, args.trailers)

    # Build git command
    git_args = ["commit"]
    if type_ in MEMORY_TYPES:
        git_args.append("--allow-empty")
    git_args += ["-m", msg]

    # Execute
    result = subprocess.run(
        ["git"] + git_args,
        capture_output=True, text=True, timeout=15,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        print(f"{RED}{BOLD}Error{RESET}: git commit failed: {stderr}", file=sys.stderr)
        sys.exit(1)

    # Extract SHA from output (format: "[branch SHA] message")
    sha = "?"
    stdout = result.stdout.strip()
    if "[" in stdout and "]" in stdout:
        bracket = stdout[stdout.index("[") + 1:stdout.index("]")]
        parts = bracket.split()
        if len(parts) >= 2:
            sha = parts[-1][:7]

    # Pretty output
    emoji = EMOJIS.get(type_, "")
    color = TYPE_COLORS.get(type_, RESET)
    print(f"  {emoji} {color}{BOLD}{type_}{RESET}{DIM}({args.scope}){RESET}: {args.message} {DIM}[{sha}]{RESET}")

    # Push if requested
    if args.push:
        push_result = subprocess.run(
            ["git", "push"],
            capture_output=True, text=True, timeout=30,
        )
        if push_result.returncode == 0:
            print(f"  {DIM}↑ pushed{RESET}")
        else:
            print(f"  {RED}push failed: {push_result.stderr.strip()}{RESET}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
