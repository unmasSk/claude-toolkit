---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last changelog update: 2026-03-24
Last commit covered (toolkit root): 0001616 (fix(plugin/config): restaurar scopes.json)
Last commit covered (chatroom): 3c8a1e0 (feat(plugin/chatroom/agents): V2 prompts self-review pass)
Current version in plugin.json: 3.7.0 (unmassk-gitmemory), 1.6.0 (unmassk-crew)
Versions documented (toolkit root): 1.0.0 through 3.7.0 plus [Unreleased] section; unmassk-crew 1.5.0 and 1.6.0 entries added
[Unreleased] contains (toolkit root): unmassk-ops plugin (5 skills), compliance-legal-docs skill (SKILL.md created + 12 reference files fixed), ops-error-tracking skill (SKILL.md created, 6 reference frontmatters stripped, otel-backends.md created)
[Unreleased] contains (chatroom/CHANGELOG.md): V2 agent prompts (9 agents, self-review pass), 5-phase pipeline rewrite + 146 golden tests, moriarty-v3 deletion, mention-parser fix, stoppedRooms guard, file attachments (API + UI + DB + frontend)

**Why:** Alexandria needs to know where to resume on next launch — only commits after the covered commits need processing.
**How to apply:** On next run for toolkit root: `git log 0001616..HEAD --oneline` filtering non-chatroom paths. For chatroom: `git log 3c8a1e0..HEAD --oneline -- chatroom/`. Check for new code changes not yet in either CHANGELOG.md.
