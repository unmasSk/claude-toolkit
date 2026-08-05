"""
managed_blocks.py — Single source of truth for all unmassk CLAUDE.md managed blocks.

Both session-start-crew.py (SessionStart hook) and git-memory-install.py
(installer) import this module so the blocks never diverge.

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

This project uses the **unmassk toolkit**. Its memory lives in git, and it is
what you know about this project -- not a log you may consult.

**On every session start**, you MUST:
1. Read the session-start briefing already in your context: the last Next,
   every blocker, every restriction, the counts and the checks
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-memory"` (TOOL CALL, not bash)
4. Tell the user the menu of the day, then respond

**Four rules that hold even when no skill is loaded:**
- Memory is a commit. Never write it into a file.
- The indexes and the zone list are written by the commands. Never by hand.
- A restriction is retired by asking the user, never on your own judgement.
- Never ask the user to run a command -- you run it.""",
    },
    {
        "begin": "<!-- BEGIN unmassk-protocols (managed block) -->",
        "end": "<!-- END unmassk-protocols -->",
        "body": """\
## Protocols

These protocols exist as skills. Detect the situation and load the matching skill (TOOL CALL). The list is always visible here so you never need to "remember" a protocol exists — pick from this menu.

**Project lifecycle** — detect by checking two facts: does this project have memory? is there existing code?

- memory + code → continuing our project → Skill `unmassk-project-lifecycle`
- code, no memory → external repo → Skill `unmassk-project-lifecycle`
- nothing → new project → Skill `unmassk-project-lifecycle`

(One skill handles all three; it routes internally. State the detected situation in one line before acting.)

**Starting a brand new project (scaffolding, tech stack, boilerplate):**

- Scaffold, initialize, or create a new project / decide the tech stack → Skill `unmassk-scaffolding` (IDE-grade scaffolding wizard, 70+ project types)

**Before building something significant:**

- Ambiguous request, or a decision with stakes → Skill `unmassk-grill` (interrogate until the decision tree is resolved, before writing code)
- A real choice between options, or "help me decide / I'm torn" → Skill `unmassk-council` (5-advisor pressure-test; also covers brainstorming and prototyping)

**Building a feature, fixing a non-trivial bug, or refactoring:**

- Build a feature, implement, add functionality, fix a non-trivial bug, or refactor → Skill `unmassk-flow` (8-step creative pipeline, idea to shipped code)

**Auditing existing code against enterprise standards:**

- Audit a module or an enterprise review request → Skill `unmassk-audit` (14-step structured audit, weighted score out of 110)

**Ending a session:**

- Wrapping up / handoff → Skill `unmassk-close-session` (write the Next, update the plan, prune walls, register blockers)

All protocol output persists to **memory**, never to `.md` files.""",
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
- **Surface contradictions and gaps** honestly, even mid-task.
- **NOT YAPPING.** Zero filler. Don't repeat back what the user just said, don't re-justify, don't re-list points already accepted. When something is corrected, fix it and move on. Answer the minimum that resolves it, then act — one sentence is usually enough.
- **Don't assume.** If you haven't read it, don't state it. Verify against the file, the code, or memory — or say you don't know and go check. Never fill a gap with a guess dressed as fact.""",
    },
    {
        "begin": "<!-- BEGIN unmassk-build-mode (managed block) -->",
        "end": "<!-- END unmassk-build-mode -->",
        "body": """\
## Build mode (you decide, before delegating)

Before running the Execute step of `unmassk-flow` (the build pipeline skill), decide the build mode and tell the agents which one applies. The agents do not choose — you do.

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
    (r"<!-- BEGIN unmassk-caveman.*?<!-- END unmassk-caveman -->", "unmassk-caveman"),
]


# ── Core logic ────────────────────────────────────────────────────────────

def _render_block(block: dict[str, str]) -> str:
    """Render a full block string including markers."""
    return f"{block['begin']}\n{block['body']}\n{block['end']}"


def upsert_managed_blocks(content: str) -> tuple[str, list[str]]:
    """Update-or-insert all managed blocks into CLAUDE.md content.

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

        pattern = re.compile(
            re.escape(begin) + r".*?" + re.escape(end),
            re.DOTALL,
        )
        match = pattern.search(content)

        if match:
            # Block present with both markers — update in place if stale.
            # DEUDA.md #15 (real incident 2026-08-02): whatever currently
            # sits between the markers is captured BEFORE it's overwritten,
            # regardless of whether it's an old canonical body or hand-
            # written content the function never produced itself — from
            # here, the two are indistinguishable, and both are about to be
            # destroyed. The single output channel is this log line, so the
            # full previous text is embedded verbatim (never summarized or
            # truncated) — that's what makes it recoverable instead of just
            # "announced as lost".
            old_body = match.group(0)[len(begin):-len(end)].strip("\n")
            new_content = pattern.sub(rendered, content)
            if new_content != content:
                if old_body.strip() == block["body"].strip():
                    # Only whitespace/formatting drifted; the body itself
                    # was already the canonical one -- nothing was lost, so
                    # dumping it back verbatim would just be noise on what
                    # is otherwise a routine, silent-safe regeneration.
                    log.append(f"updated {begin}")
                else:
                    log.append(
                        f"updated {begin} -- previous content between the "
                        f"markers was overwritten, recovered verbatim here: "
                        f"{old_body}"
                    )
            else:
                # Deliberately NOT "up-to-date {begin}": that phrase is
                # reserved for hooks/session-start-crew.py's single
                # aggregate message, printed only when truly nothing
                # changed anywhere. A per-block log line mixed into a run
                # that also regenerates a corrupted block must never let
                # "up to date" wording leak into that run's output (T1-A,
                # issue #63) — an unchanged block among changed ones is
                # still accurately reported, just without that phrase.
                log.append(f"unchanged {begin}")
            content = new_content
        elif begin in content:
            # Orphaned BEGIN: this block's own END marker is missing
            # somewhere in the whole document (deleted line, merge-conflict
            # resolution, editor auto-fix). begin…end can't match, so this
            # block is corrupted, never "up to date" — it must be
            # regenerated, not silently accepted.
            #
            # Design constraint (issue #63, Moriarty T1-1 regression on
            # T1-A's own fix): a BEGIN with no END gives us NO reliable
            # signal of where the block actually ends. Any deletion of the
            # surrounding text — up to the "next" managed block, up to a
            # blank line, whatever heuristic — risks eating real user
            # content that happens to sit in that gap (a completely normal
            # place for a user to write free-text notes). The ONLY byte we
            # can prove is corruption is the dangling BEGIN marker line
            # itself. So: remove exactly that line, nothing else, and
            # reinsert the full canonical block (BEGIN+body+END) in its
            # place — an in-place replacement never touches any byte
            # outside that single line, so it is always safe regardless of
            # what sits before or after it (trivially safe by
            # construction, not just "in this case").
            start = content.find(begin)
            line_end = content.find("\n", start)
            line_end = len(content) if line_end == -1 else line_end + 1
            content = content[:start] + rendered + "\n" + content[line_end:]
            log.append(f"regenerated {begin} (orphaned END marker)")
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
    """Return True if all BEGIN markers are present in content."""
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
