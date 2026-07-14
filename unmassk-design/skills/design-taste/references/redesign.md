# Redesign: Audit an Existing Project to Premium

Source: `redesign-existing-projects` skill by leonxlnx (MIT), condensed.

Upgrades an existing website/app to premium quality without breaking
functionality. Works with any CSS framework or vanilla CSS. Different from
starting fresh: you are improving what's there, not replacing it.

## Workflow

1. **Scan** -- read the codebase, identify framework, styling method
   (Tailwind, vanilla CSS, styled-components...), current patterns.
2. **Diagnose** -- run the audit below, list every generic pattern, weak
   point, missing state found.
3. **Fix** -- apply targeted upgrades within the existing stack. Do not
   rewrite from scratch.

## Audit checklist by category

**Typography** -- browser-default/Inter-everywhere fonts (replace with
`Geist`/`Outfit`/`Cabinet Grotesk`/`Satoshi`, or serif+sans pairing for
editorial); flat headlines (increase size, tighten tracking, reduce
leading); body text too wide (cap ~65ch); only Regular+Bold weights used
(add Medium/SemiBold); numbers in proportional font on data UIs (use mono
or `font-variant-numeric: tabular-nums`); missing letter-spacing tuning;
all-caps subheaders everywhere (try lowercase italics or sentence case);
orphaned words (`text-wrap: balance`/`pretty`).

**Color and surfaces** -- pure `#000000` bg (use off-black/charcoal/tinted
navy); oversaturated accents (keep saturation below 80%); more than one
accent color (pick one); mixed warm/cool grays (pick one family); purple/
blue "AI gradient" aesthetic (replace with neutral base + one considered
accent); generic untinted `box-shadow` (tint to background hue); flat
zero-texture design (add subtle noise/grain); perfectly even 45deg
gradients (break with radial/mesh); inconsistent light direction across
shadows; a random dark section dropped into an otherwise light page (or
vice versa -- either commit to full dark mode or vary shade within the same
palette, never jump to `#111` mid-page); empty flat sections with no depth
(add background imagery/patterns/ambient gradients --
`https://picsum.photos/seed/{name}/1920/1080` when no real asset exists).

**Layout** -- everything centered/symmetrical (break with offset margins,
mixed ratios); three equal card columns (the most generic AI layout --
replace with zig-zag, asymmetric grid, horizontal scroll, masonry);
`height: 100vh` full-screen sections (use `min-height: 100dvh`); flexbox
percentage math (use CSS Grid); no max-width container (add
1200-1440px constraint); equal-height cards forced by flexbox (allow
variable height or masonry); uniform border-radius everywhere (vary --
tighter inner, softer outer); no overlap/depth (use negative margins);
symmetrical vertical padding (bottom often needs to be slightly larger);
dashboard always has a left sidebar (try top nav or command menu); missing
whitespace (double it); buttons not bottom-aligned across card groups
(pin CTAs to bottom); feature lists starting at different Y positions
across columns (align to fixed-height title/price blocks); misaligned
baselines across side-by-side elements; mathematically-centered-but-
optically-wrong alignment (nudge 1-2px by eye).

**Interactivity and states** -- no hover states; no active/pressed feedback
(add `scale(0.98)`/`translateY(1px)`); instant transitions (add 200-300ms);
missing focus ring (accessibility requirement, not optional); generic
circular spinners (use skeleton loaders matching layout shape); no empty
state (design a composed "getting started" view); no error state (inline,
never `window.alert()`); dead links (`href="#"`); no active-nav
indication; scroll jumping (add `scroll-behavior: smooth`); animating
`top`/`left`/`width`/`height` instead of `transform`/`opacity`.

**Content** -- generic names ("John Doe"); fake round numbers (`99.99%`,
`$100.00` -- use organic messy data `47.2%`, `$99.00`); placeholder brand
names ("Acme", "Nexus"); AI copywriting cliches ("Elevate", "Seamless",
"Unleash", "Delve"); exclamation marks in success messages; "Oops!" error
copy (be direct: "Connection failed. Please try again."); passive voice;
identical blog dates; same avatar reused across users; Lorem Ipsum; Title
Case on every header (use sentence case).

**Component patterns** -- generic card look (border+shadow+white -- remove
border, or keep only bg, or only spacing); always one filled + one ghost
button (add text links/tertiary styles); pill "New"/"Beta" badges (try
square badges or flags); accordion FAQ (try side-by-side list or inline
disclosure); 3-card carousel testimonials with dots (masonry wall or
embedded posts); 3-tower pricing table (highlight recommended tier with
color, not just height); modals for everything (inline edit/slide-over
instead); avatar circles exclusively (try squircles); sun/moon dark toggle
(dropdown or system detection); 4-column footer link farm (simplify).

**Iconography** -- Lucide/Feather exclusively (use Phosphor/Heroicons/
custom); rocketship-for-"Launch"/shield-for-"Security" cliches (bolt,
fingerprint, spark, vault); inconsistent stroke widths; missing favicon;
stock "diverse team" photos.

**Code quality** -- div soup (use `<nav>`/`<main>`/`<article>`/`<aside>`/
`<section>`); inline styles mixed with classes; hardcoded pixel widths;
missing alt text; arbitrary `z-index: 9999`; commented-out dead code;
import hallucinations (verify against `package.json`); missing meta tags
(title, description, og:image).

**Strategic omissions** -- no legal links; no back navigation; no custom
404; no form validation; no skip-to-content link; no cookie consent if
jurisdiction requires it.

## Upgrade techniques (when you want to go further than "fix the audit")

- **Typography:** variable-font weight/width interpolation on scroll/hover;
  outlined-to-fill text transitions; text-mask reveals over video/imagery.
- **Layout:** broken-grid asymmetry; whitespace maximization; parallax card
  stacks; split-screen scroll (two halves sliding opposite directions).
- **Motion:** smooth scroll with inertia; staggered entry (Y-translate +
  opacity, never mount-all-at-once); spring physics over linear easing;
  scroll-driven reveals (masks, wipes, draw-on SVG paths).
- **Surfaces:** true glassmorphism (1px inner border + inner shadow for
  edge refraction, beyond plain `backdrop-filter: blur`); spotlight
  borders that illuminate under the cursor; grain/noise overlays (fixed,
  `pointer-events-none`); colored/tinted shadows carrying the bg hue.

## Fix priority (max visual impact, min risk, in order)

1. Font swap
2. Color palette cleanup
3. Hover/active states
4. Layout and spacing (grid, max-width, consistent padding)
5. Replace generic components
6. Add loading/empty/error states
7. Polish typography scale and spacing

## Rules

- Work with the existing tech stack. Do not migrate frameworks or styling
  libraries.
- Do not break existing functionality -- test after every change.
- Check the dependency file before importing any new library.
- If Tailwind, confirm v3 vs v4 before touching config.
- No framework present → vanilla CSS.
- Small, targeted, reviewable changes over big rewrites.
