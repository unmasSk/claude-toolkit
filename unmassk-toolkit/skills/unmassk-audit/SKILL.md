---
name: unmassk-audit
version: 1.1.0
description: Use when the user asks to "audit a module", "audit this codebase", "code audit", "enterprise review", "launch audit", "review against standards", or mentions auditing EXISTING code against enterprise standards. Works with any stack or language. Also use when resuming an audit in progress.
---

# Enterprise Audit

## Overview

Structured 14-step workflow for auditing any module against enterprise quality standards. Stack-agnostic — works with any language, framework, or test runner. Each step assigns a specific agent role (orchestrator, explorer, implementer, tester, reviewer, documenter). The process produces a weighted score out of 110 and a final senior verdict.

## When to Use

- User requests auditing any module (backend, frontend, library, service)
- User says "audit", "enterprise review", "launch audit"
- Resuming an in-progress audit (check TodoWrite for current step)

Do NOT use for: one-off code reviews or quick linting checks.

**Audit vs. build pipeline:** this skill is for reviewing an EXISTING module against enterprise standards. Use `unmassk-flow` (the build pipeline) when BUILDING something new. "Auditing" = existing code → standards gap analysis. "Building" = new code → Flow's definition-of-done pipeline. Do not confuse the two.

## Workflow

### Initialization

Before step 0, create a TodoWrite with one item per step (steps 0-13). Update status after completing each step. Issue a WIP commit after every step. Only two real commits: step 0 (context) and step 13 (closure).

### Step 0 -- Preparation (ORCHESTRATOR (Claude + User))

