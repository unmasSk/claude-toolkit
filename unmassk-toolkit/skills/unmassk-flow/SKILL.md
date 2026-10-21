---
name: unmassk-flow
version: 2.0.0
description: >
  Builds a feature, fix or refactor from idea to merged code, sizing the procedure to the risk
  (Trivial, Short or Full). Use for any work that requires writing code, Trivial included: when
  the owner asks to build a feature, implement, add functionality, fix a non-trivial bug or
  refactor; to open or change a plan that spans sessions; or when something that already worked
  breaks. Not for questions about how a plan or issue is going (answer from
  the plan and the issue), choosing between options (unmassk-council), undefined requirements
  (unmassk-grill) or audits (unmassk-audit).
---

# Flow — from idea to merged code

Eight parts take work from a request to a merge, in this order: Triage, Ideas, Research, Plan, Build, Review, Document, Close. Each goes by its name only, never a number. The procedure chosen in Triage decides which of them run. Decisions are saved through `unmassk-memory`; agents are launched with `subagent_type: unmassk-toolkit:<agent>` (bilbo, ultron, dante, cerberus, argus, moriarty, yoda, house, alexandria).

Flow only describes the process of building. How to talk to the owner, how to prompt agents, the blind-review template, and the common rules on tests, commits and cleanup live in `unmassk-core`. Where this skill restates one of them at the point of use, `unmassk-core` is the authority. Each agent's card holds how that agent works; this skill says when to launch it, what to give it, and what to do with its report.

Flow runs in any project and any stack. Every stack value (test, lint and build commands, plan directory, coverage bar, threat model) comes from the project profile (see "Resolve the project's profile"), never from this skill.

## Words used here

| Word | Means |
|---|---|
| **Milestone** | A group of tasks (a GitHub milestone). |
| **Task** | One unit of work: one branch, and one issue when it crosses sessions. |
| **Phase** | A block of a task's plan. |
| **Step** | One numbered item inside a phase. The owner addresses work by number: «#101, 1.2» is phase 1, step 2 of task #101. |
| **Procedure** | Trivial, Short or Full: which of flow's eight parts a piece of work runs. |
| **Session** | One conversation. Not a plan level; a task can stop halfway through one. |
| **Base commit** | The commit the work starts from. Every diff handed to a reviewer is taken against it. |

## When to use

Use for any work that writes code. For an incident (something that was signed off and then broke), read `references/incident.md`. For a plan that spans sessions, read `references/plan.md`.

Do not use for:
- A question about how a plan or issue is going: read the plan and the issue and answer.
- Ideas, or a choice between known options: `unmassk-council`.
- Requirements still undefined: `unmassk-grill`.
- An audit of existing code: `unmassk-audit`.

## Before you start

1. **Check that no task is in flight** (Short and Full; a Trivial goes on the open branch if there is one). Run both checks; do not rely on recall:
   - `git branch --no-merged <integration branch> --list 'feat/*' 'fix/*' 'refactor/*'` (gitflow; the integration branch is `dev`). A listed branch is open work. Trunk has no work branches: only the plan check applies.
   - `find <plan directory> -maxdepth 1 -name '*.md' -exec grep -L 'Status: COMPLETED' {} + 2>/dev/null` (default plan directory `docs/plan/`; the project profile may name another). A listed file is an open plan; no output, including a missing directory, means none.
   - If either returns something, finish that task through Close or park it: `gitmem wip` the current state and tell the owner in one line where it stopped. Do not write a Next; the owner asks for the session close.
   - An incident repair is exempt: park the open task the same way and start the repair.
