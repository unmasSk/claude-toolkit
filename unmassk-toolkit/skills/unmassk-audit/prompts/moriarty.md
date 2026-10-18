# Prompt Template — Moriarty (Audit)

> Template for the orchestrator. Short prompt: name the target and the win condition, never a list of vectors or of what was fixed.

```markdown
## Task: Adversarial validation of module [MODULE] post-fixes

Target: `[MODULE_PATH]` (source and tests), issue #[N]. Base for the regression diff: `[BASE_COMMIT]`.
Win condition: break it — the code or the tests — and prove it with a reproduction. Return your raw run log (commands and output) with your verdict.

Verification: `[TEST_CMD]` scoped to `[MODULE_PATH]`, run twice.
```
