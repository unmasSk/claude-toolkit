# Animation Vocabulary

A reverse-lookup glossary: turn a vague description of a motion effect ("the bouncy thing when a popover opens", "the iOS rubber-band scroll") into its precise term. Use this to name an effect precisely — before designing or building it — or to disambiguate two close terms (*clip-path* vs *mask*, *pop in* vs *bounce*, *shared element transition* vs *layout animation*).

Condensed from Emil Kowalski's `animation-vocabulary` skill (MIT).

### Entrances & Exits
- **Fade in / Fade out** — opacity change only.
- **Slide in** — enters by sliding from off-screen (left/right/top/bottom).
- **Scale in** — grows from smaller to full size, usually paired with a fade.
- **Pop in** — appears with a slight overshoot, like it bounces into place.
- **Reveal** — content is uncovered gradually, typically by animating a clip-path or mask.
- **Enter / Exit** — the animation an element plays on mount/unmount.

### Sequencing & Timing
- **Keyframes** — defined points (0%, 50%, 100%) the browser interpolates between.
- **Interpolation / Tween** — generating the in-between frames from a start to an end value.
- **Stagger** — animate several items one after another with a small delay each, creating a cascade.
- **Orchestration** — deliberately timing multiple animations so they read as one coordinated motion.
- **Delay** — time before an animation starts. **Duration** — how long it takes.
- **Fill mode** — whether an element keeps its first/last frame's styles before/after the animation (e.g. `forwards`).
- **Stepped animation** — divided into discrete steps, like a countdown timer.

### Movement & Transforms
- **Translate / Scale / Rotate / Skew** — position, size, angle, shear.
- **3D tilt / Flip** — `rotateX`/`rotateY` for depth.
- **Perspective** — how strong the 3D effect looks; lower value exaggerates depth.
- **Transform origin** — the anchor point a scale/rotation grows or spins from.
- **Origin-aware animation** — an element animates out of its trigger (a popover growing from the button that opened it), instead of its own center (CSS default).

### Transitions Between States
- **Crossfade** — one element fades out as another fades in, same spot.
- **Continuity transition** — a change that keeps the user oriented by visually connecting before/after (e.g. the same rectangle getting bigger/smaller).
- **Morph** — one shape smoothly turns into another (e.g. Dynamic Island).
- **Shared element transition** — an element travels and transforms from one position into another (a thumbnail expanding into a card).
- **Layout animation** — when size/position changes, the element animates to the new spot instead of snapping.
- **Accordion / Collapse** — a section smoothly expands/collapses its height.
- **Direction-aware transition** — content slides one way going forward, the opposite way going back.

### Scroll
- **Scroll reveal** — elements fade/slide into place as they enter the viewport.
- **Scroll-driven animation** — progress tied directly to scroll position.
- **Parallax** — background/foreground move at different speeds, creating depth.
- **Page transition** — plays when navigating between pages/routes.
- **View transition** — the browser morphs between two states/pages, connecting shared elements (View Transitions API).

### Feedback & Interaction
- **Hover effect** — visual change on cursor-over.
- **Press / Tap feedback** — a subtle scale-down on click, so it feels physical.
- **Hold to confirm** — a progress fill while a button is held.
- **Drag** — moving an element by grabbing it, often with momentum on release.
- **Drag to reorder** — dragging list items to rearrange, others shift to make room.
- **Swipe to dismiss** — dragging an element off-screen to close it (drawer, toast).
- **Rubber-banding** — resistance + snap-back past a boundary (iOS overscroll feel).
- **Shake / Wiggle** — a quick side-to-side jitter signaling an error or rejected input.
- **Ripple** — a circle expanding from the tap point, confirming the press.

### Easing
- **Easing** — the rate at which an animation speeds up/slows down.
- **Ease-out** — fast start, slow end; default for UI and anything responding to the user.
- **Ease-in** — slow start, fast end; usually avoided, can feel sluggish.
- **Ease-in-out** — slow, fast, slow; good for elements already on screen moving A→B.
- **Linear** — constant speed; avoid for UI, reserve for spinners/marquees.
- **Cubic-bezier** — a custom easing curve for precise control.
- **Asymmetric easing** — accelerates and decelerates at different rates; feels more alive than a symmetric curve.

### Spring Animations
- **Spring** — physics-driven motion (tension/stiffness, mass, damping) rather than a fixed duration.
- **Stiffness / Tension** — how strongly the spring pulls toward its target; higher = snappier.
- **Damping** — how quickly a spring settles; lower = more bounce/oscillation.
- **Mass** — how heavy the element feels; more mass = slower, more sluggish.
- **Bounce** — a spring that overshoots and settles, adding playfulness.
- **Perceptual duration** — how long a spring *feels* finished, even while it micro-settles underneath.
- **Momentum / Velocity** — motion carrying speed and direction, especially after a drag or interruption; a spring carries it into the next animation when interrupted.
- **Interruptible animation** — can be smoothly redirected mid-flight instead of finishing first.

### Looping & Ambient Motion
- **Marquee** — content scrolling continuously in a loop.
- **Loop** — repeats a set number of times or infinitely.
- **Alternate (yoyo)** — plays forward then reverses each iteration, instead of jumping back to start.
- **Orbit** — an element circling around another continuously.
- **Pulse** — a gentle repeating scale/opacity change to draw attention.
- **Float** — a gentle continuous up-and-down drift, making a static element feel alive.
- **Idle animation** — subtle motion while an element just sits, waiting to be interacted with.

### Polish & Effects
- **Blur** — softens an element, or masks tiny imperfections in a crossfade.
- **Clip-path** — clips an element to a shape; used for reveals, masks, before/after sliders.
- **Mask** — like clip-path but with soft, fadeable edges.
- **Before / after slider** — a draggable divider wiping between two overlaid images.
- **Line drawing** — an SVG path draws itself in, like an invisible pen tracing it.
- **Text morph** — text animates character-by-character when it changes.
- **Skeleton / Shimmer** — a placeholder with a moving sheen shown while content loads.
- **Number ticker** — digits rolling/counting up to a value. **Tabular numbers** — fixed-width digits so they don't shift as they change; essential for tickers/timers.
- **Typewriter** — text appearing one character at a time.

### Performance
- **Frame rate (FPS)** — frames drawn per second; 60fps baseline, 120fps on newer displays.
- **Jank / Dropped frame** — visible stutter when the browser misses a frame's deadline.
- **Compositing** — GPU moves/fades an element on its own layer without redoing layout or paint.
- **will-change** — a CSS hint to promote an element to its own layer ahead of an imminent animation.
- **Layout thrashing** — animating `width`/`height`/`top`/`left` forces layout recalculation every frame.

### Principles to Know
- **Purposeful animation** — motion serves a function (orient, feedback, relationship), not decoration.
- **Anticipation** — a small wind-up in the opposite direction before a move, hinting at what's coming.
- **Follow-through** — parts of an element keep moving and settle slightly after the main motion stops.
- **Squash & stretch** — deforming an element as it moves, to convey weight and speed.
- **Perceived performance** — the right animation makes an interface feel faster than it is.
- **Frequency of use** — the more often an animation is seen, the shorter and subtler it should be.
- **Spatial consistency** — an element keeps its identity/position across states, so users never lose track.
- **Hardware acceleration** — animating transform/opacity lets the GPU keep motion smooth.
- **Reduced motion** — respecting `prefers-reduced-motion` by toning down or removing motion.
