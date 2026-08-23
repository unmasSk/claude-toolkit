---
name: project-context
description: Core identity of the unmassk-gitmemory project — what it is, how it works, key conventions
type: project
---

unmassk-toolkit is a Claude Code plugin monorepo providing persistent memory, 10 specialized agents, creative pipeline, enterprise audit, and quality standards. Git is the memory — every commit is resumable across machines and sessions.

- Author: unmasSk
- License: MIT
- Current version: **1.38.0** released (source of truth: `unmassk-toolkit/.claude-plugin/plugin.json`) — verified 2026-08-23, commit `ff8c954`. `1.37.1` (2026-08-23) retired the Stop-time test gate entirely (`stop-dod-gate.py`, `stop-dod-declare.py`, `dod_gate_classify.py`, `dod_gate_state.py` + tests all deleted — D-046, it was eating half a session's context in moria-v3) and — **found misattributed to 1.38.0 by Alexandria's 2026-08-23 close pass, corrected** — fixed `gitmem work` failing to commit a deletion already staged with `git rm` (`lib/memory/notes_commit.py`). `1.38.0` (2026-08-23) added Modo automático (`unmassk-core/SKILL.md`), the Spanish-phrase skill router + `[orden]` reminders (`lib/skill_router.py`), `gitmem rule --quote` (owner's literal words required to save a rule), the Argus/Bilbo EXECUTED/READ/UNVERIFIED verification-tag story; changed Dante and Ultron to no longer carry the `Task` tool (can't spawn agents — a prompt-level ban had already failed once); removed restriction R-009 (archived, the gate it described no longer exists). Issue #83 (message-level memory injection) closed 2026-08-09, discarded — see doc-map.md's root CLAUDE.md entry. See changelog-state.md for the full entry breakdown, the misattribution fix, and prior releases' history. The old git-memory system (git-memory-commit.py, trailer validation hooks, etc.) referenced in earlier entries below is fully retired — replaced by the `gitmem` memory-v2 system since 1.26.0.
- **New owner rule (rules.md line 44, 2026-08-23): the CHANGELOG is Alexandria's to write, never the orchestrator's.** Added as a root `CLAUDE.md` "Reglas vivas" bullet this pass (genuine coverage gap — was nowhere in root CLAUDE.md despite governing this very close pass's mandate).
- **Owner's rules file (`.claude/project-memory/rules.md`) is now 42 entries**, not 37 — grew during the 2026-08-23 session (D-050 quote requirement + several more owner corrections, incl. the changelog-ownership rule itself). Root `CLAUDE.md` cites this count twice; both corrected in the 2026-08-23 close pass. Re-check with `grep -c '^\[remember\]' .claude/project-memory/rules.md` before trusting either the doc or this note — it will drift again.
- **Threat model reframe (2026-07-18, issue #72):** confirmed the root CLAUDE.md's "the system against itself, not an external attacker" policy is now actually IMPLEMENTED in the test suite, not just written — all attacker-framed tests retired, integrity-framed coverage kept/restored. Future doc passes should assume "anti-attacker defense" claims (control-byte injection, hardlink/symlink-hostile-actor framing) as coverage are now WRONG unless re-verified; the guarded production functions (`verify_path_within_project()`, `sanitize_trailer_value()`, hard-link rejection) are still live, just no longer tested against a hostile-actor narrative.
- Core language: Python (lib/, bin/) for git-memory; TypeScript/Bun for chatroom
- Distribution: Claude Code plugin marketplace (marketplace.json at repo root)
- Commit convention: conventional commits with emojis (feat, fix, refactor, etc.)
- Non-code commit types: memo, decision, context, wip, remember — these are memory, NOT code changes
- Chatroom is a separate sub-project under chatroom/ with its own CHANGELOG, version track (0.x), and build system (Bun/Elysia)

**Why:** Knowing the project identity prevents misclassifying commits and helps write accurate changelogs.
**How to apply:** Filter out memo/decision/context/wip/remember commits from changelog. Only feat/fix/refactor/perf/chore/ci/test/docs with real code changes go in.
