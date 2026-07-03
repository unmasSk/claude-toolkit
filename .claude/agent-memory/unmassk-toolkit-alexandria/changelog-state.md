---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-07-03
Last commit covered (toolkit root): 5ee3c04 (fix(plugin/i18n): fix hardcoded Spanish forced onto every toolkit installer)
Last commit covered (chatroom): f4196fa (fix(plugin/chatroom/frontend): formatContent keeps agent name capitalized in queue messages)
Current version in plugin.json: check at next release — v1.11.0 already tagged/released (ecd8ce8); [Unreleased] below it now holds post-release fixes queued for a v1.11.1 patch.

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] now has entries (2026-07-03, Alexandria doc sync, prepped for v1.11.1):
- Changed (commit 0fc88ee, 2026-07-03): README "Standards" row corrected 33→34 sections to match §34 already shipped in v1.11.0.
- Fixed (commit 5ee3c04, 2026-07-03): hardcoded Spanish forced onto every toolkit installer regardless of language, across `lib/managed_blocks.py`, `skills/unmassk-standards/references/standards.md` §18, `hooks/pre-task-recall.py`, `hooks/session-start-boot.py`, `skills/unmassk-project-lifecycle/references/prd-template.md`, `bin/git-memory-commit.py` — all now English/language-neutral. Found via Bilbo full-surface sweep.
- Deliberately excluded: commit 9719856 (docs/gitto-consolidador-DRAFT.md revised per council review) — internal draft doc, not installed/shipped functionality (still pending Bex's final read-through before wiring into agents/gitto.md). Not changelog-worthy for external consumers; would be noise. Also excluded: b71b13f (context/session-close), 1b2b30e (memo retraction), 4c1d040 + 45ca924 (remember commits) — memory/context bookkeeping, not code changes.

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
**How to apply:** On next run: `git log 6611017..HEAD --oneline` for toolkit root; `git log f4196fa..HEAD --oneline -- chatroom/` for chatroom. Check for new code changes not yet in either CHANGELOG.md.
