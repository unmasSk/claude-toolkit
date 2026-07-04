---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-07-04 (third pass same day)
Last commit covered (toolkit root): d2ca4b7 (fix(plugin/architecture): fix real frontmatter trigger-phrase collisions found by council validation + speed up skill-router tests 60x) — HEAD at time of this audit, working tree otherwise clean.
Last commit covered (chatroom): f4196fa (fix(plugin/chatroom/frontend): formatContent keeps agent name capitalized in queue messages) — not re-checked this pass, no chatroom commits in the range reviewed.
Current version in plugin.json: v1.13.0 released (chore 05fce42). [Unreleased] filled again (2026-07-04) with the single commit that landed right after that release (d2ca4b7) — version bump is NOT Alexandria's job, that's release.py's.

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] now has (2026-07-04, commit d2ca4b7 only):
- Added: per-message skill-router nudge — `hooks/user-prompt-memory-check.py` + new `lib/skill_router.py` (`match_skills()`, `SKILL_TRIGGER_PHRASES` dict for all 9 protocol skills). Fires on every user message, appends `[skill-router] Possibly relevant skill(s): ...`, never blocks. Drift-guard test (`tests/test_user_prompt_skill_router.py`) loads live SKILL.md descriptions and asserts every trigger phrase is a substring of its own skill's real description.
- Changed: `lib/managed_blocks.py` Protocols block body extended with `unmassk-flow`, `unmassk-audit`, `unmassk-flow-stack` rows (decision 1c0070b: these were shipped+tested but excluded from the CLAUDE.md menu under an old "only installed+referenced" policy). **Caveat — verified separately, see stale-zones.md**: this only changed the *generator source*; this repo's own root `CLAUDE.md` Protocols block has NOT been regenerated yet and still lacks all 3 rows.
- Fixed: 4 real frontmatter description collisions across `unmassk-grill`/`unmassk-council`/`unmassk-project-lifecycle`/`unmassk-flow-stack` SKILL.md (grill vs council still tied on "two interpretations" vs "which option"; council's own text self-contradicted; project-lifecycle now defers to grill when scope undecided AND to flow-stack when a stack is already named — was one-directional before). CRLF→LF in `unmassk-audit/SKILL.md` (only CRLF file in repo). `test_user_prompt_skill_router.py` 4+min → well under 1s (591-line file, entirely new, in-process `match_skills()` calls instead of per-case subprocess+git-repo spawn; only 6 hook-wiring tests still use subprocess). 85 tests, same coverage.
- No prior-pass entries survive here — the previous [Unreleased] content (grill vagueness preamble, Gitto Mode C, wip-then-squash cadence, etc.) was correctly promoted to [1.12.0]/[1.13.0] by release.py; confirmed both sections read correctly in CHANGELOG.md before writing this pass.

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
**How to apply:** On next run: `git log 4f11e8e..HEAD --oneline` for toolkit root; `git log f4196fa..HEAD --oneline -- chatroom/` for chatroom. Check for new code changes not yet in either CHANGELOG.md.
