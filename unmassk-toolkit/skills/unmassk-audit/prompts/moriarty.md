# Prompt Template — Moriarty (Audit)

> Template for the orchestrator.

```markdown
## Task: Adversarial validation of module [MODULE] post-fixes

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]

### Module files

[LIST of all source files in the module — source code + tests]

### Previous audit findings

[PASTE SUMMARY of findings that were fixed — so REGRESSION has context]

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
```
