# Test-First Build

The *method* Flow's Execute step follows when the build mode is **test-first**. Which mode is chosen is the orchestrator's build-mode decision (decided at the end of Brainstorm); the guarantee that code ships with tests is a gate/hook — not this doc.

Reach for test-first when behavior is clear and being wrong is costly: business logic, APIs, anything with a real contract.

The code produced MUST meet the toolkit's quality bar in `unmassk-standards/references/standards.md` (tiers T1/T2/T3). Test-first proves the code *works*; standards proves it's *correct enterprise code*. Both apply.

## Two levels — do not confuse them

"Test-first" means different things at two scales, and collapsing them into one is the classic mistake (it's what makes people think the crew pipeline "violates TDD"). The toolkit runs both, and each has its own rule.

### Inter-agent (the crew pipeline) = ATDD / BDD — horizontal, and correct

Across isolated subagents, **Dante writes the failing tests that define the contract first → Ultron implements until they pass.** Tests precede code, as a batch. This is **acceptance-test-driven**, not unit-TDD: the tests encode what *"done"* means from the outside (behavior, acceptance criteria), not every internal unit.

This is "tests first, then code" — and at the acceptance level that is **the method, not an antipattern.** The "never write all tests first" rule in the next section does NOT apply here, and it can't: two isolated agents cannot ping-pong a per-unit loop without spawning dozens of times. Contract-first handoff is the right shape for the multi-agent layer.

- **BDD** — the user/orchestrator describes behavior in plain language (Given / When / Then). The entry point for non-developers: describe *what should happen*, the agent translates it down.
- **ATDD** — those behaviors become the acceptance tests Dante writes: the contract Ultron must satisfy for the work to be accepted.
- **Granularity guard (critical)** — Dante's upfront tests are **acceptance/behavior contracts, NOT the exhaustive unit suite.** Front-loading every unit and branch test before any code exists reintroduces the "imagined behavior" trap even inside ATDD. Keep the upfront set to the behaviors that define done; exhaustive unit/branch coverage comes from the intra-agent loop or post-implementation hardening.

### Intra-agent (inside one implementing agent's task) = TDD — vertical

When a single agent (Ultron) builds its slice within one context, it MAY run the classic micro-loop on its own code — no spawn cost, all in one head. Here the vertical rule applies in full:

> **Never write all tests first then all code.** That's horizontal slicing and it produces tests of imagined behavior. Go vertical: one test → one implementation → repeat.

1. **Tracer bullet** — write ONE test for ONE behavior. It must fail first (RED), for the right reason. Then minimal code to pass (GREEN). Proves the path end to end.
2. **Incremental loop** — for each remaining behavior, RED → GREEN, one at a time. Only enough code to pass the current test. Don't anticipate future tests.
3. **Refactor** — only once GREEN, never while RED. Apply standards.md (file size, typed errors, no duplication 3+). Run tests after each step.

**Reality check — this level is best-effort, not a gate.** Ultron is a subagent that receives a contract and fulfils it; whether it runs its own red-green micro-loop inside its task is desirable but not forceable or verifiable from outside. Treat vertical TDD here as the ideal an implementing agent SHOULD reach for, not a checkable guarantee. Expect most of what actually happens in practice to be the inter-agent ATDD level above; this lower level is "do it if you can", not a promise.

**The rule in one line:** the inter-agent contract is ATDD (horizontal, correct); "go vertical" governs the TDD an agent does inside its own task — as an aspiration, not an enforced gate.

## What to test

Follow standards.md §7 (backend) and §27 (frontend) for what to test per module type and at which tier. In short:
- Security modules: missing/manipulated token, privilege escalation, env guards (T1).
- API modules: happy path, invalid input, not found, DB error, permissions.
- Don't test: getters without logic, library internals, exhaustive param combos.

## Quality rules for the tests themselves

From standards.md §7: AAA pattern, `clearAllMocks` in `beforeEach`, no tautological assertions (`expect(true).toBe(true)` is forbidden, T2), no tests depending on execution order (T2), no mocks replicating production logic (T2). Test behavior through public interfaces, not implementation — a test that breaks on a rename was testing the wrong thing.

## Persistence

Acceptance criteria and behavior decisions that emerge → `decision()` in git-memory with their Why. Never to `.md` files.
