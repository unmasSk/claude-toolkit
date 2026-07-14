# Provenance

This plugin is **original work, not a lift.** The method (the reality-first
pipeline, the two hard gates, the "never invent a measurement" prime directive),
the SKILL.md, and every reference were written from scratch, synthesized from a
verified research pass — not copied file-for-file from any source. There is no
per-file correspondence to an upstream repo.

## What was synthesized, and from where

The research (2026-07-14) surveyed the current best-in-class tooling and existing
Claude skills for CAD / 3D-printing, verified licenses and maturity, and
distilled a shortlist. The design was **informed** by, but not lifted from,
three prior skills:

| Source | URL | License | What it informed |
|---|---|---|---|
| `flowful-ai/cad-skill` | https://github.com/flowful-ai/cad-skill | PolyForm Noncommercial 1.0.0 | The execute → structured-result → self-correct loop shape (mirrored in `cad-patterns.md` and the `scripts/` runner), and the design-review / printability framing. |
| `EdwinjJ1/3d-print-skill` | https://github.com/EdwinjJ1/3d-print-skill | MIT | The manifold3d-backed watertight gate (watertight + normals + volume + no degenerate faces) — the model for `validate_mesh.py`. |
| `andreahaku/openscad_claude_skill` | https://github.com/andreahaku/openscad_claude_skill | MIT | The OpenSCAD reference + print-module-library approach behind the DSL path in `cad-patterns.md`. |

No files from these were copied. `flowful-ai/cad-skill`'s PolyForm Noncommercial
license would restrict redistribution of *its* files — which is why nothing from
it is lifted; only its architectural idea informed our own original text.

## Factual grounding

The tool choices, install steps, iPhone-scan pipeline, and accuracy figures in
the references come from a cited research pass, with each uncertain claim flagged
in-place (e.g. the iPhone 17 Pro accuracy verdict is explicitly marked as
unverified for that specific generation, with the honest limits stated). The
printability numbers are community-consensus starting values, flagged as such —
to be cross-checked against the actual printer/material before being trusted as
gate thresholds.

## Reconciling drift

If an upstream tool or referenced skill changes materially, re-run the research
pass, diff against the current references, and fold in genuinely new facts —
keeping every accuracy/spec claim sourced, never asserted from memory.
