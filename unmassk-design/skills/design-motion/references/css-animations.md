# CSS Animation Techniques

Pure-CSS craft techniques beyond the core's duration/easing/reduced-motion basics (`skills/unmassk-design/references/motion.md`). These are the tools that let CSS do what people reach for JavaScript for — reveals, masks, choreographed multi-element layouts, and interruptible entrances — without a library.

## Transform mastery

**Percentage `translate` is relative to the element's own size.** `translateY(100%)` moves an element by its own height regardless of actual dimensions — this is how Sonner positions toasts and Vaul hides a drawer before animating it in. Prefer percentages over hardcoded pixel values; they adapt to content and don't need remeasuring.

```css
.drawer-hidden { transform: translateY(100%); }   /* works regardless of drawer height */
.toast-enter   { transform: translateY(-100%); }  /* works regardless of toast height */
```

**`scale()` scales children too** — unlike `width`/`height`. Scaling a button on `:active` proportionally scales its font, icon, and content. This is a feature, not a bug: it's why press-feedback scale reads as one cohesive object shrinking, not a container shrinking around static content.

**3D transforms for real depth.** `rotateX()`/`rotateY()` with `transform-style: preserve-3d` create orbiting, coin-flip, and depth effects without JS:

```css
.wrapper { transform-style: preserve-3d; }

@keyframes orbit {
  from { transform: translate(-50%, -50%) rotateY(0deg) translateZ(72px) rotateY(360deg); }
  to   { transform: translate(-50%, -50%) rotateY(360deg) translateZ(72px) rotateY(0deg); }
}
```

**`transform-origin`** is the anchor a scale/rotation executes from — default is center. Set it explicitly whenever an element should scale from its trigger rather than its own center (see origin-aware popovers in `craft-principles.md` §2).

## clip-path — an animation tool, not just a shape tool

`clip-path: inset(top right bottom left)` defines a rectangular clip region; each value "eats" into the element from that side. It composites on the GPU and is one of the most versatile animation primitives in CSS.

```css
.hidden  { clip-path: inset(0 100% 0 0); }  /* fully hidden from the right */
.visible { clip-path: inset(0 0 0 0); }     /* fully visible */

.overlay { clip-path: inset(0 100% 0 0); transition: clip-path 200ms ease-out; }
.button:active .overlay { clip-path: inset(0 0 0 0); transition: clip-path 2s linear; }
```

**Concrete uses:**
- **Seamless tab color transitions.** Duplicate the tab list; style the copy as "active" (different bg/text color); clip the copy so only the active tab shows; animate the clip on tab change. This produces a color transition that timing individual `color`/`background-color` properties can never match — one shape sweeping across, not two colors crossfading.
- **Hold-to-delete.** A colored overlay at `inset(0 100% 0 0)`; on `:active`, transition to `inset(0 0 0 0)` over `2s linear` (deliberate, slow — the user is deciding); on release, snap back at `200ms ease-out` (fast — the system responding). Pair with `scale(0.97)` on the button for press feedback. See the asymmetric-timing rule in `craft-principles.md` §2.
- **Image reveals on scroll.** Start `inset(0 0 100% 0)` (hidden from bottom), animate to `inset(0 0 0 0)` when the element enters the viewport — via `IntersectionObserver` or `whileInView`/`useInView` (`react-libraries.md`).
- **Before/after comparison sliders.** Overlay two images; clip the top one with `clip-path: inset(0 50% 0 0)`; adjust the right-inset value on drag. No extra DOM elements, fully hardware-accelerated.

## `@starting-style` — CSS-native entrance animation

The modern way to animate an element's entry without a `useEffect`-driven "mounted" flag:

```css
.toast {
  opacity: 1;
  transform: translateY(0);
  transition: opacity 400ms ease, transform 400ms ease;

  @starting-style {
    opacity: 0;
    transform: translateY(100%);
  }
}
```

Use it when browser support allows; fall back to a `data-mounted` attribute set after mount otherwise:

```jsx
useEffect(() => { setMounted(true); }, []);
// <div data-mounted={mounted}>
```

## Web Animations API (WAAPI) — JS control, CSS performance

