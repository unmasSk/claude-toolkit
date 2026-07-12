---
name: unmassk-flow
description: Use when the user asks to "build a feature", "implement", "add functionality", "fix a non-trivial bug", "refactor", or any task that is not trivial and requires writing code. Also use when the user mentions Flow by name. NOT for open-ended idea exploration with no build committed yet, or for picking between known options — those are `unmassk-council`; NOT for undefined requirements — that's `unmassk-grill`. This is the creative pipeline — from idea to shipped code; its own internal Step 1 (Brainstorm) resolves gray areas once a build is already underway, it does not trigger Flow from the outside.
---

# Flow — Creative Pipeline

8-step workflow for building features, fixes, and refactors from idea to shipped code. Combines gray-area brainstorming, bite-sized planning, and evidence-first agent execution. All decisions persist in git-memory. The plan file is the single source of truth.

**This skill runs in ANY project, any stack.** Nothing here hardcodes a language, framework, test runner, or directory layout. Every stack-specific value (test command, lint command, build command, plan directory, coverage bar) comes from the **project profile** — never from this skill. If a value you need isn't in the profile, detect it from the project (see "Project profile" below) and record it; do not assume a default like `npm`/`vitest`/`pytest`.

## Dependencies

- **unmassk-gitmemory plugin** — required for decision/memo/context commits
- **Claude Code subagents** — bundled agents: Bilbo, Ultron, Dante, Cerberus, Argus, Moriarty, Yoda, House, Alexandria (use `subagent_type` by name)
- **TodoWrite tool** — native Claude Code tool for task tracking visible to the user

## When to Use

- Building new features
- Non-trivial bug fixes (trivial = 1 file, obvious cause)
- Refactors that touch 3+ files
- Any task where "just do it" could go wrong

Do NOT use for: trivial 1-file fixes, documentation-only changes, config tweaks, or enterprise audits (use `unmassk-audit` skill instead).

## Lane discipline — who does what, and what each NEVER does (ABSOLUTE)

This is the rule the whole pipeline exists to protect. When Flow is carried to another project, this is the first thing that erodes — the orchestrator starts cross-assigning and agents drift off-lane. It does not bend.

