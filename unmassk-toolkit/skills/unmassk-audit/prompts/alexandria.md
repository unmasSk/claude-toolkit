# Prompt Template — Alexandria (Audit, Step 12)

> Template for the orchestrator. Fill in the fields in brackets.

```markdown
## Task: Post-audit documentation for module [MODULE]

TASK: document what the audit of `[MODULE_PATH]` changed (issue #[N], branch `chore/audit-[MODULE]`):
1. Read every WIP commit of the audit, whole: `[FIRST_WIP]..[LAST_WIP]`. Cite the range read.
2. Create or update the module's CLAUDE.md with the patterns learned.
3. Update CHANGELOG.md under [Unreleased] with meaningful entries.
4. Cross-check the documentation against the current code.
KNOWN:
- Final verdict: Yoda [XX/110] — [APPROVED / APPROVED WITH CONDITIONS / REJECTED / CANNOT JUDGE], then the step 11 fixes.
- Tests: [N] passing. Coverage: [X]%.
- Files created, renamed or deleted during the audit: [LIST]
- Step reports, for what each step changed: [REPORT PATHS — steps 2, 3, 5, 7, 9, 11]
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: touch only the module's CLAUDE.md, CHANGELOG.md and your memory. Never edit code or tests. No commits; no git stash/reset/checkout/restore.
VERIFY: every documented claim matches the code you read. Tag claims EXECUTED/READ/UNVERIFIED. List every file you changed under `Files changed`, and the memory file you touched.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
