#!/usr/bin/env python3
"""PreToolUse hook: skill gate + project memory injection for subagent spawns.

Purpose
-------
Intercepts calls that spawn a subagent (the live payload uses tool_name
"Agent"; "Task" is also accepted for robustness). For recognised crew
workers, two things happen in order:

1. Skill gate (issue #68): if the prompt doesn't already carry the domain
   skill marker and one or more domain skills clear the gate threshold (see
   _find_gate_skills), the spawn is DENIED with instructions to re-invoke
   with the skill block(s) pasted at the top of the prompt. This is the
   only case where this hook denies.
2. Memory injection: when the spawn is allowed (no gate-worthy skill match,
   or the marker is already present), a relevant recall block is appended to
   the prompt as a clearly delimited footer, when one exists.

All other tool calls, and any agent not on the whitelist, pass through
unmodified.

Fail-open posture (CRITICAL)
-----------------------------
This hook MUST NEVER block a spawn due to its OWN failure. Any failure in
the skill gate — missing skill-search.py, subprocess timeout/crash,
malformed JSON, missing fields, or any other exception — is swallowed and
falls through to the memory-injection flow (never a deny). The same holds
for memory injection: JSON parse error, missing git, recall() exception,
missing tool_input fields, timeout from git operations, or any other
exception results in an unconditional allow with no updatedInput. The ONLY
condition that produces a deny is a clean, successful skill-gate match
(score >= threshold, marker absent) — every other path is allow.

I/O contract (Claude Code PreToolUse hook)
------------------------------------------
- Stdin:  JSON  {"tool_name": str, "tool_input": {...}}
- Stdout: JSON  {"hookSpecificOutput": {"hookEventName": "PreToolUse",
                                        "permissionDecision": "allow"|"deny",
                                        ["updatedInput": {...},]
                                        ["permissionDecisionReason": str]}}
- Exit 0 always.
"""

import json
import os
import subprocess
import sys
import traceback
from pathlib import Path

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

# ── Skill gate (issue #68) ───────────────────────────────────────────────
# Plugin root, derived from this hook's own location: hooks/ -> unmassk-toolkit/.
_PLUGIN_ROOT: Path = Path(__file__).resolve().parents[1]
_SKILL_SEARCH_SCRIPT: Path = _PLUGIN_ROOT / "scripts" / "skill-search.py"

# Marker the orchestrator pastes into the retried prompt. Its presence means
# a domain skill was already selected and injected for this task — the gate
# must not re-trigger (anti-loop).
_SKILL_MARKER: str = "[DOMAIN SKILL —"

# Same threshold as skill-search.py's own LOW_SCORE_THRESHOLD: below this,
# the match isn't confident enough to gate on.
_SKILL_SCORE_THRESHOLD: float = 1.5

# Any result at or above this score is confident enough to be gated on
# alongside others (multi-skill injection), not just the single top result.
_SKILL_CONFIDENT: float = 5.0

# Hard cap on how many skill blocks a single deny can list, even if more
# results clear _SKILL_CONFIDENT — keeps the reinvoke prompt bounded.
_SKILL_MAX: int = 3

# Subprocess timeout for the skill search — must not be able to hang a spawn.
_SKILL_SEARCH_TIMEOUT: float = 6.0

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


def _deny(reason: str) -> None:
    """Emit a deny with the given reason and exit 0.

    This is the ONLY output path in this hook that denies. It is only ever
    called from the skill gate on a clean, successful match — never from a
    failure branch.
    """
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
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


# ── Skill gate helpers ───────────────────────────────────────────────────

