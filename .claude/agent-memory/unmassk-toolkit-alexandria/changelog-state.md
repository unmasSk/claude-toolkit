---
name: changelog-state
description: Tracks the last changelog update date and what was included, so future runs only process new commits
type: project
---

Last full audit: 2026-07-07 (seventh pass — issue #49 multi-machine boot memory freshness, GO from Yoda at 107/110, squash pending). Range documented: `d958659..80cf97e` (HEAD at audit time, clean tree). Verified against code directly, not from the plan doc: `fetch_memory_ref()`/`render_memoria_stamp()`/`check_upstream_shares_history()`/`_win32_kill_tree()` in `lib/boot_git_checks.py` and `lib/git_helpers.py`, `resolve_boot_memory()`/`_merge_diverged_memory()` in `lib/boot_memory.py`, the origin-sha cache key in `lib/boot_glossary_cache.py`, `_check_behind_warn_only()` + pre-existing `SUBJECT_MAX_LEN=100` cap in `bin/git-memory-commit.py`, and the two same-day fixes in commit 6fc6386 (`time_ago` `OverflowError`, `_win32_kill_tree` schtasks cross-ref docstring note — confirmed the latter is a comment-only change, not a behavior fix, so it was folded into the Added feature's "known limitation" prose rather than mislabeled under Fixed). SKILL.md `unmassk-gitmemory` updated: new "Multi-machine freshness" paragraph in Boot Protocol, new bullet in Wrapper Scripts for the warn-only behind notice. README.md Memory row got one clause. No root CLAUDE.md change needed — `lib/managed_blocks.py` has no boot-freshness-specific content to regenerate, and the existing generic "read SessionStart output" instruction already covers the new MEMORY:/PULL DIRECTIVE lines without modification. `docs/plan/feat-boot-freshness.md` is an internal Flow-pipeline planning artifact (not a Diátaxis doc for the three-audience rule) — left untouched, same treatment as roadmapv2.md-only edits.
Last commit covered (toolkit root, sixth pass): 51a3c44 (decision: F6 hard-link bypass deferred past v1.16.1) — HEAD at time of this audit. The fix itself (`git_helpers.py`, `_symlink_safe_open.py`, `version.py`, `boot_health.py`, 4 hooks, `skill-search.py`) is UNCOMMITTED working-tree changes at audit time, documented into [Unreleased] ahead of the commit/release so `bin/release.py` has content to promote. Verified every changed file's diff against HEAD directly (not from memory): `os.O_NOFOLLOW` Windows branch in both twins (`open_no_follow_symlink`/`open_no_follow_symlink_fallback`), `encoding="utf-8"` added to `run_git`, `version.py`, `boot_health.py` (3 subprocess/open sites), 4 hooks, and `os.pathsep` in `scripts/skill-search.py`. Previous audit (fifth pass, f6cc6ac) superseded by this one.
Last commit covered (chatroom): f4196fa — not re-checked this pass, no chatroom commits in the range reviewed.
Current version in plugin.json: v1.15.0 released (chore f1dcb8e). [Unreleased] now covers the 2026-07-05 boot-hook incident: started as a truncation bug (SessionStart stdout losing the `Next:` instruction on large briefings), escalated via a 14-round Cerberus+Argus audit into 3 real security fixes (parent-directory `.claude` symlink escape closed by new `verify_path_within_project()` chokepoint in `lib/git_helpers.py`, 9 call sites; untrusted git-commit content reaching Claude's context unsanitized at several render sites; control-byte log-injection via forged `\x1e`/`\x1f` separators, fixed with `git log -z`) plus a structural refactor (session-start-boot.py 1278→330 lines + 6 lib modules; git-memory-bootstrap.py 936→143; git-memory-install.py 541→252; doctor.py/upgrade.py accepted as documented 500-line-limit exceptions). Verified against code: `verify_path_within_project()` docstring/9 call sites, `_sanitize_trailer_value` (21 call sites), `git log -z` (2 sites in boot_memory.py), all line counts via `git show <old-commit>:<path> | wc -l` vs current. SKILL.md `unmassk-gitmemory` updated: confirmed the existing "boot stdout always banner" note was already accurate (no change needed there), added a new "Filesystem Safety Pattern" section documenting `verify_path_within_project()` as canonical for any new `.claude/` filesystem code. ROADMAP.md checked — no stale/contradictory entries (this was unplanned incident work, correctly absent from roadmap).

Root CHANGELOG structure note: Three product timelines merged into one file. Old git-memory [1.1.0] entry was renamed [1.1.0-gitmemory] on 2026-03-24 to avoid collision with toolkit [1.1.0].

[Unreleased] now has (2026-07-04, commits 278b41b + 4042f28):
- Added: project startup quality floor — `unmassk-project-lifecycle`'s START branch (`unmassk-toolkit/skills/unmassk-project-lifecycle/SKILL.md`) gains a step, before the first feature commit on a new project, confirming a working test command, lint/format config, and a `.env.example` (if secrets are implied). Missing pieces must be logged as `decision()`, not silently skipped. A small slice of the frozen "solid project startup guide" roadmap idea that a validation council found didn't depend on the memory/consolidator maturity gate the rest of that idea is waiting on.
- Excluded (by design, see precedent note below): 278b41b also added a "roadmap worked in written order" discipline to `roadmapv2.md`'s "Cómo trabajamos" section. This is a `roadmapv2.md`-only edit (internal project bookkeeping), not a shipped product change — left out of CHANGELOG, already covered by the roadmap edit itself + the `decision()` git-memory commit.

**Precedent confirmed this pass — roadmapv2.md-only edits never go in CHANGELOG:** scanned full `git log -- roadmapv2.md` history (20+ commits touching only that file: adding/removing candidates, marking items done, reordering). None ever appear as individual CHANGELOG entries. Contrast with the 1.12.0 "commit/push cadence" entry, which WAS included — that one changed real shipped `unmassk-gitmemory`/`unmassk-flow` SKILL.md behavior, not just a roadmap note. Applied this distinction to exclude the roadmap-order-discipline item above.

- No prior-pass entries survive here — the previous [Unreleased] content (skill-router nudge, protocols menu extension, frontmatter collision fixes) was correctly promoted to [1.14.0] by release.py; confirmed the section reads correctly in CHANGELOG.md before writing this pass.

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
**How to apply:** On next run: `git log 80cf97e..HEAD --oneline` for toolkit root (supersedes the old `51a3c44..HEAD` marker — 1.16.1 already released and this pass's #49 entry already covers everything through 80cf97e); `git log f4196fa..HEAD --oneline -- chatroom/` for chatroom. Check for new code changes not yet in either CHANGELOG.md. Note: [Unreleased] (issue #49 entry) is not yet versioned — a squash/merge is pending per Yoda's 107/110 GO, then the next `release.py` run stamps it as the next version. Also check `git status`/`git diff HEAD` for uncommitted working-tree changes, not just `git log`.
