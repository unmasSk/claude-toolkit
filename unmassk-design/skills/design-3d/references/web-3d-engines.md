# Web 3D Engines -- Three.js, React Three Fiber, Babylon.js, PlayCanvas

Sources: `threejs-webgl/`, `react-three-fiber/`, `babylonjs-engine/`,
`playcanvas-engine/` (claudedesignskills, Apache 2.0).

These four solve the same problem (real-time 3D in the browser) with
different trade-offs. Pick one per the table in SKILL.md, then use the
patterns below -- don't mix engines in one scene.

## Three.js -- the default, code-first choice

What it is: the industry-standard low-level WebGL/WebGPU library. Scene
graph of Scene -> Camera + Lights + Meshes(Geometry+Material) -> Renderer.

When to use it: maximum control, custom GLSL shaders, no React in the
project, or every other engine here is "built on Three.js anyway" (A-Frame
and Vanta.js both are) and the abstraction they add isn't wanted.

Minimal scene:
```javascript
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(75, innerWidth/innerHeight, 0.1, 1000);
camera.position.set(0, 2, 5);
const renderer = new THREE.WebGLRenderer({ antialias: true });
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;

const clock = new THREE.Clock();
function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);
}
animate();
```

Key patterns:
- **Material choice**: `MeshBasicMaterial` (unlit/debug) < `MeshLambertMaterial`
  (cheap, mobile) < `MeshPhongMaterial` (specular) < `MeshStandardMaterial`
  (PBR, default choice) < `MeshPhysicalMaterial` (clearcoat/transmission).
- **InstancedMesh** for hundreds/thousands of identical objects — one draw
  call instead of N. Set matrices via `setMatrixAt` + `instanceMatrix.needsUpdate = true`.
- **glTF loading**: `GLTFLoader` + `DRACOLoader` (set decoder path) for
  compressed models; traverse `gltf.scene` to enable `castShadow`/`receiveShadow`;
  drive `gltf.animations` through an `AnimationMixer`.
- **Shadows**: enable on renderer (`shadowMap.enabled`, `PCFSoftShadowMap`),
  on the light (`castShadow`, `shadow.mapSize`), and on meshes
  (`castShadow`/`receiveShadow`) -- all three or nothing renders.
- **Color space**: always set `texture.colorSpace = THREE.SRGBColorSpace`
  and `renderer.outputColorSpace = THREE.SRGBColorSpace`, or colors wash out.
- **GSAP integration**: `gsap.to(camera.position, {...})` /
  `gsap.to(mesh.rotation, {...})` works directly on Three.js objects.

Pitfalls: forgetting `camera.updateProjectionMatrix()` on resize; creating
geometry inside the animation loop; z-fighting (fix: widen near/far plane
gap, or `polygonOffset`); not disposing geometry/material/texture on teardown.

## React Three Fiber (R3F) -- Three.js as JSX

What it is: a React renderer for Three.js. `<mesh>`, `<boxGeometry>`,
`<meshStandardMaterial>` map 1:1 to Three.js classes; props map to
constructor args (`args={[...]}`) or setters (`position={[x,y,z]}`).

When to use it: the project is already React (esp. Next.js) and 3D needs to
compose with component state/hooks rather than live in an imperative script.

Minimal scene:
```jsx
import { Canvas } from '@react-three/fiber';
import { useFrame } from '@react-three/fiber';
import { useRef } from 'react';

function Box() {
  const ref = useRef();
  useFrame((state, delta) => { ref.current.rotation.y += delta; });
  return (
    <mesh ref={ref}>
      <boxGeometry args={[1, 1, 1]} />
      <meshStandardMaterial color="hotpink" />
    </mesh>
  );
}

export default () => (
  <Canvas camera={{ position: [0, 0, 5], fov: 75 }}>
    <ambientLight intensity={0.5} />
    <Box />
  </Canvas>
);
```

Key patterns:
- **Drei is not optional in practice**: `OrbitControls`, `Environment`
  (HDRI in one line), `useGLTF`/`useTexture` (cached loaders), `Html`
  (DOM overlay in 3D space), `ScrollControls`/`useScroll` (scroll-driven 3D),
  `Detailed` (LOD), `PerformanceMonitor`/`AdaptiveDpr` (auto quality).
- **useLoader / useGLTF** cache automatically and integrate with
  `<Suspense fallback={...}>` — always wrap async 3D content in Suspense.
- **On-demand rendering**: `<Canvas frameloop="demand">` + manual
  `invalidate()` when nothing is animating continuously — saves battery.

