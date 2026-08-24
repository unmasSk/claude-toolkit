# Prompt Template — Argus (Audit Integrity)

> Template for the orchestrator.

```markdown
## Task: Deep integrity audit of module [MODULE]

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]
- Runs in parallel with Cerberus (step 4)

### Scope

All source files in `[MODULE_PATH]` (source code, not tests).

### Focus areas

No external attacker in this project's threat model — the target is the system breaking itself. Go deeper than Cerberus's surface pass on:

1. Memory/persistence integrity (`standards.md` §3): atomic writes, index↔target consistency, round-trip verified (Pilar 1 / §34)
2. Silent-failure surfaces (§4): swallowed errors, masked exit codes, fail-open without a log line, a status derived from an unsafe proxy
3. Concurrency / shared-state races (§6): re-run duplicating or corrupting state, global mutation on shared state
4. Platform robustness (§5): path/encoding/env-var/timeout portability across Windows/Linux/macOS
5. Data flow traceability (where critical data enters, is transformed, and is persisted — tracing for corruption/loss risk, not exfiltration)
6. Environment guard patterns — allowlist vs denylist (§4: a denylist silently enables the wrong behavior in an env it forgot)

### Rules
- Limit scope to the deeper integrity surfaces listed above; leave Cerberus's checklist to Cerberus
- Audit patterns only; active attacks belong to Moriarty (step 8)
- Classify every finding by tier (T1/T2/T3)
- ONLY report — never fix

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
```
