---
name: unmassk-cad
description: >
  Use when the user asks to "design a 3D-printable part", "make a case for X",
  "make a bracket / mount / stand / holder / enclosure", "model a part in CAD",
  "CAD by code", "parametric part", "generate an STL", "turn a 3D scan into a
  printable model", "fit a part to a real object", "check printability", "make
  this watertight / manifold", "design in CadQuery / OpenSCAD", or "3D print
  this". Also use when a real object must be measured or scanned so a printed
  part fits it. Or mentions any of: CAD, CadQuery, build123d, OpenSCAD, BOSL2,
  STL, 3MF, parametric part, 3D printing, printable, enclosure, bracket, mount,
  holder, snap-fit, tolerance, clearance, wall thickness, 3D scan, LiDAR scan,
  photogrammetry, mesh, watertight, manifold, non-manifold, printability,
  slicer, mesh repair, calipers, fit part, reverse-engineer a part.
  Covers the reality-first pipeline that turns a real object or a stated need
  into a validated printable STL: capture (3D scan / official spec / caliper
  measurement) -> scale calibration -> parametric design as code -> hard
  watertight validation gate -> STL. Uses Blender (driven live) to import,
  measure, and clean 3D scans and to model organic printable shapes; uses
  CadQuery/OpenSCAD for deterministic functional parts. The prime rule: a
  measurement is never invented, only sourced from a scan, a spec, or a caliper.
  Use when NOT: real-time / web / game 3D — WebGL, GPU rendering, animation,
  glTF assets for a website, in-browser scenes — that is a different domain and
  out of scope here. Physical printing (running a slicer / sending G-code to a
  printer) is deferred until a printer exists; this skill stops at a validated
  STL.
version: 1.0.0
---

# unmassk-cad — Reality-First CAD for 3D Printing

Turn a real object, or a stated need, into a **validated printable STL** that
actually fits. This is not "3D art" and it is not web 3D — it is functional and
organic parts headed for a 3D printer, designed from **real measurements**.

The whole skill hangs on one rule. Everything else is machinery around it.

## THE PRIME DIRECTIVE — never invent a measurement

A printed part that is 1 mm off does not fit. So **every dimension that matters
must come from a verifiable source**, never from memory or a guess:

1. **Caliper** (hand-measured) — the source of truth for any *fit-critical*
   dimension: port cutouts, clip lips, screw bosses, wall clearances, anything
   that mates.
2. **3D scan** — the source for *overall shape / contour* only (organic curves,
   silhouettes). A scan is never trusted for a snug dimension.
3. **Official spec sheet** — for a known product, a starting envelope (usually
   bounding-box, rarely exact contours).

If a dimension is not from one of these, **stop and get it** — do not proceed on
a guessed number. A guessed millimetre is a part that does not fit: a real,
physical, silent failure. This is the "system does not harm itself" rule applied
to the physical world.

## The pipeline (two hard gates)

```
1. CAPTURE        user scans (Scaniverse) / measures (caliper) / names a product   [user]
2. IMPORT + ⛔GATE: SCALE   import scan into Blender, calibrate scale against a       [claude]
                  known caliper reading — DO NOT ADVANCE until scale is verified
3. DIMENSION RULE fit-critical dims = caliper (truth); scan = shape only            [claude]
4. DESIGN         parametric part as code (CadQuery / OpenSCAD) -> STL              [claude]
5. ⛔GATE: WATERTIGHT   trimesh / manifold3d: manifold, correct normals, positive    [claude]
                  volume, no degenerate faces — a broken STL DOES NOT PASS
6. FIT-CHECK      re-import the STL beside the scan mesh in Blender, verify fit     [claude]
7. [SLICE]        deferred — no printer yet; skill stops at a validated STL
```

**Gate at step 2 (scale).** Scan meshes lie about scale: USDZ import ignores the
embedded `metersPerUnit`, and OBJ/PLY carry no units at all (Scaniverse exports
in metres, others in millimetres). Never trust an imported dimension until you
have measured a known feature on the mesh, compared it to a caliper reading of
that same feature, and applied the correction. Skipping this is the classic
silent scale failure.

**Gate at step 5 (watertight).** An STL that is non-manifold, has inverted
normals, zero/negative volume, or degenerate faces will fail in a slicer or
print as garbage. This gate is a hard stop, not a warning.

## The toolset (canonical — installed by the START setup step)

All open source on the computer. The setup step (see `references/setup.md`)
installs it; do not assume it is present — check, and install if missing.

| Role | Tool | Install |
| --- | --- | --- |
| CAD by code (primary) | **CadQuery** (+ build123d) | `pip install cadquery build123d` |
| Mesh validation gate | **trimesh** + **manifold3d** | `pip install trimesh manifold3d` |
| Measure / clean / organic | **Blender** (+ Blender MCP, `uv`) | `brew install --cask blender`; `brew install uv` |
| CAD by DSL (optional) | **OpenSCAD** + BOSL2 | `brew install --cask openscad` |
| Mesh repair (optional) | **admesh** | `brew install admesh` |
| Slicer (deferred) | PrusaSlicer / OrcaSlicer | when a printer exists |

Off-computer, manual: the **iPhone scan app (Scaniverse)** — the user installs
it and hands over the mesh — and a **caliper** (hardware). Claude never captures
the scan directly; it works live from the mesh the user delivers.

## Blender: integrated, driven live, with a guard

Blender is used *inside* this skill (not a separate skill) for two jobs: (a)
importing/measuring/cleaning scans, (b) organic printable modelling. It is
driven live over an MCP bridge (see `references/blender-mcp.md`).

The Blender MCP runs **arbitrary Python** inside Blender. This project's threat
model is "the system must not harm itself," not an external attacker — so the
guard is scoped to that: **never let a Blender operation write outside the
project's working directory, and save before running any generated script.** Not
attacker-hardening; self-harm prevention.

## CAD-as-code needs no MCP

The parametric side (CadQuery/OpenSCAD) is deterministic and testable: write a
script, run it with Bash, inspect the STL, iterate. That is the whole "live"
loop for design — no MCP needed. Keep exactly **one** live MCP surface (Blender),
where interactive viewport inspection actually earns it.

## When to read which reference

- `references/scan-pipeline.md` — capture apps, iPhone→Mac transfer, import,
  the scale-calibration procedure. Read before touching a scan.
- `references/printability.md` — wall thickness, clearances, overhangs, bridges,
  chamfer-vs-fillet. Read before finalising any part's dimensions.
- `references/blender-mcp.md` — Blender MCP setup, the working-dir guard, and
  the measure/clean operations. Read before driving Blender.
- `references/cad-patterns.md` — CadQuery patterns and the OpenSCAD/BOSL2 path.
  Read before writing the parametric part.
- `references/setup.md` — the START setup step: what installs and how.

> Printing itself is out of scope until a printer exists. This skill's finished
> product is a **validated STL** plus the parametric source that made it.
