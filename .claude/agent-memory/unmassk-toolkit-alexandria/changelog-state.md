---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-06-05
Last commit covered (toolkit root): 9cd42b8 (merge: eliminar subsistema de seguimiento de contexto, + auto-cura statusline)
Last commit covered (chatroom): f4196fa (fix(plugin/chatroom/frontend): formatContent keeps agent name capitalized in queue messages)
Current version in plugin.json: 1.1.1 (unmassk-toolkit) — [Unreleased] section now populated

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] contains (root CHANGELOG.md as of 2026-06-05):
- Added: recall engine (lib/recall.py + bin/git-memory-recall.py, IDF ranking, BM25-style tokenization, dedup, full history scan)
- Changed: git_helpers.run_git gains cwd param; TOMBSTONE_KEYS/RECALL_KEYS extracted to constants.py
- Removed: context-tracking subsystem (context-writer.py, statusline wrapper, % warnings, install/uninstall/upgrade lifecycle)
- Fixed: upgrade self-heal for stale statusline pointing at deleted context-writer.py
- Security: shell=True in context-writer.py eliminated (issue #48, T1) by file deletion

[Unreleased] chatroom CHANGELOG.md: still contains V2 agent prompts, 5-phase pipeline, file attachments, LOC refactor, mention-parser fix, stoppedRooms guard — not yet versioned/released (unchanged from 2026-03-24).

**Why:** Alexandria needs to know where to resume on next launch — only commits after the covered commits need processing.
**How to apply:** On next run: `git log 9cd42b8..HEAD --oneline` for toolkit root; `git log f4196fa..HEAD --oneline -- chatroom/` for chatroom. Check for new code changes not yet in either CHANGELOG.md.
