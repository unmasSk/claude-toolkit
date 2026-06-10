# Changelog

## [Unreleased]

### Added
- Memory dedup gate (`hooks/pre-memory-dedup-gate.py`): PreToolUse/Bash hook that WARNS (non-blocking, fail-open) when a `memo`/`remember` commit is a lexical near-duplicate of an existing entry of the same type — Jaccard ≥ 0.40 over recall's tokenizer with an extended dedup stoplist, naming the match in `permissionDecisionReason`. Decisions are never compared (sacred). Cheap pre-filter regex so the 99% of Bash commands that are not memory commits skip git entirely. 40 tests; validated against the real corpus (does not fire on the iterated "3 memory systems" memos — those are semantic restatements, not lexical dups). Documented in `unmassk-gitmemory` Active Hooks.

### Changed
- Memory capture reminder (`hooks/user-prompt-memory-check.py`): the per-message `[memory-check]` flipped from "contains memory? → save it" to restraint — save ONLY if durable, non-derivable, and not already captured; on a correction, RETIRE the old entry with a tombstone instead of stacking; systemic/process rules belong in the loaded skill, not memory. Lowers over-saving pressure at the source (the gate is the net; this is the belt).

## [1.4.0] - 2026-06-09

### Added
- Release script (`bin/release.py` + `bin/release_helpers.py`): single command to orchestrate a full plugin release — pre-flight checks (clean tree, semver order, non-empty changelog, upstream configured, not behind remote), version bump, changelog promotion, pathspec commit via `git-memory-commit.py`, push, and post-push verification. Supports `--dry-run` and `--allow-dirty`. Exit codes: 0 = ok, 1 = preflight/execution error, 2 = post-push verify failure.
- `git-memory-commit.py --path` flag: allows callers to commit only specific files by pathspec, used by the release script to stage exactly the three release files without touching the rest of the index.
- `docs/RELEASING.md`: human-readable how-to guide for the release workflow — preconditions, dry-run first, what each step does, flags, version rules, mid-release recovery, and a first-use checklist.
- Documentation coverage: `unmassk-seo` SKILL.md now documents both active hooks (`pre-commit-seo-check.sh` and `validate-schema.py`) with triggers, what they check, and how to interpret their output. `unmassk-ops/ops-observability` routing table corrected to reference `logql-regression-checks.sh` as the LogQL validator. `unmassk-ops/ops-cicd` documents the usage trigger for `azure-step-walker.py` (traversal library, not invoked directly) and `azure-test-regressions.py` (regression suite). `unmassk-media/media-image-edit` now references `.env.example` for `FAL_KEY` configuration.
- Documentation discipline (three-audience rule): every new capability must be documented for humans (`README`/`docs`), the team (roadmap/git-memory), and Claude at load (`SKILL.md`/`CLAUDE.md`) in the same change. Encoded in `unmassk-core`, Flow's Document step, `unmassk-close-session`, and Alexandria's mandate.
- Toolkit discoverability in skills: `unmassk-gitmemory` now documents the `--path` flag, the `git-memory-recall.py` search tool (with ranking internals), the `memo(stack)` category, the release process (`bin/release.py`), and an "Active Hooks" section (merge gate, recall gatekeeper, commit validation, etc.). `unmassk-core` gains a Protocol-skills menu and Gitto Mode B (git ops). `README` gains a Development section and a Protocols row.
- Config for domain plugins: `unmassk-seo/.env.example` (5 MCP credentials), `unmassk-compliance/.mcp.json` + `.env.example` (Better i18n MCP).

### Fixed
- Scope-map path in `unmassk-gitmemory` SKILL.md corrected (`unmassk-crew-bilbo` → `unmassk-toolkit-bilbo`) — was a silent failure whenever Claude looked up the scope map.
- Test isolation bug: `test_migrate_statusline.py` left a stub `git_helpers` (missing `GIT_TIMEOUT`) in `sys.modules` without restoring it, breaking `test_recall.py` in the full suite (58 failures). Now snapshots/restores `sys.modules`. Full suite: 315/315 green.

