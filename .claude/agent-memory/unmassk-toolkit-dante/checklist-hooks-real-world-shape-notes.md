---
name: checklist-hooks-real-world-shape-notes
description: Real Claude Code shapes the checklist hooks must handle -- prefixed skill names, wiped task boards, cwd inside a subfolder
metadata:
  type: project
---

Shapes verified on the owner's machine (Moriarty drill, 2026-10-18), which synthetic fixtures had missed:
- `tool_input.skill` arrives as `unmassk-toolkit:unmassk-flow` (plugin prefix), almost never bare.
- ~5 s after the last task completes, Claude Code deletes every `N.json`; the board dir keeps only `.lock` (empty) and `.highwatermark` (task count, e.g. "19", no newline).
- Hook payload `cwd` can be a subfolder; registry must resolve to git top-level.

**Why:** all previous checklist tests used bare names, live task files and cwd == root, so the gate was green in tests and dead in real use.
**How to apply:** any new checklist/board test needs at least one case with the prefixed name, a wiped board, and a git repo + `src/` cwd. A test whose silence could also come from "nothing registered" must first assert the registry exists. Contract file: tests/hooks/test_checklist_drill_fixes.py.

**Stop `background_tasks` (D-141, 2026-10-19).** Official docs (curl `code.claude.com/docs/en/hooks.md`, section "Stop input"; WebFetch truncates at 100k, curl+grep gets it all): Stop/SubagentStop stdin carries `background_tasks` (every entry is in-flight: id/type/status/description + per-type command/agent_type/name/server/tool) and `session_crons`; both always present, empty when nothing runs. Contract file: tests/hooks/test_checklist_gate_background_tasks.py. Pin "empty array = today's gate" so a fix keyed on key-presence fails, and crons-only must still block.

**D-142 replaces D-141 (2026-10-19).** Only `subagent`/`workflow` entries silence the gate (uncounted, one stderr line naming the wait); `shell`/`monitor` alone block and count (a dev server or `tail -f` lives to the real close); non-list `background_tasks` = today's gate. Pin a mixed shell+monitor+subagent case so an "all entries must be agents" or "first entry only" filter fails.
