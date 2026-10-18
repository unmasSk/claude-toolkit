# Prompt Template — Cerberus (Audit, Step 4)

> Template for the orchestrator. Fill in the fields in brackets. Blind review: give the artifact and the contract, never your conclusion or what to look for (`unmassk-core`, «Review prompts are blind»).
> Scope: the COMPLETE module, not a diff. `MODE: audit` switches Cerberus from the diff to a full module read.

```markdown
## Task: Enterprise audit of module [MODULE]

MODE: audit
ARTIFACT: these files of `[MODULE_PATH]`, read complete (not a diff) — only those assigned to this agent: [EXACT LIST, with LOC]. Issue #[N].
CONTRACT: the enterprise standards in `unmassk-standards` (`references/standards.md`) and the project profile — tiers T1/T2/T3 and the weighted score /110 as defined there. Score only against criteria in `standards.md`.
SCOPE: only the files listed above. Report only — never fix.
ASK: review and audit the whole artifact — every file, function and module in scope — and return, for each one, "reviewed" and what you checked. Finding nothing is a valid answer; a report without that coverage list is not.

Before counting something as a gap (a missing guard, a missing check), verify whether it is already handled upstream — a shared wrapper, a caller-level guard, a config default. A module that correctly relies on an upstream safeguard has no gap there.

Verification: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
