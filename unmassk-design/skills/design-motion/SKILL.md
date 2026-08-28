---
name: design-motion
description: >
  Use when the user asks to "make it feel good", "polish this animation",
  "review the animations", "audit the motion", "add a spring", "make this
  interruptible", "add gestures", "drag to dismiss", "animate this with
  Motion.dev", "use Framer Motion", "use React Spring", "tune the spring
  physics", "this animation feels off", "make the popover open from the
  button", or mentions any of: motion craft, animation review, spring
  physics, damping, stiffness, tension, bounce, gesture-driven UI, drag
  interactions, velocity, momentum, rubber-banding, interruptible animation,
  transform-origin, clip-path reveal, @starting-style, layout animation,
  shared element transition, layoutId, AnimatePresence, useSpring,
  Motion.dev, Framer Motion, React Spring, animation vocabulary, "what's
  this animation called".
  Covers the deep craft layer above ordinary motion implementation: Emil
  Kowalski's design-engineering philosophy (should this animate at all,
  physical correctness, interruptibility, cohesion), Apple's fluid-interfaces
  gesture/spring physics (velocity handoff, momentum projection,
  rubber-banding), the React animation library landscape (Motion.dev,
  Framer Motion, React Spring — when to use which, and how their spring
  parameters map to each other), advanced CSS techniques (clip-path,
  @starting-style, WAAPI, trigonometric choreography), a reverse-lookup
  animation vocabulary, and a ten-point non-negotiable review/audit bar for
  judging whether motion is production-craft or merely functional.
  Use when NOT: baseline motion decisions — standard duration/easing tables,
  `prefers-reduced-motion` boilerplate, basic entrance snippets, the AI Slop
  Test, or any other design domain (color, typography, layout, accessibility,
  UX writing); scroll-driven page choreography; 3D/WebGL or canvas animation;
  or exported animation formats — all out of scope here.
version: 1.0.0
---

# Design Motion -- Motion Craft

The craft layer above ordinary animation implementation. The core skill
(`skills/unmassk-design/references/motion.md`) already covers the baseline:
duration tables, standard easing curves, the two GPU-safe properties,
`prefers-reduced-motion`, stagger caps, and basic Framer Motion entrance
snippets. **Do not re-derive that here and do not duplicate it** — load it
first for the baseline, then load this family's references for judgment,
physics, library depth, and review rigor.

> **Paths.** Every `scripts/…` and `references/…` path below is relative to this skill's own directory. To actually run one, resolve that directory in the same command — a shell variable does not survive from one call to the next:

```bash
SKILL_DIR=$(find ~/.claude/plugins/cache -maxdepth 5 -type d -path '*/unmassk-design/*/skills/design-motion' 2>/dev/null | while read -r d; do [ -e "${d%/skills/*}/.orphaned_at" ] || echo "$d"; done | sort -V | tail -1)
python3 "$SKILL_DIR/scripts/<the script you want>"
```

