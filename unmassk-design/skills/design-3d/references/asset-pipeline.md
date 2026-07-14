# 3D Asset Pipeline -- Blender to Web, PBR Texturing

Sources: `blender-web-pipeline/`, `substance-3d-texturing/` (claudedesignskills,
Apache 2.0).

This is the step BEFORE any engine in `references/web-3d-engines.md` renders
anything: getting a modeled, textured asset out of authoring tools (Blender,
Substance Painter) and into a web-ready format (glTF/GLB). Route here first
whenever the request mentions exporting, optimizing, or texturing a model
rather than rendering one that already exists.

## Blender -> glTF/GLB

Why glTF: the universal web 3D interchange format — binary (`.glb`, single
file, recommended) or JSON+bin+textures (`.gltf`), PBR-native, animation and
skinning support, loaded identically by Three.js/R3F, Babylon.js,
PlayCanvas, and A-Frame.

**Target budget for web**: <5MB per model (ideally <1MB), <50k triangles for
real-time, textures at 1024x1024 (2048 max, only for hero/close-up assets).

Manual export (Blender Python console or script):
```python
bpy.ops.export_scene.gltf(
    filepath='/path/to/model.glb',
    export_format='GLB',
    export_apply=True,                          # bake modifiers — do this
    export_draco_mesh_compression_enable=True,   # 60-90% size reduction
    export_draco_mesh_compression_level=6,       # 0-10, 6 = balanced
    export_animations=True,
)
```

Key operations, all via `bpy` (Blender's Python API), scriptable for batch
processing across many `.blend` files:
- **Decimate modifier** (`ratio=0.3-0.5`) to cut polygon count before export
  — always apply, don't ship non-destructive modifiers.
- **Remove doubles / triangulate faces** before export — some engines
  require pure triangles.
- **LOD generation**: duplicate the mesh at 2-3 decreasing ratios
  (`_LOD0`, `_LOD1`, `_LOD2`) for distance-based swapping at runtime.
- **Texture downscale + JPEG for color, PNG for data maps** at export time
  (`export_image_format='JPEG'`, `export_jpeg_quality=85`) — cuts size
  dramatically; normal/metallic/roughness must stay lossless (PNG).
- **Batch export**: run headless with
  `blender --background --python batch_export.py -- /in /out` to process a
  whole directory without opening the GUI (much faster than the GUI path).

Pre-export checklist (the actual failure modes, in order of frequency):
1. Apply all modifiers and transforms (Ctrl+A) — unapplied transforms are
   the #1 cause of models importing at the wrong scale/rotation.
2. Materials use **Principled BSDF** — custom shader nodes don't export;
   anything else silently loses its look on the web.
3. Textures are saved (not packed-only) and paths are relative.
4. Animations are baked to the timeline, not left in unlinked NLA strips.
5. File size still too big after the above -> Draco compression is off, or
   textures weren't downscaled.

Loading the result is identical across engines:
```javascript
// Three.js / R3F
const gltf = useGLTF('/models/exported.glb'); // R3F (drei), auto-cached
// Babylon.js
BABYLON.SceneLoader.ImportMesh('', '/models/', 'exported.glb', scene, cb);
```
Set up a `DRACOLoader` (Three.js) if Draco compression was enabled at export
— the model won't decode without it.

## Substance Painter -- PBR texturing for the web

Workflow: metallic/roughness PBR — `baseColor` (albedo, sRGB), `normal`
(tangent-space), `metallic` (0=dielectric, 1=metal), `roughness`
(0=glossy, 1=matte), plus optional `ambientOcclusion`/`emissive`/`opacity`.

**Export preset for web/glTF**: always "PBR Metallic Roughness" — the
universal format every engine here expects. Padding algorithm: "infinite"
(prevents seam artifacts at UV borders).

Resolution guide (matches the Blender budget above): 512 for background
props, 1024 standard (the web default — start here), 2048 only for
hero/close-up assets, 4096 rarely justified on web.

Channel packing to cut texture count: pack grayscale maps into one RGB
texture — **ORM** (R=Occlusion, G=Roughness, B=Metallic) is the standard
packed format glTF and most engines expect for `metallicRoughnessTexture`.

Python API batch export (for many texture sets at once):
```python
config = {
    "exportPath": "/export/web_textures",
    "defaultExportPreset": preset.url(),  # "PBR Metallic Roughness"
    "exportList": [{"rootPath": ts.name()} for ts in substance_painter.textureset.all_texture_sets()],
    "exportParameters": [{"parameters": {"fileFormat": "png", "bitDepth": "8",
                                          "paddingAlgorithm": "infinite", "sizeLog2": 10}}]  # 1024
}
substance_painter.export.export_project_textures(config)
```

Using exported textures (same pattern regardless of engine):
```jsx
// R3F / drei
const [baseColor, normal, metallicRoughness, ao] = useTexture([...]);
<meshStandardMaterial map={baseColor} normalMap={normal}
  metalnessMap={metallicRoughness} roughnessMap={metallicRoughness} aoMap={ao} />
```
Real pitfalls (in order of how often they bite):
1. **BaseColor washed out** — must be sRGB color space at load
   (`texture.colorSpace = THREE.SRGBColorSpace` in Three.js/R3F).
2. **AO map invisible** — Three.js requires a second UV channel
   (`geometry.attributes.uv2`) for `aoMap` to have any effect at all.
3. **Metallic/roughness channels swapped** — Substance's default (Blue=metallic,
   Green=roughness) already matches glTF; don't remap unless the engine
   says otherwise.
4. **4K textures on web** — the default reflex to "make it look better" is
   the #1 cause of slow loads; 1024 is the right default, 2048 the
   exception, not the rule.

## Related

`references/web-3d-engines.md` for loading the exported glTF and applying
the exported textures at render time — this reference only covers getting
the asset to that point.
