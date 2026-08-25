---
name: stale-zones
description: Documentation zones known to be outdated or needing review — revisit on next run
type: project
---

## Open, not yet fixed

- **`unmassk-close-session/SKILL.md` and `unmassk-council/SKILL.md` have zero mention of the program-set checklist mechanism** (D-052/M-125, shipped 1.39.0) even though `checklists/close-session.json` and `checklists/council.json` gate them via `hooks/checklist-gate.py`. Re-verified 2026-08-25 (this pass): `grep -il checklist` on both files still returns nothing. Likely deliberate — the design's whole point is the hook injects the boxes live, Claude doesn't need to know in advance — but flagged every pass since 2026-08-24 because close mode's 4-surface table doesn't cover SKILL.md and nobody has made the call either way. Ask the owner once instead of re-flagging forever.
- **`D-056` (the 1.40.0 memory-legibility batch's scoping decision) has no closing/confirmation `gitmem` note** recording it shipped — unlike `M-125`, which explicitly confirmed `casillas-por-programa` landed in 1.39.0. Not lost (3 commit messages + `CHANGELOG.md [1.40.0]` record it), just missing the project's usual "decision → closing note" convention. `gitmem` write access is outside Alexandria's permissions — someone else's to close.
- **`docs/plan/fix-stop-dod-gate-loop-and-issue-field.md`** says "D-046 retiró la entrada Stop de hooks.json entera" — imprecise, the `Stop` key still exists in `hooks/hooks.json` (now points at `checklist-gate.py` instead of the retired `stop-dod-gate.py`). The substantive claim (`stop-dod-gate.py`/`stop-dod-declare.py` don't run on any `Stop` anymore) is accurate. Cosmetic, doesn't mislead a reader — low priority.
- **`compliance-legal-docs`'s 42 reference files: only 12 have been individually verified**, the other 30 were sampled (12 names listed in the original pass) and found clean but never read file-by-file. Only relevant if this plugin becomes active again.
- **`chatroom/docs/`** was flagged "not deeply audited" against later frontend/backend changes (Tauri shell, brainstorm mode filters, rate limiting) — `websocket-protocol.md`, `agent-invocation-pipeline.md`, `module-reference.md` are the priority re-reads if chatroom work resumes. `chatroom/CHANGELOG.md [Unreleased]` also has no version stamp and is missing several already-shipped features — needs a backfill pass before chatroom's next release.
- **Root `CHANGELOG.md [Unreleased]` has (or had) two separate `### Fixed` headers** instead of one — cosmetic against Keep a Changelog's "group by type" convention, not a factual error. Worth collapsing next time `[Unreleased]` is touched for an unrelated reason; check before assuming this is still true, hasn't been re-verified since 2026-07-18.

## Closed this pass (2026-08-25 compaction — verified against current code)

- **`unmassk-memory/SKILL.md`'s v1.40.0 gap is fixed**, contradicting the "open" entry this same file carried until now: `grep` for `--chain`/`archivada`/`sustituye`/`retract`/`replaces` in the file now finds all of them (lines 283-285, 335-336), fixed by commit `54a244e` the same day the gap was flagged. See doc-map.md's Active-zone table for the full evidence. **Lesson:** a "not fixed" memory entry is a claim exactly as perishable as a "fixed" one — both need re-checking before being trusted, not just the optimistic direction.

## Orchestrator-owned, flag-only (not mine to fix, re-check if the orchestrator ever touches them)

- `unmassk-core/SKILL.md:44` vs `:77` (self-search claim vs skill-gate claim, both stale against the no-BM25 reality since 2026-07-12) and `unmassk-audit/SKILL.md:273` ("loads via BM25 skill search" — actually loads by frontmatter). Flagged 2026-07-12, unconfirmed whether fixed since.
- `unmassk-core/SKILL.md:40` — still may say "unmassk-design | 1 skill" (revamped to 7 on 2026-07-14). Flagged 2026-07-14, unconfirmed since.

## Durable lessons from resolved zones

See doc-map.md's "Durable lessons" section — the "how we recover from X reads as plausible" lesson, the "check a Moriarty/Cerberus verdict against their own MEMORY.md directly" lesson, and the "surrounding paragraph may cite a newer decision than the brief" lesson all originated from zones fully cleared and compacted out of this file (the 2026-08-02/03 memoria-v2-era passes — see doc-map.md's "Retired" section for what those zones were).

**How to apply:** On each launch, re-run the verification behind every "Open" item above before re-flagging it — don't just copy the line forward. An item that's actually closed and left marked open is as much a coverage gap as a real gap left unflagged.
