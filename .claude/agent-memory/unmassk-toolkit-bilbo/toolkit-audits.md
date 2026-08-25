---
name: toolkit-audits
description: Bilbo scans of the toolkit's own plugins/skills ecosystem — integrity checks, ref-repo surveys, capability gap map. Mostly March 2026, several claims now stale — see verification notes per section.
metadata:
  type: project
---

All entries here are about `claude-toolkit`'s own plugin/skill inventory (zone: `skills`, per `gitmem
zones list`). Several source ref-repos this material was surveyed from no longer exist at the paths
named — see `codebase-patterns.md` for the current `.ref-repos/` contents. That does not invalidate the
findings about the PLUGINS that were built from them, which do still exist.

## 2026-03-15 — BM25 skill-search.py architecture trace — MECHANISM NOW GONE (verified 2026-08-25)

Full data-flow map of `skill-search.py` (unmassk-crew 1.3.0): 4 ordered search dirs (cache always wins
on name collision), corpus of exactly 36 skills, 4 skills deliberately unreachable via BM25
(orchestrator-level, invoked only by explicit Skill tool), two-stage dedup (path-level then
name-level), smoothed BM25+ IDF variant, tokenizer detail, undocumented `SKILL_SEARCH_EXTRA_DIRS` env
var (noted only in Ultron memory, unused in production).

**Confirmed gone 2026-08-25 (EXECUTED):** `find -iname skill-search.py` returns nothing, and
`find -iname "*.skillcat"` returns 0 files anywhere in the repo. The BM25 auto-search mechanism this
entire entry describes has been replaced — current skill loading goes through the explicit
"Protocols" menu in CLAUDE.md (skill name → trigger condition table) instead of a corpus search.
Kept as history only; nothing here is actionable against the current tree.

## 2026-03-14 — marketingskills ref-repo survey — SOURCE REPO GONE, PLUGIN BUILT

Mapped 27 non-SEO skills from `.ref-repos/marketingskills/skills/`, all following a
`product-marketing-context` check pattern (see `codebase-patterns.md`). Inventory scan, no orphans, no
escalation.

**SEO Skills identified as out of marketing plugin scope at the time:** seo-audit, ai-seo,
programmatic-seo, site-architecture, competitor-alternatives, schema-markup — "already covered by
unmassk-seo plugin". **Confirmed 2026-08-25: these are no longer separate skill names anywhere.**
`unmassk-seo` is now a single aggregate skill with topic files under `references/` (competitor,
content, geo, hreflang, images, page-analysis, plan, programmatic, schema, sitemap, technical,
thresholds) — see `codebase-patterns.md` for the full shape. `unmassk-marketing` likewise consolidated
to one skill dir. The ref-repo `marketingskills/` itself is gone from `.ref-repos/` (EXECUTED `ls`).

## 2026-03-14 — unmassk-design plugin source survey (5 repos) — ALL SOURCE REPOS GONE

Surveyed 5 design ref-repos for consolidation: Impeccable (~10,400 words, anti-AI-slop philosophy, 17
command skills), UI/UX Pro Max (~6,500 words, searchable CSV DB + 3 Python scripts, only source with a
working search engine), bencium-controlled-ux-designer (~10,500 words, ARIA/shadcn/Tailwind patterns),
typography (~3,800 words, Butterick's Practical Typography, OpenType/JSX curly-quote guide),
relationship-design (~9,400 words, agentic UX / memory architecture / trust evolution — orthogonal to
the other 4). Consolidation call at the time: Impeccable = principles core, UI/UX Pro Max = data/search
infra, bencium = accessibility/components, typography = typographic layer, relationship-design =
separate agentic-UX concern. Inventory scan, no orphans, no escalation.

**Confirmed 2026-08-25: none of these 5 repo names exist under `.ref-repos/` anymore** (EXECUTED `ls`
→ communitytools, lote-a..d, spec-kit, .claude only). `unmassk-design/skills/` exists and is populated,
so the consolidation happened; the source material to re-diff against is gone.

## 2026-03-14 — cc-devops-skills ref-repo full inventory — SOURCE REPO GONE, PLUGIN BUILT

Surveyed all 31 skills in `.ref-repos/cc-devops-skills/devops-skills-plugin/skills/`: 103 script files,
63 reference files, 31 doc files; 6 skills with no scripts; 14 duplicated script names across skills
(confirmed different implementations, except `detect_crd.py` between k8s-yaml-validator and
helm-validator which diverged significantly); heaviest scripts up to ~1,900 lines
(jenkinsfile-generator, loki-config-generator, fluentbit-generator); domain grouping IaC/CI-CD/
Containers-K8s/Observability/Scripting. No orphan SKILL.md files. No escalation.

**Confirmed 2026-08-25: `cc-devops-skills/` is gone from `.ref-repos/`.** `unmassk-ops/skills/` exists
with 7 skill dirs today (ops-cicd, ops-containers, ops-deploy, ops-error-tracking, ops-iac,
ops-observability, ops-scripting) — 2 more than the 5 that existed at the integrity-check date below.

## 2026-03-15 — unmassk-ops plugin integrity verification (5 skills, at the time) — SKILL COUNT GREW SINCE

Cross-reference of `/unmassk-ops/skills/` against 5 SKILL.md declarations. **All 5 passed** —
ops-iac (20 scripts/14 refs), ops-containers (22/19), ops-cicd (29 scripts +jenkins-lib/__init__.py
undeclared-but-expected /30 refs), ops-observability (10/9), ops-scripting (11/21) — all declared items
physical and matching, all `.py` compile, all `.sh` pass `bash -n`, all paths use
`${CLAUDE_PLUGIN_ROOT}`. Minor non-failures: committed `__pycache__/` in 4 skills, a metadata
script-count-off-by-one in ops-cicd (29 vs 30 table rows). No escalation.

**NOT reverified 2026-08-25 — flagging, not claiming pass/fail:** `unmassk-ops/skills/` now has 7
dirs, not 5 (`ops-deploy` and `ops-error-tracking` added — EXECUTED `ls`). Those 2 new skills were
never subjected to this integrity check. The 5 original ones were not re-diffed either; only their
continued existence was confirmed by directory listing, not their internal script/reference counts.

## 2026-03-15 — unmassk-db plugin integrity verification (7 skills) — COUNT STILL MATCHES

Cross-reference of `/unmassk-db/skills/` against 7 SKILL.md declarations. **5 passed, 2 failed at the
time:** db-postgres (22 refs, PASS), db-mysql (19 refs, PASS), db-mongodb (10 refs, PASS, routing table
uses bare filenames — format difference only), **db-redis FAILED** (35 physical files, 34 declared in
routing table — `redis-overview.md` on disk and counted in frontmatter but missing from the routing
table, dead reference), db-migrations (4 refs + 4 scripts, PASS), db-vector-rag (5 refs, PASS),
db-schema-design (5 refs + 2 scripts, PASS). All `.py` compile, all paths use
`${CLAUDE_PLUGIN_ROOT}`. No escalation was raised (this is Bilbo's own scan-and-report, not a fix).

**Confirmed 2026-08-25: skill directory count still matches (7)** — db-migrations, db-mongodb,
db-mysql, db-postgres, db-redis, db-schema-design, db-vector-rag (EXECUTED `ls`). **The db-redis
missing-routing-table-entry finding was NOT re-verified** — this only confirms the skill list is
stable, not that the specific dead-reference bug is still there or was fixed. Worth a targeted re-check
if anyone touches db-redis.

## 2026-03-15 — compliance-i18n skill content audit — SKILL.md GAP NOW CLOSED

At the time: **SKILL.md was MISSING** from `compliance-i18n/` — 10 reference files present (i18n
architecture, CLI usage, key management, AI translation/ICU, GitHub sync, CDN delivery, MCP
integration [10 tools], SDK integration, best practices) but no frontmatter/triggers, so the skill
could not be invoked. Also flagged: content is 100% localization-tooling docs for a SaaS platform
("Better i18n"), zero regulatory/legal content — misclassified inside the compliance plugin regardless
of the SKILL.md gap. Escalated to Ultron at the time to create the missing SKILL.md.

**A later 2026-03-15 scan (toolkit capability map, below) already noted "SKILL.md now exists (was
missing in earlier scan, created since)" — content mismatch (dev-tooling vs compliance) unresolved at
that time.** Confirmed 2026-08-25 (EXECUTED `ls`): `compliance-i18n/` has both `SKILL.md` and
`references/` today — the invocability gap is closed. Whether the content-misclassification concern
was ever addressed was not checked this pass.

## 2026-03-15 — Full toolkit capability map (47 skills + 10 crew agents, at the time)

Top 10 confirmed gaps at the time (nothing in the toolkit covered these): (1) backend framework skill,
(2) auth implementation (only ever audited, never built), (3) frontend dev patterns, (4) API design
(OpenAPI/REST/GraphQL/gRPC — absent), (5) payment integration, (6) email service, **(7) serverless/PaaS
deployment — ops was K8s-only**, **(8) application error tracking — ops-observability was infra-only**,
(9) ORM/data-access layer, (10) product analytics/event tracking. Coverage-by-phase summary: DB
best-covered (7 engines), Compliance deepest (9 skills), Ops enterprise K8s/IaC but no PaaS,
Marketing/SEO well-covered, Frontend/Backend/Auth/API all gap-heavy. No escalation — inventory only.

**Gaps #7 and #8 look closed as of 2026-08-25 — NOT re-verified in depth, flagging by name match
only.** `unmassk-ops/skills/` now includes `ops-deploy` and `ops-error-tracking` (didn't exist at scan
time, confirmed by the 7-vs-5 count discrepancy noted in the ops integrity entry above). Whether their
actual content covers what gap #7/#8 described (Vercel/Railway/Fly/Cloudflare Workers for #7,
Sentry/OpenTelemetry app-level instrumentation for #8) was not read — only the directory names line up.
Gaps #1-#6, #9, #10 not re-checked at all this pass.
