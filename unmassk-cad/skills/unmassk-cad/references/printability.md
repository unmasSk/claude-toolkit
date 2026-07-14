# Printability rules (FDM)

Design rules for parts that actually print and fit on a fused-deposition (FDM)
printer. Read before finalising any part's dimensions.

> **These are community-consensus starting values, not a spec.** They converge
> across independent sources (EdwinjJ1/3d-print-skill, flowful-ai/cad-skill, and
> general FDM practice) but the real thresholds depend on the specific
> **printer, nozzle, and material**. Cross-check against the actual machine
> before hardcoding any of these as a gate. Until a printer exists, treat them
> as sane defaults.

## Core numbers

| Rule | Value | Why |
| --- | --- | --- |
| Wall thickness | **2 mm nominal, 1.2 mm minimum** | thinner walls are fragile / fail to print solidly |
| Hole/pin clearance | **0.3 mm** | nominal fit; printed holes shrink |
| Fit tolerance (snug/mating) | **0.2–0.5 mm** gap | too tight = won't assemble; too loose = rattles |
| Overhang angle | **≤ 45° from vertical** | steeper needs supports |
| Bridge span | **≤ ~20 mm** unsupported | longer sags |
| Bottom edges | **chamfer, not fillet** | a bottom fillet needs supports; a chamfer prints clean |
| First-layer contact | flat, generous | adhesion; avoid tiny footprints |

## Design-for-print habits

- **Orient for strength and supports**: layer lines are the weak axis — put
  loads across layers, not along them. Minimise overhangs by choosing the print
  orientation before finalising geometry.
- **Avoid tiny unsupported features** and knife-edges — they don't survive the
  nozzle.
- **Screw bosses / heat-set inserts**: use known insert specs (from the insert
  datasheet, a caliper on the real insert) — never a guessed diameter.
- **Snap-fits / living hinges**: these are load-bearing and tolerance-sensitive
  → their dimensions come from calipers on the mating part, and benefit from
  BOSL2's tested modules if using OpenSCAD (see `references/cad-patterns.md`).

## The validation gate (enforced, not advisory)

Before a part is "done", its STL passes the watertight gate — manifold, correct
normals, positive volume, no degenerate faces (see the `scripts/` validator and
`references/blender-mcp.md`). A part that violates these prints as garbage or
fails in the slicer: catch it here, not on the print bed.
