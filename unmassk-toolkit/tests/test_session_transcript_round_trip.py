"""Round-trip of the close extractor's seam: Claude Code's .jsonl in, the owner's words out.

Plan docs/plan/fix-close-transcript.md, step 1.3. The fixture holds records with the
exact shape Claude Code writes (fields, types, tags, order), their texts and ids
replaced by invented ones. Every expected value is read from the records' own fields.
"""

import json
import os
import re
import sys

import pytest

from conftest import SOURCE_ROOT, git_cmd, run_cmd

SCRIPT = os.path.join(
    SOURCE_ROOT, "skills", "unmassk-close-session", "scripts", "session_transcript.py"
)
FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures",
                       "session_transcript_real_records.jsonl")
COMMAND_ARGS = re.compile(r"<command-args>(.*)</command-args>", re.DOTALL)
COMMAND_NAME = re.compile(r"<command-name>(.*?)</command-name>", re.DOTALL)
INJECTED_BLOCK = re.compile(r"<system-reminder>.*</system-reminder>", re.DOTALL)


def _records():
    with open(FIXTURE, encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _owner_texts(records):
    """(timestamp, text) of every message the owner wrote, as the producer stored it."""
    out = []
    for record in records:
        if record.get("type") == "user" and (record.get("origin") or {}).get("kind") == "human":
            content = record["message"]["content"]
            out.append((record["timestamp"], _typed(content)))
        attachment = record.get("attachment") or {}
        if attachment.get("type") == "queued_command" \
                and (attachment.get("origin") or {}).get("kind") == "human":
            out.append((record["timestamp"], _prompt_text(attachment["prompt"])))
    return out


def _typed(content):
    """A slash command as the owner typed it, `/name args`; any other text as is."""
    args, name = COMMAND_ARGS.search(content), COMMAND_NAME.search(content)
    if not args:
        return content
    return " ".join(part for part in (name.group(1), args.group(1)) if part)


def _prompt_text(prompt):
    """A str prompt as is; a list prompt as its text blocks, injected reminders left out."""
    if isinstance(prompt, str):
        return prompt
    return "\n".join(block["text"] for block in prompt
                     if block.get("type") == "text" and not INJECTED_BLOCK.fullmatch(block["text"]))


def _foreign_texts(records):
    """What a peer session or a task notification carried: never the owner's words."""
    out = []
    for record in records:
        attachment = record.get("attachment") or {}
        origin = attachment.get("origin") or {}
        if attachment.get("type") != "queued_command" or origin.get("kind") == "human":
            continue
        if "body" in origin:
            out.append(origin["body"])
        out.extend(re.findall(r"<(?:task-id|summary)>(.*?)</", attachment["prompt"]))
    return out


@pytest.fixture(scope="module")
def extracted(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("round_trip")
    repo = tmp / "repo"
    repo.mkdir()
    git_cmd(["init", "-q", "-b", "main"], str(repo))
    stamp = "2026-10-18T20:00:00Z"
    rc, _, err = git_cmd(["commit", "-q", "--allow-empty", "-m", "[NEXT] 🔜 previous close"],
                         str(repo), env={"GIT_AUTHOR_DATE": stamp, "GIT_COMMITTER_DATE": stamp})
    assert rc == 0, err
    out = tmp / "close-input.txt"
    rc, _, stderr = run_cmd([sys.executable, SCRIPT, "--repo", str(repo),
                             "--transcript", FIXTURE, "--out", str(out)], cwd=str(repo))
    assert rc == 0, stderr
    conversation = out.read_text(encoding="utf-8").partition("# CONVERSATION")[2]
    conversation = conversation.split("\n", 1)[1].lstrip("\n")
    turns = [chunk for chunk in re.split(r"(?:^|\n\n)=== ", conversation) if chunk]
    return conversation, [tuple(chunk.split("\n", 1)) for chunk in turns]


def test_fixture_should_hold_each_kind_of_record_the_round_trip_needs():
    """A guard on the fixture itself: trimmed of a kind, the other tests prove less."""
    records = _records()
    typed = [r for r in records if r.get("type") == "user"]
    attachments = [r["attachment"] for r in records if r.get("type") == "attachment"]
    attachment_kinds = [(a.get("origin") or {}).get("kind") for a in attachments]
    list_prompts = [a for a in attachments
                    if (a.get("origin") or {}).get("kind") == "human" and isinstance(a["prompt"], list)
                    and any(INJECTED_BLOCK.fullmatch(b.get("text", "")) for b in a["prompt"])]

    assert (sum(not COMMAND_ARGS.search(r["message"]["content"]) for r in typed),
            sum(bool(COMMAND_ARGS.search(r["message"]["content"])) for r in typed),
            sorted(attachment_kinds), len(list_prompts)) == \
        (1, 1, ["human", "human", "human", "peer", "task-notification"], 1)


def test_should_output_every_owner_text_exactly_as_the_producer_wrote_it(extracted):
    _, turns = extracted
    expected = [(f"user {stamp}", text) for stamp, text in _owner_texts(_records())]

    assert sorted(turns) == sorted(expected), turns


def test_should_output_nothing_a_peer_or_a_task_notification_carried(extracted):
    conversation, _ = extracted
    foreign = _foreign_texts(_records())

    assert (len(foreign) >= 2, [text for text in foreign if text in conversation]) \
        == (True, []), conversation
