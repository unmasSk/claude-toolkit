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
    # SEC-CRIT-NEW-01 pattern (Argus, mirrored from lib/boot_memory.py's
    # extract_memory()/extract_glossary(), issue #57): `-z` (NUL, \x00)
    # record boundaries instead of an embedded \x1e in the --pretty=format
    # string. A commit body CAN contain a literal \x1e byte -- str.split()-
    # ing on it let a single real commit forge an entire fake commit entry
    # (attacker-chosen sha/scope/date/author) in the "recent" list fed to
    # `git memory bootstrap --json`. A commit message can never contain a
    # raw NUL byte, so splitting on \x00 has no forgeable equivalent. \x1f
    # remains the FIELD separator within a single record.
    code, output = run_git([
        "log", "-n", str(depth), "-z",
        # %aI (not %at): this date is never parsed, only carried through to
        # bin/git-memory-bootstrap.py's --json output for presentation to
        # the user (see that script's own docstring). %aI gives a readable
        # ISO-8601 string; do not "fix" this back to a raw epoch digit
        # string -- a bare epoch is not presentable as-is, and this module
        # never parses the field, so there is no equivalent robustness
        # argument for %at here (see test_date_parsing_epoch_contract.py's
        # TestBootstrapCommitsDateFieldContract for the full reasoning).
        "--pretty=format:%h\x1f%s\x1f%b\x1f%aI\x1f%an",
        "--",
    ])
    if code != 0 or not output:
        return None

    commits: list[dict[str, Any]] = []
    authors: defaultdict[str, int] = defaultdict(int)
    has_trailers = 0
    trailer_re = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*:\s*.+$", re.MULTILINE)
    scope_re = re.compile(r"^\w+\(([^)]+)\)")

    for raw in output.split("\x00"):
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
