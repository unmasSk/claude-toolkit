# Prompt Template — Bilbo (Audit Scan, Step 1)

> Template for the orchestrator. Fill in the fields in brackets.

```markdown
## Task: Deep scan of module [MODULE] for enterprise audit

TASK: map module `[MODULE_PATH]` (issue #[N]) for the audit:
1. List ALL source files in the module, subfolders included.
2. Count LOC per file.
3. List existing tests (detect the test directory convention: `__tests__/`, `tests/`, `*_test.*`, `*.test.*`).
4. Map imports/exports and inter-module dependencies.
5. Run the existing tests: `[TEST_CMD]` scoped to `[MODULE_PATH]`.
6. Flag files over 300 LOC (or the project profile's limit), missing tests, visible anti-patterns and broken tests.
KNOWN: [anything already known about the module, or "nothing"]
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: read-only on the project; write only your memory and your report file. No commits; no git stash/reset/checkout/restore.
VERIFY: quote the test run output. Tag claims EXECUTED/READ/UNVERIFIED.

Under `Confirmed findings`, put this summary table:

| File | LOC | Existing tests | Imports from | Consumed by | Visible problems |
|------|-----|----------------|--------------|-------------|------------------|

Also under `Confirmed findings`:
- Failing tests, with their error output. Classify each: broken test, or source blocker.
- Files needing a split (over 300 LOC, or the profile's limit).
- Inter-module dependencies (which other modules this one touches).
- Risk assessment for the audit.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
