# Credits

`unmassk-3d`'s method and references are original, but the plugin stands on
open-source tools and was informed by prior open work. It would not exist
without:

## Tools it drives (open source)

- **CadQuery** (Apache-2.0) — https://github.com/CadQuery/cadquery — Python
  CAD-as-code, the primary functional-part engine.
- **build123d** (Apache-2.0) — https://github.com/gumyr/build123d — same OCCT
  kernel, companion to CadQuery.
- **trimesh** (MIT) — https://github.com/mikedh/trimesh — mesh I/O and the
  watertight validation layer.
- **manifold3d** (Apache-2.0) — https://github.com/elalish/manifold —
  guaranteed-manifold geometry / boolean gate.
- **Blender** (GPL) — https://www.blender.org — scan measurement/cleanup and
  organic modelling.
- **ahujasid/blender-mcp** (MIT) — https://github.com/ahujasid/blender-mcp — the
  live Blender MCP bridge.
- **OpenSCAD** (GPL) + **BOSL2** (BSD-2-Clause) —
  https://github.com/openscad/openscad , https://github.com/BelfrySCAD/BOSL2 —
  the DSL path and its parts library (threads, gears, snap-fits).
- **admesh** (GPL) — https://github.com/admesh/admesh — STL diagnose/repair.

## Prior Claude-skill work that informed the design

Discovered during research; their *approach* shaped this skill (no files were
lifted — see PROVENANCE.md):

- **flowful-ai/cad-skill** (PolyForm Noncommercial) —
  https://github.com/flowful-ai/cad-skill — the execute → structured-result →
  self-correct loop shape, and the design-review / printability framing.
- **EdwinjJ1/3d-print-skill** (MIT) — https://github.com/EdwinjJ1/3d-print-skill
  — the manifold3d-backed hard validation gate (watertight + normals + volume +
  no degenerate faces).
- **andreahaku/openscad_claude_skill** (MIT) —
  https://github.com/andreahaku/openscad_claude_skill — the OpenSCAD language
  reference and print-module library idea.

## This plugin

`unmassk-3d`'s own text (the method, the pipeline, the references, the scripts)
is licensed MIT — see `LICENSE`.