> If `$SKILL_DIR` comes back empty, the plugin is running from a checkout rather than an install: use the absolute path from the `Base directory for this skill:` line printed when this skill loaded. `${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a command.

This skill exists for the questions the core doesn't answer: *should this
animate at all? does it feel alive when interrupted? which spring model and
which library? is this actually good, or does it just run?*

## The Core Judgment, in One Paragraph

Before reaching for a duration or a curve, decide whether the animation
should exist (frequency + purpose test), make sure it's physically honest
(nothing appears from nothing, popovers scale from their trigger, not
center), and make sure anything touchable is interruptible (springs that
retarget from the live value, never keyframes that restart from zero). Get
those three right before tuning anything. Full detail in
`references/craft-principles.md`.

## Request Routing

| User request | Reference | Load when |
|---|---|---|
| Should this animate? Purpose/frequency test, physical correctness (`scale(0)`, origin-aware popovers), custom easing curves, interruptibility, gesture/drag physics (velocity handoff, momentum projection, rubber-banding), cohesion, debugging a transition that "feels off" | `references/craft-principles.md` | Any judgment call about whether/how something should animate — the first stop for most requests |
| "What's this animation called" / naming an effect for a prompt or a designer | `references/vocabulary.md` | Reverse-lookup only — not for designing or building the effect |
| Motion.dev, Framer Motion, React Spring — which library, gestures, layout/shared-element transitions, `AnimatePresence`, scroll-linked values, spring parameter tuning (stiffness/damping/mass vs tension/friction vs duration/bounce) | `references/react-libraries.md` | Any React animation implementation beyond the core's basic entrance snippets |
| clip-path reveals, `@starting-style`, WAAPI, transform mastery (`translateY(%)`, 3D transforms), the CSS-variable perf trap, trigonometric choreography for circular/radial layouts, hiding elements without visual artifacts | `references/css-animations.md` | Any CSS-only technique beyond the core's fade/slide/scale keyframes |
| Reviewing a diff, auditing a codebase's motion, deciding block vs approve, the ten non-negotiable standards, escalation triggers, remedial fix ordering | `references/animation-review.md` | Any review, audit, or "make this feel better" request |

Load references on-demand — never all at once. Most requests need exactly
one, occasionally two (a review always cross-checks against
`craft-principles.md`; a library implementation question sometimes needs
the physics cross-reference table there too).

## Scripts

Scripts are tools, not optional helpers. Run them via Bash. Do not replicate
their logic manually.

| Script | Purpose | Usage |
|---|---|---|
| `scripts/motion-framer/animation_generator.py` | Generate Motion/Framer Motion component boilerplate for 11 animation types (hover, tap, drag, exit, layout, scroll, spring, stagger, gesture, variant, custom) | `python3 scripts/motion-framer/animation_generator.py --type <type> --name <Component> [--output file.jsx] [--typescript] [--constraints] [--shared-id <id>] [--spring]` |
| `scripts/motion-framer/variant_builder.py` | Build Motion/Framer Motion variant configurations from 7 presets (fade, slide, scale, rotate, stagger, modal, page) or interactively | `python3 scripts/motion-framer/variant_builder.py [--preset <name>] [--output variants.js] [--typescript] [--interactive]` |
| `scripts/react-spring-physics/physics_calculator.py` | Calculate damping ratio, critical friction, and settle time for React Spring `{ mass, tension, friction }` configs; classify under/critical/over-damped | `python3 scripts/react-spring-physics/physics_calculator.py [--feel <preset>\|--tension N --friction N\|--critical --tension N]` |
| `scripts/react-spring-physics/spring_generator.py` | Generate React Spring boilerplate for 7 patterns (click, scroll, trail, transition, inview, chain, gesture) | `python3 scripts/react-spring-physics/spring_generator.py --type <type> [--output file.jsx]` |
| `scripts/motion-dev/validate_motion_config.py` | Validate a Motion.dev animation config JSON against `schema/motion-config.schema.json`; warns on missing accessibility/performance fields | `python3 scripts/motion-dev/validate_motion_config.py <config.json>` or `--all <directory>`. **Requires** `pip install jsonschema` (see `scripts/requirements.txt`) |

### Assets (`scripts/<tool>/assets/`)

Not loaded into context — reference material and starter templates copied
into a project on request, never read wholesale:

- `scripts/motion-framer/assets/examples/README.md` — large collection of
  production-ready Framer Motion patterns (page transitions, gestures,
  modals, forms, lists). Grep for a section, don't load whole.
- `scripts/motion-framer/assets/starter_motion/` — complete Vite + React
  starter project wired with Framer Motion example components.
- `scripts/react-spring-physics/assets/README.md` — React Spring starter
  template, official example links, and common patterns.

## When to Route to the Core Instead

If the request is a plain "add a fade-in" / "what duration should a modal
use" / "how do I respect reduced motion" with no craft judgment involved,
`skills/unmassk-design/references/motion.md` already answers it directly —
don't load this family for it. This family is for the layer above: *is this
animation justified, does it feel right when interrupted, which library and
which spring model, and is it good enough to ship.*

## Attribution

- **Craft principles** — Emil Kowalski's `emil-design-eng` skill (MIT) and
  Apple's WWDC design talks translated to the web, via the `apple-design`
  skill (MIT).
- **Vocabulary** — Emil Kowalski's `animation-vocabulary` skill (MIT).
- **Review bar** — Emil Kowalski's `review-animations` and
  `improve-animations` skills (MIT).
- **React libraries** — Motion.dev API from `motion-dev-animations-skill`
  (MIT); Framer Motion patterns from `claudedesignskills/motion-framer`
  (Apache 2.0); React Spring/Popmotion physics from
  `claudedesignskills/react-spring-physics` (Apache 2.0).
- **CSS techniques** — clip-path/`@starting-style`/transform mastery from
  `emil-design-eng` (MIT); trigonometric choreography and visibility
  patterns from the `css-animation` walkthrough-generator skill (MIT).

All source content is condensed and rewritten for this skill's voice; none
of the original SKILL.md files are reproduced verbatim.
