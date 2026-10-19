# Test-first build

Open this when the build mode is test-first: clear, testable behavior where being wrong is costly (business logic, APIs, a real contract). The code still meets the tiers of `unmassk-standards/references/standards.md`; the test rules of Build in `SKILL.md` apply.

## Order

1. **Dante writes the complete test set of each phase, once, before any code of that phase.** Every behavior, error path and edge the change must honor, observed from outside. Every new contract test starts red, for the right reason; golden tests start green and are listed as such. Internal structure gets no tests of its own. A non-developer can describe the behavior as Given / When / Then; Dante turns it into tests.
2. **Ultron writes only the code those tests ask for**, one red test at a time: pick one, write the minimal code that turns it green, take the next. Refactor only when everything is green (file size, typed errors; reuse an existing helper always, and extract new duplication at the third copy) and re-run the tests after each step.
3. **Dante does not return** for a hardening pass. He returns only in the fix passes after the reviewers, to write the test House's diagnosis calls for, and in the case under "A test is wrong".

## Code beyond the tests

Something real that no test foresaw (for example a library limit) may need code the tests do not ask for. Ultron adds it only as a declared exception, in its own report section («Beyond the tests») with three facts: what he added, why, and which behavior has no test yet. His status is then DONE_WITH_CONCERNS. Dante writes those tests in the fix pass. Never add it silently.

## A test is wrong

When Ultron reports one of Dante's tests as wrong, he stops and does not edit it. Send a fresh Dante at once to correct that test, before the reviewers: nothing can go green around a wrong test.

## Short in test-first

Dante writes the change's tests before Ultron, scaled to the change; for a bug, the failing repro test comes first. Ultron makes them pass. There is no mutation check; Dante's report says `Not run — Short.` in its Mutants section.

## What to test

Choose by tier (`standards.md` §1, §9):
- Persistence and integrity code: write, then read back across the real seam; atomic writes; no concurrent-write race (§3, §6, §34).
- Silent-failure paths: no swallowed catch, no masked exit code, a fail-open logs why it fell back (§4).
- Behavior and API code: happy path, invalid input, not-found, error paths, the permissions the project defines.
- Skip: getters without logic, library internals, exhaustive parameter combinations.

Test behavior through public interfaces. A test that breaks on a rename tested the wrong thing.

## Where decisions go

Acceptance criteria and behavior decisions that emerge are saved as decisions, with their why, through `unmassk-memory`. Never write them to a `.md` file.
