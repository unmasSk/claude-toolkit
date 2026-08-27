---
name: Plugin and SKILL.md conventions
description: Structural conventions for unmassk-claude-toolkit plugins and SKILL.md orchestrators
type: project
---

## SKILL.md Frontmatter

Every SKILL.md must have a `description` field. The house wording is **"Use when the user asks to ..."** followed by a list of literal trigger phrases in the user's own languages (Spanish and English here), then what the skill is NOT for. Re-verified 2026-08-27 against `unmassk-3d`, `unmassk-electronics/electronics-micro`, `unmassk-db/db-schema-design`, `unmassk-toolkit/unmassk-memory` and the new `unmassk-trading` — all five open with "Use when...". The older note in this file said the field had to begin with "This skill should be used when..."; that is stale, no shipped SKILL.md uses it. Do not flag "Use when..." as a convention violation.

## A new plugin is not shipped until it is in the root marketplace

`.claude-plugin/marketplace.json` at the repo root lists every installable plugin. A plugin directory with its own `.claude-plugin/plugin.json` but no entry there cannot be installed, and `bin/release.py <plugin> <version>` fails preflight (`_preflight_check_plugin_exists` reads marketplace.json). Always diff the marketplace list against the `unmassk-*/` directories on disk when reviewing a new plugin.

## Plugin File Layout

Standard plugin structure (verified in unmassk-marketing, 2026-03-14):

```
skills/<skill-name>/
  SKILL.md             — orchestrator with routing table
  references/          — domain knowledge files loaded on-demand
  scripts/             — zero-dependency Node.js CLI scripts for platform APIs
  evals/               — eval JSON + search script (evals.json, search-evals.py)
```

The `scripts/` directory may contain a `README.md` — this is documentation, not a routed script. Do not flag it as orphaned.

## Routing Table Audit Pattern

When auditing SKILL.md routing completeness:
1. Extract every `references/*.md` path from the routing table AND the Reference Files section (they can overlap — deduplicate).
2. Extract every `scripts/*.js` filename from the Script Categories table.
3. Diff against actual disk contents.
4. `README.md` in scripts/ is always expected and benign.
