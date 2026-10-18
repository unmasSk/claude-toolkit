# Prompt Template — Moriarty (Audit, Step 8)

> Template for the orchestrator. Short prompt: name the target and the win condition. Never list vectors or what was fixed.

```markdown
## Task: Adversarial validation of module [MODULE] post-fixes

TASK: break `[MODULE_PATH]` — the code or the tests — and prove each break with a reproduction. Issue #[N].
KNOWN:
- Base for the regression diff: `[BASE_COMMIT]`.
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: never edit the project's code, tests or config; sabotage and mutate copies in the session scratchpad. No commits; no git stash/reset/checkout/restore.
VERIFY: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice. Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Write the raw run log (commands and output) in its own file, `moriarty-<…>-rawlog.md`, never inside the report. Answer in three lines: status, what to act on, both paths.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
