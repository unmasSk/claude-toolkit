"""
managed_blocks.py — Single source of truth for all unmassk CLAUDE.md managed blocks.

Both session-start-crew.py (SessionStart hook) and git-memory-install.py
(installer) import this module so the 5 blocks never diverge.

Public API
----------
BLOCKS : list[dict]
    Ordered list of block definitions. Each dict has:
        begin (str)   — full BEGIN comment marker
        end   (str)   — full END comment marker
        body  (str)   — content between markers, no leading/trailing newline

upsert_managed_blocks(content: str) -> tuple[str, list[str]]
    Given the full text of a CLAUDE.md file, update-or-insert every block in
    BLOCKS while preserving all other content. Returns (new_content, log_lines).
    Idempotent: calling twice with the same content returns the same content.
    Order is preserved: blocks are written in BLOCKS order, appended if absent.
"""

from __future__ import annotations

import re


# ── Block definitions ─────────────────────────────────────────────────────
# Each block is reproduced EXACTLY from !new_skills/to_add_CLAUDE.md.
# Do NOT reformat; any whitespace change will trigger "block outdated" in upgrade.

BLOCKS: list[dict[str, str]] = [
    {
        "begin": "<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->",
        "end": "<!-- END unmassk-toolkit -->",
        "body": """\
## unmassk-toolkit Active

This project uses the **unmassk toolkit**.

**On every session start**, you MUST:
1. Read the `[git-memory-boot]` SessionStart output already in your context
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-gitmemory"` (TOOL CALL, not bash)
4. Read CALIBRATION.md: `${CLAUDE_PLUGIN_ROOT}/skills/unmassk-gitmemory/CALIBRATION.md`
5. Show the boot summary, then respond to the user

**On every user message**, the `[memory-check]` hook fires. Follow the CALIBRATION rules.

Never ask the user to run commands -- run them yourself.""",
    },
    {
        "begin": "<!-- BEGIN unmassk-protocols (managed block) -->",
        "end": "<!-- END unmassk-protocols -->",
        "body": """\
## Protocols

These protocols exist as skills. Detect the situation and load the matching skill (TOOL CALL). The list is always visible here so you never need to "remember" a protocol exists — pick from this menu.

**Project lifecycle** — detect by checking two facts: is there toolkit git-memory? is there existing code?

- git-memory + code → continuing our project → Skill `unmassk-project-lifecycle`
- code, no git-memory → external repo → Skill `unmassk-project-lifecycle`
- nothing → new project → Skill `unmassk-project-lifecycle`

(One skill handles all three; it routes internally. State the detected situation in one line before acting.)

**Before building something significant:**

- Ambiguous request, or a decision with stakes → Skill `unmassk-grill` (interrogate until the decision tree is resolved, before writing code)
- A real choice between options, or "help me decide / I'm torn" → Skill `unmassk-council` (5-advisor pressure-test; also covers brainstorming and prototyping)

**Ending a session:**

- Wrapping up / handoff → Skill `unmassk-close-session` (flush decisions to git-memory, write the resume point)

All protocol output persists to **git-memory**, never to `.md` files.""",
    },
    {
        "begin": "<!-- BEGIN unmassk-caveman (managed block) -->",
        "end": "<!-- END unmassk-caveman -->",
        "body": """\
## Communication mode: caveman (when active)

Ultra-compressed mode. Cuts tokens ~75% by dropping filler while keeping full technical accuracy. Activate when the user says "caveman", "be brief", "less tokens", or "/caveman". Stays active every response until "stop caveman" / "normal mode".

Drop: articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries, hedging. Fragments OK. Short synonyms. Abbreviate common terms (DB/auth/config/fn/impl). Arrows for causality (X -> Y). One word when one word is enough.

Technical terms exact. Code blocks unchanged. Errors quoted exact.

Pattern: `[thing] [action] [reason]. [next step].`
Yes: "Bug in auth middleware. Token expiry check uses `<` not `<=`. Fix:"

Drop caveman temporarily for: security warnings, irreversible-action confirmations, multi-step sequences where order matters, or when the user asks to clarify. Resume after.""",
    },
    {
        "begin": "<!-- BEGIN unmassk-communication (managed block) -->",
        "end": "<!-- END unmassk-communication -->",
        "body": """\
## Communication

- **Concise and plain.** No internal jargon (hook names, issue numbers, made-up terms). Long or overly technical responses lose the user.
- **Results, not process** — except when there's a failure, a risk, or a decision to make: then the "why" does matter.
- **Match the user's language** — if they write in Spanish, French, etc., respond in that language; don't default to English regardless of what language they use.
- **Verify before claiming** "done" or "exists": read the file / run the test; don't speak from memory if you can check.
- **Confirm before structural changes** (CLAUDE.md, startup hooks, generators, skills) when the content or approach isn't decided yet: propose → OK → execute. Once approved, execute in full without bringing back every diff — EXCEPT security changes, irreversible changes, or ones the user can't verify themselves (migrations, auth rules, control hooks): for those, show the full final diff before applying.
- **One thing at a time.** Don't open new work without closing the current one. A mid-task idea → candidate, not built. Nothing "NEW" without the user's approval.
- **Surface contradictions and gaps** honestly, even mid-task.""",
    },
    {
        "begin": "<!-- BEGIN unmassk-build-mode (managed block) -->",
        "end": "<!-- END unmassk-build-mode -->",
        "body": """\
## Build mode (you decide, before delegating)

Before running the Flow execute step, decide the build mode and tell the agents which one applies. The agents do not choose — you do.

- **Test-first** (TDD/BDD/ATDD) → for business logic, APIs, anything with clear rules where being wrong is costly. Order: Dante writes failing tests (the contract) → Ultron implements until they pass.
- **Linear** → for prototypes, exploration, throwaway code, or when the shape isn't clear yet. Order: Ultron implements → Dante tests after (Flow's normal Verify step).

Decision factors:
- Clear, testable behavior + matters if wrong → test-first
- Exploratory / "let me see it first" / disposable → linear
- Uncertain → test-first (the safer default for real code)

State the chosen mode in one line before delegating, and pass it to Ultron/Dante in their task prompt.""",
    },
]

