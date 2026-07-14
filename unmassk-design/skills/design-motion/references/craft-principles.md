# Craft Principles

The judgment layer above the core's duration/easing tables (`skills/unmassk-design/references/motion.md`). Where the core says *what* value to use, this says *whether, when, and why* to animate at all — and how to make motion feel alive instead of merely correct.

Condensed from Emil Kowalski's design-engineering philosophy (animations.dev) and Apple's *Designing Fluid Interfaces* (WWDC 2018) + *Principles of Great Design* (WWDC 2026), translated to the web.

---

## 1. Should this animate at all? (decide before any easing/duration)

Match motion to how often the user sees it:

| Frequency | Decision |
|---|---|
| 100+ times/day (keyboard shortcuts, command-palette toggle) | No animation. Ever. |
| Tens of times/day (hover effects, list navigation) | Remove or drastically reduce |
| Occasional (modals, drawers, toasts) | Standard animation |
| Rare / first-time (onboarding, celebrations) | Can add delight |

Never animate a keyboard-initiated action — it's repeated hundreds of times a day and animation makes it feel slow and disconnected. (Raycast ships zero open/close animation on its command palette — that absence is the correct call, not an oversight.)

**Valid purposes for motion** — an animation must serve one of these, or it should not exist:
- **Spatial consistency** — a toast enters and exits from the same direction, so swipe-to-dismiss feels intuitive.
- **State indication** — a morphing button communicates a state change.
- **Explanation** — a marketing animation shows how a feature works.
- **Feedback** — a button scales down on press, confirming the interface heard the user.
- **Preventing a jarring change** — elements appearing/disappearing without transition feel broken.

"It looks cool" on a frequently-seen element is not a purpose. If you can't name which of these an animation serves, delete it — deletion is a valid, often correct, outcome of a motion review.

## 2. Physical correctness — nothing appears from nothing

- **Never animate from `scale(0)`.** Nothing in the real world disappears and reappears completely. Start from `scale(0.9–0.97)` + `opacity: 0` — even a barely-visible initial scale reads as natural, like a balloon that keeps its shape even deflated.
- **Origin-aware popovers.** Popovers, dropdowns, and tooltips scale from their trigger, not from center:
  ```css
  .popover { transform-origin: var(--radix-popover-content-transform-origin); } /* Radix */
  .popover { transform-origin: var(--transform-origin); }                       /* Base UI */
  ```
  **Modals are exempt** — they appear centered in the viewport with no single trigger, so `transform-origin: center` is correct there. Don't flag it.
- **Buttons must feel responsive.** `transform: scale(0.97)` on `:active`, subtle range 0.95–0.98, `transition: transform 160ms ease-out`. Applies to any pressable element.
- **Asymmetric enter/exit.** Deliberate phases (a press, a hold-to-confirm, a destructive confirm) animate slower; the system's response snaps back fast. A hold-to-delete can be `2s linear` on press and `200ms ease-out` on release — slow where the user is deciding, fast where the system responds. Symmetric timing on a press-and-release is a finding, not a neutral choice.

## 3. Custom easing — the built-ins are too weak

The core's `motion.md` gives the standard curve set. For deliberate, high-craft motion, prefer stronger custom curves over the default CSS easings:

```css
--ease-out: cubic-bezier(0.23, 1, 0.32, 1);        /* strong ease-out for UI */
--ease-in-out: cubic-bezier(0.77, 0, 0.175, 1);    /* strong ease-in-out for on-screen movement */
--ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);      /* iOS-like drawer curve (Ionic) */
```

Never `ease-in` on UI — it delays the exact moment the user is watching most closely, so it *feels* slower than `ease-out` even at an identical duration. Don't hand-roll curves from scratch; pull stronger variants from [easing.dev](https://easing.dev/) or [easings.co](https://easings.co/).

## 4. Interruptibility is the single most important principle for anything touchable

> "The thought and the gesture happen in parallel." — Apple, *Designing Fluid Interfaces*

Anything a user can grab, drag, or trigger rapidly (toasts stacking, toggles, a drawer mid-close) must be interruptible and redirectable at any instant:

- **Never lock out input during a transition.**
- **Animate from the current on-screen (presentation) value, never the target/logical value.** On interrupt, read the live transform and start the new animation from there — starting from the target causes a visible jump.
- **CSS transitions retarget smoothly mid-flight; `@keyframes` restart from zero.** For anything triggered rapidly, use transitions or springs, not keyframes.
- **When a gesture reverses, blend velocity — don't hard-cut it.** A closing modal the user grabs again should follow the finger, not finish closing first. Springs carry velocity through a re-target; keyframes and most tweens don't.
- **Decompose 2D motion into independent X and Y springs** rather than one spring on a 2D distance — otherwise X and Y desync when their velocities differ.

Springs are the tool that makes interruptibility natural, because they have no fixed duration and are velocity-aware by construction. See `react-libraries.md` for the concrete stiffness/damping/duration/bounce parameters across libraries.

## 5. Gesture and drag physics (Apple's fluid-interfaces vocabulary)

