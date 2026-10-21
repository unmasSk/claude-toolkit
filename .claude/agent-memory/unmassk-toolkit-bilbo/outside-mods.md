---
name: outside-mods
description: Where the official Claude Code "mods" docs live and how to read the bundled plugin-authoring skill (it is NOT on disk)
metadata:
  type: reference
---

Official mods docs (read 2026-10-17): index https://code.claude.com/docs/llms.txt -> /docs/en/plugins/mods/{overview,reference,events,interface,api}.md. Mods need Claude Code >= 2.1.287 (terminal).
The `plugin-authoring` skill is compiled into the binary (~/.local/share/claude/versions/<v>, zst chunk); `strings` only shows its description. Read the docs instead, do not waste time on the binary.
Statusline doc: https://code.claude.com/docs/en/statusline (refreshInterval, cost.total_duration_ms; subagent requests NOT counted in its stats).

2026-10-20: community plan/todo mods exist (created 2026-10-02..13, MIT): nikscz/nix-checklist-sidebar and wapacz/claude-todo-tracker-plugin run on Desktop and tick from TodoWrite/own tools; none of 9 hooks `update_plan` (grep). Anthropic playground mods (token-weather, blast-radius, replay-theater) are no plan panel. `gh api repos/<r>/tarball` + grep is the fast way to read them; `gh api search/code` returns 404 here. claudeissues.com is a mirror, not GitHub.

2026-10-20 usage-limit mods: ~17 community mods (MIT mostly, created 2026-10-03..20) show 5h/7d bars; found with `gh search repos "claude code mod usage limit"` (topic phrase "Claude Code mod:" in descriptions). Numbers come from mod API `$.session.usage().rateLimits` [{kind,percentUsed,resetsAt}] + event `session.measure` (docs mods/reference.md); statusline JSON has `rate_limits.five_hour|seven_day.used_percentage` (Pro/Max only, after 1st response). Closest to two bars: MaeharaTakumi/claude-usage-band (122 lines, rings, no licence), jsni94/usage-band (calls undocumented oauth/usage). Best-built: zgmengde/usage-bar (desktop), MoonZhe/usage-band.

2026-10-21: changelog page (https://code.claude.com/docs/en/changelog) is 1.07M chars, WebFetch pages it in 100k chunks with `offset`; top = 2.1.306. Newest weekly digest is wk37 (no Oct digests). skills.md has the full SKILL.md frontmatter table; worktrees.md is short and complete. Delta report: .claude/informes/bilbo-2026-10-21-*-claude-code-delta-*.md
