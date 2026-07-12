# Frontend Standards — React (components, state, testing, styling, structure)

> Executable reference for AI agents. Binary rules (IF/THEN).
> Quality test: if two AIs read the same rule, they reach the same action.
> Domain skill — NOT loaded on boot. Discovered via skill-search when the task smells of frontend.

## Relationship to the core (unmassk-standards)

This document **extends** the core with frontend-specific rows. It never redefines core machinery:

- **Tiers, waivers, tie-breaker, pointer rule, scoring /110** — all governed by the core. A frontend finding is classified with core tier semantics and blocked/waived by core rules.
- **Threat model boundary** — same as core: internal failure only. No attacker-model rules here (XSS, CSRF, clickjacking, CSP → Argus's material / project profile). If a rule below looks security-adjacent (e.g. "error state shown to user"), it is here because silent failure is the internal threat, not because of an attacker.
- **Project profile** holds the *choices*: styling approach, breakpoints/design tokens, state/data-fetching library, framework routing convention, monitoring destination. This document holds the *rules that apply once a choice is made*. IF a rule below depends on a profile value that is missing THEN fail loud (core §10), never silently skip the check.

### Scoring absorption (no new dimensions)

Frontend findings feed the core's /110 through the existing dimensions — this skill adds checklist rows, never weight-units:

| Frontend rule family | Core dimension |
|----------------------|----------------|
| Direct state mutation, race between concurrent fetches, optimistic update without rollback | Integrity (×3) |
| Silent error/loading states, swallowed fetch errors, AbortError mishandling | Silent-failure (×3) |
| Component size/split, styling discipline, file structure, import direction | Structure (×2) |
| Component/hook tests, real-seam verification (§34 core) | Real verification (×2) |
| Naming, dead components, magic values in styles | Maintainability (×1) |

---

## 1. Component Patterns

### Component types

| Type | Max LOC | What it does |
|------|---------|-------------|
| Page component | 200 | Layout + composition of smaller components. No business logic. |
| Feature component | 300 | Business logic + state. Contains hooks, handlers. |
| UI component | 100 | Pure presentational. Props in, JSX out. Zero side effects. |
| Layout component | 100 | Grid, spacing, wrappers. Children only. |

```
IF component > 300 LOC THEN mandatory split (T2)
IF component has business logic AND presentation mixed THEN split into container + presentational (T2)
IF component has 5+ useState THEN extract to custom hook (T2)
IF component has 3+ useEffect THEN refactor — too many side effects (T2)
```

### Rules

| Rule | Tier |
|------|------|
| Functional components only. NEVER class components. | T2 |
| Props destructured in signature | T3 |
| Default exports for page components, named exports for everything else | T3 |
| NEVER inline function definitions in JSX `onClick={() => { ...10 lines }}` — extract to handler | T2 |
| NEVER nested component definitions (component inside component) | T2 |
| Props interface in same file if used once, in `.types.ts` if shared | T3 |
| `children` typed as `React.ReactNode` | T3 |
| NEVER `any` in props interface without justification comment | T2 |

### Custom hooks

```
IF logic is reused in 2+ components THEN extract to custom hook
IF component has complex state machine THEN extract to custom hook
IF hook > 50 LOC THEN split into smaller hooks (T2)
IF hook name does not start with `use` THEN finding T2
```

| Rule | Tier |
|------|------|
| Custom hooks in `hooks/` directory (or the profile's declared location) | T3 |
| Hook returns typed object, not positional array (unless 2 values like useState) | T3 |
| Hook with side effects must handle cleanup in return of useEffect | T2 |

### Error boundaries

| Rule | Tier |
|------|------|
| Error boundary at route/page level | T2 |
| Error boundary around async data-fetching sections | T2 |
| Fallback UI must be user-friendly (not stack trace) | T2 |
| Error boundary must log to the project's declared monitoring (profile); IF none declared THEN a logged, contextual error is the minimum — a boundary that swallows silently is core §4 | T2 (T1 if the boundary swallows the error with no signal at all) |
| NEVER wrap entire app in single error boundary only — granular boundaries per route | T2 |

```
IF page fetches data THEN must have error boundary (T2)
IF error boundary has no fallback UI THEN finding T2
IF only one error boundary for entire app THEN finding T2
```

### Forms

| Rule | Tier |
|------|------|
| Validation schema shared with backend (same schema source) when possible | T3 |
| Client-side validation before submit | T2 |
| Error messages displayed next to the field, not only in alert/toast | T2 |
| Submit button disabled while submitting (prevent double submit — server must still be safe: core §6 idempotency) | T2 |
| Form state reset on successful submit (unless edit mode) | T3 |
| NEVER uncontrolled inputs for forms that submit data | T2 |

### Accessibility (in code)

| Rule | Tier |
|------|------|
| Semantic HTML: `<button>` for actions, `<a>` for navigation, `<nav>`, `<main>`, `<section>` | T2 |
| All `<img>` must have `alt` attribute (empty string `alt=""` for decorative) | T2 |
| Interactive custom elements must have `role`, `aria-label`, and keyboard handler (`onKeyDown`) | T2 |
| Form inputs must have associated `<label>` (via `htmlFor` or wrapping) | T2 |
| Color must NOT be the only indicator (add icon or text) | T3 |
| Focus must be visible on all interactive elements | T2 |
| Tab order must be logical (no positive `tabIndex` values) | T2 |
| NEVER `div` or `span` with `onClick` without `role="button"` and `tabIndex={0}` and `onKeyDown` | T2 |
| Modals must trap focus | T2 |
| Page must have exactly one `<h1>` | T3 |
| Heading hierarchy must not skip levels (h1 → h3 without h2) | T3 |

---

## 2. State & Data Fetching

### State management decision tree

```
IF state used in 1 component only THEN useState (local)
IF state shared between parent-child (1-2 levels) THEN props drilling
IF state shared 3+ levels deep THEN Context or state library
IF state is server data (API responses) THEN data fetching library cache (NOT manual state)
IF state is complex with many transitions THEN useReducer or state library
IF global UI state (theme, sidebar open, toasts) THEN Context
IF global server state (user session, permissions) THEN data fetching library cache
```

| Rule | Tier |
|------|------|
| NEVER store server response in useState manually if using a data fetching library | T2 |
| NEVER put everything in global state — local first | T2 |
| Context providers must be as close to consumers as possible (not all at root) | T3 |
| NEVER mutate state directly (spread or immer) — shared-state corruption, core §6 applied to UI state | T1 |

### Data fetching

| Rule | Tier |
|------|------|
| All API calls through a centralized fetcher/client (never raw `fetch` scattered in components) | T2 |
| Loading state must be shown to user (spinner, skeleton, or similar) | T2 |
| Error state must be shown to user (not silent failure — core §4 applied to UI) | T2 (T1 if the failure is load-bearing and produces no signal anywhere) |
| Retry logic on transient network errors (at least 1 retry; cap + backoff per core §6) | T3 |
| NEVER fetch in useEffect without cleanup / abort controller | T2 |
| Request cancellation on component unmount | T2 |
| AbortError must be caught and silently ignored (it is the one expected non-failure; anything else re-thrown or logged) | T2 |
| Optimistic updates must have rollback on error | T2 |

### Client cache

```
IF data is read-heavy and changes rarely THEN cache with stale-while-revalidate
IF data is user-specific and changes frequently THEN short TTL or no cache
IF mutation succeeds THEN invalidate related cache keys (not manual refetch everywhere)
```

---

## 3. Frontend Testing

This is the frontend module-by-type test taxonomy. It complements Dante's test-quality rules and the core §34 provenance rules — it never replaces them.

### What to test by component type

**Page component:**

| Test | Tier |
|------|------|
| Renders without crash | T2 |
| Shows loading state | T2 |
| Shows error state | T2 |
| Shows data when loaded | T2 |
| Navigation/routing works | T3 |

**Feature component (with business logic):**

| Test | Tier |
|------|------|
| Happy path user interaction | T2 |
| Form validation errors shown | T2 |
| Submit calls correct API with correct data | T2 |
| Error handling (API failure) | T2 |
| Edge cases (empty state, boundary values) | T3 |

**UI component (presentational):**

| Test | Tier |
|------|------|
| Renders with required props | T3 |
| Conditional rendering based on props | T3 |
| Snapshot test ONLY if visually critical | T3 |

**Custom hook:**

| Test | Tier |
|------|------|
| Happy path return values | T2 |
| Error states | T2 |
| Cleanup on unmount | T2 |

### What NOT to test

- Styling / CSS classes applied (brittle, low value)
- Third-party library internals (router navigation, UI library rendering)
- Implementation details (internal state values, private methods)
- Static text content (unless contractual/legal)
- Every prop combination exhaustively

### Test quality rules

| Rule | Tier |
|------|------|
| Test user behavior, not implementation (`getByRole` > `getByTestId` > `querySelector`) | T2 |
| `getByTestId` only as last resort, prefer accessible queries | T3 |
| NEVER test internal state directly (test what the user sees) | T2 |
| Async operations: use `waitFor` / `findBy`, NEVER arbitrary `setTimeout` | T2 |
| Mock the API layer, never mock hooks directly (except router hooks or similar) | T2 |
| Each test independent (no shared mutable state between tests) | T2 |
| `cleanup` between tests (automatic in most frameworks, verify if custom render) | T2 |

### The real seam (core §34 applied to frontend)

The component ↔ API boundary is a producer↔consumer seam. Component tests MAY mock the API layer — that is unit isolation, not fabrication — but:

```
IF the mocked response shape is hand-typed against "what the backend returns"
  THEN it must derive from the documented contract (Alexandria's contract doc / shared schema),
       never from memory or guesswork
IF the feature's correctness depends on the real backend response shape
  THEN a §34 round-trip against the real dependency exists SEPARATELY (Dante owns it) —
       a component test with a mocked API never substitutes it
```

| Rule | Tier |
|------|------|
| Mocked API response invented instead of derived from the documented/shared contract | T1 (core §34.2 — fabricated ground truth) |
| Component test with mocked API claimed as seam verification | T1 |
| Mock that replicates production logic | T2 (core — forbidden) |

---

## 4. CSS / Styling

### Approach (project-level — lives in the profile)

The styling approach is a **project profile value**, chosen ONCE:

| Option | When to pick |
|--------|-------------|
| Utility-first (Tailwind-style) | Rapid development, no separate CSS files |
| CSS Modules | Scoped styles, traditional CSS preference |
| CSS-in-JS / Styled Components | Dynamic styles from props, theme-heavy apps |

```
IF the profile declares the approach THEN enforce it
IF the profile is missing the approach AND frontend code exists THEN fail loud (core §10) —
   report the missing profile value; do not infer it from one file and silently "enforce" a guess
IF this is the first frontend component of the project THEN the choice is made now and recorded in the profile
```

| Rule | Tier |
|------|------|
| ONE styling approach per project. No mixing. | T2 |
| NEVER inline `style={{}}` except truly dynamic computed values (e.g., `width` from data) | T2 |
| NEVER `!important` without documented justification | T2 |
| Magic numbers in spacing/sizing: use design tokens or the declared scale | T3 |
| Color values ALWAYS from design tokens / theme / variables. NEVER hardcoded hex inline. | T2 |
| Z-index values from a defined scale (constants), never arbitrary numbers | T2 |

### Responsive

| Rule | Tier |
|------|------|
| Mobile-first approach (base styles = mobile, then breakpoints up) | T3 |
| Breakpoints from the profile's declared constants, never magic numbers | T3 |
| NEVER hide critical content/functionality on mobile (only reflow) | T2 |
| Touch targets minimum 44x44px on interactive elements | T3 |

### File organization

```
IF using CSS Modules THEN one `.module.css` per component, co-located
IF using utility-first THEN no separate CSS files (classes in markup)
IF using CSS-in-JS THEN styles in same file if <50 LOC, separate `.styles.ts` if more
IF global styles needed THEN single `global.css` at root, nothing else global
```

### Size limit

| Concept | Hard limit | Sweet spot |
|---------|-----------|------------|
| CSS file | 800 LOC | 300-500 |

---

## 5. Frontend File Structure

### Directory convention (concept-keyed DEFAULT — override via project profile)

```
src/
├── pages/           # Route-level components (one per route)
├── components/      # Shared/reusable components
│   ├── ui/          # Pure presentational (Button, Input, Modal, Card)
│   └── features/    # Business-logic components (UserForm, DataTable)
├── hooks/           # Custom hooks
├── services/        # API client, fetchers, external integrations
├── utils/           # Pure functions, formatters, helpers
├── types/           # Shared TypeScript types/interfaces
├── constants/       # Enums, config values, magic strings
├── contexts/        # Context definitions
├── assets/          # Images, fonts, icons (static)
└── styles/          # Global styles, theme, design tokens
```

**Framework rule:** IF the framework imposes its own convention (file-based routing — e.g. an `app/` router — or any generator-enforced layout) THEN the framework's convention IS the profile value for structure; do not fight it. The dependency-direction and placement rules below still apply on top of whatever tree the framework mandates.

### Rules

| Rule | Tier |
|------|------|
| Co-locate component + test + types + styles in same directory when component-specific | T3 |
| Shared types in `types/`, component-specific types in component directory | T3 |
| NEVER import from `pages/` (route-level) in `components/` — pages import components, not the reverse | T2 |
| NEVER circular imports between directories | T2 |
| `index` barrel exports ONLY at directory level for public API, not for every subdirectory | T3 |
| Assets referenced by import (bundler-handled), NEVER relative path strings | T3 |

### Placement decision tree

```
IF component used in 1 page only THEN keep in that page's directory
IF component used in 2+ pages THEN move to components/
IF hook used in 1 component only THEN keep in component file
IF hook used in 2+ components THEN move to hooks/
IF utility used in 1 file only THEN keep in that file
IF utility used in 3+ files THEN move to utils/
```

---

## Acceptance gate for THIS document

Same machine as the core's gate, honestly applied: this skill has **no lived frontend incident to replay yet** — fabricating one would be the §34 sin at the meta level. Therefore:

```
IF the first real frontend internal failure occurs in any project
  THEN add it here as a replay row (incident → must classify → under §N), same format as the core gate
UNTIL then, the core's determinism probe applies as-is: hand the same frontend finding
  to two independent instances and compare the tier — divergence = ambiguous rule, pin it down
```
