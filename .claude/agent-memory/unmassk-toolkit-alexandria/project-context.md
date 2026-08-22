---
name: project-context
description: Core identity of the unmassk-gitmemory project — what it is, how it works, key conventions
type: project
---

unmassk-toolkit is a Claude Code plugin monorepo providing persistent memory, 10 specialized agents, creative pipeline, enterprise audit, and quality standards. Git is the memory — every commit is resumable across machines and sessions.

- Author: unmasSk
- License: MIT
- Current version: **1.37.0** released (source of truth: `unmassk-toolkit/.claude-plugin/plugin.json`) — verified 2026-08-22, commit `65c57f8`. `1.36.0` (2026-08-21) made `stop-dod-gate` classify a red before blocking (test-first empty-suite/never-written-module allowed with a once-per-session warning). `1.37.0` (2026-08-22) opened `gitmem note --issue` from M-only to all seven types (D-043→D-045), added `unmassk-memory/references/issues.md`. **Shipped same day, in the tree at 1.37.0, but NOT in the CHANGELOG entry for it** (flagged to the user, not fixed — CHANGELOG belongs to `merge` mode): `stop-dod-gate`'s working-tree fingerprint cache (skips re-running `test_command` when nothing changed — closes the 704-orphaned-process incident from `moria-v3`, restriction R-009) and `bin/stop-dod-declare.py` (`declare`/`clear`/`status`, lets the orchestrator shield a known-in-flight test-first red from the Stop gate) — documented into `unmassk-flow/SKILL.md` for the first time in the 2026-08-22 close pass, since it had zero mention anywhere before that. Issue #83 (message-level memory injection) closed 2026-08-09, discarded — see doc-map.md's root CLAUDE.md entry. See changelog-state.md for the full entry breakdown and prior releases' history. The old git-memory system (git-memory-commit.py, trailer validation hooks, etc.) referenced in earlier entries below is fully retired — replaced by the `gitmem` memory-v2 system since 1.26.0.
- **Owner's rules file (`.claude/project-memory/rules.md`) is now 37 entries**, not 34 — grew during the 2026-08-22 session (new rule: no explaining with analogies/metaphors). Root `CLAUDE.md` cites this count twice; both corrected in the 2026-08-22 close pass. Re-check with `grep -c '^\[remember\]' .claude/project-memory/rules.md` before trusting either the doc or this note — it will drift again.
- **Threat model reframe (2026-07-18, issue #72):** confirmed the root CLAUDE.md's "the system against itself, not an external attacker" policy is now actually IMPLEMENTED in the test suite, not just written — all attacker-framed tests retired, integrity-framed coverage kept/restored. Future doc passes should assume "anti-attacker defense" claims (control-byte injection, hardlink/symlink-hostile-actor framing) as coverage are now WRONG unless re-verified; the guarded production functions (`verify_path_within_project()`, `sanitize_trailer_value()`, hard-link rejection) are still live, just no longer tested against a hostile-actor narrative.
- Core language: Python (lib/, bin/) for git-memory; TypeScript/Bun for chatroom
- Distribution: Claude Code plugin marketplace (marketplace.json at repo root)
- Commit convention: conventional commits with emojis (feat, fix, refactor, etc.)
- Non-code commit types: memo, decision, context, wip, remember — these are memory, NOT code changes
- Chatroom is a separate sub-project under chatroom/ with its own CHANGELOG, version track (0.x), and build system (Bun/Elysia)

**Why:** Knowing the project identity prevents misclassifying commits and helps write accurate changelogs.
**How to apply:** Filter out memo/decision/context/wip/remember commits from changelog. Only feat/fix/refactor/perf/chore/ci/test/docs with real code changes go in.
