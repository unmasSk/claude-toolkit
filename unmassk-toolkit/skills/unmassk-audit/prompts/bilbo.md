# Prompt Template — Bilbo (Audit Scan)

> Template for the orchestrator.

```markdown
## Task: Deep scan of module [MODULE] for enterprise audit

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]

### Exploration scope

1. List ALL source files in the module (including subfolders)
2. Count LOC per file
3. List existing tests (detect the test directory convention: `__tests__/`, `tests/`, `*_test.*`, `*.test.*`)
4. Map imports/exports and inter-module dependencies
5. Run existing tests: `[TEST_CMD]` scoped to `[MODULE_PATH]` (resolve from the project profile — see SKILL.md "Prompt Templates")
6. Flag: files over 300 LOC (or the project profile's limit), missing tests, visible anti-patterns, broken tests

### Output expected

Summary table:

| File | LOC | Existing tests | Imports from | Consumed by | Visible problems |
|------|-----|----------------|-------------|-------------|------------------|

Plus:
- Broken tests (if any) with error output
- Files needing split (over 300 LOC, or the profile's limit)
- Inter-module dependencies (what other modules does this one touch)
- Risk assessment for the audit
```
