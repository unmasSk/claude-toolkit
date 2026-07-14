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
  Use when NOT: the request is 2D UI motion with no 3D/WebGL (use
  design-scroll or unmassk-design's motion reference instead), or the request
  is about color/typography/layout with no 3D element (use unmassk-design).
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