1. Point the audit at an issue. If one already covers the target, use it. If none does, **propose it in one line and wait — you never open one on your own judgement** (the protocol, the labels and the template are in the memory skill's `references/issues.md`). If the user declines, the audit still runs; the opening note simply carries no issue number.
2. Create the audit branch -- branch strategy depends on the project's `repo_type` (declared in `.claude/project-memory/config.json`; read it, do not redefine it here):
   - **gitflow** → `git checkout -b chore/audit-<module> dev`
   - **trunk** → work directly on `main`; no separate audit branch needed
3. Save the opening note:
   `gitmem note M --zones codeaudit <module-zone> "enterprise audit of <module> starts" --description "..." --stops no --issue N`
4. Load `unmassk-standards` skill for quality criteria + read any project-level CLAUDE.md

### Step 1 -- Scan (Bilbo Agent)

1. List ALL source files in the module (including subfolders), not just those in the issue.
2. Count LOC per file (`wc -l`).
3. List existing tests (detect test directory convention: `__tests__/`, `tests/`, `*_test.*`, `*.test.*`).
4. Map imports/exports and inter-module dependencies.
5. Run existing tests using the project's test runner (e.g., `npx vitest run`, `pytest`, `go test ./...` — detect from project config).
6. Produce summary table: file | LOC | existing tests | visible problems.
7. Flag large files, missing tests, or visible anti-patterns.

Prompt template: see `prompts/bilbo.md`

### Step 2 -- Fix Critical Blockers (Ultron)

Only if step 1 reported broken tests or critical blockers preventing further work.

1. Fix broken tests BEFORE touching source code.
2. Run tests twice to confirm stability.
3. If nothing is broken, skip to step 3.

### Step 3 -- Golden Tests (Dante -- parallel)

Characterization testing -- capture current behavior BEFORE any code changes. Run in parallel with step 4.

1. One Dante agent per source file (no overlap).
2. Target: 97%+ coverage with REAL assertions (no tautologies).
3. Include unit tests and integration tests appropriate for the stack (e.g., supertest for Express, httpx for FastAPI, net/http/httptest for Go).
4. Each agent runs tests twice for stability.

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
4. ONLY report -- never fix. Do not duplicate Cerberus surface-level checks.

ORCHESTRATOR (Claude + User) compiles findings from both Cerberus and Argus into a single findings table.

Prompt templates: see `prompts/cerberus.md` (Template 1) and `prompts/argus.md`

### Step 5 -- Tier Fixes (Ultron)

Order: T1 first, then T2, then T3. 1 agent per finding or group of findings in the same file.

1. Apply fix addressing root cause.
2. Clean documentation (JSDoc, docstrings, comments) per project conventions if touching the area.
3. Check file size after fix — flag if it grew significantly.
4. If fix makes a file excessively large, use architect-then-implementer pattern to split.
5. Run tests TWICE after each fix round.

Gate: tests pass after each round.

House circuit breaker: if Ultron fails the same fix 3 times, launch House (agent: `house`) to diagnose root cause before retrying. **Say in the prompt that this is a stuck fix, not a failure in delivered behaviour** — otherwise the diagnosis comes back proposing an incident note, and a defect found while fixing is ordinary work, not a scar.

Prompt templates: see `prompts/ultron.md` and `prompts/house.md`

### Step 6 -- Review Fixes (Cerberus)

1. Re-read ALL module files (not just touched ones).
2. Verify each original finding: closed? Root cause resolved?
3. Check for NEW findings introduced by fixes.
4. Verify no anti-patterns from standards.
5. Compare score before/after.
6. Run tests TWICE.

Verdict: APPROVED or REQUIRES ANOTHER ROUND. If another round needed, return to step 5.

### Step 7 -- Test Fixed Code (Dante)

1. Write tests for code Ultron changed in step 5 that lacks coverage.
2. Update golden tests if function signatures or behavior changed.
3. Run full module suite TWICE.

Gate: coverage maintained at 97%+. Same explicit audit exception as step 3 — the general merge-override does not apply; the audit gate supersedes it.

### Step 8 -- Adversarial Validation (Moriarty)

1. Moriarty attacks the full module across all attack phases.
2. Document each break with tier classification. Do NOT fix.
3. Output: attack report with confirmed breaks and per-phase summary.

Prompt template: see `prompts/moriarty.md`

### Step 9 -- Adversarial Tests (Dante)

1. Write regression tests for every confirmed break from step 8.
2. Write confirmation tests for attacks the module withstood.
3. Create `<module>.adversarial.test.*` (extension per project stack).

Gate: 0 T1 bugs, 0 T2 bugs unresolved. If T1/T2 bugs found, return to step 5.

Prompt template: see `prompts/dante.md` (Template 2: Adversarial Tests)

### Step 10 -- Re-Audit (Cerberus)

Full re-audit using the same closed checklist. Same process as step 6.

If score decreased or new T1/T2 findings exist, return to step 5. Repeat until APPROVED.

Prompt template: see `prompts/cerberus.md` (Template 2: Re-Audit)

### Step 11 -- Senior Review (Yoda)

1. Read ALL source files (not tests).
2. Run tests TWICE.
3. Write prose evaluation per dimension (2-4 sentences each).
4. Provide honest professional sentiment (one paragraph, no bullets).
5. Score on weighted table out of 110.
6. Verdict: APPROVED / APPROVED WITH RESERVATIONS / NOT READY.

If NOT READY, return to step 5 with Yoda's concerns. If Moriarty gave FAIL verdict, Yoda cannot give APPROVED (only RESERVATIONS if orchestrator accepted the risk).

Prompt template: see `prompts/yoda.md`

### Step 12 -- Documentation (Alexandria)

1. Read ALL WIP commits and changes accumulated during the audit.
2. Create or update module CLAUDE.md with patterns learned.
3. Update CHANGELOG.md under [Unreleased] with meaningful descriptions.
4. Cross-check documentation against current code state.
5. Update Alexandria memory.

Prompt template: see `prompts/alexandria.md`

### Step 13 -- Closure (ORCHESTRATOR (Claude + User))

1. Delete temporary files (`AUDIT-<module>.tmp.md`).
2. **MANDATORY: Run FULL test suite** (detect and use the project's test command — e.g., `npx vitest run`, `pytest`, `go test ./...`) — not just the module tests. If any test fails that was passing before the audit started, the audit introduced a regression. Fix before merging.
3. Final commit with score and closed findings.
4. Merge and push — strategy depends on the same `repo_type` read in step 0:
   - **gitflow** → `git checkout dev && git merge --no-ff chore/audit-<module>` then `git push origin dev`
   - **trunk** → changes already committed to `main`; push directly. No branch merge needed.
5. Close issue: `gh issue close N --comment "Enterprise audit complete -- YY/110"`
6. Delete branch (local and remote) if a branch was created (gitflow only).
7. Save the closing note, with the score and what it cost:
   `gitmem note M --zones codeaudit <module-zone> "<module> audited: YY/110" --description "..." --stops no --issue N`

## Loop Conditions

| Trigger | Action |
|---------|--------|
| Steps 8-9 find T1/T2 bugs | Return to step 5 |
| Step 6 or 10 gives REQUIRES ANOTHER ROUND | Return to step 5 |
| Step 11 gives NOT READY | Return to step 5 |
| Step 11 gives APPROVED or APPROVED WITH RESERVATIONS | Continue to step 12 |

## Commit Policy

| When | Commit type |
|------|-------------|
| Step 0 | a memo saying the audit starts -- real note |
| Steps 1-12 | checkpoints only (`gitmem wip "..."`) |
| Step 13 | `gitmem work "<module>: enterprise audit complete"` + the closing memo |

## ORCHESTRATOR (Claude + User) Rules

- Never edit code directly -- everything through agents.
- Never accept first re-audit as definitive after significant changes. Historical data: one module required 6 re-audit rounds.
- Always verify agent claims independently (run tests, check LOC).
- Distrust "all clean" reports without evidence. Agents tend to report "clean" without verifying all tiers.
- Never send 2 agents to the same file simultaneously.
- Never say "move code AS-IS" if it has anti-patterns from the enterprise standards.

## Agent Dispatch Rules

Each agent receives ONLY context and data, NOT instructions on how to work (agent system prompts handle that). Provide:

- Module path and file list
- Relevant findings or reports from previous steps
- Reference to `unmassk-standards` skill for quality criteria (agents load it on boot via the `skills: unmassk-standards` frontmatter declaration)
- Verification block (test commands, run twice)

Never send two agents to the same file simultaneously.

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
| 0 | ORCHESTRATOR (Claude + User) | - | Branch + context commit |
| 1 | Bilbo | No | Summary table |
| 2 | Ultron | No | Tests pass (if needed) |
| 3 | Dante | Yes | 97%+ coverage, tests pass x2 (audit gate — supersedes merge override) |
| 4 | Cerberus + Argus | Yes | Score + security findings |
| 5 | Ultron | Depends | Tests pass after each fix |
| 6 | Cerberus | No | APPROVED or loop |
| 7 | Dante | No | Tests pass x2 |
| 8 | Moriarty | No | Breaks documented |
| 9 | Dante | No | Adversarial tests pass x2 |
| 10 | Cerberus | No | APPROVED or loop |
| 11 | Yoda | No | Verdict |
| 12 | Alexandria | No | Docs updated |
| 13 | ORCHESTRATOR (Claude + User) | - | Merged (per repo_type) + closed |

## Additional Resources

### Standards

The enterprise quality standards (tiers, scoring, checklists, anti-patterns — calibrated to "the system against itself", no OWASP or external-attacker material) are in a separate skill: **`unmassk-standards`**. Every crew agent loads it on boot via the `skills: unmassk-standards` declaration in its frontmatter. The audit workflow references standards but does not bundle them.

### Prompt Templates

Every template below is stack-agnostic: `[MODULE_PATH]` stands for the module's real path in the audited project (not a fixed layout), and `[TEST_CMD]` / `[FORMAT_CMD]` / `[LINT_CMD]` stand for that project's own commands. Resolve them the same way `unmassk-flow` resolves its stack-specific values (`unmassk-flow/SKILL.md` §"Project profile"): read the project's `CLAUDE.md`/git-memory profile first; if not declared, detect from the repo (`package.json` scripts, `pyproject.toml`, `Makefile`, `go.mod`, etc.) and record what you found. Never assume a fixed path like `backend/src/`, a fixed runner like `npx vitest`/`npx prettier`, or a specific validation library like Zod — those are project-specific, not universal defaults.

- **`prompts/bilbo.md`** -- Module scan prompt template
- **`prompts/ultron.md`** -- Fix findings prompt template
- **`prompts/house.md`** -- Diagnostic prompt templates (new investigation, continue, re-diagnose)
- **`prompts/dante.md`** -- Golden tests + adversarial tests prompt templates
- **`prompts/cerberus.md`** -- Enterprise audit + re-audit prompt templates
- **`prompts/argus.md`** -- Deep integrity audit prompt template
- **`prompts/moriarty.md`** -- Adversarial validation prompt template
- **`prompts/yoda.md`** -- Senior review prompt template
- **`prompts/alexandria.md`** -- Documentation prompt template
