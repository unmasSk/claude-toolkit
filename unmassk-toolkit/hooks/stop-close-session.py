#!/usr/bin/env python3
"""
Stop hook — close-session protocol reminder.

Fires at session end (Stop event) to remind Claude to run the
unmassk-close-session skill: flush uncommitted decisions, run adaptive
housekeeping (versioning/changelog/cleanup if the project has them), and
write the resume point to git-memory.

Coexistence: stop-dod-check.py handles auto-wip + context() commit.
This hook adds the higher-level close-session checklist *after* those
mechanics are addressed. Both hooks run; they are complementary.

Suppression: if no substantive activity occurred (no commits since last
context(), shallow or empty repo), the reminder is skipped to avoid noise.

Exit codes:
    0: Always. This hook never blocks.
"""

import os
import re
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import run_git, is_git_repo
from colors import YELLOW, RESET

# Number of commits to scan when checking for recent activity.
_ACTIVITY_SCAN_DEPTH = 20

# Commit types that count as "substantive" session work worth a close.
_SUBSTANTIVE_TYPES = frozenset([
    "feat", "fix", "refactor", "perf", "test", "build",
    "ci", "chore", "decision", "memo", "remember", "wip",
])


def _commits_since_last_context(depth: int = _ACTIVITY_SCAN_DEPTH) -> int:
    """Count commits since the most recent context() commit.

    Returns:
        Number of commits between HEAD and the last context() commit.
        Returns 0 if the repo is empty, a git error occurs, or no
        non-context commits exist since the last checkpoint.
        Returns `depth` if no context() commit is found within `depth`.
    """
    code, output = run_git(["log", f"-n{depth}", "--pretty=format:%s"])
    if code != 0 or not output:
        return 0

    count = 0
    for line in output.splitlines():
        subject = line.strip()
        cleaned = re.sub(r"^[^\w#]+", "", subject).strip().lower()
        if cleaned.startswith("context(") or cleaned.startswith("context:"):
            return count
        count += 1

    # No context() found in the scan window — treat all as uncommitted
    return count


def _has_substantive_commits(count: int) -> bool:
    """Check if any of the recent `count` commits are substantive work.

    Args:
        count: How many commits from HEAD to inspect.

    Returns:
        True if at least one commit type is in _SUBSTANTIVE_TYPES.
    """
    if count <= 0:
        return False

    code, output = run_git(["log", f"-n{count}", "--pretty=format:%s"])
    if code != 0 or not output:
        return False

    for line in output.splitlines():
        subject = line.strip()
        cleaned = re.sub(r"^[^\w#]+", "", subject).strip().lower()
        # Match conventional commit types: "feat(scope):" or "decision:"
        m = re.match(r"^([a-z]+)[\(:]", cleaned)
        if m and m.group(1) in _SUBSTANTIVE_TYPES:
            return True

    return False


def main() -> None:
    """Entry point. Never blocks — always exit 0."""
    if not is_git_repo():
        sys.exit(0)

    commits_since = _commits_since_last_context()

    # Suppress if nothing substantive happened since the last checkpoint.
    if not _has_substantive_commits(commits_since):
        sys.exit(0)

    msg = (
        f"\n{YELLOW}[close-session] This session has uncommitted work since the last context() checkpoint.{RESET}\n"
        f"{YELLOW}Run the unmassk-close-session protocol before ending:{RESET}\n"
        f"{YELLOW}  1. Flush uncommitted decisions → decision()/memo() commits with Why: trailers{RESET}\n"
        f"{YELLOW}  2. Housekeeping — version bump if shipped, changelog if present, remove scratch files{RESET}\n"
        f"{YELLOW}  3. Write resume point → context() commit with Next: trailer{RESET}\n"
        f"{YELLOW}The stop-dod-check hook handles the context() commit mechanics.{RESET}\n"
        f"{YELLOW}This checklist is the *content* layer on top of those mechanics.{RESET}"
    )
    print(msg, file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
