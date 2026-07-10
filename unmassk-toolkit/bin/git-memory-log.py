#!/usr/bin/env python3
"""
git-memory-log — Pretty git log for git-memory.

Prints recent commits with colored type indicators.

Usage:
  git-memory-log.py [N]          # last N commits (default 10)
  git-memory-log.py --all        # all memory commits (decision, memo, context)
  git-memory-log.py --type memo  # only memos

Exit codes:
  0: OK
  1: Error
"""

import argparse
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()
from parsing import sanitize_trailer_value

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
BLUE = "\033[34m"
MAGENTA = "\033[35m"

CYAN = "\033[36m"

TYPE_COLORS = {
    "decision": YELLOW, "memo": BLUE, "context": GREEN,
    "remember": CYAN,
    "feat": MAGENTA, "fix": MAGENTA, "refactor": MAGENTA,
    "perf": MAGENTA, "test": MAGENTA, "docs": MAGENTA,
    "chore": MAGENTA, "ci": MAGENTA, "wip": DIM,
}

# Pattern to parse: "emoji type(scope): message"
SUBJECT_RE = re.compile(r"^(.+?)\s+(feat|fix|refactor|perf|test|docs|chore|ci|wip|context|decision|memo|remember)\(([^)]+)\):\s*(.+)$")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pretty git log for git-memory")
    parser.add_argument("count", nargs="?", type=int, default=10, help="Number of commits (default 10)")
    parser.add_argument("--all", action="store_true", help="Show only memory commits (decision, memo, context)")
    parser.add_argument("--type", dest="filter_type", default=None, help="Filter by commit type")
    args = parser.parse_args()

    # Validate count before passing it to git
    if not args.all and args.count <= 0:
        print(f"Error: count must be >= 1, got {args.count}", file=sys.stderr)
        sys.exit(1)

    # Get commits
    n = args.count if not args.all else 100
    result = subprocess.run(
        ["git", "log", f"-n{n}", "--pretty=format:%h %s"],
        capture_output=True, timeout=15,
    )

    if result.returncode != 0:
        print(f"Error: git log failed", file=sys.stderr)
        sys.exit(1)

    # SEC-CRIT-16 (issue #59, Argus): the previous `text=True` (no
    # `newline=` kwarg) let Python's universal-newlines decoding silently
    # translate a raw `\r` embedded mid-subject into `\n` before the
    # `.split("\n")` below ever ran -- splitting ONE real "sha subject"
    # line into two, the second fragment carrying no real sha, so
    # `sha = line[:7]` below would manufacture a phantom sha from
    # attacker-controlled subject text and render a fabricated extra
    # commit entry indistinguishable from a real one. bytes.decode()
    # performs no newline translation, so a `\r` git actually wrote stays
    # a `\r` and never fragments the line.
    try:
        stdout = result.stdout.decode("utf-8")
    except UnicodeDecodeError:
        print(f"Error: git log output was not valid UTF-8", file=sys.stderr)
        sys.exit(1)

    lines = stdout.strip().split("\n") if stdout.strip() else []

    print()
    shown = 0
    for line in lines:
        if not line.strip():
            continue

        sha = line[:7]
        subject = line[8:] if len(line) > 8 else ""

        m = SUBJECT_RE.match(subject)
        if m:
            emoji, type_, scope, msg = m.group(1), m.group(2), m.group(3), m.group(4)
        else:
            emoji, type_, scope, msg = "", "?", "", subject

        # Filters
        if args.all and type_ not in ("decision", "memo", "context", "remember"):
            continue
        if args.filter_type and type_ != args.filter_type:
            continue

        color = TYPE_COLORS.get(type_, RESET)
        if scope:
            # issue #57 round 2d (Argus SEC-CRIT-B): this script is the
            # MANDATORY substitute for `git log` (enforced by
            # pre-validate-commit-trailers.py), making its stdout the
            # guaranteed path any commit message reaches Claude's context
            # through -- sanitize the matched message the same way every
            # other commit-derived field in the codebase already is.
            #
            # issue #57 round 2e (decision e861680, Moriarty EXPLOIT-4):
            # that round only wrapped "msg" (group 4). "scope" (group 3)
            # and the emoji/prefix token (group 1) are also
            # attacker-controlled substrings of the matched subject and
            # were still printed raw -- a hostile ANSI escape placed
            # inside either one survived unsanitized. type_ (group 2)
            # needs no sanitization: it can only be one of the fixed
            # alternatives in SUBJECT_RE, never attacker-controlled text.
            print(f"  {sanitize_trailer_value(emoji)} {color}{BOLD}{type_}{RESET}{DIM}({sanitize_trailer_value(scope)}){RESET}: {sanitize_trailer_value(msg)} {DIM}[{sha}]{RESET}")
        else:
            print(f"  {DIM}[{sha}]{RESET} {sanitize_trailer_value(subject)}")

        shown += 1

    if shown == 0:
        print(f"  {DIM}(no commits found){RESET}")

    print()


if __name__ == "__main__":
    main()
