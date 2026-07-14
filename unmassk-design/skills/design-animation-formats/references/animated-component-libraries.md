# Animated Component Libraries -- Magic UI + React Bits

Source: `animated-component-libraries` (claudedesignskills by freshtechbro,
Apache 2.0).

## What it is

Two pre-built React component collections for common animated UI effects --
use these instead of hand-authoring (Anime.js) or designer-file playback
(Lottie/Rive) when the ask is a generic, already-solved effect: a shimmer
button, a marquee, a particle background, a blur-text reveal. Installing a
maintained component is faster and more consistent than re-implementing the
same effect from scratch every time.

- **Magic UI** -- 150+ TypeScript components, built on Tailwind CSS +
  Framer Motion, designed to slot into a shadcn/ui project.
- **React Bits** -- 90+ components with minimal dependencies, copy-paste
  install, focused on visual effects/backgrounds/micro-interactions;
  includes WebGL-based effects (Particles, Plasma, Aurora) via `ogl`.

## When to reach for which

| Effect | Library | Why |
|---|---|---|
| Shimmer button, border beam, animated grid pattern, marquee | Magic UI | Already matches shadcn/Tailwind conventions |
| Blur-text word/character reveal | React Bits | `BlurText` component, no shadcn dependency needed |
| macOS-style dock navigation with magnification | React Bits | `Dock` component |
| Animated stat counters (`CountUp`) | React Bits | Purpose-built, minimal deps |
| WebGL particles/plasma/aurora background | React Bits | Requires `ogl`; heavier, budget for perf |

## Magic UI

```bash
# Preferred: shadcn CLI
npx shadcn@latest add https://magicui.design/r/animated-beam

# Manual: copy component to components/ui/, then:
npm install motion clsx tailwind-merge
```

Requires a `cn()` utility (`lib/utils.ts`):

```typescript
import clsx, { ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)); }
```

Manual installs also require the component's CSS keyframes registered in
`globals.css` (Magic UI ships these per-component, e.g. `marquee`,
`shimmer-slide`, `ripple` -- see the component's install docs; they are not
auto-injected by the shadcn CLI's manual-copy path).

```typescript
import { ShimmerButton } from "@/components/ui/shimmer-button";
import { BorderBeam } from "@/components/ui/border-beam";

<ShimmerButton shimmerColor="#fff" background="rgba(0,0,0,1)">Get Started</ShimmerButton>
<Card className="relative overflow-hidden">...<BorderBeam duration={8} size={100} /></Card>
```

## React Bits

```bash
# Copy component files from reactbits.dev into the project (primary method)
npm install framer-motion   # animation-heavy components
npm install ogl             # WebGL components: Particles, Plasma, Aurora
```

```jsx
import BlurText from './components/BlurText';
<BlurText text="Transform your ideas" delay={100} animateBy="words" direction="top" />

import Particles from './components/Particles';
<Particles particleCount={200} particleColors={['#FF6B6B','#4ECDC4']} speed={0.12} />
```

## Combining both

```jsx
// Magic UI: structural/pattern components. React Bits: interactive effects.
<section className="relative h-screen">
  <Particles particleCount={150} />                 {/* React Bits background */}
  <GridPattern squares={[[4,4],[8,2]]} className="opacity-30" /> {/* Magic UI overlay pattern */}
  <BlurText text="Next-Generation Platform" />       {/* React Bits reveal */}
</section>
```

## Pitfalls

- **Missing dependencies/utility.** Both libraries assume `motion`
  (Framer Motion) plus, for Magic UI, `clsx` + `tailwind-merge` + a working
  `cn()`. React Bits' WebGL components additionally need `ogl`.
- **CSS keyframes not registered.** A manually-copied Magic UI component
  animates via a CSS custom property/keyframe pair that must exist in
  `globals.css` -- if the animation silently does nothing, this is the
  first thing to check.
- **Z-index conflicts.** Background/pattern components (`GridPattern`,
  `Particles`) need `absolute inset-0 -z-10` (or similar) with content at
  `relative z-10`, or they cover the foreground.
- **Tailwind content globs miss the components directory.** If custom
  classes on a Magic UI component don't apply, check `tailwind.config.js`'s
  `content` array includes `./components/**/*.{js,jsx,ts,tsx}`.
- **No `prefers-reduced-motion` gate by default.** Neither library disables
  itself for reduced-motion users -- check `window.matchMedia('(prefers-
  reduced-motion: reduce)')` and drop `delay`/`animateBy` accordingly (React
  Bits' `BlurText` pattern), same rule as the rest of this family.
- **Heavy WebGL effects on low-end devices.** Scale `particleCount` (or
  swap to a lighter component) based on `navigator.hardwareConcurrency` and
  mobile detection -- don't ship the desktop particle count unconditionally.

## Related

`animejs.md` for when the desired effect isn't already a pre-built
component and needs hand-authoring. `design-3d` for a full 3D/WebGL scene
(these libraries' WebGL components are 2D-effect-only, not scene-graph 3D).
