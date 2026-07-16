---
name: frontend-react
description: Use EVERY TIME React or frontend code is written, reviewed, tested, audited, or fixed — components, hooks, JSX, UI state, data fetching, forms, error boundaries, accessibility (a11y, ARIA, semantic HTML), CSS and styling (Tailwind, CSS Modules, CSS-in-JS), responsive design, loading/error states, or frontend file structure. Self-contained — the framework-agnostic web rules (accessibility, CSS discipline, file structure, frontend test taxonomy) live here too, not in a separate core. Extends unmassk-standards (core), which governs tiers, /110 scoring, waivers, and the project-profile pointer rule; this skill adds the frontend rows. NO attacker-model rules here (XSS, CSRF, CSP → Argus / project profile). Stack choices (styling approach, breakpoints, state library, framework routing convention, monitoring destination) live in the project profile, never hardcoded here.
allowed-tools: mcp__agent-browser, Bash(agent-browser:*), Bash(npx agent-browser:*), Bash(npm i -g agent-browser:*)
---

# frontend-react

React-centered frontend quality standards, self-contained: component patterns, UI state and data fetching, frontend test taxonomy, styling discipline, and file structure — the web-agnostic sections (a11y, CSS, structure) included, valid for any frontend.

Extends `unmassk-standards` (core). A frontend finding is a normal finding: core tier semantics, scored inside the core's five dimensions (absorption map at the top of the reference — no new weight-units, the total stays /110), blocked or waived by core rules.

## ⚠️ Browser work: use AgentBrowser to SEE and drive the real UI

**The moment a task needs you to observe or drive the rendered result — validate how it looks on screen, scrape a page, navigate, fill a form, check a flow, log into a site — use AgentBrowser** (the `mcp__agent-browser__*` MCP tools, registered on demand — see `references/agent-browser.md` — backed by the `agent-browser` CLI). Never assume how the UI renders or behaves: open it and check. (Writing components/hooks/JSX/CSS by itself does **not** invoke this — it applies the moment you must look at or drive the running UI.)

**Preflight — before first use, once per machine:** run `agent-browser --version`. If it fails or is `< 0.31.2` (the version with the MCP server), install: `npm i -g agent-browser@latest && agent-browser install` (downloads Chrome for Testing once, ~186 MB). **If install fails (e.g. no network), STOP and report — never fake a visual check.** Load the live how-to before operating: `agent-browser skills get core` (version-matched to the binary, never stale).

- **Visual validation = capture and JUDGE the image.** open the URL → screenshot to a file **in the session scratchpad dir** → **`Read` the PNG back and evaluate it** (broken / correct / missing / overlapping). The judgment is worthless unless you actually read the image; never "it should look fine".
- **Inspect / scrape / interact:** `snapshot` (accessibility tree, `@eN` refs, low context) → click/fill/type by ref. Exact command/tool syntax: `agent-browser skills get core` (authoritative, version-matched) — do not hardcode it from memory.

**ONLY EXCEPTION — TESTS use Playwright**, not AgentBrowser: suites and specs (E2E, component, regression) need a runner, assertions, and CI, which AgentBrowser does not provide. Observing/driving the running UI ⇒ AgentBrowser; tests ⇒ Playwright.

Install, MCP wiring, version pin, and login/session patterns: **`references/agent-browser.md`**.

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
| Observe/validate the rendered UI, scrape, navigate, login, drive a real flow | **`references/agent-browser.md`** (AgentBrowser; tests → Playwright) |

## Project profile

Styling approach, breakpoints/design tokens, state/data-fetching library, framework routing convention, and monitoring destination are profile values. IF a check depends on a missing profile value THEN fail loud (core §10) — never resolve the check to a silent no-op.
