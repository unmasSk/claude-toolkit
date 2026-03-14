# unmassk-design Implementation Plan

**Issue:** #4
**Branch:** feat/plugin-expansion
**Triage:** Big
**Created:** 2026-03-14

## Goal

Build unmassk-design — comprehensive frontend design toolkit with 11 references, BM25 search engine + CSV databases, and knowledge from 5 sources. Zero agents; crew executes.

## Decisions

- 11 reference files consolidated from 5 sources
- Pro Max search engine (search.py + core.py + design_system.py) + CSV databases ported as scripts
- 17 Impeccable commands become instructions within references
- Bounce/elastic: no-bounce default, spring only for explicit playful contexts
- No hooks needed
- No MCP needed
- Attribution to all 5 sources in README

## Sources

- `.ref-repos/impeccable/` (pbakaus) — Apache 2.0
- `.ref-repos/ui-ux-pro-max/` (nextlevelbuilder) — MIT
- `.ref-repos/bencium-marketplace/bencium-controlled-ux-designer/` (bencium) — MIT
- `.ref-repos/bencium-marketplace/typography/` (bencium) — MIT
- `.ref-repos/bencium-marketplace/relationship-design/` (bencium) — MIT

## Tasks

### Task 1: Plugin manifest + structure + scripts
- Update .claude-plugin/plugin.json
- Create directory structure
- Port search.py + core.py + design_system.py from Pro Max
- Port all CSV databases from Pro Max src/ui-ux-pro-max/data/
- Commit

### Task 2: SKILL.md orchestrator
- Canonical frontmatter with all design trigger phrases
- Routing table for 11 references
- Mandate search.py for design system generation
- Attribution to 5 sources
- Commit

### Task 3: 11 reference files (Alexandria x3)
- Batch A: design-principles, color, typography, motion
- Batch B: layout-and-space, interaction, responsive, ux-writing
- Batch C: design-system-kickoff, accessibility, agentic-ux
- Commit

### Task 4: README + version bump
- README with attribution to all 5 sources
- Bump to 1.0.0
- Push

## Wave Map

- Wave 1: Task 1 (manifest + scripts/CSVs)
- Wave 2: Task 2 (SKILL.md) — parallel with Wave 1
- Wave 3: Task 3 (11 refs in 3 batches) — after SKILL.md
- Wave 4: Task 4 (README + bump) — after all
- Wave 5: Verify (Alexandria + Yoda)

**Status: IN PROGRESS**
