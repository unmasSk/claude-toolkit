# Prompt Templates — Cerberus (Audit)

> Templates for the orchestrator. Fill in the fields in brackets.

---

## Template 1: Enterprise Audit (Step 4)

> Scope: COMPLETE module, not diff. Cerberus normally works with diff —
> this prompt changes its scope to a full module read.

```markdown
## Task: Enterprise audit of module [MODULE]

ARTIFACT: these files of `[MODULE_PATH]`, read complete (not a diff) — only those assigned to this agent: [EXACT LIST, with LOC]. Issue #[N].
CONTRACT: the enterprise standards in `unmassk-standards` (`references/standards.md`) and the project profile — tiers T1/T2/T3 and the weighted score /110 as defined there (Integrity ×3, Silent-failure ×3, Structure ×2, Real verification ×2, Maintainability ×1). Score only against criteria in `standards.md`.
SCOPE: only the files listed above. Report only — never fix.
ASK: review and audit the whole artifact — every file, function and module in scope — and return, for each one, "reviewed" and what you checked. Finding nothing is a valid answer; a report without that coverage list is not.

Before counting something as a gap (a missing guard, a missing check), verify whether it is already handled upstream — a shared wrapper, a caller-level guard, a config default. If the module correctly relies on an upstream safeguard, it is valid context, not a gap.

Verification: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice.
```