### Removed
- Dead weight: `!new_skills/` (already integrated in v1.3.0), empty `generated-images/`, and orphaned `.pyc` files under the root `tests/`.

## [1.3.0] - 2026-06-08

### Added
- Recall gatekeeper (`hooks/pre-task-recall.py`): PreToolUse/Task hook that injects relevant project memory (decisions, memos, remembers) into subagent prompts before they execute. Uses `lib/recall.py` for keyword-ranked retrieval. Fail-open: any error lets the spawn through unchanged. Whitelisted to the 8 crew agents (Ultron, Dante, Cerberus, Argus, Moriarty, House, Yoda, Alexandria); Bilbo and Gitto are excluded. 51 tests.
- Build mode (`skills/unmassk-flow/references/linear.md`, `references/test-first.md`): two coding modes selectable per task. Linear for straightforward work; test-first/ATDD for complex features (Dante enters twice — acceptance contract before implementation, exhaustive hardening after). Flow acts as router in Execute Step 4 and delegates to the chosen reference document. Ultron and Dante gain explicit build-mode awareness.
- CLAUDE.md block generator (`lib/managed_blocks.py`): single source of truth for all 5 managed blocks (toolkit, protocols, caveman, communication, build-mode). Idempotent upsert — install, upgrade, and uninstall all import from this module; the blocks can no longer diverge across lifecycle commands. 35 new tests, 0 regressions.
- Protocol skills installed: `close-session`, `grill`, `council`, `project-lifecycle` — all four built, tested, and registered in the CLAUDE.md menu. Previously listed as planned; now live.
- Close-session hook (`hooks/stop-close-session.py`): Stop hook that fires at end of session, prompts the orchestrator to run the close-session skill (decisions dump, versioning if applicable, cleanup). Suppressed when the session had no substantive work. Coexists with the existing `stop-dod-check` hook.
- PRD template saved to `skills/unmassk-project-lifecycle/references/prd-template.md` for use in the START branch of the lifecycle skill.
- Communication block added to CLAUDE.md: rules for how agents report to the orchestrator (results not process, confirm structural changes with exceptions for security/irreversible/unverifiable, one thing at a time).

### Changed
- Flow skill (`skills/unmassk-flow/SKILL.md`) updated: Execute phase now routes to `references/linear.md` or `references/test-first.md` instead of inlining the method. Follows the Standards pattern — one rule, one place.
- Memory calibration tightened (`skills/unmassk-gitmemory/CALIBRATION.md`, `SKILL.md`): three root-cause fixes for over-saving — scope test (project rules belong in project memory, not global remember), stable-done filter (only save what is finished and confirmed, not in-progress reasoning), and timing-not-volume (urgency of a commit is determined by when the signal fires, not how many signals accumulated). `"never commit to main"` rule reframed by repo type: gitflow repos keep the rule; trunk-based repos commit to main by design.
- `unmassk-audit` skill aligned with session decisions: steps 0 and 13 now inherit `repo_type` from `unmassk-gitmemory` (gitflow → branch from dev + merge; trunk → main directly) instead of always assuming `dev`. The 97% coverage gate is documented as a deliberate audit exception that supersedes the pipeline's "coverage does not block merge" override. Scoring/tiers/weights now reference `unmassk-standards` rather than duplicating them.
- Core skill clarified: Ultron = production code only (not skills, agent prompts, or docs). Orchestrator loads standards on-demand; it does not load them at boot.

### Fixed
- Boot hook (`hooks/session-start-boot.py`): removed redundant full-text dump of `unmassk-core`, `unmassk-gitmemory`, and `CALIBRATION.md` from the boot output. These were being injected twice (once by the hook, once by the explicit Skill calls in CLAUDE.md), inflating the session start to ~57 KB that the harness truncated. Explicit Skill calls remain; the duplicate inline dump is gone.
- Flow-stack scaffold path corrected: `scaffold.py` was referenced as `flow-stack-selection` (does not exist) — fixed to `unmassk-flow-stack/scripts/scaffold.py` in two places, unblocking the lifecycle START branch.

