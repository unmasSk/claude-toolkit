# unmassk-design

**Frontend + mobile design toolkit**

Complete design system generation, aesthetic direction, color and typography, accessible interaction, responsive layout, UX writing, design tokens, component library setup, and AI-native interface patterns — plus six specialist branches for motion craft, 3D/WebGL, scroll-driven animation, animation formats, named aesthetic directions, and Flutter UI.

## What's included

- 7 skills: the core (`unmassk-design`) + 6 family branches
- Core: 11 references, BM25 search engine + 12 CSV databases, design system generator
- Branches: condensed, attributed references per family (see each branch's own reference count below)

## Quick start

Run `/plugin` in Claude Code and install `unmassk-design` from the marketplace.

## The 7 skills

| Skill | Covers | Source |
|---|---|---|
| `unmassk-design` (core) | Design systems, color, typography, layout, accessibility, UX writing, agentic UX, AI Slop Test | Impeccable, UI/UX Pro Max, bencium-marketplace |
| `design-motion` | Motion craft above ordinary implementation: should-it-animate judgment, physical correctness, interruptibility, gesture/spring physics, Motion.dev/Framer Motion/React Spring, advanced CSS techniques, animation vocabulary, a 10-point review bar | emilkowalski/skills, motion-dev-animations-skill, claudedesignskills, css-animation-skill |
| `design-3d` | Choosing a 3D/WebGL engine (Three.js, R3F, Babylon.js, PlayCanvas), immersive VR/AR (A-Frame/WebXR), lightweight decorative 3D (Zdog, Vanta.js, Vanilla-Tilt, Spline, PixiJS), the Blender-to-glTF and Substance Painter PBR pipeline | claudedesignskills |
| `design-scroll` | Scroll-driven libraries and when to use which: GSAP ScrollTrigger (pinning/scrubbing), Locomotive Scroll (smooth-scroll feel), Barba.js (SPA-like page transitions), AOS (zero-JS scroll reveal) | claudedesignskills |
| `design-animation-formats` | Lottie/dotLottie (After Effects export), Rive (state-machine interactive vector), Anime.js (hand-authored timelines/morphing), animated component libraries (Magic UI, React Bits) | claudedesignskills |
| `design-taste` | Named aesthetic directions with concrete tokens (brutalist, minimalist, high-end/soft), redesign-to-premium audits, image-to-code translation, `DESIGN.md` authoring, brand-kit/logo generation | taste-skill |
| `design-flutter` | Flutter UI composition (layout, Material 3/Cupertino theming), animation (implicit, explicit, Hero, physics, page transitions), and CustomPaint/performance-safe rendering | claude-flutter-ui-skills |

Full source attribution (URLs, licenses, per-branch upstream skill names) lives in `PROVENANCE.md` and `CREDITS.md`. All branch content is condensed and rewritten in this plugin's own voice — none of it is a byte-faithful lift.

Each branch's `SKILL.md` documents its own "use when NOT" boundary against the other branches and against the core — load the branch that matches the request, not all of them.

## Core skill (`unmassk-design`)

The sections below (design system generation, references, scripts, commands) describe the core skill only. The 6 family branches each carry their own routing table and references — see `PROVENANCE.md` for what each one covers and where it comes from.

### Design system generation

Before any design work, the skill generates a complete design system from a plain-language product description. This is the first step for every new project.

`search.py` queries a BM25-indexed corpus built from 12 CSV databases. The `--design-system` flag runs a full generation pipeline: pattern matching, style selection, color palette construction, typography stack recommendation, spacing system, and anti-pattern detection — all scoped to the product category.

| CSV file | What it contains |
|---|---|
| `app-interface.csv` | Accessibility and interaction rules for mobile/React Native app interfaces — icon labels, touch targets, ARIA patterns |
| `charts.csv` | Chart type selection guide — best chart per data type, color guidance, accessibility grades, library recommendations |
| `colors.csv` | Ready-made color palettes per product type (SaaS, e-commerce, healthcare…) with full token set including dark mode |
| `google-fonts.csv` | Full Google Fonts catalog with classifications, variable axes, popularity rank, and CDN import URLs |
| `icons.csv` | Curated icon reference — name, category, Phosphor library import code, and best-use context |
| `landing.csv` | Landing page layout patterns — section order, CTA placement, color strategy, conversion optimization tips |
| `products.csv` | Per-product-type design recommendations — primary style, landing pattern, color focus, key considerations |
| `react-performance.csv` | React/Next.js performance anti-patterns — async waterfalls, unnecessary renders, with do/don't code examples |
| `styles.csv` | Visual style catalog (Minimalism, Glassmorphism, Neumorphism…) — colors, effects, framework compatibility, era, CSS keywords |
| `typography.csv` | Font pairing library — heading + body combinations, mood keywords, Google Fonts URLs, Tailwind config snippets |
| `ui-reasoning.csv` | Decision rules per UI category — recommended pattern, style priority, color mood, anti-patterns |
| `ux-guidelines.csv` | UX best practices by category (navigation, scroll, forms…) — do/don't with code examples |

Example command:

```
python3 ${CLAUDE_PLUGIN_ROOT}/skills/unmassk-design/scripts/search.py 'SaaS dashboard analytics' --design-system -p 'ExampleApp'
```

Example output:

```
+-----------------------------------------------------------------------------------------+
|  TARGET: ExampleApp - RECOMMENDED DESIGN SYSTEM                                         |
+-----------------------------------------------------------------------------------------+
|  PATTERN: AI Personalization Landing                                                    |
|  STYLE: Data-Dense Dashboard                                                            |
|     Keywords: Multiple charts/widgets, data tables, KPI cards, minimal padding          |
|  COLORS:                                                                                |
|     Primary:    #2563EB                                                                 |
|     Secondary:  #3B82F6                                                                 |
|     CTA:        #F97316                                                                 |
|     Background: #F8FAFC                                                                 |
|     Text:       #1E293B                                                                 |
|  TYPOGRAPHY: Fira Code / Fira Sans                                                      |
|     Mood: dashboard, data, analytics, technical, precise                                |
|  KEY EFFECTS: Hover tooltips, chart zoom on click, smooth filter animations             |
|  AVOID: Ornate design, no filtering                                                     |
+-----------------------------------------------------------------------------------------+
```

Use this output as the foundation for all subsequent design decisions. If the project already has a Tailwind config, tokens file, or Figma variables, read those first and treat them as the source of truth — only generate a new system if none exists.

## References

Eleven reference files provide the knowledge base. The skill loads them on-demand based on the request — not all at startup.

| Reference | Domain |
|---|---|
| `design-principles.md` | Aesthetic philosophy, visual hierarchy, contrast, whitespace, the Impeccable framework |
| `color.md` | Color theory, palette construction, dark mode implementation, semantic color tokens, contrast ratios |
| `typography.md` | Font stacks, type scales (fluid and fixed), font pairing rules, OpenType features, typographic correctness |
| `motion.md` | Motion principles, easing curves, duration guidelines, reduced motion, Framer Motion patterns |
| `layout-and-space.md` | Spacing systems, 4pt grid, CSS Grid and Flexbox patterns, z-index scale, visual rhythm |
| `interaction.md` | Focus management, keyboard navigation, form design, ARIA patterns, error states, loading states |
| `responsive.md` | Breakpoint systems, mobile-first approach, container queries, fluid typography, responsive images |
| `ux-writing.md` | Microcopy principles, button labels, error messages, empty states, onboarding copy, voice and tone |
| `design-system-kickoff.md` | Design token structure, Tailwind config scaffolding, shadcn setup, component naming conventions |
| `accessibility.md` | WCAG 2.2 checklist, ARIA roles and properties, screen reader behavior, keyboard interaction patterns |
| `agentic-ux.md` | AI-native interface patterns, memory UI, trust signals, progressive disclosure, error recovery in agentic flows |

## Scripts

| Script | Purpose | Flags |
|---|---|---|
| `search.py` | Query the design reference corpus for patterns, tokens, or a full design system | `--design-system`, `--domain`, `-p` |

### search.py flags

| Flag | What it does |
|---|---|
| `--design-system` | Generate a complete design system: pattern, style, colors, typography, spacing, effects, anti-patterns |
| `--domain color` | Search color reference only: palettes, dark mode strategies, contrast values |
| `--domain typography` | Search typography reference only: font stacks, type scales, pairing rules |
| `-p '<project name>'` | Scope recommendations to a specific product name and category |

Install dependencies before first run:

```
pip install -r ${CLAUDE_PLUGIN_ROOT}/skills/unmassk-design/scripts/requirements.txt
```

`${CLAUDE_PLUGIN_ROOT}` is auto-resolved by Claude Code. Use it as written in all script invocations.

## User interaction workflow

Before executing any design work, the skill presents 2-3 design system options in plain language. Each option describes the visual feeling in non-technical terms:

- The visual feeling, not the style name ("elegant and calm" not "Soft UI Evolution")
- The color palette as a simple list with descriptive names
- The typography choice by mood ("sophisticated serif" not "Cormorant Garamond")

The skill offers to generate quick HTML mockups so the user can see the options before committing. Mockups are saved as `mockup-option-a.html`, `mockup-option-b.html`, etc., and cover header, hero, one content block, and footer.

Execution proceeds only after the user selects a direction.

| Request type | Behavior |
|---|---|
| Subjective (colors, style, vibes) | Present 2-3 options with plain descriptions, offer mockups |
| Technical (animation, responsive, accessibility) | Execute directly, no options needed |
| Explicit (specific color, specific font) | Execute without asking |
| Partial change ("same style, different colors") | Re-run `search.py` for the changed domain only, keep everything else |
| Full reset ("start over") | Return to initial design direction step |

## Design commands

These are the 17 user-facing actions the skill understands. The first ten are steering commands from Impeccable — treat each as a precise instruction, not a vague request.

| Command / Request | What it does | References loaded |
|---|---|---|
| `audit` | Technical quality checks: contrast ratios, spacing consistency, type scale, ARIA coverage, touch targets, motion safety | `design-principles.md` + `accessibility.md` |
| `critique` | UX review focused on hierarchy, clarity, emotional tone, and whether the design communicates its intent | `design-principles.md` |
| `polish` | Final pass before shipping: tighten spacing, fix orphaned text, verify alignment, confirm hover states, check empty states | `design-principles.md` + `typography.md` |
| `bolder` | Amplify a design that is too safe or forgettable — increase contrast, add color, add weight, add motion | `design-principles.md` + `color.md` + `motion.md` |
| `quieter` | Tone down a design that is overly loud or cluttered — reduce contrast, desaturate, simplify | `design-principles.md` + `color.md` |
| `animate` | Add purposeful motion: define what moves, when, how fast, and why — justify every animation against user benefit | `motion.md` |
| `colorize` | Introduce strategic color into a neutral or monochrome design — expand palette, establish hierarchy through color | `color.md` |
| `distill` | Strip the design to its essential elements — remove decorative noise, collapse redundant structure | `design-principles.md` + `layout-and-space.md` |
| `harden` | Add error handling, validation states, loading states, i18n-safe layouts, and edge cases the happy path hides | `interaction.md` + `ux-writing.md` |
| `normalize` | Align a component or screen with the project's design system — standardize tokens, replace one-offs, enforce grid | `design-system-kickoff.md` |
| Design philosophy, aesthetic direction | Explain what makes good design for this context | `design-principles.md` |
| Colors, palettes, dark mode | Color selection, contrast auditing, dark mode strategy | `color.md` |
| Fonts, type scale, font pairing | Typography selection and scale decisions | `typography.md` |
| Spacing, grids, layout systems | Layout structure, spacing audit, grid setup | `layout-and-space.md` |
| Forms, focus states, keyboard navigation | Form design, interactive components, ARIA | `interaction.md` |
| Breakpoints, mobile-first, responsive | Responsive design, mobile audit, breakpoint planning | `responsive.md` |
| AI interfaces, agentic UX, memory UI | AI-native product design, trust signals, agentic flows | `agentic-ux.md` |

## Skill routing

The orchestrator loads each of the 7 skills' frontmatter (name + description) at boot and injects the matching one(s) into the agent's prompt by criterion — there is no per-agent search step. This is separate from the core's own `search.py` BM25 corpus search over the 12 CSV databases (see above), which is unaffected and scoped to the core skill only.

## Dependencies

Python 3.x is required for the core's `search.py`. The 6 family branches are documentation-only (no scripts).

## Attribution

- Core: [Impeccable](https://github.com/pbakaus/impeccable) by Paul Bakaus (Apache 2.0), [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) by nextlevelbuilder (MIT), and plugins by [bencium.io](https://github.com/bencium/bencium-marketplace) (MIT).
- `design-motion`: [emilkowalski/skills](https://github.com/emilkowalski/skills) (MIT), [motion-dev-animations-skill](https://github.com/199-biotechnologies/motion-dev-animations-skill) (MIT), [claudedesignskills](https://github.com/freshtechbro/claudedesignskills) (Apache 2.0), [css-animation-skill](https://github.com/neonwatty/css-animation-skill) (MIT).
- `design-3d`, `design-scroll`, `design-animation-formats`: [claudedesignskills](https://github.com/freshtechbro/claudedesignskills) by freshtechbro (Apache 2.0).
- `design-taste`: [taste-skill](https://github.com/leonxlnx/taste-skill) by leonxlnx (MIT).
- `design-flutter`: [claude-flutter-ui-skills](https://github.com/Naimehossein77/claude-flutter-ui-skills) by Naimehossein77 (MIT).

Full mapping (which upstream skill fed which branch) in `PROVENANCE.md`; per-source credit in `CREDITS.md`. Every branch is condensed and rewritten in this plugin's own voice — no byte-faithful lift.

## License

MIT
