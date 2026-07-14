# React Animation Libraries

Three JS-side animation approaches for React, when to reach for each, and their APIs. The core's `motion.md` already covers CSS transitions/`@starting-style`/WAAPI and basic Framer Motion entrances — this file covers the deeper library surface: Motion.dev (Framer Motion's successor), the full Framer Motion feature set (gestures, layout animations, `AnimatePresence`), and React Spring's physics model as an alternative.

## Which library, when

| Need | Library | Why |
|---|---|---|
| Declarative entrances, gestures (`whileHover`/`whileTap`), scroll reveal, layout/shared-element transitions | **Motion.dev** (`motion/react`) — successor to Framer Motion, same API surface, smaller and faster | Default choice for React/Next.js/Svelte/Astro. 120fps target, GPU-accelerated. |
| Same as above, existing codebase already on `framer-motion` | **Framer Motion** | Full-featured predecessor; still widely deployed, migrate to Motion.dev opportunistically, not urgently. |
| Physically-accurate spring tuning, momentum/inertia utilities, reactive-stream composition (Popmotion) | **React Spring** (+ Popmotion) | Truer mass/tension/friction physics model; better fit when a design calls for named, tunable physical presets rather than duration+bounce. |
| Complex multi-step timelines, scroll-triggered choreography across many elements | GSAP (own family/skill) | Not covered here — timeline-based, not physics-based. |
| Simple hover/focus states, single-step entrances, predetermined motion | Plain CSS (see `css-animations.md` + core `motion.md`) | Runs off the main thread; smoother under load than any JS library for this class of animation. |

**Do not reach for a JS library for what CSS already does well.** CSS animations/transitions stay smooth while the main thread is busy (loading, scripting, painting); Framer Motion / Motion.dev's convenience shorthand props run on `requestAnimationFrame` on the main thread and can drop frames under load — see the perf note below.

## Motion.dev / Framer Motion — core API surface

```tsx
import { motion, AnimatePresence, useScroll, useTransform, useSpring, useInView } from "motion/react"
// framer-motion package is API-compatible; swap the import only.

<motion.div
  initial={{ opacity: 0, y: 20 }}
  animate={{ opacity: 1, y: 0 }}
  exit={{ opacity: 0, y: -20 }}                 // needs <AnimatePresence>
  transition={{ duration: 0.3, ease: [0.25, 1, 0.5, 1] }}
  whileHover={{ scale: 1.02, y: -2 }}
  whileTap={{ scale: 0.98 }}
  whileInView={{ opacity: 1 }}
  viewport={{ once: true, amount: 0.3 }}
  drag="x"
  dragConstraints={{ left: -100, right: 100 }}
  dragElastic={0.2}
  layout                                        // FLIP auto-animate on resize/reposition
  layoutId="shared-card"                        // morph between two mounted elements
/>
```

### Exit animations require `AnimatePresence`

```tsx
<AnimatePresence mode="wait">   {/* sync (default) | wait | popLayout */}
  {isVisible && (
    <motion.div key="modal" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} />
  )}
</AnimatePresence>
```
Common pitfall: forgetting `AnimatePresence` (exit prop silently does nothing), or forgetting a unique `key` in a mapped list (breaks exit tracking).

### Variants — for orchestration, not per-element repetition

```tsx
const container = { visible: { transition: { staggerChildren: 0.08 } } }
const item = { hidden: { opacity: 0, x: -20 }, visible: { opacity: 1, x: 0 } }

<motion.ul initial="hidden" animate="visible" variants={container}>
  {items.map(i => <motion.li key={i.id} variants={item} />)}
</motion.ul>
```

### Layout animations & shared elements

`layout` animates transforms via FLIP when position/size changes — cheap, GPU-only. `layoutId="x"` on two different mounted components morphs between them (tab underline indicators, thumbnail→full-image expansion). Use `layout="position"` or `layout="size"` to scope the cost when only one axis changes. Overusing `layoutId` is expensive — it tracks elements globally; use only where a real visual continuity payoff exists.

### Scroll & motion values

```tsx
const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end start"] })
const opacity = useTransform(scrollYProgress, [0, 0.5], [0, 1])
const springX = useSpring(useMotionValue(0), { stiffness: 300, damping: 20 })
```
`useMotionValue`/`useTransform` update without triggering React re-renders — prefer them over `useState` for anything that changes on every frame (scroll position, drag offset, cursor tracking).

### Performance: the shorthand trap

Motion's convenient shorthand props (`x`, `y`, `scale` as direct `animate` keys) are **not hardware-accelerated** — they run via `requestAnimationFrame` on the main thread and drop frames when the page is busy loading or scripting. For anything that must stay smooth under load, animate the full `transform` string instead:

```tsx
<motion.div animate={{ x: 100 }} />                          // main-thread rAF, can drop frames
<motion.div animate={{ transform: "translateX(100px)" }} />  // hardware-accelerated
```
CSS animations beat `requestAnimationFrame`-based JS under load for exactly this reason — reserve JS/springs for motion that genuinely needs interruptibility or dynamic values, and let CSS carry predetermined motion.

