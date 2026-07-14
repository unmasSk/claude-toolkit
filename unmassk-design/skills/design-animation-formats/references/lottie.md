# Lottie -- After Effects Animation for Web/React

Source: `lottie-animations` (claudedesignskills by freshtechbro, Apache 2.0).

## What it is

Lottie renders After Effects animations at runtime instead of shipping a
GIF/video. A designer builds the animation in AE, exports it with the
Bodymovin plugin as JSON (or the newer compressed `.lottie` container), and
the app plays that file natively. It is vector-based, small, and editable at
runtime (colors, speed, segments) -- but it has no state machine: it plays,
seeks, and loops a fixed timeline, nothing more.

**Use for:** onboarding/loading animations, animated icons and
micro-interactions, marketing/promo animations -- anywhere the designer's AE
timeline should play back faithfully with no interactive branching logic.
If the animation needs states or input-driven logic, that's Rive
(`references/rive.md`), not Lottie.

## Format choice

- **`.json`** -- original format, human-readable, uncompressed, universally
  supported.
- **`.lottie`** (dotLottie) -- a zip container (JSON + assets, can bundle
  multiple animations/themes), up to 90% smaller. Default to this for
  production.

## Libraries

```bash
npm install @lottiefiles/dotlottie-react   # React, recommended
npm install @lottiefiles/dotlottie-web     # vanilla JS, recommended
npm install lottie-react                   # React, needed for the
                                            # interactivity/hover helpers below
```

```jsx
// React, dotLottie (recommended default)
import { DotLottieReact } from '@lottiefiles/dotlottie-react';

<DotLottieReact src="animation.lottie" loop autoplay style={{ height: 300 }} />
```

```jsx
// lottie-react -- needed for scroll/hover interactivity helpers
import Lottie from 'lottie-react';
import animationData from './animation.json';

<Lottie animationData={animationData} loop />
```

## Interactivity patterns (no state machine, but still useful)

```jsx
// Scroll-driven playback with lottie-react's interactivity prop
const interactivity = {
  mode: 'scroll',
  actions: [
    { visibility: [0, 0.2], type: 'stop', frames: [0] },
    { visibility: [0.2, 0.45], type: 'seek', frames: [0, 45] },
    { visibility: [0.45, 1.0], type: 'loop', frames: [45, 60] },
  ],
};
<Lottie animationData={anim} interactivity={interactivity} />
```

```jsx
// GSAP-driven frame scrubbing (pairs with design-scroll's ScrollTrigger)
gsap.to(lottieRef.current, {
  scrollTrigger: { trigger: '#section', start: 'top center', end: 'bottom center', scrub: 1 },
  onUpdate: (self) => {
    const frame = Math.floor(self.progress * (anim.totalFrames - 1));
    anim.goToAndStop(frame, true);
  },
});
```

Controls available on any loaded instance: `.play()` / `.pause()` /
`.stop()` / `.setFrame(n)` / `.destroy()`.

## Pitfalls

- **Memory leak from not calling `.destroy()`.** Always destroy the
  instance in the `useEffect` cleanup (or the component's unmount hook) --
  the animation keeps rendering after the component is gone otherwise.
- **Event listeners not removed.** Same shape as any event emitter: mirror
  every `addEventListener` with a `removeEventListener` in cleanup.
- **Oversized JSON exports (500KB+).** In After Effects: enable "skip
  images that aren't used," simplify paths, avoid particle/noise effects,
  prefer shape layers. Then export as `.lottie` for automatic compression.
- **Unsupported AE features.** Layer effects (drop shadow, glow), 3D
  layers, most blending modes, and expressions do not export cleanly to
  Lottie -- convert to shapes before export, and preview in LottieFiles
  before shipping.
- **CORS/path issues.** Prefer bundling the file (`animationData` import)
  over a remote `src` URL when the app controls the asset; remote URLs need
  CORS headers.

## Performance

- Prefer `.lottie` over raw `.json` for file size.
- Lazy-load off-screen animations with an `IntersectionObserver`.
- For heavy animations, use a Canvas renderer (not SVG) or offload to
  `DotLottieWorker` (a Web Worker).
- Reduce `devicePixelRatio` on mobile.

## Related

`rive-interactive` (this family's `rive.md`) for the same "designer
animation" problem when it needs states/logic. `design-scroll`'s GSAP
reference for scroll-scrubbed playback. `animated-component-libraries.md`
for pre-built components that may already wrap a Lottie animation
internally.
