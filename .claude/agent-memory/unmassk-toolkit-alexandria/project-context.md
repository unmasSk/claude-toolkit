---
name: project-context
description: Core identity of the unmassk-gitmemory project — what it is, how it works, key conventions
type: project
---

unmassk-toolkit is a Claude Code plugin monorepo providing persistent memory, 10 specialized agents, creative pipeline, enterprise audit, and quality standards. Git is the memory — every commit is resumable across machines and sessions.

- Author: unmasSk
- License: MIT
- Current version: 1.29.1 released (source of truth: unmassk-toolkit/.claude-plugin/plugin.json) — verified 2026-08-06. `[Unreleased]` holds the 1.29.2-bound work in progress: customs.py rescue-command robustness (approved before reading memory files, corrupt-file rejection with repair instructions, shlex-fallback rescue-flag recovery), stop-dod-gate.py corrupt-config stderr warning, doctor/zones-list absent-vs-empty distinction + shape validation, installer decoupled from `lib/memory` (seeds via `gitmem rezones`), CI hardening. See changelog-state.md for the full entry breakdown and prior releases' history. The old git-memory system (git-memory-commit.py, trailer validation hooks, etc.) referenced in earlier entries below is fully retired — replaced by the `gitmem` memory-v2 system since 1.26.0.
- **Threat model reframe (2026-07-18, issue #72):** confirmed the root CLAUDE.md's "the system against itself, not an external attacker" policy is now actually IMPLEMENTED in the test suite, not just written — all attacker-framed tests retired, integrity-framed coverage kept/restored. Future doc passes should assume "anti-attacker defense" claims (control-byte injection, hardlink/symlink-hostile-actor framing) as coverage are now WRONG unless re-verified; the guarded production functions (`verify_path_within_project()`, `sanitize_trailer_value()`, hard-link rejection) are still live, just no longer tested against a hostile-actor narrative.
- Core language: Python (lib/, bin/) for git-memory; TypeScript/Bun for chatroom
- Distribution: Claude Code plugin marketplace (marketplace.json at repo root)
- Commit convention: conventional commits with emojis (feat, fix, refactor, etc.)
- Non-code commit types: memo, decision, context, wip, remember — these are memory, NOT code changes
- Chatroom is a separate sub-project under chatroom/ with its own CHANGELOG, version track (0.x), and build system (Bun/Elysia)

**Why:** Knowing the project identity prevents misclassifying commits and helps write accurate changelogs.
**How to apply:** Filter out memo/decision/context/wip/remember commits from changelog. Only feat/fix/refactor/perf/chore/ci/test/docs with real code changes go in.
