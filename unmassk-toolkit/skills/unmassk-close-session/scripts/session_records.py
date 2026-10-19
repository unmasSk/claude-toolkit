"""Read Claude Code transcripts: the conversation turns, and the closes a session holds."""

import heapq
import json
import os
import re
import time

# Machinery the harness injects: reminders, subagent reports,
# slash-command echoes. Only WELL-FORMED spans are removed: in a project
# whose subject is its own machinery, a real message can open with
# "<system-reminder> why does this fire on every message".
_INJECTED = (
    "system-reminder",
    "task-notification",
    "local-command-caveat",
    "local-command-stdout",
    "local-command-stderr",
    "command-name",
    "command-message",
    "user-prompt-submit-hook",
    "bash-input",
    "bash-stdout",
    "bash-stderr",
)
_INLINE_TAGS = re.compile(r"<(" + "|".join(_INJECTED) + r")\b.*?</\1>", re.DOTALL)

# The arguments of a slash command are what the owner typed: only the tags go.
_COMMAND_ARGS_TAGS = re.compile(r"</?command-args>")

# How recently another transcript must have been touched for a second
# open session to be worth naming.
_RECENT_SECONDS = 1800

# What the harness writes when the owner presses Esc: nothing he typed.
_INTERRUPT_MARKER = re.compile(r"\[Request interrupted by user[^\]]*\]")

# A close is written by `gitmem next`, which prints `<sha> [NEXT] ...`.
_GITMEM_NEXT = re.compile(r"\bgitmem\b[^|;&\n]*\snext\s")
_CLOSE_LINE = re.compile(r"^([0-9a-f]{7,40}) \[NEXT\]", re.MULTILINE)


