---
name: boot-memory-mechanics
description: Chronological history of the toolkit's own boot/memory system mechanics (issue #63 → memoria-v2 → 2026-08-25 verification). A chain of checkpoints in time, not duplicated entries — read top to bottom.
metadata:
  type: project
---

This file merges three prior files (`boot-simplification-63-map.md`, `memory-injection-2026-08-09.md`
plus two smaller scan entries) into one chronological record. **Nothing here should be trusted as
"current state" without re-checking the newest entry first** — each entry below records what was true
on ITS date, and several things it describes have since been replaced or removed. Zones: `boot`,
`memory` (per `gitmem zones list`, confirmed 24 zones exist 2026-08-25).

## 2026-07-04 — spec-kit (.ref-repos/spec-kit) mechanics research, for own-toolkit design

Read `templates/commands/*.md` (10), root `templates/*.md` (5), `scripts/bash/*.sh` (5),
`src/specify_cli/__init__.py`, `init.py` (partial), `workflows/steps/gate/__init__.py`,
`workflows/speckit/workflow.yml`, `.specify/memory/constitution.md`. Ref-repo still present at this
path as of 2026-08-25 (unlike marketingskills/cc-devops-skills/design repos — see `codebase-patterns.md`).

**Reusable idea (the one worth keeping):** spec-kit's "Constitution Check gate" is NOT automated —
`plan-template.md:39-43` is literally `[Gates determined based on constitution file]`, a placeholder
the AI fills by reasoning over prose. There IS a real automated `gate` step type
(`workflows/steps/gate/__init__.py`) but it's a generic human-in-the-loop approve/reject pause,
unrelated to constitution semantics. **The distinction between a real deterministic gate and an
AI-reasoned "gate" in prose is the single most reusable idea from this repo** — relevant any time this
toolkit's own boot/memory checks are being designed or audited: know which of its gates are code and
which are just instructions to the agent.

Genuinely deterministic (non-prompt) pieces in spec-kit: `create-new-feature.sh` (sequential numbering,
branch slugging), `common.sh:resolve_template`/`resolve_template_content` (override/preset priority
stack), `check-prerequisites.sh` (`[[ -f ... ]]` gating — the only real "hard" gate in the system).

Scope note: only the ~25 SDD-mechanics-relevant files were read out of 452 total in the repo;
integrations/bundler/tests/docs excluded as irrelevant to phase mechanics.

## 2026-07-11 (commit `8f509fc`) — issue #63 boot-simplification map, 6 points

Full scope: `unmassk-toolkit/` on branch `feat/issue-63-simplificacion-boot`, hook registry
`hooks/hooks.json`, against the PRE-memoria-v2 hook tree. **Every file path below from this era is
gone or renamed as of 2026-08-25 — see the verification entry at the end of this file before acting
on any of it.** Kept because the reasoning (why each point was a problem) can still matter if similar
bugs get reintroduced elsewhere.

1. **Managed blocks of CLAUDE.md regenerated on every boot, no version gate.**
   `session-start-crew.py:61` called `upsert_managed_blocks()` unconditionally on every SessionStart,
   never checking `manifest.json`'s version first — even though that check pattern already existed
   elsewhere (`boot_health.py` via `check_version_mismatch()`, see point 3). Two separate code paths
   (SessionStart unconditional + UserPromptSubmit versioned) wrote the same file with the same
   function — race/double-write risk if the manifest was stale exactly at boot.
2. **Auto-upgrade check ran on every UserPromptSubmit, not just once per session.**
   `needs_upgrade()` (`user-prompt-memory-check.py`, then lines 87-142) did 2 file reads
   (CLAUDE.md + manifest.json) on every message, fail-safe to `False` on any error (never looped).
   Triggered `git-memory-install.py --auto` via subprocess (15s timeout, fail-open try/except) only
   when actually behind. Moving this to SessionStart was flagged as a real behavior change, not just
   timing: a mid-session `/plugin update` would then only be caught at the NEXT session.
