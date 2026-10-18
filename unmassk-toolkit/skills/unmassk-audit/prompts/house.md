# Prompt Templates — House (Diagnostic)

> Templates for the orchestrator.

---

## Template 1: New Investigation

```markdown
## Task: Diagnose [ISSUE_SUMMARY]

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N] (if applicable)

### Symptoms

- Expected: [what should happen]
- Actual: [what actually happens]
- Errors: [error messages, stack traces — paste verbatim]
- Reproduction: [exact steps to trigger]
- Timeline: [when it started, what changed recently]

### Debug session file
Keep it in your session scratchpad, never as a file committed into the project (your card, «Persistent Session File»).

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
```

---

## Template 2: Continue Investigation (after context reset)

```markdown
## Task: Continue diagnosing [SLUG]

### Prior state
Debug session file: your scratchpad log from the previous House run, if this session still has it; otherwise the previous House report, pasted here by the orchestrator: [PREVIOUS HOUSE REPORT].

Read it. It contains: current focus, symptoms, eliminated hypotheses, and evidence collected so far. Resume from `next_action`.

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
```

---

## Template 3: Re-diagnose (after Ultron fix failed)

```markdown
## Task: Re-diagnose [ISSUE_SUMMARY] — previous fix by Ultron did not resolve the issue

### Context
- Module: `[MODULE_PATH]`
- Previous diagnosis: [PASTE ROOT CAUSE from previous House report]
- Fix applied: [PASTE what Ultron changed]
- Result: [still failing / new error / partial fix]

### New symptoms after fix

- Expected: [what the fix should have achieved]
- Actual: [what actually happened after the fix]
- Errors: [new or persisting error messages]

### Debug session file
Continue your scratchpad log (append to existing evidence), never a file in the project.

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
```
