---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

## Bookmark

**Last commit that touched `CHANGELOG.md`: `867fd72` (2026-08-25).** `CHANGELOG.md [Unreleased]` currently holds one `### Changed` bullet describing `unmassk-memory`'s opening-session menu (fixed 8-section table: Today/Last session/Blockers/Questions/Incidents/Branch/Issues/Health, one item per line, Health always shown — supersedes the earlier design where Health was a conditional 6th row). `[1.41.0]` (unmassk-groundhog skill) and `[1.40.0]` (memory legibility+integrity batch) are already released and dated.

**On next run:** `git log 867fd72..HEAD --oneline -- CHANGELOG.md` first to see if anyone else already updated it; then `git log 867fd72..HEAD --oneline` for the full range. As of this pass, the 4 commits since `867fd72` (`ba23a71`/`ac53f3a`/`61ce67b`/`2ecfeb0`) are all `[R-0xx]` restriction/rule commits — memory-only per project-context.md's commit-type convention, correctly excluded, nothing pending.

## Durable lessons

- **Never write a manual `## [N.N.N] - date` header in `CHANGELOG.md`.** `bin/release.py` promotes `## [Unreleased]` to the version header itself on release — a manually-added header means `release.py` sees an empty `[Unreleased]` and aborts. Content always goes straight under `## [Unreleased]`, always. (Learned 2026-08-25, first pass of that day — added a manual `[1.40.0]` header, had to remove it same pass.)
- **Verify a CHANGELOG entry's version attribution against `plugin.json` at the actual fixing commit, not the commit message's own claim or which release window it "felt like."** A real misattribution happened 2026-08-23: a bugfix was dated `[1.38.0]` in the entry but `plugin.json` at the fixing commit still read `1.37.0` — it had actually shipped inside `1.37.1`, one release earlier. Fixed by reading `plugin.json` at every commit between the two release tags.
- **`memo`/`decision`/`context`/`wip`/`remember` commit types never go in the CHANGELOG** — they're the memory system's own audit trail, not shipped product changes (see project-context.md). Also excluded by the same logic: edits to `roadmapv2.md`/`ROADMAP.md` alone (confirmed by scanning its full history — 20+ commits, none ever became individual CHANGELOG entries; contrast with the 1.12.0 commit/push-cadence entry, which changed real shipped SKILL.md behavior and correctly was included).
- **Verify every claim in a task-supplied "KNOWN" bullet list against the actual code/skill file before writing the entry — don't transcribe it as given.** This has caught real drift more than once: a task's KNOWN block claiming a fact was anchored in "the managed block of CLAUDE.md" turned out false on grep (2026-08-25, `unmassk-groundhog` pass); a task's paraphrase of a diff described a "CSS combo" fix that the actual diff didn't contain (2026-08-24 pass, wrote what the diff really showed instead).
- **A doc-only/CHANGELOG-only pass still owes a check of the 3-surface rule** (README/docs, CHANGELOG, SKILL.md/CLAUDE.md) even when scope is restricted to one file — flag what's out of scope rather than silently skip it. Recurring pattern: several 2026-08-25 passes found the skill prose itself had drifted (e.g. "always these five labeled sections" left un-updated after the table grew to eight rows) while fixing only the CHANGELOG bullet — correctly flagged, not fixed, out of that pass's file scope.

## Historical pass index (compact — full narrative recoverable via `git log` for each range)

| Date(s) | What shipped | Notes |
|---|---|---|
| 2026-08-25 (4 same-day passes) | 8-section opening-menu table (D-060/D-062/D-063/D-064), `unmassk-groundhog` skill, v1.40.0 memory-legibility batch | See Bookmark above for final state |
| 2026-08-24 | Program-set checklists (D-052/M-125), shared delegation template + blind-review template, "excuse" tables on all 9 agent cards, `unmassk-scaffolding` reference split, `lib/memory/rules.py`/`zones.py` split | Prep for 1.39.0 |
| 2026-08-23 | Modo automático, Spanish-phrase skill router, `gitmem rule --quote`, Argus/Bilbo verification tags, Dante/Ultron lose `Task` tool | 1.38.0; misattribution fix noted above landed same pass |
| 2026-08-20 | `stop-dod-gate` exit-code classification (D-042) | Later fully retired by D-046 |
| 2026-08-06 | `hooks/customs.py` rescue-command robustness, `stop-dod-gate.py` corrupt-config handling, CI hardening | Pre-1.29.2 |
| 2026-08-02 – 2026-08-05 | memoria-v2 build/merge — false-promise fixes in `unmassk-audit`/`unmassk-flow` prompts, `feat/memoria-v2` → `main` merge gate (the `gitmem` 9-subcommand system itself) | Target docs since moved to `docs/deprecated/`, see doc-map.md |
| 2026-07-25/26 | Trailer-content validation moved to the wrapper, dead validation-hook layer retired | 1.24.0 prep |
| 2026-07-18 | Issue #72 (anti-attacker test cut, ~9.6k lines) + issue #61 (9 read sites wrapped in retry) | |
| 2026-07-16 | MCP on-demand pattern rolled to 6 plugins | See doc-map.md "Other plugins" |
| 2026-07-13/14 | `unmassk-pentesting` v1.0.0 (30 skills), `unmassk-design` 1→7 skills | See doc-map.md "Other plugins" |
| 2026-07-12 | BM25 skill-search gate retired entirely | |
| 2026-07-04 – 2026-07-11 | Boot simplification (issue #63), issue #60 (freshness stamp), issue #55 (date parsing), issue #49 (multi-machine freshness) | |
| 2026-03-14 – 2026-03-24 | chatroom docs/JSDoc, root CHANGELOG structure fixes (duplicate `[1.1.0]` tag renamed) | |

**Why:** Alexandria needs to know where to resume on next launch — only commits after the bookmark need processing. The historical index exists only so a date can be located; it is not a substitute for reading `CHANGELOG.md` itself, which already has the real entries.