# Convenience set of all begin markers for membership tests
_BEGIN_MARKERS: set[str] = {b["begin"] for b in BLOCKS}


# ── Legacy block patterns to remove before upsert ────────────────────────

_LEGACY_PATTERNS: list[tuple[str, str]] = [
    (r"<!-- BEGIN unmassk-gitmemory.*?<!-- END unmassk-gitmemory -->", "unmassk-gitmemory"),
    (r"<!-- BEGIN unmassk-crew.*?<!-- END unmassk-crew -->", "unmassk-crew"),
    (r"<!-- BEGIN claude-git-memory.*?<!-- END claude-git-memory -->", "claude-git-memory"),
]


# ── Core logic ────────────────────────────────────────────────────────────

def _render_block(block: dict[str, str]) -> str:
    """Render a full block string including markers."""
    return f"{block['begin']}\n{block['body']}\n{block['end']}"


def upsert_managed_blocks(content: str) -> tuple[str, list[str]]:
    """Update-or-insert all 5 managed blocks into CLAUDE.md content.

    Args:
        content: The current text of CLAUDE.md (may be empty string for new files).

    Returns:
        (new_content, log_lines) where log_lines describes what changed.
    """
    log: list[str] = []

    # 1. Remove legacy blocks first
    for pattern_str, name in _LEGACY_PATTERNS:
        pattern = re.compile(pattern_str, re.DOTALL)
        if pattern.search(content):
            content = pattern.sub("", content)
            content = re.sub(r"\n{3,}", "\n\n", content).strip()
            if content:
                content += "\n"
            log.append(f"removed legacy {name} block")

    # 2. For each block: replace if present, collect missing ones
    missing_blocks: list[dict[str, str]] = []

    for block in BLOCKS:
        begin = block["begin"]
        end = block["end"]
        rendered = _render_block(block)

        if begin in content:
            # Block present — update in place (regex replace begin…end)
            pattern = re.compile(
                re.escape(begin) + r".*?" + re.escape(end),
                re.DOTALL,
            )
            new_content = pattern.sub(rendered, content)
            if new_content != content:
                log.append(f"updated {begin}")
            else:
                log.append(f"up-to-date {begin}")
            content = new_content
        else:
            missing_blocks.append(block)

    # 3. Append missing blocks in order (already ordered by BLOCKS)
    if missing_blocks:
        base = content.rstrip()
        for block in missing_blocks:
            base += "\n\n" + _render_block(block)
            log.append(f"appended {block['begin']}")
        content = base + "\n"

    return content, log


def all_blocks_present(content: str) -> bool:
    """Return True if all 5 BEGIN markers are present in content."""
    return all(b["begin"] in content for b in BLOCKS)


def any_block_outdated(content: str) -> bool:
    """Return True if any block's current rendered form differs from expected."""
    for block in BLOCKS:
        begin = block["begin"]
        end = block["end"]
        if begin not in content:
            return True  # missing counts as outdated
        pattern = re.compile(
            re.escape(begin) + r"(.*?)" + re.escape(end),
            re.DOTALL,
        )
        m = pattern.search(content)
        if not m:
            return True
        current_body = m.group(1).strip()
        if current_body != block["body"].strip():
            return True
    return False
