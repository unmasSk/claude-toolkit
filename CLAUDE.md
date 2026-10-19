# claude-toolkit

Bex's personal tool: the ground every one of his projects runs on. It is not a public product; the only thing that counts is that it works perfectly for him. Python 3 (standard library only in the core), Claude Code hooks and Markdown skills; several plugins (`unmassk-toolkit`, `unmassk-media`, `unmassk-trading`…) published in its own marketplace.

## What security and tests are for here

- **There is no external attacker.** Every defence built for hostile repositories (control-byte injection, booby-trapped links, malicious input, anti-exploit hardening) is dead weight: don't build it, and retire what exists. A finding about hostile input is surplus here.
- **What matters, and comes first: the system must not harm itself.** Memory lost or corrupted, a write in the wrong place, data lost to an internal failure or across sessions and machines, a failure that passes silently.
- **A test is justified only if it proves that**, and only if it compares two things written separately. A test that simulates an attacker is cut.
- **`unmassk-standards` is this project's yardstick**: generic, on the axis "the system against itself". Weights: integrity ×3, silent failure ×3, structure ×2, real verification ×2, maintainability ×1.
- **`unmassk-audit` is clean too**, with no fixed stack. Its 97 % coverage is a deliberate gate: an audit is stricter than an ordinary merge.
- **The nine agent cards are agnostic** and travel to every project: never judge them against this one. No attacker here says nothing about whether Argus's OWASP material should exist; the host project sets that.

## How we work here

1. **There are three sources and no fourth:** the docs; the code and the diff, read or run, never remembered; and asking Bex. What comes from none of them is not filled in with your own judgement: a gap may be deliberate.
2. **Delegating is mandatory, and so is verifying.** Without delegating the session runs out mid-work; delegated work arrives unverified, and one agent deleted sixteen files in one pass.
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
- `gitmem work` and `wip` add `[skip ci]` to every working commit; the release commit is the only one that runs CI.
- Cards, skills and prompts are written in English; Bex is shown them in Spanish, above all the diff.

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
- The CHANGELOG → always Alexandria, never the orchestrator.

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

- Build a feature, implement, add functionality, fix a non-trivial bug, or refactor → Skill `unmassk-flow` (eight parts, Triage to Close, idea to merged code)

**Auditing existing code against enterprise standards:**

- Audit a module or an enterprise review request → Skill `unmassk-audit` (14-step structured audit, weighted score out of 110)

**Hunting repetition (Groundhog Protocol):**

- What the project does or needs repeatedly, every session, that no skill covers yet — "protocolo marmota" → Skill `unmassk-groundhog` (inventory the repetition, check coverage, propose at most 1-3 skill candidates with cited evidence; a skill is created only after the owner approves)

**Ending a session:**

- Wrapping up / handoff → Skill `unmassk-close-session` (clean up, branches and issues, docs, write the Next)

All protocol output persists to **memory**, never to `.md` files.
<!-- END unmassk-protocols -->

<!-- BEGIN unmassk-communication (managed block) -->
## Communication

- **Concise and plain.** No internal jargon (hook names, made-up terms); task, phase and step numbers are fine (`#101, 1.2`). Long or overly technical responses lose the user.
- **Results, not process** — except when there's a failure, a risk, or a decision to make: then the "why" does matter. While work runs: one numbered line per agent or step that finishes, name and "done" only.
- **Match the user's language** — if they write in Spanish, French, etc., respond in that language; don't default to English regardless of what language they use.
- **Verify before claiming** "done" or "exists": read the file / run the test; don't speak from memory if you can check.
- **Confirm before structural changes** (CLAUDE.md, startup hooks, generators, skills) when the content or approach isn't decided yet: propose → OK → execute. Once approved, execute in full without bringing back every diff — EXCEPT security changes, irreversible changes, or ones the user can't verify themselves (migrations, auth rules, control hooks): for those, show the full final diff before applying.
- **One thing at a time.** Don't open new work without closing the current one. A mid-task idea → candidate, not built. Nothing "NEW" without the user's approval.
- **Surface contradictions and gaps** honestly, even mid-task.
- **NOT YAPPING.** Zero filler. Don't repeat back what the user just said, don't re-justify, don't re-list points already accepted. When something is corrected, fix it and move on. Answer the minimum that resolves it, then act — one sentence is usually enough.
- **Don't assume.** If you haven't read it, don't state it. Verify against the file, the code, or memory — or say you don't know and go check. Never fill a gap with a guess dressed as fact.
<!-- END unmassk-communication -->

<!-- BEGIN unmassk-build-mode (managed block) -->
## Build mode (you decide, before delegating)

At the end of Ideas in `unmassk-flow` (the build pipeline skill), decide the build mode and tell the agents which one applies. The agents do not choose — you do.

- **Test-first** (TDD/BDD/ATDD) → for business logic, APIs, anything with clear rules where being wrong is costly. Order: Dante writes failing tests (the contract) → Ultron implements until they pass.
- **Linear** → for prototypes, exploration, throwaway code, or when the shape isn't clear yet. Order: Ultron implements → Dante writes the tests for what was built, before that phase's review.

Decision factors:
- Clear, testable behavior + matters if wrong → test-first
- Exploratory / "let me see it first" / disposable → linear
- Uncertain → test-first (the safer default for real code)

State the chosen mode in one line before delegating, and pass it to Ultron/Dante in their task prompt.
<!-- END unmassk-build-mode -->
