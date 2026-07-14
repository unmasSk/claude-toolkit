# Provenance

`unmassk-design` is a **fusion**, not a lift. Every branch below condenses and
rewrites its source material into this plugin's own voice — there is no
byte-faithful, per-file correspondence to any single upstream skill.
Reconciling drift means diffing against a fresh clone and re-folding
condensed patterns, not re-lifting files wholesale.

Repo clone commands and canonical source URLs live in `.ref-repos/SOURCES.md`
(repo root) — this file maps each **branch** to its sources; that file lists
the raw repos.

## Core (`skills/unmassk-design`)

| Source | URL | License | What it contributed |
|---|---|---|---|
| Impeccable (pbakaus) | https://github.com/pbakaus/impeccable | Apache 2.0 | Aesthetic philosophy, design-principles reference, the 10 steering commands |
| UI/UX Pro Max (nextlevelbuilder) | https://github.com/nextlevelbuilder/ui-ux-pro-max-skill | MIT | Design-system generation workflow, BM25 CSV corpus structure |
| bencium-marketplace (bencium) | https://github.com/bencium/bencium-marketplace | MIT | Plugin patterns folded into the core skill |

Pre-existing — condensed 2026-03-14, unchanged by this revamp.

## design-motion

| Source | URL | License | What it contributed |
|---|---|---|---|
| emilkowalski/skills | https://github.com/emilkowalski/skills | MIT | `emil-design-eng` (craft principles), `apple-design` (fluid-interfaces gesture/spring physics), `animation-vocabulary` (reverse-lookup naming), `review-animations` + `improve-animations` (the ten-point review bar) |
| motion-dev-animations-skill (199-biotechnologies) | https://github.com/199-biotechnologies/motion-dev-animations-skill | MIT | Motion.dev API reference |
| claudedesignskills (freshtechbro) | https://github.com/freshtechbro/claudedesignskills | Apache 2.0 | `motion-framer` (Framer Motion patterns), `react-spring-physics` (React Spring/Popmotion physics) |
| css-animation-skill (neonwatty) | https://github.com/neonwatty/css-animation-skill | MIT | `walkthrough-generator` (trigonometric choreography, visibility patterns) |

## design-3d

| Source | URL | License | What it contributed |
|---|---|---|---|
| claudedesignskills (freshtechbro) | https://github.com/freshtechbro/claudedesignskills | Apache 2.0 | `threejs-webgl`, `react-three-fiber`, `babylonjs-engine`, `playcanvas-engine`, `aframe-webxr`, `lightweight-3d-effects`, `spline-interactive`, `pixijs-2d`, `blender-web-pipeline`, `substance-3d-texturing` — ten source skills condensed into one routing family |

## design-scroll

| Source | URL | License | What it contributed |
|---|---|---|---|
| claudedesignskills (freshtechbro) | https://github.com/freshtechbro/claudedesignskills | Apache 2.0 | `gsap-scrolltrigger`, `locomotive-scroll`, `barba-js`, `scroll-reveal-libraries` (AOS) |

## design-animation-formats

| Source | URL | License | What it contributed |
|---|---|---|---|
| claudedesignskills (freshtechbro) | https://github.com/freshtechbro/claudedesignskills | Apache 2.0 | `lottie-animations`, `rive-interactive`, `animejs`, `animated-component-libraries` (Magic UI + React Bits) |

## design-taste

| Source | URL | License | What it contributed |
|---|---|---|---|
| taste-skill (leonxlnx) | https://github.com/leonxlnx/taste-skill | MIT | `industrial-brutalist-ui`, `minimalist-ui`, `high-end-visual-design`, `redesign-existing-projects`, `stitch-design-taste`, `image-to-code`, `gpt-taste`, `brandkit` — eight single-file skills condensed into one family |

## design-flutter

| Source | URL | License | What it contributed |
|---|---|---|---|
| claude-flutter-ui-skills (Naimehossein77) | https://github.com/Naimehossein77/claude-flutter-ui-skills | MIT | `flutter-ui` — layout, Material 3/Cupertino theming, and animation patterns. State-management architecture and navigation-architecture material from the source were intentionally left out (out of this branch's design/UI scope) |

## Revamp date

2026-07-14 — core (1 skill) expanded to a 7-skill multi-branch plugin
(`plugin.json` bumped to reflect the new branch set; branch contents were
already condensed and verified before this pass — this file documents that
work, it does not redo it).
