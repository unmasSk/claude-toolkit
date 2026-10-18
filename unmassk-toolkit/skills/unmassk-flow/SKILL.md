---
name: unmassk-flow
version: 1.2.0
description: >
  Use when the user asks to build a feature, implement, add functionality, fix a
  non-trivial bug or refactor — any task that requires writing code — or names Flow. Also use to
  open or change a plan for work that spans sessions ("let's make a plan", "plan this",
  "update the plan"), and when something that already worked breaks ("it's broken",
  "this used to work", "it crashed in production"). NOT for a question about how the
  plan or an issue is going (answer it from the plan and the issue, without loading
  this), NOT for open-ended ideas or picking between known options (unmassk-council),
  NOT for undefined requirements (unmassk-grill), NOT for audits (unmassk-audit). Its
  own Step 1 (Brainstorm) resolves gray areas once a build is underway.
---

# Flow — Creative Pipeline

8-step workflow for building features, fixes, and refactors from idea to shipped code. Combines gray-area brainstorming, bite-sized planning, and evidence-first agent execution. All decisions persist in git-memory. In the Full procedure, the plan file is the single source of truth.

**This skill runs in ANY project, any stack.** Nothing here hardcodes a language, framework, test runner, or directory layout. Every stack-specific value (test command, lint command, build command, plan directory, coverage bar) comes from the **project profile** — never from this skill. If a value you need isn't in the profile, detect it from the project (see "Project profile" below) and record it; do not assume a default like `npm`/`vitest`/`pytest`.

## Dependencies

