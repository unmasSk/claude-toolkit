---
name: frontend-react
description: Use EVERY TIME React or frontend code is written, reviewed, tested, audited, or fixed — components, hooks, JSX, UI state, data fetching, forms, error boundaries, accessibility (a11y, ARIA, semantic HTML), CSS and styling (Tailwind, CSS Modules, CSS-in-JS), responsive design, loading/error states, or frontend file structure. Self-contained — the framework-agnostic web rules (accessibility, CSS discipline, file structure, frontend test taxonomy) live here too, not in a separate core. Extends unmassk-standards (core), which governs tiers, /110 scoring, waivers, and the project-profile pointer rule; this skill adds the frontend rows. NO attacker-model rules here (XSS, CSRF, CSP → Argus / project profile). Stack choices (styling approach, breakpoints, state library, framework routing convention, monitoring destination) live in the project profile, never hardcoded here.
---

# frontend-react

React-centered frontend quality standards, self-contained: component patterns, UI state and data fetching, frontend test taxonomy, styling discipline, and file structure — the web-agnostic sections (a11y, CSS, structure) included, valid for any frontend.

Extends `unmassk-standards` (core). A frontend finding is a normal finding: core tier semantics, scored inside the core's five dimensions (absorption map at the top of the reference — no new weight-units, the total stays /110), blocked or waived by core rules.

## Router

The full standards are in `references/frontend-standards.md`. Load the section the task needs:

| If the task involves | Read |
|----------------------|------|
| Components, hooks, error boundaries, forms, accessibility | §1 Component Patterns |
| UI state, data fetching, AbortController, optimistic updates, client cache | §2 State & Data Fetching |
| Frontend tests (per component type), mocked APIs vs the real seam (§34 core) | §3 Frontend Testing |
| CSS, styling approach, design tokens, z-index, responsive | §4 CSS / Styling |
| Directory layout, import direction, where a component/hook/util lives | §5 Frontend File Structure |
| Scoring a frontend finding into the /110 | Absorption map (top of reference) |

## Project profile

Styling approach, breakpoints/design tokens, state/data-fetching library, framework routing convention, and monitoring destination are profile values. IF a check depends on a missing profile value THEN fail loud (core §10) — never resolve the check to a silent no-op.