### Accessibility

```tsx
const shouldReduceMotion = useReducedMotion()
<motion.div animate={{ opacity: 1, y: shouldReduceMotion ? 0 : 0 }}
            transition={{ duration: shouldReduceMotion ? 0.01 : 0.3 }} />
```

## Spring configuration — three mental models, reconciled

The same physical spring is exposed three different ways across these libraries. Pick one model per project and stay consistent — don't mix.

**1. Duration + bounce (Apple-style — recommended default, easiest to reason about):**
```tsx
transition={{ type: "spring", duration: 0.5, bounce: 0.2 }}   // bounce 0–1, 0 = no overshoot
```
Maps directly to Apple's damping-ratio + response model (`craft-principles.md` §4): `bounce ≈ 1 − damping`. Start most UI at `bounce: 0` (critically damped, no overshoot); reserve `bounce: 0.1–0.3` for momentum-driven interactions (a flick, a drag release) where the gesture itself carried energy.

**2. Stiffness / damping / mass (Motion.dev, Framer Motion):**
```tsx
transition={{ type: "spring", stiffness: 300, damping: 20, mass: 1 }}
```
| Parameter | Effect | Range |
|---|---|---|
| `stiffness` | speed — higher = snappier | 100–200 gentle · 300–400 standard UI · 500–700 snappy micro-interactions · 800+ cursor-tracking |
| `damping` | overshoot control — lower = more bounce | 10–15 playful · 20–25 balanced (default) · 30–40 subtle · 50+ no bounce (critically damped) |
| `mass` | perceived weight — higher = slower to start/stop | 0.5 small elements (icons, badges) · 1 standard (buttons, cards) · 2+ large (modals, full-screen) |

**3. Tension / friction / mass (React Spring):**
```jsx
useSpring({ from: {...}, to: {...}, config: { tension: 170, friction: 26, mass: 1 } })
```
Presets: `config.default` (170/26) · `config.gentle` (120/14) · `config.wobbly` (180/12) · `config.stiff` (210/20) · `config.slow` (280/60) · `config.molasses` (280/120).

Critical damping point: `friction_critical = 2 × √(tension × mass)` — at `tension: 170, mass: 1` that's ≈26, which is why React Spring's own `config.default` friction is 26. Below that ratio the spring overshoots (bouncy); above it, it's sluggish but never overshoots.

**Cross-reference by feel** (use to translate a value from one library's docs into another):

| Feel | Motion.dev (stiffness/damping) | React Spring (tension/friction) |
|---|---|---|
| Snappy | 500 / 25 | 300 / 20 |
| Bouncy | 400 / 12 | 180 / 12 |
| Gentle / modal | 200 / 25 | 120 / 14 |
| Critically damped (no bounce) | 300 / 50 | 170 / 26 (mass 1) |

### Preserving velocity across interruption (both libraries)

```tsx
// Motion.dev — velocity is handled internally on interrupt when the animation is still running

// React Spring — pass current velocity explicitly on retarget
api.start({ x: newTarget, velocity: springs.x.getVelocity() })
```
Never hard-reset a moving spring to a new target without carrying velocity — it produces the "brick wall" discontinuity described in `craft-principles.md` §4.

## React Spring — declarative hook API

```jsx
import { useSpring, useTrail, useTransition, animated, config } from '@react-spring/web'

// Single value
const springs = useSpring({ from: { opacity: 0, y: -40 }, to: { opacity: 1, y: 0 }, config: config.gentle })
<animated.div style={springs}>Hello</animated.div>

// Imperative control — use the function-config form for api.start()
const [springs, api] = useSpring(() => ({ from: { x: 0 } }), [])
api.start({ to: { x: 100 } })

// Multiple elements in sequence
const trails = useTrail(items.length, { from: { opacity: 0, x: -20 }, to: { opacity: 1, x: 0 } })

// Enter/exit lists (React Spring's AnimatePresence equivalent)
const transitions = useTransition(items, {
  from: { opacity: 0, height: 0 }, enter: { opacity: 1, height: 80 }, leave: { opacity: 0, height: 0 },
  keys: item => item.id,
})
```

Common pitfalls: mutating a spring value directly (`springs.x.set(100)`) instead of going through `api.start()`; omitting the `[]` dependency array on the function-config form (recreates the spring every render); leaving `precision` at its very fine default (`0.0001`) when a coarser `0.01` would stop updates sooner with no visible difference — a real, if small, performance win on long-running springs.

### Skip all animation (accessibility / testing)

```jsx
import { Globals } from '@react-spring/web'
useEffect(() => {
  Globals.assign({ skipAnimation: true })
  return () => Globals.assign({ skipAnimation: false })
}, [])
```

## Attribution

Motion.dev API distilled from `motion-dev-animations-skill` (MIT). Framer Motion patterns and pitfalls from `claudedesignskills/motion-framer` (Apache 2.0). React Spring / Popmotion physics from `claudedesignskills/react-spring-physics` (Apache 2.0). Spring parameter reconciliation and Apple duration+bounce cross-reference is original synthesis for this skill.
