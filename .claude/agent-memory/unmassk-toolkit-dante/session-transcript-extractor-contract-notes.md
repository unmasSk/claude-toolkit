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

Round-trip (1.3): tests/test_session_transcript_round_trip.py + tests/fixtures/session_transcript_real_records.jsonl (10 verbatim records). Expected values read from producer fields: user content / <command-args> group / attachment.prompt (origin.kind human); foreign = origin.body + <task-id>/<summary>. A guard test pins the fixture's record kinds so trimming it can't silently weaken the rest. Session 6f693e4e has NO slash command with args -- the only one found was in c62e54c4 line 4951. Peers also arrive as isMeta `user` records ("Another Claude session sent a message:") -- dropped by isMeta.

**How to apply:** date fixture commits with GIT_AUTHOR_DATE+GIT_COMMITTER_DATE (script reads %at). Keep redo-close fixtures (newest [NEXT] after the transcript's first record) separate from plain ones by placing the transcript start after every [NEXT] when testing something else -- otherwise D-143 detection changes the boundary. Assert zero-commit output as `in ([], ["(none)"])`, not the placeholder alone.

**Public repo: never copy real .jsonl records verbatim.** The 1.3 fixture first held the owner's private messages, a peer's client-project text, real session/task/tool ids and local paths; it was anonymised after the fact. Technique: raw-text replace of each human text (so duplicates across content/prompt/rendered/queue-operation stay identical), regex-map every 8-4-4-4-12 uuid to a sequential fake one (keeps source_uuid==commandUuid links), then a recursive keys+types+order diff old vs new. The script reads no sessionId/cwd, so ids are free to change. Keep one accented owner text for encoding.

**List-shaped `attachment.prompt`** (3/190 real human queued_commands): 2.1.299 = [text "<system-reminder>Linked sessions now...</system-reminder>", text owner], rendered = [{content:[text block]}], queue-op content = blocks joined "\n"; 2.1.287 = [image{source:{type,media_type,data}}, text], no rendered, extra top-level session_id. Before quoting a test literal, grep ~/.claude/projects for it: two "invented" literals (OWNER_MID_TURN, CLOSE_ARGS) were real owner sentences.

**Producer↔consumer header test:** the close prompt STOPs on any `warning:` line; read that prefix from references/close-agent-prompt.md by regex instead of hardcoding it, so a prompt edit and a script edit can't drift apart unnoticed.