3. **Skill-drift check (`check_skill_drift()`) false-positived on any project WITHOUT the toolkit's
   own source checkout — confirmed root cause, not a design choice.** `boot_health.py`'s
   `REPO_BASE_DIR` was computed as 3 `dirname()` up from the module's own file location. In the dev
   repo that correctly reaches `<GIT_ROOT>`. In production (any installed project, running from
   `~/.claude/plugins/cache/.../unmassk-toolkit/<version>/lib/`), those same 3 `dirname()` calls
   landed on the plugin's own CACHE folder — whose subdirectories are VERSION numbers, not plugin
   names. `_build_repo_skill_index()` then built a bogus index mapping skill names to whichever
   cached version `os.listdir()` happened to return (non-deterministic order, no semver sort), and
   `check_skill_drift()` compared the newest cached version against that bogus index — i.e. against
   ANOTHER cached version of itself, not the real repo. Any project with ≥2 cached toolkit versions
   (normal after any `/plugin update` that doesn't purge old ones) could spuriously "detect drift".
   Zero tests existed for this path (`grep check_skill_drift\|boot_health tests/` → nothing). Bug
   present unchanged since `037e0cb` (2026-03-17, v1.0.0) — ~4 months at time of mapping.
4. **3 migrations ran on every boot, in `lib/boot_migrations.py`, via
   `session-start-boot.py:run_preboot_migrations():236-284`:** `_migrate_runtime_to_unmassk()` (moves
   legacy `.claude/`-root JSONs into `.claude/.unmassk/`, pre-1.0), `_migrate_untrack_generated_jsons()`
   (git-untracks generated JSONs old installs committed by mistake), and
   `_migrate_stale_context_writer_statusline()` (repairs/removes a global `statusLine.command` pointing
   at a deleted `context-writer.py`, introduced `df0a4a1` 2026-06-05). None had a "already ran" marker
   — each just checked current filesystem state and no-op'd if clean. `bin/git-memory-upgrade.py:206`
   had its OWN separate re-implementation of `_migrate_runtime_to_unmassk()` — two sources of truth
   for the same migration, same risk pattern flagged elsewhere for `BANNED_TOOLS`/`RESERVED_AGENT_NAMES`
   in the chatroom project (see `external-project-scans.md`).
5. **Self-healing after a rebase/history-rewrite existed only as PROSE, never as code.**
   `skills/unmassk-gitmemory/SKILL.md:491-505` described "compare known commit hashes with current
   tree, detect amnesia, rebuild conservatively" — but exhaustive grep (`rebase`, `amnesia`,
   `self-heal`, `reconstruct`, `heal`, `orphan`, `_gap`) across `hooks/`+`lib/`+`bin/` found no code
   that persists a list of known commit hashes, detects their disappearance, or reconstructs anything.
   What actually happened on boot was passive: `git log --grep=...` against the live tree, so a
   rebased-away commit just silently stopped appearing — no crash, but also no explicit warning,
   which was exactly the gap the issue wanted closed.
6. **The `[memory-check]` reminder text printed on every UserPromptSubmit was mostly redundant with
   `CALIBRATION.md`.** 577 chars / 95 words, restating durable/non-derivable/not-already-captured
   criteria already in CALIBRATION.md:23,56,195 nearly verbatim. Tests only asserted the literal
   `"[memory-check]"` prefix as substring, never the full body — safe to shorten as long as that
   prefix and a non-ASCII character survived somewhere in the output (a cp1252-encoding regression
   test depended on a `→` character being present in SOME line printed by this hook).

**Coverage of this pass:** 8 files read in full (session-start-boot.py, user-prompt-memory-check.py,
managed_blocks.py, session-start-crew.py, boot_health.py, boot_migrations.py, pre-merge-gate.py,
version.py), ~20 more grepped directly. 9 hooks and most of `lib/` were NOT read — none matched the 6
key-term greps and had no import relationship to the mapped functions.

## 2026-08-04 — memoria-v2 boundary-detector: 8 zero/zero symbols, all false alarms

