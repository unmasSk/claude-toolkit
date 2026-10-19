"""Contract tests for the close-session extractor (session_transcript.py).

Plan docs/plan/fix-close-transcript.md, step 1.1; decision D-143.
Driven through the script's command line, on .jsonl fixtures built from the
record shapes Claude Code really writes, against a disposable git repo.
"""

import json
import os
import re
import sys
import uuid

import pytest

from conftest import SOURCE_ROOT, git_cmd, run_cmd

SCRIPT = os.path.join(
    SOURCE_ROOT, "skills", "unmassk-close-session", "scripts", "session_transcript.py"
)
CLOSE_PROMPT = os.path.join(
    SOURCE_ROOT, "skills", "unmassk-close-session", "references", "close-agent-prompt.md"
)
SESSION_ID = "6f693e4e-0000-4000-8000-000000000001"


def close_prompt_stop_prefix():
    """The header prefix the close agent's prompt says to STOP on."""
    with open(CLOSE_PROMPT, encoding="utf-8") as handle:
        found = re.search(r"carries a `([^`]+)` line[^.]*STOP", handle.read(), re.DOTALL)
    assert found, f"no STOP prefix found in {CLOSE_PROMPT}"
    return found.group(1)
DAY = "2026-10-19"


# ── transcript records (shapes taken from a real 2.1.299 transcript) ────


def _base(record_type, ts):
    return {
        "parentUuid": str(uuid.uuid4()),
        "isSidechain": False,
        "type": record_type,
        "uuid": str(uuid.uuid4()),
        "timestamp": ts,
        "userType": "external",
        "entrypoint": "claude-desktop",
        "cwd": "/somewhere/project",
        "sessionId": SESSION_ID,
        "version": "2.1.299",
        "gitBranch": "main",
    }


def human(text, ts):
    record = _base("user", ts)
    record.update(
        {
            "promptId": str(uuid.uuid4()),
            "message": {"role": "user", "content": text},
            "permissionMode": "auto",
            "origin": {"kind": "human"},
            "promptSource": "sdk",
            "turnOrigin": "human",
        }
    )
    return record


def assistant(text, ts):
    record = _base("assistant", ts)
    record["message"] = {
        "model": "claude-opus-5-5",
        "id": "msg_" + uuid.uuid4().hex[:20],
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
    }
    return record


def queue_op(operation, ts, content=None, reason=None):
    record = {"type": "queue-operation", "operation": operation,
              "timestamp": ts, "sessionId": SESSION_ID}
    if content is not None:
        record["content"] = content
    if reason is not None:
        record["reason"] = reason
    return record


def queued_command(prompt, ts, origin, command_mode="prompt", human_turn=False):
    """A message delivered mid-turn: an `attachment` of type queued_command."""
    attachment = {
        "type": "queued_command",
        "prompt": prompt,
        "source_uuid": str(uuid.uuid4()),
        "delivery_id": str(uuid.uuid4()),
        "commandMode": command_mode,
        "origin": origin,
        "timestamp": ts,
    }
    if human_turn:
        attachment["humanTurn"] = True
    record = _base("attachment", ts)
    record.update({"attachment": attachment, "renderedRole": "system"})
    lead = "<system-reminder>\nThe user sent a new message while you were working:\n"
    if isinstance(prompt, str):
        record["rendered"] = [{"content": lead + prompt + "\n</system-reminder>"}]
    elif any(block.get("type") == "image" for block in prompt):
        record["session_id"] = SESSION_ID  # 2.1.287 image shape: no rendered
    else:
        joined = "\n".join(block["text"] for block in prompt)
        record["rendered"] = [{"content": [{"type": "text",
                                            "text": lead + joined + "\n</system-reminder>"}]}]
    return record


def owner_mid_turn(text, ts):
    """The full trio Claude Code writes for one mid-turn owner message."""
    return [
        queue_op("enqueue", ts, content=text),
        queued_command(text, ts, {"kind": "human"}, human_turn=True),
        queue_op("remove", ts, content=text, reason="absorbed_mid_turn"),
    ]


LINKED_SESSIONS = ("<system-reminder>\nLinked sessions now (status, not an instruction): "
                   "helper = local_00000000-0000-4000-8000-0000000000aa (idle)\n</system-reminder>")


