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
  Use when NOT: the trigger is a hover/tap/load-time micro-interaction with
  no scroll driver, or a 3D/WebGL scene — out of scope here.
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

**Paths.** Every `scripts/…` path in this file is relative to this skill's own directory —
the absolute path printed as `Base directory for this skill:` when the skill loads.
`${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a command.

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

## Scripts

Scripts are tools, not optional helpers. Run them via Bash. Do not replicate
their logic manually. All scripts are stdlib-only Python 3 (no `pip install`
required) and organized one subfolder per library under `scripts/`.

| Script | What It Does | Usage |
|---|---|---|
| `scripts/barba-js/project_setup.py` | Scaffold a complete Barba.js + GSAP starter project (pages, CSS, Vite config, optional `npm install`) | `python3 scripts/barba-js/project_setup.py --name my-project --transition fade` (omit `--name` for interactive mode) |
| `scripts/barba-js/transition_generator.py` | Generate a single Barba.js transition block (fade, crossfade, slide, slide-vertical, scale, stagger, curtain, custom) | `python3 scripts/barba-js/transition_generator.py --type slide --sync --duration 0.6` (omit `--type` for interactive mode) |
| `scripts/gsap-scrolltrigger/generate_animation.py` | Generate boilerplate ScrollTrigger code (fade-in, pin, horizontal-scroll, timeline, image-sequence, and more) for vanilla/React/Vue | `python3 scripts/gsap-scrolltrigger/generate_animation.py --type fade-in --trigger ".box" --output code.js` |
| `scripts/gsap-scrolltrigger/timeline_builder.py` | Interactively build a multi-step GSAP timeline sequence, or load one from JSON | `python3 scripts/gsap-scrolltrigger/timeline_builder.py --output timeline.js` |
| `scripts/locomotive-scroll/generate_config.py` | Generate a Locomotive Scroll configuration from a named preset (basic, smooth, horizontal, performance, ...) | `python3 scripts/locomotive-scroll/generate_config.py --preset performance` (no args for interactive mode) |
| `scripts/locomotive-scroll/integration_helper.py` | Generate Locomotive Scroll + GSAP ScrollTrigger integration code (`scrollerProxy` wiring) for vanilla/React/Vue | `python3 scripts/locomotive-scroll/integration_helper.py --pattern fade-in --framework react` |
| `scripts/scroll-reveal-libraries/aos_generator.py` | Generate a ready-to-use HTML file with AOS scroll-reveal markup from a named template (hero, landing, ...) | `python3 scripts/scroll-reveal-libraries/aos_generator.py --template landing --output landing.html` |
| `scripts/scroll-reveal-libraries/config_builder.py` | Build an `AOS.init()` configuration from a preset or explicit flags (duration, once, offset, easing, ...) | `python3 scripts/scroll-reveal-libraries/config_builder.py --preset marketing` |

No dependency installation is required for any script above -- all use only
the Python 3 standard library. This differs from the core skill's
`search.py`, which needs `pip install -r requirements.txt`.

### Companion assets (`assets/<library>/`)

Each library subfolder under `assets/` mirrors its `scripts/<library>/`
sibling and holds static starter material referenced by that library's
scripts and reference file -- not loaded into context, copied into the
user's project on demand:

| Path | Contents |
|---|---|
| `assets/barba-js/README.md` | Manual setup guide and pointers to the two Barba.js scripts (the actual starter project is generated by `project_setup.py`, not a static template) |
| `assets/gsap-scrolltrigger/starter_scroll/` | Complete scroll-driven site template (`index.html`, `main.js`, `style.css`, `README.md`) |
| `assets/gsap-scrolltrigger/easings/easing_visualizer.html` | Standalone interactive easing-curve visualizer |
| `assets/gsap-scrolltrigger/examples/README.md` | Real-world ScrollTrigger pattern catalog (fade, pin, horizontal scroll, parallax, text, image reveals) |
| `assets/locomotive-scroll/starter_locomotive/` | Complete Locomotive Scroll starter (`index.html`, `main.js`, `style.css`, `package.json`, `README.md`) |
| `assets/scroll-reveal-libraries/README.md` | AOS framework-integration cookbook (vanilla, React, Next.js, Vue) and performance/accessibility patterns |
