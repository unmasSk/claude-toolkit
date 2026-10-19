---
name: d124-per-message-checklist-contract-notes
description: #95 part 2b D-124 checklist RED contract in user-prompt-memory-check.py -- concept anchors per line (EN/ES), [memory-check] fallback trap
metadata:
  type: project
---

`unmassk-toolkit/tests/test_d124_per_message_checklist.py` (17 at RED; 16 after Cerberus fix pass merged the duplicate size test).

Label is `[each-message]` (was `[checklist]`, collided with skill-checklist-inject.py). Tests anchor on concept words, never the label.
"or deciding" in Q4 is the owner's own wording (#95: "proponer opciones o tomar una decisión") -- do not strip it on a reviewer's say-so.

**Wording-free pinning:** each D-124 question is pinned by concept-word groups
taken from D-124's own text, EN or ES alternatives, accent/case-normalized,
all groups on ONE output line. Wording stays Ultron's; scattered words don't pass.

**Trap guarded:** the hook prints `[memory-check] No skill match...` only when
`lines` is empty. An always-present checklist fills `lines`, so that fallback
silently dies unless Ultron re-gates it on "no route and no [orden]". Test
`test_should_keep_memory_check_line_when_nothing_matches` pins it.

**Running as Claude Code:** command read from hooks.json UserPromptSubmit,
shell=True, CLAUDE_PLUGIN_ROOT, HOME=tmp, full real payload (session_id,
transcript_path, cwd, permission_mode, hook_event_name, prompt).

Worst-case output before the change: ~1.2k chars; after: ~1.6k (first msg + 4 routes + 4 [orden]).
"Far under the 10k cap" interpreted as <= 5000 -- my reading, not the owner's number.
