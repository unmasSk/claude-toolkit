---
name: design-3d
description: >
  Use when the user asks to "add 3D to the site", "build a WebGL scene",
  "make a Three.js configurator", "add a VR/AR experience", "embed a Spline
  scene", "render particles", "export a Blender model for the web", "texture
  a 3D model", "add a tilt effect to a card", "animated 3D background", or
  mentions any of: Three.js, React Three Fiber, R3F, Babylon.js, PlayCanvas,
  WebGL, WebGPU, WebXR, A-Frame, VR, AR, glTF, GLB, Draco, Zdog, Vanta.js,
  Vanilla-Tilt, Spline, PixiJS, particle system, Blender export, Substance
  Painter, PBR texturing, product configurator, 3D hero section.
  Covers the full "3D/WebGL for web" family: choosing an engine (Three.js,
  R3F, Babylon.js, PlayCanvas), immersive VR/AR (A-Frame/WebXR), lightweight
  decorative 3D (Zdog, Vanta.js, Vanilla-Tilt, Spline, PixiJS 2D), and the
  asset pipeline (Blender to glTF, Substance Painter PBR texturing).
  Use when NOT: 2D UI motion with no 3D/WebGL element, or color/typography/
  layout work with no 3D element -- out of scope here.
  Based on claudedesignskills by freshtechbro (Apache 2.0): threejs-webgl,
  react-three-fiber, babylonjs-engine, playcanvas-engine, aframe-webxr,
  lightweight-3d-effects, spline-interactive, pixijs-2d, blender-web-pipeline,
  substance-3d-texturing.
version: 1.0.0
---

# Design 3D -- WebGL/3D for the Web

One family, ten sources, condensed into routing + patterns. This skill does
not teach any single engine end-to-end -- it tells which engine or technique
fits the request, then hands off to the reference that carries the patterns
that actually matter (setup, the 2-3 gotchas everyone hits, integration).
Load references on-demand. Do not load all four at startup.

Based on claudedesignskills by freshtechbro (Apache 2.0).

**Paths.** Every `scripts/…` and `assets/…` path in this file is relative to this skill's
own directory — the absolute path printed as `Base directory for this skill:` when the
skill loads. `${CLAUDE_PLUGIN_ROOT}` is empty in the Bash tool; never paste it into a
command.

## First Decision: What Kind of "3D" Is This?

Before picking a reference, answer this in order:

1. **Does it need to run as VR/AR or be viewed through a headset/phone AR?**
   -> `references/immersive-xr.md` (A-Frame/WebXR). Nothing else in this
   skill handles headset input or hit-testing.
2. **Is it a full interactive 3D scene** (configurator, 3D game, real-time
   rendering with camera control, physics, complex lighting)?
   -> `references/web-3d-engines.md`. Pick Three.js, R3F, Babylon.js, or
   PlayCanvas per the table below.
3. **Is it decorative** (a tilt card, an animated background, a few
   particles, a hero illustration) or **built by a non-coder** (Spline) or
   **2D but WebGL-accelerated** (thousands of sprites/particles)?
   -> `references/lightweight-3d.md`.
4. **Is the request about getting a 3D model INTO the browser** (exporting
   from Blender, texturing with Substance Painter, optimizing a glTF)?
   -> `references/asset-pipeline.md`. This is the step before any of the
   above renders anything.

