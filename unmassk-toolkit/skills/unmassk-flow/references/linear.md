# Linear Build (code-first)

The *method* Flow's Execute step follows when the build mode is **linear** — the default for prototypes, exploration, throwaway code, or when the shape isn't clear yet. Anywhere "let me see it first" beats "define the contract first."

Linear changes the ORDER of code vs tests; it does not lower the bar. The code still MUST meet the toolkit's quality bar in `unmassk-standards/references/standards.md` (tiers T1/T2/T3).

## Order — code first, tests after

1. **Ultron implements** the plan tasks (wave execution), in normal Implementation/Fix mode.
2. **Dante tests after**, in Verify (Step 5): covers what changed — happy path, error paths, edge cases — and runs the full EXHAUSTION PROTOCOL with the coverage gate (≥90% functions / ≥80% error paths) against the real code.

## When to pick linear over test-first

- The shape is still being discovered — writing a contract first would be guessing.
- Throwaway / spike / prototype where the code itself is the experiment.
- Exploration where "see it running" teaches more than "define done up front."

If the behavior is clear and being wrong is costly (business logic, APIs, a real contract) → that's **test-first** (`references/test-first.md`), not linear.

## What to test (after implementation)

Follow standards.md §7 (backend) and §27 (frontend) per module type and tier. Dante's hardening pass owns this in Verify — same coverage bar as any Flow feature.

## Boundary

This doc defines the linear method (code → tests). Which mode is chosen is the orchestrator's build-mode decision; the guarantee that code ships with tests is a gate/hook. Method / choice / guarantee — three different things.
