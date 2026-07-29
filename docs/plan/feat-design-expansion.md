# unmassk-design → multi-branch expansion — Implementation Plan

**Issue:** #78
**Branch:** main (trunk repo — no feature branch)
**Triage:** Big
**Build mode:** linear (content adaptation, shape emerges per branch; not test-driven — these are `.md` skills + adapted scripts, orchestration content)
**Created:** 2026-07-14

## Goal

Turn `unmassk-design` from a single skill into a multi-branch plugin (core + 6 family branches) that absorbs the 41 source skills cloned in `.ref-repos/`, adapted to our conventions with attribution.

## Decisions (git-memory)

- `unmassk-design` becomes a multi-skill plugin; everything in (heavy 3D included) — decision `10591ad`.
- Granularity = one branch per **family** (~6), not per library — decision `fedeaf3`.
- GSAP copied inside; **imagegen stays out** (unmassk-media); taste's anti-slop **merged into the core AI Slop Test** (no duplicate branch) — decision `fedeaf3`.
- Mobile/Flutter in scope — decision `5edea94`.
- Sources & links: SOURCES.md + memo `c2ce9ad`.

## Sources (in `.ref-repos/`)

Old/base: `impeccable`, `ui-ux-pro-max-skill`, `bencium-marketplace`, `claude-plugins-official` (frontend-design), `emilkowalski-skills`. New: `taste-skill`, `claudedesignskills`, `motion-dev-animations-skill`, `css-animation-skill`, `claude-flutter-ui-skills`.

## Convention (every branch)

Each branch = a skill directory under `unmassk-design/skills/<branch>/` with its own `SKILL.md` (our frontmatter conventions: `Use when…` trigger-led description, EN triggers) + `references/` adapted (rewritten in our voice, not byte-lifted where licensing/quality calls for it). Attribution per source in the plugin's `PROVENANCE.md`/`CREDITS.md`. Licenses: MIT/Apache — preserve.

**Lane:** orchestrator did the investigation and owns the plan + verification. Ultron places/adapts content per branch (one branch = one Ultron phase). Alexandria syncs docs/attribution. Orchestrator verifies each branch (frontmatter parses, references exist, plugin-validator PASS).

## Tasks (one per branch)

### Task 0: Plugin re-shape (foundation)
**Files:** `unmassk-design/.claude-plugin/plugin.json` (skills dir already `./skills/`), keep core skill as `skills/unmassk-design/`. Confirm multi-skill layout works (plugin.json `"skills": "./skills/"` already supports N skills).
**Steps:**
- [ ] Verify `skills: "./skills/"` discovers multiple skill dirs (it does — pentesting/db precedent).
- [ ] Merge taste-skill's anti-slop rules into the core skill's AI Slop Test (dedup, no new branch).
- [ ] Create `PROVENANCE.md` + `CREDITS.md` scaffolding for the new sources.

### Task 1: `motion` branch
**Sources:** emilkowalski-skills (emil-design-eng, apple-design, review-animations, improve-animations, animation-vocabulary), motion-dev-animations-skill, claudedesignskills/motion-framer, react-spring-physics, css-animation-skill.
**Note:** reconcile with the existing `skills/unmassk-design/references/motion.md` (814L) — the craft layer deepens it; decide move vs cross-reference during placement.

### Task 2: `3d` branch
**Sources:** claudedesignskills: threejs-webgl, react-three-fiber, babylonjs-engine, playcanvas-engine, aframe-webxr, pixijs-2d, lightweight-3d-effects, spline-interactive, blender-web-pipeline, substance-3d-texturing.

### Task 3: `scroll` branch
**Sources:** claudedesignskills: gsap-scrolltrigger (copy in), locomotive-scroll, barba-js, scroll-reveal-libraries (AOS).

### Task 4: `animation-formats` branch
**Sources:** claudedesignskills: lottie-animations, rive-interactive, animejs, animated-component-libraries (Magic UI/React Bits).

### Task 5: `taste` branch
**Sources:** taste-skill: brutalist-skill, minimalist-skill, soft-skill (high-end), redesign-skill, stitch-skill, image-to-code-skill, gpt-tasteskill, brandkit, taste-skill (v2). **Excluded:** imagegen-frontend-web/mobile (→ media), output-skill (generic), the anti-slop parts (→ merged into core).

### Task 6: `flutter` branch
**Sources:** claude-flutter-ui-skills/flutter-ui.

### Task 7: Docs + release (Alexandria + orchestrator)
- [ ] PROVENANCE/CREDITS complete per source; README updated (plugin + root); CHANGELOG.
- [ ] plugin-validator PASS (mandatory for the reshaped plugin).
- [ ] Bump unmassk-design version; release via bin/release.py.

## Wave Map
- Wave 1: Task 0 (foundation) — must go first.
- Wave 2: Tasks 1–6 (branches) — independent, can run one at a time or in parallel (disjoint dirs). Recommend sequential by value: motion → taste → scroll → animation-formats → 3d → flutter.
- Wave 3: Task 7 (docs + release) — after all branches land.

## Notes / open placement details (re-investigate on doubt, per Bex)
- Deep-read the specific source SKILL.md + references at placement time per branch (method-level content), not upfront — investigation was contrast-level.
- `3d` is the heaviest (10 sources) — may split internally into sub-references, decided at placement.
- Existing `motion.md` reconciliation is the one real merge conflict to resolve carefully.

**Status: COMPLETED** — issue cerrado; marcado en la limpieza del 2026-07-29 (censo de deuda). El plan quedó sin marcar al cerrar el trabajo: el paso 7 de Flow depende de que el orquestador lo recuerde, y no lo hizo.