Pitfalls (R3F-specific, on top of Three.js's own):
- **Never `setState` inside `useFrame`** — mutate `ref.current` directly,
  or every frame triggers a React re-render.
- **Don't create objects in render** (`position={new THREE.Vector3(...)}`)
  — use array shorthand `position={[x,y,z]}` or `useMemo`.
  Never call `useThree()` outside a `<Canvas>` child — it will crash.
- **Don't conditionally mount/unmount stages** (`{stage===1 && <A/>}`) —
  toggle a `visible` prop instead; mount/unmount is expensive.

## Babylon.js -- the "batteries included" alternative

What it is: a full engine (Engine + Scene) with built-in physics (Havok),
GUI system, node-material visual editor, and a first-class WebXR helper.
Heavier than Three.js but trades setup code for included features.

When to use it: the project needs physics, an in-scene GUI, or turnkey
WebXR without assembling it from separate libraries — or the team prefers
its Playground-first workflow.

Minimal scene:
```javascript
const engine = new BABYLON.Engine(canvas, true);
const scene = new BABYLON.Scene(engine);
const camera = new BABYLON.ArcRotateCamera('cam', -Math.PI/2, Math.PI/2.5, 15, BABYLON.Vector3.Zero(), scene);
camera.attachControl(canvas, true);
new BABYLON.HemisphericLight('light', new BABYLON.Vector3(0,1,0), scene);
BABYLON.MeshBuilder.CreateSphere('sphere', { diameter: 2 }, scene);
engine.runRenderLoop(() => scene.render());
window.addEventListener('resize', () => engine.resize());
```

Key patterns:
- **PBRMaterial** (metallic/roughness or specular workflow) is the standard
  material; `StandardMaterial` for cheaper non-PBR needs.
- **Physics**: `enablePhysics()` with `HavokPlugin`, then
  `PhysicsAggregate(mesh, ShapeType, { mass, restitution }, scene)` — mass 0
  = static. Must call `attachControl` on any camera or input does nothing.
- **Instancing**: `mesh.createInstance()` for standard instances, or
  `thinInstanceSetBuffer` for very large counts (thousands).
- **WebXR in one call**: `scene.createDefaultXRExperienceAsync({ floorMeshes })`
  sets up VR/AR with teleportation and controller input.
- **Scene optimizer**: `SceneOptimizer` + `SceneOptimizerOptions` auto-degrades
  quality (shadows, post-processing, textures) to hit a target FPS.

Pitfalls: forgetting `.dispose()` on removed meshes/scenes/engine (leak);
one draw call per mesh — use instances instead of loops creating meshes;
enabling physics components before `scene.enablePhysics()` throws.

## PlayCanvas -- the game-engine / editor-first choice

What it is: entity-component-system (ECS) architecture with an optional
web-based visual editor. Entities are containers; components (`model`,
`camera`, `light`, `rigidbody`) add behavior.

When to use it: a game-shaped project, a team that wants a non-technical
editor workflow, or performance-critical apps where ECS batching helps.

Minimal scene:
```javascript
const app = new pc.Application(canvas);
app.setCanvasFillMode(pc.FILLMODE_FILL_WINDOW);
app.setCanvasResolution(pc.RESOLUTION_AUTO);

const camera = new pc.Entity('camera');
camera.addComponent('camera');
camera.setPosition(0, 2, 5);
app.root.addChild(camera);

const light = new pc.Entity('light');
light.addComponent('light', { type: pc.LIGHTTYPE_DIRECTIONAL });
app.root.addChild(light);

const cube = new pc.Entity('cube');
cube.addComponent('model', { type: 'box' });
app.root.addChild(cube);

app.on('update', (dt) => cube.rotate(10*dt, 20*dt, 30*dt));
app.start(); // nothing renders without this
```

Key patterns:
- **Custom scripts**: `pc.createScript('name')` with `initialize`/`update`/
  `destroy` lifecycle methods and editor-exposed `attributes` — PlayCanvas's
  equivalent of a component class.
- **Physics needs Ammo.js loaded first** (`rigidbody` + `collision`
  components throw "Ammo is not defined" otherwise).
- **Object pooling** is the idiomatic pattern for spawn/despawn-heavy scenes
  (bullets, particles) — reuse entities instead of destroy/create.
- **Editor export**: projects built in the visual editor export a
  `config.json` + scene hierarchy that `app.scenes.loadSceneHierarchy()` loads.

Pitfalls: forgetting `app.start()` (renders nothing, no error); destroying
entities mid-`update` iteration (mutates the array being iterated — mark
for deletion, destroy in `postUpdate` instead); confusing local vs world
position when parenting entities.

## Choosing between them -- quick recap

| Three.js | R3F | Babylon.js | PlayCanvas |
|---|---|---|---|
| Max control, custom shaders | React-native 3D | Physics/GUI/XR built in | ECS, editor workflow |
| No React needed | Needs React | Heavier bundle | Own asset/editor pipeline |
