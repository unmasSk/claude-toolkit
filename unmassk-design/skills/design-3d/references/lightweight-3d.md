# Lightweight & Decorative 3D -- Zdog, Vanta.js, Vanilla-Tilt, Spline, PixiJS

Sources: `lightweight-3d-effects/` (Zdog, Vanta.js, Vanilla-Tilt),
`spline-interactive/`, `pixijs-2d/` (claudedesignskills, Apache 2.0).

Common thread: none of these are for a full interactive 3D scene with
camera control and physics — they're for a decorative element, a
micro-interaction, a no-code visual scene, or accelerated 2D. If the request
needs a real navigable 3D scene, use `references/web-3d-engines.md` instead.

## Zdog -- pseudo-3D vector illustrations

What it is: a designer-friendly pseudo-3D engine (Canvas or SVG) for flat,
round illustrations that rotate in 3D space. ~28kb.

When to use it: a small hand-drawn-feeling 3D icon or illustration, not a
scene — logos, mascots, decorative shapes with drag-to-rotate.

```javascript
let illo = new Zdog.Illustration({ element: '.zdog-canvas', zoom: 4, dragRotate: true });
new Zdog.Ellipse({ addTo: illo, diameter: 20, translate: { z: 10 }, stroke: 5, color: '#636' });
function animate() {
  illo.rotate.y += 0.03;
  illo.updateRenderGraph(); // required after any shape/property change
  requestAnimationFrame(animate);
}
animate();
```
Group shapes with `Zdog.Group` to build composite models (e.g., a face from
ellipses + a bezier mouth) and rotate the group as one unit. Keep total
shape count under ~100 for smooth 60fps. Pitfall: blank canvas almost always
means a forgotten `updateRenderGraph()` call or a canvas with 0 dimensions.

## Vanta.js -- animated WebGL backgrounds

What it is: turnkey animated backgrounds (Waves, Clouds, Birds, Net, Cells,
Fog, and more) built on Three.js or p5.js. ~120KB total.

When to use it: a hero section or full-bleed background that needs ambient
motion with near-zero setup — not when the background itself needs to be
interactive content.

```javascript
VANTA.WAVES({ el: "#hero", mouseControls: true, touchControls: true,
  color: 0x23153c, waveHeight: 15, waveSpeed: 0.75 });
```

Key rules:
- **Colors are hex numbers, not strings** (`0x23153c`, not `"#23153c"`) —
  the most common "colors don't work" bug.
- **Use only 1-2 instances per page** — multiple simultaneous Vanta effects
  tank performance; lazy-load with `IntersectionObserver` if a page has
  several candidate sections.
- **Always `.destroy()` on unmount** in SPAs/React — it doesn't clean up
  itself.
- Consider a static gradient fallback on mobile instead of running the
  effect at all.

## Vanilla-Tilt.js -- parallax tilt on hover

What it is: ~8.5kb, no-dependency tilt effect that responds to mouse
movement (and gyroscope on mobile) for cards/images.

When to use it: a card-hover or product-image tilt effect — nothing more.

```html
<div class="tilt-card" data-tilt data-tilt-glare data-tilt-max-glare="0.5">...</div>
<script src=".../vanilla-tilt.min.js"></script>
```
Or programmatically: `VanillaTilt.init(el, { max: 25, glare: true, "max-glare": 0.5, gyroscope: true })`.
For a layered depth look, combine with CSS `transform-style: preserve-3d`
and `translateZ()` on inner elements so they separate as the card tilts.
Always call `.destroy()` on unmount in SPAs. Enable `gyroscope: true` for
the effect to do anything on mobile (mouse-only otherwise).

## Spline -- no-code 3D design tool

What it is: a browser-based visual 3D editor (parametric shapes, state-based
animation, event-driven interactions) that exports to React components,
vanilla JS, or glTF.

When to use it: a designer is building the 3D scene visually and handing it
to engineering as an embed — not when the scene needs to be authored in
code from scratch (use `web-3d-engines.md` for that, or export Spline's
glTF into Three.js/Babylon.js for further coding).

```jsx
import Spline from '@splinetool/react-spline';
<Spline scene="https://prod.spline.design/SCENE-ID/scene.splinecode" onLoad={onLoad} />
```
Key patterns:
- **Object control from React**: `onLoad(spline)` gives
  `spline.findObjectByName('X')` — store the returned object in a `useRef`
  (not a plain variable, which is lost on re-render) to mutate
  `position`/`rotation`/`scale`/`material.color` later.
- **Trigger scene animations from code**: `spline.emitEvent('mouseHover', 'ObjectName')`
  (and `emitEventReverse` to play back). Only call after the scene has
  actually loaded (guard with a loaded flag).
- **Next.js**: import from `@splinetool/react-spline/next` (SSR placeholder,
  avoids hydration mismatch) rather than the base package.
- **Performance**: `renderOnDemand` (default true) avoids rendering every
  frame; author a separate lower-poly mobile scene rather than scaling one
  scene down at runtime.

## PixiJS -- accelerated 2D, not 3D

What it is: a 2D WebGL/WebGPU renderer. Included in this family because it's
the answer to "2D but needs WebGL performance" — particle systems, sprite
sheets, HUD/UI overlaid on a 3D canvas, thousands of interactive sprites.
**Not for 3D** — use `web-3d-engines.md` if the request needs depth/a camera.

```javascript
const app = new Application();
await app.init({ width: 800, height: 600, backgroundColor: 0x1099bb });
document.body.appendChild(app.canvas);
const sprite = new Sprite(await Assets.load('bunny.png'));
app.stage.addChild(sprite);
```
Key patterns:
- **ParticleContainer**, not a regular `Container`, for anything above a
  few hundred sprites — up to 10x faster because it skips per-child
  transform/style diffing for properties marked static.
  Enable dynamic properties (`position`/`scale`/`rotation`/`color`) only for
  what actually changes per frame.
- **BitmapText over Text** for frequently-updated text (scores, counters) —
  `Text` re-renders its texture on every change, `BitmapText` doesn't.
- **Filters are expensive**: 1-2 max per sprite, always set `filterArea`
  to avoid runtime bounds measurement.
- **2D overlay on a 3D canvas**: a second, transparent (`backgroundAlpha: 0`)
  PixiJS canvas positioned absolutely with `pointerEvents: 'none'`, rendered
  in the same rAF loop as the 3D scene.
- Always `Assets.load()` (awaited) before constructing a `Sprite`, not
  `Sprite.from(url)`, to avoid async/render-order races.
- Destroy everything (`sprite.destroy({ children: true, texture: true })`)
  — GPU-side leaks are silent until the tab crashes.

## Related

`references/web-3d-engines.md` for full 3D scenes. `design-scroll` for
scroll-triggering any of these effects.
