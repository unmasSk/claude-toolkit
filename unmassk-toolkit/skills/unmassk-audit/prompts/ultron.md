# Prompt Template — Ultron (Audit Fix, Steps 2, 5, 9, 11)

> Template for the orchestrator. Fill in the fields in brackets.

```markdown
## Task: Fix findings in module [MODULE]

Build order: audit-fix. The findings below are the contract. The golden tests stay green.

TASK: fix every finding listed in KNOWN, at its root cause, in module `[MODULE_PATH]` (issue #[N], branch `chore/audit-[MODULE]`). Order: T1, then T2, then T3.
KNOWN:
- Findings to fix (the step's findings table, or the report path and section that holds it: [REPORT_PATH] § [SECTION]):

| ID | Tier | File:line | Description | Recommended fix |
|----|------|-----------|-------------|-----------------|
| F1 | T1   | <file>:45 | ...         | ...             |

- 10/10 reference, enterprise code approved by Yoda — use as model: `[REFERENCE_MODULE_PATH]/[reference_file]`
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: touch only these files: [EXACT LIST, e.g. `[MODULE_PATH]/[file1]`, `[MODULE_PATH]/[file2]`]. No tests: Dante writes them. No commits; no git stash/reset/checkout/restore; nothing outside your files.
VERIFY:
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`, run TWICE.
2. `[FORMAT_CMD]` scoped to `[MODULE_PATH]`.
3. `[LINT_CMD]` scoped to `[MODULE_PATH]`.
Quote the real output in the report. Tag claims EXECUTED/READ/UNVERIFIED.

In the report, per fixed finding: finding ID, root cause, fix applied, modified files with LOC before/after.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