`tests/memory/test_boundary.py::_symbol_usage_report` flagged 8 symbols in `unmassk-toolkit/lib/memory/`
as production==0 AND tests==0. All 8 were verdict **INTERNA** (used within their own file by the
module's real entry point — `build_message`→`build_subject`, `parse_message`→`parse_subject`,
`validate_note`→`validate_type`, `run_git_log`→`is_unborn_branch`, plus dict-literal construction of
FieldSpec/TypeSpec) — none dead.

**Reusable finding — a blind spot in the detector itself, not a code bug:** every test file that
imports `lib/memory/format.py` aliases its fixture away from the module stem (`fmt`, `format_mod`,
`format_lib` — never `format`, because that shadows Python's builtin). The detector's test-branch only
recognizes a touch when the pytest fixture PARAMETER NAME equals the module stem exactly
(`params & stem_set`). Consequence: **the detector can never see any test coverage of `format.py`'s
symbols, system-wide.** Produced 2 false "tests=0" negatives at the time
(`build_subject`/`parse_subject`, actually called as `fmt.build_subject(...)` in
`test_format.py::test_emoji_after_brackets_enforced`). If this detector (or one like it) gets reused
elsewhere, check for aliased fixtures before trusting a "0 tests" row. Confirmed as of 2026-08-25 that
`tests/memory/test_boundary.py` still exists (EXECUTED `find`).

## 2026-08-09 — memoria-v2 redesign snapshot (superseded points 1/2/6 above, NOT 3/4/5)

Written right after the `memoria-v2` redesign (docs moved to `docs/deprecated/memoria-v2/`,
2026-08-05). At the time this was written it explicitly said points 3/4/5 of the 07-11 map "siguen
siendo válidas... no se reverificaron en esta pasada" — i.e. it only superseded the memory-injection
parts (1, 2, 6), not the skill-drift bug, the migrations inventory, or the self-healing prose gap.

**Hooks live at that date (`hooks/hooks.json`):** SessionStart = `boot_launcher.py` +
`session-start-crew.py`; PreToolUse = `customs.py` (Bash), `pre-merge-gate.py` (Bash),
`validate-memory-path.py` (Write|Edit); UserPromptSubmit = `user-prompt-memory-check.py`; Stop =
`stop-dod-gate.py`. Eight files in `hooks/`. **This list is stale — see 2026-08-25 below, the Stop
hook and a whole new PostToolUse hook changed since.**

**Boot report is deliberately NOT injected (decision B4, owner's).** `bin/memory/boot.py:main()`
writes the full report to `.claude/.unmassk/boot-latest.txt` and only prints the order to load the two
skills + the file path + "read it whole, it's not summarized" — because a hook has a context-size cap
and a report with twenty walls gets truncated from the end, which is exactly where health warnings sit.

**The v1 recall engine (`recall_relevant()`) is confirmed DEAD, not just disconnected.** No
`lib/recall.py`, no `bin/git-memory-recall.py` in the tree. `lib/memory/similar.py:27-34` documents it
explicitly: written, 8 tests green, zero consumers. Remaining "recall" mentions in
`lib/parsing.py`/`lib/git_helpers.py`/`lib/incidents.py` are stale docstring references to already-retired
hooks (`pre-task-recall.py`, `session-start-boot.py`, `precompact-snapshot.py`) — none exist. **Still
true as of 2026-08-25** (re-grepped: `recall_relevant` only in `tests/test_user_prompt_recall.py`,
`tests/test_hardening_recall.py`, and that same `similar.py` docstring mention).

**No `PreToolUse` hook on `Task`/`Agent` existed then, and grep for `modifiedInput`/`hookSpecificOutput`
across `hooks/`+`lib/`+`bin/` was empty** — no subagent gets memory rewritten into its prompt by a hook.
Consistent with CLAUDE.md's "nothing reaches an agent on its own" rule (now R-010/R-011 per the current
CLAUDE.md, 2026-08-23). Not re-verified on 2026-08-25 (would need the same grep re-run; nothing in this
pass's checks touched PreToolUse/Task wiring).

**`user-prompt-memory-check.py` had already dropped the long `[memory-check]` text** (point 6 of the
07-11 map) — issue #69, decision `1e94975` "recall push→pull". Only a filler line remained:
`"[memory-check] No skill match this turn — nothing to report."`.

**Residue flagged for Alexandria (doc-stale, not dead code):**
`lib/parsing.py:sanitize_trailer_value()` docstring still named retired callers (recall,
session-start-boot, precompact-snapshot) instead of the real ones (`lib/incidents.py`,
`bin/git-memory-log.py`, `bin/git-memory-doctor.py`). Not re-verified 2026-08-25.

## 2026-08-25 — verification pass for this compaction (EXECUTED)

Everything above describes a moving target. Checked against the live tree today:

- **`hooks/hooks.json` changed again since 2026-08-09.** Current wiring (READ, full file): SessionStart
  = `boot_launcher.py` + `session-start-crew.py` (unchanged); PreToolUse = `customs.py` (Bash),
  `validate-memory-path.py` (Write|Edit), `pre-merge-gate.py` (Bash) (unchanged); UserPromptSubmit =
  `user-prompt-memory-check.py` (unchanged); **PostToolUse (Skill matcher) = `skill-checklist-inject.py`
  — new hook type, didn't exist 2026-08-09; Stop = `checklist-gate.py` — `stop-dod-gate.py` is GONE**
  (only stale `.pyc` files remain in `hooks/__pycache__/`, confirmed EXECUTED find). Anyone reading the
  2026-08-09 "hooks vivos" list as current will look for a Stop hook that no longer exists.
- **Point 3 of the 07-11 map (skill-drift path bug) is now MOOT — the whole mechanism was replaced,
  not patched.** `lib/boot_health.py` is down to 65 lines with only `_md5_file()` and
  `_latest_version_dir()` — `check_skill_drift()` and `check_version_mismatch()` no longer exist there
  (READ, full file). A new module `lib/cache_sync_check.py` (188 lines) does the comparison instead,
  via `_dir_fingerprint()` / `_compute_drift()` / `check_repo_cache_sync()` / `count_repo_cache_drift()`
  — a directory-fingerprint diff, not the old repo-index-vs-cache approach that had the path bug. This
  reads as the bug's actual fix, just done as a rewrite rather than a patch to the old function.
- **Point 4 (the 3 boot migrations) is also MOOT.** `lib/boot_migrations.py` no longer exists in
  `lib/`, and `grep -rl "_migrate_\|def.*migrat" lib/ hooks/ bin/` returns no file that defines an
  actual migration function (the 3 hits it does return — `upgrade_check.py`, `hooks_doc.py`,
  `_symlink_safe_open.py` — are comments/docstrings mentioning `tests/test_migrate_statusline.py` by
  name, not migration code). The 3 migrations described in the 07-11 map (runtime-dir move,
  untrack-generated-jsons, statusline repair) appear to have been retired outright.
- **Point 5's file path is stale by rename, not verified further.** `skills/unmassk-gitmemory/` no
  longer exists — the skill is now `unmassk-memory` (+ a new `unmassk-memory-doctor`, EXECUTED `ls
  skills/`). Whether the self-healing prose from the old `SKILL.md:491-505` migrated into
  `unmassk-memory/SKILL.md` was NOT checked this pass — flagging, not claiming either way.
- **`gitmem` (the CLI, `/Users/unmassk/.local/bin/gitmem`) is the live command surface** described in
  this project's CLAUDE.md ("nueve comandos bajo gitmem", memory as commits). This is a further
  generation beyond even the 08-09 snapshot, which still described `boot.py`/hooks as the whole story.
  Not mapped in detail here — out of scope for a memory-compaction pass; a fresh Bilbo exploration
  would be needed to map `gitmem`'s command surface itself if that's ever the ask.

**What this means for anyone reading this file cold:** trust the 2026-08-25 entry for "does X still
exist", trust 07-11/08-04/08-09 only for "why was X considered a problem" — the reasoning survives even
where the code doesn't.