- **Respond on pointer-down, not on release.** The moment lag appears, directness "falls off a cliff." Highlight the instant a button is pressed.
- **1:1 tracking, respecting grab offset.** `setPointerCapture` so tracking continues past the element's bounds; track position + timestamp history for velocity, don't just read the final point.
- **Velocity handoff.** When a gesture ends, hand the release velocity to the settling animation so there's no seam between dragging and animating. Some spring APIs want it normalized: `relativeVelocity = gestureVelocity / (targetValue − currentValue)`.
- **Momentum projection — animate to where the gesture is *going*, not where it stopped.** Project the resting position from velocity before choosing the snap target (same idea as scroll deceleration):
  ```js
  // decelerationRate ≈ 0.998 for normal scroll feel; 0.99 for snappier
  function project(initialVelocity, decelerationRate = 0.998) {
    return (initialVelocity / 1000) * decelerationRate / (1 - decelerationRate);
  }
  const target = nearestSnapPoint(currentPosition + project(releaseVelocity));
  ```
- **Rubber-banding at boundaries — resist progressively, never hard-stop:**
  ```js
  function rubberband(overshoot, dimension, constant = 0.55) {
    return (overshoot * dimension * constant) / (dimension + constant * Math.abs(overshoot));
  }
  ```
- **Momentum-based dismissal.** Don't require crossing a distance threshold alone — compute velocity (`Math.abs(distance) / elapsedMs`) and dismiss if it exceeds ~0.11. A quick flick should be enough regardless of distance travelled.
- **Multi-touch protection.** Ignore additional touch points once a drag has started (`if (isDragging) return`) — otherwise switching fingers mid-drag jumps the element.
- **Spatial consistency.** An element that enters from the right must exit to the right. Anchor menus/sheets/popovers to their trigger so the spatial relationship is visually obvious. Mirror the easing curve on reversible transitions (inverse cubic-bézier control points) so the return path matches the outbound path.

## 6. Cohesion — motion has a personality, and it must match the product's

Motion should match the component's and product's personality: a playful consumer app can be bouncier; a professional dashboard stays crisp and fast. Mismatched personality across components — one bouncy toast in an otherwise crisp dashboard — is a craft failure even if each animation is individually "correct."

Sonner (13M+ weekly downloads) feels right partly because the whole experience is cohesive: it uses `ease` rather than `ease-out`, slightly slower than typical UI timing, to feel more elegant — matching the toast's design and the library's name. There's no formula for this; the opacity+height combination in an entering/exiting list is trial and error, adjusted until it feels right.

**Debugging feel** (use when a transition feels "off" but the values look correct on paper):
- **Slow motion**: bump duration 2–5× temporarily, or use the browser's DevTools animation inspector. Check: do colors crossfade smoothly or show two overlapping states? Does easing stop abruptly? Is `transform-origin` correct? Are coordinated properties in sync?
- **Frame-by-frame**: step through in Chrome DevTools' Animations panel to reveal timing drift between coordinated properties.
- **Fresh eyes the next day.** Imperfections invisible during development surface after a break.
- **Real devices for gestures.** Test drawers/swipes on physical hardware — simulators don't replicate touch feel.
- **Mask an imperfect crossfade with blur.** When a crossfade shows two distinct overlapping states despite tuning easing/duration, add `filter: blur(2px)` (cap at ~20px — heavy blur is expensive, especially in Safari) during the transition. It blends the states into one perceived transformation instead of two objects swapping.

## 7. Apple's eight design principles — the frame this craft serves

Every rule above exists to serve one of these (from *Principles of Great Design*, WWDC 2026): **Purpose** (intention — decide what not to build), **Agency** (control + forgiveness, easy undo), **Responsibility** (privacy, safety, anticipate misuse), **Familiarity** (honor real-world metaphors, be consistent), **Flexibility** (adapt to context/device/ability), **Simplicity — not minimalism** (concise + clear, not just sparse), **Craft** (nothing is random — every timing value is a defensible, deliberate choice), **Delight** (the result of the other seven, not confetti bolted on top).

Feedback comes in four kinds — status, completion, warning, error — and each deserves its own visual language, fired inline, not just at submit. When motion, sound, and haptics combine, they must fire on the same frame (harmony) and only for meaningful moments (utility) — over-feedback trains users to ignore all of it.

## 8. Materials & depth (translucency, when relevant)

Translucent chrome (`backdrop-filter: blur() saturate()`) reads as a floating functional layer, not a wall. Heavier/darker materials separate structural regions (sidebars); lighter materials draw attention to interactive elements. Never stack one light translucent surface on another — legibility collapses. Materialize surfaces on enter/exit by animating blur radius and scale together, not just opacity — a glass panel should arrive as a material, not fade like a flat rectangle. Full detail (vibrancy, scroll-edge effects, `prefers-reduced-transparency`) lives in the source; pull it in only when a project actually uses glass/blur chrome.

## Attribution

Distilled from Emil Kowalski's design-engineering philosophy (`emil-design-eng`, MIT) and Apple's WWDC design talks translated to the web (`apple-design`, MIT) — see `SKILL.md` Attribution section for full source list.
