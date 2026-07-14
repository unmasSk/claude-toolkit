# Style: Industrial Brutalism & Tactical Telemetry

Source: `industrial-brutalist-ui` skill by leonxlnx (MIT), condensed.

Raw, mechanical interfaces that fuse Swiss typographic print with military
terminal aesthetics. Rigid grids, extreme type-scale contrast, utilitarian
color, simulated analog degradation. Fits data-heavy dashboards, portfolios,
or editorial sites that want to feel like declassified blueprints.

## Pick ONE archetype, never mix

### A. Swiss Industrial Print (light mode)
1960s corporate identity systems and heavy-machinery manuals. High-contrast
light substrate, monolithic heavy sans-serif, unforgiving grid with visible
dividing lines, oversized viewport-bleeding numerals, primary red as the
only alert/accent color.

### B. Tactical Telemetry / CRT Terminal (dark mode)
Classified military databases, legacy mainframes, aerospace HUDs. Dark mode
only, high-density tabular data, monospace dominance, ASCII framing
(crosshairs, brackets), simulated hardware limitations (phosphor glow,
scanlines, dithering).

Choose one substrate per project and hold it -- never mix light and dark
substrate within the same interface.

## Typography

- **Macro (structural headers):** Neo-grotesque/heavy sans -- Neue Haas
  Grotesk Black, Inter Black, Archivo Black, Monument Extended. Fluid scale
  via `clamp(4rem, 10vw, 15rem)`. Tracking `-0.03em` to `-0.06em` (tight,
  negative). Leading `0.85`-`0.95`. Uppercase only.
- **Micro (data/telemetry):** Monospace -- JetBrains Mono, IBM Plex Mono,
  Space Mono, VT323. Fixed small scale `10px`-`14px` / `0.7rem`-`0.875rem`.
  Tracking `0.05em`-`0.1em` (generous, typewriter feel). Leading `1.2`-`1.4`.
  Uppercase, used for metadata, nav, unit IDs, coordinates.
- **Textural disruption (sparingly):** High-contrast serif (Playfair
  Display, EB Garamond) subjected to halftone/1-bit dithering to degrade
  vector perfection against the clean sans.

## Color

Gradients, soft drop shadows, and translucency are prohibited. Colors
simulate physical media or primitive emissive displays.

**If Swiss Industrial Print (light):**
- Background `#F4F4F0` or `#EAE8E3` (matte, unbleached paper)
- Foreground `#050505`-`#111111` (carbon ink)
- Accent `#E61919` / `#FF2A2A` (aviation red) -- the only accent

**If Tactical Telemetry (dark):**
- Background `#0A0A0A` / `#121212` (avoid pure `#000000`)
- Foreground `#EAEAEA` (white phosphor)
- Accent same red as above, same rule (only accent)
- Terminal green `#4AF626` -- optional, one single status element max,
  never a general text color

## Layout

- CSS Grid, strict tracks and intersections -- elements do not float.
- Visible compartmentalization: `1px`-`2px solid` borders delineate zones;
  full-width `<hr>` rules segregate operational units.
- Bimodal density: tight monospace metadata clusters vs. vast negative
  space framing macro-typography -- no in-between.
- No `border-radius` anywhere. All corners are 90 degrees.

## Components and symbology

- ASCII framing: `[ DELIVERY SYSTEMS ]`, `< RE-IND >`, directional `>>>`,
  `///`, `\\\\`.
- Registration/copyright/trademark symbols (`® © ™`) used as geometric
  structural elements, not legal text.
- Crosshairs (`+`) at grid intersections, repeating vertical lines
  (barcode look), warning stripes, randomized unit strings (`REV 2.6`,
  `UNIT / D-01`).

## Analog degradation effects

- Halftone/1-bit dithering on images or large serif type -- via
  pre-processing or `mix-blend-mode: multiply` with SVG radial dot overlays.
- CRT scanlines (dark mode): `repeating-linear-gradient(0deg, transparent,
  transparent 2px, rgba(0,0,0,0.1) 2px, rgba(0,0,0,0.1) 4px)`.
- A single low-opacity SVG noise/static filter on the DOM root for unified
  physical grain across both modes.

## Engineering notes

- Use `display: grid; gap: 1px;` with contrasting parent/child backgrounds
  to get razor-thin dividing lines without manual border declarations.
- Prefer semantic tags that match the telemetry framing: `<data>`,
  `<samp>`, `<kbd>`, `<output>`, `<dl>`.
- Reserve `clamp()` for macro-typography only -- it's what lets the massive
  scale hold up across viewports without breaking the grid.
