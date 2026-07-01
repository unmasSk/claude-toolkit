#!/usr/bin/env python3
"""
git-memory-recall — Search git memory by query text.

Scans commits of type decision/memo/remember and returns a ranked,
deduplicated block of matching entries.

Usage:
  git-memory-recall.py "<query>" [--limit N] [--scope SCOPE]

Examples:
  git-memory-recall.py "memoria"
  git-memory-recall.py "auth JWT" --limit 5
  git-memory-recall.py "plugin" --scope plugin/recall

Limit behavior:
  The CLI rejects --limit values < 1 with exit code 1.
  The recall() library function clamps limit < 1 to 1 instead of raising.
  This intentional divergence means the CLI is strict (user-facing) while
  the library is lenient (programmatic callers). Both are tested.

Exit codes:
  0: OK (even if no results)
  1: Error
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))

from recall import recall


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Search git memory by query text.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("query", help="Search query (natural language)")
    parser.add_argument(
        "--limit", type=int, default=8,
        help="Maximum number of results (default: 8)",
    )
    parser.add_argument(
        "--scope", default=None,
        help="Filter to entries whose scope starts with this prefix (e.g. plugin/recall)",
    )
    args = parser.parse_args()

    if args.limit < 1:
        print("Error: --limit must be >= 1", file=sys.stderr)
        sys.exit(1)

    result = recall(args.query, limit=args.limit, scope=args.scope)

    if result:
        print(result)
    else:
        print("(no matches)")


if __name__ == "__main__":
    main()
