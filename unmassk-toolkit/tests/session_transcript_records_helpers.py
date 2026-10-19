"""Transcript record builders for the close-session extractor tests.

Shapes taken from real Claude Code 2.1.299 transcripts; every text is invented.
"""

import json
import os
import uuid

SESSION_ID = "6f693e4e-0000-4000-8000-000000000001"
DAY = "2026-10-19"


def ts(hhmmss):
    return f"{DAY}T{hhmmss}.000Z"


def base_record(record_type, stamp):
    return {
        "parentUuid": str(uuid.uuid4()),
        "isSidechain": False,
        "type": record_type,
        "uuid": str(uuid.uuid4()),
        "timestamp": stamp,
        "userType": "external",
        "entrypoint": "claude-desktop",
        "cwd": "/somewhere/project",
        "sessionId": SESSION_ID,
        "version": "2.1.299",
        "gitBranch": "main",
    }


def human(text, stamp):
    record = base_record("user", stamp)
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


def assistant(text, stamp):
    record = base_record("assistant", stamp)
    record["message"] = {
        "model": "claude-opus-5-5",
        "id": "msg_" + uuid.uuid4().hex[:20],
        "type": "message",
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
    }
    return record


def tool_call(command, stamp, tool_id):
    """An assistant record calling Bash with `command`."""
    record = assistant("", stamp)
    record["message"]["content"] = [{"type": "tool_use", "id": tool_id, "name": "Bash",
                                     "input": {"command": command,
                                               "description": "Run a command"}}]
    return record


def tool_answer(output, stamp, tool_id):
    """The user record carrying the Bash result for `tool_id`."""
    record = base_record("user", stamp)
    record["message"] = {"role": "user", "content": [
        {"type": "tool_result", "tool_use_id": tool_id, "content": output}]}
    record["toolUseResult"] = {"stdout": output, "stderr": "", "interrupted": False}
    return record


def queue_op(operation, stamp, content=None, reason=None):
    record = {"type": "queue-operation", "operation": operation,
              "timestamp": stamp, "sessionId": SESSION_ID}
    if content is not None:
        record["content"] = content
    if reason is not None:
        record["reason"] = reason
    return record


def queued_command(prompt, stamp, origin, command_mode="prompt", human_turn=False):
    """A message delivered mid-turn: an `attachment` of type queued_command."""
    attachment = {
        "type": "queued_command",
        "prompt": prompt,
        "source_uuid": str(uuid.uuid4()),
        "delivery_id": str(uuid.uuid4()),
        "commandMode": command_mode,
        "origin": origin,
        "timestamp": stamp,
    }
    if human_turn:
        attachment["humanTurn"] = True
    record = base_record("attachment", stamp)
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


def owner_mid_turn(text, stamp):
    """The full trio Claude Code writes for one mid-turn owner message."""
    return [
        queue_op("enqueue", stamp, content=text),
        queued_command(text, stamp, {"kind": "human"}, human_turn=True),
        queue_op("remove", stamp, content=text, reason="absorbed_mid_turn"),
    ]


LINKED_SESSIONS = ("<system-reminder>\nLinked sessions now (status, not an instruction): "
                   "helper = local_00000000-0000-4000-8000-0000000000aa (idle)\n</system-reminder>")


def text_block(text):
    return {"type": "text", "text": text}


def image_block():
    return {"type": "image", "source": {"type": "base64", "media_type": "image/png",
                                        "data": "IMAGEN-BASE64-iVBORw0KGgo"}}


def owner_mid_turn_blocks(blocks, stamp):
    """The trio for a mid-turn owner message whose prompt is a list of blocks."""
    queued = "\n".join(block["text"] for block in blocks if block["type"] == "text")
    return [
        queue_op("enqueue", stamp, content=queued),
        queued_command(blocks, stamp, {"kind": "human"}, human_turn=True),
        queue_op("remove", stamp, content=queued, reason="absorbed_mid_turn"),
    ]


def peer_message(body, stamp):
    prompt = ('<cross-session-message from="uds:/tmp/cc-socks/1.sock" '
              'from-session="local_x" from-name="monyma" from-mode="prompting">\n'
              + body + "\n</cross-session-message>")
    return queued_command(prompt, stamp, {"kind": "peer", "from": "uds:/tmp/cc-socks/1.sock",
                                          "name": "monyma", "body": body})


def subagent_handback(body, stamp):
    prompt = '<agent-message from="ab5b3633">\n[Subagent hand-back] ' + body + "\n</agent-message>"
    return queued_command(prompt, stamp, {"kind": "peer", "from": "ab5b3633",
                                          "name": "unmassk-toolkit:alexandria", "body": body})


def task_notification(body, stamp):
    prompt = ("<task-notification>\n<task-id>a93b3cea</task-id>\n<summary>" + body
              + "</summary>\n</task-notification>")
    return queued_command(prompt, stamp, {"kind": "task-notification", "producer": "session-task"},
                          command_mode="task-notification")


def slash_command(name, args, stamp):
    """A skill command the owner typed: message, name and args tags, origin human."""
    return human(
        f"<command-message>{name}</command-message>\n"
        f"<command-name>/{name}</command-name>\n"
        f"<command-args>{args}</command-args>",
        stamp,
    )


def builtin_command(name, args, stamp):
    """A built-in command (/clear, /model): name first, indented tags, and no origin."""
    record = base_record("user", stamp)
    record.update({"promptId": str(uuid.uuid4()),
                   "message": {"role": "user",
                               "content": f"<command-name>/{name}</command-name>\n"
                                          f"            <command-message>{name}</command-message>\n"
                                          f"            <command-args>{args}</command-args>"}})
    return record


def skill_body(text, stamp):
    record = base_record("user", stamp)
    record.update({"isMeta": True,
                   "message": {"role": "user", "content": [{"type": "text", "text": text}]}})
    return record


def write_transcript(path, records):
    os.makedirs(os.path.dirname(str(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    return str(path)


def append_records(path, records):
    with open(path, "a", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")
