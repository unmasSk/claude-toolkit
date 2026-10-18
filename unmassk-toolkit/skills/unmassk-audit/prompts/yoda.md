# Prompt Template — Yoda (Audit, Step 10)

> Template for the orchestrator. Fill in the fields in brackets. Blind: no narrative of what was found or fixed, no conclusion. Pass the PATH of Moriarty's raw-log file, never its content pasted, never his report or verdict word. Without the raw log, Yoda answers CANNOT JUDGE.

```markdown
## Task: Final senior evaluation of module [MODULE]

ARTIFACT: the source of `[MODULE_PATH]`, its tests and the coverage result ([% lines, % branches]); Moriarty's raw run log: [RAWLOG_PATH] (`moriarty-<…>-rawlog.md`); reference: issue #[N].
CONTRACT: `unmassk-standards` (tiers T1/T2/T3, weighted score /110). 110 is perfection: for any lower score, say what to fix to reach 110 and, if it cannot be reached, why. Verdict vocabulary: APPROVED / APPROVED WITH CONDITIONS / REJECTED / CANNOT JUDGE.
SCOPE: the module only. Optional reference: a previously approved module `[REFERENCE_MODULE_PATH]` ([XX/110]).
ASK: review and audit the whole artifact — every file, function and module in scope — and return, for each one, "reviewed" and what you checked. Finding nothing is a valid answer; a report without that coverage list is not.

Verification: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
