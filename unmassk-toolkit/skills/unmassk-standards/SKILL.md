---
name: unmassk-standards
version: 1.1.0
description: >
  Use EVERY TIME code is written, reviewed, tested, audited, or fixed. Generic,
  stack-agnostic quality criteria under the "system against itself" threat model —
  the failures a project inflicts on itself: data/memory loss or corruption, silent
  failures, platform (Windows/Linux/macOS) breakage, producer→consumer round-trip
  integrity, and concurrency races. Provides tier classification (T1/T2/T3), weighted
  scoring (/110), size/structure decision trees, and error-handling/async rules.
  Loaded by ALL agents on boot. NOT about external attackers — no OWASP/injection
  defense here. Project-specific values (stack, response contract, DB schema, build
  command, coverage number) live in the project profile, never hardcoded in this
  skill. If you are touching code, you need these standards.
---

# Enterprise Quality Standards — Generic

Stack-agnostic quality standards for software auditing and review, calibrated to one threat model: **the system against itself.** These standards define the tiers, weighted scoring, and checklists that agents use to evaluate whether code corrupts, loses, or silently mis-handles its own data and state — on any language, any project.

There is **no external adversary** in this model. Rules about injection, exploitation, or hostile input do not live here; a project that needs them declares them in its own profile.

## How agents use this

Every crew agent loads this skill on boot (via `skills: unmassk-standards` in frontmatter). Each loader uses it differently:

- **Cerberus** — classify findings by tier; score the weighted dimensions in audit mode.
- **Argus** — apply the integrity checklist (memory/persistence integrity, silent failure, platform, round-trip). Argus carries its own external-threat material in its own prompt; this skill is the internal-failure model.
- **Yoda** — scoring dimensions and weighted evaluation; the round-trip (§34) evidence gate.
- **Ultron** — prioritize fixes by tier; read project-specific limits/commands from the project profile, not from here.
- **Dante** — round-trip / anti-fabricated-fixture rules (§34); test-quality rules (no tautological/order-dependent assertion, no mock replicating production). Dante's own prompt owns test-type selection and the exhaustive coverage gate; security-by-module cases enter via Argus→regression.
- **Moriarty** — which surfaces are T1: memory corruption, silent failure, concurrency race, round-trip sabotage.
- **Bilbo** — flag anti-patterns during exploration.
- **House** — classify failure severity (data/memory integrity and silent failure lead).
- **Alexandria** — document the real producer↔consumer contract discovered (§34).

## Reference

The complete standards are in `references/standards.md`. Load it when you need:

- Threat-model framing ("the system against itself")
- Pilar 1 — Producer↔Consumer round-trip integrity (canonical `§34`)
- Tier system (T1/T2/T3) and what blocks merge
- Generic finding classification + execution priority (integrity-first)
- Design principles + size/structure decision trees
- Memory/persistence integrity, silent-failure/fail-loud, platform robustness, internal idempotency & concurrency
- Async & error-handling rules
- Anti-pattern catalog
- Weighted scoring (/110) with the closed per-dimension checklists, per-item evidence, and the **score≠gate** rule (a T1 blocks merge even at 110/110)
- The project-profile pointer rule + **tailoring boundary** (a profile may tighten, never downgrade a T1)
- T2 **waiver** mechanics, the rule **tie-breaker**, and the determinism probe in the acceptance gate

## Sections covered

- **Pilar 1** — Producer↔Consumer round-trip integrity (`§34`, `§34.1`–`§34.4`)
- **§1** — Tier system + generic finding classification + execution priority
- **§2** — Design principles (SOLID/DRY/KISS/YAGNI) + size-limit & extraction decision trees + dead-code/cast policy
- **§3** — Memory / persistence integrity
- **§4** — Silent failure / fail-loud
- **§5** — Platform robustness (Windows / Linux / macOS)
- **§6** — Internal idempotency & concurrency (race / compare-and-set)
- **§7** — Async & error handling
- **§8** — Anti-pattern catalog (generic, pseudocode)
- **§9** — Weighted scoring (/110) + closed per-dimension checklists + anti-void rule
- **§10** — Project profile & pointer rule
- **§11** — Comments, naming & dependencies

## Where project-specific values live

This skill NEVER hardcodes a stack. Project-specific values live in two homes and are referenced by name:

- **Agent memory** (`.claude/agent-memory/<agent>/MEMORY.md`) — size limits, coverage threshold, build/test command, past mistakes on this codebase.
- **Project profile** (in `CLAUDE.md` / git-memory) — response/data contract, soft-delete convention, schema, roles, stack conventions.

IF a check depends on a profile value that is missing THEN fail loud (warn), never resolve the check to a silent no-op.
