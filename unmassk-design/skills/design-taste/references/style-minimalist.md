# Style: Premium Utilitarian Minimalism (Editorial)

Source: `minimalist-ui` skill by leonxlnx (MIT), condensed.

Clean, "document-style" interfaces analogous to top-tier workspace
platforms (Notion/Linear-adjacent). High-contrast warm monochrome, bespoke
typographic hierarchy, meticulous macro-whitespace, bento grids, ultra-flat
components with deliberate muted-pastel accents. Actively rejects generic
SaaS defaults.

## Banned defaults

- `Inter`, `Roboto`, `Open Sans` as the typeface.
- Generic thin-line icon sets (Lucide, Feather, plain Heroicons).
- Heavy drop shadows (`shadow-md`/`lg`/`xl`). Shadows must be near-absent or
  ultra-diffuse, opacity below `0.05`.
- Primary-colored large backgrounds/hero sections.
- Gradients, neon, 3D glassmorphism (beyond a subtle navbar blur).
- `rounded-full` on large containers, cards, or primary buttons.
- Emojis anywhere in code, markup, or content.
- Generic placeholders ("John Doe", "Acme Corp", Lorem Ipsum).
- AI copywriting cliches ("Elevate", "Seamless", "Unleash", "Delve").

## Typography

- **Sans (body/UI/buttons):** clean geometric or system-native with
  character -- `SF Pro Display`, `Geist Sans`, `Helvetica Neue`, `Switzer`.
- **Serif (hero headings/quotes):** `Lyon Text`, `Newsreader`, `Playfair
  Display`, `Instrument Serif`. Tight tracking `-0.02em` to `-0.04em`,
  tight leading `1.1`.
- **Mono (code/keystrokes/metadata):** `Geist Mono`, `SF Mono`, `JetBrains
  Mono`.
- Body text never pure black -- off-black/charcoal `#111111` or `#2F3437`,
  generous leading `1.6`. Secondary text muted gray `#787774`.

## Color: warm monochrome + spot pastels

- Canvas/background: pure white `#FFFFFF` or warm bone `#F7F6F3` /
  `#FBFBFA`.
- Card surface: `#FFFFFF` or `#F9F9F8`.
- Structural borders/dividers: `#EAEAEA` or `rgba(0,0,0,0.06)`.
- Accents: highly desaturated, washed-out pastels only, for tags/inline
  code/subtle icon backgrounds:
  - Pale red `#FDEBEC` / text `#9F2F2D`
  - Pale blue `#E1F3FE` / text `#1F6C9F`
  - Pale green `#EDF3EC` / text `#346538`
  - Pale yellow `#FBF3DB` / text `#956400`

## Components

- **Bento feature grids:** asymmetrical CSS Grid, cards `border: 1px solid
  #EAEAEA`, radius `8px`-`12px` max, generous internal padding
  `24px`-`40px`.
- **Primary CTA:** solid `#111111` bg / white text, radius `4px`-`6px`, no
  box-shadow. Hover: shift to `#333333` or `scale(0.98)`.
- **Tags/badges:** pill-shaped, `text-xs`, uppercase, `letter-spacing:
  0.05em`, muted-pastel background.
- **Accordions:** strip container boxes, separate with `border-bottom: 1px
  solid #EAEAEA` only. Sharp `+`/`-` toggle icon.
- **Keystrokes:** `<kbd>` with `border: 1px solid #EAEAEA`, `radius: 4px`,
  `background: #F7F6F3`, monospace.
- **Faux-OS chrome:** for software mockups, wrap in a minimal container with
  a white top bar and three small light-gray circles (macOS-style).

## Iconography and imagery

- Icons: Phosphor (Bold/Fill) or Radix UI Icons, one stroke weight
  standardized across the interface.
- Illustrations: monochrome rough continuous-line ink sketches on white,
  one offset geometric shape filled with a muted pastel.
- Photography: desaturated, warm-toned, subtle warm-grain overlay (opacity
  `0.04`). Never oversaturated stock. `https://picsum.photos/seed/{context}/
  1200/800` as a reliable placeholder.
- Backgrounds: avoid empty flat sections -- low-opacity full-width imagery,
  soft warm radial light spots (`opacity: 0.03`), or minimal line patterns
  for depth.

## Motion

Quiet sophistication, not spectacle.

- Scroll entry: `translateY(12px)` + `opacity: 0` resolving over `600ms`,
  `cubic-bezier(0.16, 1, 0.3, 1)`. Use `IntersectionObserver`, never scroll
  listeners.
- Hover: cards lift with an ultra-subtle shadow (`0 0 0` to `0 2px 8px
  rgba(0,0,0,0.04)` over `200ms`). Buttons: `scale(0.98)` on `:active`.
- Staggered reveals: `animation-delay: calc(var(--index) * 80ms)`. Never
  mount everything at once.
- Optional ambient motion: one very slow radial-gradient blob (`20s+`
  duration, opacity `0.02`-`0.04`) on a `position: fixed; pointer-events:
  none` layer -- never on a scrolling container.
- Animate only `transform`/`opacity`. No `top`/`left`/`width`/`height`.

## Execution order

1. Macro-whitespace first -- massive vertical section padding (`py-24` to
   `py-32`).
2. Constrain main content width to `max-w-4xl`/`max-w-5xl`.
3. Apply the typographic hierarchy and monochrome variables.
4. Enforce `1px solid #EAEAEA` on every card/divider/border, no exceptions.
5. Add scroll-entry animation to major content blocks.
6. Give sections visual depth (imagery, ambient gradients, subtle texture)
   -- no empty flat backgrounds.