- **`unmassk-memory`** — every decision, memo and close in this pipeline is saved through it
- **Claude Code subagents** — bundled agents: Bilbo, Ultron, Dante, Cerberus, Argus, Moriarty, Yoda, House, Alexandria (use `subagent_type` by name)
- **The visible list** — the phases and steps the owner follows live. Today: the task list the app shows under the conversation. Planned: a live panel (a Claude Code mod) that shows the plan the way PLAN-SESION.md does (#98).

## When to Use

For any work that writes code. The first thing is choosing the procedure (Step 0): **Trivial**, **Short** or **Full**. Trivial is done by Claude directly, without agents.

Not for: a question about how a plan or an issue is going (read the plan and the issue and answer); ideas or choosing between known options (`unmassk-council`); requirements still undefined (`unmassk-grill`); enterprise audits (`unmassk-audit`).

## Lane discipline — who does what, and what each NEVER does (ABSOLUTE)

This is the rule the whole pipeline exists to protect. When Flow is carried to another project, this is the first thing that erodes — the orchestrator starts cross-assigning and agents drift off-lane. It does not bend.

| Agent | DOES | NEVER does |
| ----- | ---- | ---------- |
| **Orchestrator (you)** | decides what/who/when, writes the plan, runs Flow, and does the Trivial procedure itself | writes production code or tests outside the Trivial procedure |
| **Bilbo** | investigates — maps the codebase and traces dependencies, AND researches the web when the answer isn't in the repo | implements, reviews, or judges |
| **Ultron** | implements production code | writes/edits tests, explores as a phase, reviews, attacks |
| **Dante** | writes the tests | implements production code, investigates the codebase (that's Bilbo) |
| **Cerberus** | reviews code | fixes what it finds (reports → Ultron fixes code, Dante fixes tests) |
| **Argus** | security audit | fixes, or does general code review |
| **Moriarty** | tries to break the shipping candidate | fixes, or reviews |
| **Yoda** | final production-readiness verdict | fixes, re-reviews, or attacks |
| **Alexandria** | syncs docs to reality | implements or tests |

**The two failures this table forbids, by name:** sending **Dante to investigate** the codebase (that is Bilbo's lane) and sending **Ultron to write tests** (that is Dante's lane). Both are the exact cross-assignments that break the pipeline. There is no "small enough" exception. If GREEN needs a test change, Ultron STOPS and reports; the orchestrator routes it to a fresh Dante at once — the one case Dante is called before the reviewers (D-126).

## One feature in flight — close before you open (GATE)

**If a previous Flow feature is still open, finish it through Step 7 — or explicitly park it — before starting a new one.** A feature is "open" from the moment Step 0 creates its branch/issue until Step 7 closes it. Opening a second branch over an unfinished first is how the pipeline ends up with a trail of half-done branches.

Before Step 0 of any new feature, **run the check — don't just recall it:** `git branch --list 'feat/*' 'fix/*' 'refactor/*'` for an un-merged feature branch, and `grep -L 'Status: COMPLETED' docs/plan/*.md 2>/dev/null` for an open plan. A non-empty result means a feature is still in flight → finish it through Step 7 (or explicitly park it: a checkpoint plus a close whose Next says where it stopped) BEFORE starting the new one. One at a time.

## Project profile — where stack-specific values live

Flow is stack-agnostic; the project supplies its own commands. The **project profile** (`unmassk-standards` §10) is declared in the project's `CLAUDE.md` / git-memory — never a loose file. Resolve the test/lint/build commands like this:

1. **Read the profile** — the commands the project declares, in its `CLAUDE.md` or in a saved note (`gitmem search test command`).
2. **If not declared, detect from the repo** — the command the project actually uses: `package.json` scripts (npm/pnpm/yarn/bun), `pyproject.toml`/`pytest`, `go test ./...`, `cargo test`, a `Makefile` target, etc. Never impose a runner the repo doesn't use.
3. **Record the test command where the MACHINE reads it.** Write the resolved test command into `.claude/project-memory/config.json` under `test_command` (the same file that holds `repo_type`), and save it as a memo so a person can find it without opening a config file. [2026-08-23] The Stop-time test gate was retired by the owner: it re-ran the suite at every stop and multiplied side effects across his other projects. Nothing runs `test_command` automatically any more — the tests run when the pipeline runs them: Execute, Verify and the scoped run at Close (Step 7).

The right place to establish `test_command` once is project start (`unmassk-project-lifecycle`), so Flow rarely has to detect it. If you still cannot resolve a test command, STOP at the Step 7 gate and ask the user — do not skip the gate and do not guess a runner.

## Step 0 — Triage (ORCHESTRATOR)

Classify the work BEFORE anything else. Decide together with the user. (First run the "One feature in flight" gate above.)

**The go is explicit or it is not a go.** A user's question ("what's next?", "is this ready?") never starts a build; "ok" / "looks fine" does not either. Before creating a branch or launching the first agent, you need an unambiguous yes to "do I start?" — if the last thing the user wrote was a question or a shrug, ask and stop. [2026-08-20: "¿ahora qué toca?" was read as "go" — plan opened, three agents launched, a skeleton committed, all unasked.]

| Procedure | What it covers | Who |
| --------- | -------------- | --- |
| **Trivial** | Quick, isolated and checkable at a glance, and NONE of: logic change, data, security, a seam, new behavior, or anything other modules depend on. Examples: widening a button, a typo, a config value. If on inspection several things have to be redone, it is no longer trivial. | **Claude does it, with no agents, no plan, no branch and no list**: one finished-work commit (`gitmem work`), not a WIP, since there is nothing to squash later. If a work branch is already open, it goes on that branch; otherwise on `main` (trunk) or directly on `dev` (gitflow; `gitmem` only protects `main`). If the repo has tests, run once the ones covering the touched file. |
| **Short** | A change with logic but bounded: 1 to 3 files, one part of the project, and touching no data, memory, security or money (a producer↔consumer seam counts as data: it goes to Full). Examples: fixing a known bug in a function, adding a field to a form. | In the build mode chosen: linear, Ultron implements → Dante adds the test for the change; test-first, Dante writes the test first → Ultron makes it pass (if the project has no tests, they are not set up here) → Cerberus reviews → one fix pass (code: Ultron; tests: Dante). No Argus, Moriarty, Yoda or Alexandria. |
| **Full** | Anything touching data, memory, security or money, a new feature, or several parts of the project at once. | The whole Step 5 pipeline. If it is large (3+ new files or 5+ modified), Execute in several Ultron rounds and deeper Research. |

The owner speaks Spanish: Trivial / Short / Full are *procedimiento trivial / corto / completo*.

**Before starting, Claude states the procedure in one line. When in doubt, the bigger one**; a Trivial that grows on inspection becomes Short. Then create the task-list box of the procedure chosen — `Procedimiento: Trivial`, `Procedimiento: Corto` or `Procedimiento: Completo` — and only that procedure's boxes, as the loaded checklist lists them: the closing check reads that box to know which list applies (no box = the whole list).

**A plan file belongs to Full only.** Trivial and Short carry no written plan (Steps 3 and 4's plan gate apply to Full); the issue with its checklist is opened only when the work crosses sessions.

Triage settles **size** (knowable early: files touched, whether it hits auth/data/permissions). It may also **propose** a tentative build mode (test-first vs linear), but the mode is NOT locked here — the feature isn't understood yet. The firm build-mode decision happens at the end of Brainstorm (Step 1), once the gray areas are resolved.

**Seam declaration (mandatory, independent of size):** state whether this feature touches a producer↔consumer seam (network call, DB read/write, file written and reread — see `unmassk-standards` §34.1). "No seam" requires the mechanical check from §34.1, not a guess. A seam always makes the work Full, which pulls Moriarty + Yoda into Verify and applies Step 5's seam subsection. Record the declaration together with the start in memory (end of this step).

**If Short or Full:** use the Skill tool with `skill="unmassk-grill"` now (pipeline-invoked mode — 5-question cap) to catch vague wording and bundled scope in the request before Brainstorm starts. Skip it for Trivial.

Create the branch after triage (in a gitflow repo; in a trunk repo `main` is the working branch) — one branch per task, never for a Trivial. **The issue is a plan, and a plan is never opened on your own judgement** — offer it in one line and wait; with the user's yes you open it, and then follow `references/plan.md` for what it holds and how it is kept up to date. Then record the start in memory.

## Step 1 — Brainstorm (ORCHESTRATOR + User)

Identify gray areas — decisions that change the outcome — and resolve them before planning. If Triage's `unmassk-grill` call hit its 5-question cap and logged open branches, start from that list before generating new gray areas — don't re-derive what's already flagged.

### Gray Area Identification

Analyze the feature domain and generate specific gray areas (not generic categories):

| Domain | Gray areas to surface |
| ------ | -------------------- |
| Visual features | Layout, density, interactions, empty states, responsive behavior |
| APIs | Response format, error codes, rate limiting, pagination, versioning |
| Data | Schema design, relationships, constraints, migrations, defaults |
| Security | Auth model, permissions, data exposure, environment guards |
| Integration | Which existing modules touched, API contracts, data flow |

### Process

1. State the domain boundary — what this feature delivers
2. Check memory for prior decisions that apply: `gitmem search <zone or word>` (and `--id D-xxx` for one)
3. Present gray areas as specific questions, one at a time
4. For each gray area: propose 2-3 approaches with trade-offs, recommend one
5. Save each decision the moment it is made — with its why and every option it beat
6. Apply scope guardrails — if user suggests scope creep: "That is a separate feature. Want me to create an issue for it?"

### Exit Conditions

- All gray areas resolved → proceed to Step 2
- Feature found infeasible → close issue with rationale, STOP
- User says "enough, let's build" → proceed with decisions locked so far

### Decide the Build Mode (here, not at Triage)

Now that the gray areas are resolved you finally know the feature's shape — clear contract vs fuzzy exploration. Decide the build mode and record it: in Full, in the plan (Step 3); in Short, in the one-line start statement. Short follows the mode too — test-first puts Dante's test before Ultron (e.g. the failing repro test of a bug fix). Triage's tentative guess does not bind this.

- Clear, testable behavior + costly if wrong → **test-first** (method: `references/test-first.md`).
- Exploratory / throwaway / shape still unclear → **linear** (method: `references/linear.md`).
- Uncertain → test-first (the safer default for real code).

## Step 2 — Research (Bilbo)

Investigate how to implement, guided by decisions from Step 1. **Research is Bilbo's lane — never Dante's, never Ultron's.**

### Depth Levels

| Level | Scope | When |
| ----- | ----- | ---- |
| Quick | Verify syntax, check existing code, confirm pattern | Confirming known approach works |
| Standard | Explore codebase, map dependencies, compare approaches | Choosing between options, new integration |
| Deep | Full dependency trace, integration map, risk assessment | Architectural decisions, novel problems |

Orchestrator chooses depth based on the procedure (Short = quick research, a large Full = deep research).

### Process

1. Launch Bilbo agent with the depth chosen from the table above (Quick / Standard / Deep) and the decisions from Step 1
2. Info stays in conversation context — no RESEARCH.md file
3. If Bilbo finds something permanent — a pattern, a constraint, something waiting on someone — save it as a memo, a decision or a blocker
4. If research reveals infeasibility → close issue with rationale, STOP

## Step 3 — Plan (ORCHESTRATOR)

**Full only** — Trivial and Short skip this step and carry no plan file. Write the plan. This is the SINGLE source of truth for the feature.

**This is the execution plan of one feature: its steps and the order they run in.** When the work also carries a plan of its own — one that spans sessions, with an issue and a checklist the user follows — read **`references/plan.md`** and follow it: the document, the issue and the record that ties them to the decision. That file governs the plan; this step only plans the execution.

### Location

`docs/plan/<type>-<name>.md` (or the plan directory the project profile declares) where type is `feat`, `fix`, `refactor`, etc. If the project has no `docs/plan/`, create it or use the profile's location — do not assume it exists.

### Format

```markdown
# <Name> Plan (task = issue #N)

**Issue:** #N (only if the work crosses sessions)
**Branch:** feat/<name> | fix/<name> | refactor/<name>
**Procedure:** Full
**Build mode:** test-first | linear
**Created:** YYYY-MM-DD

## Goal
[One sentence — what this delivers]

## Decisions
[Reference the memory decisions or summarize those from Step 1]

## Phases

### Phase 1: [Name]
**Files:** create/modify/test
**Steps:**
- [ ] 1.1: [specific action]
- [ ] 1.2: [specific action]
- [ ] 1.3: [verify — command + expected output]
- [ ] 1.4: [WIP]

### Phase 2: [Name]
**Depends on:** Phase 1
**Files:** ...
**Steps:** 2.1, 2.2…

## Wave Map
[Which phases can run in parallel]
- Wave 1: Phase 1, Phase 2 (independent)
- Wave 2: Phase 3 (depends on Phase 1)
```

### Plan Checker

Before execution, verify the plan achieves the goal:

1. Does every decision from Step 1 have a corresponding step?
2. Does every step have a clear way to verify it?
3. Are dependencies between steps explicit?
4. If any gap → amend plan before executing

### The visible list

One line per phase and per step of the plan, with its number («#101 · 1.2»), in the app's task list. Update it at every step: the owner must always see where we are and what comes next.

## Step 4 — Execute (Ultron + Dante)

Implement the plan. Wave-based parallel execution where possible.

### Build Mode Router (read the build mode — the plan's in Full, the start statement's in Short — then load the matching method)

This step is a **router** — it does NOT spell the method out; it points to the reference doc that does (same pattern as `unmassk-standards` → `references/standards.md`). Load the matching doc and follow it:

- **Linear** → read **`references/linear.md`** (Ultron implements → Dante tests after).
- **Test-first** → read **`references/test-first.md`** (Dante writes the complete test set once → Ultron writes only the code those tests ask for, until GREEN; no later hardening pass — D-125. Code Ultron adds beyond the tests is an exception he declares in his report — D-126).

Everything below (waves, deviation rules, circuit breaker, tracking) applies to both methods. **Lane discipline (top of this skill) applies at every wave: Ultron never writes tests, Dante never investigates.**

### Pre-execution Gate

MANDATORY (Full): Read the plan file before any implementation. Verify the plan exists and is checked. If a Full change has no plan file, STOP — do not implement from memory or conversation context alone.

### Wave Execution

1. Read wave map from plan
2. Launch Ultron agents for Wave 1 phases in parallel (1 agent per phase, no overlap on same file) — in test-first, Dante's tests for that phase come first
3. Wait for Wave 1 to complete
4. Launch Wave 2 phases
5. Repeat until all waves done

- **Tests in parallel:** every agent that runs tests uses its own test database (the project-cleanup skill will set it up — D-100, not built yet). If the project does not have that yet, its tests are not run in parallel.
- **Before refactoring:** Dante writes and checks the golden tests of what is affected; never refactor without that net.
- **Progress:** as `unmassk-core` says (How you talk) — one numbered line per agent or step that finishes, ticking the visible list.

### Deviation Rules (in the Ultron agent prompt) — bounded, not a blank cheque

Ultron may, without stopping to ask, do ONLY what the assigned task requires to be correct:

- Fix a bug it hits **inside the code it is already changing**. In test-first, a fix no test asks for is code beyond the tests: declared exception, on its own report line, and Dante tests it in the fix pass (D-126).
- Add the error handling / input validation the change itself needs to be safe. In test-first that is code no test asks for: allowed only as the declared exception — its own line in his report, with why, and Dante writes its tests in the fix pass (D-126).

Everything else is scope creep and is FORBIDDEN mid-task:

- New helpers, utils, or "infrastructure" beyond the minimal surface the task needs → do NOT add speculatively. A genuinely required helper is part of the task's minimal surface; a "nice to have" is a separate feature.
- Anything touching a file outside the task's declared surface → STOP and report.
- A spotted improvement out of scope → record it as an **Observation** in the report (Ultron's ficha channel) — never build it unasked.

All deviations, however small, are listed in the report. "No permission needed" covers the two bounded cases above and nothing wider.

### Plan Amendment Protocol

If a deviation invalidates a LATER step in the plan:

1. Ultron STOPS and reports to orchestrator
2. Orchestrator amends the plan file in `docs/plan/`
3. Execution resumes from the amended step

In Full, the plan file is always the truth. Ultron does not improvise later steps.

### House Circuit Breaker

If Ultron fails the same step 3 times:

1. STOP execution
2. Launch House agent to diagnose root cause
3. House delivers diagnostic report with root cause and fix strategy
4. Orchestrator amends plan if needed
5. A fresh Ultron fixes it with House's diagnosis (the previous one is never resumed, unless the owner asks)

**This is not an incident.** A defect found while the thing is still being built is ordinary work — House diagnoses, Ultron fixes, the pipeline carries on, and nothing is recorded as a scar. **An incident is something that had already been signed off and then broke**, and it has its own protocol in `references/incident.md`: what to record, when, and how it closes.

### Progress Tracking

- After every agent that changes files, the orchestrator saves a WIP (`gitmem wip`); agents never commit (Cerberus, Argus and Yoda change no code, so they leave none). When a step is done, its WIPs are squashed into one commit for that step, **keeping memory-note commits out of the squash**, and that step commit is pushed. Until the squash is built and tested (issue #87), nothing is squashed: the WIPs are pushed as they are.
- The visible list (section «The visible list»), updated as steps complete
- Each step marked done only after its verification passes

## Step 5 — Verify (TWO PHASES: review per plan phase while building, then one final break-and-judge)

**Every agent runs once and every fix is done once.** Nobody runs again: not Cerberus and Argus, not Moriarty, not Yoda. Fixes always go to a fresh agent of the same type, with the report and the exact files, unless the owner asks for the same one. **Before fixing a finding, check that it is real** and happens in real use; if not, note it and leave it. A regression from a fix is caught by the scoped tests at Close (Step 7), never by another round of reviewers.

**PART A — per independent plan phase, as it is built (owner rule, 2026-09-18 — «las partes principales se hacen separadas; las partes finales son Moriarty, Yoda y Alexandria»):**

1. **Build, per build mode:**
   - **Test-first:** Dante writes the complete test set once (it starts red) → Ultron writes only the code those tests ask for, until they pass (D-125, D-126).
   - **Linear:** Ultron implements → Dante writes the tests for what was built.
   Tests hit the REAL dependency by default; mock only what genuinely cannot run, and at least one test wires the core seam end-to-end (`unmassk-standards` §34.5). Coverage gate: the project profile's bar. Ultron never edits tests; Dante never edits code.
2. **Cerberus + Argus, in parallel, over the code AND the tests of that phase.** In the Full procedure, Argus is never skipped. Each writes its report to a file that starts with an index (as every agent does, per its card); Claude reads the index and goes into detail only if there is a problem.
3. **What they flagged is fixed, once:** code, Ultron; tests, Dante. They do not review again.

**PART B — once, when every phase of the issue and its checklist are done:**

4. **Moriarty** attacks what was already fixed: the code and the tests. One per part, or one for all.
5. **What he breaks is fixed, once:** Ultron or Dante, whoever owns it; in parallel when the fixes don't collide.
6. **Yoda — once.** He gets the ARTIFACT (including Moriarty's raw run log: commands and output, never his summary; without it he answers CANNOT JUDGE), the CONTRACT and the reference id, and finds his own evidence in the code, tests and memory. He is given no narrative and no conclusion («no le digas a Yoda lo que tiene que buscar, que se busque la vida»). **110 is perfection:** with any lower score he says what to fix to reach 110 and, if 110 cannot be reached, why (e.g. no E2E tests planned).
7. **What Yoda names is fixed, once:** Ultron or Dante, whoever owns it. Reaching 110 is taken as given, and those fixes are checked by the scoped tests at Close (Step 7). Yoda does not run again.
8. **Alexandria** documents what changed (Step 6).

### Prompting the reviewers in Verify

- **Cerberus, Argus and Yoda: blind.** They get the artifact, the contract and the reference, using the blind review template in `unmassk-core`. Never your conclusion or what to look for, and never «find the issues»: ask them to review and audit everything and say what they reviewed.
- **Moriarty**: SHORT prompt (≈1 line) — name the target and the win condition, hand him NO vector list. A long prompt that pre-chews the attack vectors collapses his break rate and robs him of the only thing he's for — finding the break you didn't think of. Never lead the executioner.

### If producer↔consumer seam exists (network call, DB read/write, file written and reread)

Triggered by the Step 0 seam declaration — a seam always makes the work Full. Apply `unmassk-standards` §34 (Producer↔Consumer Data Integrity). Not a new pipeline step — it runs inside this one:

- **Dante** owns the round-trip check, never Ultron (the implementer does not verify his own write path). Add it as its own step in the Step 3 plan and the visible list so it cannot be silently dropped from tracking.
- **Moriarty** runs his Round-Trip Sabotage mandate against the real dependency before declaring the feature holds up (AGUANTA).
- **Cerberus** confirms no expected value in the round-trip test is a hand-typed literal.
- **Yoda** applies his Round-Trip Evidence Rule — mechanical pass/fail on the artifact, no discretion — as part of his one verdict.

IF a seam is discovered during Execute that Triage did not flag THEN amend the plan (Plan Amendment Protocol) to add the round-trip step before Verify proceeds.

### No verify loop (by design)

There is no "repeat until clean" loop — that is the failure mode this sequence exists to kill. Each reviewer runs once; the implementer's fix after each is the correction, not the trigger for another full round. The only mechanical backstop is the scoped test run at Close (Step 7) — the tests covering the change, not the whole suite: a regression there sends the specific failing test back to Ultron (code) or Dante (test), never a fresh pass of the whole review chain.

## Step 6 — Document (Alexandria)

Separate from closure — documentation deserves its own step.

1. Launch Alexandria agent
2. Read all WIP commits and changes from the feature
3. **Document the new capability for ALL THREE audiences** (deliberate duplication — see `unmassk-core` "Documentation discipline"): humans (`README.md` / `docs/`), us (roadmap + git-memory), and Claude at load (the relevant `SKILL.md` / `CLAUDE.md`). A feature documented in only one surface is half-shipped.
4. Update module CLAUDE.md if patterns changed
5. Alexandria updates CHANGELOG.md under [Unreleased] — never the orchestrator
6. Cross-check documentation against current code state — same fact, every surface, no drift

## Step 7 — Close (ORCHESTRATOR)

Merge ceremony. Only after VERIFY passes and DOCUMENT completes.

**MANDATORY pre-merge gate — run ONLY the tests covering what you changed, NOT the whole suite.** [2026-09-18, owner rule — Bex] Run the tests of the modified area (a `-k`/path filter on the touched modules and their tests), never the full suite: it burns time and tokens for no added signal on a small change. Resolve the test command from the project profile (see "Project profile" above); if none is declared, detect it from the repo (`pytest`, `package.json` test script, `go test ./...`, `cargo test`, a `Makefile` target, …) and scope it to the change. The WHOLE suite is run by CI/CD when the work goes to staging or production; by hand ONLY if the owner explicitly asks. If a scoped test that passed before now fails, the change introduced a regression — fix before merging. **Never skip this gate; if you cannot find a test command, stop and ask the user.**

Check the project's `repo_type` (`.claude/project-memory/config.json`; when it is not declared, the main branch counts as protected) — this step branches on it, and **runs without asking**:

1. Every step is already one commit (see «Progress Tracking»); squash any step still pending the same way. Until the squash is built and tested (issue #87), nothing is squashed: merge as is.
2. **Gitflow:** merge to dev (`git switch dev && git merge --no-ff <branch>`; the merge commit carries the summary listing the step commits) → push (`git push origin dev`). No merge gate stops a merge into dev: the work already went through its reviewers here (D-119). **Trunk:** the commits land on `main` → push `main` — no branch/merge step, `main` is the working branch.
3. If the work has an issue (only when it crossed sessions), close it: `gh issue close N --comment "Feature complete — [summary]"`
4. Delete branch, gitflow only (local + remote) — trunk repos have none to delete
5. Nothing else to record: the issue's closing comment and the step/merge commits are the record — there is no separate "context" commit (a bare commit is bounced by the commit gate).
6. Full only: mark the plan as completed in `docs/plan/` (add `**Status: COMPLETED**` to header)
7. **Ask the owner whether to go on with the next task.** One branch per task: it is deleted the moment it is merged to dev (the session close only sweeps forgotten ones). Moving from dev to staging or production is always asked first, and that merge goes through the heavy gate: Cerberus and Argus on the whole incoming batch, Alexandria checking CHANGELOG and version, the owner's yes; the full suite runs in CI on push (D-120).

### If Merge Fails

1. Do NOT force push
2. Identify conflicting files
3. If simple conflict → resolve and commit normally
4. If complex conflict → escalate to user before proceeding
5. After resolving the conflict, re-run the scoped tests of the touched area (never the whole Verify sequence)

## Quick Reference

| Step | Agent | Parallel? | Gate |
| ---- | ----- | --------- | ---- |
| — | ORCHESTRATOR | - | One feature in flight: previous closed before this starts |
| 0 | ORCHESTRATOR | - | Procedure (Trivial / Short / Full) + seam declaration |
| 1 | ORCHESTRATOR + User | No | Gray areas resolved + build mode decided |
| 2 | Bilbo | No | Research complete |
| 3 | ORCHESTRATOR | No | Plan written + checked (Full only) |
| 4 | Ultron (+ Dante), forked by build mode | Waves | All steps complete |
| 5 | Cerberus (+ Argus, Moriarty, Yoda) | Depends | VERIFY passes |
| 6 | Alexandria | No | Docs updated |
| 7 | ORCHESTRATOR | - | Scoped tests green + merged + closed |

## Recovery Paths

| Situation | Action |
| --------- | ------ |
| BRAINSTORM: feature infeasible | Close issue with rationale, STOP |
| RESEARCH: approach does not work | Pivot or close issue |
| PLAN: checker finds gaps | Amend plan before executing |
| EXECUTE: Ultron stuck (3 fails) | House diagnoses, amend plan |
| EXECUTE: deviation invalidates a later step | Ultron STOPS, orchestrator amends plan |
| EXECUTE: Ultron needs a test change for GREEN | Ultron STOPS, orchestrator routes the change to Dante (never lets Ultron touch the test) |
| EXECUTE: user abandons mid-feature | `gitmem wip` of the current state, then `gitmem next` with where it stopped, for the next session |
| VERIFY: Cerberus/Argus/Moriarty findings | Check they are real. Ultron fixes code, Dante fixes tests, once each, always fresh agents. No re-review. |
| VERIFY: Yoda scores below 110 | Ultron or Dante fix Yoda's points, once; 110 is taken as given and the Close tests check the fixes. If 110 cannot be reached, Yoda said why. Yoda does NOT re-run. |
| CLOSE: no test command found | STOP, ask the user — do not skip the pre-merge gate |
| CLOSE: merge conflict | Resolve or escalate; after resolution re-run only the scoped tests (not the whole Verify sequence) |
| CLOSE: merge fails completely | Do NOT force push, escalate to user |
