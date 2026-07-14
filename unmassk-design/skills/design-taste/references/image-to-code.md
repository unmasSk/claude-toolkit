# Image-to-Code: Faithful Image-First Implementation

Source: `image-to-code` skill by leonxlnx (MIT), condensed. Originally
written for Codex's image-generation-plus-implementation loop; the
image-first *discipline* below applies whenever you're translating a
provided image/screenshot into a real frontend, whether or not you can
generate images yourself.

## Core discipline: image first, analysis second, code third

For visually important frontend work, do not start with freeform coding.
If a reference image exists (user-provided) or you can generate one:
1. Get/produce the design reference image(s).
2. Deeply analyze them (see checklist below) before writing any code.
3. Implement to match, treating the image as the source of truth and the
   code as the translation layer.

Do not rely on memory of "good frontend taste" instead of the actual
reference in front of you.

## One image per section, not one giant board

Do not compress many sections into one small, unreadable composite. If N
sections are needed, prefer N separate, large, readable images (or N
distinct visual regions if working from a single provided reference) so
text, spacing, and buttons stay analyzable. It's better to have one clear
image per section than one compressed board for the whole site. If a
section is unclear, treat it as needing closer inspection -- don't guess.

## Never crop to fabricate detail; regenerate/re-inspect instead

Do not manufacture a "detail view" by cropping a low-res region of a larger
image -- cropping destroys spacing accuracy, type-scale relationships, and
proportions. If more detail is needed and you can regenerate, produce a
fresh, standalone image for that section preserving the same palette,
typography mood, button style, and radius logic -- just cleaner and more
legible. If you cannot regenerate (the image is user-provided and final),
say explicitly which details are unclear rather than inventing them.

## Deep analysis checklist (before implementing)

For every section image, extract:
- **Text:** hero headline, subheadline, CTA labels, section headings --
  exact wording where legible.
- **Typography:** size/weight relationships, line count, tracking, leading
  feel, serif-vs-sans behavior, display-vs-body contrast.
- **Spacing:** headline-to-subhead distance, text-to-button distance,
  card-to-card gaps, section top/bottom padding, side gutters, card
  padding, overall cadence.
- **Buttons/components:** size, shape, radius, fill-vs-outline, icon
  usage, implied hover state, primary-vs-secondary hierarchy, card
  structure, dividers, shadows, borders.
- **Color:** background, panel colors, accent, text hierarchy, border
  logic, shadow mood, image tint/grade, gradient restraint.
- **Layout/structure:** grid logic, section ordering, density, visual
  rhythm, repeated motifs that define the design language.

If something is unclear, treat that as a blocker to resolve (ask, inspect
closer, or flag it explicitly) before implementing -- don't fill the gap
with a generic default.

## Anti-drift implementation rule

The most common failure mode: the reference looks strong, but the coded
result becomes generic. During implementation:
- Do not simplify into default templates.
- Do not replace distinctive sections with generic rows.
- Do not compress generous spacing into a denser layout "for efficiency".
- Do not replace strong typography with plain hierarchy.
- Do not reintroduce nested-box complexity the reference deliberately
  avoided.

The coded result should still read as the same design as the reference,
not "inspired by" it.

## Hero-specific rules (carried over regardless of style)

- Hero headline: 1-3 lines maximum. 4+ lines is a failure -- reduce words,
  don't force more lines.
- Keep the first viewport clean and readable on a small laptop: one strong
  focal point, obvious hierarchy, no competing focal points.
- Do not overfill the hero with pills, fake stats, badges, or decorative
  system labels ("00 orchestration layer") that don't add real value.
- The hero and immediate first-view area must show: headline, readable
  supporting text, clean spacing, a visible primary CTA, one clear focal
  visual -- not the entire product crammed above the fold.

## Anti-nested-box rule

Avoid box-in-box-in-box layouts: giant rounded section containers wrapping
everything, cards inside cards inside cards, dashboard-style compartment
stacking with no purpose. Prefer open layouts, fewer but stronger
containers, direct alignment/spacing over excessive enclosure. Use a box
only when it has a clear reason to exist.

## Committing to a coherent visual combination

Rather than mashing several visual ideas together, pick one coherent
combination and execute it consistently across the whole surface:
- **Theme:** pristine light / deep dark / bold studio solid / quiet
  premium neutral.
- **Background character:** subtle grid or dotted field / solid with
  ambient gradient depth / full-bleed cinematic imagery / tactile texture.
- **Typography character:** clean grotesk / refined grotesk / expressive
  display / compressed statement / editorial serif+sans / Swiss rational.
- **Hero architecture:** cinematic centered minimalist / asymmetric split /
  floating scatter / inline-typography-in-headline / editorial offset /
  massive image-first with restrained text.
- **Section system:** modular bento / alternating editorial blocks /
  poster-like stacked storytelling / gallery cadence / Swiss grid
  discipline / asymmetric marketing flow.

Hold the same brand world, palette, typography mood, and component family
across every image/section generated for one project -- image 2, 3, or 8
must not drift into a different-looking website.

## Final check before implementing

- Has the reference been deeply analyzed, not just glanced at?
- Is text readable? If not, was closer inspection/regeneration done first?
- Is the hierarchy obvious and the hero clean?
- Are spacing, buttons, and colors extracted rather than guessed?
- Is the result free of nested-box clutter and decorative micro-labels?
- Does the final coded result still feel like the same design as the
  reference, not a generic reinterpretation of it?
