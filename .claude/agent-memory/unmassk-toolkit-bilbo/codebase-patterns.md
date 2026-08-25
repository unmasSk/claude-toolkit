---
name: codebase-patterns
description: Plugin structure, skill anatomy, ref-repo convention for claude-toolkit — corrected 2026-08-25
type: project
---

## Plugin Structure (unmassk-claude-toolkit)

Each plugin lives under `.claude/plugins/cache/<namespace>/<plugin-name>/<version>/` when installed
(confirmed READ 2026-08-25 from the injected skill base dir of this very session:
`/Users/unmassk/.claude/plugins/cache/unmassk-claude-toolkit/unmassk-toolkit/1.40.0/skills/unmassk-standards`).
In the dev repo it's `<plugin-name>/skills/<skill-name>/SKILL.md`.

**Two coexisting plugin shapes, confirmed 2026-08-25 (EXECUTED `ls`) — not one pattern:**
- **Multi-skill plugins** — one dir per skill, each with its own `SKILL.md` (+ optional `scripts/`,
  `references/`). Examples: `unmassk-toolkit/skills/` (12 dirs: unmassk-audit, unmassk-close-session,
  unmassk-core, unmassk-council, unmassk-flow, unmassk-grill, unmassk-groundhog, unmassk-memory,
  unmassk-memory-doctor, unmassk-project-lifecycle, unmassk-scaffolding, unmassk-standards),
  `unmassk-ops/skills/` (7: ops-cicd, ops-containers, ops-deploy, ops-error-tracking, ops-iac,
  ops-observability, ops-scripting), `unmassk-db/skills/` (7: db-migrations, db-mongodb, db-mysql,
  db-postgres, db-redis, db-schema-design, db-vector-rag).
- **Single-aggregate-skill plugins** — the whole plugin is ONE `SKILL.md` with a `references/*.md`
  fan-out for subtopics, no per-topic skill dirs. Confirmed for `unmassk-seo/skills/unmassk-seo/`
  (references: competitor, content, geo, hreflang, images, page-analysis, plan, programmatic, schema
  [+schema-templates.json], sitemap, technical, thresholds) and `unmassk-marketing/skills/unmassk-marketing/`
  (same shape). **This replaces the old assumption that SEO/marketing ship as many separate named
  skills** — see the corrected note below.

## Skill Anatomy — frontmatter is FLAT, not nested

Confirmed READ 2026-08-25 (`unmassk-toolkit/skills/unmassk-memory/SKILL.md:1-4`): frontmatter is
`name:`, `version:` (top-level, e.g. `2.1.0`), `description:` — **no `metadata:` wrapper**. An earlier
version of this note said `metadata.version`; that was wrong (or was true once and drifted — not
reverified against a date). Trust the flat form until contradicted.

Body: role declaration, initial assessment (context-check pattern), core principles, workflow.
Optional `references/` subdir with supporting detail loaded on demand.

**Historical pattern note (not reverified in detail, ref-repo it came from is gone — see below):**
27 marketing skills surveyed pre-consolidation all followed a `product-marketing-context` check
pattern at skill entry. Worth checking for when building a new skill in that family, but the source
material no longer exists to re-diff against.

## Ref-Repo Convention — structure holds, specific repos rotate

`.ref-repos/` holds upstream source repos cloned for reference during plugin authoring — NOT
installed plugins. Structure: `.ref-repos/<repo>/skills/<skill-name>/SKILL.md`.

**The repos themselves are not stable — confirmed 2026-08-25 (EXECUTED `ls .ref-repos/`):** current
contents are `communitytools/`, `lote-a/` through `lote-d/`, `spec-kit/`, `.claude/`. The repos this
memory previously named — `marketingskills/`, `cc-devops-skills/`, and the 5 design source repos
(Impeccable, UI/UX Pro Max, bencium-controlled-ux-designer, typography, relationship-design) — **are
gone from this path.** The plugins they fed (`unmassk-marketing`, `unmassk-ops`, `unmassk-design`) do
exist and are populated, so the source repos were consumed and cleaned up, not lost — but if you go
looking for them at those names, they will not be there. Full survey content of what those repos held
is preserved as history in `toolkit-audits.md`, not here.

`spec-kit/` is the one ref-repo still present under its original name — used for boot/memory design
research, see `boot-memory-mechanics.md`.
