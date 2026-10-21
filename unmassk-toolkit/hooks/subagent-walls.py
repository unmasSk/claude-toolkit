#!/usr/bin/env python3
"""SubagentStart hook: hand every agent the project's walls.

Finds `.claude/project-memory/RESTRICTIONS.md` walking up from the payload's
`cwd` (nearest wins) and returns a heading plus every line starting with
`[R-` as additionalContext. Nothing to say: no output. Any failure: one line
on stderr, no output. Always exit 0.
"""

import json
import os
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402
force_utf8_streams()

_INDEX_REL = os.path.join(".claude", "project-memory", "RESTRICTIONS.md")
_WALL_PREFIX = "[R-"
_HEADING = "Project walls (restrictions) -- never break these:"


def _find_index(start):
    """Nearest RESTRICTIONS.md going up from `start`, or None."""
    current = os.path.abspath(start)
    while True:
        candidate = os.path.join(current, _INDEX_REL)
        if os.path.isfile(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _payload_cwd():
    """The payload's cwd; raises ValueError on any malformed input."""
    payload = json.loads(sys.stdin.read())
    cwd = payload.get("cwd") if isinstance(payload, dict) else None
    if not isinstance(cwd, str) or not cwd:
        raise ValueError("payload has no string 'cwd'")
    return cwd


def main():
    try:
        cwd = _payload_cwd()
    except Exception as exc:
        sys.stderr.write(f"subagent-walls: bad input, no walls given ({exc.__class__.__name__}: {exc})\n")
        return
    index = _find_index(cwd)
    if index is None:
        return
    try:
        with open(index, "rb") as f:
            text = f.read().decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        sys.stderr.write(f"subagent-walls: cannot read {index}, no walls given ({exc.__class__.__name__})\n")
        return
    walls = [line for line in text.split("\n") if line.startswith(_WALL_PREFIX)]
    if not walls:
        return
    out = {
        "hookSpecificOutput": {
            "hookEventName": "SubagentStart",
            "additionalContext": "\n".join([_HEADING, *walls]),
        }
    }
    sys.stdout.write(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
    sys.exit(0)
