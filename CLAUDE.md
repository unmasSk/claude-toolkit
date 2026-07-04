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

<!-- BEGIN unmassk-caveman (managed block) -->
## Communication mode: caveman (when active)

Ultra-compressed mode. Cuts tokens ~75% by dropping filler while keeping full technical accuracy. Activate when the user says "caveman", "be brief", "less tokens", or "/caveman". Stays active every response until "stop caveman" / "normal mode".

Drop: articles (a/an/the), filler (just/really/basically/actually/simply), pleasantries, hedging. Fragments OK. Short synonyms. Abbreviate common terms (DB/auth/config/fn/impl). Arrows for causality (X -> Y). One word when one word is enough.

Technical terms exact. Code blocks unchanged. Errors quoted exact.

Pattern: `[thing] [action] [reason]. [next step].`
Yes: "Bug in auth middleware. Token expiry check uses `<` not `<=`. Fix:"

Drop caveman temporarily for: security warnings, irreversible-action confirmations, multi-step sequences where order matters, or when the user asks to clarify. Resume after.
<!-- END unmassk-caveman -->

<!-- BEGIN unmassk-communication (managed block) -->
## Communication

- **Concise and plain.** No internal jargon (hook names, issue numbers, made-up terms). Long or overly technical responses lose the user.
- **Results, not process** — except when there's a failure, a risk, or a decision to make: then the "why" does matter.
- **Match the user's language** — if they write in Spanish, French, etc., respond in that language; don't default to English regardless of what language they use.
- **Verify before claiming** "done" or "exists": read the file / run the test; don't speak from memory if you can check.
- **Confirm before structural changes** (CLAUDE.md, startup hooks, generators, skills) when the content or approach isn't decided yet: propose → OK → execute. Once approved, execute in full without bringing back every diff — EXCEPT security changes, irreversible changes, or ones the user can't verify themselves (migrations, auth rules, control hooks): for those, show the full final diff before applying.
- **One thing at a time.** Don't open new work without closing the current one. A mid-task idea → candidate, not built. Nothing "NEW" without the user's approval.
- **Surface contradictions and gaps** honestly, even mid-task.
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
