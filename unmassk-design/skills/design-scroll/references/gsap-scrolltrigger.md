# GSAP ScrollTrigger

The most powerful of the four -- full timeline control, pinning, scrubbing,
and arbitrary scroll-position math. Reach for this when AOS-style "fade in
when visible" isn't enough: pinned sections, horizontal scroll, image
sequences, or anything that must track scroll progress precisely rather than
just react to a threshold.

Condensed from claudedesignskills' `gsap-scrolltrigger` skill (Apache 2.0,
freshtechbro).

## Setup

```javascript
import gsap from "gsap";
import { ScrollTrigger } from "gsap/ScrollTrigger";
gsap.registerPlugin(ScrollTrigger); // forgetting this is the #1 "it does nothing" bug
```

## Core mental model

- `gsap.to/from/fromTo(target, {...})` -- a tween. `scrollTrigger` is just
  another option inside the vars object.
- `start`/`end` use the format `"[trigger position] [viewport position]"`:
  `"top center"` = trigger's top hits viewport's center. `"top 80%"` = 80%
  down the viewport. Offsets: `"top top+=100"`.
- `scrub: true` links progress directly to the scrollbar (no easing lag);
  `scrub: 1` adds a 1s catch-up smoothing -- almost always what you want for
  a natural feel over `scrub: true`.
- `pin: true` fixes the trigger element in place for the duration of
  `start`→`end`, letting content underneath continue scrolling past it.
- `toggleActions: "play none none reverse"` controls the 4 scroll-direction
  events (`onEnter onLeave onEnterBack onLeaveBack`); actions are
  `play/pause/resume/restart/reverse/reset/complete/none`.

## Patterns worth remembering

**Fade in on scroll (scrubbed)**
```javascript
gsap.from(".fade-in", {
  opacity: 0, y: 50,
  scrollTrigger: { trigger: ".fade-in", start: "top 80%", scrub: 1 }
});
```

**Pin a section**
```javascript
ScrollTrigger.create({
  trigger: ".panel", start: "top top", end: "+=500", pin: true
});
```

**Horizontal scroll section** (a full track, not a single tween)
```javascript
const sections = gsap.utils.toArray(".panel");
gsap.to(sections, {
  xPercent: -100 * (sections.length - 1),
  ease: "none",
  scrollTrigger: {
    trigger: ".container", pin: true, scrub: 1,
    end: () => "+=" + document.querySelector(".container").offsetWidth
  }
});
```

**Parallax (background slower, foreground faster)**
```javascript
gsap.to(".bg", { y: 200, ease: "none",
  scrollTrigger: { trigger: ".section", start: "top bottom", end: "bottom top", scrub: true } });
gsap.to(".fg", { y: -100, ease: "none",
  scrollTrigger: { trigger: ".section", start: "top bottom", end: "bottom top", scrub: true } });
```

**Batch stagger for many elements** (cheaper than one ScrollTrigger per item)
```javascript
ScrollTrigger.batch(".box", {
  onEnter: batch => gsap.to(batch, { opacity: 1, y: 0, stagger: 0.15 }),
  start: "top 80%", once: true
});
```

**Scrubbed timeline with pin + snap** -- the scrollytelling pattern
```javascript
gsap.timeline({
  scrollTrigger: { trigger: ".container", start: "top top", end: "+=1500", scrub: 1, pin: true,
    snap: { snapTo: "labels", duration: { min: 0.2, max: 3 } } }
})
  .addLabel("start").from(".title", { scale: 0.3, autoAlpha: 0 })
  .addLabel("reveal").to(".box", { rotation: 360 });
```

**Image-sequence scrubbing** (canvas frame-by-frame tied to scroll) -- see
the source skill's `common_patterns.md` §12 for the full render loop; the
shape is: preload N frames into an array, animate a plain `{frame: 0}`
object's value with `snap: "value"` inside a pinned ScrollTrigger, redraw
the canvas `onUpdate`.

## Easing -- the one rule that matters

`ease: "none"` for anything with `scrub` (the user controls speed via
scroll, so easing fights them). For non-scrubbed entrance/exit animations:
`power2.out` covers ~80% of cases; reach for `power3.out`/`power4.out` for
hero-scale drama, `back.out(1.7)` for playful, and never use elastic/bounce
outside explicitly playful contexts.

## Integration

**Locomotive Scroll as the scroller** -- ScrollTrigger needs a
`scrollerProxy` when Locomotive owns the actual scroll container:
```javascript
ScrollTrigger.scrollerProxy("[data-scroll-container]", {
  scrollTop(value) {
    return arguments.length ? scroller.scrollTo(value, 0, 0) : scroller.scroll.instance.scroll.y;
  },
  getBoundingClientRect() { return { top: 0, left: 0, width: innerWidth, height: innerHeight }; },
  pinType: document.querySelector("[data-scroll-container]").style.transform ? "transform" : "fixed"
});
ScrollTrigger.addEventListener("refresh", () => scroller.update());
ScrollTrigger.refresh();
```
See `locomotive-scroll.md` for the Locomotive side of this pairing.

**React (`useGSAP` from `@gsap/react`)** -- scope animations to a container
ref so cleanup is automatic on unmount:
```javascript
useGSAP(() => {
  gsap.to(box.current, { x: 200, scrollTrigger: { trigger: box.current, scrub: true } });
}, { scope: container });
```

## Pitfalls that actually bite

- **Forgetting `gsap.registerPlugin(ScrollTrigger)`** -- silent no-op, not an error.
- **Two tweens on the same property of the same element** -- second one
  jumps instead of blending. Fix: `fromTo()`, or `immediateRender: false`,
  or put both tweens on one timeline with one ScrollTrigger.
- **ScrollTrigger on individual tweens inside a timeline** -- put the
  ScrollTrigger on the parent timeline, not on each `.to()` call inside it.
- **Not refreshing after layout shifts** (images loading, fonts swapping) --
  call `ScrollTrigger.refresh()` on `window.load` or after `imagesLoaded`.
- **Never killing triggers on unmount** -- `ScrollTrigger.getAll().forEach(t => t.kill())`
  or return a cleanup function in the framework's effect/hook.
