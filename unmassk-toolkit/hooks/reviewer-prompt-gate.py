#!/usr/bin/env python3
"""PreToolUse gate: reviewing lanes (cerberus, argus, yoda) get blind prompts.

Denies a launch whose prompt asks the reviewer to find/report problems, or
that lacks a line starting with `ASK:` (template in skills/unmassk-core/SKILL.md).
Fail-open: an internal error (bad JSON, missing key, regex bug) lets the launch
through but warns via `systemMessage`. A non-reviewer or non-string prompt stays silent.
"""

import json
import os
import re
import sys
import unicodedata

REVIEWERS = {"cerberus", "argus", "yoda"}

_VERB = (r"(?:find|finds|search for|look for|looking for|hunt for|report|reports|"
         r"list|identify|detect|encuentr\w*|busc\w*|report\w*|list\w*|detect\w*|identific\w*)")
_NOUN = (r"(?:issues?|bugs?|problems?|findings?|errors?|flaws?|defects?|vulnerabilit\w*|"
         r"fallos?|errores|error|problemas?|hallazgos?|defectos?|vulnerabilidades)")
_BIASING = re.compile(r"\b" + _VERB + r"\s+(?:\w+\s+){0,3}" + _NOUN + r"\b")
_QUOTED = re.compile(r"\"[^\"\n]*\"|“[^”\n]*”|‘[^’\n]*’|«[^»\n]*»|(?<!\w)'[^'\n]*'(?!\w)")
_ASK = re.compile(r"^ASK:", re.M)

REASON = ("Blind review: use the template in unmassk-core SKILL.md and do not ask for findings.\n"
          "Add a line starting with `ASK:` (review the whole artifact; \"Finding nothing is a valid answer\").")


def _fold(text):
    text = unicodedata.normalize("NFD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _violates(prompt):
    if not _ASK.search(prompt):
        return True
    return bool(_BIASING.search(_fold(_QUOTED.sub(" ", prompt))))


def main():
    data = json.loads(sys.stdin.buffer.read().decode("utf-8", errors="replace"))
    tool_input = data["tool_input"]
    who = tool_input["subagent_type"]
    if not isinstance(who, str) or who.rsplit(":", 1)[-1].lower() not in REVIEWERS:
        return
    prompt = tool_input.get("prompt")
    if not isinstance(prompt, str):
        return
    if _violates(prompt):
        sys.stdout.write(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": REASON}}))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # No permissionDecision on purpose: normal permission flow continues.
        try:
            sys.stdout.write(json.dumps({"systemMessage": (
                f"reviewer-prompt-gate failed ({type(exc).__name__}: {exc}); "
                "the launch was NOT checked")}))
            sys.stdout.flush()
        except OSError:
            # Broken pipe: the buffered text would fail again at exit (rc 120).
            os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
    sys.exit(0)
