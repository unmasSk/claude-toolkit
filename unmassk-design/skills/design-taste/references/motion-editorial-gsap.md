# Motion: Editorial GSAP Scroll Choreography

Source: `gpt-taste` skill by leonxlnx (MIT), condensed. Adds concrete GSAP
implementation patterns on top of `unmassk-design`'s general motion
principles (`references/motion.md` in the core skill) -- use this when a
brief specifically wants Awwwards/editorial-grade scroll choreography, not
just "some hover states".

## Structure: AIDA with heavy spacing

Attention (hero) -> Interest (features/bento) -> Desire (GSAP
scroll/media) -> Action (footer/pricing/CTA). Add huge vertical padding
between sections (`py-32 md:py-48`) so each section reads as a distinct
cinematic chapter -- never cramped together.

## Hero: the 2-3 line rule

- Ultra-wide H1 container (`max-w-5xl`/`max-w-6xl`/`w-full`) so words flow
  horizontally instead of wrapping into a text wall.
- H1 must never exceed 2-3 lines. If it's running long, shrink the font
  (`clamp(3rem, 5vw, 5.5rem)`) and widen the container -- never just let it
  wrap to 4+ lines.
- Button contrast must be correct: dark bg -> white text, light bg -> dark
  text. Invisible button text is a hard failure.
- Do not stuff the hero with floating badge icons, pill-tags, or raw
  stats -- those belong in dedicated sections below.

## Gapless bento grids

LLMs commonly leave dead empty cells in CSS grids. Use `grid-auto-flow:
dense` (Tailwind: `grid-flow-dense`) on every bento grid and verify
`col-span`/`row-span` values interlock with no missing corner or void.
Prefer 3-5 highly intentional cards over 8 messy ones.

## GSAP motion patterns

- **Hover physics:** every clickable card/image reacts --
  `group-hover:scale-105 transition-transform duration-700 ease-out`
  inside an `overflow-hidden` wrapper.
- **Scroll pinning:** pin a section title (`ScrollTrigger pin: true`) on
  one side while a gallery scrolls on the other. Start trigger at `"top
  top"`, not `"top center"` or `"top 80%"` -- the common failure is the
  pin firing halfway through scroll instead of at viewport top.
- **Image scale/fade on scroll:** images start at `scale: 0.8`, grow to
  `1.0` entering view, then darken/fade (`opacity: 0.2`) leaving view.
- **Scrubbing text reveal:** paragraph words start at `opacity: 0.1`,
  scrub sequentially to `1.0` as the user scrolls.
- **Card stacking:** cards overlap and stack from the bottom as the user
  scrolls down.
- Always clean up `ScrollTrigger`/`gsap.context` on unmount; wrap
  interactive/animated leaves in isolated client components so they don't
  trigger parent re-renders.

## Component arsenal (pick a few, don't use all at once)

- Inline typography images: small pill-shaped images embedded directly
  inside massive headings (`I shape <img class="inline-block w-24 h-10
  rounded-full ..."> digital spaces.`).
- Horizontal accordions: vertical slices expanding horizontally on hover.
- Infinite marquee for trust logos -- real icon/logo assets, not styled
  text.
- Testimonial carousel: overlapping portrait images next to minimalist
  quote typography, subtle arrow controls.

## Content bans

- No meta-labels like "SECTION 01", "QUESTION 05", "ABOUT US" -- remove
  entirely, they read as cheap.
- Stock imagery: `https://picsum.photos/seed/{keyword}/1920/1080` with the
  seed matched to the vibe, plus CSS filters (`grayscale`,
  `mix-blend-luminosity`, `contrast-125`) so it doesn't look like boring
  stock.
- Backgrounds: deep radial blurs, grainy mesh gradients, shifting dark
  overlays -- never flat, boring solid colors.
- Wrap the page in `overflow-x-hidden w-full max-w-full` to prevent
  horizontal-scroll bugs from off-screen scroll animations.

## Pre-flight check before shipping

- Hero H1 container width guarantees 2-3 line flow, no stamp icons or spam
  tags in the hero.
- Bento grid columns/rows verified to leave zero empty cells,
  `grid-flow-dense` applied.
- No cheap meta-labels anywhere; every button's text contrast is correct.
- Every scroll animation has a stated reason (hierarchy, storytelling,
  feedback, state transition) -- "it looked cool" is not a reason; if you
  can't state the reason in one sentence, drop the animation.
