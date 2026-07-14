# Style: High-End / Soft Structuralism (Awwwards-Tier Agency Look)

Source: `high-end-visual-design` skill by leonxlnx (MIT), condensed.

The "$150k agency build" register: haptic depth, cinematic spatial rhythm,
obsessive micro-interactions, flawless fluid motion. Never generate the
same layout/aesthetic twice in a row -- dynamically combine premium layout
archetypes and texture profiles while holding the elite "Apple-esque /
Linear-tier" language.

## Absolute-zero anti-patterns (any one of these fails the design)

- Banned fonts: Inter, Roboto, Arial, Open Sans, Helvetica -- use `Geist`,
  `Clash Display`, `PP Editorial New`, `Plus Jakarta Sans`.
- Banned icons: thick-stroke Lucide/FontAwesome/Material -- use
  ultra-light precise lines (Phosphor Light, Remix Line).
- Banned borders/shadows: generic `1px solid gray`, harsh dark drop shadows
  (`shadow-md`, `rgba(0,0,0,0.3)`).
- Banned layouts: edge-to-edge sticky navbars glued to the top; symmetrical
  3-column Bootstrap grids with no whitespace.
- Banned motion: `linear`/`ease-in-out`, instant state changes.

## Pick one Vibe archetype

1. **Ethereal Glass** (SaaS/AI/tech) -- OLED black `#050505`, radial mesh
   gradients (subtle glowing orbs), vantablack cards with heavy
   `backdrop-blur-2xl` and white/10 hairlines, wide geometric grotesk type.
2. **Editorial Luxury** (lifestyle/real estate/agency) -- warm cream
   `#FDFBF7`, muted sage/espresso, high-contrast variable serif for massive
   headings, subtle noise/film-grain overlay (`opacity-[0.03]`).
3. **Soft Structuralism** (consumer/health/portfolio) -- silver-grey or
   white backgrounds, massive bold grotesk, airy floating components with
   highly diffused ambient shadows.

## Pick one Layout archetype

1. **Asymmetrical Bento** -- masonry-like grid (`col-span-8 row-span-2`
   next to stacked `col-span-4`). Mobile: collapse to `grid-cols-1`, all
   spans reset to `col-span-1`.
2. **Z-Axis Cascade** -- physical-card stacking with slight `-2deg`/`3deg`
   rotation. Mobile: remove all rotation/overlap below `768px`.
3. **Editorial Split** -- massive type on the left half, scrollable
   horizontal cards/pills on the right. Mobile: full-width vertical stack.

Universal mobile override: any asymmetric layout collapses to `w-full`,
`px-4`, `py-8` below `768px`. Never `h-screen` for full-height -- always
`min-h-[100dvh]`.

## The "Double-Bezel" component technique

Never place a card/image flatly on the background -- make it look like
machined hardware (a glass plate in an aluminum tray):
- **Outer shell:** wrapper with subtle bg (`bg-black/5`), hairline ring
  (`ring-1 ring-black/5`), padding `p-1.5`/`p-2`, large radius
  (`rounded-[2rem]`).
- **Inner core:** distinct bg, inner highlight
  (`shadow-[inset_0_1px_1px_rgba(255,255,255,0.15)]`), smaller concentric
  radius (`rounded-[calc(2rem-0.375rem)]`).

## Nested CTA / "island" buttons

Primary buttons: fully rounded pills, generous padding (`px-6 py-3`). A
trailing arrow icon never sits naked -- nest it in its own circular wrapper
(`w-8 h-8 rounded-full bg-black/5`) flush with the button's inner padding.

## Spatial rhythm

- Double standard padding: `py-24` to `py-40` per section.
- Eyebrow tags before H1/H2: `rounded-full px-3 py-1 text-[10px] uppercase
  tracking-[0.2em]`.

## Motion choreography

Never default transitions -- simulate mass/spring physics with custom
cubic-beziers, e.g. `duration-700 ease-[cubic-bezier(0.32,0.72,0,1)]`.

- **Fluid nav:** floating glass pill detached from top (`mt-6 mx-auto
  w-max rounded-full`). Hamburger morphs into an X on click. Menu expands
  full-screen with heavy glass (`backdrop-blur-3xl bg-black/80`), links
  stagger in with `translate-y-12 opacity-0` → visible, `delay-100/150/200`.
- **Magnetic hover:** `group` utility, scale down on hover
  (`active:scale-[0.98]`), nested icon translates diagonally
  (`group-hover:translate-x-1 group-hover:-translate-y-[1px]`) and scales
  up (`scale-105`).
- **Scroll entry:** heavy fade-up (`translate-y-16 blur-md opacity-0` →
  `translate-y-0 blur-0 opacity-100` over `800ms+`) via `IntersectionObserver`
  or Motion's `whileInView` -- never scroll listeners.

## Performance guardrails

- Animate only `transform`/`opacity` -- never `top`/`left`/`width`/`height`.
- `backdrop-blur` only on fixed/sticky elements, never scrolling content.
- Grain/noise only on fixed, `pointer-events-none` pseudo-elements.
- No arbitrary `z-50`/`z-[9999]` -- reserve z-index for systemic layers
  (sticky nav, modal, overlay, tooltip).

## Pre-ship checklist

- [ ] No banned fonts/icons/borders/shadows/layouts/motion present
- [ ] One Vibe archetype and one Layout archetype consciously applied
- [ ] Major cards use the double-bezel (outer shell + inner core)
- [ ] CTAs use button-in-button trailing icon where applicable
- [ ] Section padding at minimum `py-24`
- [ ] All transitions use custom cubic-bezier, no `linear`/`ease-in-out`
- [ ] Scroll entry animation present on every major block
- [ ] Layout collapses to single-column, `w-full`, `px-4` below `768px`
- [ ] Animations use only `transform`/`opacity`
- [ ] `backdrop-blur` only on fixed/sticky elements
- [ ] Overall impression reads "agency build", not "template with nice fonts"