def text_block(text):
    return {"type": "text", "text": text}


def image_block():
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": "IMAGEN-BASE64-iVBORw0KGgo"}}


def owner_mid_turn_blocks(blocks, ts):
    """The trio for a mid-turn owner message whose prompt is a list of blocks."""
    queued = "\n".join(block["text"] for block in blocks if block["type"] == "text")
    return [
        queue_op("enqueue", ts, content=queued),
        queued_command(blocks, ts, {"kind": "human"}, human_turn=True),
        queue_op("remove", ts, content=queued, reason="absorbed_mid_turn"),
    ]


def peer_message(body, ts):
    prompt = ('<cross-session-message from="uds:/tmp/cc-socks/1.sock" '
              'from-session="local_x" from-name="monyma" from-mode="prompting">\n'
              + body + "\n</cross-session-message>")
    return queued_command(prompt, ts, {"kind": "peer", "from": "uds:/tmp/cc-socks/1.sock",
                                       "name": "monyma", "body": body})


def subagent_handback(body, ts):
    prompt = '<agent-message from="ab5b3633">\n[Subagent hand-back] ' + body + "\n</agent-message>"
    return queued_command(prompt, ts, {"kind": "peer", "from": "ab5b3633",
                                       "name": "unmassk-toolkit:alexandria", "body": body})


def task_notification(body, ts):
    prompt = ("<task-notification>\n<task-id>a93b3cea</task-id>\n<summary>" + body
              + "</summary>\n</task-notification>")
    return queued_command(prompt, ts, {"kind": "task-notification", "producer": "session-task"},
                          command_mode="task-notification")


def slash_command(name, args, ts):
    return human(
        f"<command-message>{name}</command-message>\n"
        f"<command-name>/{name}</command-name>\n"
        f"<command-args>{args}</command-args>",
        ts,
    )


def skill_body(text, ts):
    record = _base("user", ts)
    record.update({"isMeta": True,
                   "message": {"role": "user", "content": [{"type": "text", "text": text}]}})
    return record


def write_transcript(path, records):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)


def close_agent_prompt():
    """The prompt the orchestrator hands the close agent, read from the skill."""
    with open(CLOSE_PROMPT, encoding="utf-8") as handle:
        found = re.search(r"## THE PROMPT\s*```\n(.*?)\n```", handle.read(), re.DOTALL)
    assert found, f"no prompt block in {CLOSE_PROMPT}"
    return found.group(1)


def held_close(transcript_path, session_id, sha, subject, launched, done):
    """What a session that wrote a close holds, as Claude Code lays it out: the
    close agent launched from the top-level transcript, and that agent's own
    sidechain file (<session>/subagents/agent-*.jsonl) running `gitmem next`.
    Writes the sidechain file; returns the top-level records."""
    agent_id = uuid.uuid4().hex[:17]
    tool_id = "toolu_" + uuid.uuid4().hex[:24]
    prompt = close_agent_prompt()
    launch = assistant("", launched)
    launch["sessionId"] = session_id
    launch["message"]["content"] = [{"type": "tool_use", "id": tool_id, "name": "Agent",
                                     "input": {"description": "Write the session close",
                                               "subagent_type": "general-purpose",
                                               "prompt": prompt}}]
    result = _base("user", done)
    result.update({"sessionId": session_id, "sourceToolAssistantUUID": launch["uuid"],
                   "message": {"role": "user", "content": [
                       {"type": "tool_result", "tool_use_id": tool_id,
                        "content": [{"type": "text", "text": "Close written."}]}]},
                   "toolUseResult": {"status": "completed", "prompt": prompt,
                                     "agentId": agent_id, "agentType": "general-purpose",
                                     "content": [{"type": "text", "text": "Close written."}]}})

    headline = subject.split(" ", 2)[2]
    bash_id = "toolu_" + uuid.uuid4().hex[:24]
    side = [_base("user", launched), _base("assistant", done), _base("user", done)]
    for record in side:
        record.update({"isSidechain": True, "agentId": agent_id, "sessionId": session_id})
    side[0]["message"] = {"role": "user", "content": prompt}
    side[1]["message"] = {"role": "assistant", "type": "message", "content": [
        {"type": "tool_use", "id": bash_id, "name": "Bash",
         "input": {"command": f'python3 "/somewhere/bin/gitmem" next "{headline}"',
                   "description": "Write the close"}}]}
    side[2]["message"] = {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": bash_id,
         "content": f"EXIT=0\n{sha[:8]} {subject}"}]}
    folder = os.path.join(os.path.dirname(str(transcript_path)), session_id, "subagents")
    write_transcript(os.path.join(folder, f"agent-{agent_id}.jsonl"), side)
    return [launch, result]


