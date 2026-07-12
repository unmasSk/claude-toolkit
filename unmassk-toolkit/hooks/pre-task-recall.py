#!/usr/bin/env python3
"""PreToolUse hook: inject relevant project memory and domain skills into
Task (subagent) spawns.

Purpose
-------
Intercepts calls to the Task tool. When the spawned subagent is one of the
recognised crew workers, TWO independent signals are computed for its
prompt:

  1. git-memory recall — prior decisions/notes relevant to the prompt.
  2. domain-skill search — the best-matching domain skill (BM25 over
     .skillcat files), injected only when its score clears a confidence
     gate.

Either, both, or neither may fire. Each is rendered as its OWN clearly
delimited block and concatenated onto the prompt — the skill block is never
nested inside the memory footer. All other tool calls pass through
unmodified.

Fail-open posture (CRITICAL)
-----------------------------
This hook MUST NEVER block or deny a Task spawn. Any failure — JSON parse
error, missing git, recall() exception, skill-search subprocess timeout or
malformed output, missing tool_input fields, or any other exception — is
swallowed and results in an unconditional allow with no updatedInput (or a
partial injection from whichever signal did succeed). A broken recall or
broken skill search cannot be allowed to paralyse the orchestrator. No
permissionDecision: "deny" is ever emitted.

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
import subprocess
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

# ── Domain-skill search ──────────────────────────────────────────────────
# scripts/ sits one level under unmassk-toolkit/, same depth as hooks/.

_SCRIPTS_DIR = os.path.join(os.path.dirname(_HOOKS_DIR), "scripts")
_SKILL_SEARCH_SCRIPT = os.path.join(_SCRIPTS_DIR, "skill-search.py")

# Subprocess budget — comfortably inside the hook's overall ~10s ceiling.
_SKILL_SEARCH_TIMEOUT: int = 6

# Mirrors scripts/skill-search.py's own LOW_SCORE_THRESHOLD. Kept as a
# separate constant (rather than importing the hyphenated module) so a
# skill-search subprocess failure can never take this hook down with it;
# the two are expected to move together and both are named, not magic.
_SKILL_LOW_SCORE_THRESHOLD: float = 1.5

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
        ensure_ascii=False,
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
        ensure_ascii=False,
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


# ── Domain-skill block ───────────────────────────────────────────────────
# Its own channel, own imperative header — deliberately NEVER nested inside
# the [PROJECT MEMORY] footer above (that footer is tagged low-priority
# reference context; diluting the skill's "read this now" instruction into
# it would bury the action). Contains no "---" so it never collides with
# the memory footer's own delimiter pair when both are concatenated.

_SKILL_BLOCK_TEMPLATE = (
    "\n\n[DOMAIN SKILL — auto-selected for this task.]\n"
    "Skill: {name} (score {score:.1f})\n"
    "Path: {skill_md}\n"
    "ACTION: Read this SKILL.md now; it may point to scripts/references you must use.\n"
)


def _build_skill_block(skill: dict) -> str:
    """Render the domain-skill injection block for a matched skill dict."""
    return _SKILL_BLOCK_TEMPLATE.format(
        name=skill["name"], score=skill["score"], skill_md=skill["skill_md"]
    )


def _search_skill(prompt: str) -> dict | None:
    """Run skill-search.py as a subprocess and return the top match as
    {"name", "score", "skill_md"} when it clears the confidence gate, else
    None.

    Fail-open on every possible failure mode — subprocess timeout/spawn
    error, non-zero exit, malformed JSON, missing/invalid fields, or a
    low-confidence score. Every branch (success, low-score skip, failure)
    writes exactly one stderr breadcrumb so a broken searcher is never a
    silent no-op.
    """
    try:
        proc = subprocess.run(
            [sys.executable, _SKILL_SEARCH_SCRIPT, prompt, "--json"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=_SKILL_SEARCH_TIMEOUT,
        )
    except Exception as exc:
        try:
            sys.stderr.write(
                f"pre-task-recall: skill-search subprocess failed ({exc!r}); "
                "skipping skill injection\n"
            )
        except Exception:
            pass
        return None

    if proc.returncode != 0:
        try:
            sys.stderr.write(
                f"pre-task-recall: skill-search exited {proc.returncode}; "
                "skipping skill injection\n"
            )
        except Exception:
            pass
        return None

    try:
        payload = json.loads(proc.stdout)
        results = payload.get("results") or []
    except Exception:
        try:
            sys.stderr.write(
                "pre-task-recall: skill-search returned malformed JSON; "
                "skipping skill injection\n"
            )
        except Exception:
            pass
        return None

    if not results:
        try:
            sys.stderr.write("pre-task-recall: skill-search returned no results\n")
        except Exception:
            pass
        return None

    top = results[0]
    try:
        score = float(top.get("score"))
    except (TypeError, ValueError):
        try:
            sys.stderr.write(
                "pre-task-recall: skill-search top result missing/invalid score; "
                "skipping skill injection\n"
            )
        except Exception:
            pass
        return None

    name = top.get("name")
    skill_md = top.get("skill_md")
    if not name or not skill_md:
        try:
            sys.stderr.write(
                "pre-task-recall: skill-search top result missing name/skill_md; "
                "skipping skill injection\n"
            )
        except Exception:
            pass
        return None

    if score < _SKILL_LOW_SCORE_THRESHOLD:
        try:
            sys.stderr.write(
                f"pre-task-recall: skill '{name}' scored {score} < "
                f"{_SKILL_LOW_SCORE_THRESHOLD}, skipping skill injection\n"
            )
        except Exception:
            pass
        return None

    try:
        sys.stderr.write(f"pre-task-recall: injecting skill '{name}' (score {score})\n")
    except Exception:
        pass
    return {"name": name, "score": score, "skill_md": skill_md}


# ── Main ─────────────────────────────────────────────────────────────────

def main() -> None:
    try:
        raw = sys.stdin.read(_STDIN_READ_LIMIT)
        hook_input = json.loads(raw)

        tool_name = hook_input.get("tool_name", "")

        # Only intercept Task calls.
        if tool_name != "Task":
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

        # Two INDEPENDENT signals — neither gates the other. A task with no
        # relevant memory (a brand-new task, exactly where a domain skill
        # matters most) must still be able to receive a skill block, and
        # vice versa.

        # Signal 1 — git-memory recall. recall() returns '' when nothing
        # matches; an exception here degrades to "no memory match" rather
        # than aborting the skill-search signal below.
        try:
            memory_block = recall(prompt, limit=_RECALL_LIMIT)
        except Exception:
            try:
                sys.stderr.write("pre-task-recall: recall() failed:\n")
                sys.stderr.write(traceback.format_exc())
            except Exception:
                pass
            memory_block = ""

        # Signal 2 — domain-skill search. Fully self-contained fail-open;
        # never raises, logs its own outcome on every branch.
        skill = _search_skill(prompt)

        if not memory_block and not skill:
            try:
                sys.stderr.write(
                    "pre-task-recall: no memory match and no skill match -- passthrough\n"
                )
            except Exception:
                pass
            _allow_passthrough()
            return

        # Combine — skill block first (own header, own channel), memory
        # footer last (its own trailing '---' stays the end of the prompt).
        # Never nested inside each other.
        updated_prompt = prompt
        if skill:
            updated_prompt += _build_skill_block(skill)
        if memory_block:
            updated_prompt = _build_prompt(updated_prompt, memory_block)

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
