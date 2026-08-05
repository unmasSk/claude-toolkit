# Prompt Templates — Dante (Audit)

> Templates for the orchestrator. Fill in the fields in brackets.

---

## Template 1: Golden Tests

```markdown
## Task: Golden tests for [FILE] — 97%+ coverage

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]
- Source file: `[MODULE_PATH]/[FILE]`
- Existing tests: [TEST_FILE or "none"]

### Exports to cover

[LIST of public exports from the file — extracted from the step 1 scan]

- `exportA()`
- `exportB()`

### Integrations

[Which other modules/files this one integrates with — extracted from the step 1 scan]

- Imports from: `[module1]`, `[module2]`
- Consumed by: `[module3]`

### Enterprise test reference

Tests approved by Yoda — use as style and structure model:
- `[REFERENCE_MODULE_PATH]/[reference_test]` (test directory per project convention)

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]/[TEST_FILE]`, with coverage
2. If < 97%: identify uncovered branches
3. `[TEST_CMD]` scoped to `[MODULE_PATH]`
4. Run TWICE
```

---

## Template 2: Adversarial Tests

```markdown
## Task: Adversarial tests for [MODULE] based on adversarial validation report

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]

### Adversarial report

[PASTE SUMMARY of the report — confirmed breaks and attacks that held]

| Phase | Attack | Result | File:line |
|-------|--------|--------|-----------|
| BREAK | ... | BROKEN | ... |
| ABUSE | ... | HELD | ... |

### Output file
- `[MODULE_PATH]/[test dir]/[MODULE].adversarial.test` (extension and test-dir convention per project)

### Verification
1. `[TEST_CMD]` scoped to the new adversarial test file
2. `[TEST_CMD]` scoped to `[MODULE_PATH]`
3. Run TWICE
```
