# Blender via MCP — setup, guard, operations

Blender is driven **live** over an MCP bridge for two jobs: (a) import / measure
/ clean 3D scans, (b) organic printable modelling. Read before driving Blender.

## Which MCP server

**`ahujasid/blender-mcp`** (MIT, most mature — 24k★), run as `uvx blender-mcp`.
It is **not** bundled in the plugin's `.mcp.json` — it is installed **on demand**
the first time this skill needs it (see "Activate the MCP" below), so it never
hangs connected when you are not doing CAD. Alternatives, for reference:

- **Official Blender Lab MCP** (`blender.org/lab`) — genuinely official but
  experimental ("Lab") and self-describes as unguarded; its exact state was not
  directly verifiable. Watch it; not the default yet.
- **`PatrykIti/blender-ai-mcp`** (Apache-2.0) — a *curated* fixed tool set
  instead of raw arbitrary-code execution. Prefer it if raw `execute_blender_code`
  is ever unwanted, at the cost of flexibility.

## Activate the MCP (on-demand — Claude drives this)

The Blender MCP is **not connected by default**. The first time this skill needs
it, Claude registers it, then tells the user to restart. Claude runs these steps
and guides the user — the user only restarts when told.

**Before using this tool, check its `mcp__blender__*` tools are actually
available.** If they are not, the server is not installed/loaded — run the
registration below and tell the user to restart; never proceed as if Blender
were available without the tool actually present.

1. **Register the server** (once, user scope — available in every project):
   ```
   claude mcp add blender --scope user -- uvx blender-mcp
   ```
2. **Restart Claude Code.** MCP servers only start at boot; there is no hot
   activation. After the restart the `blender` tools are available.
3. **API key:** none — Blender MCP needs no key.

This is the standard on-demand shape for every MCP in the toolkit: *register →
restart → (key if needed)*. It replaces bundling the server in `.mcp.json`, which
would connect it at every boot whether or not you do CAD.

## One-time setup

(These are the Blender-side steps, separate from registering the MCP above.)

1. `brew install uv`
2. Download `addon.py` from `ahujasid/blender-mcp`.
3. Blender → Preferences → Add-ons → Install… → `addon.py` → enable
   **"Interface: Blender MCP"**.
4. Start the connection in Blender's N-panel sidebar.

**Every session**: Blender must be open with the addon connection running. The
MCP does not launch Blender — if the connection is not up, tool calls fail.

## The guard (self-harm prevention, not attacker defence)

The MCP exposes **`execute_blender_code`** — arbitrary Python inside Blender.
This project's threat model is "the system must not harm itself," so the guard
is scoped to that, not to a hostile attacker:

- **Never let a Blender operation write outside the project's working
  directory.** Resolve every output path and confirm it is inside the project
  before writing. A stray absolute path is how a "safe" export lands somewhere it
  shouldn't.
- **Save before running any generated script** — a crash mid-operation must not
  cost unsaved work.
- Keep operations idempotent where possible; prefer named objects so a re-run
  doesn't silently duplicate geometry.

## Core operations

**Import a scan**
- OBJ/PLY/USD/USDZ import natively. Immediately run the scale gate (see
  `references/scan-pipeline.md`) — never trust the imported scale.

**Measure**
- N-panel → Item → Dimensions for a bounding box; the Measure tool for
  point-to-point. Always after scale calibration, never before.

**Clean a scan mesh**
1. Merge by Distance (weld duplicate verts).
2. Non-manifold check: Select → All by Trait → Non-Manifold (should select
   nothing).
3. Recalculate normals outside.
4. Decimate modifier (preserves silhouette) — or Voxel Remesh only if topology
   is too broken for Decimate.
5. Enable the **3D Print Toolbox** addon and run its manifold / thin-wall check
   before export.

**Fit-check**
- Re-import the CAD-generated STL beside the cleaned scan, position it, and
  visually/boolean-check the fit — report gaps or interferences.

**Export**
- STL/3MF for print; confirm the output path is inside the working directory.
