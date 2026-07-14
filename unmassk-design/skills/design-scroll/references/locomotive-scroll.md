# Locomotive Scroll

Owns the *feel* of scrolling -- inertia, lerp smoothing, element-level
parallax speeds -- rather than being an animation-timeline tool. Reach for
this when the ask is "make scrolling feel smooth/premium" (Apple-style
landing pages), not "animate this specific element on scroll" (that's
ScrollTrigger, and the two are commonly paired).

Condensed from claudedesignskills' `locomotive-scroll` skill (Apache 2.0,
freshtechbro).

## Setup and required markup

Every element that participates needs `data-scroll` on a container marked
`data-scroll-container`:

```html
<div data-scroll-container>
  <div data-scroll-section>
    <h1 data-scroll>Basic detection</h1>
    <div data-scroll data-scroll-speed="2">Moves faster than scroll</div>
  </div>
</div>
```

```javascript
import LocomotiveScroll from "locomotive-scroll";
const scroll = new LocomotiveScroll({
  el: document.querySelector("[data-scroll-container]"),
  smooth: true,
  lerp: 0.1,       // lower = smoother/slower catch-up
  multiplier: 1,   // scroll speed multiplier
  smartphone: { smooth: false }, // disable on mobile by default -- performance
});
```

`data-scroll-section` is optional but improves performance by segmenting
long pages -- use it on real sites, skip it only for short/simple pages.

## Key data attributes

| Attribute | Purpose |
|---|---|
| `data-scroll-speed="N"` | Parallax intensity. `0-1` = slower than scroll, `>1` = faster, negative = reverse direction |
| `data-scroll-direction="horizontal"` | Parallax axis (default vertical) |
| `data-scroll-sticky` (+ `data-scroll-target`) | Pin within a section or a named target boundary |
| `data-scroll-offset="20%"` | Custom trigger point |
| `data-scroll-call="name"` | Fires a named JS callback on enter/exit -- read via `scroll.on('call', ...)` |
| `data-scroll-id="hero"` | Tag an element to read its live `.progress` (0-1) in the scroll event |
| `data-scroll-repeat` | Re-trigger detection every pass instead of once |

## Patterns worth remembering

**Parallax by speed** -- this is the library's signature move, purely declarative:
```html
<div data-scroll data-scroll-speed="0.5">Background, slow</div>
<div data-scroll data-scroll-speed="3">Foreground, fast</div>
<div data-scroll data-scroll-speed="-2">Reversed</div>
```

**Progress-driven JS** (when you need a number, not just CSS):
```javascript
scroll.on("scroll", (args) => {
  const hero = args.currentElements["hero"];
  if (hero) console.log(hero.progress); // 0 to 1
});
```

**Programmatic scroll**
```javascript
scroll.scrollTo("#section", { offset: -100, duration: 1000 });
```

**Respect `prefers-reduced-motion`** -- this is the one accessibility trap
specific to smooth-scroll libraries (they hijack native scroll):
```javascript
const reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
new LocomotiveScroll({ smooth: !reduced });
```

## Integration with GSAP ScrollTrigger

Locomotive owns the scroll container; ScrollTrigger needs to be told how to
read/write its position via `scrollerProxy`. This is the standard pairing
for "smooth scroll feel + precise scroll-driven animation":

```javascript
locoScroll.on("scroll", ScrollTrigger.update);
ScrollTrigger.scrollerProxy("[data-scroll-container]", {
  scrollTop(value) {
    return arguments.length
      ? locoScroll.scrollTo(value, { duration: 0, disableLerp: true })
      : locoScroll.scroll.instance.scroll.y;
  },
  getBoundingClientRect() { return { top: 0, left: 0, width: innerWidth, height: innerHeight }; },
  pinType: document.querySelector("[data-scroll-container]").style.transform ? "transform" : "fixed"
});
ScrollTrigger.addEventListener("refresh", () => locoScroll.update());
ScrollTrigger.refresh();
```
Every ScrollTrigger created after this must pass `scroller: "[data-scroll-container]"`
so it reads Locomotive's position instead of the native window scroll. See
`gsap-scrolltrigger.md` for the ScrollTrigger-side patterns.

## Pitfalls that actually bite

- **`position: fixed` breaks under smooth scroll** -- keep truly fixed
  elements (nav bars) *outside* `data-scroll-container`, or use
  `data-scroll-sticky` instead of CSS fixed for anything that must live
  inside the scrolled content.
- **Dynamic content doesn't reposition** -- call `scroll.update()` after any
  DOM change (content added, images loaded) or trigger points go stale.
- **Not destroying on route change (SPA)** -- `scroll.destroy()` in cleanup,
  otherwise duplicate instances accumulate and both fight over the scroll.
- **pinType mismatch with ScrollTrigger** -- if pinning looks broken when
  paired with ScrollTrigger, check `pinType` matches whether the container
  uses `transform` (smooth mode) or native `fixed`.
