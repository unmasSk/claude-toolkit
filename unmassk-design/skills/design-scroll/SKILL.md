---
name: design-scroll
description: >
  Use when the user asks to "add scroll animations", "make it scroll-driven",
  "pin this section", "scrub an animation to scroll", "add parallax",
  "smooth scroll", "page transitions", "animate on scroll", "reveal on
  scroll", "fade in as you scroll", or mentions any of: scroll-driven
  animation, ScrollTrigger, pinning, scrubbing, parallax, smooth scrolling,
  Locomotive Scroll, page transitions, Barba.js, scroll reveal, AOS,
  Animate On Scroll, horizontal scroll, scrollytelling, sticky sections,
  scroll progress indicator, image sequence scrubbing.
  Covers the family of scroll-driven web libraries and picks the right one
  for the job: GSAP ScrollTrigger for complex pinning/scrubbing/timelines,
  Locomotive Scroll for smooth-scroll + parallax feel, Barba.js for
  SPA-like page transitions on multi-page sites, and AOS for simple
  fade/slide/zoom reveals with zero JavaScript orchestration. Routes to
  condensed per-library references with decision guidance, key patterns,
  and integration snippets.
  Use when NOT: the user wants a general animation (hover states, button
  micro-interactions, load-time animation with no scroll trigger) that
  belongs to `motion.md` in unmassk-design, not this skill; or wants 3D/WebGL
  scene work (Three.js, React Three Fiber), which is a separate concern.
  Based on the community skill pack claudedesignskills by freshtechbro
  (Apache 2.0): gsap-scrolltrigger, locomotive-scroll, barba-js, and
  scroll-reveal-libraries (AOS).
version: 1.0.0
---

# Design Scroll -- Scroll-Driven Animation Family

Four libraries, one job: make the page react to scroll. This skill exists so
we don't reach for GSAP's full API when AOS's `data-aos="fade-up"` would do,
and don't reach for AOS when the ask is a pinned, scrubbed, multi-step
scrollytelling sequence.

Based on the community skill pack **claudedesignskills** by freshtechbro
(Apache 2.0) -- specifically its `gsap-scrolltrigger`, `locomotive-scroll`,
`barba-js`, and `scroll-reveal-libraries` skills. Content here is condensed
and rewritten from those sources, not copied verbatim.

## Decision Table -- which library for which case

| The ask | Library | Why | Reference |
|---|---|---|---|
| Pin a section while scrolling, scrub a timeline to scroll position, horizontal scroll sections, image-sequence scrubbing, complex multi-step scrollytelling | **GSAP ScrollTrigger** | Only one here with real pinning + scrubbing + timeline control. Most powerful, most API surface. | `references/gsap-scrolltrigger.md` |
| "Make scrolling feel smooth", buttery inertia scroll, element-level parallax speeds via data attributes, Apple-style landing pages | **Locomotive Scroll** | Owns the *feel* of scrolling itself (lerp/inertia), not just what animates. Commonly paired with ScrollTrigger for the animation layer on top. | `references/locomotive-scroll.md` |
| Multi-page (MPA) site should feel like an SPA: no full reload between pages, animated route changes | **Barba.js** | The only one of the four solving *page-to-page* navigation, not in-page scroll. Orthogonal to the other three -- pairs with any of them for the transition animations themselves. | `references/barba-js.md` |
| Simple fade/slide/zoom-in-as-you-scroll on marketing/landing/content pages, no orchestration needed | **AOS (scroll reveal)** | Data-attribute only, no JS timeline to write. Lightest of the four (~13KB). Reach for this first if the ask is "just make things appear as I scroll." | `references/aos-scroll-reveal.md` |

**Escalation rule**: start with AOS. Move to GSAP ScrollTrigger only when the
ask needs something AOS's data attributes can't express: pinning, scrubbing
tied to exact scroll progress, or sequencing across multiple elements with
precise timing. Reach for Locomotive Scroll when the *scrolling itself*
needs to feel different (inertia/lerp), independent of what's animating.
Reach for Barba.js only when the site is multi-page and navigation itself
should transition -- it says nothing about in-page scroll.

These libraries **combine**: Locomotive Scroll commonly drives ScrollTrigger
(via `scrollerProxy`), and Barba.js transitions commonly use GSAP tweens for
the leave/enter animations. See each reference's integration section.

## Common ground across all four

- **GPU-accelerated properties only** (`transform`, `opacity`) for anything
  scroll-synced. Animating `width`/`height`/`top`/`left` causes reflow and
  will visibly stutter under scroll, which is the one failure mode that
  reads as "broken" to a user.
- **`prefers-reduced-motion` must be respected.** Every one of these
  libraries can be disabled or short-circuited for users who ask for
  reduced motion -- check the reference for the specific flag/disable
  option before shipping scroll-driven motion as the primary way content
  appears.
- **Refresh after DOM/layout changes.** Every library caches element
  positions at init. Images loading late, fonts swapping, or content
  injected after init will desync trigger points unless the library's
  refresh/update method is called afterward (`ScrollTrigger.refresh()`,
  `scroll.update()`, `AOS.refresh()`).
- **Clean up on unmount** in SPA/component contexts (React, Vue): kill
  ScrollTrigger instances, destroy the Locomotive Scroll instance, kill
  ScrollTriggers in Barba's `beforeLeave`. Leaving these alive across route
  changes is the most common source of duplicated or ghost animations.

## Routing

Load only the reference the case needs -- do not load all four for a
single-library ask.

| Reference | Load when |
|---|---|
| `references/gsap-scrolltrigger.md` | Pinning, scrubbing, horizontal scroll, timelines, image sequences, or the request explicitly says GSAP/ScrollTrigger |
| `references/locomotive-scroll.md` | Smooth/inertia scroll, data-attribute parallax, or pairing smooth scroll with ScrollTrigger |
| `references/barba-js.md` | Page transitions, SPA-like navigation on a traditional multi-page site |
| `references/aos-scroll-reveal.md` | Simple scroll reveals, marketing pages, no orchestration needed |
