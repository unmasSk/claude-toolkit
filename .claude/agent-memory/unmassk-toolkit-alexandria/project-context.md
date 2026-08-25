---
name: project-context
description: Core identity of the unmassk-toolkit project — what it is, how it works, current version, key conventions
type: project
---

unmassk-toolkit is a Claude Code plugin monorepo providing persistent memory (git-as-memory), 10 specialized agents, creative pipeline, enterprise audit, and quality standards.

- Author: unmasSk. License: MIT.
- **Current version: 1.41.0** — verified `unmassk-toolkit/.claude-plugin/plugin.json:3`, 2026-08-25. Full per-version content lives in `CHANGELOG.md` (root) — that file is the authoritative shipped-history record; this note only tracks the current number so a stale version isn't quoted elsewhere. Re-check `plugin.json` before quoting a version in any doc pass, it moves every release.
- **Owner's rules file (`.claude/project-memory/rules.md`): 49 entries** as of 2026-08-25 (`grep -c '^\[remember\]' .claude/project-memory/rules.md`). Grows every session the owner corrects something — root `CLAUDE.md` deliberately stopped hardcoding this count (commit `2506c44`, 2026-08-24) precisely because it drifted every pass; don't reintroduce a hardcoded number there. Re-run the grep before trusting this line, it will already be stale by the time you read it.
- **Threat model: "the system against itself," no external attacker** (root `CLAUDE.md` §"What security and tests are for"). Confirmed actually implemented in the test suite, not just written (issue #72, 2026-07-18): all attacker-framed tests retired, integrity-framed coverage kept. `unmassk-standards` and `unmassk-audit` are both calibrated to this model (verified 2026-07-29 / 2026-08-05 respectively — no OWASP/React/TypeScript/Zod/PostgreSQL anywhere in either).
- **Issue #83 (message-level memory injection) closed 2026-08-09, discarded** — the owner declined to reinstate it because the real gap (a subordinate agent working blind on memory) was already closed a different way, in the search command (D-041).
- Core language: Python (`lib/`, `bin/`) for the memory system; TypeScript/Bun for `chatroom/` (separate sub-project, own CHANGELOG/version track/build).
- Distribution: Claude Code plugin marketplace (`marketplace.json` at repo root).
- Commit convention: conventional commits with emojis (feat/fix/refactor/etc). Non-code commit types — `memo`, `decision`, `context`, `wip`, `remember` — are memory, not code changes: **filter these out of any changelog pass**, only feat/fix/refactor/perf/chore/ci/test/docs with real code changes go in.
- **The CHANGELOG is Alexandria's to write, never the orchestrator's** (`.claude/project-memory/rules.md`, added 2026-08-23) — a root `CLAUDE.md` "Reglas vivas" bullet now states this explicitly.
- The old pre-`gitmem` memory system (git-memory-commit.py, trailer-validation hooks, `docs/memoria-v2/*`, `DEUDA.md`) is fully retired, replaced by the 9-subcommand `gitmem` system since v1.26.0, and physically moved to `docs/deprecated/` (frozen history, explicitly "no se mantiene" per its own `LEEME.md`) once the branch merged. Never treat those files as describing present behavior — see doc-map.md's "Retired" section for what NOT to re-verify.

**Why:** Knowing the project identity prevents misclassifying commits and helps write accurate changelogs.
**How to apply:** Before writing a CHANGELOG entry or quoting a version/rule-count number anywhere, re-run the verification command above — don't trust this file's numbers past the date on their evidence.