def _records(path):
    """Every JSON object in a .jsonl file, in order; other lines are skipped."""
    with open(path, encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def _clean(text):
    return _COMMAND_ARGS_TAGS.sub("", _INLINE_TAGS.sub("", text)).strip()


def _text_blocks(content):
    """The cleaned text of a content value: a string or a list of blocks."""
    if isinstance(content, str):
        content = [{"type": "text", "text": content}]
    if not isinstance(content, list):
        return []
    out = []
    for chunk in content:
        # thinking, tool_use and tool_result all fall out here.
        if not isinstance(chunk, dict) or chunk.get("type") != "text":
            continue
        text = _clean(chunk.get("text") or "")
        if text:
            out.append(text)
    return out


def _typed_mid_turn(entry):
    """The owner's message typed while Claude was working, if this is one.

    It arrives only as a `queued_command` attachment; the queue operations
    repeat its text and are ignored.
    """
    attachment = entry.get("attachment")
    if not isinstance(attachment, dict) or attachment.get("type") != "queued_command":
        return []
    if (attachment.get("origin") or {}).get("kind") != "human":
        return []
    return _text_blocks(attachment.get("prompt"))


def _typed_by_owner(entry):
    """What the owner typed in a `user` record. Scheduled tasks, prompts a
    parent session wrote and the interrupt marker are not him; built-in
    commands carry no origin at all and are kept."""
    if (entry.get("origin") or {}).get("kind", "human") != "human":
        return []
    if entry.get("turnOrigin", "human") != "human":
        return []
    said = _text_blocks((entry.get("message") or {}).get("content"))
    return [text for text in said if not _INTERRUPT_MARKER.fullmatch(text)]


def _turn(entry):
    """(who, said) for an entry of this conversation, or None."""
    # A subagent's own conversation, and whatever the harness flags as
    # injected (skill bodies, hook feedback), are not this conversation.
    if entry.get("isSidechain") or entry.get("isMeta"):
        return None
    if entry.get("type") == "attachment":
        return "user", _typed_mid_turn(entry)
    if entry.get("type") == "user":
        return (entry.get("message") or {}).get("role", "user"), _typed_by_owner(entry)
    if entry.get("type") == "assistant":
        return (entry.get("message") or {}).get("role", "assistant"), _text_blocks(
            (entry.get("message") or {}).get("content"))
    return None


def session_id(transcript):
    """Claude Code names each transcript after its session id."""
    return os.path.splitext(os.path.basename(transcript))[0]


def _turns(transcript, since_iso):
    """[(sort_key, who, stamp, said)] of one transcript, in file order.

    An undated entry is kept, sorted where it sits: an empty timestamp sorts
    below every boundary, so dropping it would delete real words unseen.
    """
    out = []
    last = ""
    for entry in _records(transcript):
        stamp = entry.get("timestamp") or ""
        if since_iso and stamp and stamp < since_iso:
            continue
        last = stamp or last
        who, said = _turn(entry) or (None, None)
        if said:
            out.append((last, who, stamp, said))
    return out


def conversation(transcripts, since_iso):
    """Returns (turns, undated, sessions) for every transcript since the boundary.

    Turns of overlapping sessions interleave by time; each file keeps its own
    order. When more than one session speaks, each turn names its session.
    `sessions` lists the ids that contributed a turn, in the order given.
    """
    per_file = [(session_id(path), _turns(path, since_iso)) for path in transcripts]
    sessions = [sid for sid, turns in per_file if turns]
    labelled = len(sessions) > 1
    streams = [[(key, sid, who, stamp, said) for key, who, stamp, said in turns]
               for sid, turns in per_file]

    out = []
    undated = 0
    for _, sid, who, stamp, said in heapq.merge(*streams, key=lambda turn: turn[0]):
        if not stamp:
            undated += 1
            stamp = "(no timestamp)"
        label = f" · session {sid[:8]}" if labelled else ""
        out.append(f"=== {who} {stamp}{label}\n" + "\n".join(said))
    return out, undated, sessions


def _results_of_close_calls(path):
    """The text of every tool result answering a `gitmem next` call in a file."""
    calls = set()
    for entry in _records(path):
        content = (entry.get("message") or {}).get("content")
        for block in content if isinstance(content, list) else []:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and _GITMEM_NEXT.search(
                    str((block.get("input") or {}).get("command") or "")):
                calls.add(block.get("id"))
            elif block.get("type") == "tool_result" and block.get("tool_use_id") in calls:
                result = block.get("content")
                if isinstance(result, list):
                    result = "\n".join(str(part.get("text") or "") for part in result
                                       if isinstance(part, dict))
                yield str(result or "")


def held_closes(transcript):
    """Sha prefixes of the closes this session wrote itself.

    A close is held when the session (or one of its subagents, under
    `<session>/subagents/`) ran `gitmem next` and got the close's sha back.
    Seeing a close in `git log` is not holding it.
    """
    folder = os.path.join(os.path.splitext(transcript)[0], "subagents")
    files = [transcript]
    if os.path.isdir(folder):
        files += sorted(os.path.join(folder, name) for name in os.listdir(folder)
                        if name.endswith(".jsonl"))
    held = set()
    for path in files:
        for result in _results_of_close_calls(path):
            held.update(_CLOSE_LINE.findall(result))
    return held


def _projects_root():
    return os.path.join(os.path.expanduser("~"), ".claude", "projects")


def _slug(path):
    """Claude Code's folder name for a project: every non-alphanumeric of its path as a dash."""
    return re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(path))


def project_transcripts(repo):
    """Returns (paths oldest first, note). The newest is the session being
    closed; the note is never empty when something is off."""
    root = _projects_root()
    if not os.path.isdir(root):
        return [], f"{root} does not exist — is this Claude Code?"

    wanted = _slug(repo)
    folder = os.path.join(root, wanted)
    if not os.path.isdir(folder):
        others = sorted(os.listdir(root))
        return [], (
            f"no transcript folder for this project (expected {wanted} "
            f"inside {root}, which holds {len(others)} others such as "
            f"{others[:3]})"
        )

    files = [os.path.join(folder, name) for name in os.listdir(folder)
             if name.endswith(".jsonl")]
    if not files:
        return [], f"{folder} holds no .jsonl transcript"
    files.sort(key=os.path.getmtime)
    newest = files[-1]

    # This cannot tell which open window is asking, only which file was
    # written to last; so any other recently active transcript is named,
    # with the age of the one chosen [Moriarty, 2026-08-05].
    now = time.time()
    rivals = [other for other in files[:-1] if now - os.path.getmtime(other) < _RECENT_SECONDS]
    if rivals:
        return files, (
            "MORE THAN ONE SESSION IS OPEN ON THIS PROJECT — "
            f"the one chosen was last written to {int((now - os.path.getmtime(newest)) // 60)} "
            f"min ago; {len(rivals)} other(s) active within the last "
            f"{_RECENT_SECONDS // 60} min: "
            + ", ".join(os.path.basename(r) for r in rivals)
            + ". Confirm this is the session being closed."
        )
    return files, ""
