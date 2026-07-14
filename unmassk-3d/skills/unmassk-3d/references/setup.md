# Setup — the START step of a 3D project

Run this when a 3D-printing project starts. It installs the canonical toolset
and wires the Blender MCP. **Do not assume anything is present — check, then
install what is missing.** The automated installer lives at
`scripts/setup_cad_env.py` (it runs the steps below and reports what it did);
this reference is the human-readable contract of what that script must do.

Everything on the computer here is **open source**.

## 1. Python libraries (pip)

Core (always):

```bash
pip install cadquery build123d trimesh manifold3d
```

- `cadquery`, `build123d` — CAD as code (Apache-2.0), same OCCT kernel.
- `trimesh` (MIT), `manifold3d` (Apache-2.0) — the watertight validation gate.

Optional:

```bash
pip install pymeshfix   # focused hole-repair for closed solids (GPL)
```

## 2. Applications (Homebrew, macOS)

```bash
brew install uv                    # runs the Blender MCP server (Apache/MIT)
brew install --cask blender        # GPL — measure/clean scans, organic modelling
brew install --cask openscad       # optional, GPL — DSL CAD + BOSL2 parts library
brew install admesh                # optional, GPL — STL diagnose/repair CLI
```

BOSL2 (OpenSCAD parts library — threads, gears, snap-fits) is a library, not a
package: clone into the OpenSCAD libraries dir if the DSL path is used.

## 3. Blender MCP (the live bridge)

The `.mcp.json` at the plugin root already declares the server
(`uvx blender-mcp`). The one-time Blender side:

1. Download `addon.py` from `ahujasid/blender-mcp` (MIT).
2. Blender → Preferences → Add-ons → Install… → select `addon.py` → enable
   **"Interface: Blender MCP"**.
3. In Blender's N-panel sidebar, start the MCP connection.

**Blender must be open with the addon connection running every session** — the
MCP does not launch Blender for you. See `references/blender-mcp.md` for the
safety guard.

## 4. Verify (do not trust, check)

```bash
python -c "import cadquery, build123d, trimesh, manifold3d; print('cad env OK')"
uv --version && blender --version
```

If any import fails, install it before proceeding — a half-installed env is a
silent failure waiting to happen mid-design.

## 5. Off-computer / manual (cannot be auto-installed)

- **iPhone scan app — Scaniverse** (App Store). The user installs it and hands
  over the exported mesh; Claude never captures the scan directly.
- **Calipers** — physical hardware; the source of truth for every fit-critical
  dimension. Without them, snug fits cannot be trusted (see
  `references/scan-pipeline.md`).

## 6. Deferred until a printer exists

- A **slicer** (PrusaSlicer — best-documented CLI; or OrcaSlicer — most active;
  both AGPL). Installed only when a printer is chosen, because the slicer profile
  (nozzle, material, tolerances) depends on that printer.
