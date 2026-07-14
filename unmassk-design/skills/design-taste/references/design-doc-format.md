# Design-Doc Format: Semantic DESIGN.md for Downstream Tools/Agents

Source: `stitch-design-taste` skill by leonxlnx (MIT), condensed. Written
originally for prompting Google Stitch; the format is useful any time you
need to hand a concrete, opinionated design language to another agent or
tool as a single written spec rather than as code.

## When to use this

When the deliverable is a *document* that another agent, tool, or
generator will read to produce screens/code -- not code you're writing
yourself. Use it to translate whichever named style (brutalist,
minimalist, soft/high-end) or brief you've chosen into a structured,
semantic spec: descriptive natural language paired with precise values.

## Step 1 -- Set the dials

Four dials control tone; state chosen values before writing the doc:

| Dial | 1 | 5 | 10 |
|---|---|---|---|
| Creativity | Ultra-minimal, Swiss, monochrome | Balanced, clean with personality | Expressive, editorial, inline images in headlines, strong asymmetry |
| Density | Gallery-airy, massive whitespace | Balanced sections | Cockpit-dense, data-heavy |
| Variance | Predictable, symmetric grids | Subtle offsets | Artsy chaotic, no two sections alike |
| Motion Intent | Static, no animation | Subtle hover/entrance cues | Cinematic orchestration on every component |

Default baseline if nothing else is specified: Variance 8, Motion 6,
Density 4.

## Step 2 -- Write the document in this structure

```markdown
# Design System: [Project Title]

## 1. Visual Theme & Atmosphere
(Evocative description of mood, density, variance, motion intensity.)

## 2. Color Palette & Roles
- Named color (hex) — functional role, one line each
(Max 1 accent color. Saturation < 80%. No purple/neon "AI" aesthetic.
Never pure black — Off-Black or Zinc-950. One palette for the whole doc,
no warm/cool gray mixing.)

## 3. Typography Rules
- Display / Body / Mono: font name — behavior (tracking, leading, scale)
- Banned: list fonts explicitly excluded and why

## 4. Component Stylings
Buttons, cards, inputs, loaders, empty states, error states — shape,
color, shadow depth, interaction behavior for each.

## 5. Layout Principles
Grid system, spacing philosophy, containment width, responsive strategy,
full-height section rule (`min-h-[100dvh]`, never `h-screen`).

## 6. Motion & Interaction
Animation engine (spring physics values), staggered reveals, perpetual
micro-interactions if density/motion dials call for them, hardware rules
(transform/opacity only).

## 7. Anti-Patterns (Banned)
Explicit "NEVER DO" list for this specific document — not a copy of a
generic checklist, but the specific tells that would break THIS design.
```

## Best practices for writing it

- **Be descriptive, not just numeric:** "Deep Charcoal Ink (`#18181B`)",
  not "dark text".
- **Be functional:** state what each token is *for*, not just its value.
- **Be consistent:** same term for the same thing everywhere in the doc.
- **Be precise:** always include hex/rem/px values alongside the
  descriptive name.
- **Be opinionated:** this is not a neutral template. It should read as
  enforcing one specific, premium aesthetic -- not "here are some options".

## Common pitfalls

- Technical jargon with no translation (write "generously rounded corners",
  not just "rounded-xl").
- Hex codes or functional roles omitted.
- Vague atmosphere descriptions that could apply to any project.
- Skipping the anti-pattern section -- what's explicitly banned is as load
  -bearing as what's prescribed.
- Defaulting back to a generic "safe" design instead of holding the
  curated aesthetic the dials called for.
