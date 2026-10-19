---
name: session-transcript-extractor-contract-notes
description: close-session session_transcript.py RED contract: real .jsonl record shapes (queued_command, slash command), git-dated fixture repo
metadata:
  type: project
---

session_transcript.py (skills/unmassk-close-session/scripts) had no tests until 2026-10-19 (plan fix-close-transcript 1.1, D-143).
Test file: unmassk-toolkit/tests/test_session_transcript.py (CLI only, --transcript + --out always, so ~/.claude and /tmp are never touched).

Real record shapes (Claude Code 2.1.299):
- Mid-turn owner message = TRIO: queue-operation enqueue (content=text), attachment{type:queued_command, prompt, origin{kind:human}, humanTurn:true}, queue-operation remove (reason absorbed_mid_turn). No `user` record exists. Assert "exactly once" so a fix reading the queue-operations too gets caught.
- Same attachment shape carries peer (cross-session-message, agent-message hand-back: origin.kind=peer) and task-notification (origin.kind=task-notification) -- must stay out.
- Slash command = plain `user` record, content str of three tags; the args live in <command-args>; the skill body after it is isMeta.

**How to apply:** date fixture commits with GIT_AUTHOR_DATE+GIT_COMMITTER_DATE (script reads %at). Keep redo-close fixtures (newest [NEXT] after the transcript's first record) separate from plain ones by placing the transcript start after every [NEXT] when testing something else -- otherwise D-143 detection changes the boundary. Assert zero-commit output as `in ([], ["(none)"])`, not the placeholder alone.
