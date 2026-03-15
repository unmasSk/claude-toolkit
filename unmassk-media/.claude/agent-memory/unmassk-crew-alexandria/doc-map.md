---
name: doc-map
description: SKILL.md files in unmassk-media — location, canonical format status, last verified
type: project
---

## skills/media-image-gen/SKILL.md

- Status: canonical format DONE (2026-03-15)
- name: media-image-gen
- version: 1.0.0
- description: multiline YAML block with English + Spanish trigger phrases
- CLI path fixed: `${CLAUDE_PLUGIN_ROOT}/skills/media-image-gen/mcp-server/build/cli.bundle.js`
- Body: unchanged (high quality)

## skills/media-image-gen/references/prompt-crafting.md

- Status: clean — no frontmatter, starts with `# Advanced Prompt Crafting`
- No changes needed

## skills/media-mermaid/SKILL.md

- Status: canonical format DONE (2026-03-15)
- name: media-mermaid
- version: 1.0.0
- description: multiline YAML block with English + Spanish trigger phrases covering all diagram types
- Hardcoded path fixed: `bash .claude/skills/mermaid-diagram-skill/references/render_mermaid.sh` → `bash ${CLAUDE_PLUGIN_ROOT}/skills/media-mermaid/references/render_mermaid.sh`
- Body: unchanged (high quality — kept as-is per instructions)

## skills/media-mermaid/references/* (11 files)

- Status: all clean — no frontmatter in any reference file
- No changes needed

## skills/media-image-edit/SKILL.md

- Status: canonical format DONE (2026-03-15)
- name: media-image-edit
- version: 1.0.0
- description: multiline YAML block with English + Spanish trigger phrases
- Broken paths removed: `/mnt/skills/user/fal-image-edit/` and `/mnt/skills/user/fal-generate/` replaced with `${CLAUDE_PLUGIN_ROOT}/skills/media-image-edit/`
- Cross-dependency on `fal-generate/scripts/search-models.sh` eliminated — models hardcoded in script, documented in model-selection.md
- `metadata:` block removed

## skills/media-image-edit/references/operations.md

- Status: created 2026-03-15
- No frontmatter — starts with `# Image Edit Operations`
- Documents all 4 operations (style, remove, background, inpaint) with parameters and examples

## skills/media-image-edit/references/model-selection.md

- Status: created 2026-03-15
- No frontmatter — starts with `# Model Selection`
- Hardcoded model table + instructions for finding alternatives on fal.ai manually

## skills/media-ffmpeg/SKILL.md

- Status: canonical format DONE (2026-03-15)
- name: media-ffmpeg
- version: 1.0.0
- description: multiline YAML block with English + Spanish trigger phrases
- Removed stale `plugin:` and `updated:` lines after frontmatter
- Removed "Related Skills" section (madappgang-internal references)
- Body rewritten: routing table, workflow, mandatory rules, done criteria

## skills/media-ffmpeg/references/commands.md

- Status: created 2026-03-15
- No frontmatter — starts with `# FFmpeg Command Patterns`
- All original commands preserved exactly: video info, trim, concat, format conversion, scale, audio, effects, error handling

## skills/media-ffmpeg/references/codec-guide.md

- Status: created 2026-03-15
- No frontmatter — starts with `# Codec Selection Guide`
- Codec table, ProRes profiles table, hardware acceleration section

## skills/media-screenshots/SKILL.md

- Status: canonical format DONE (2026-03-15)
- name: media-screenshots
- version: 1.0.0
- description: multiline YAML block with English + Spanish trigger phrases
- Removed: `argument-hint`, `context: fork`, `metadata:` from frontmatter
- Extracted: ~100-line Node.js Playwright script → `scripts/screenshot-script.mjs` (executable)
- Created: `references/screenshot-types.md` (platform dimensions, viewport configs)
- Created: `references/workflow.md` (framework routing table, advanced Playwright options, error reference)
- Body: routing table, 5-step workflow, script reference with `${CLAUDE_PLUGIN_ROOT}`, mandatory rules, done criteria

## skills/media-transcribe/SKILL.md

- Status: canonical format DONE (2026-03-15)
- name: media-transcribe
- version: 1.0.0
- description: multiline YAML block with English + Spanish trigger phrases
- argument-hint removed
- All hardcoded paths replaced with `${CLAUDE_PLUGIN_ROOT}/skills/media-transcribe/`
- whisper-cli discovery documented (PATH lookup + fallback locations + install hints)
- WHISPER_MODEL env var documented with fallback logic
- Body: routing table, 3-step workflow, mandatory rules, done criteria

## skills/media-transcribe/references/analysis-prompt.md

- Status: clean — no frontmatter, no broken paths
- Content unchanged (it's the value)

## skills/media-transcribe/references/platforms.md

- Status: created 2026-03-15
- Supported platforms table (YouTube, TikTok, Instagram, Twitter/X, local files)
- Subtitle priority order documented
- Known limitations per platform

## skills/media-transcribe/references/whisper-models.md

- Status: created 2026-03-15
- Model comparison table (tiny/base/small/medium/large)
- Download instructions
- WHISPER_MODEL env var usage

## skills/media-transcribe/scripts/transcribe.sh

- Status: fixed 2026-03-15
- WHISPER_ROOT hardcode removed; uses `which whisper-cli` with fallback candidate list
- MODEL uses WHISPER_MODEL env var with fallback to candidate list relative to PGM
- macOS-only `sed -i ''` replaced with cross-platform temp-file pattern