2. **Wait for an explicit go.** A question ("what's next?", "is this ready?") and a tepid reply ("ok", "looks fine") are not a go. When the last message was one of those, ask «shall I start?» and stop. Create no branch and launch no agent before the yes.
3. **Resolve the project's profile.** Read it first (`unmassk-standards` §10): declared in the project's `CLAUDE.md` or in git memory, never a loose file.
   1. Test, lint and build commands. For the test command: `gitmem search test command`. If undeclared, detect what the repo uses: `package.json` scripts, `pyproject.toml`, `go test ./...`, `cargo test`, a `Makefile` target. Never impose a runner the repo does not use.
   2. Only when it was undeclared: write the resolved test command to `.claude/project-memory/config.json` under `test_command`, and save it as a memo so a person can find it. Nothing runs it automatically; the pipeline runs it at Build, Review and Close. The best moment to set it is project start (`unmassk-project-lifecycle`).
   3. Full only: the threat model (an external attacker, or the system harming itself). If the profile does not declare one, ask the owner and save his answer as a decision. Argus cannot audit without it: pass it in his CONTRACT slot.

## Lanes

Each agent does its own work and nothing else. There is no "small enough" exception.

| Agent | Does | Never does |
|---|---|---|
| **Orchestrator (you)** | Decides what, who and when; writes the plan; runs flow; does the Trivial procedure itself. | Writes production code or tests outside the Trivial procedure. |
| **Bilbo** | Maps the codebase, traces dependencies, researches the web. Read-only. Rates risk or compares options only when the prompt asks. | Fixes, reviews, gives security verdicts, writes docs. |
| **Ultron** | Implements production code. Reads the area he changes before editing. | Writes or edits tests; explores beyond the area he changes; reviews; attacks. |
| **Dante** | Writes tests. Reads the code and tests he works on. | Implements production code; maps the codebase beyond the files under test. |
| **Cerberus** | Reviews code and tests. | Fixes what he finds. |
| **Argus** | Audits security against the project's threat model. | Fixes, reviews code quality, exploits, gives the final verdict. |
| **Moriarty** | Tries to break the shipping candidate, on a copy. | Fixes, reviews, audits patterns, writes in the project beyond his memory and reports. |
| **Yoda** | Gives the final production-readiness verdict. May re-run another agent's claim on a copy. | Fixes, re-reviews, writes tests or docs, audits security, attacks. |
| **Alexandria** | Syncs docs to reality; writes the CHANGELOG. | Implements, tests, fixes the bugs she notices (she reports them), commits, edits plan files. |
| **House** | Reproduces and diagnoses a failure nobody can explain; instruments temporarily and removes it. | Fixes, edits logic, writes tests, reverts files, commits. |

The two cross-assignments that break the pipeline are Dante mapping the codebase (send Bilbo) and Ultron writing tests (send Dante). When Ultron needs a test change to reach green, he stops and reports; send a fresh Dante at once.

## Rules that hold everywhere in flow

