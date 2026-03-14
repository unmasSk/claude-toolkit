# unmassk-seo Implementation Plan

**Issue:** #2
**Branch:** feat/plugin-expansion
**Triage:** Big
**Created:** 2026-03-14

## Goal

Build the unmassk-seo plugin — a complete technical SEO skill with references, hooks, scripts, and MCP configuration, sourced from claude-seo (AgriciDaniel). Zero agents; crew executes everything.

## Decisions

- 1 SKILL.md orchestrator (~2k words) + 12 reference files (progressive disclosure)
- Python scripts: fetch_page.py + parse_html.py (with SSRF protection)
- MCP: .mcp.json template with placeholders + DataForSEO field-config
- 2 hooks: pre-commit SEO check + JSON-LD schema validation
- No agents — crew handles execution via skill context
- Attribution to AgriciDaniel/claude-seo in README

## Source Material

Cloned at `.ref-repos/claude-seo/` — all files readable locally.

## Tasks

### Task 1: Plugin manifest + structure
**Files:** create
**Steps:**
- [ ] Verify `.claude-plugin/plugin.json` exists (already scaffolded at 0.1.0)
- [ ] Update plugin.json with full metadata (author, homepage, keywords, license)
- [ ] Create directory structure: `skills/unmassk-seo/references/`, `hooks/`, `scripts/`
- [ ] Commit

### Task 2: SKILL.md orchestrator
**Files:** create `skills/unmassk-seo/SKILL.md`
**Steps:**
- [ ] Write frontmatter (name, description with trigger phrases, version)
- [ ] Write body: purpose, routing table, SEO Health Score weights, priority levels, industry detection, workflow for audits
- [ ] Reference all 12 reference files
- [ ] Keep under 2,500 words
- [ ] Commit

### Task 3: Reference files (12 files)
**Files:** create `skills/unmassk-seo/references/*.md`
**Depends on:** Task 2 (must match references cited in SKILL.md)
**Steps:**
- [ ] `technical.md` — 9 categories from seo-technical agent + skill
- [ ] `content.md` — E-E-A-T framework, content minimums, AI content assessment
- [ ] `schema.md` — Schema.org types, deprecated/restricted, JSON-LD templates
- [ ] `geo.md` — GEO scoring, citability, AI crawlers, platform optimization
- [ ] `images.md` — alt text, format, lazy loading, CLS, responsive
- [ ] `sitemap.md` — XML validation, quality gates, generation
- [ ] `hreflang.md` — International SEO, 8 validation checks, implementation methods
- [ ] `programmatic.md` — Scaled content, quality gates, abuse enforcement
- [ ] `plan.md` — 4-phase roadmap, industry templates
- [ ] `competitor.md` — Vs pages, alternatives, roundups, schema
- [ ] `page-analysis.md` — Deep single-page audit, Page Score Card
- [ ] `thresholds.md` — CWV values, scoring weights, quality gates consolidated
- [ ] Commit

### Task 4: Python scripts
**Files:** create `scripts/fetch_page.py`, `scripts/parse_html.py`
**Steps:**
- [ ] Port fetch_page.py from source (HTTP fetcher, SSRF protection, Googlebot UA)
- [ ] Port parse_html.py from source (BeautifulSoup SEO extraction)
- [ ] Adapt paths to use ${CLAUDE_PLUGIN_ROOT}
- [ ] Add requirements.txt (requests, beautifulsoup4, lxml)
- [ ] Verify both scripts run
- [ ] Commit

### Task 5: Hooks
**Files:** create `hooks/hooks.json`, `hooks/scripts/pre-commit-seo-check.sh`, `hooks/scripts/validate-schema.py`
**Steps:**
- [ ] Port hooks.json with PreToolUse (Bash matcher) + PostToolUse (Edit|Write matcher)
- [ ] Port pre-commit-seo-check.sh (blocks placeholder text, deprecated schema)
- [ ] Port validate-schema.py (validates JSON-LD blocks)
- [ ] Adapt paths to ${CLAUDE_PLUGIN_ROOT}
- [ ] Commit

### Task 6: MCP configuration
**Files:** create `.mcp.json`, `extensions/dataforseo/field-config.json`
**Steps:**
- [ ] Create .mcp.json template with DataForSEO, Ahrefs, Semrush, GSC, PageSpeed
- [ ] Port DataForSEO field-config.json (75% token reduction)
- [ ] All API keys as ${ENV_VAR} placeholders
- [ ] Commit

### Task 7: Schema templates
**Files:** create `skills/unmassk-seo/references/schema-templates.json`
**Steps:**
- [ ] Port 9 JSON-LD templates from source
- [ ] Reference in schema.md
- [ ] Commit

### Task 8: README + attribution
**Files:** create `unmassk-seo/README.md`
**Steps:**
- [ ] Write README with: overview, what's included, MCP setup, attribution
- [ ] Credit AgriciDaniel/claude-seo as source
- [ ] Commit

### Task 9: Marketplace version bump
**Files:** modify `.claude-plugin/marketplace.json`, `unmassk-seo/.claude-plugin/plugin.json`
**Steps:**
- [ ] Bump unmassk-seo from 0.1.0 to 1.0.0
- [ ] Push to feat/plugin-expansion
- [ ] Commit

## Wave Map

- **Wave 1:** Task 1 (manifest), Task 4 (scripts), Task 6 (MCP) — independent
- **Wave 2:** Task 2 (SKILL.md), Task 5 (hooks), Task 7 (schema templates) — independent
- **Wave 3:** Task 3 (references) — depends on Task 2
- **Wave 4:** Task 8 (README), Task 9 (version bump) — depends on all above

## Verify

- Cerberus: skill structure correct per plugin-dev spec
- Dante: scripts run, hooks validate, SKILL.md triggers correctly
- Argus: SSRF protection in scripts, no secrets in MCP config
- Moriarty: adversarial on hooks and scripts
- Yoda: senior verdict before merge

**Status: IN PROGRESS**
