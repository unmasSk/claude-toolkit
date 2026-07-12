#!/usr/bin/env python3
"""PreToolUse hook: project memory injection for subagent spawns.

Purpose
-------
Intercepts calls that spawn a subagent (the live payload uses tool_name
"Agent"; "Task" is also accepted for robustness). For recognised crew
workers (see _WORKER_WHITELIST), a relevant recall block is appended to
the prompt as a clearly delimited footer, when one exists.

All other tool calls, and any agent not on the whitelist, pass through
unmodified.

Fail-open posture (CRITICAL)
-----------------------------
This hook MUST NEVER block a spawn due to its OWN failure. JSON parse
error, missing git, recall() exception, missing tool_input fields, timeout
from git operations, or any other exception results in an unconditional
allow with no updatedInput. This hook never denies.

I/O contract (Claude Code PreToolUse hook)
------------------------------------------
- Stdin:  JSON  {"tool_name": str, "tool_input": {...}}
- Stdout: JSON  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                        "permissionDecision": "allow",
                                        ["updatedInput": {...},]
                                        ["permissionDecisionReason": str]}}
- Exit 0 always.
"""

import json
import os
import sys
import traceback

# ── Path setup — lib/ must be importable ────────────────────────────────

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_LIB_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "lib")
if _LIB_DIR not in sys.path:
    sys.path.insert(0, _LIB_DIR)

from encoding_guard import force_utf8_streams  # noqa: E402  (import after sys.path mutation)
force_utf8_streams()

from recall import recall  # noqa: E402  (import after sys.path mutation)

_STDIN_READ_LIMIT = 1_048_576  # 1 MiB

# ── Worker whitelist ─────────────────────────────────────────────────────
# Inject memory ONLY for these crew agents. bilbo, gitto, and any unknown
# agents are excluded — they either don't benefit from memory injection or
# are orchestration-layer agents that should not see it.

_WORKER_WHITELIST: frozenset[str] = frozenset({
    "ultron",
    "dante",
    "cerberus",
    "argus",
    "moriarty",
    "house",
    "yoda",
    "alexandria",
})

# Number of memory entries to request from recall(). Named so it cannot
# silently diverge from intent; recall()'s own default is also 8.
_RECALL_LIMIT: int = 8

# ── Output helpers ───────────────────────────────────────────────────────


def _allow_passthrough() -> None:
    """Emit a bare allow and exit 0.

    Builds a fresh dict on every call so there is no shared module-level
    mutable state to accidentally corrupt.
    """
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
            }
        },
        sys.stdout,
    )
    sys.stdout.flush()


def _allow_with_injection(tool_input: dict, updated_prompt: str) -> None:
    """Emit an allow with the rewritten tool_input prompt."""
    updated_input = dict(tool_input)
    updated_input["prompt"] = updated_prompt
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "allow",
                "updatedInput": updated_input,
                "permissionDecisionReason": "git-memory recall injected",
            }
        },
        sys.stdout,
    )
    sys.stdout.flush()


# ── Normalisation ────────────────────────────────────────────────────────

def _normalize_agent(subagent_type: str) -> str:
    """Extract the agent name from a subagent_type string.

    Handles both 'ultron' and 'unmassk-toolkit:ultron' forms by taking
    the segment after the last ':' and lowercasing it. The .strip() also
    tolerates accidental whitespace around the name (e.g. 'namespace: ultron').
    """
    return subagent_type.rsplit(":", 1)[-1].strip().lower()


# ── Prompt footer ────────────────────────────────────────────────────────

_FOOTER_HEADER = (
    "\n\n---\n"
    "[PROJECT MEMORY — auto-recalled, relevant to your task]\n"
    "These are prior decisions, memos, and notes from the project. Treat them as\n"
    "reference context; the task you must execute is described ABOVE.\n"
    "\n"
)
_FOOTER_TAIL = "\n---"


def _build_prompt(original_prompt: str, memory_block: str) -> str:
    """Append the memory footer to the original prompt."""
    return original_prompt + _FOOTER_HEADER + memory_block + _FOOTER_TAIL


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        hook_input = json.loads(raw)

        tool_name = hook_input.get("tool_name", "")

        # Intercept subagent spawns. Live payloads use "Agent"; "Task" is
        # also accepted for robustness (older/alternate naming).
        if tool_name not in ("Agent", "Task"):
            _allow_passthrough()
            return

        tool_input = hook_input.get("tool_input") or {}

        # Extract required fields; pass through if absent or empty.
        subagent_type = tool_input.get("subagent_type", "")
        prompt = tool_input.get("prompt", "")

        if not prompt or not prompt.strip():
            _allow_passthrough()
            return

        # Whitelist check — normalise to handle 'namespace:agent' form.
        agent_name = _normalize_agent(subagent_type)
        if agent_name not in _WORKER_WHITELIST:
            _allow_passthrough()
            return

        # Query memory. recall() returns '' when nothing matches.
        try:
            memory_block = recall(prompt, limit=_RECALL_LIMIT)
        except Exception:
            try:
                sys.stderr.write(traceback.format_exc())
            except Exception:
                pass
            _allow_passthrough()
            return

        if not memory_block:
            _allow_passthrough()
            return

        # Inject memory into the prompt.
        updated_prompt = _build_prompt(prompt, memory_block)
        _allow_with_injection(tool_input, updated_prompt)

    except Exception:
        # Fail-open: any unhandled error must not block the spawn.
        # Write diagnostic to stderr (best-effort; a write failure must not
        # propagate — stderr is never the decision channel).
        try:
            sys.stderr.write(traceback.format_exc())
        except Exception:
            pass
        try:
            _allow_passthrough()
        except Exception:
            pass


if __name__ == "__main__":
    main()
