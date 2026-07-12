# TypeScript Strict Config & Type Safety

> Executable reference for AI agents. Binary rules (IF/THEN).
> Quality test: if two AIs read the same rule, they reach the same action.
> Language skill — applies to ANY TypeScript code, backend or frontend. Domain skill, NOT loaded on boot; the orchestrator injects it into the agent's prompt when the task is TypeScript work.

## Relationship to the core (unmassk-standards)

Extends the core; never redefines its machinery. Tiers, waivers, tie-breaker, and scoring are the core's. These rules exist under the same threat model — the system against itself: loose typing is how a value lies about what it is until it crashes at runtime or, worse, silently mis-handles data. `strictNullChecks` off is a T1 for exactly that reason.

The core already mandates a justification comment on every force/unchecked cast (core §2). This skill supplies the TypeScript-specific mechanics of that rule and its siblings.

Findings absorb into the core dimensions: type-safety violations that can crash or corrupt at runtime → Integrity / Silent-failure; config and cast hygiene → Structure / Maintainability.

---

## 1. Mandatory tsconfig Rules

| Option | Value | Tier if wrong |
|--------|-------|---------------|
| `strict` | `true` | T2 |
| `noImplicitAny` | `true` (implied by strict) | T2 |
| `strictNullChecks` | `true` (implied by strict) | T1 (causes runtime crashes) |
| `noUncheckedIndexedAccess` | `true` | T2 |
| `noImplicitReturns` | `true` | T2 |
| `noFallthroughCasesInSwitch` | `true` | T2 |
| `forceConsistentCasingInFileNames` | `true` | T3 |
| `exactOptionalPropertyTypes` | `true` | T3 |

IF `strict: false` in tsconfig THEN finding T2. No exceptions.

IF the project profile declares a stricter or additional compiler option THEN enforce the profile's value (core pointer rule — a profile may tighten, never downgrade).

---

## 2. Type Safety Rules

| Rule | Tier |
|------|------|
| `any` forbidden without justification comment explaining why | T2 |
| `unknown` preferred over `any` for values of uncertain type | T2 |
| Type assertions (`as Type`) must have type guard or validation before | T2 |
| Non-null assertion (`!`) must have justification comment | T2 |
| `// @ts-ignore` must have reason comment. Prefer `// @ts-expect-error` with description. | T2 |
| NEVER `as any` to silence errors — fix the type | T2 |
| API response types must match the producer's contract (shared types or code generation — hand-typing what "the backend returns" is core §34.2 territory) | T2 |

Exceptions (no comment needed): `as const` (compile-time only), `as unknown as Type` in test mocks (test infrastructure) — same as core §2.

---

## 3. Pattern Rules

```
IF value can be null/undefined THEN use narrowing (if check), not assertion (!)
IF function returns different shapes THEN use discriminated union with literal type field
IF object has optional properties THEN use Partial<T> or explicit optionals, not `| undefined` on every field
IF casting is needed THEN use a type guard function (returns `x is Type`), not bare `as`
IF generic has no constraint THEN add `extends` to constrain it
```

---

## 4. Discriminated Unions (mandatory pattern for variant types)

```typescript
// CORRECT: discriminated union
type Result =
  | { status: 'ok'; data: User }
  | { status: 'error'; message: string };

// INCORRECT: optional fields guessing game
type Result = {
  status: string;
  data?: User;
  message?: string;
};
```

IF a type represents 2+ variants THEN use a discriminated union (T2).

Why it is the internal-failure pattern: the incorrect form lets `{ status: 'ok' }` exist with no `data` — a shape that lies. The discriminated union makes the illegal state unrepresentable, which is cheaper than any runtime check.
