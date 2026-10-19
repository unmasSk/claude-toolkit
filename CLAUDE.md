# claude-toolkit

Bex's personal tool: the ground every one of his projects runs on. It is not a public product; the only thing that counts is that it works perfectly for him. Python 3 (standard library only in the core), Claude Code hooks and Markdown skills; several plugins (`unmassk-toolkit`, `unmassk-media`, `unmassk-trading`…) published in its own marketplace.

## What security and tests are for here

- **There is no external attacker.** Every defence built for hostile repositories (control-byte injection, booby-trapped links, malicious input, anti-exploit hardening) is dead weight: don't build it, and retire what exists. A finding about hostile input is surplus here.
- **What matters, and comes first: the system must not harm itself.** Memory lost or corrupted, a write in the wrong place, data lost to an internal failure or across sessions and machines, a failure that passes silently.
- **A test is justified only if it proves that**, and only if it compares two things written separately. A test that simulates an attacker is cut.
- **`unmassk-standards` is this project's yardstick**: generic, on the axis "the system against itself". Weights: integrity ×3, silent failure ×3, structure ×2, real verification ×2, maintainability ×1.
- **`unmassk-audit` is clean too**, with no fixed stack. Its 97 % coverage is a deliberate gate: an audit is stricter than an ordinary merge.

## How we work here

1. **There are four sources and no fifth:** the memory; the docs; the code and the diff, read or run, never remembered; and asking Bex. What comes from none of them is not filled in with your own judgement: a gap may be deliberate.
2. **Filter findings before handing them over:** only what happens in everyday use, ordered by real frequency. A list of eight where three are far-fetched gets none of the five good ones read.
3. **Test by running, through the door the user comes in by.** A «0 of 60» measured from inside came out «16 of 30» measured the way a person uses it.
4. **What must really be forbidden goes in a hook or in removing the tool, not in a text.** Moriarty once lost the barrier against touching code: it rested on his not having the tool, not on being written.
5. **When Bex asks to stop telling him something, it is literal.** No reasonable exception you think of applies; if a case seems worth telling, ask.
6. **Orchestrate: never make Bex decide the split of agents or the order.** If it is unclear, write it down and run it. «Solo tienes que orquestar, coño.»
7. **Don't get nervous.** On a minor incident, fix it and go on; no four-message operation over two temporary files.
8. **An out-of-date document never stops work already done.** If a document says something is open and the code says it is closed, the code wins: fix the document and go on. It once cost a whole session.

## Commands

- Tests while writing code: only the touched module's, by file or folder: `python3 -m pytest unmassk-toolkit/tests/test_managed_blocks.py -q` or `python3 -m pytest unmassk-toolkit/tests/memory -q`. The whole suite runs in CI on release, never by hand; report the rest only when it fails.

## Where this repo departs from the usual

- Project memory is commits (`gitmem`), never files. How it works today is read in one place: `unmassk-toolkit/skills/unmassk-memory/`.
- `gitmem work` and `wip` add `[skip ci]` to working commits, so they start no CI run.

## Traps

- The blocks below, between the `unmassk` markers, are rewritten by the generator at every session start: change them in `unmassk-toolkit/lib/managed_blocks.py`, never by hand here, and never write your own text inside the markers (a first version written there was wiped without trace).
- The discipline layer of `unmassk-trading` is copied byte for byte from someone else's MIT repository: don't touch it (`unmassk-trading/CREDITS.md` says why).
- `docs/deprecated/` tells why things are as they are, but does not describe the present and is not maintained: if it clashes with the code, the code wins.

## Read it when…

- `unmassk-toolkit/skills/unmassk-memory/` — before changing anything in the memory system.
- `unmassk-trading/CREDITS.md` — before touching anything in `unmassk-trading`.
- `docs/deprecated/` — only to learn why something was decided, never how it works today.

## Skills by task

- Publishing a version → this repository's `release` skill. Here, and only here, the session close publishes; it is not in the close-session skill on purpose: there it would be an order to publish in every project.

<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->
## unmassk-toolkit Active

This project uses the **unmassk toolkit**. Its memory lives in git, and it is
what you know about this project -- not a log you may consult.

The owner's rules below bind from the first message:

@.claude/project-memory/rules.md

**On every session start**, you MUST:
1. Read the boot report whose path the `[memory]` lines of the session
   start give you: the last Next, every blocker, every restriction, the
   counts and the checks. If no such line or no report arrived, the boot
   failed: tell the user so in your first line
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-memory"` (TOOL CALL, not bash)
4. Tell the user the menu of the day, then respond

**Four rules that hold even when no skill is loaded:**
- Memory is a commit. Never write it into a file.
- The indexes and the zone list are written by the commands. Never by hand.
- A restriction is retired by asking the user, never on your own judgement — unless you have checked that the piece it describes no longer exists anywhere (not just moved or renamed): then it is retired in the same act, and said.
- Never ask the user to run a command -- you run it.
<!-- END unmassk-toolkit -->

<!-- BEGIN unmassk-protocols (managed block) -->
## Protocols — pick the skill by the situation (TOOL CALL)

- Start, continue or scan a project → `unmassk-project-lifecycle` (state the situation in one line before acting)
- Choose a stack or scaffold a new project → `unmassk-scaffolding`
- Ambiguous request, or a decision with stakes → `unmassk-grill`
- Choose between options, or brainstorm and prototype → `unmassk-council`
- Build, fix a non-trivial bug or refactor → `unmassk-flow` (before delegating you decide the build mode: the skill says how)
- Audit existing code against standards → `unmassk-audit`
- What repeats every session with no skill ("protocolo marmota") → `unmassk-groundhog` (a skill is created only with the owner's approval)
- Close the session → `unmassk-close-session`

All protocol output goes to **memory**, never to `.md` files.
<!-- END unmassk-protocols -->

<!-- BEGIN unmassk-communication (managed block) -->
## Communication

- **Concise and plain.** Match the user's language. No internal jargon (hook names, made-up terms) or filler; task, phase and step numbers are fine (`#101, 1.2`): results, not process (except for a failure, a risk or a decision). Answer the minimum that resolves it; one sentence is usually enough. Don't repeat back what the user said, don't re-justify or re-list what was already accepted; when something is corrected, fix it and move on.
- **Verify before claiming** "done" or "exists": read the file or run the test. Don't assume: if you haven't read it, say you don't know and go check.
- **Structural changes** (CLAUDE.md, startup hooks, generators, skills) not yet decided: propose → OK → execute in full. Security changes, irreversible ones, or ones the user can't verify: show the full final diff before applying.
- **One thing at a time:** don't open new work without closing the current one; a mid-task idea is a candidate, not built; nothing new without the user's approval.
- **Surface contradictions and gaps**, even mid-task.
<!-- END unmassk-communication -->
