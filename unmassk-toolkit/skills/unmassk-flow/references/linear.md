# Linear build

Open this when the build mode is linear: prototypes, spikes, exploration, or any work whose shape is still being discovered, where seeing it run teaches more than defining done up front. If the behavior is clear and being wrong is costly, use `references/test-first.md`.

Linear changes the order of code and tests, not the bar: the code meets the tiers of `unmassk-standards/references/standards.md`, and the test rules of Build in `SKILL.md` apply.

## Order

1. **Ultron implements**: the plan's phases in Full (wave execution), the change itself in Short.
2. **Dante writes the tests for what was built**, once per phase and before that phase's review (the whole change in Short). He covers what changed: happy path, error paths and edge cases. Follow the tier system (`standards.md` §1) and the Real-verification checklist (§9). He also breaks each important behavior on purpose, on a copy, and reports the mutants that survive: in linear nobody else runs that check.
3. The review starts (Review in `SKILL.md`), identical to test-first.
