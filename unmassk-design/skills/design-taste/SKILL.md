---
name: design-taste
description: >
  Use when the user asks to "make it brutalist", "give it an industrial or
  terminal look", "make it minimalist", "editorial minimalism", "make it feel
  expensive", "high-end / premium / Awwwards-tier design", "redesign this",
  "upgrade this existing project to premium", "audit this design and fix it",
  "turn this image into code", "image to code", "match this screenshot",
  "build a brand kit", "logo system", "brand identity board", or mentions any
  of: brutalism, tactical telemetry, CRT terminal UI, Swiss industrial print,
  minimalist editorial UI, warm monochrome bento grid, high-end agency design,
  double-bezel cards, magnetic button hover, redesign audit, DESIGN.md, Google
  Stitch, brand kit, brand guidelines board, logo concept, monogram.
  Covers three named aesthetic directions (brutalist, minimalist, soft/
  high-end) with concrete tokens -- fonts, hex colors, spacing, shadows,
  radii -- a redesign audit-to-premium workflow for existing projects, an
  image-to-code faithful-translation workflow, a semantic DESIGN.md authoring
  format, editorial motion choreography, and brand-kit/logo generation.
  Use when NOT: a generic "make this not look like AI slop" with no named
  style direction and no existing project to redesign -- that baseline
  critique/polish is out of scope here. This skill is for committing to one
  named style, or one of the specific workflows below (redesign,
  image-to-code, brand kit).
  Based on the `taste-skill` collection by leonxlnx (MIT).
version: 1.0.0
---

# Design Taste -- Named Style Variants, Redesign, and Adjacent Workflows

`unmassk-design` (the core skill) already owns the generic anti-slop
checklist -- the AI Slop Test, the ten design commands (audit, critique,
polish, bolder, quieter...), and the general design-principles reference.
This skill does not repeat that. It exists for the thing the core skill
does *not* have: **committing to one named, concrete aesthetic direction**,
and a handful of adjacent workflows (redesign an existing project,
image-to-code, semantic design docs, GSAP editorial motion, brand kits) that
share the same "condensed reference, pick one, execute fully" shape.

Condensed and rewritten from the `taste-skill` collection by leonxlnx
(MIT) -- see Attribution at the end.

## Core rule: pick ONE, commit fully

Every reference below (style or workflow) is internally opinionated. Do not
blend two named styles in the same interface, and do not cherry-pick three
rules from brutalist and two from minimalist. Read the brief, pick the
matching reference, load only that one, and execute it completely. If the
user gives conflicting signals (e.g. "brutalist but soft and friendly"),
surface the contradiction back to them in one line instead of averaging it
away.

## Request Routing

| User says / brief reads as | Reference | Core value it adds over `unmassk-design` |
|---|---|---|
| brutalist, industrial, terminal, tactical, blueprint, CRT, declassified dashboard | `references/style-brutalist.md` | A named, opinionated aesthetic with exact fonts/tracking/hex values -- the core has no such direction |
| minimalist, editorial, warm monochrome, bento grid, Notion-like, "document-style" | `references/style-minimalist.md` | Same -- a named direction, not a principle |
| expensive, premium, high-end, Awwwards-tier, Apple-esque, Linear-tier, agency-grade | `references/style-soft-highend.md` | Same -- concrete component techniques (double-bezel, magnetic hover) the core doesn't specify |
| redesign an existing project, upgrade to premium, audit real code and fix it | `references/redesign.md` | An audit-first, non-destructive workflow for a project that already exists -- the core's `audit`/`polish` commands assume you're improving a design in the abstract, not a live codebase |
| turn an image/screenshot into code, match this reference image, image-to-code | `references/image-to-code.md` | An image-first workflow (generate/inspect references before coding) the core doesn't cover at all |
| generate a `DESIGN.md`, prompt Google Stitch, write a semantic design spec for another agent/tool | `references/design-doc-format.md` | A structured document format for handing taste to a downstream tool, not a design direction itself |
| GSAP scroll choreography, pinned sections, scroll-driven motion for an editorial/premium site | `references/motion-editorial-gsap.md` | Concrete GSAP patterns (pin, scrub, stagger) -- the core's `references/motion.md` covers general motion principles, not this level of implementation detail |
| brand kit, logo system, brand identity board, brand guidelines deck | `references/brandkit.md` | Brand-system generation (logo concepting, board composition) -- entirely outside the core's UI-component scope |

Load references on-demand, one at a time, matching the request. Do not load
all eight at startup.

## Relationship to the core skill

Still run the core's AI Slop Test and accessibility baseline regardless of
which named style you pick -- a brutalist interface can still fail contrast
or ship an inaccessible focus state. The named style controls aesthetic
choices (fonts, color, layout, motion feel); the core's accessibility and
anti-slop rules are a floor underneath all of them, not an alternative to
them.

## Excluded from this branch

Image *generation* (producing the actual pixels/photos for a UI) lives in
`unmassk-media`, not here. This branch covers image-to-code (turning an
existing/generated image into implementation) and brand-kit *art direction*
(what a brand board should contain and why), not the generation tooling
itself.

## Attribution

Condensed and rewritten in our own voice from the `taste-skill` collection
by leonxlnx (MIT license): `industrial-brutalist-ui`, `minimalist-ui`,
`high-end-visual-design`, `redesign-existing-projects`,
`stitch-design-taste`, `image-to-code`, `gpt-taste`, and `brandkit`. Original
sources are single-file `SKILL.md` skills; this branch condenses their
actionable content and attributes rather than reproducing them verbatim.
