# AOS -- Animate On Scroll

The simplest of the four: CSS-driven fade/slide/zoom/flip reveals via a
single `data-aos` attribute, no JavaScript timeline to write. This is the
default starting point for "make things appear as I scroll" -- escalate to
GSAP ScrollTrigger only when the ask needs pinning, scrubbing, or precise
multi-element sequencing that a data attribute can't express.

Condensed from claudedesignskills' `scroll-reveal-libraries` skill (Apache
2.0, freshtechbro).

## Setup

```javascript
import AOS from "aos";
import "aos/dist/aos.css";
AOS.init({ duration: 800, once: true, offset: 120 });
```

`once: true` matters for performance -- without it, elements re-animate
every time they cross the trigger point in either direction.

## Usage

```html
<h1 data-aos="fade-down">Heading</h1>
<p data-aos="fade-up" data-aos-delay="200">Subtext</p>
<button data-aos="zoom-in" data-aos-delay="400">CTA</button>
```

Every global option (`duration`, `delay`, `easing`, `offset`, `once`,
`mirror`, `anchor-placement`) can be overridden per element with a matching
`data-aos-*` attribute.

## Animation catalog (28 built-ins, by performance tier)

| Tier | Animations | Notes |
|---|---|---|
| Cheapest (opacity only) | `fade-in`, `fade-up/down/left/right`, 4 diagonal variants | Default choice for most content |
| Cheap (transform only) | `slide-up/down/left/right`, `zoom-in/out` + 8 directional zoom variants | Use for featured content, CTAs |
| Costliest (3D transform) | `flip-up/down/left/right` | CPU-heavier -- use sparingly, key elements only |

## Staggering -- the one pattern that does the heavy lifting

```html
<div data-aos="fade-up" data-aos-delay="0">Item 1</div>
<div data-aos="fade-up" data-aos-delay="100">Item 2</div>
<div data-aos="fade-up" data-aos-delay="200">Item 3</div>
```
50-150ms increments between items reads as a deliberate sequence rather than
simultaneous pop-in.

## Selection guide by content type

| Content | Animation |
|---|---|
| Hero heading | `fade-down` |
| Hero subtext / body copy | `fade-up` |
| CTA button | `zoom-in` |
| Feature card grid | `fade-up`, staggered |
| Image gallery | `zoom-in-up` |
| Timeline items | `slide-left` / `slide-right` |

## Accessibility -- non-negotiable given how this project treats motion

```javascript
AOS.init({
  disable: () => matchMedia("(prefers-reduced-motion: reduce)").matches
});
```
`disable` also accepts `'mobile'`/`'phone'`/`'tablet'` string shortcuts if
the concern is performance rather than user preference specifically.

## Framework integration (React)

```jsx
useEffect(() => { AOS.init({ duration: 800, once: true }); }, []);
useEffect(() => { AOS.refresh(); }, [location.pathname]); // re-scan on route change
```
`AOS.refresh()` recalculates trigger positions for existing elements;
`AOS.refreshHard()` re-scans the DOM for new elements entirely (needed after
dynamically injected content, e.g. an infinite-scroll list appending items).

## Pitfalls that actually bite

- **Forgetting to refresh after dynamic DOM changes** -- newly injected
  elements with `data-aos` won't animate until `AOS.refresh()` runs.
- **Not respecting reduced motion** -- covered above; this is the
  accessibility gap unique to this library since it's the "just ship it"
  option and easy to skip the disable check.
- **Duration/delay values above 3000ms silently don't work** -- AOS caps
  there; anything longer needs custom CSS transition durations.
- **Reaching for `flip-*` by default** -- it's the most CPU-intensive tier;
  default to `fade-*`/`zoom-*` and reserve flip for a small number of
  deliberately showcased elements.

## When to stop using AOS and escalate to GSAP ScrollTrigger

The moment the ask becomes "sync exactly to scroll position" (scrubbing),
"keep this pinned while other content scrolls past," or "sequence 5+
elements with precise relative timing" -- AOS's data-attribute model can't
express that. Move to `gsap-scrolltrigger.md`.
