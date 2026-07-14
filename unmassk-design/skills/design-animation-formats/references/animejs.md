# Anime.js -- Hand-Authored Timelines, Stagger, SVG Morphing

Source: `animejs` (claudedesignskills by freshtechbro, Apache 2.0).

## What it is

Anime.js is a small (~9KB gzipped), framework-agnostic JS animation engine
for DOM elements, CSS properties, SVG attributes, and plain JS objects.
Unlike Lottie/Rive, there is no designer file behind it -- the animation is
authored directly in code. Use it when the ask is a hand-coded timeline,
stagger effect, or SVG morph/line-draw, and GSAP (owned by `design-scroll`)
would be overkill or the project isn't scroll-driven.

**Use for:** timeline sequences with precise relative offsets, staggered
reveals across a list/grid, SVG path morphing and line-drawing, keyframe
animations, framework-agnostic animation (no React required).

## Core API

```javascript
import anime from 'animejs';

anime({
  targets: '.element',       // CSS selector, DOM node(s), array, or a JS object
  translateX: 250, rotate: '1turn', scale: 2,
  duration: 800, easing: 'easeInOutQuad',
});
```

Animatable targets: CSS selector/DOM nodes, individual CSS transform
properties (`translateX`, `rotate`, `scale` -- never the raw `transform`
string), SVG attributes (`d`, `fill`, `strokeDashoffset`), or a plain JS
object's properties (useful for driving a counter or a canvas value via
`update`).

## Timeline (relative sequencing)

```javascript
const tl = anime.timeline({ duration: 750, easing: 'easeOutExpo' });
tl.add({ targets: '.title', translateY: [-50, 0], opacity: [0, 1] })
  .add({ targets: '.subtitle', translateY: [-30, 0], opacity: [0, 1] }, '-=500') // starts 500ms before previous ends
  .add({ targets: '.button', scale: [0, 1], opacity: [0, 1] }, '-=300');
```

`-=N` / `+=N` are relative to the *previous* animation's end -- a bare
`'500'` is treated as an absolute time, which is almost never what's wanted.

## Stagger

```javascript
anime({
  targets: '.grid-item', scale: [0, 1],
  delay: anime.stagger(50, { grid: [14, 5], from: 'center', axis: 'x' }),
  // from: 'first' | 'last' | 'center' | index | [x, y]
});
```

## SVG morphing and line-drawing

```javascript
// Line-draw
anime({ targets: 'path', strokeDashoffset: [anime.setDashoffset, 0],
        duration: 2000, delay: (el, i) => i * 250 });

// Shape morph (path 'd' must have the same point count on both ends)
anime({ targets: '#morphing-path',
        d: [{ value: 'M10 80 Q 77.5 10, 145 80' }, { value: 'M10 80 Q 77.5 150, 145 80' }],
        duration: 2000, loop: true, direction: 'alternate' });
```

## Keyframes and easing

```javascript
anime({ targets: '.element',
        keyframes: [{ translateX: 100 }, { translateY: 100 }, { translateX: 0 }, { translateY: 0 }],
        duration: 4000, loop: true });

// Easing options: 'easeInOutQuad', 'spring(mass, stiffness, damping, velocity)',
// 'steps(n)', 'cubicBezier(x1, y1, x2, y2)'
```

## Playback control

```javascript
const animation = anime({ targets: '.el', translateX: 250, autoplay: false });
animation.play(); animation.pause(); animation.reverse(); animation.seek(500);
```

## React integration

```jsx
useEffect(() => {
  const animation = anime({ targets: ref.current, translateX: 250, duration: 800 });
  return () => animation.pause(); // MUST clean up, same rule as Lottie/Rive
}, []);
```

## Pitfalls

- **Missing unit on non-transform CSS properties.** `width: 200` is
  invalid -- use `width: '200px'`. Transform properties (`translateX`,
  `scale`) don't need this.
- **Animating the raw `transform` string.** `transform: 'translateX(250px)'`
  does not animate -- use the individual property `translateX: 250`.
  instead.
- **No cleanup on unmount.** Always store the returned animation instance
  and call `.pause()` in the effect's cleanup.
- **Animating 1000+ elements with one `anime()` call.** Falls back to CSS
  `@keyframes` for very large element counts -- JS-driven animation doesn't
  scale the same way.
- **Missing relative-offset operator in timelines.** `.add({...}, '500')` is
  absolute time, not "500ms relative to the previous step" -- use `'-=500'`
  / `'+=500'`.
- **Infinite `loop: true` for simple rotations.** Prefer a CSS `@keyframes`
  animation for indefinite loops -- cheaper than a running JS engine.

## Anime.js vs. GSAP vs. Framer Motion

- **vs. GSAP** (owned by `design-scroll`): choose Anime.js for SVG-heavy
  work, smaller bundle size, or projects without a scroll-choreography need.
  GSAP wins for complex scroll-driven sequences and ScrollTrigger-class
  control.
- **vs. Framer Motion**: Anime.js is framework-agnostic (vanilla JS, Vue,
  React all work the same way); Framer Motion is React-specific with
  built-in gesture support -- pick it when the project is already React and
  wants declarative `motion.div` components instead of imperative calls.

## Related

`design-scroll` for GSAP-driven scroll choreography.
`animated-component-libraries.md` for pre-built components (Magic UI is
built on Framer Motion, not Anime.js) when the effect is generic enough to
not need hand-authoring at all.
