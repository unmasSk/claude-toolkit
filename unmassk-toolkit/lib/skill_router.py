"""
skill_router — per-message protocol-skill trigger-phrase matcher.

Lightweight, cheap trigger-phrase table used by the UserPromptSubmit hook
(hooks/user-prompt-memory-check.py) to nudge Claude toward the right
protocol skill on EVERY message, not just the first. NOT a BM25/ranking
rebuild -- an 11-agent council explicitly rejected building anything
heavier than a static substring check for this. Purely informational:
never blocks, never denies.

Public interface:
    match_skills(prompt_text) -> list[str]

Every phrase in SKILL_TRIGGER_PHRASES is sourced from the matching skill's
own SKILL.md frontmatter `description` field (see skills/<name>/SKILL.md).
Exception: unmassk-core's description has no quoted trigger phrases (it is
"Loaded on session boot", not phrase-triggered) -- its entries are the
closest equivalent, drawn from its own distinctive nouns/verbs instead.
"""

SKILL_TRIGGER_PHRASES: dict[str, list[str]] = {
    "unmassk-core": [
        "agents", "delegate", "invoke workflows", "domain plugins", "standards",
    ],
    "unmassk-gitmemory": [
        "memory", "resume", "context", "decision", "memo", "remember",
        "what did we decide", "what's pending",
    ],
    "unmassk-flow": [
        "build a feature", "requires writing code", "implement",
        "add functionality", "non-trivial bug", "refactor",
    ],
    "unmassk-grill": [
        "grill me", "the request is ambiguous", "let's think this through",
    ],
    "unmassk-council": [
        "should i", "which option", "council this", "pressure-test this",
        "i'm torn", "help me decide", "open-ended idea generation", "prototype this",
    ],
    "unmassk-project-lifecycle": [
        "new project", "let's start", "continue", "where were we",
        "pick up the project", "scan this repo", "i inherited this codebase",
    ],
    "unmassk-audit": [
        "audit a module", "enterprise review", "launch audit",
    ],
    "unmassk-close-session": [
        "let's wrap up", "close the session", "we're done for today", "hand off",
    ],
    "unmassk-flow-stack": [
        "scaffold project", "which stack", "tech stack", "what framework",
    ],
}


def match_skills(prompt_text: str) -> list[str]:
    """Return the list of skill names whose trigger phrases appear in
    prompt_text, in SKILL_TRIGGER_PHRASES iteration order.

    Cheap case-insensitive substring check -- no stemming, no fuzzy
    matching, no scoring. Never raises: any unexpected input just yields no
    matches (fail-open, same discipline as the rest of the hook).
    """
    try:
        haystack = prompt_text.lower()
    except Exception:
        return []
    matched = []
    for skill, phrases in SKILL_TRIGGER_PHRASES.items():
        for phrase in phrases:
            if phrase in haystack:
                matched.append(skill)
                break
    return matched