def ts(hhmmss):
    return f"{DAY}T{hhmmss}.000Z"


# ── disposable git repo ─────────────────────────────────────────────────


def make_repo(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git_cmd(["init", "-q", "-b", "main"], str(repo))
    return str(repo)


def commit(repo, subject, hhmmss):
    stamp = f"{DAY}T{hhmmss}Z"
    rc, _, err = git_cmd(["commit", "-q", "--allow-empty", "-m", subject], repo,
                         env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
    assert rc == 0, err
    rc, sha, err = git_cmd(["rev-parse", "HEAD"], repo)
    assert rc == 0, err
    return sha.strip()


# ── running the script the way the close agent runs it ──────────────────


class Run:
    def __init__(self, rc, stdout, stderr, text):
        self.rc, self.stdout, self.stderr, self.text = rc, stdout, stderr, text
        head, _, rest = text.partition("# COMMITS SINCE THE BOUNDARY")
        commits_part, _, conversation = rest.partition("# CONVERSATION")
        self.header = head
        self.commits = [line for line in commits_part.split("\n")[1:]
                        if line and not line.startswith("#")]
        self.conversation = conversation.split("\n", 1)[1] if "\n" in conversation else ""
        self.turns = [chunk for chunk in re.split(r"^=== ", self.conversation, flags=re.M)
                      if chunk.strip()]

    def user_turns_with(self, phrase):
        return [t for t in self.turns if t.startswith("user ") and phrase in t]

    def anywhere_in_conversation(self, phrase):
        return phrase in self.conversation

    def header_lines(self, prefix):
        return [line for line in self.header.split("\n") if line.startswith(prefix)]

    def commit_notes(self):
        return [line for line in self.header_lines("note:") if "commit" in line.lower()]

    def stop_lines(self):
        """Header lines the close agent stops on (prefix read from its prompt)."""
        return self.header_lines(close_prompt_stop_prefix())


def run(tmp_path, repo, transcript, *extra):
    out = str(tmp_path / "close-input.txt")
    rc, stdout, stderr = run_cmd(
        [sys.executable, SCRIPT, "--repo", repo, "--transcript", transcript, "--out", out,
         *extra],
        cwd=repo,
    )
    assert rc == 0, f"script failed rc={rc}: {stderr}"
    with open(out, encoding="utf-8") as handle:
        return Run(rc, stdout, stderr, handle.read())


@pytest.fixture
def closed_repo(tmp_path):
    """A repo whose last close happened before the transcript starts."""
    repo = make_repo(tmp_path)
    commit(repo, "[DECISION][x] 🧭 earlier work", "06:00:00")
    commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    return repo


# ── (a) owner messages typed mid-turn ───────────────────────────────────

OWNER_MID_TURN = "Recuerda cerrar la ventana del garaje antes de cenar."


def test_should_output_owner_message_when_typed_mid_turn(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")), assistant("Hola Bex.", ts("08:00:05"))]
    records += owner_mid_turn(OWNER_MID_TURN, ts("08:51:38"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert len(result.user_turns_with(OWNER_MID_TURN)) == 1, result.conversation


def test_should_output_mid_turn_message_once_when_queue_operations_repeat_it(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00"))] + owner_mid_turn(OWNER_MID_TURN, ts("08:51:38"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert result.conversation.count(OWNER_MID_TURN) == 1, result.conversation


def test_should_place_mid_turn_message_between_the_turns_around_it(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")),
               assistant("ANTES del mensaje", ts("08:51:00"))]
    records += owner_mid_turn(OWNER_MID_TURN, ts("08:51:38"))
    records += [assistant("DESPUES del mensaje", ts("08:52:00"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)
    conversation = result.conversation

    assert 0 <= conversation.find("ANTES del mensaje") < conversation.find(OWNER_MID_TURN) \
        < conversation.find("DESPUES del mensaje"), conversation


def test_should_bound_mid_turn_messages_by_since(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn("mensaje viejo a mitad de turno", ts("08:10:00"))
    records += owner_mid_turn("mensaje nuevo a mitad de turno", ts("08:40:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript, "--since", f"{DAY}T08:30:00")

    assert (result.anywhere_in_conversation("mensaje viejo a mitad de turno"),
            len(result.user_turns_with("mensaje nuevo a mitad de turno"))) == (False, 1)


@pytest.mark.parametrize("make_record", [peer_message, subagent_handback, task_notification],
                         ids=["peer-session", "subagent-handback", "task-notification"])
def test_should_drop_queued_command_when_origin_is_not_the_owner(tmp_path, closed_repo,
                                                                 make_record):
    records = [human("hola", ts("08:00:00")),
               make_record("TEXTO-QUE-NO-ES-DEL-DUENO", ts("08:20:00"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert not result.anywhere_in_conversation("TEXTO-QUE-NO-ES-DEL-DUENO"), result.conversation


# ── (b) the arguments of a slash command ────────────────────────────────

CLOSE_ARGS = "y apunta que el martes toca pintar la valla"


def test_should_output_command_args_when_owner_types_a_slash_command(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")),
               slash_command("unmassk-toolkit:unmassk-close-session", CLOSE_ARGS, ts("08:50:47"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert len(result.user_turns_with(CLOSE_ARGS)) == 1, result.conversation


def test_should_drop_skill_body_when_it_follows_the_slash_command(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00")),
               slash_command("unmassk-toolkit:unmassk-close-session", CLOSE_ARGS, ts("08:50:47")),
               skill_body("CUERPO-DE-LA-SKILL Base directory for this skill", ts("08:50:47"))]
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert not result.anywhere_in_conversation("CUERPO-DE-LA-SKILL"), result.conversation


# ── (c) --since bounds the commits as well as the conversation ──────────


@pytest.fixture
def two_close_repo(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "A before everything", "08:00:00")
    commit(repo, "[NEXT] 🔜 close one", "09:00:00")
    commit(repo, "C between the closes", "10:00:00")
    commit(repo, "[NEXT] 🔜 close two", "11:00:00")
    commit(repo, "F just after close two", "11:15:00")
    commit(repo, "E latest", "12:00:00")
    return repo


def _late_transcript(tmp_path):
    return write_transcript(tmp_path / "s.jsonl", [human("hola", ts("12:30:00")),
                                                   assistant("hola", ts("12:30:05"))])


def test_should_include_commits_after_since_when_since_predates_last_close(tmp_path,
                                                                           two_close_repo):
    result = run(tmp_path, two_close_repo, _late_transcript(tmp_path),
                 "--since", f"{DAY}T09:30:00")

    assert result.commits == ["C between the closes", "[NEXT] 🔜 close two",
                              "F just after close two", "E latest"], result.text


def test_should_exclude_commits_before_since_when_since_follows_last_close(tmp_path,
                                                                           two_close_repo):
    result = run(tmp_path, two_close_repo, _late_transcript(tmp_path),
                 "--since", f"{DAY}T11:30:00")

    assert result.commits == ["E latest"], result.text


# ── (d) zero commits in the window is said, without stopping the close ─


def test_should_note_without_a_stop_line_when_no_commit_follows_the_last_close(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "work", "09:00:00")
    commit(repo, "[NEXT] 🔜 previous session close", "10:00:00")
    transcript = write_transcript(tmp_path / "s.jsonl", [human("hola", ts("10:30:00")),
                                                         assistant("hola", ts("10:30:05"))])

    result = run(tmp_path, repo, transcript)

    assert (result.commits in ([], ["(none)"]), len(result.commit_notes()),
            result.stop_lines()) == (True, 1, []), result.text


def test_should_note_without_a_stop_line_when_since_is_after_every_commit(tmp_path,
                                                                         two_close_repo):
    result = run(tmp_path, two_close_repo, _late_transcript(tmp_path),
                 "--since", f"{DAY}T12:10:00")

    assert (result.commits in ([], ["(none)"]), len(result.commit_notes()),
            result.stop_lines()) == (True, 1, []), result.text


def test_should_not_note_about_commits_when_the_window_has_some(tmp_path, closed_repo):
    commit(closed_repo, "work after the close", "08:30:00")
    transcript = write_transcript(tmp_path / "s.jsonl", [human("hola", ts("08:00:00"))])

    result = run(tmp_path, closed_repo, transcript)

    assert (result.commits, result.commit_notes(), result.stop_lines()) == \
        (["work after the close"], [], []), result.text


# ── (e) a second close in the same session covers the whole session ─────


@pytest.fixture
def redo(tmp_path):
    """Previous session closed at 07:00; this session (from 08:00) closed at 09:00
    and is now being closed again."""
    repo = make_repo(tmp_path)
    commit(repo, "old work", "06:00:00")
    previous = commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    commit(repo, "work before the first close", "08:30:00")
    first_subject = "[NEXT] 🔜 this session, first close"
    first = commit(repo, first_subject, "09:00:00")
    commit(repo, "work after the first close", "09:10:00")
    path = tmp_path / f"{SESSION_ID}.jsonl"
    records = [queue_op("enqueue", ts("08:00:00"), content="hola"),
               human("ANTES-DEL-PRIMER-CIERRE", ts("08:00:01")),
               assistant("respuesta temprana", ts("08:00:05"))]
    records += held_close(path, SESSION_ID, first, first_subject, ts("08:58:00"), ts("09:00:01"))
    records += [human("DESPUES-DEL-PRIMER-CIERRE", ts("09:05:00"))]
    transcript = write_transcript(path, records)
    return repo, transcript, previous, first


SECOND_CLOSE = "[NEXT] 🔜 this session, second close"


def hold_second_close(transcript, sha):
    """This session closes again: its transcript gains the second close's records."""
    with open(transcript, "a", encoding="utf-8") as handle:
        for record in held_close(transcript, SESSION_ID, sha, SECOND_CLOSE,
                                 ts("09:18:00"), ts("09:20:01")):
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def test_should_return_whole_session_conversation_when_closing_twice(tmp_path, redo):
    repo, transcript, _, _ = redo

    result = run(tmp_path, repo, transcript)

    assert (len(result.user_turns_with("ANTES-DEL-PRIMER-CIERRE")),
            len(result.user_turns_with("DESPUES-DEL-PRIMER-CIERRE"))) == (1, 1), result.text


def test_should_return_whole_session_commits_when_closing_twice(tmp_path, redo):
    repo, transcript, _, _ = redo

    result = run(tmp_path, repo, transcript)

    assert result.commits == ["work before the first close",
                              "[NEXT] 🔜 this session, first close",
                              "work after the first close"], result.text


def test_should_name_previous_session_close_as_boundary_when_closing_twice(tmp_path, redo):
    repo, transcript, previous, first = redo

    result = run(tmp_path, repo, transcript)
    boundary = [line for line in result.header.split("\n") if line.startswith("boundary:")]

    assert (len(boundary), previous[:12] in boundary[0], first[:12] in boundary[0]) == \
        (1, True, False), result.header


def test_should_skip_every_earlier_close_of_this_session_when_closing_a_third_time(tmp_path,
                                                                                    redo):
    repo, transcript, previous, _ = redo
    hold_second_close(transcript, commit(repo, SECOND_CLOSE, "09:20:00"))

    result = run(tmp_path, repo, transcript)

    assert (previous[:12] in result.header,
            len(result.user_turns_with("ANTES-DEL-PRIMER-CIERRE")),
            result.commits[0]) == (True, 1, "work before the first close"), result.text


def test_should_keep_last_close_as_boundary_when_it_predates_the_transcript(tmp_path,
                                                                            closed_repo):
    last = commit(closed_repo, "[NEXT] 🔜 the close right before this session", "07:30:00")
    commit(closed_repo, "work in this session", "08:30:00")
    transcript = write_transcript(tmp_path / "s.jsonl", [
        queue_op("enqueue", ts("08:00:00"), content="hola"),
        human("hola", ts("08:00:01"))])

    result = run(tmp_path, closed_repo, transcript)

    assert (last[:12] in result.header, result.commits) == \
        (True, ["work in this session"]), result.text


def test_should_name_the_skipped_close_when_the_newest_close_is_this_sessions_own(tmp_path,
                                                                                 redo):
    repo, transcript, _, first = redo

    result = run(tmp_path, repo, transcript)
    naming = [line for line in result.header.split("\n")
              if first[:12] in line and not line.startswith("boundary:")]

    assert len(naming) == 1, result.header


def test_should_name_the_newest_skipped_close_when_closing_a_third_time(tmp_path, redo):
    repo, transcript, _, _ = redo
    second = commit(repo, SECOND_CLOSE, "09:20:00")
    hold_second_close(transcript, second)

    result = run(tmp_path, repo, transcript)
    naming = [line for line in result.header.split("\n")
              if second[:12] in line and not line.startswith("boundary:")]

    assert len(naming) == 1, result.header


def test_should_not_say_none_found_when_the_only_close_was_skipped(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "work before the first close", "08:30:00")
    first_subject = "[NEXT] 🔜 this session, first close"
    first = commit(repo, first_subject, "09:00:00")
    path = tmp_path / f"{SESSION_ID}.jsonl"
    transcript = write_transcript(path, [human("hola", ts("08:00:00"))]
                                  + held_close(path, SESSION_ID, first, first_subject,
                                               ts("08:58:00"), ts("09:00:01"))
                                  + [human("otra vez", ts("09:05:00"))])

    result = run(tmp_path, repo, transcript)

    assert ("NONE FOUND" in result.header, first[:12] in result.header) == (False, True), \
        result.header


# ── (f) a mid-turn owner message whose prompt is a list of blocks ───────

BLOCKS_OWNER = "Mañana hay que llevar el coche al taller."


def test_should_output_owner_text_when_list_prompt_leads_with_a_system_reminder(tmp_path,
                                                                               closed_repo):
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn_blocks([text_block(LINKED_SESSIONS), text_block(BLOCKS_OWNER)],
                                     ts("08:20:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert (result.conversation.count(BLOCKS_OWNER), len(result.user_turns_with(BLOCKS_OWNER)),
            result.anywhere_in_conversation("Linked sessions now")) == (1, 1, False), \
        result.conversation


def test_should_output_owner_text_when_list_prompt_carries_an_image(tmp_path, closed_repo):
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn_blocks([image_block(), text_block(BLOCKS_OWNER)], ts("08:20:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)

    assert (len(result.user_turns_with(BLOCKS_OWNER)),
            result.anywhere_in_conversation("IMAGEN-BASE64")) == (1, False), result.conversation


def test_should_output_every_text_block_when_list_prompt_has_several(tmp_path, closed_repo):
    second = "Y comprar pan de camino."
    records = [human("hola", ts("08:00:00"))]
    records += owner_mid_turn_blocks([text_block(LINKED_SESSIONS), text_block(BLOCKS_OWNER),
                                      text_block(second)], ts("08:20:00"))
    transcript = write_transcript(tmp_path / "s.jsonl", records)

    result = run(tmp_path, closed_repo, transcript)
    both = [turn for turn in result.user_turns_with(BLOCKS_OWNER) if second in turn]

    assert (len(both), result.anywhere_in_conversation("Linked sessions now")) == (1, False), \
        result.conversation


# ── (g) a transcript line that is JSON but not a record ─────────────────


@pytest.mark.parametrize("raw_line", ["42", "null", "[1, 2]", '"just a string"'],
                         ids=["number", "null", "list", "string"])
def test_should_keep_going_when_a_line_parses_to_non_dict_json(tmp_path, closed_repo, raw_line):
    path = tmp_path / "s.jsonl"
    write_transcript(path, [human("ANTES-DE-LA-LINEA-RARA", ts("08:00:00"))])
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(raw_line + "\n")
        handle.write(json.dumps(human("DESPUES-DE-LA-LINEA-RARA", ts("08:10:00"))) + "\n")

    result = run(tmp_path, closed_repo, str(path))

    assert (len(result.user_turns_with("ANTES-DE-LA-LINEA-RARA")),
            len(result.user_turns_with("DESPUES-DE-LA-LINEA-RARA"))) == (1, 1), result.text
