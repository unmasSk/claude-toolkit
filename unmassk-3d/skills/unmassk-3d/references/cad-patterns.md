# CAD-as-code patterns

The deterministic side: functional parts written as source, run to produce an
STL, validated, iterated. Read before writing a parametric part.

## Why code, not clicks

A part written as code is **deterministic, diffable, and testable** — you can
assert on its geometry (volume, bounding box, face/edge counts) before it ever
becomes a mesh. That is why fit parts go through CadQuery/OpenSCAD, not a GUI:
the design fits our build → verify → gate loop.

**No MCP needed here.** The live loop is: write script → run with Bash → inspect
the STL / assertions → iterate. Keep exactly one live MCP surface (Blender).

## CadQuery (primary — Python, Apache-2.0)

Pattern: named parameters at the top (every fit-critical value sourced from a
caliper, never invented), build the solid, **assert on geometry**, export.

```python
import os
import cadquery as cq

# --- parameters (fit-critical values come from calipers, not guesses) ---
WALL   = 2.0      # mm, printability minimum respected
CLEAR  = 0.4      # mm, snug-fit tolerance (0.2-0.5)
DEV_W  = 65.3     # mm, CALIPER-measured device width
DEV_H  = 22.1     # mm, CALIPER-measured device height

inner_w = DEV_W + 2 * CLEAR
inner_h = DEV_H + 2 * CLEAR

case = (
    cq.Workplane("XY")
    .box(inner_w + 2 * WALL, inner_h + 2 * WALL, 30)
    .faces(">Z").shell(-WALL)
)

# --- verify BEFORE trusting the mesh ---
vol = case.val().Volume()
assert vol > 0, "empty solid — geometry failed"
bb = case.val().BoundingBox()
assert abs(bb.xlen - (inner_w + 2 * WALL)) < 1e-6, "outer width drifted"

# Export to CADQUERY_OUT when run via run_cadquery.py (it sets that env var);
# falls back to a local name for standalone runs. Keep the path inside the project dir.
cq.exporters.export(case, os.environ.get("CADQUERY_OUT", "case.stl"))
```

Export formats: STL (print), STEP (interchange/CAD), 3MF. STEP is B-rep — prefer
it when the part will be re-edited; STL for slicing.

## build123d (companion — same OCCT kernel)

Interchangeable objects with CadQuery, more "Pythonic" (context-manager blocks).
Use whichever reads cleaner for the part; both assert on native geometry objects.

## OpenSCAD + BOSL2 (the DSL path — optional)

Reach for OpenSCAD when you want its mature parts library **BOSL2**: tested
modules for threads, gears, snap-fits, attachments — exactly the load-bearing
features you should not hand-roll. CLI render is headless:

```bash
openscad -o part.stl part.scad
```

OpenSCAD is CSG-first and manifold-by-construction, which pairs well with the
watertight gate; its weakness vs CadQuery is weaker in-process testability (you
assert via the exported mesh, not a live object).

## The iterate loop (from the flowful-ai/cad-skill pattern)

Write script → run → capture a **structured result** (did it run? volume? bbox?
validator pass?) → Claude reads that and self-corrects → repeat. This is the
same execute → JSON → iterate loop the toolkit uses elsewhere, applied to CAD.
The `scripts/` runner + watertight validator implement the machine side of it.

## Non-negotiable

Every fit-critical parameter carries a comment naming its source (a caliper
reading, an insert datasheet, a spec sheet). A number with no sourced origin is
a bug — it is an invented measurement, and invented measurements do not fit.