def _find_gate_skills(prompt: str) -> tuple[list[dict], str | None]:
    """Run skill-search.py against the prompt and select the skill set to gate on.

    Selection:
    - All results with score >= _SKILL_CONFIDENT are taken (a project may
      legitimately need more than one domain skill for a single task).
    - If none reach _SKILL_CONFIDENT, fall back to the single top result,
      but only if its score >= _SKILL_SCORE_THRESHOLD.
    - The resulting set is sorted by score descending and capped to
      _SKILL_MAX entries.

    Returns (skills, None) on a clean run — skills is [] when nothing
    cleared the threshold (this is "allow", not a failure) — or ([],
    error_str) when the search itself failed for any reason. The error_str
    form is what the caller uses to distinguish "no match" from "search
    broke" in the stderr breadcrumb — both are fail-open (never deny), but
    the message differs.

    Never raises: every failure mode (missing script, non-zero exit,
    timeout, malformed JSON, unexpected shape) is caught here.
    """
    try:
        if not _SKILL_SEARCH_SCRIPT.exists():
            return [], f"script not found: {_SKILL_SEARCH_SCRIPT}"

        result = subprocess.run(
            ["python3", str(_SKILL_SEARCH_SCRIPT), prompt, "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_SKILL_SEARCH_TIMEOUT,
        )
        if result.returncode != 0:
            return [], f"exit {result.returncode}: {(result.stderr or '').strip()[:200]}"

        data = json.loads(result.stdout)
        results = data.get("results") or []
        if not results:
            return [], None

        valid = [r for r in results if isinstance(r, dict) and "score" in r and "name" in r]
        if not valid:
            return [], "malformed results"

        confident = [r for r in valid if r.get("score", 0) >= _SKILL_CONFIDENT]
        if confident:
            selected = confident
        else:
            top = valid[0]
            selected = [top] if top.get("score", 0) >= _SKILL_SCORE_THRESHOLD else []

        selected.sort(key=lambda r: r.get("score", 0), reverse=True)
        return selected[:_SKILL_MAX], None

    except subprocess.TimeoutExpired:
        return [], f"timeout after {_SKILL_SEARCH_TIMEOUT}s"
    except json.JSONDecodeError as exc:
        return [], f"malformed JSON: {exc}"
    except Exception as exc:  # noqa: BLE001 — fail-open, any error must not deny
        return [], f"{type(exc).__name__}: {exc}"


def _build_skill_gate_message(skills: list[dict]) -> str:
    """Build the deny reason instructing the orchestrator to retry with the skill block(s).

    One [DOMAIN SKILL — ...] block per selected skill, highest score first
    (skills is expected pre-sorted by the caller). The instruction header
    switches to plural when there's more than one block.
    """
    plural = len(skills) > 1
    intro = (
        "⛔ SKILL GATE: antes de lanzar este agente, pega "
        + ("los siguientes bloques" if plural else "el siguiente bloque")
        + " AL PRINCIPIO de su prompt y reinvoca el agente (mismo subagent_type, mismo "
        "prompt + " + ("estos bloques delante):\n\n" if plural else "este bloque delante):\n\n")
    )
    blocks = [
        (
            "[DOMAIN SKILL — auto-selected for this task]\n"
            f"Skill: {skill.get('name', '')} (score {skill.get('score', 0):.1f})\n"
            f"Path: {skill.get('skill_md', '')}\n"
            "ACTION: Read this SKILL.md now before starting; it may point to "
            "scripts/references you must use."
        )
        for skill in skills
    ]
    return intro + "\n\n".join(blocks)


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

        # ── Skill gate (issue #68) ───────────────────────────────────────
        # Wrapped in its own try/except so a gate failure falls through to
        # the memory-injection flow below, never to a deny.
        try:
            if _SKILL_MARKER in prompt:
                sys.stderr.write("skill gate: allow (marcador presente)\n")
            else:
                skills, err = _find_gate_skills(prompt)
                if err is not None:
                    sys.stderr.write(f"skill gate: fail-open {err}\n")
                elif skills:
                    names = ", ".join(s.get("name", "") for s in skills)
                    sys.stderr.write(f"skill gate: deny {len(skills)} skills: {names}\n")
                    _deny(_build_skill_gate_message(skills))
                    return
                else:
                    sys.stderr.write("skill gate: allow (no match)\n")
        except Exception as exc:  # noqa: BLE001 — fail-open, never deny on our own failure
            try:
                sys.stderr.write(f"skill gate: fail-open {type(exc).__name__}: {exc}\n")
            except Exception:
                pass

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
