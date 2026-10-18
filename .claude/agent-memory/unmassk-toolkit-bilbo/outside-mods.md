---
name: outside-mods
description: Where the official Claude Code "mods" docs live and how to read the bundled plugin-authoring skill (it is NOT on disk)
metadata:
  type: reference
---

Official mods docs (read 2026-10-17): index https://code.claude.com/docs/llms.txt -> /docs/en/plugins/mods/{overview,reference,events,interface,api}.md. Mods need Claude Code >= 2.1.287 (terminal).
The `plugin-authoring` skill is compiled into the binary (~/.local/share/claude/versions/<v>, zst chunk); `strings` only shows its description. Read the docs instead, do not waste time on the binary.
Statusline doc: https://code.claude.com/docs/en/statusline (refreshInterval, cost.total_duration_ms; subagent requests NOT counted in its stats).
