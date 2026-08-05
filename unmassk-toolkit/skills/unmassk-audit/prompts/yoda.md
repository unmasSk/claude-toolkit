# Prompt Template — Yoda (Audit)

> Template for the orchestrator.

```markdown
## Task: Final senior evaluation of module [MODULE]

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]
- Full enterprise audit complete (steps 1-10 executed)

### Input from other agents

**Audit findings (Cerberus):**
[PASTE original findings + which ones were closed]

**Adversarial report:**
[PASTE summary — phases executed, breaks, verdict]

**Test coverage:**
[PASTE coverage result — % lines, % branches]

### Reference module (optional)
- Previously approved module: `[REFERENCE_MODULE_PATH]`
- Previous score: [XX/110]

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
```
