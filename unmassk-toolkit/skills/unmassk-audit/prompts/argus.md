# Prompt Template — Argus (Audit Integrity)

> Template for the orchestrator. Blind review: give the artifact and the contract, never your conclusion or what to look for (`unmassk-core`, «Review prompts are blind»).

```markdown
## Task: Integrity audit of module [MODULE]

ARTIFACT: all source files in `[MODULE_PATH]` (source code and its tests) — issue #[N]. Runs in parallel with Cerberus (step 4).
CONTRACT: the project's declared threat model (its CLAUDE.md / memory) and `unmassk-standards` (`references/standards.md`): persistence integrity §3 and round-trip §34, fail-loud §4, platform robustness §5, concurrency §6. Classify by tier (T1/T2/T3).
SCOPE: patterns only — active attacks belong to Moriarty (step 8); Cerberus's general review checklist is his. Report only — never fix.
ASK: review and audit the whole artifact — every file, function and module in scope — and return, for each one, "reviewed" and what you checked. Finding nothing is a valid answer; a report without that coverage list is not.

Verification: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice.
```
