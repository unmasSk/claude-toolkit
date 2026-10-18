# Prompt Templates — House (Diagnostic, Step 5 circuit breaker)

> Templates for the orchestrator. Fill in the fields in brackets.

---

## Template 1: New Investigation

```markdown
## Task: Diagnose [ISSUE_SUMMARY]

TASK: find the root cause of [ISSUE_SUMMARY] in `[MODULE_PATH]` (issue #[N], if applicable). Diagnose only — never fix.
KNOWN:
- [From the step 5 circuit breaker: "This is a stuck fix, not a failure in delivered behaviour."]
- Expected: [what should happen]
- Actual: [what actually happens]
- Errors: [error messages, stack traces — verbatim]
- Reproduction: [exact steps to trigger]
- Timeline: [when it started, what changed recently]
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: keep your Working log in the session scratchpad, never in the project (your card, «Working log»). Remove every marker you add. No commits; no git stash/reset/checkout/restore.
VERIFY: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run TWICE. Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```

---

## Template 2: Continue Investigation (after context reset)

```markdown
## Task: Continue diagnosing [SLUG]

TASK: resume the diagnosis of [SLUG] in `[MODULE_PATH]` from where it stopped. Diagnose only — never fix.
KNOWN:
- Previous House report: [PREVIOUS_HOUSE_REPORT_PATH] — symptoms, evidence collected, eliminated hypotheses, where it stopped.
- Your Working log from that run, if this session still has it: [WORKING_LOG_PATH or "gone"].
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: keep your Working log in the session scratchpad, never in the project (your card, «Working log»). Remove every marker you add. No commits; no git stash/reset/checkout/restore.
VERIFY: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run TWICE. Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```

---

## Template 3: Re-diagnose (after Ultron's fix failed)

```markdown
## Task: Re-diagnose [ISSUE_SUMMARY] — Ultron's fix did not resolve it

TASK: find why the fix for [ISSUE_SUMMARY] in `[MODULE_PATH]` did not work, and the real root cause. Diagnose only — never fix.
KNOWN:
- [From the step 5 circuit breaker: "This is a stuck fix, not a failure in delivered behaviour."]
- Previous House report: [PREVIOUS_HOUSE_REPORT_PATH] — read `Root cause`.
- Ultron's report on the fix: [ULTRON_REPORT_PATH].
- Result: [still failing / new error / partial fix]
- Expected after the fix: [what it should have achieved]
- Actual after the fix: [what happened]
- Errors: [new or persisting error messages — verbatim]
CROSS-CHECK: this KNOWN block is a starting point, not a substitute. If the task touches anything present in your memory index or in the project's memory, verify it in pairs before acting: your own memory, the real code, and `gitmem search` — even if KNOWN already tells you the answer.
LIMITS: continue your Working log in the session scratchpad if this session still has it; otherwise start a new one from the previous report. Never in the project (your card, «Working log»). Remove every marker you add. No commits; no git stash/reset/checkout/restore.
VERIFY: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run TWICE. Tag claims EXECUTED/READ/UNVERIFIED.

Write your report file. Answer in three lines: status, what to act on, report path.

Do the task yourself or report back — never spawn agents of your own. Never end your turn waiting on background work — read the result and deliver the report. If the task grows past its point, finish the coherent part, report, and wait.
```
