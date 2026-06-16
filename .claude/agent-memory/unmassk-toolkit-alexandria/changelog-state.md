---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-06-16
Last commit covered (toolkit root): aa9b32e (feat(plugin/memory): el disparador del consolidador)
Last commit covered (chatroom): f4196fa (fix(plugin/chatroom/frontend): formatContent keeps agent name capitalized in queue messages)
Current version in plugin.json: 1.7.0 (released 2026-06-12) — next release will promote current [Unreleased]

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] now has entries (2026-06-16, Alexandria doc sync):
- Orchestrator recall (documented 2026-06-12): UserPromptSubmit hook injects relevant memory into main Claude thread per message; recall_relevant() BM25/IDF gate; anti prompt-injection framing; _sanitize strips memory-data delimiters; fail-open; 70 tests; Yoda READY 107/110.
- Crown marker (2026-06-16, commits 5d5da3e): Crown trailer marks the canonical "king" entry per memory category; boot renders it first with 👑 outside normal budget; VALID_KEYS + MEMORY_KEYS; 21 tests. Phase 1 of consolidator — infrastructure only.
- Consolidation trigger (2026-06-16, commit aa9b32e): boot emits CONSOLIDATE: block when commits since last context(consolidation) >= threshold (default 50, env-overridable); commits_since_last_consolidation() in lib/git_helpers.py; 11 tests. Phase 2 of consolidator — trigger only; Gitto prompt is draft in docs/gitto-consolidador-DRAFT.md (Phase 4, pending review).

SKILL.md updated: Crown row added to Trailer Spec table; "Memory consolidation trigger" bullet added to Active Hooks; new "Crown entries (👑)" section added between Active Hooks and Hierarchical Scopes.

[1.6.0] section covers (2026-06-10):
- Added: hard DoD gate (hooks/stop-dod-gate.py, 23 tests)
- Changed: unmassk-core hardened (no trivial code edits by orchestrator)

[1.5.0] section covers (2026-06-10):
- Added: memory dedup gate (hooks/pre-memory-dedup-gate.py, 40 tests)
- Changed: memory capture reminder flipped to restraint

[1.4.0] section covers (2026-06-09):
- Added: release script (bin/release.py + helpers + --path flag + docs/RELEASING.md) + documentation coverage improvements
- Fixed: scope-map path in unmassk-gitmemory SKILL.md, test isolation bug in test_migrate_statusline.py
- Removed: dead weight (!new_skills/, generated-images/, orphaned .pyc)

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
**How to apply:** On next run: `git log da3970c..HEAD --oneline` for toolkit root; `git log f4196fa..HEAD --oneline -- chatroom/` for chatroom. Check for new code changes not yet in either CHANGELOG.md.
