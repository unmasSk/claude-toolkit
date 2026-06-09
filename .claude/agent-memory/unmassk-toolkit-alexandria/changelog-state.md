---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-06-09
Last commit covered (toolkit root): c1065ce (docs(docs): roadmap: #9 = solo script de release; hook de push-automatico movido a candidatos)
Last commit covered (chatroom): f4196fa (fix(plugin/chatroom/frontend): formatContent keeps agent name capitalized in queue messages)
Current version in plugin.json: 1.1.1 (source of truth) — CHANGELOG written for 1.3.0 but version bump is another agent's job (do NOT touch plugin.json or marketplace.json)

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] now has entries (2026-06-09): release script (bin/release.py + helpers + --path flag in git-memory-commit.py + docs/RELEASING.md) + documentation coverage improvements (unmassk-seo hooks, ops-observability LogQL validator, ops-cicd azure scripts, media-image-edit .env.example).

[1.3.0] section covers (2026-06-08):
- Added: recall gatekeeper hook (pre-task-recall.py, 51 tests), build-mode (Flow router + linear/test-first references + Ultron/Dante awareness), CLAUDE.md block generator (lib/managed_blocks.py, 35 tests), 4 protocol skills installed (close-session/grill/council/lifecycle), close-session Stop hook, PRD template, communication block in CLAUDE.md
- Changed: Flow skill (routes to references/ instead of inlining), memory calibration tightened (anti-over-saving, repo-type reframe), unmassk-audit aligned with repo_type and coverage gate decisions, core skill clarified (Ultron=prod code only)
- Fixed: boot hook redundant dump removed, flow-stack scaffold path corrected

[1.2.0] section covers (2026-06-05):
- Added: recall engine (lib/recall.py + CLI)
- Changed: run_git cwd param, constants.py extraction
- Removed: context-tracking subsystem
- Fixed: upgrade self-heal for stale statusline
- Security: shell=True eliminated

[Unreleased] chatroom CHANGELOG.md: still contains V2 agent prompts, 5-phase pipeline, file attachments, LOC refactor, mention-parser fix, stoppedRooms guard — not yet versioned/released (unchanged from 2026-03-24).

**Why:** Alexandria needs to know where to resume on next launch — only commits after the covered commits need processing.
**How to apply:** On next run: `git log 90307bf..HEAD --oneline` for toolkit root; `git log f4196fa..HEAD --oneline -- chatroom/` for chatroom. Check for new code changes not yet in either CHANGELOG.md.