## [1.2.0] - 2026-06-05

### Added
- Memory recall engine: `lib/recall.py` + CLI `bin/git-memory-recall.py`. Searches all decision/memo/remember commits by keyword with IDF ranking (rare terms score high, common terms sink), 1.5x bonus for scope matches, alphanumeric tokenization (finds `BM25`, `v2`, `RS256`), deduplication, and full history scan with no commit cap. Robust against context-injection attempts (sanitizes Unicode terminators) and enforces a query length cap.

### Changed
- `git_helpers.run_git` now accepts a `cwd` parameter, making it usable from any working directory.
- `TOMBSTONE_KEYS` and `RECALL_KEYS` constants extracted to `lib/constants.py` — shared between the recall engine and the boot hook (eliminates duplication).

### Removed
- Context-tracking subsystem removed entirely: `bin/context-writer.py`, the statusline wrapper it installed, context percentage warnings in `hooks/user-prompt-memory-check.py`, and all associated install/uninstall/upgrade lifecycle code. The subsystem was designed for the 200k-token context window; with 1M tokens it was noise.

### Fixed
- Upgrade self-heal: if a user's existing Claude settings still pointed the statusline at the deleted `context-writer.py`, the boot hook now detects this and restores the original statusline value (or removes the key), preventing a broken statusline after upgrading from any older version.

