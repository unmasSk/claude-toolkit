<!-- BEGIN unmassk-toolkit (managed block — do not edit) -->
## unmassk-toolkit Active

This project uses the **unmassk toolkit**.

**On every session start**, you MUST:
1. Read the `[git-memory-boot]` SessionStart output already in your context
2. Use the Skill tool with `skill="unmassk-core"` (TOOL CALL, not bash)
3. Use the Skill tool with `skill="unmassk-gitmemory"` (TOOL CALL, not bash)
4. Read CALIBRATION.md: `${CLAUDE_PLUGIN_ROOT}/skills/unmassk-gitmemory/CALIBRATION.md`
5. Show the boot summary, then respond to the user

**On every user message**, the `[memory-check]` hook fires. Follow the CALIBRATION rules.

Never ask the user to run commands -- run them yourself.
<!-- END unmassk-toolkit -->

<!-- BEGIN unmassk-protocols (managed block) -->
## Protocols

These protocols exist as skills. Detect the situation and load the matching skill (TOOL CALL). The list is always visible here so you never need to "remember" a protocol exists — pick from this menu.

**Project lifecycle** — detect by checking two facts: is there toolkit git-memory? is there existing code?

- git-memory + code → continuing our project → Skill `unmassk-project-lifecycle`
- code, no git-memory → external repo → Skill `unmassk-project-lifecycle`
- nothing → new project → Skill `unmassk-project-lifecycle`

(One skill handles all three; it routes internally. State the detected situation in one line before acting.)

**Starting a brand new project (scaffolding, tech stack, boilerplate):**

- Scaffold, initialize, or create a new project / decide the tech stack → Skill `unmassk-flow-stack` (IDE-grade scaffolding wizard, 70+ project types)

**Before building something significant:**

- Ambiguous request, or a decision with stakes → Skill `unmassk-grill` (interrogate until the decision tree is resolved, before writing code)
- A real choice between options, or "help me decide / I'm torn" → Skill `unmassk-council` (5-advisor pressure-test; also covers brainstorming and prototyping)

**Building a feature, fixing a non-trivial bug, or refactoring:**

- Build a feature, implement, add functionality, fix a non-trivial bug, or refactor → Skill `unmassk-flow` (8-step creative pipeline, idea to shipped code)

**Auditing existing code against enterprise standards:**

- Audit a module or an enterprise review request → Skill `unmassk-audit` (14-step structured audit, weighted score out of 110)

**Ending a session:**

- Wrapping up / handoff → Skill `unmassk-close-session` (flush decisions to git-memory, write the resume point)

All protocol output persists to **git-memory**, never to `.md` files.
<!-- END unmassk-protocols -->

<!-- BEGIN unmassk-communication (managed block) -->
## Communication

- **Concise and plain.** No internal jargon (hook names, issue numbers, made-up terms). Long or overly technical responses lose the user.
- **Results, not process** — except when there's a failure, a risk, or a decision to make: then the "why" does matter.
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

Before running the Execute step of `unmassk-flow` (the build pipeline skill), decide the build mode and tell the agents which one applies. The agents do not choose — you do.

- **Test-first** (TDD/BDD/ATDD) → for business logic, APIs, anything with clear rules where being wrong is costly. Order: Dante writes failing tests (the contract) → Ultron implements until they pass.
- **Linear** → for prototypes, exploration, throwaway code, or when the shape isn't clear yet. Order: Ultron implements → Dante tests after (Flow's normal Verify step).

Decision factors:
- Clear, testable behavior + matters if wrong → test-first
- Exploratory / "let me see it first" / disposable → linear
- Uncertain → test-first (the safer default for real code)

State the chosen mode in one line before delegating, and pass it to Ultron/Dante in their task prompt.
<!-- END unmassk-build-mode -->

## What security and tests are for in THIS project

This toolkit is the owner's personal tool — the foundation under all his projects. It is not a public product. Whether anyone else downloads it or not is irrelevant; the only thing that counts is that **it works perfectly for him**. With that settled:

- **Security against a malicious attacker → DOES NOT APPLY.** The system has a single owner and nobody is going to attack it. Every defense built for hostile repos (control-byte injection, booby-trapped symlinks/hardlinks, malicious inputs, anti-exploit hardening) is **dead weight**: don't build it, and retire whatever exists. That is not this project's threat.
- **Robustness against the system breaking itself → THIS matters, and it's the priority.** What must be protected is that the system **does not self-harm**: a bug must not corrupt memory, a script must not write where it shouldn't, data must not be lost to an internal failure, a failure must not pass silently. That is the real threat model: the system against itself, not a person against the system.
- **Rule for writing or reviewing tests:** a test is justified **only** if it proves the system doesn't break on its own (memory loss or corruption, writing to the wrong place, silent failure, data lost across sessions/machines). A test that simulates a malicious attacker is **surplus** — cut it.
- **The `unmassk-standards` are not this project's yardstick.** They're written for a web app (Node/Express/React/PostgreSQL/Zod, 97% coverage, §34 anti-fixture, Coordinador/Municipio roles). The toolkit is Python (hooks and scripts): it is not measured with web-app rules, nor held to that test ceremony.

In one line: **less ceremony, zero attacker paranoia, focus on the system not breaking itself.**
