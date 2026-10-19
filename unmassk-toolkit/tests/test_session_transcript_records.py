"""Contract tests: which user records are the owner, undated records, git failure.

Fix pass after Moriarty's attack (plan docs/plan/fix-close-transcript.md):
non-owner `user` records, and the surviving mutants M10 (undated records
dropped) and M11 (a git failure read as an empty history). Record shapes are
the ones Claude Code 2.1.299 writes; texts are invented.
"""

import sys

import pytest

from conftest import run_cmd
from session_transcript_harness import SCRIPT, commit, make_repo, run
from session_transcript_records_helpers import (
    base_record as _base, human, ts, write_transcript,
)

NOT_THE_OWNER = "TEXTO-QUE-NO-ESCRIBIO-EL-DUENO"


@pytest.fixture
def closed_repo(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    commit(repo, "work", "08:30:00")
    return repo


def scheduled_task_prompt(body, when):
    """A scheduled task firing: the prompt is the task file, not something typed."""
    record = _base("user", when)
    record.update({
        "promptId": "00000000-0000-4000-8000-0000000000f1",
        "message": {"role": "user",
                    "content": f'<scheduled-task name="tarea-semanal" '
                               f'file="/somewhere/scheduled/tarea-semanal/SKILL.md">\n'
                               f"{body}\n</scheduled-task>"},
        "permissionMode": "auto",
        "origin": {"kind": "task-notification", "subkind": "scheduled-trigger",
                   "fireReason": "scheduled"},
        "promptSource": "system",
        "turnOrigin": "scheduled",
        "turnPosition": {"promptIndex": 0, "turnIndex": 1},
        "queueSkipAttachments": True,
    })
    return record


def spawned_session_prompt(body, when):
    """The first prompt of a session Claude started: written by the parent session."""
    record = _base("user", when)
    record.update({
        "promptId": "00000000-0000-4000-8000-0000000000f2",
        "message": {"role": "user",
                    "content": "<system-reminder>\nLinked sessions now (status, not an "
                               "instruction): parent = local_0000 (idle)\n</system-reminder>"
                               "\n\nBackground (from the session that started this one):\n"
                               f"{body}\n\nTask: haz la tarea."},
        "permissionMode": "auto",
        "promptSource": "sdk",
        "turnOrigin": "sdk",
        "turnPosition": {"promptIndex": 0, "turnIndex": 1},
    })
    return record


def interrupt_marker(text, when):
    """What the harness writes when the owner presses Esc: nothing he typed."""
    record = _base("user", when)
    record.update({"promptId": "00000000-0000-4000-8000-0000000000f3",
                   "message": {"role": "user", "content": [{"type": "text", "text": text}]}})
    return record


# ── user records the owner did not type are not the owner ───────────────


@pytest.mark.parametrize("make_record", [scheduled_task_prompt, spawned_session_prompt],
                         ids=["scheduled-task", "spawned-session-prompt"])
def test_should_not_output_as_the_owner_a_prompt_he_did_not_type(tmp_path, closed_repo,
                                                                  make_record):
    transcript = write_transcript(tmp_path / "s.jsonl", [
        make_record(NOT_THE_OWNER, ts("08:00:00")), human("hola", ts("08:05:00"))])

    result = run(tmp_path, closed_repo, transcript)

    assert result.user_turns_with(NOT_THE_OWNER) == [], result.conversation


@pytest.mark.parametrize("marker", ["[Request interrupted by user]",
                                    "[Request interrupted by user for tool use]"])
def test_should_not_output_the_interrupt_marker_as_the_owner(tmp_path, closed_repo, marker):
    transcript = write_transcript(tmp_path / "s.jsonl", [
        human("hola", ts("08:00:00")), interrupt_marker(marker, ts("08:01:00"))])

    result = run(tmp_path, closed_repo, transcript)

    assert result.user_turns_with(marker) == [], result.conversation


def test_should_keep_the_owner_when_a_spawned_session_prompt_is_dropped(tmp_path, closed_repo):
    transcript = write_transcript(tmp_path / "s.jsonl", [
        spawned_session_prompt(NOT_THE_OWNER, ts("08:00:00")),
        human("PALABRA-DEL-DUENO-EN-LA-SESION-HIJA", ts("08:05:00"))])

    result = run(tmp_path, closed_repo, transcript)

    assert len(result.user_turns_with("PALABRA-DEL-DUENO-EN-LA-SESION-HIJA")) == 1, \
        result.conversation


def test_should_output_the_args_of_a_builtin_command_that_carries_no_origin(tmp_path,
                                                                            closed_repo):
    """Built-in commands (/model ...) are typed by the owner but written without `origin`."""
    record = _base("user", ts("08:10:00"))
    record.update({"promptId": "00000000-0000-4000-8000-0000000000f4",
                   "message": {"role": "user",
                               "content": "<command-name>/model</command-name>\n"
                                          "            <command-message>model</command-message>\n"
                                          "            <command-args>ARGS-DEL-DUENO</command-args>"}})
    transcript = write_transcript(tmp_path / "s.jsonl", [human("hola", ts("08:00:00")), record])

    result = run(tmp_path, closed_repo, transcript)

    assert len(result.user_turns_with("ARGS-DEL-DUENO")) == 1, result.conversation


# ── M10: a record without a timestamp is kept, and counted ──────────────


def test_should_keep_and_count_owner_records_that_carry_no_timestamp(tmp_path, closed_repo):
    undated = [human("SIN-FECHA-UNO", ts("08:00:00")), human("SIN-FECHA-DOS", ts("08:00:00"))]
    for record in undated:
        del record["timestamp"]
    transcript = write_transcript(tmp_path / "s.jsonl",
                                  [human("hola", ts("08:00:00"))] + undated)

    result = run(tmp_path, closed_repo, transcript)
    counted = [line for line in result.header.split("\n")
               if "timestamp" in line and " 2 " in f" {line} "]

    assert (len(result.user_turns_with("SIN-FECHA-UNO")),
            len(result.user_turns_with("SIN-FECHA-DOS")), len(counted)) == (1, 1, 1), \
        result.text


# ── M11: git refusing to answer is a failure, never an empty history ────


def test_should_fail_loud_when_git_cannot_read_the_repo(tmp_path):
    not_a_repo = tmp_path / "not-a-repo"
    not_a_repo.mkdir()
    transcript = write_transcript(tmp_path / "s.jsonl", [human("hola", ts("08:00:00"))])
    out = tmp_path / "close-input.txt"

    rc, _, stderr = run_cmd(
        [sys.executable, SCRIPT, "--repo", str(not_a_repo), "--transcript", transcript,
         "--out", str(out)],
        cwd=str(tmp_path), env={"GIT_CEILING_DIRECTORIES": str(tmp_path), "GIT_DIR": None})

    assert (rc != 0, "git" in stderr.lower(), out.exists()) == (True, True, False), \
        (rc, stderr)