| Agent | DOES | NEVER does |
| ----- | ---- | ---------- |
| **Orchestrator (you)** | decides what/who/when, writes the plan, runs Flow | writes production code or tests — not even one line |
| **Bilbo** | explores/maps the codebase, traces dependencies | implements, reviews, or judges |
| **Ultron** | implements production code | writes/edits tests, explores as a phase, reviews, attacks |
| **Dante** | writes and hardens tests | implements production code, investigates the codebase (that's Bilbo) |
| **Cerberus** | reviews code | fixes what it finds (reports → Ultron fixes) |
| **Argus** | security audit | fixes, or does general code review |
| **Moriarty** | tries to break the shipping candidate | fixes, or reviews |
| **Yoda** | final production-readiness verdict | fixes, re-reviews, or attacks |
| **Alexandria** | syncs docs to reality | implements or tests |
| **Gitto** | git ops under instruction | decides scope |

**The two failures this table forbids, by name:** sending **Dante to investigate** the codebase (that is Bilbo's lane) and sending **Ultron to write tests** (that is Dante's lane). Both are the exact cross-assignments that break the pipeline. There is no "small enough" exception. If GREEN needs a test change, Ultron STOPS and reports; the orchestrator routes it to Dante.

## One feature in flight — close before you open (GATE)

**Do not start a new Flow feature while a previous one is still open.** A feature is "open" from the moment Step 0 creates its branch/issue until Step 7 closes it. Opening a second branch over an unfinished first is how the pipeline ends up with a trail of half-done branches.

Before Step 0 of any new feature, **run the check — don't just recall it:** `git branch --list 'feat/*' 'fix/*' 'refactor/*'` for an un-merged feature branch, and `grep -L 'Status: COMPLETED' docs/plan/*.md 2>/dev/null` for an open plan. A non-empty result means a feature is still in flight → finish it through Step 7 (or explicitly park it: WIP commit + `context()` with a `Next:` trailer) BEFORE starting the new one. One at a time.

## Project profile — where stack-specific values live

Flow is stack-agnostic; the project supplies its own commands. The **project profile** (`unmassk-standards` §10) is declared in the project's `CLAUDE.md` / git-memory — never a loose file. Resolve the test/lint/build commands like this:

1. **Read the profile** — the project's declared commands in its `CLAUDE.md` or git-memory (`decision()`/`memo()`).
2. **If not declared, detect from the repo** — the command the project actually uses: `package.json` scripts (npm/pnpm/yarn/bun), `pyproject.toml`/`pytest`, `go test ./...`, `cargo test`, a `Makefile` target, etc. Never impose a runner the repo doesn't use.
3. **Record the test command where the MACHINE reads it.** Write the resolved test command into `.claude/git-memory-config.json` under `test_command` (the same file that holds `repo_type`). This is not just documentation: the `stop-dod-gate` hook **runs `test_command` from that file automatically at session close** — recording it there turns "run the tests" from a line the orchestrator has to remember into a gate that fires by itself (mechanism, not prose). Also note it in the profile (`memo()`) so a human can read it.

The right place to establish `test_command` once is project start (`unmassk-project-lifecycle`), so Flow rarely has to detect it. If you still cannot resolve a test command, STOP at the Step 7 gate and ask the user — do not skip the gate and do not guess a runner.

## Step 0 — Triage (ORCHESTRATOR)

Classify the work BEFORE anything else. Decide together with the user. (First run the "One feature in flight" gate above.)

| Size | Criteria | Pipeline |
| ---- | -------- | -------- |
| Quick | 1-2 files, obvious fix, no design decisions | Skip to PLAN (1-liner), lightweight VERIFY — Cerberus always; **Dante only if the change alters behavior or lacks test coverage**; a seam still pulls the full seam subsection |
| Standard | Normal feature, clear scope | Full pipeline (steps 1-7) |
| Big | 3+ new files, 5+ modified, or touches auth/data/permissions | Full pipeline + mandatory Argus + Moriarty + Yoda in VERIFY |

Triage settles **size** (knowable early: files touched, whether it hits auth/data/permissions). It may also **propose** a tentative build mode (test-first vs linear), but the mode is NOT locked here — the feature isn't understood yet. The firm build-mode decision happens at the end of Brainstorm (Step 1), once the gray areas are resolved.

**Seam declaration (mandatory, independent of size):** state whether this feature touches a producer↔consumer seam (network call, DB read/write, file written and reread — see `unmassk-standards` §34.1). "No seam" requires the mechanical check from §34.1, not a guess. A seam pulls Moriarty + Yoda into Verify regardless of size — a Quick or Standard feature with a seam is NOT exempt from Step 5's seam subsection. Record the declaration in the context commit at the end of this step.

**If Standard or Big:** use the Skill tool with `skill="unmassk-grill"` now (pipeline-invoked mode — 5-question cap) to catch vague wording and bundled scope in the request before Brainstorm starts. Skip for Quick — a 1-2 file obvious fix doesn't carry that risk.

Create issue + branch after triage (in a gitflow repo; in a trunk repo `main` is the working branch — see `unmassk-gitmemory` Safety → Repo type). Context commit: `context(<scope>): start <type> — issue #N`

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
2. Check git-memory for prior decisions that apply (`git log --grep="Decision:"`)
3. Present gray areas as specific questions, one at a time
4. For each gray area: propose 2-3 approaches with trade-offs, recommend one
5. Capture each decision as `decision()` commit immediately
6. Apply scope guardrails — if user suggests scope creep: "That is a separate feature. Want me to create an issue for it?"

### Exit Conditions

- All gray areas resolved → proceed to Step 2
- Feature found infeasible → close issue with rationale, STOP
- User says "enough, let's build" → proceed with decisions locked so far

### Decide the Build Mode (here, not at Triage)

Now that the gray areas are resolved you finally know the feature's shape — clear contract vs fuzzy exploration. Decide the build mode and record it in the plan (Step 3). Triage's tentative guess does not bind this.

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

Orchestrator chooses depth based on triage (Quick task = quick research, Big task = deep research).

### Process

1. Launch Bilbo agent with appropriate depth and the decisions from Step 1
2. Info stays in conversation context — no RESEARCH.md file
3. If Bilbo finds something permanent (pattern, constraint, blocker) → `memo()` or `decision()` commit
4. If research reveals infeasibility → close issue with rationale, STOP

## Step 3 — Plan (ORCHESTRATOR)

Write the plan. This is the SINGLE source of truth for the feature.

### Location

`docs/plan/<type>-<name>.md` (or the plan directory the project profile declares) where type is `feat`, `fix`, `refactor`, etc. If the project has no `docs/plan/`, create it or use the profile's location — do not assume it exists.

### Format

```markdown
# <Feature Name> Implementation Plan

**Issue:** #N
**Branch:** feat/<name> | fix/<name> | refactor/<name>
**Triage:** Quick | Standard | Big
**Build mode:** test-first | linear
**Created:** YYYY-MM-DD

## Goal
[One sentence — what this delivers]

## Decisions
[Reference decision commits or summarize key decisions from Step 1]

## Tasks

### Task 1: [Name]
**Files:** create/modify/test
**Steps:**
- [ ] Step 1: [specific action]
- [ ] Step 2: [specific action]
- [ ] Step 3: [verify — command + expected output]
- [ ] Step 4: [commit]

### Task 2: [Name]
**Depends on:** Task 1
**Files:** ...
**Steps:** ...

## Wave Map
[Which tasks can run in parallel]
- Wave 1: Task 1, Task 2 (independent)
- Wave 2: Task 3 (depends on Task 1)
```

### Plan Checker

Before execution, verify the plan achieves the goal:

1. Does every decision from Step 1 have a corresponding task?
2. Does every task have clear verification steps?
3. Are dependencies between tasks explicit?
4. If any gap → amend plan before executing

### Create TodoWrite

One item per task in the plan. Update status as execution progresses.

## Step 4 — Execute (Ultron + Dante)

Implement the plan. Wave-based parallel execution where possible.

### Build Mode Router (read the plan's Build mode, then load the matching method)

This step is a **router** — it does NOT spell the method out; it points to the reference doc that does (same pattern as `unmassk-standards` → `references/standards.md`). Load the matching doc and follow it:

- **Linear** → read **`references/linear.md`** (Ultron implements → Dante tests after).
- **Test-first** → read **`references/test-first.md`** (Dante writes the acceptance contract → Ultron implements until GREEN; Dante's exhaustive hardening is the Verify pass).

Everything below (waves, deviation rules, circuit breaker, tracking) applies to both methods. **Lane discipline (top of this skill) applies at every wave: Ultron never writes tests, Dante never investigates.**

### Pre-execution Gate

MANDATORY: Read the plan file before any implementation. Verify the plan exists and is checked. If no plan file exists, STOP — do not implement from memory or conversation context alone.

### Wave Execution

1. Read wave map from plan
2. Launch Ultron agents for Wave 1 tasks in parallel (1 agent per task, no overlap on same file)
3. Wait for Wave 1 to complete
4. Launch Wave 2 tasks
5. Repeat until all waves done

### Deviation Rules (in the Ultron agent prompt) — bounded, not a blank cheque

Ultron may, without stopping to ask, do ONLY what the assigned task requires to be correct:

- Fix a bug it hits **inside the code it is already changing**.
- Add the error handling / input validation the change itself needs to be safe.

Everything else is scope creep and is FORBIDDEN mid-task:

- New helpers, utils, or "infrastructure" beyond the minimal surface the task needs → do NOT add speculatively. A genuinely required helper is part of the task's minimal surface; a "nice to have" is a separate feature.
- Anything touching a file outside the task's declared surface → STOP and report.
- A spotted improvement out of scope → record it as an **Observation** in the report (Ultron's ficha channel) — never build it unasked.

All deviations, however small, are listed in the report. "No permission needed" covers the two bounded cases above and nothing wider.

### Plan Amendment Protocol

If a deviation invalidates a FUTURE task in the plan:

1. Ultron STOPS and reports to orchestrator
2. Orchestrator amends the plan file in `docs/plan/`
3. Execution resumes from the amended task

The plan file is always the truth. Ultron does not improvise future tasks.

### House Circuit Breaker

If Ultron fails the same task 3 times:

1. STOP execution
2. Launch House agent to diagnose root cause
3. House delivers diagnostic report with root cause and fix strategy
4. Orchestrator amends plan if needed
5. Ultron resumes with diagnosis context

### Progress Tracking

- WIP commit after each completed task
- TodoWrite updated as tasks complete — user sees progress in real time
- Each task marked `completed` only after its verification step passes

## Step 5 — Verify (Cerberus + conditionals)

Verify the feature works and meets quality standards.

### Always (Cerberus on every feature; Dante on every feature that changed behavior)

- **Cerberus** — goal-backward verification: does the code deliver the goal from the plan, not just complete the tasks? Runs on every feature, Quick included.
- **Dante** — tests for code that changed without coverage. In **test-first** mode this is Dante's **hardening pass**: the full EXHAUSTION PROTOCOL (an exhaustive read of the changed files, their imports/exports/call-sites and existing tests before reporting) + coverage gate (the project profile's bar; default ≥90% functions / ≥80% error paths) against the now-real code. **Exception, consistent with the Quick Triage row:** a Quick fix that changes no behavior and already has coverage may skip Dante — but any producer↔consumer seam pulls the seam subsection below in regardless of size.

### If Big feature (or touches auth/data/permissions)

- **Argus** — deep security audit of the feature
- **Moriarty** — adversarial attack
- **Yoda** — senior review with verdict

**Verify runs in ORDER, not all-at-once. Moriarty attacks LAST, on already-corrected code — never in parallel with the reviewers.** The sequence:
1. **Cerberus + Argus** review the fresh implementation (these two CAN run in parallel — different lenses, no dependency).
2. **Ultron** fixes everything they surface (phase-sized, one point per invocation; test changes go to Dante).
3. **Moriarty** then attacks the *fixed* result — his single adversarial pass is spent on the code that's meant to ship, not on a version about to change under him.
4. **Yoda** renders the verdict last of all.

Reason: Moriarty's value is one hard break-attempt against the real candidate. Run him before the review→fix cycle settles and you either re-break what Ultron is already fixing, or burn the attempt on soon-dead code. Cerberus/Argus are cartographers (map every flaw up front, in parallel); Moriarty is the executioner (one clean strike, last).

### Prompting the crew in Verify (calibrated per agent — NOT one size)

- **Cerberus / Argus**: detailed, spelled-out prompts help — name the files, the foci, the specific concerns. They are cartographers; more surface area given = more mapped.
- **Moriarty**: SHORT prompt (≈1 line) — name the target and the win condition, hand him NO vector list. A long prompt that pre-chews the attack vectors collapses his break rate and robs him of the only thing he's for — finding the break you didn't think of. Never lead the executioner.

### If producer↔consumer seam exists (network call, DB read/write, file written and reread)

Triggered by the Step 0 seam declaration, regardless of size — this applies to a Quick or Standard feature exactly as it applies to a Big one. Apply `unmassk-standards` §34 (Producer↔Consumer Data Integrity). Not a new pipeline step — it runs inside this one:

- **Dante** owns the round-trip check, never Ultron (the implementer does not verify his own write path). Add it as its own TodoWrite item in the Step 3 plan so it cannot be silently dropped from tracking.
- **Moriarty** runs his Round-Trip Sabotage mandate against the real dependency before declaring the feature holds up (AGUANTA).
- **Cerberus** confirms no expected value in the round-trip test is a hand-typed literal.
- **Yoda** applies his Round-Trip Evidence Rule — mechanical pass/fail on the artifact, no discretion — before rendering a verdict on this seam.

IF a seam is discovered during Execute that Triage did not flag THEN amend the plan (Plan Amendment Protocol) to add the round-trip task before Verify proceeds.

### Loop Condition

If VERIFY finds T1/T2 issues (blocking-severity tiers, per `unmassk-standards`) → return to Step 4 with findings. Repeat until clean.

## Step 6 — Document (Alexandria)

Separate from closure — documentation deserves its own step.

1. Launch Alexandria agent
2. Read all WIP commits and changes from the feature
3. **Document the new capability for ALL THREE audiences** (deliberate duplication — see `unmassk-core` "Documentation discipline"): humans (`README.md` / `docs/`), us (roadmap + git-memory), and Claude at load (the relevant `SKILL.md` / `CLAUDE.md`). A feature documented in only one surface is half-shipped.
4. Update module CLAUDE.md if patterns changed
5. Update CHANGELOG.md under [Unreleased]
6. Cross-check documentation against current code state — same fact, every surface, no drift

## Step 7 — Close (ORCHESTRATOR)

Merge ceremony. Only after VERIFY passes and DOCUMENT completes.

**MANDATORY pre-merge gate — run the project's OWN full test suite.** Resolve the test command from the project profile (see "Project profile" above); if none is declared, detect it from the repo (`package.json` test script, `pytest`, `go test ./...`, `cargo test`, a `Makefile` target, …) and record it. Run the WHOLE suite, not just the feature's tests. If any test that passed before the feature started now fails, the feature introduced a regression — fix before merging. **Never hardcode a runner and never skip this gate; if you truly cannot find a test command, stop and ask the user.**

Check repo type (`unmassk-gitmemory` Safety → Repo type) — this step branches on it:

1. Gitto squashes the accumulated pipeline wips (see `unmassk-gitmemory` Wip Strategy) into a final commit with real trailers
2. **Gitflow:** merge to dev (`git checkout dev && git merge --no-ff <branch>`) → push (`git push origin dev`). **Trunk:** squash lands directly on `main` → push `main` — no branch/merge step, `main` is the working branch.
3. Close issue: `gh issue close N --comment "Feature complete — [summary]"`
4. Delete branch, gitflow only (local + remote) — trunk repos have none to delete
5. Context commit: `context(<scope>): issue #N CLOSED`
6. Mark plan as completed in `docs/plan/` (add `**Status: COMPLETED**` to header)

### If Merge Fails

1. Do NOT force push
2. Identify conflicting files
3. If simple conflict → resolve, commit with `Conflict:` + `Resolution:` trailers
4. If complex conflict → escalate to user before proceeding
5. Re-run VERIFY after conflict resolution to confirm no regressions

## Quick Reference

| Step | Agent | Parallel? | Gate |
| ---- | ----- | --------- | ---- |
| — | ORCHESTRATOR | - | One feature in flight: previous closed before this starts |
| 0 | ORCHESTRATOR | - | Triage classification + seam declaration |
| 1 | ORCHESTRATOR + User | No | Gray areas resolved + build mode decided |
| 2 | Bilbo | No | Research complete |
| 3 | ORCHESTRATOR | No | Plan written + checked |
| 4 | Ultron (+ Dante), forked by build mode | Waves | All tasks complete |
| 5 | Cerberus (+ Argus, Moriarty, Yoda) | Depends | VERIFY passes |
| 6 | Alexandria | No | Docs updated |
| 7 | ORCHESTRATOR | - | Project's own suite green + merged + closed |

## Recovery Paths

| Situation | Action |
| --------- | ------ |
| BRAINSTORM: feature infeasible | Close issue with rationale, STOP |
| RESEARCH: approach does not work | Pivot or close issue |
| PLAN: checker finds gaps | Amend plan before executing |
| EXECUTE: Ultron stuck (3 fails) | House diagnoses, amend plan |
| EXECUTE: deviation invalidates future task | Ultron STOPS, orchestrator amends plan |
| EXECUTE: Ultron needs a test change for GREEN | Ultron STOPS, orchestrator routes the change to Dante (never lets Ultron touch the test) |
| EXECUTE: user abandons mid-feature | WIP commit current state, context commit with Next trailer for future session |
| VERIFY: T1/T2 findings | Return to EXECUTE with findings |
| VERIFY: Yoda NOT READY | Return to EXECUTE with concerns |
| CLOSE: no test command found | STOP, ask the user — do not skip the pre-merge gate |
| CLOSE: merge conflict | Resolve or escalate, re-run VERIFY after resolution |
| CLOSE: merge fails completely | Do NOT force push, escalate to user |
