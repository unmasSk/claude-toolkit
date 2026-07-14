# Animation Review — the craft bar

Use this when the user asks to "review the animations", "audit the motion", "make this feel better", or hands over a diff/component that adds or changes motion. Default posture: **flag first, approve is earned.** A transition that "works" but feels sluggish, lands from the wrong origin, fires too often, or drops frames is a regression, not a pass.

Condensed from Emil Kowalski's `review-animations` and `improve-animations` skills (MIT). This is the QA layer over the rest of the family — `craft-principles.md` explains *why* a rule exists; this file is the checklist to run a diff or a codebase against it.

## The ten non-negotiable standards

Every animation in scope is measured against these. A violation is a finding.

1. **Justified motion.** Every animation must answer "why does this animate?" (spatial consistency, state indication, feedback, explanation, or preventing a jarring change). "It looks cool" on a frequently-seen element is a block.
2. **Frequency-appropriate.** 100+/day and keyboard-initiated actions get **no** animation. Tens/day gets reduced/removed. Occasional gets standard. Rare/first-time can have delight.
3. **Responsive easing.** Entering/exiting elements use `ease-out` or a strong custom curve. `ease-in` on UI is a block. Built-in CSS easings are too weak for deliberate motion — expect custom cubic-beziers.
4. **Sub-300ms UI.** UI animations stay under 300ms unless justified (see per-element budgets in `craft-principles.md` §3 and the core's duration table).
5. **Origin & physical correctness.** Popovers/dropdowns/tooltips scale from their trigger, not center. Never `scale(0)` — start from `scale(0.9–0.97)` + opacity. Modals are exempt (they stay centered — don't flag it).
6. **Interruptibility.** Rapidly-triggered or gesture-driven motion (toasts, toggles, drags) must be interruptible — transitions or springs that retarget from current state, not keyframes restarting from zero.
7. **GPU-only properties.** Animate `transform` and `opacity` only. `width`/`height`/`margin`/`padding`/`top`/`left` — or Framer Motion `x`/`y`/`scale` shorthands under load — are performance findings.
8. **Accessibility.** `prefers-reduced-motion` honored (gentler, not zero — keep opacity/color, drop movement). Hover motion gated behind `@media (hover: hover) and (pointer: fine)`.
9. **Asymmetric enter/exit.** Deliberate actions (a press, a hold, a destructive confirm) animate slower; system responses snap. Symmetric timing on press-and-release is a finding.
10. **Cohesion.** Motion matches the component's and the product's personality — playful can be bouncier, a dashboard stays crisp. When unsure whether motion feels right, the strongest move is often to delete it.

## Escalation triggers — flag these on sight, hard

- `transition: all` (unbounded property animation)
- `scale(0)` or a pure-fade entrance with no initial transform
- `ease-in` on any UI interaction; weak built-in easing on deliberate motion
- Animation on a keyboard shortcut, command-palette toggle, or any 100+/day action
- UI duration > 300ms with no stated reason
- `transform-origin: center` on a trigger-anchored popover/dropdown/tooltip
- `@keyframes` on toasts, toggles, or anything added/triggered rapidly
- Animating layout properties (`width`/`height`/`margin`/`padding`/`top`/`left`)
- Framer Motion `x`/`y`/`scale` props on motion that runs while the page is busy
- Updating a CSS variable on a *parent* to drive a child transform (style-recalc storm — see `css-animations.md`)
- Missing `prefers-reduced-motion` handling on movement
- Ungated `:hover` motion (fires falsely on touch tap)
- Symmetric enter/exit timing on a press-and-release or hold interaction
- An everything-at-once entrance where a 30–80ms stagger belongs

## Remedial preference hierarchy — in this order

1. **Delete the animation** (high-frequency / no purpose / keyboard-triggered).
2. **Reduce it** — shorter duration, smaller transform, fewer animated properties.
3. **Fix the easing** — swap `ease-in` → `ease-out`/custom curve.
4. **Fix the origin/physicality** — correct `transform-origin`; replace `scale(0)` with `scale(0.95)` + opacity.
5. **Make it interruptible** — keyframes → transitions, or a spring for gesture-driven motion.
6. **Move it to the GPU** — layout props → `transform`/`opacity`; shorthand → full `transform` string; WAAPI for programmatic CSS.
7. **Asymmetric timing** — slow the deliberate phase, snap the response.
8. **Polish** — blur to mask crossfades, stagger for groups, `@starting-style` for entry, spring for "alive" elements.
9. **Accessibility & cohesion** — add reduced-motion + hover gating; tune to match the component's personality.

## Required output — a single-diff review

Two parts, in order.

**Part 1 — findings table** (never a "Before:/After:" list):

| Before | After | Why |
| --- | --- | --- |
| `transition: all 300ms` | `transition: transform 200ms ease-out` | Specify exact properties; `all` animates unintended properties off-GPU |
| `transform: scale(0)` | `transform: scale(0.95); opacity: 0` | Nothing appears from nothing |
| `ease-in` on dropdown | `ease-out` + custom curve | `ease-in` delays the moment the user watches most |
| `transform-origin: center` on popover | `var(--radix-popover-content-transform-origin)` | Popovers scale from their trigger, not center (modals exempt) |

**Part 2 — verdict**, grouped by impact tier, highest first, empty tiers omitted:
1. Feel-breaking regressions (sluggish easing, comes-from-nowhere, fires on high-frequency/keyboard actions)
2. Missed simplifications (animations that should be removed or drastically reduced)
3. Performance (non-GPU properties, dropped-frame risk, recalc storms)
4. Interruptibility & timing (keyframes where transitions/springs belong; symmetric timing that should be asymmetric)
5. Origin, physicality & cohesion (wrong origin, mismatched personality, jarring crossfades)
6. Accessibility (reduced-motion and pointer/hover gating)

Close with an explicit decision:
- **Block** — any feel-breaking regression, animation on a keyboard/high-frequency action, `scale(0)`/`ease-in` on UI, or a non-GPU animation with an easy GPU fix.
- **Approve** — no feel-breaking regressions, no obvious motion that should be deleted, durations/easing in bounds, interruptibility handled where needed, reduced-motion respected.

Cite `file:line`. Pull exact values from `craft-principles.md` / the core's `motion.md` rather than approximating.

## Whole-codebase audit — the eight categories

When surveying a codebase rather than reviewing one diff, audit against these (each maps to standards above):

1. **Purpose & frequency** — hunt for animation on keyboard-initiated actions, command palettes with unnecessary open/close transitions, decorative motion on constantly-hit hover states.
2. **Easing & duration** — hunt for `ease-in` anywhere, bare `ease`/`linear` on entrances, durations > 300ms on UI, tooltip delay-plus-animation repeated on every item in a toolbar (should be instant after the first).
3. **Physicality & origin** — hunt for `scale(0)`, pure-fade entrances with no initial transform, missing/centered `transform-origin` on trigger-anchored elements, pressable elements with no press feedback.
4. **Interruptibility** — hunt for `@keyframes` on toasts/toggles/rapidly-triggered UI, drags without velocity-based dismissal, hard stops at drag boundaries instead of rising friction (`craft-principles.md` §5).
5. **Performance** — hunt for `transition: all`, animated layout properties, Framer Motion shorthand props on busy pages, `setProperty('--x', …)` driving child transforms.
6. **Accessibility** — hunt for movement with no `prefers-reduced-motion` handling, ungated `:hover` motion.
7. **Cohesion & tokens** — hunt for duplicated near-identical easings/durations that should be one shared token, one bouncy component in an otherwise crisp app, list/grid entrances missing a stagger.
8. **Missed opportunities** (additive, not corrective) — state changes that teleport where a brief transition would prevent a jarring change, spatially-connected UI with no motion explaining where it came from, rare high-emotion moments (first-run, success) with none of the delight budget they're allowed.

Severity for audit findings: **HIGH** = feel-breaking (wrong easing on UI, animation on keyboard/high-frequency actions, dropped frames, `scale(0)`). **MEDIUM** = noticeably off (wrong origin, non-interruptible dynamic UI, missing reduced-motion). **LOW** = polish (stagger, blur-masked crossfades, token consolidation).

Vet every finding against the actual code before reporting it — reject anything that's by-design, mis-attributed, or exempt (a modal's centered `transform-origin` is correct, not a finding). Never present a finding not confirmed at its file:line.

## Attribution

Standards, escalation triggers, remedial hierarchy, and audit categories condensed from Emil Kowalski's `review-animations` and `improve-animations` skills (MIT) — `STANDARDS.md` and `AUDIT.md` in the source repo hold the full, uncondensed rule catalog if a finding needs a citation this file doesn't carry.