1. **The visible list is the plan pane.** Before the first step, send the whole task to the pane with the `mcp__unmassk-toolkit__plan` tool: the issue (or the request, when there is none), every phase and every step, each with its number («#101 · 1.2»). Mark each step there as it starts and as it ends; the agents of the step in progress show under it by themselves. Tick a step only after its verification passes, in the plan file and in the pane in the same act.
2. **Commits.** After every agent that changes tracked files, save a WIP with exactly the files in that agent's Files changed section (`gitmem wip "<message>" --path <file> --path <file>`), so one agent's WIP never takes another's half-done files. Agents never commit. Report files live in `.claude/informes/`, outside git, and need no WIP. When a step is done, apply the step-commit rule of `unmassk-core` (common rule 14). In Short the whole change is one step.
3. **Every agent runs once; every fix is done once.** Nobody is launched again over a fix. There is no repeat-until-clean loop. The one exception is an agent that stopped before doing its work (Argus `BLOCKED`, House `NO DIAGNOSIS`, Ultron `BLOCKED` or `NEEDS_CONTEXT`, Dante `BLOCKED`, Yoda `CANNOT JUDGE` for a missing input): supply what it lacked and send a fresh one, once. A second stop goes to the owner. The same holds when Moriarty's raw log is missing or was taken on a commit outside this work: Moriarty runs once more. A log from before the fix pass is expected and is not a reason to run him again.
4. **Fixes go to a fresh agent of the owning type** (code: Ultron; tests: Dante), with the reviewer's report and the exact files. Resume an agent only when the owner names it. Every Ultron and Dante prompt names its build order: `test-first`, `linear`, or, in a fix pass, `audit-fix` together with the task's mode (`audit-fix, test-first` or `audit-fix, linear`): the report's findings are the contract, the existing tests stay green, and the mode tells Dante which Mutants line his report carries.
5. **A fix pass is one fresh Dante per review round, taking every report of that round, and Ultron split by file group.** Ultron's fixes from the round's reports go in one prompt per file group, launched together. Never two agents on the same file at once: a fix that needs a file another running agent holds (a later wave included) waits until that agent finishes. When a finding needs a new test, Dante writes it first and Ultron fixes after, in both build modes. Fixes on separate modules run together. The fixer runs the phase's scoped tests; Close runs them again.
6. **Before fixing a finding, check that it is real:** every finding carries its real case, how often everyday use reaches it (for example «2 of 528 notes», «every save»), or «not in real use» when no everyday path reaches it. Zero in today's data is not «not in real use» when the path exists (new code has no data yet). Write the real case yourself when the report does not give it. Fix every real finding, nitpicks included. A finding not in real use is noted and left, except a T1 from Yoda or a round-trip failure: that goes to the owner, and is left only with his yes. A real T1 or T2 from any reviewer blocks the merge until it is fixed and has a green test, which Dante writes in the same pass; a T2 is left unfixed only with the owner's yes, and then carries a `Waiver:` line (rule and reason) in the commit of the fix (the step commit, once steps are squashed). A reviewer's Pre-existing items inside the task's files are fixed in the same pass; outside them, offer each as a separate task (rule 8).
7. **Open an agent's report by its index**, then only the sections you act on:
   - Cerberus: Changes required, Pre-existing, Verdict, and the "outside my domain" line of each finding section (a flag for Argus is there).
   - Argus: Findings, Verdict.
   - Yoda: Findings, Path to 110, Recommendations to the orchestrator.
   - Moriarty: Attempts (the confirmed breaks), Surviving mutants, Unverified, and the raw-log path.
   - Ultron: Status, Deviations, Beyond the tests, Bugs seen, not fixed, Observations for the orchestrator, and Options when he stopped.
   - Dante: Result, Files changed, Mutants, Bugs found, Not tested. On a Dante `FAIL`: a test red on the code is a bug for Ultron in the phase's fix pass; a contract test red for the wrong reason goes back to a fresh Dante before Ultron starts; a mutant he could not kill is named to the reviewers.
   - House: Root cause, Fix to route, Cleanup verification, and in an incident the Proposed incident note.
   - Bilbo: Map, Confirmed findings, Likely findings, Figures with their source, Handoffs, DEAD-ENDS.
   - Alexandria: Files changed, Contradictions, Shipped with no home, Contracts.
8. **Name a new idea, do not build it.** Scope creep gets one line: «That is a separate task. Want me to open an issue for it?» Then wait.
9. **Enterprise is the bar; no over-engineering, no academic code.** Build what the task needs, at the quality a professional team ships, and stop there: no abstraction with one user, no option nobody asked for, no handling of a case that does not happen in real use (rule 6), no pattern for its own sake, and tests in proportion to the change (each behaviour once, not every combination). Put this line in the LIMITS of every Ultron and Dante prompt.

## Triage (orchestrator)

Classify the work with the owner before anything else.

### Choose the procedure

| Procedure | The work | What runs |
|---|---|---|
| **Trivial** | Quick, isolated, checkable at a glance, and none of: logic change, data, security, a seam, new behavior, or something other modules depend on. Examples: a typo, a button width, a config value. | Triage only. You do it: no agents, no plan, no branch, no list except the one `Procedimiento: Trivial` selector box. One `gitmem work` commit, on the open work branch if there is one, otherwise on `main` (trunk) or `dev` (gitflow). If the repo has tests, run once the ones covering the touched file. |
| **Short** | Bounded logic: 1-3 files, one part of the project, no data, memory, security or money. A producer-consumer seam counts as data and goes to Full. Example: fix a known bug in one function. | Triage, Ideas, Build, a short Review, and Close: Ultron and Dante in the order of the build mode, Cerberus reviews code and tests, one fix pass. No Plan, Argus, Moriarty, Yoda or Alexandria. Research is skipped, or a quick pass only if the owner asks; when the size or the seam cannot be told without looking at the code, ask Bilbo one pointed question first (for «fix the save button»: what does the save button do when pressed?). If the project has no tests, Dante is not launched and none are set up here. |
| **Full** | Data, memory, security or money; a new capability; several parts at once; any seam. | All eight. When the work is large (3+ new files or 5+ modified), Build runs in several Ultron rounds and Research goes deep. |

1. State the procedure in one line before starting. When in doubt, take the bigger one, unless the owner asked for speed and the work touches no data, memory, security or money.
2. A Trivial that grows on inspection becomes Short. A Short that turns out to touch data, memory, security, money or a seam becomes Full, including when Cerberus flags something for Argus. A Short promoted to Full keeps what already ran (nobody runs twice), writes the plan from the current state, and adds what Full adds: Argus on the diff, the final round and Document. Its `Procedimiento: Corto` box is replaced by `Procedimiento: Completo`, and the Full boxes it lacks are created, so the closing check enforces the Full list.
3. Create the task-list box of the chosen procedure: `Procedimiento: Trivial`, `Procedimiento: Corto` or `Procedimiento: Completo`. Use that exact text (a hook matches it) and create only the boxes that procedure's checklist lists.
4. The owner speaks Spanish: Trivial, Short and Full are *procedimiento trivial, corto, completo*.

### Declare the seam

State whether the work touches a producer-consumer seam (network call, DB read or write, a file written and read back). Run the mechanical check in `unmassk-standards` §34.1 for every procedure, Trivial included; "no seam" needs that check, not a guess. A seam always makes the work Full. In Short and Full, record the declaration in memory with the start; a Trivial records nothing beyond its `gitmem work` commit.

### Run the interview (Short and Full)

Invoke `unmassk-grill` in pipeline-invoked mode (5-question cap) to catch vague wording and bundled scope. Start Ideas from any open branches it logged.

### Open the task

1. In gitflow, create one branch per task after triage. In trunk, `main` is the working branch. Trivial gets no branch.
2. The Full plan file is written without asking (Plan). What needs the owner's yes is making the task span sessions: its issue and its record (`references/plan.md`).
3. Record the start in memory (Short and Full).

## Ideas (Short and Full)

Settle the decisions that change the outcome before building. Name gray areas specific to this task, not generic categories.

1. State the domain boundary: what the work delivers.
2. Search memory for decisions that already apply: `gitmem search <zone or word>`, or `--id D-xxx`.
3. Put each gray area to the owner as a question, one at a time, with 2-3 approaches, their trade-offs and one recommendation.
4. Save each decision the moment it is made, with its why and every option it beat.
5. Decide the build mode (below).

**Build mode.** Choose it now, once the shape of the work is known:
- Clear, testable behavior that is costly to get wrong: **test-first** (`references/test-first.md`).
- Exploratory, throwaway, or shape still unclear: **linear** (`references/linear.md`).
- Uncertain: test-first, the safer default for real code.

Record the mode in the plan (Full) or state it in one line right after Ideas (Short). Short follows the mode too: in test-first, Dante's tests of the change come before Ultron.

**Exit.**
- All gray areas resolved: continue (Full to Research, Short to Build).
- The owner says «enough, let's build»: continue with the decisions locked so far.
- The work is infeasible: close the issue with the rationale if there is one, delete the branch, stop.

## Research (Full; Short: skip, or a quick pass only if the owner asks; Bilbo's one pointed question for sizing is in Triage)

Research is Bilbo's lane only.

1. Pick the depth from the table (a large Full takes Deep).

   | Depth | What Bilbo is asked | Use when |
   |---|---|---|
   | Quick | A pointed question: one fact (syntax, where something lives, who calls it). | The approach is known. |
   | Standard | A map of an area with its dependencies. | Choosing between options, a new integration. |
   | Deep | A sweep: the complete list (every caller, every use, the whole risk surface), with his coverage gate. | Architecture decisions, novel problems. |

2. Launch Bilbo with: the question, the target directories, the depth, what to leave out, whether to rate risk or compare options, and the decisions from Ideas as constraints (never as a conclusion to confirm).
3. If he returns `PARTIAL`, split what is left by directory and launch several Bilbos together, each with its own question; or accept the gap and write it in the plan.
4. His report lives in `.claude/informes/`, outside git, so it dies with the machine. There is no RESEARCH.md. What must outlive the session is saved:
   - his DEAD-ENDS section, as `unmassk-core` describes;
   - anything permanent he found (a pattern, a constraint, something waiting on someone), as a memo, a decision or a blocker, keeping his `UNVERIFIED` tags.
5. Route his Handoffs: stale docs go into Alexandria's Document prompt; tags for Cerberus or Argus inform the plan and never enter their blind prompts.
6. If research shows the work is infeasible, close the issue with the rationale if there is one, delete the branch, stop. If the approach fails, pivot or stop.

## Plan (Full only)

Write the execution plan of this task: its phases and steps, and the order they run in. It is one file: when the task spans sessions, the same file is the plan's document and the task also has an issue (`references/plan.md`). Short and Trivial carry no plan file.

1. Write the plan at `<plan directory>/<type>-<name>.md` (default `docs/plan/`), where type is `feat`, `fix` or `refactor`. Create the directory when it does not exist.
2. Use this format. Every step has a checkbox. Tick it in the file when the step is genuinely done, with a one-line summary of where it stands; the visible list and, if the task has an issue, the issue's checklist say the same.

   ```markdown
   # <Name> Plan (task = issue #N)

   **Issue:** #N (only if the work crosses sessions)
   **Branch:** feat/<name> | fix/<name> | refactor/<name>
   **Procedure:** Full
   **Build mode:** test-first | linear
   **Base:** <sha> (trunk: filled in at Build)
   **Created:** YYYY-MM-DD

   ## Goal
   One sentence: what this delivers.

   ## Decisions
   The memory decisions from Ideas, by id, or a summary.

   ## Out of scope
   What this plan does not include, and the risks the zone's past incidents point at.

   ## Phases

   ### Phase 1: <name>
   **Files:** create / modify / test
   **Steps:**
   - [ ] 1.1 <specific action>
   - [ ] 1.2 <specific action>
   - [ ] 1.3 <verify: command and expected output>

   ### Phase 2: <name>
   **Depends on:** Phase 1
   ...

   ## Wave map
   - Wave 1: Phase 1, Phase 2 (independent)
   - Wave 2: Phase 3 (depends on Phase 1)
   ```

3. When the work has a seam, add a round-trip step owned by Dante (see "Extra checks when the work has a seam").
4. Run the plan checker before building:
   - Does every decision from Ideas have a step?
   - Does every step have a way to verify it?
   - Are dependencies between steps explicit?
   - Does the plan respect the restrictions Bilbo's map quoted for the zone?
   - Amend the plan for every gap.
5. Build the visible list from the plan.

## Build (Ultron and Dante)

Build each phase of the plan, or the whole change in Short.

### Before building

- Record the base commit first, before any agent builds or saves a WIP. Gitflow: the merge-base with the integration branch. Trunk: the current `HEAD`, written into the plan's `Base:` line; Short has no plan, so state it in one line. Every reviewer's diff is taken against it.
- Full: read the plan file. If it does not exist or the plan checker has not passed, stop. Do not build from memory or conversation alone.
- Read the build mode and open its reference: `references/test-first.md` or `references/linear.md`. Name the mode in every Ultron and Dante prompt (rule 4).
- Refactor: Dante writes and checks the golden tests of the affected code first.
- Trunk: an incident repair made while this task was parked lands inside that range. Name its commits as out of scope to every agent that works from the diff.

### Run the waves

1. Read the wave map.
2. Launch one Ultron per phase of Wave 1, all together, never two on the same file. In test-first, Dante's tests for each phase come first.
3. Wait for Wave 1 to finish, then launch Wave 2. Repeat until every wave is done.
4. When a phase is built (and, in linear, Dante has tested it), start its review (Review, per-phase review) while later waves continue.
5. Run tests in parallel only when each agent has its own test database. No setup for this exists yet, so run tests in parallel only in projects that already have it.

### Test rules (both build modes)

1. Tests run against a real dependency, as common rule 31 in `unmassk-core` says.
2. At least one test drives the change through the entry point the user or the system uses (CLI, hook, script, endpoint), and, when there is a seam, one wires it end to end (`unmassk-standards` §34.5).
3. The coverage gate is the project profile's bar.
4. Test quality follows the Real-verification checklist in `unmassk-standards` §9.

### What Ultron decides on his own

His card holds what he fixes without asking and when he stops. You act on his report: rule 7 lists the sections. A bug he saw inside the task's files is fixed in the phase's fix pass (rule 6). A bug outside them, or an improvement he spotted, is offered as a separate task (rule 8).

### When Ultron stops

| He reports | You do |
|---|---|
| A deviation that breaks a later step | Amend the plan file; execution resumes from the amended step. In Full the plan file is the truth; Ultron does not improvise later steps. |
| One of Dante's tests is wrong | A fresh Dante corrects it at once (`references/test-first.md`). |
| `BLOCKED` or `NEEDS_CONTEXT` for an answer | Answer it, or ask the owner; then a fresh Ultron with the answer in KNOWN (rule 3). |
| A vulnerability found mid-task | In Short, the work becomes Full. In Full, it goes into Argus's ARTIFACT for that phase. |
| `BLOCKED — circuit breaker: I fail the same step 3 times` | House (below). |

### When Ultron fails the same step three times

1. Stop execution: let the agents already running finish and save their WIPs, then launch House, and launch nothing else on the tree until he returns.
2. House's prompt says **construction** and carries Ultron's `BLOCKED` report (his three attempts), the step's plan line, the failing command or test, where the project writes its logs, and any reviewer finding on the same code.
3. Save no WIP until House's Cleanup verification shows no instrumentation lines beyond the baseline.
4. Act on his status:
   - `ROOT CAUSE` or `PROBABLE`: a fresh agent of the type his Fix to route names (Ultron or Dante) fixes it with his diagnosis; a `PROBABLE` fix is labelled so. When the cause is a behavior no test covers, Dante writes that test first.
   - `NO DIAGNOSIS`: get the data his report names (production logs, a Bilbo map), then House again (rule 3).
   - `ESCALATED`: tell the owner in one line, with what the report says is needed next. House goes past three hypotheses only with the owner's written authorization in his prompt.
5. Amend the plan when the root cause shows the step itself is wrong.

This is ordinary work, not an incident, and records no scar. An incident is something already signed off that then broke: `references/incident.md`.

## Review (Full; Short: Cerberus only, launched as below, against the base commit stated in Build)

Reviews run in two parts: per-phase review while building, and one final round when every phase of the plan is done. The order never changes and nobody runs twice (rule 3).

### How to launch each agent

- **Cerberus, Argus, Yoda: blind.** Fill every slot of the blind-review template in `unmassk-core`. Give no conclusion and no list of what to look for.
- **Moriarty.** TASK is one line: the target and the win condition. Never a list of attack vectors, a suspicion or a "look at X"; Argus's Hypotheses for Moriarty are not passed to him. The facts still travel: the build mode, the plan path, the base commit, the seam declaration from Triage, the scoped test command, and any `[DOMAIN SKILL]` block.
- **Yoda's slots.** ARTIFACT: the whole diff against the base commit, plus the path of every Moriarty raw-log file (commands and output; never his summary or verdict word). Without the log Yoda answers `CANNOT JUDGE`. CONTRACT: the plan file path and the issue. SCOPE: as the template says. When there is no seam, re-run the §34.1 check on the final diff and add that output; never the one from Triage.

### Per-phase review

Start it for a phase as soon as that phase is built.

1. Launch **Cerberus and Argus** together. Their ARTIFACT is the diff of the phase's files against the base commit, code and tests. Argus is never skipped in Full. Each writes a report file that starts with an index.
2. Fix what they flagged, once: code by Ultron, tests by Dante (rules 4-6). A file a later wave is still editing waits for that wave (rule 5).

### Final round

Start it when every phase of the plan is done.

1. **Moriarty**: one per independent part of the work, all launched together, each once, at the end, over the code and the tests as already fixed. In test-first he also runs the mutation check on the contract's behaviors and data-losing error paths, on a copy, and reports the mutants that survive.
2. Every Moriarty verdict goes on to one fix pass and then Yoda. Fix what he broke, once (rule 5): each confirmed break gets the code fix from Ultron and a regression test from Dante in the same pass; surviving mutants get their tests too. His `Unverified` items are not findings unless you confirm them (rule 6).
3. **Yoda**, once. He finds his own evidence in the code, tests and memory. 110 is perfection: with a lower score he says what to fix to reach 110, or why 110 cannot be reached (for example, no E2E tests planned).
4. Act on his verdict, once. Taking 110 as given, Close's scoped tests check the fixes.
   - `APPROVED`: merge.
   - `APPROVED WITH CONDITIONS`: fix the T3 points, nitpicks included, in the same single pass. Tell the owner in one line any condition that is not a fix (such as the parts Moriarty did not attack); he decides whether it becomes an issue. Then merge.
   - `REJECTED`: the merge waits until every T1 and T2 he named is fixed and its test is green (rule 6).
   - `CANNOT JUDGE` for a missing input (the log path, the no-seam output, the contract): supply it and send a fresh Yoda, once. For scope that grew, scope not defined, or a design decision: ask the owner.
5. Alexandria documents the result (Document).

### Extra checks when the work has a seam

Triage declared the seam.
1. Dante owns the round-trip check, never Ultron. It has its own step in the plan and in the visible list.
2. Cerberus's card already checks that no expected value in the round-trip test is a hand-typed literal. Do not add it to his prompt; make sure the round-trip test is in his ARTIFACT.
3. Moriarty runs his Round-Trip Sabotage mandate against a copy of the real dependency, never the original.
4. Yoda applies his Round-Trip Evidence Rule to the artifact.
5. A seam found during Build that Triage did not flag: amend the plan to add the round-trip step before review proceeds. The no-seam output from Triage is then void.
6. A seam Moriarty's raw log shows that Triage did not declare: Dante writes the round-trip test in the fix pass after Moriarty, and Yoda gets no no-seam output.

### If a regression appears after a fix

The scoped tests at Close catch it. Send the failing test to Ultron (code) or Dante (test). Do not run the review again. A red that one fix did not clear, or that nobody can explain (it passes alone and fails next to the others), goes to House, told **construction**.

## Document (Full)

1. Launch Alexandria in default mode. Give her the diff of the work against the base commit, the Decisions ids of the plan, any stale docs Bilbo flagged, and, if the project already squashes WIPs into step commits, those commits too. WIPs are working saves; she works from the diff.
2. When the work has a seam, also give her Yoda's verdict and the path of the round-trip evidence: she records the verified contract.
3. She documents the new capability for the three audiences in `unmassk-core` (Documentation discipline), updates the module `CLAUDE.md` when patterns changed, and writes the CHANGELOG entry under `[Unreleased]`. You never write the CHANGELOG.
4. Read her index (rule 7). A Contradiction where the code is wrong is a defect: route it as a finding (rule 6), or to the owner when it needs his decision. Plan files are prescriptive: she reports, never edits them.

## Close (orchestrator)

Run after Review (and Document, in Full). Everything here runs without asking, except where marked.

1. **Run the tests that cover the change, and only those** (a path or `-k` filter on the touched modules and their tests). Do not skip this. Use the command from the profile. Every scoped test must pass before merging. A red blocks the merge: route it as in "If a regression appears after a fix". The whole suite runs in CI at staging or production, and by hand only if the owner asks.
   - A project with tests but no findable command: stop and ask the owner.
   - A Short in a project with no tests: say so in one line and continue.
2. **Merge.** Read `repo_type` in `.claude/project-memory/config.json`; when undeclared, treat the main branch as protected.
   - Gitflow: `git switch dev && git merge --no-ff <branch>`; the merge commit lists the commits of the work; then `git push origin dev`. No gate stops a merge into dev: the work already passed its reviewers.
   - Trunk: the commits land on `main`; push `main`. There is no branch or merge step.
3. **Close the issue**, if the task has one: `gh issue close N --comment "Task complete — <summary>"`. In flow, "shipped" means merged to the integration branch (`dev`, or `main` in trunk).
4. **Delete the branch** (gitflow only; local and remote).
5. **Full only:** add `**Status: COMPLETED**` to the plan's header.
6. Write nothing else: the closing comment and the step and merge commits are the record. No separate context commit. A Short or Trivial gets its CHANGELOG entry at session close, from Alexandria in close mode.
7. **Say one line:** the task is closed, and name the next task the owner already approved (the next task of the milestone he approved, for example). Go on to it without asking. Ask only when no approved task comes next.
8. **Above dev, always ask first.** A merge from dev to staging or production needs the owner's yes and passes the heavy gate: Cerberus and Argus on the whole incoming batch, and Alexandria in merge mode checking the CHANGELOG and the version claims against it. CI runs the full suite on push.

### If the merge fails

1. Do not force push.
2. List the conflicting files.
3. Resolve a simple conflict and finish it with `git merge --continue`.
4. For a complex conflict, escalate to the owner before going on.
5. After resolving, re-run the scoped tests of the touched area. Do not run the review again.
6. A merge that fails completely: escalate to the owner.

## If something goes wrong

| Situation | Action |
|---|---|
| Ideas or Research: the work is infeasible | Close the issue with the rationale if there is one, delete the branch, stop. |
| Research: the approach does not work | Pivot or stop. |
| Research: Bilbo returns `PARTIAL` | Split the rest by directory into new questions, or accept the gap in the plan. |
| Plan: the checker finds gaps | Amend the plan before building. |
| Build: Ultron stops | See "When Ultron stops". |
| Build: the owner abandons the task | `gitmem wip` the state, tell him in one line where it stopped. |
| Review: Argus returns `BLOCKED` (no threat model) | Settle the threat model with the owner, then a fresh Argus (rule 3). |
| Review: findings from Cerberus, Argus, Moriarty or Yoda | Check each is real, fix once by fresh agents, no re-review. |
| Review: Yoda scores below 110 | Fix what he named, once. He does not run again. |
| Review: Yoda returns `CANNOT JUDGE` twice | Ask the owner. |
| Anywhere: a red nobody can explain | House, told construction. |
| Close: no test command found (project has tests) | Stop and ask the owner. |
| Close: merge conflict or failed merge | See "If the merge fails". |

## References

- `references/test-first.md` — open when the build mode is test-first.
- `references/linear.md` — open when the build mode is linear.
- `references/plan.md` — open to propose, open, change or close a plan that spans sessions.
- `references/incident.md` — open when something already signed off breaks.
