"""
bootstrap_commits -- Recent git commit history analysis for
bin/git-memory-bootstrap.py.

Split out of git-memory-bootstrap.py (was 953 LOC). This module owns the
"what does recent commit history tell us" concern (contributor count,
trailer adoption, scope usage) — kept separate from bootstrap_tree.py and
bootstrap_deps.py, which never touch git history.
"""

import re
from collections import defaultdict
from typing import Any

from git_helpers import run_git

SCAN_COMMITS = 20


def scan_recent_commits(depth: int = SCAN_COMMITS) -> dict[str, Any] | None:
    """Analyze recent commits for contributor count, trailer usage, and scopes.

    Returns:
        Dict with commit stats, or None if git log fails or is empty.
    """
    code, output = run_git([
        "log", "-n", str(depth),
        "--pretty=format:%h%x1f%s%x1f%b%x1f%at%x1f%an%x1e",
    ])
    if code != 0 or not output:
        return None

    commits: list[dict[str, Any]] = []
    authors: defaultdict[str, int] = defaultdict(int)
    has_trailers = 0
    trailer_re = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*:\s*.+$", re.MULTILINE)
    scope_re = re.compile(r"^\w+\(([^)]+)\)")

    for raw in output.split("\x1e"):
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.split("\x1f", 4)
        if len(parts) < 5:
            continue

        sha, subject, body, date, author = parts
        authors[author.strip()] += 1

        if trailer_re.search(body):
            has_trailers += 1

        # Extract scope
        scope = None
        m = scope_re.match(subject.strip())
        if m:
            scope = m.group(1)

        commits.append({
            "sha": sha.strip(),
            "subject": subject.strip(),
            "scope": scope,
            "date": date.strip(),
            "author": author.strip(),
        })

    return {
        "count": len(commits),
        "authors": dict(authors),
        "has_trailers": has_trailers,
        "recent": commits[:5],
    }
