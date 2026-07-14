---
name: design-animation-formats
description: >
  Use when the user asks to "add a Lottie animation", "import an After
  Effects animation", "build an interactive Rive animation", "add a state
  machine animation", "animate with Anime.js", "build a timeline animation",
  "morph an SVG", "stagger these elements", "add Magic UI components", "use
  React Bits", "add a pre-built animated component", "shimmer button",
  "border beam", "animated marquee", "particles background", or mentions any
  of: Lottie, dotLottie, Bodymovin, lottie-web, lottie-react, After Effects
  JSON export, Rive, .riv, state machine, ViewModel data binding, Anime.js,
  anime.timeline, SVG path morphing, stagger, keyframe animation, Magic UI,
  React Bits, shadcn animated component.
  Covers four designer-facing animation formats/libraries and when each
  applies: Lottie (After Effects animation shipped as JSON/dotLottie, no
  runtime logic), Rive (state-machine-driven interactive vector animation
  with two-way data binding), Anime.js (hand-authored JS timelines, stagger,
  SVG morphing, framework-agnostic), and animated component libraries (Magic
  UI + React Bits pre-built animated React components instead of hand-rolling
  an effect). Includes web/React integration snippets, common pitfalls, and
  performance guidance for each.
  Use when NOT: the animation is scroll-driven page choreography (GSAP,
  Locomotive Scroll, Barba) -- use `design-scroll`; the animation is 3D/WebGL
  (Three.js, R3F, Babylon.js, Spline) -- use `design-3d`; the request is
  general motion principles (easing, duration, reduced-motion) with no
  specific format in mind -- use `unmassk-design`'s motion reference.
  Based on claudedesignskills by freshtechbro (Apache 2.0): lottie-animations,
  rive-interactive, animejs, animated-component-libraries.
version: 1.0.0
---

# Design Animation Formats -- Lottie, Rive, Anime.js, Component Libraries

Four ways a "designer animation" or "animated component" reaches a web/React
app, condensed into one routing decision plus per-format patterns. This
skill does not teach any one library end-to-end -- it tells which format
fits the request, then hands off to the reference with the setup, the
snippets that matter, and the pitfalls everyone hits.

Based on claudedesignskills by freshtechbro (Apache 2.0).

## First Decision: What Kind of Animation Is This?

Answer in order:

1. **Is there an After Effects file (or a designer who exported one) and the
   animation just needs to play back faithfully, with no runtime branching
   logic?** -> `references/lottie.md`. Lottie is a JSON/dotLottie
   recording of an AE timeline -- it plays, seeks, and loops, but it does
   not have states or inputs.
2. **Does the animation need states, user-driven transitions, or two-way
   data binding** (hover/click/loading/toggle logic, a value from the app
   driving a property inside the animation)? -> `references/rive.md`. Rive
   is the only format here with a real state machine and a ViewModel data
   layer.
3. **Is there no designer file at all -- the animation is hand-authored in
   JS/CSS** (a timeline sequence, a staggered reveal, an SVG line-draw or
   morph)? -> `references/animejs.md`. Framework-agnostic, small, and the
   strongest option for SVG-heavy work outside of GSAP (which lives in
   `design-scroll`).
4. **Is the goal a common UI effect** (shimmer button, border beam, marquee,
   animated background, blur-text reveal, dock nav, count-up stat) **that
   already exists as a ready component**, rather than building the animation
   from scratch? -> `references/animated-component-libraries.md`. Check this
   first when the ask is "make this section pop" and the effect is generic --
   installing a component is faster and more consistent than hand-rolling
   the same shimmer/marquee/particle effect again.

A request can span two references (e.g. "animate this Rive button's
container on scroll" = rive.md for the button + design-scroll's GSAP
reference for the scroll trigger). Load both, in that order -- the
interactive/designer element before the choreography wrapping it.

## Decision Table -- Which Format for Which Job

| Need | Format | Reference |
|---|---|---|
| Play back an After Effects export faithfully (loading spinner, onboarding illustration, marketing animation) | Lottie | lottie.md |
| Animated icon/micro-interaction that must be pixel-perfect to the designer's AE file | Lottie | lottie.md |
| Button/toggle/loader with hover, click, or loading states driven by app logic | Rive | rive.md |
| Animation that needs live data pushed into it (a dashboard gauge, a stock ticker, a rating widget) | Rive (ViewModel) | rive.md |
| Hand-coded timeline with precise relative offsets (`-=500`, `+=200`) | Anime.js | animejs.md |
| Staggered grid/list reveal, SVG line-draw, SVG shape morph | Anime.js | animejs.md |
| Framework-agnostic animation (no React, or animating a JS object/canvas value directly) | Anime.js | animejs.md |
| Shimmer button, border beam, animated grid pattern, marquee -- shadcn/Tailwind stack | Magic UI | animated-component-libraries.md |
| Blur-text reveal, magnetic hover, macOS-style dock, WebGL particles/aurora/plasma background | React Bits | animated-component-libraries.md |

## Cross-Cutting Rules

- **Always clean up on unmount.** Lottie instances need `.destroy()`, Rive
  event listeners need `.off()`/`removeEventListener`, Anime.js animations
  need `.pause()` in the `useEffect` cleanup. All four sources hit this as
  their #1 pitfall independently -- treat any animation library instance
  like a subscription that must be torn down.
- **Respect `prefers-reduced-motion`.** None of these libraries disable
  motion by default. Gate autoplay/duration/stagger behind a media-query
  check, same rule as `unmassk-design`'s accessibility baseline.
- **Prefer transform/opacity over layout properties.** Anime.js and the
  component libraries both call this out: animating `left`/`width` forces
  layout; animating `translateX`/`scale`/`opacity` stays on the GPU
  compositor.
- **Don't blend formats for the same element.** Pick Lottie OR Rive for a
  given animated asset -- they solve different problems (playback vs.
  interactivity) and mixing them on one element usually means the AE
  animation should have been built in Rive from the start, not patched with
  both.

## Related unmassk-design Skills

- `design-scroll` -- GSAP, Locomotive Scroll, Barba: scroll-driven page
  choreography. Use it to trigger any of the four formats above on scroll
  (e.g. GSAP `ScrollTrigger.create({ onEnter: () => trigger.fire() })` to
  fire a Rive trigger, or scrubbing an Anime.js timeline's `.seek()`).
- `design-3d` -- Three.js/R3F/Babylon.js/Spline for actual 3D/WebGL scenes.
  React Bits' WebGL background components (Particles, Plasma, Aurora) are
  2D-effect-only and stay in this skill; a full 3D scene does not.
- `unmassk-design` (core) -- `references/motion.md` for general motion
  principles (easing, duration, reduced-motion) when no specific format has
  been chosen yet.

## Attribution

Condensed and rewritten in our own voice from **claudedesignskills** by
freshtechbro (Apache 2.0): `lottie-animations`, `rive-interactive`,
`animejs`, `animated-component-libraries`. Original sources are single-file
`SKILL.md` skills with full API references, scripts, and starter assets;
this branch condenses their actionable patterns and attributes rather than
reproducing them verbatim.
