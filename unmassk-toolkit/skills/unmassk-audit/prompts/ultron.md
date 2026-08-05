# Prompt Template — Ultron (Audit Fix)

> Template for the orchestrator. Fill in the fields in brackets.

```
## Task: Fix findings in module [MODULE]

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]
- Branch: `chore/audit-[MODULE]-[N]`

### Findings to fix

[PASTE FINDINGS TABLE — ordered T1 first, T2 second, T3 last]

| ID | Tier | File:line | Description | Recommended fix |
|----|------|-----------|-------------|-----------------|
| F1 | T1   | <file>:45  | ...        | ...             |

### Files in scope

[EXACT LIST of files this agent may touch]

- `[MODULE_PATH]/[file1]`
- `[MODULE_PATH]/[file2]`

### 10/10 reference

Enterprise code approved by Yoda — use as model:
- `[REFERENCE_MODULE_PATH]/[reference_file]`

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
3. `[FORMAT_CMD]` scoped to `[MODULE_PATH]`
4. `[LINT_CMD]` scoped to `[MODULE_PATH]`

### Expected output
For each fixed finding:
- Finding ID
- Root cause
- Fix applied
- Modified files with LOC before/after

Verification results (paste real output, do not summarize).
```