A request can span two references (e.g., "export this Blender model and
show it in Three.js" = asset-pipeline + web-3d-engines). Load both, in that
order -- assets before rendering.

## Decision Table -- Which Tool for Which Job

| Need | Tool | Reference |
|---|---|---|
| Full control, custom shaders, max flexibility | Three.js | web-3d-engines.md |
| Same as above, but the app is already React | React Three Fiber (R3F) | web-3d-engines.md |
| Built-in physics, GUI, node-material editor, XR helper baked in | Babylon.js | web-3d-engines.md |
| Game project, entity-component-system, visual editor workflow | PlayCanvas | web-3d-engines.md |
| VR/AR, WebXR hit-testing, 360 media, HTML-first 3D | A-Frame | immersive-xr.md |
| Card tilt / parallax hover on an image or card | Vanilla-Tilt.js | lightweight-3d.md |
| Animated WebGL background behind a hero/section | Vanta.js | lightweight-3d.md |
| Small pseudo-3D icon/illustration, hand-drawn feel | Zdog | lightweight-3d.md |
| Designer wants to build the 3D scene visually, no code | Spline | lightweight-3d.md |
| Thousands of 2D sprites/particles at 60fps, 2D game, HUD over a 3D scene | PixiJS | lightweight-3d.md |
| Get a Blender model onto the web (glTF/GLB, compression, LOD) | Blender pipeline | asset-pipeline.md |
| Author PBR materials/textures for a 3D model | Substance Painter | asset-pipeline.md |

## Cross-Cutting Rules (apply regardless of engine)

These recur in every engine's pitfalls section -- worth stating once instead
of four times:

- **Dispose everything.** Geometries, materials, textures, and
  scenes/engines all hold GPU memory. Every engine here has a `.dispose()`
  or `.destroy()` — call it on unmount/teardown, or the tab leaks memory.
- **Never create objects inside the render/animation loop.** Geometry,
  Vector3, Color, etc. created every frame is the single most common
  performance bug across all four engines.
- **Batch repeated objects.** InstancedMesh (Three.js/R3F), thin
  instances/mesh instances (Babylon.js), or entity pooling (PlayCanvas,
  A-Frame) -- never spawn 1000 individual draw calls when one instanced call
  will do.
- **glTF/GLB is the interchange format.** Blender exports it, Substance
  Painter textures feed it, and every engine here (Three.js, R3F, Babylon.js,
  PlayCanvas, A-Frame) loads it the same way. Compress with Draco.
- **Frame-rate independence.** Always animate with a delta/elapsed time
  (clock.getDelta(), useFrame's `delta`, `dt` in PlayCanvas/A-Frame's tick),
  never a fixed per-frame increment.
- **Mobile is the real constraint.** Lower texture resolution, fewer lights,
  disable shadows/antialiasing, and test hardware scaling before shipping
  any of these to production.

## Scripts

Scripts are code generators, not optional helpers. Run them via Bash to produce
boilerplate instead of hand-writing it. All scripts are Python 3 standard
library only (`argparse`, `json`, `pathlib`, `os`, `sys`, `typing`) -- no
`pip install` needed -- except the three scripts explicitly flagged
"Requires" below, which run inside a host application's embedded Python
(Blender, Substance 3D Painter), not as standalone CLI tools.

Every script supports `--help` for its full flag list; the usage column below
shows the shape, not every flag.

| Script | What It Does | Usage |
|---|---|---|
| `scripts/threejs/setup_scene.py` | Generate Three.js scene boilerplate (renderer, camera, lighting, shadows) | `python3 scripts/threejs/setup_scene.py [--renderer basic\|webgpu] [--lighting basic\|shadows\|physical] [--shadows] [-o out.js]` |
| `scripts/r3f/scene_setup.py` | Generate React Three Fiber scene setup (Canvas, lighting, performance, physics) | `python3 scripts/r3f/scene_setup.py [--environment] [--performance] [--physics]` |
| `scripts/r3f/component_generator.py` | Generate R3F component boilerplate (box, sphere, model, scene, interactive) | `python3 scripts/r3f/component_generator.py --name <Name> --type <box\|sphere\|scene\|interactive\|...> [--events onClick,onHover]` |
| `scripts/babylon/scene_generator.py` | Generate Babylon.js scene boilerplate (8 scene types) | `python3 scripts/babylon/scene_generator.py --type <scene-type>` |
| `scripts/babylon/mesh_builder.py` | Generate Babylon.js mesh creation code (13 shapes) | `python3 scripts/babylon/mesh_builder.py --shape <shape>` |
| `scripts/playcanvas/project_generator.py` | Generate PlayCanvas project boilerplate | `python3 scripts/playcanvas/project_generator.py --name <project>` |
| `scripts/playcanvas/component_builder.py` | Generate PlayCanvas script components | `python3 scripts/playcanvas/component_builder.py --name <Component>` |
| `scripts/aframe/scene_generator.py` | Generate A-Frame scene boilerplate (7 scene types) | `python3 scripts/aframe/scene_generator.py --type <scene-type>` |
| `scripts/aframe/component_builder.py` | Generate A-Frame custom component boilerplate (7 component types) | `python3 scripts/aframe/component_builder.py --type <component-type>` |
| `scripts/lightweight/generate_zdog.py` | Generate Zdog pseudo-3D illustrations (6 illustration types) | `python3 scripts/lightweight/generate_zdog.py --type <illustration-type>` |
| `scripts/lightweight/setup_vanta.py` | Generate Vanta.js animated background setup (11 effects) | `python3 scripts/lightweight/setup_vanta.py --effect <effect-name>` |
| `scripts/pixijs/sprite_generator.py` | Generate PixiJS sprite/texture-atlas boilerplate | `python3 scripts/pixijs/sprite_generator.py [-o out.js]` |
| `scripts/pixijs/particle_builder.py` | Generate PixiJS particle system boilerplate | `python3 scripts/pixijs/particle_builder.py [-o out.js]` |
| `scripts/spline/project_generator.py` | Generate Spline + React starter project (Vite or Next.js) | `python3 scripts/spline/project_generator.py --name <project> [--nextjs]` |
| `scripts/spline/component_builder.py` | Generate Spline React component wrappers (6 types: basic, interactive, animated, controlled, responsive, lazy) | `python3 scripts/spline/component_builder.py --name <Name> --type <component-type>` |
| `scripts/substance/generate_export_preset.py` | Generate a Substance 3D Painter export preset JSON (gltf, mobile-webgl, etc.) | `python3 scripts/substance/generate_export_preset.py --preset gltf --output preset.json` |
| `scripts/substance/web_optimizer.py` | Optimize/plan Substance 3D Painter texture output for web delivery | `python3 scripts/substance/web_optimizer.py --input <dir> --output <dir>` |
| `scripts/substance/batch_export.py` | Batch export all texture sets from the currently open Substance Painter project | Requires Substance 3D Painter running with a project open. Run via File -> Python -> Execute Script inside Substance Painter (not a standalone CLI). |
| `scripts/blender/batch_export.py` | Batch export a directory of `.blend` files to compressed `.glb` (Draco) | Requires Blender. `blender --background --python scripts/blender/batch_export.py -- <input_dir> <output_dir>` |
| `scripts/blender/optimize_model.py` | Decimate/optimize mesh polycount in an open Blender file | Requires Blender. `blender --background <model.blend> --python scripts/blender/optimize_model.py` |
| `scripts/blender/generate_lods.py` | Generate LOD (Level of Detail) copies for every mesh in an open Blender file | Requires Blender. `blender --background <model.blend> --python scripts/blender/generate_lods.py` |

### Starter templates (`assets/`)

Copy-and-run boilerplate, one per engine. Referenced from `web-3d-engines.md`,
`lightweight-3d.md`, and `immersive-xr.md` when the user wants a working
project instead of a bare code snippet.

| Directory | Contents |
|---|---|
| `assets/threejs_starter/` | Vanilla Three.js scene (`index.html`, `main.js`) |
| `assets/r3f_starter/` | Vite + React Three Fiber project (`package.json`, `src/`) |
| `assets/babylon_starter/` | Vite + Babylon.js project (`package.json`, `src/`) |
| `assets/playcanvas_starter/` | Vanilla PlayCanvas project with camera/input/orbit scripts |
| `assets/aframe_starter/` | Vanilla A-Frame WebXR scene |
| `assets/lightweight_starter/` | Vanilla Zdog/Vanta.js/Vanilla-Tilt starter |
| `assets/pixijs_starter/` | Vanilla PixiJS 2D starter |
| `assets/substance_export_templates/` | 5 export-preset JSONs (glTF, Babylon.js PBR, Three.js optimized, mobile WebGL, packed ORM) importable directly into Substance 3D Painter |

## Related unmassk-design Skills

- `design-scroll` -- scroll-driven 2D motion (GSAP ScrollTrigger, Locomotive
  Scroll, Barba). Combine with web-3d-engines.md when a 3D scene needs to
  react to scroll position.
- `unmassk-design` (core) -- color, typography, layout, accessibility, and
  the motion reference for non-3D animation. Load it for anything that
  isn't specifically 3D/WebGL.

## Attribution

Condensed from **claudedesignskills** by freshtechbro (Apache 2.0):
`threejs-webgl`, `react-three-fiber`, `babylonjs-engine`, `playcanvas-engine`,
`aframe-webxr`, `lightweight-3d-effects`, `spline-interactive`, `pixijs-2d`,
`blender-web-pipeline`, `substance-3d-texturing`.