Gives imperative JavaScript control with hardware-accelerated, interruptible, no-library CSS-grade performance — the middle ground between a static CSS transition and a full animation library:

```js
element.animate(
  [{ clipPath: 'inset(0 0 100% 0)' }, { clipPath: 'inset(0 0 0 0)' }],
  { duration: 1000, fill: 'forwards', easing: 'cubic-bezier(0.77, 0, 0.175, 1)' }
);
```

## The CSS-variable performance trap

Changing a CSS custom property on a **parent** recalculates styles for **every child** that references it — a real cost in a drawer or list with many items:

```js
// Bad — triggers a style recalc on every child that reads --swipe-amount
element.style.setProperty('--swipe-amount', `${distance}px`);

// Good — only this element is affected
element.style.transform = `translateY(${distance}px)`;
```

Set `transform` directly on the element being dragged/animated; reserve CSS variables for values that genuinely need to cascade (a theme token, not a per-frame drag offset).

## Trigonometric positioning for choreographed circular layouts

When a design places N elements evenly around a circle (an orbiting avatar ring, a radial menu), never eyeball pixel positions — calculate them:

```
left = centerX + R * cos(angle_radians) - (elementWidth / 2)
top  = centerY + R * sin(angle_radians) - (elementHeight / 2)
```
where `R` is the container's visible radius plus half the element's size (so the element's inner edge touches the container perimeter), and for N items evenly spaced: `angle_i = startAngle + i * (2π / N)`, conventionally starting at `-π/2` (top center). Convert degrees to radians with `radians = degrees * π / 180`.

For items distributed along a rectangle's edge instead of a circle: `x = containerLeft + containerWidth * (i + 1) / (numItemsOnEdge + 1)`, `y = edge ± elementHeight / 2`.

## Hiding elements without leaving artifacts

Pair `opacity: 0` with `visibility: hidden` — on any background, but especially dark ones, an `opacity: 0` element compressed through screenshot/video capture can leave a faint ghost. `visibility` should apply instantly on show, and only after the fade completes on hide:

```css
.el-hidden {
  opacity: 0;
  visibility: hidden;
  transition: opacity 0.5s ease-out, visibility 0s 0.5s;   /* visibility delays on hide */
}
.el-hidden.visible {
  opacity: 1;
  visibility: visible;
  transition: opacity 0.5s ease-out, visibility 0s 0s;     /* visibility is instant on show */
}
```
For elements that should leave the layout flow entirely when hidden (placeholder text, empty states), toggle `display: none` via a parent class instead.

## Class toggling over inline styles for JS-driven state

When JavaScript drives a CSS animation's state (a timed sequence, a choreography loop), toggle classes — never set `element.style.*` directly for the same property a CSS class also controls. An inline style always wins the cascade over a class rule, which causes state bugs: an element meant to be hidden by a class stays visible because a stray inline style from an earlier step still overrides it.

```js
// Good — the only state lever is class membership
stage.classList.remove('clicking', 'processing', 'complete');
stage.classList.add('processing');
```

## When to choose CSS vs JavaScript (decision already in the core)

The core's `motion.md` has the full CSS-vs-Framer-Motion decision table (simple hover → CSS; physics-based spring → JS; shared element transitions → JS `layoutId`). The rule that matters most for craft: **CSS and WAAPI stay smooth when the main thread is busy** (page loading, scripts running); `requestAnimationFrame`-based JS animations (including Framer Motion's `x`/`y`/`scale` shorthand) can drop frames under that exact load. Use CSS for predetermined motion; reserve JS/springs for motion that must respond to a value that changes unpredictably (drag position, gesture velocity, live data).

## Attribution

Transform mastery, clip-path techniques, `@starting-style`, and the CSS-variable performance trap are from Emil Kowalski's `emil-design-eng` skill (MIT). Trigonometric positioning and the visibility/opacity/class-toggling patterns are from the `css-animation` walkthrough-generator skill (MIT) — narrowed here to the general-purpose technique, not its full demo-generation workflow (Chrome research, interview, freeze-and-inspect review loop), which is a distinct tool for building marketing/onboarding walkthroughs rather than day-to-day motion craft.
