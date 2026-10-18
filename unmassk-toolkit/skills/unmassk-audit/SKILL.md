---
name: unmassk-audit
version: 1.2.0
description: Use when the user asks to "audit a module", "audit this codebase", "code audit", "enterprise review", "launch audit", "review against standards", or mentions auditing EXISTING code against enterprise standards. Works with any stack or language. Also use when resuming an audit in progress.
---

# Enterprise Audit

## Overview

Structured 14-step workflow for auditing any module against enterprise quality standards. Stack-agnostic — works with any language, framework, or test runner. Each step assigns a specific agent role (orchestrator, explorer, implementer, tester, reviewer, documenter). The process produces a weighted score out of 110 and a final senior verdict.

## When to Use

- User requests auditing any module (backend, frontend, library, service)
- User says "audit", "enterprise review", "launch audit"
- Resuming an in-progress audit (check the app's task list for the current step)

Use this skill for structured audits of a complete module; a one-off review or a quick lint check is out of scope.

**Audit vs. build pipeline:** this skill is for reviewing an EXISTING module against enterprise standards. Use `unmassk-flow` (the build pipeline) when BUILDING something new. "Auditing" = existing code → standards gap analysis. "Building" = new code → Flow's definition-of-done pipeline. Confirm which applies before starting: existing code with no planned rewrite → audit; new code or a full rewrite → Flow.

## Workflow

### Initialization

Before step 0, create the app's task list (TodoWrite or its equivalent) with one item per step (steps 0-13), numbered, and update it after each step. After every agent that changes files, the orchestrator saves a WIP (`gitmem wip`); agents never commit. When an audit step is done, its WIPs are squashed into one commit for that step, keeping memory-note commits out (until issue #87 is built, nothing is squashed). Memory notes open (step 0) and close (step 13) the audit.

### Step 0 -- Preparation (ORCHESTRATOR (Claude + User))

1. Point the audit at an issue. If one already covers the target, use it. If none does, **propose it in one line and wait — you never open one on your own judgement** (the protocol, the labels and the template are in the memory skill's `references/issues.md`). If the user declines, the audit still runs; the opening note simply carries no issue number.
2. Create the audit branch -- branch strategy depends on the project's `repo_type` (declared in `.claude/project-memory/config.json`; read it, do not redefine it here):
   - **gitflow** → `git switch -c chore/audit-<module> dev`
   - **trunk** → work directly on `main`; no separate audit branch needed
3. Save the opening note:
   `gitmem note M --zones codeaudit <module-zone> "enterprise audit of <module> starts" --description "..." --stops no --issue N --searched "<searched>: <found>"`
4. Load `unmassk-standards` skill for quality criteria + read any project-level CLAUDE.md — record both (skill version + path read) in the opening note

### Step 1 -- Scan (Bilbo Agent)

1. List ALL source files in the module (including subfolders), not just those in the issue.
2. Count LOC per file (`wc -l`).
3. List existing tests (detect test directory convention: `__tests__/`, `tests/`, `*_test.*`, `*.test.*`).
4. Map imports/exports and inter-module dependencies.
5. Run existing tests using the project's test runner (e.g., `npx vitest run`, `pytest`, `go test ./...` — detect from project config).
6. Produce summary table: file | LOC | existing tests | imports from | consumed by | visible problems.
7. Flag large files, missing tests, or visible anti-patterns.
8. Classify each failing test: broken test, or source blocker (step 2 routes on it).

Prompt template: see `prompts/bilbo.md`

### Step 2 -- Fix Critical Blockers (Dante / Ultron)

Only if step 1 reported broken tests or critical blockers preventing further work.

1. Send broken tests to Dante first.
2. Send source blockers to Ultron, after Dante: the blockers Bilbo reported and the ones Dante reports back.
3. Run tests twice to confirm stability.
4. If nothing is broken, skip to step 3.

Prompt templates: see `prompts/dante.md` (Template 3: Broken Tests) and `prompts/ultron.md`

### Step 3 -- Golden Tests (Dante -- parallel)

Characterization testing -- capture current behavior BEFORE any code changes. Run in parallel with step 4.

1. One Dante agent per source file (no overlap).
2. Target: 97%+ coverage with REAL assertions (no tautologies).
3. Include unit tests and integration tests appropriate for the stack (e.g., supertest for Express, httpx for FastAPI, net/http/httptest for Go).
4. Each agent runs tests twice for stability. Parallel Dantes need one test database each; if the project does not have that yet, their tests run one after another.

Gate: all golden tests pass at 97%+ coverage before proceeding past step 4. **Coverage exception:** the general "coverage is not a merge gate" override does NOT apply here. In an audit, 97%+ is a hard gate — an audit is more stringent than a normal merge, and this is a conscious, explicit decision to supersede that override.

Prompt template: see `prompts/dante.md` (Template 1: Golden Tests)

### Step 4 -- Enterprise Audit (Cerberus + Argus -- parallel)

Run in parallel with step 3 (independent work). Cerberus and Argus run simultaneously.

**Cerberus** (quality audit):
1. One Cerberus agent per file (or group of 2-3 small files <100 LOC).
2. Evaluate ONLY against the enterprise standards (loaded from `unmassk-standards` skill — weights and tiers are defined there, not here).
3. Classify every finding by tier (T1/T2/T3).
4. Produce weighted score out of 110.
5. Agents ONLY report -- never fix.

**Argus** (deep integrity audit — no external attacker in this project's threat model, target is the system breaking itself):
1. Full integrity analysis of the module: memory/persistence integrity, silent-failure surfaces, concurrency races, platform robustness, data flow traceability.
2. Deeper pass on the same T1 surfaces Moriarty later attacks: memory corruption, silent failure, concurrency race, round-trip sabotage.
3. Classify findings by tier (T1/T2/T3).
4. Report findings only — fixing happens in step 5 (Ultron). Focus on the integrity surfaces beyond Cerberus's checklist.

ORCHESTRATOR (Claude + User) compiles findings from both Cerberus and Argus into a single findings table.

Prompt templates: see `prompts/cerberus.md` and `prompts/argus.md`

### Step 5 -- Tier Fixes (Ultron)

Order: T1 first, then T2, then T3. 1 agent per finding or group of findings in the same file.

1. Apply fix addressing root cause.
2. Clean documentation (JSDoc, docstrings, comments) per project conventions if touching the area.
3. Check file size after fix — flag it if it now exceeds the project's declared size limit (default 300 LOC per unmassk-standards §2).
4. If the fixed file exceeds the size limit from unmassk-standards §2, use architect-then-implementer pattern to split.
5. Run tests TWICE after each fix round.

Gate: tests pass after each round.

House circuit breaker: if Ultron fails the same fix 3 times, launch House (agent: `house`) to diagnose root cause before retrying. **Say in the prompt that this is a stuck fix, not a failure in delivered behaviour** — otherwise the diagnosis comes back proposing an incident note, and a defect found while fixing is ordinary work, not a scar.

Prompt templates: see `prompts/ultron.md` and `prompts/house.md`

### Step 6 -- Verify Fixes (ORCHESTRATOR)

No second review: every reviewer runs once and every fix runs once (D-122). The orchestrator checks the fix pass itself:

1. Every T1/T2/T3 finding from step 4 maps to a change in the diff, or to a written reason why it was not a real finding.
2. Run the module's tests TWICE.

Gate: every finding accounted for and tests green. A finding with no change and no reason goes back to Ultron once, as part of this same fix pass.

### Step 7 -- Test Fixed Code (Dante)

1. Write tests for code Ultron changed in step 5 that lacks coverage.
2. Update golden tests if function signatures or behavior changed.
3. Run full module suite TWICE.

Gate: coverage maintained at 97%+. Same explicit audit exception as step 3 — the general merge-override does not apply; the audit gate supersedes it.

### Step 8 -- Adversarial Validation (Moriarty)

1. Moriarty attacks the full module across all attack phases.
2. Document each break with tier classification; hand every confirmed break to step 9 (Dante's regression test, Ultron's fix — once).
3. Output: two files — the attack report, and the raw run log in its own `moriarty-<…>-rawlog.md`. Step 10 gets only the raw-log path.

Prompt template: see `prompts/moriarty.md`

### Step 9 -- Adversarial Tests (Dante)

1. Write regression tests for every confirmed break from step 8.
2. Write confirmation tests for attacks the module withstood.
3. Create `<module>.adversarial.test.*` (extension per project stack).

Gate: 0 T1 bugs, 0 T2 bugs unresolved: every confirmed T1/T2 break gets its regression test here and its code fix from Ultron in this same step — once.

Prompt templates: see `prompts/dante.md` (Template 2: Adversarial Tests) and `prompts/ultron.md`

### Step 10 -- Senior Review (Yoda)

1. Read ALL source files and their tests; state the file count read in the senior evaluation output.
2. Run tests TWICE.
3. Write prose evaluation per dimension.
4. Score on weighted table out of 110.
5. Verdict: APPROVED / APPROVED WITH CONDITIONS / REJECTED / CANNOT JUDGE. 110 is perfection: for any lower score, Yoda says what to fix to reach it, or why it cannot be reached.

Yoda judges once. He is sent again only after CANNOT JUDGE, with what was missing. Whatever the verdict, what Yoda names is fixed once in step 11.

FALLA rule: Yoda never gets Moriarty's verdict word; the rule rests on what the raw log shows.
- A confirmed break, or a round-trip check that stayed green under sabotage, makes plain APPROVED unavailable.
- Each such break without a test Yoda re-ran green on the fixed code is an open T1.
- A raw log whose coverage facts show the attack budget spent before the coverage gate also makes plain APPROVED unavailable; the not-attacked list goes in his conditions.

Prompt template: see `prompts/yoda.md`

### Step 11 -- Yoda's Fixes (Ultron / Dante, once)

1. Fix exactly what Yoda named, T3 and nitpicks included: code goes to Ultron, tests to Dante, each a fresh agent.
   REJECTED blocks the merge until every T1/T2 he named is fixed and its test is green.
2. Run the module's tests TWICE.
3. No new verdict: if every named point is fixed, the path to 110 Yoda gave is taken as walked (D-089). What cannot be fixed is written in the closing note with Yoda's reason.

### Step 12 -- Documentation (Alexandria)

1. Read ALL WIP commits and changes accumulated during the audit; cite the commit range read (first WIP → last).
2. Create or update module CLAUDE.md with patterns learned.
3. Update CHANGELOG.md under [Unreleased] with meaningful descriptions.
4. Cross-check documentation against current code state.
5. Update Alexandria memory; name the memory file touched in the closing note.

Prompt template: see `prompts/alexandria.md`

### Step 13 -- Closure (ORCHESTRATOR (Claude + User))

1. Delete temporary files (`AUDIT-<module>.tmp.md`).
2. **MANDATORY: run the module's tests and those of everything that depends on it** (detect the project's test command) — never the whole suite by hand: CI runs it when the work goes to staging or production. If any test fails that was passing before the audit started, the audit introduced a regression. Fix before merging.
3. Final commit with score and closed findings.
4. Merge and push — strategy depends on the same `repo_type` read in step 0:
   - **gitflow** → `git switch dev && git merge --no-ff chore/audit-<module>` then `git push origin dev`
   - **trunk** → changes already committed to `main`; push directly. No branch merge needed.
5. Close issue: `gh issue close N --comment "Enterprise audit complete -- YY/110"`
6. Delete branch (local and remote) if a branch was created (gitflow only).
7. Save the closing note, with the score and what it cost:
   `gitmem note M --zones codeaudit <module-zone> "<module> audited: YY/110" --description "..." --stops no --issue N --searched "<searched>: <found>"`

## No Loops

Every agent runs once and every fix runs once (D-122), except Yoda after CANNOT JUDGE. Nothing returns to step 5:

| Trigger | Action |
|---------|--------|
| Step 8 finds T1/T2 bugs | Step 9: Dante writes their regression tests, Ultron fixes the code — once |
| Step 10 answers CANNOT JUDGE | Supply what was missing; send Yoda again |
| Step 10 gives any other verdict | Step 11 fixes what Yoda named — once — then step 12 |

## Commit Policy

| When | Commit type |
|------|-------------|
| Step 0 | a memo saying the audit starts -- real note |
| Steps 1-12 | a WIP after every agent that changes files (`gitmem wip`, by the orchestrator), squashed into one commit per step |
| Step 13 | `gitmem work "<module>: enterprise audit complete"` + the closing memo |

## ORCHESTRATOR (Claude + User) Rules

- Never edit code directly -- everything through agents.
- Always verify agent claims independently (run tests, check LOC).
- Reject an "all clean" report unless it cites, per checklist item, the file:line or command output checked. Agents tend to report "clean" without verifying all tiers.
- Assign each file to exactly one agent at a time; queue other work on that file until the first agent finishes.
- Require a fix for every anti-pattern from the enterprise standards before code moves.

## Agent Dispatch Rules

Each agent receives ONLY context and data, NOT instructions on how to work (agent system prompts handle that).

- Build Bilbo, Ultron, Dante, House, Moriarty and Alexandria prompts from core's task template: TASK, KNOWN, CROSS-CHECK, LIMITS, VERIFY.
- Build Cerberus, Argus and Yoda prompts from core's blind template: ARTIFACT, CONTRACT, SCOPE, ASK. Never a KNOWN block, never your conclusion.
- End every prompt with core's three closing orders.
- Pass earlier reports to non-reviewers by path, never pasted. Reviewers get none; Yoda gets only Moriarty's raw-log path.
- Give module path and file list, and the verification command (run twice).
- Point to `unmassk-standards` for quality criteria; agents load it on boot (`skills: unmassk-standards` in their frontmatter).
- Tell Ultron the build order: audit-fix. Dante's prompts need no build mode.

Every agent writes its report file and answers in three lines. Read the report's index and the sections you need.

## Findings Report Format

ORCHESTRATOR (Claude + User) compiles agent outputs into `AUDIT-<module>.tmp.md`:

```markdown
## Audit: <module-name>

### Summary
- Files: X
- Total LOC: Y
- Existing tests: Z

### Findings
| ID | Tier | Severity | File:line | Description | Action |
|----|------|----------|-----------|-------------|--------|

### Score

Scoring dimensions, weights (Integrity x3, Silent-failure/Error handling x3, Structure x2, Real verification x2, Maintainability x1), and tier definitions live in `unmassk-standards`. Do not redefine them here -- agents load `unmassk-standards` to apply them. Only the final table structure lives here:

| Dimension | Score | Weight | Total |
|-----------|-------|--------|-------|
| (see unmassk-standards) | X/10 | per standards | XX |
| **Total** | | | **XX/110** |
```

## Quick Reference

| Step | Agent | Parallel? | Gate |
|------|-------|-----------|------|
| 0 | ORCHESTRATOR (Claude + User) | - | Opening note saved; branch (gitflow only) |
| 1 | Bilbo | No | Summary table |
| 2 | Dante / Ultron | No | Tests pass (if needed) |
| 3 | Dante | Yes | 97%+ coverage, tests pass x2 (audit gate — supersedes merge override) |
| 4 | Cerberus + Argus | Yes | Score + integrity findings |
| 5 | Ultron | Depends | Tests pass after each fix |
| 6 | ORCHESTRATOR | No | Every finding mapped to a fix, tests x2 |
| 7 | Dante | No | Tests pass x2 |
| 8 | Moriarty | No | Report + raw log on file |
| 9 | Dante / Ultron | No | Adversarial tests pass x2, breaks fixed once |
| 10 | Yoda | No | Verdict + path to 110 |
| 11 | Ultron / Dante | Depends | What Yoda named, fixed once |
| 12 | Alexandria | No | Docs updated |
| 13 | ORCHESTRATOR (Claude + User) | - | Merged (per repo_type) + closed |

## Additional Resources

### Standards

The enterprise quality standards (tiers, scoring, checklists, anti-patterns — calibrated to "the system against itself", no OWASP or external-attacker material) are in a separate skill: **`unmassk-standards`**. Every crew agent loads it on boot via the `skills: unmassk-standards` declaration in its frontmatter. The audit workflow references standards but does not bundle them.

### Prompt Templates

Every template below is stack-agnostic: `[MODULE_PATH]` stands for the module's real path in the audited project (not a fixed layout), and `[TEST_CMD]` / `[FORMAT_CMD]` / `[LINT_CMD]` stand for that project's own commands. Resolve them the same way `unmassk-flow` resolves its stack-specific values (`unmassk-flow/SKILL.md` §"Project profile"): read the project's `CLAUDE.md`/git-memory profile first; if not declared, detect from the repo (`package.json` scripts, `pyproject.toml`, `Makefile`, `go.mod`, etc.) and record what you found. Never assume a fixed path like `backend/src/`, a fixed runner like `npx vitest`/`npx prettier`, or a specific validation library like Zod — those are project-specific, not universal defaults.

- **`prompts/bilbo.md`** -- Module scan prompt template
- **`prompts/ultron.md`** -- Fix findings prompt template (build order audit-fix)
- **`prompts/house.md`** -- Diagnostic prompt templates (new investigation, continue, re-diagnose)
- **`prompts/dante.md`** -- Golden tests, adversarial tests and broken tests prompt templates
- **`prompts/cerberus.md`** -- Enterprise audit prompt template (one pass, no re-audit)
- **`prompts/argus.md`** -- Deep integrity audit prompt template
- **`prompts/moriarty.md`** -- Adversarial validation prompt template
- **`prompts/yoda.md`** -- Senior review prompt template
- **`prompts/alexandria.md`** -- Documentation prompt template
