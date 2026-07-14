# Scan pipeline — capture → transfer → import → scale gate

How a real object becomes a correctly-scaled mesh Claude can measure. Read this
before touching any scan. The scale-calibration step is a **hard gate**, not
optional.

## 1. Capture (user, phone in hand)

**App: Scaniverse** (primary) — free, no export paywall, no watermark,
LiDAR-first, exports OBJ/PLY/USDZ. **KIRI Engine** (secondary) — photogrammetry,
better for small/fine/glossy features, exports STL natively.

Mode by object size:

- Object **> ~10 cm** → Scaniverse **LiDAR mode** (real-time mesh).
- Object **< ~10 cm** or fine/glossy/thin features → **photogrammetry** (KIRI, or
  Polycam) — below ~10 cm, LiDAR resolution degrades and small features are lost.

Export as **OBJ** (universal, Blender-native). Note the app's unit convention —
it bites at import (see §3): **Scaniverse exports in metres, Polycam in
millimetres.**

## 2. Transfer iPhone → Mac (user)

**AirDrop** from the app's share sheet → the file lands in `~/Downloads`. No
account, no cable (scan files live in the app sandbox and are not exposed over
USB). iCloud Drive ("Save to Files") is the fallback.

## 3. Import into Blender + the SCALE GATE (Claude, live via MCP)

Blender imports OBJ/PLY natively and USD/USDZ natively. **Never trust the
imported scale:**

- **USDZ**: Blender's USD importer **ignores the embedded `metersPerUnit`** and
  assumes metres — a scan can silently import 100× off (verified: Blender issue
  #100448).
- **OBJ/PLY**: no embedded units at all — the app's raw numbers become Blender's
  generic "1 unit".

**Mandatory calibration procedure (the gate):**

1. Identify a feature on the object with a clean, measurable dimension (a flat
   edge, a port width).
2. User measures that same feature with **calipers** → the ground-truth mm.
3. Claude measures it on the imported mesh (N-panel → Item → Dimensions, or the
   Measure tool).
4. Compute the correction factor = caliper_mm / mesh_measurement, scale the mesh
   by it, then **apply the scale** (`Ctrl+A` → Scale) so it bakes in.
5. Re-measure to confirm. **Do not proceed to design until scale is verified.**

## 4. The dimension rule (carries into design)

- **Fit-critical dimensions** (anything that mates — port cutouts, clip lips,
  screw bosses, wall clearances) → **caliper values**, always. Overwrite the
  scan's numbers for these regions; the scan is shape-reference only there.
- **Overall shape / organic contour** → the scan mesh.

## 5. Accuracy — the honest limits

Grounded in verified research, not memory:

- No iPhone (including the **iPhone 17 Pro**) delivers reliable sub-millimetre or
  even ~1 mm accuracy **from the scan alone**. Published figures (older-gen, best
  available proxy) sit around **1–3 cm**, degrading under ~10 cm object size.
- A professional-scanner vendor's direct **iPhone 17 Pro vs 15 Pro** comparison
  found **no measurable scanning-accuracy improvement** between generations
  (moderate confidence — source named and on-point, article body not directly
  read; treat as an anchor, not proof).
- For **small objects the accuracy driver is photogrammetry (the cameras), not
  the LiDAR** — so the 17 Pro's better cameras help there, but the mechanism is
  images, not depth-sensing.
- A snug printed fit needs **0.2–0.5 mm** tolerance. Nothing above supports
  trusting a raw scan at that tolerance → that is exactly why fit-critical
  dimensions come from calipers.

**Where scanning earns its keep:** organic / complex-curved surfaces (an
ergonomic shell hugging an irregular body) where hand-measuring the full 3D form
is impractical. **Where it disappoints:** any snug/interference fit derived
purely from scan geometry.

**Settle it empirically for THIS phone + THESE parts:** scan something, measure
it with calipers, compare. Decide from your own data — never from memory or from
figures measured on older phones.
