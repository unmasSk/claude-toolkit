# Immersive XR -- A-Frame / WebXR

Source: `aframe-webxr/` (claudedesignskills, Apache 2.0).

## What it is, when to use it

A-Frame is a declarative, HTML-first framework for VR/AR/WebXR, built on
Three.js underneath. Entities are `<a-entity>` tags with component
attributes (`geometry="..."`, `material="..."`); primitives (`<a-box>`,
`<a-sphere>`) are shorthand for common entity+component combos.

Use it when the deliverable actually runs in a headset, needs WebXR
hit-testing to place objects in the real world, is a 360 photo/video
viewer, or the team wants to prototype 3D with HTML instead of JS. If the
target is just a desktop 3D scene with no VR/AR requirement, use
`references/web-3d-engines.md` instead — A-Frame's declarative layer is
overhead when headset support isn't needed.

## Core setup

```html
<script src="https://aframe.io/releases/1.7.1/aframe.min.js"></script>
<a-scene>
  <a-box position="-1 0.5 -3" color="#4CC3D9"></a-box>
  <a-sphere position="0 1.25 -5" radius="1.25" color="#EF2D5E"></a-sphere>
  <a-sky color="#ECECEC"></a-sky>
</a-scene>
```

`<a-scene>` auto-injects a default camera (`0 1.6 0`), mouse look-controls,
and WASD movement — no boilerplate needed for a walkable scene.

## Key patterns

- **VR camera rig + controllers**: wrap the camera in an `<a-entity id="rig">`
  so movement applies to the rig, not the camera directly; add
  `hand-controls="hand: left/right"` + `laser-controls` entities for
  controller rays and pointing.
- **AR hit-testing**: `<a-scene webxr="optionalFeatures: hit-test, dom-overlay">`
  plus `ar-hit-test="target: #object"` places a glTF model on a detected
  real-world surface; listen for `ar-hit-test-start` / `-achieved` / `-select`
  events to drive UI instructions.
- **Animations**: the `animation` component (`property`, `to`, `dur`, `loop`,
  `dir: alternate`); use `animation__name` (double underscore) to attach
  multiple independent animations to one entity.
- **Custom components**: `AFRAME.registerComponent('name', { schema, init, tick })`
  — `init` runs once, `tick(time, timeDelta)` runs every frame. This is
  A-Frame's escape hatch for anything the declarative API doesn't cover.
- **Assets**: preload everything inside `<a-assets>` (images, videos, audio,
  `<a-asset-item>` for glTF/OBJ, `<a-mixin>` for reusable component sets) —
  reference by `#id`, never inline the raw path in the entity.
- **Direct Three.js escape hatch**: `entity.object3D` is the underlying
  Three.js object — use it for GSAP animation
  (`gsap.to(box.object3D.position, {...})`) or anything A-Frame doesn't expose.

## Pitfalls

- **Entities invisible**: usually positioned behind the camera, scale 0,
  or opacity 0 — not a rendering bug.
- **Click/hover not firing**: needs a `raycaster` — either a `<a-cursor>`
  inside the camera (`<a-camera><a-cursor raycaster="objects: .interactive"></a-cursor></a-camera>`)
  or gaze/mouse won't hit anything.
- **Mobile VR performance**: cap `renderer="maxCanvasWidth: 1920; maxCanvasHeight: 1920"`,
  keep lights to 2 (ambient + one directional — lights are expensive on
  mobile GPUs), use low-poly primitives (`segments-width`/`segments-height`).
- **Z-fighting** between coplanar surfaces: offset positions slightly or set
  `object3D.renderOrder`.
- **Asset CORS/loading failures**: add `crossorigin="anonymous"` on external
  images; listen for the `<a-assets>` `loaded`/`timeout` events before using
  assets, rather than assuming they're ready.

## Related

`references/web-3d-engines.md` for non-XR 3D (same underlying Three.js, no
declarative layer). GSAP integration works directly on `object3D` as shown
above.
