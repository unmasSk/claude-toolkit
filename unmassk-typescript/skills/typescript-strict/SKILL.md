---
name: typescript-strict
description: Use EVERY TIME TypeScript code or a tsconfig is written, reviewed, audited, or fixed — strict mode, noImplicitAny, strictNullChecks, noUncheckedIndexedAccess, type safety, any vs unknown, type assertions (as), non-null assertions (!), @ts-ignore / @ts-expect-error, type guards, generics, discriminated unions. Language skill: applies to ANY TypeScript project, backend or frontend alike. Extends unmassk-standards (core), which governs tiers, scoring, and waivers; this skill adds the TypeScript-specific rows, including the TS mechanics of the core's cast-justification rule.
---

# typescript-strict

TypeScript strict configuration and type-safety standards, for any TS code — backend or frontend. Extends `unmassk-standards` (core): core tier semantics, core scoring, core waiver rules. `strictNullChecks: false` is a T1 (runtime crashes — the system against itself).

## Router

The full standards are in `references/typescript-strict.md`. Load the section the task needs:

| If the task involves | Read |
|----------------------|------|
| tsconfig options, compiler flags, strict mode | §1 Mandatory tsconfig Rules |
| `any`, `unknown`, `as`, `!`, `@ts-ignore`, API response types | §2 Type Safety Rules |
| Narrowing, optionals, type guards, generic constraints | §3 Pattern Rules |
| Variant/result types, unrepresentable illegal states | §4 Discriminated Unions |

## Project profile

The typecheck/build command is a profile value (core §10 — never hardcode `tsc`). A profile may add or tighten compiler options; it may never downgrade a tier (core tailoring boundary).
