#!/usr/bin/env python3
"""
hooks_doc_sync -- regenerate (or verify) the generated "Active Hooks" table
in skills/unmassk-memory/SKILL.md from hooks/hooks.json.

That skill is loaded on every session start, so a hook list that has drifted
does not merely go stale: it makes Claude state a behaviour that does not
exist. The table between the `unmassk-active-hooks` markers is therefore
derived, never typed. The hand-written judgment that surrounds it (what a hook
means for you, which ones are known-dead) is not touched by this tool.

Usage:
  hooks_doc_sync.py            # verify only -- exit 1 if the table has drifted
  hooks_doc_sync.py --write    # regenerate the table in place

Exit codes:
  0: in sync (or successfully rewritten)
  1: drifted, could not be verified, or the rewrite was refused

All the logic lives in lib/hooks_doc.py -- the same module the doctor's
"Hooks doc" check reads, so the tool and the health report can never disagree.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from hooks_doc import compare_hooks_doc, write_hooks_block


def default_plugin_root() -> str:
    """The plugin root this script ships in (parent of bin/)."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main() -> int:
    """Entry point: verify by default, rewrite with --write."""
    parser = argparse.ArgumentParser(
        description="Keep SKILL.md's Active Hooks table derived from hooks.json.")
    parser.add_argument("--write", action="store_true",
                        help="Regenerate the table in place (default: verify only)")
    parser.add_argument("--plugin-root", default=None,
                        help="Plugin root to operate on (default: the one this script ships in)")
    args = parser.parse_args()
    plugin_root = args.plugin_root or default_plugin_root()

    if args.write:
        status, message = write_hooks_block(plugin_root)
        print(f"{status}: {message}")
        return 0 if status in ("written", "unchanged") else 1

    verdict = compare_hooks_doc(plugin_root)
    if verdict is None:
        # Nothing to compare: hooks.json declares nothing readable, or the
        # skill file is absent. Say so instead of reporting a clean bill.
        print("cannot verify: hooks.json is unreadable/empty, or SKILL.md is absent")
        return 1
    level, message = verdict
    print(f"{level}: {message}")
    return 0 if level == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
