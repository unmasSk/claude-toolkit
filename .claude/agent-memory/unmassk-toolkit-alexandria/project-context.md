---
name: project-context
description: Core identity of the unmassk-gitmemory project — what it is, how it works, key conventions
type: project
---

unmassk-toolkit is a Claude Code plugin monorepo providing persistent memory, 10 specialized agents, creative pipeline, enterprise audit, and quality standards. Git is the memory — every commit is resumable across machines and sessions.

- Author: unmasSk
- License: MIT
- Current version: 1.19.4 (source of truth: unmassk-toolkit/.claude-plugin/plugin.json) — verified 2026-07-11, released (1.19.3 and 1.19.4 both shipped since the last check). [Unreleased] holds several passes since, most recently issue #61's fix (2026-07-18, transient-git-failure memory loss — 9 read sites wrapped in bounded retry, suite 1078→1110 passed) on top of issue #72 (2026-07-18, "adelgazamiento" — anti-attacker test cut, suite 1373→1078 passed): see changelog-state.md for the full entry breakdown.
- **Threat model reframe (2026-07-18, issue #72):** confirmed the root CLAUDE.md's "the system against itself, not an external attacker" policy is now actually IMPLEMENTED in the test suite, not just written — all attacker-framed tests retired, integrity-framed coverage kept/restored. Future doc passes should assume "anti-attacker defense" claims (control-byte injection, hardlink/symlink-hostile-actor framing) as coverage are now WRONG unless re-verified; the guarded production functions (`verify_path_within_project()`, `sanitize_trailer_value()`, hard-link rejection) are still live, just no longer tested against a hostile-actor narrative.
- Core language: Python (lib/, bin/) for git-memory; TypeScript/Bun for chatroom
- Distribution: Claude Code plugin marketplace (marketplace.json at repo root)
- Commit convention: conventional commits with emojis (feat, fix, refactor, etc.)
- Non-code commit types: memo, decision, context, wip, remember — these are memory, NOT code changes
- Chatroom is a separate sub-project under chatroom/ with its own CHANGELOG, version track (0.x), and build system (Bun/Elysia)

**Why:** Knowing the project identity prevents misclassifying commits and helps write accurate changelogs.
**How to apply:** Filter out memo/decision/context/wip/remember commits from changelog. Only feat/fix/refactor/perf/chore/ci/test/docs with real code changes go in.
