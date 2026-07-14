# unmassk-3d

**Reality-first CAD for 3D printing.** Design 3D-printable parts — cases,
brackets, mounts, holders, enclosures — that actually *fit real objects*,
because every dimension that matters comes from a real measurement, never an
invented one.

This is not web 3D and not 3D art. It is functional and organic parts headed for
a 3D printer, designed from scans, specs, and calipers.

## The prime directive

**A measurement is never invented — only sourced.** A printed part 1 mm off does
not fit, so every fit-critical dimension comes from a **caliper**, the overall
shape from a **3D scan**, and the starting envelope from an **official spec**. A
guessed millimetre is a part that does not fit: a real, physical, silent failure.

## The pipeline (two hard gates)

1. **Capture** — you scan the object (iPhone + Scaniverse) or measure it.
2. **Import + scale gate** — Claude imports the scan into Blender and calibrates
   the scale against a caliper reading. *Nothing advances on an unverified scale.*
3. **Dimension rule** — fit-critical dims = caliper; scan = shape only.
4. **Design** — parametric part as code (CadQuery/OpenSCAD) → STL.
5. **Watertight gate** — trimesh/manifold3d: manifold, normals, positive volume,
   no degenerate faces. *A broken STL does not pass.*
6. **Fit-check** — re-import the STL beside the scan in Blender, verify the fit.
7. **Print** — deferred: this skill stops at a validated STL. Slicing/printing is
   added when a printer exists.

## What you interact with

You describe a need or hand over a scan, look at the result, and give feedback —
Claude drives the CAD, the validation, and Blender. You provide the two things
no software can: the **scan** (from your phone) and the **caliper numbers** for
anything that must fit.

## Tooling (all open source on the computer)

CadQuery + build123d (CAD as code), trimesh + manifold3d (the watertight gate),
Blender + Blender MCP (measure/clean scans, organic modelling), optional
OpenSCAD + BOSL2 (DSL path, parts library) and admesh (STL repair). Off-computer:
the Scaniverse scan app on the phone and a physical caliper. See
`skills/unmassk-3d/references/setup.md`.

## Honest limits

No iPhone — including the 17 Pro — gives reliable sub-millimetre accuracy from a
scan alone; scans are for shape, calipers for snug fits. The references state the
verified limits and the empirical test to settle accuracy for your own gear,
rather than trusting any spec from memory.

## License

MIT — see `LICENSE`. Method original; stands on open-source tools and was
informed by prior skills — see `CREDITS.md` and `PROVENANCE.md`.
