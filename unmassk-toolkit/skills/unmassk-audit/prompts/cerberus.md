# Prompt Templates — Cerberus (Audit)

> Templates for the orchestrator. Fill in the fields in brackets.

---

## Template 1: Enterprise Audit (Step 4)

> Scope: COMPLETE module, not diff. Cerberus normally works with diff —
> this prompt changes its scope to a full module read.

```markdown
## Task: Audit module [MODULE] against enterprise standards

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]
- Scope: COMPLETE module read (not diff)

### Files to audit

[EXACT LIST — only those assigned to this agent]

- `[MODULE_PATH]/[file1]` ([LOC] LOC)
- `[MODULE_PATH]/[file2]` ([LOC] LOC)

### Problems already detected in scan

[PASTE scan observations from step 1 relevant to these files]

### Standards reference

Evaluate against `unmassk-standards` (`references/standards.md`):
- Integrity (data + memory): §3 (persistence integrity), Pilar 1 / §34 (round-trip), §6 (concurrency)
- Silent-failure / Error handling: §4 (fail-loud), §7 (async & error handling)
- Structure: §2 (size limits, SOLID, decision trees), §5 (platform robustness — scored as a Structure checklist item, not its own dimension)
- Real verification: §9 closed checklist (real seam, no tautological assertion, no fabricated fixture)
- Maintainability: §11 (naming, dead code, comments)

### Weighted score

| Dimension | Weight |
|-----------|--------|
| Integrity (data + memory) | x3 |
| Silent-failure / Error handling | x3 |
| Structure | x2 |
| Real verification | x2 |
| Maintainability | x1 |
| **Total** | **/110** |

Do NOT invent criteria outside `standards.md`.
Do NOT fix anything — report only.

### Critical rule: verify upstream context before reporting a finding

Before reporting a finding, especially one that looks like a missing guard or a missing check:
1. Verify whether the behavior is already handled upstream — a shared wrapper, a caller-level guard, a config default — elsewhere in the codebase.
2. If the safeguard already exists upstream and the module correctly relies on it, do NOT report it as a module-level finding — it is valid external context, not a gap.
```

---

## Template 2: Re-Audit (Step 10)

> Scope: COMPLETE module post-fixes. Compare score before/after.

```markdown
## Task: Re-audit module [MODULE] post-fixes

### Context
- Module: `[MODULE_PATH]`
- Issue: #[N]
- Scope: COMPLETE module read (not diff)

### Previous findings

[PASTE FINDINGS TABLE from step 4 — to verify which ones were closed]

| ID | Tier | Description | Expected status |
|----|------|-------------|-----------------|
| F1 | T1   | ...         | Closed          |

### Previous score: [XX/110]

### Verification
1. `[TEST_CMD]` scoped to `[MODULE_PATH]`
2. Run TWICE
3. `[FORMAT_CMD]` scoped to `[MODULE_PATH]`
4. `[LINT_CMD]` scoped to `[MODULE_PATH]`

### Critical rule: verify upstream context before reporting a finding

Before reporting a finding, especially one that looks like a missing guard or a missing check:
1. Verify whether the behavior is already handled upstream — a shared wrapper, a caller-level guard, a config default — elsewhere in the codebase.
2. If the safeguard already exists upstream and the module correctly relies on it, do NOT report it as a module-level finding — it is valid external context, not a gap.

### Expected output
- Closed findings: X/Y
- New findings (if any, with tier)
- Score: before ([XX]/110) → after ([YY]/110)
- Prose evaluation per dimension (2-3 sentences each)
```
