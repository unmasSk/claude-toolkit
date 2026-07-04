---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-07-04 (second pass same day — working-tree changes, not yet committed by Gitto)
Last commit covered (toolkit root): 4f11e8e (docs(plugin/methodology): clarify pipeline-scoped wip-then-squash push cadence in gitmemory + flow skills) — the grill/flow/lifecycle changes below are UNCOMMITTED at time of this CHANGELOG write; re-verify commit hash next audit once Gitto commits them.
Last commit covered (chatroom): f4196fa (fix(plugin/chatroom/frontend): formatContent keeps agent name capitalized in queue messages) — not re-checked this pass, no chatroom commits in the range reviewed
Current version in plugin.json: v1.11.1 already tagged/released (75b4a4f). [Unreleased] below it now filled (2026-07-04) for the next release cut via bin/release.py — version bump is NOT Alexandria's job, that's a separate release.py step.

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] now ALSO has (2026-07-04, second pass, added on top of the entries below which already sit above as [1.12.0] — working tree, uncommitted):
- Changed: `unmassk-grill` extended (not a new skill — spec-kit research + council concluded the mechanism already existed) with a Vagueness preamble, an "Independently testable slice" interview check, and a Bounded mode (5-question cap) for pipeline invocation. `unmassk-flow` Step 0 Triage and `unmassk-project-lifecycle` START now call grill explicitly (previously neither did); Flow Step 1 Brainstorm reuses grill's logged open branches. Orphaned `unmassk-project-lifecycle/references/prd-template.md` deleted (never wired). Files touched: `skills/unmassk-grill/SKILL.md`, `skills/unmassk-flow/SKILL.md`, `skills/unmassk-project-lifecycle/SKILL.md`. `roadmapv2.md` also updated (candidate item resolved) — not changelog-worthy on its own, roadmap bookkeeping only.

[Unreleased] (v1.12.0-era, first pass) entries (2026-07-04, Alexandria doc sync, prepped for next version after v1.11.1):
- Added (commit 5746e78): Gitto Mode C (Consolidator) installed in `agents/gitto.md` — periodic memory-consolidation writing "crown" entries, plus the `Retract-Crown` trailer mechanism (`VALID_KEYS`/`MEMORY_KEYS` in `lib/constants.py`, both trailer-validation hooks require `Why:` alongside it, `session-start-boot.py` excludes retracted crowns and falls back to fully un-crowned rather than resurrecting a superseded crown). 17 new tests (`tests/test_crown_retraction.py`), existing 21 Crown tests unaffected.
- Changed (commit 4f11e8e, decision 6870f1c): pipeline-scoped wip-then-squash commit/push cadence — crew never commits its own work, orchestrator wips per sub-step without pushing, squash+push only once Yoda's verdict + Alexandria's doc pass are both done. Memory commits (decision/memo/remember/context) still push immediately, no exception. `unmassk-flow` Step 7 Close made repo-type-aware (trunk vs gitflow) instead of always assuming gitflow.
- Fixed (commit 82d245b): Gitto Mode C's own grep pattern for reading memory history matched zero commits against this project's real commit format (`<emoji> decision(scope): text`, not `Decision: text`) — caught via a dry-run against the repo's own memory before shipping the feature as done.
- Deliberately excluded (data, not shippable capability): the 5 real crown commits produced by the Mode C dry-run itself (99fe735, 17d15b3, 143f331, 522fdb1, df1a7a6) — these are memory content the feature produced, not the feature. Also excluded per usual convention: remember/context bookkeeping in the same range (efc833f, 4c1d040 + 45ca924 carried over from prior audit, b71b13f, 1b2b30e, 9719856 — already noted as excluded in the prior audit pass).

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
