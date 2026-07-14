---
name: stale-zones
description: Documentation zones known to be outdated or needing review — revisit on next run
type: project
---

## Cleared zones (fixed 2026-07-11, issue #63)

- `unmassk-toolkit/skills/unmassk-gitmemory/SKILL.md` "Self-Healing (rebase/reset detection)" + "Force Push Handling" sections (~lines 491-507): described automatic amnesia/history-rewrite detection ("compare known commit hashes", "detect history rewrite... SHAs missing from tree") that never existed as code — pure prose, confirmed by repo-wide grep (zero hits for `amnesia`/`reflog`/`history rewrite` in `lib/`, `hooks/`, `bin/`). This was flagged CRITICAL by the requester because the fiction had persisted undetected through prior Alexandria passes. Rewrote to `### Passive Healing`, describing the real mechanism (live `git log` re-extraction every boot via `extract_memory()`, no stored hash comparison, no reconciliation). **Lesson: a "how we recover from X" section reads as plausible and doesn't get challenged like a feature claim does — actively grep for the implementing code behind recovery/safety-net prose, don't just check it's internally consistent.**
- Same file, "Version marker auto-sync" bullet (~line 108): said `UserPromptSubmit`/per-message; the check moved to `SessionStart`/once-per-session in issue #63. Corrected.

## Cleared zones (fixed 2026-03-24)

- chatroom/CHANGELOG.md [Unreleased] Removed section: falsely said moriarty-system-prompt-v2.md still exists after it was deleted — corrected
- Root CHANGELOG.md: missing [Unreleased] section — added
- Root CHANGELOG.md: duplicate [1.1.0] version tag — old entry renamed [1.1.0-gitmemory]
- chatroom/README.md: test count was 535+ (stale) — corrected to 1200+
- chatroom/CLAUDE.md and chatroom/apps/backend/CLAUDE.md: brainstorm mode undocumented — added
- chatroom/apps/backend/CLAUDE.md: WS message types undocumented — added
- Root CLAUDE.md Protocols menu / build-mode wording gap (fixed 2026-07-04, commit 278b41b): root CLAUDE.md now has `unmassk-flow-stack`, `unmassk-flow`, `unmassk-audit` rows and the "Execute step of `unmassk-flow` (the build pipeline skill)" wording — confirmed via `git diff CLAUDE.md` (empty against HEAD). No action needed.

## Active stale zones

### unmassk-core/SKILL.md:40 — unmassk-design skill count stale (flagged 2026-07-14, not fixed by Alexandria)
Says `unmassk-design | 1 skill | Design systems, color, typography, motion, accessibility, agentic UX` — now stale, the plugin revamped to 7 skills (core + design-motion/design-3d/design-scroll/design-animation-formats/design-taste/design-flutter) on 2026-07-14. Root `README.md`'s matching row was fixed this same pass. `unmassk-core/SKILL.md` is explicitly orchestrator-owned per the 2026-07-12 precedent below (core/gitmemory/audit SKILL.md are the orchestrator's own docs) — flagged only, not edited. Re-check on next pass whether the orchestrator updated it.

### unmassk-core/SKILL.md and unmassk-audit/SKILL.md — BM25 skill-search claims, orchestrator-owned (flagged 2026-07-12, not fixed by Alexandria)
`unmassk-core/SKILL.md:44` says "the agent runs BM25 skill search and loads the matching skill automatically" — contradicts `:77` which correctly says agents no longer search themselves. Both are now stale against the current reality (BM25 gate retired entirely 2026-07-12, decision `5d660b4`, tag `bm25-skill-gate-1.19.9`): the orchestrator loads all skill frontmatter and picks/injects by criterion — there is no gate hook doing BM25 anymore either. `unmassk-audit/SKILL.md:273` says unmassk-standards loads "via BM25 skill search" when it actually loads via frontmatter (`skills:` in agent frontmatter). These 3 files are explicitly orchestrator-owned per task instructions (not Alexandria's — core/gitmemory/audit SKILL.md + agents/*.md are the orchestrator's own docs), so Alexandria only flags, doesn't edit. Re-check on next pass whether the orchestrator has fixed them.

### chatroom/CHANGELOG.md [Unreleased] — no version stamp
Recent commits (Tauri 2 shell, stdin delivery, repo cwd selector, security hardening, tab title, queue messages) are NOT in the chatroom changelog at all. The [Unreleased] section covers up to the LOC refactor but not the more recent frontend/backend changes. If chatroom cuts a release, a significant backfill is needed.

### chatroom/docs/ folder — not deeply audited
Docs may have drifted given volume of changes. Priority files to re-verify: websocket-protocol.md (brainstorm mode, clear_queue, stop_all not documented there), agent-invocation-pipeline.md (brainstorm mode filter not shown in the spawn example), module-reference.md.

## Cleared zones (fixed 2026-07-05)

- project-context.md memory file version was stale (said 1.1.1) — corrected to 1.15.0.

## Cleared zones (fixed 2026-07-07)

- SKILL.md `unmassk-gitmemory` had zero mention of the boot-time `git fetch`/freshness behavior at all (not stale wording — a genuine coverage gap, the whole issue #49 feature was undocumented for Claude). Added Boot Protocol paragraph + Wrapper Scripts bullet. Root README.md Memory row didn't mention multi-machine sync either — added one clause.