### Security
- `shell=True` in `context-writer.py` (issue #48, T1) is eliminated as a side-effect of removing the file entirely.

## [1.1.2] - 2026-03-24

### Fixed
- Boot migration `_migrate_untrack_generated_jsons()`: added `-r` flag to `git rm --cached` for `.unmassk/` directory — was failing silently (exit 128) without it.
- Upgrade tests: replaced stale `"Git Memory Active"` string literals with `"unmassk-toolkit Active"` to match current managed block content.

## [1.1.1] - 2026-03-24

### Fixed
- All 10 agent prompts: replaced routing language (`flag to X`, `route to X`, `@mention`) with scope declarations (`X's scope`). Agents outside chatroom cannot invoke each other — they only report back to the orchestrator.
- Ultron: added missing "The Team" table, removed leftover v1-to-v2 meta sections ("Things Cut From v1", "Summary of Changes").
- Cerberus: completed "The Team" table (was missing House, Bilbo, Alexandria, Gitto).
- Removed chatroom V2 reference files (`chatroom/*-system-prompt-v2.md`) — V2 is now canonical only in plugin source (`unmassk-toolkit/agents/`).

## [1.1.0] - 2026-03-24

### Added
- `compliance-legal-docs` skill: SKILL.md created with 42-reference routing table organized by category (contract review, GDPR/privacy, risk assessment, litigation, French employment law, vendor due diligence, document processing, legal ops)
- V2 system prompts for all 10 agents (alexandria, argus, bilbo, cerberus, dante, gitto, house, moriarty, ultron, yoda): universal format with The Team table, EXHAUSTION PROTOCOL, plain agent names (no @mentions), and no chatroom references — prompts work in any Claude Code context. Each agent self-reviewed their V2 draft and restored load-bearing V1 content that the initial rewrite lost.
- 5-phase agent pipeline: `PIPELINE_GENERIC` and `AGENT_PIPELINE_POSITION` rewritten. Each agent has an explicit chain position entry covering role, when to act, and when to skip.

### Fixed
- Boot hook now skips tombstoned entries when merging glossary remembers and memos into the session summary — `Resolved-Remember:` and `Resolved-Memo:` tombstones are respected on the glossary merge path, not just on the recent-commits path.

## [1.6.0] - 2026-03-16 (unmassk-crew)

### Added
- Cerberus commit-review mode: diff-only review pass with three severity tiers — Issue (blocks merge), Suggestion (recommended, non-blocking), Nitpick (never blocks). Includes a nitpick checklist covering naming conventions, natural language, import type consistency, `as const` usage, magic numbers, stray `console.log`, and similar low-stakes hygiene items. Inspired by CodeRabbit's review model.
- Alexandria merge mode: fast pre-merge documentation gate. Reads only the branch commits vs target branch, updates CHANGELOG under `[Unreleased]`, and checks affected CLAUDE.md files for staleness. No new files created, no memory writes — designed for speed at the merge boundary.
- `pre-merge-gate.py` PreToolUse hook: blocks `git merge` and `git pull` (non-rebase) commands until Cerberus and Alexandria have both passed. Detects `git.exe` on Windows, uses case-insensitive command matching, guards against `eval`/`bash -c`/`sh -c` indirection, and normalizes null bytes. Bypass by adding `# merge-reviewed` comment after both agents pass.

### Changed
- Orchestrator rules in `session-start-crew.py` updated with merge gate awareness: orchestrator must not call merge commands without a prior Cerberus + Alexandria pass, and proactive agent launch guidance is now explicit in the managed block.
- Crew table descriptions updated: Cerberus now documents both enterprise-audit mode and commit-review mode; Alexandria now documents both standard mode and merge mode.

## [1.5.0] - 2026-03-16 (unmassk-crew)

### Added
- `validate-memory-path.py` PreToolUse hook blocks agent-memory writes outside the git root — prevents agents from creating `.claude/agent-memory/` directories in wrong locations after `cd` operations. Fail-closed design with Windows case-insensitive path handling and symlink resolution via `realpath`.
- Orchestrator rules added to the `session-start-crew.py` managed block: orchestrator must not write code (delegate to Ultron), must launch Cerberus+Argus after any new code lands, decides what and who — not how.

### Changed
- Agent boot prompts hardened in 6 agents (cerberus, dante, ultron, alexandria, bilbo, house): `GIT_ROOT` is now resolved once as an absolute path with `|| exit 1` fallback, and the memory section enforces absolute paths anchored to `GIT_ROOT`.
- `hooks.json` updated with PreToolUse matcher for `Write|Edit` pointing to `validate-memory-path.py`.

### Fixed
- `compliance-legal-docs` references: removed broken `/mnt/skills/public/docx/SKILL.md` paths in 3 GDPR files (gdpr-privacy-notice-eu, dpia-sentinel, gdpr-breach-sentinel) — now points to `legal-docx-processing-anthropic`
- `compliance-legal-docs` references: removed broken sub-file references in both assignation-en-référé files (workflow-informations.md, structure-assignation.md, workflow-collecte.md, variantes-cas-particuliers.md, conseils-strategie.md) — workflows now self-contained in the reference files
- `compliance-legal-docs` references: removed broken `assets/` template path in politique-confidentialite-malik-taiar
- `compliance-legal-docs` references: removed `scripts/office/unpack.py`, `scripts/comment.py`, `scripts/accept_changes.py`, `scripts/recalc.py` references — replaced with standard system commands (unzip, LibreOffice, zip)
- `compliance-legal-docs` references: removed `editing.md`, `pptxgenjs.md`, `scripts/thumbnail.py` references from pptx-processing — replaced with inline instructions
- `compliance-legal-docs` references: removed `REFERENCE.md`, `FORMS.md` references from pdf-processing
- `compliance-legal-docs` references: replaced `AskUserQuestion`/`Task` tool calls in tabular-review with plain prose instructions; updated pdf/docx/xlsx "skill" references to reference file names

- `unmassk-ops` plugin: 5 skills covering the full ops domain (iac, containers, cicd, observability, scripting)
- `ops-iac` skill: SKILL.md + 14 references rewritten (Terraform, Ansible, Helm, Pulumi, OpenTofu)
- `ops-containers` skill: SKILL.md + 19 references rewritten (Kubernetes, Docker, Helm, container security)
- `ops-observability` skill: SKILL.md + 9 references rewritten (Prometheus, Grafana, alerting, logging)
- `ops-scripting` skill: SKILL.md + 21 references rewritten (Bash, Makefile)
- `ops-cicd` skill: SKILL.md + 30 references rewritten (GitHub Actions, GitLab CI, Azure Pipelines, Jenkins)

## [3.7.0] - 2026-03-13

### Added
- Boot auto-detects missing `git-memory-scopes.json` and instructs Claude to generate it via Explore agent
- Next cleanup in boot: checks GitHub issue status for pending Next items — closed issues are filtered out, items older than 7 days without an issue ref are marked `[stale]`
- Cross-repo guard prevents false positives when Next items reference issues in other repositories
- GC tombstone support for `Resolved-Next:` trailers — resolved pending items are hidden from future boot output
- Context warnings now use debounce: same-level warnings suppressed for 5 messages (shows `[CTX: N%]` instead), severity escalation (warning to critical) bypasses debounce
- Advisory language for context warnings — informs the agent instead of commanding it
- Test coverage for `context-writer.py` statusline wrapper (7 tests)
- `CO_AUTHOR` is now configurable via `GIT_MEMORY_CO_AUTHOR` environment variable

### Changed
- Scout agent removed — scope scanning now handled by an Explore agent prompt during boot
- Context percentage is now always shown in the UserPromptSubmit hook output (previously only displayed at 60%+ usage)
- Removed `Refs:` trailer key from valid keys — was unused dead code
- Replaced remaining scout terminology in bootstrap script and tests

### Fixed
- Boot and commit script hardening from code review feedback
- Debounce oscillation bug: context bouncing between 59-61% caused stale debounce state to suppress warnings incorrectly — state now resets when context drops back to info level
- `.context-status.json` and `.context-warn-state.json` added to `.gitignore` (were being tracked as noise)

## [3.6.0] - 2026-03-13

### Added
- Boot briefing v2: SessionStart hook produces structured output with zero redundant bash calls
- Automatic conversion of `Next:` trailers to GitHub issues during boot

### Changed
- Version is now centralized in `lib/version.py` as single source of truth, read from `plugin.json`
- CLAUDE.md boot instructions corrected and simplified

## [3.5.1] - 2026-03-13

### Added
- Context warnings now fire mid-session via UserPromptSubmit hook, not just at boot
- Slim hook output after boot — flag file prevents repeated instructions

### Fixed
- Quote all paths in hook output to prevent Windows path mangling
- UserPromptSubmit hook now uses wrapper scripts consistently

## [3.4.0] - 2026-03-12

### Added
- New `git-memory-issues` skill — GitHub issues and milestones as shared team memory
- Safety improvements: confirmation protocol, `--no-ff` merges, pre-merge checklist, immediate back-merge
- Scout agent onboarding integration
- Alexandria documentation agent design

### Fixed
- Belt regex now catches `git -C` and other flags before `log`/`commit` interception
- Narrowed issue skill trigger to avoid false activations on generic words

## [3.3.0] - 2026-03-12

### Added
- `remember()` commit type for explicit long-term memory capture
- Hierarchical scopes with scope-scout agent for automatic scope grouping in glossary
- Mandatory rule: agents always launch in background
- Hardened stop hook — `context()` commit is now mandatory when closing a session

### Changed
- Skill refactored to consolidate all rules (CLAUDE.md managed block minimized)
- Scope-scout agent renamed to "scout"

## [3.2.0] - 2026-03-12

### Added
- Pretty ANSI output for commit and log wrapper scripts
- PreToolUse hook blocks direct `git commit`/`git log` — forces wrapper scripts
- Boot glossary: session start extracts all decisions and memos from full git history

## [3.1.0] - 2026-03-12

### Added
- Frictionless capture: auto-detect decisions, memos, and context from conversation — commit without asking

### Changed
- CLAUDE.md managed block reduced to minimal pointer; all rules moved into the skill file

## [3.0.0] - 2026-03-11

### Changed
- Complete plugin audit: dead code removed, skills merged into single coherent file
- Dashboard archived (superseded by CLI tools)
- Boot now fetches latest git history before building snapshot
- All version references synced across plugin.json, marketplace.json, and code

### Fixed
- Restored `.claude-plugin/` files accidentally deleted during cleanup
- Install script no longer deletes source files when running inside the plugin's own repository

## [2.2.0] - 2026-03-11

### Added
- Context-aware stop hook with statusline wrapper showing session summary
- Gitto memory oracle agent for querying project memory conversationally
- Silent WIP strategy — WIP commits happen without noisy output

### Fixed
- Stale hooks cleaned during zero-copy migration
- Statusline backup hardened against missing files
- Doctor command now detects stale hook configurations

## [2.1.0] - 2026-03-08

### Added
- Automatic context checkpoint commits at natural pause points
- Auto-upgrade of outdated CLAUDE.md managed blocks on session start

### Changed
- Zero-copy install model: plugin runs directly from Claude Code cache, no files copied to project root
- Upgrade script rewritten for zero-copy model with full test coverage

## [2.0.0] - 2026-03-07

### Added
- SessionStart and UserPromptSubmit hooks for automatic memory boot
- Circuit breaker in Stop hook to prevent infinite loops
- Bootstrap detection in UserPromptSubmit hook for first-run guidance
- Incomplete install detection when `lib/` or `bin/` is missing
- Comprehensive type hints with mypy strict mode
- Monorepo detection refined with Rush/Moon support and scope mapping

### Changed
- Extracted shared `lib/` module: constants, git_helpers, parsing, colors (DRY refactor)
- All CLI scripts migrated from ad-hoc argument parsing to argparse
- Migrated 5 test suites to pytest with shared fixtures (old test files removed)
- Plugin aligned with official Claude Code plugin spec
- All code translated to English (docstrings, comments, headers)
- Marketplace.json added for self-hosting distribution
- Skills updated to use local paths instead of `$CLAUDE_PLUGIN_ROOT`

### Fixed
- Security audit round 2: complete manifest, symlink safety, MEMO_CATEGORIES validation, exit codes, imports
- Security audit round 3: XSS in dashboard, atomic writes, shell injection prevention, tombstone normalization
- Hook settings.json format corrected (flatten nesting, string matchers)
- Dashboard date parsing fixed (all dates were null)
- Stop hook now ignores git-memory runtime files

## [1.1.0-gitmemory] - 2026-03-06

### Added
- Static HTML dashboard for visualizing git memory (`git memory dashboard`)
- Lifecycle scripts: doctor, install, repair, uninstall
- Bootstrap scout: detects project stack, monorepos, and commitlint configuration
- Safe upgrade system with backup, diff review, and migrations
- Integration test matrix covering 10 end-to-end scenarios

### Changed
- Restructured project as Claude Code plugin (v2 architecture)

### Fixed
- Security audit: symlink traversal, uninstall orphans, exit code handling, manifest validation

## [1.0.0] - 2026-03-05

### Added
- Core git-memory system: persistent memory via git commit trailers
- Commit types: `context()`, `decision()`, `memo()` with emoji prefixes
- Memory search protocol with `git fetch` + deep grep before asking the user
- Conversational memory detection from natural language triggers
- Contradiction detection for conflicting decisions and memos
- Drift test validating search relevance and dedup under stress (200 commits, 6 scopes)
- CLI for manual memory queries (`git memory search`, `git memory log`)
- Garbage collector for pruning stale memory entries (`git memory gc`)
- Git hooks: pre-validate and post-validate commit trailers, precompact snapshot

### Changed
- Hooks hardened with restored drift test coverage

### Fixed
- Post-hook safety for delimiter collisions and nested prefix handling
- Partial date validation in form components
