# Prompt Template — Yoda (Audit)

> Template for the orchestrator. Blind: no narrative of what was found or fixed, no conclusion. Moriarty's raw run log goes in the artifact — never his summary or verdict word; without it Yoda answers CANNOT JUDGE.

```markdown
## Task: Final senior evaluation of module [MODULE]

ARTIFACT: the source of `[MODULE_PATH]`, its tests and the coverage result ([PASTE % lines, % branches]); Moriarty's raw run log ([PASTE the commands he ran and their output, unedited]); reference: issue #[N].
CONTRACT: `unmassk-standards` (tiers T1/T2/T3, weighted score /110). 110 is perfection: for any lower score, say what to fix to reach 110 and, if it cannot be reached, why. Verdict vocabulary: APPROVED / APPROVED WITH CONDITIONS / REJECTED / CANNOT JUDGE.
SCOPE: the module only. Optional reference: a previously approved module `[REFERENCE_MODULE_PATH]` ([XX/110]).
ASK: review and audit the whole artifact — every file, function and module in scope — and return, for each one, "reviewed" and what you checked. Finding nothing is a valid answer; a report without that coverage list is not.

Verification: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice.
```
