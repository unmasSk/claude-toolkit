# Test-First Build

The *method* Flow's Execute step follows when the build mode is **test-first**. Which mode is chosen is the orchestrator's build-mode decision (decided at the end of Brainstorm); the guarantee that code ships with tests is a gate/hook — not this doc.

Reach for test-first when behavior is clear and being wrong is costly: business logic, APIs, anything with a real contract.

The code produced MUST meet the toolkit's quality bar in `unmassk-standards/references/standards.md` (tiers T1/T2/T3). Test-first proves the code *works*; standards proves it's *correct enterprise code*. Both apply.

## Two levels — do not confuse them

"Test-first" means different things at two scales, and collapsing them into one is the classic mistake (it's what makes people think the crew pipeline "violates TDD"). The toolkit runs both, and each has its own rule.

### Inter-agent (the crew pipeline) — the complete test set first, and correct

Across isolated subagents, **Dante writes the failing tests that define the contract first → Ultron implements until they pass.** Tests precede code, as one complete batch: every behavior, error path and edge the change must honor, observed from outside. Internal structure (how Ultron splits the code into helpers) gets no tests of its own — the behavior tests cover it.

This is "tests first, then code" — and across agents that is **the method, not an antipattern.** Two isolated agents cannot ping-pong a per-unit loop without spawning dozens of times, so the tests go first as one complete batch. Contract-first handoff is the right shape for the multi-agent layer.

- **BDD** — the user/orchestrator describes behavior in plain language (Given / When / Then). The entry point for non-developers: describe *what should happen*, the agent translates it down.
- **The contract** — those behaviors, with every error path and edge, become the tests Dante writes: what Ultron must satisfy for the work to be accepted.
- **One complete contract (D-125, D-126)** — Dante enters ONCE and writes the whole test set before any code: every behavior, error path and edge the change must honor, all RED for the right reason. There is no later "hardening" pass. Dante comes back only inside the one-time fix passes after the reviewers (a contract test Ultron reports as wrong is the one case Dante is called before the reviewers: a fresh Dante corrects that test at once, since nothing can go green around it).
- **Ultron writes only what the tests ask** — no code a test does not require, no "while I'm here" extras. Exception, and a big one: something real that no test foresaw (e.g. a library limit). Then Ultron may add it, but his report must say so on its own line — what he added, why, and which behaviour has no test yet — and Dante writes its tests in the fix pass. Never silent.

### Inside Ultron's task — one red test at a time

Ultron never writes tests (lane discipline). He works through Dante's contract vertically: pick one red test → the minimal code that turns it green → next. Refactor only when everything is green, applying standards.md (file size, typed errors, no duplication 3+), and re-run the tests after each step.

**The rule in one line:** Dante writes all the tests once; Ultron turns them green one by one and writes nothing they don't ask for.

## What to test

Follow standards.md §1 (tier system — what's load-bearing per module) and §9's Real-verification checklist for what to test and at which tier. In short:
- Integrity/persistence modules: write-then-read verified across the real seam, atomic writes, no concurrent-write race (T1 — §3/§6/§34).
- Silent-failure paths: no swallowed catch, no masked exit code, a fail-open logs why it fell back (T1 — §4).
- Behavior/API modules: happy path, invalid input, not-found, error paths, whatever permissions the project actually defines.
- Don't test: getters without logic, library internals, exhaustive param combos.

## Quality rules for the tests themselves

From standards.md §9's Real-verification checklist: no tautological assertions (an always-true assert is forbidden, T2), no tests depending on execution order (T2), no mocks replicating production logic (T2), mocks cleared between tests. Test behavior through public interfaces, not implementation — a test that breaks on a rename was testing the wrong thing. **Run against the real dependency by default** — real DB / seam / files; mock only what genuinely cannot run in the test environment, and wire at least one test to the core seam end-to-end (`unmassk-standards` §34.5).

## Persistence

Acceptance criteria and behaviour decisions that emerge are saved as decisions, with their why. Never to a `.md` file.
