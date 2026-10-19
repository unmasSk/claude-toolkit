"""Contract tests for the close-session extractor: a second close in the same
session covers the whole session (D-143).

Every close this session holds is written by the real bin/memory/next.py, and
the transcript carries exactly what that call printed — written by the close
agent (in its sidechain file) or by the orchestrator itself (top-level).
"""

import pytest

from session_transcript_harness import (
    commit, gitmem_next, held_close, held_close_top_level, make_repo, run,
)
from session_transcript_records_helpers import (
    SESSION_ID, append_records, assistant, human, queue_op, ts, write_transcript,
)


def _holding(where, path, close, launched, done):
    if where == "close-agent":
        return held_close(path, SESSION_ID, close, launched, done)
    return held_close_top_level(SESSION_ID, close, launched, done)


@pytest.fixture(params=["close-agent", "orchestrator"])
def redo(tmp_path, request):
    """Previous session closed at 07:00; this session (from 08:00) closed at 09:00
    and is now being closed again. Returns (repo, transcript, previous sha, first close)."""
    repo = make_repo(tmp_path)
    commit(repo, "old work", "06:00:00")
    previous = commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    commit(repo, "work before the first close", "08:30:00")
    first = gitmem_next(repo, "this session, first close", "09:00:00")
    commit(repo, "work after the first close", "09:10:00")
    path = tmp_path / f"{SESSION_ID}.jsonl"
    records = [queue_op("enqueue", ts("08:00:00"), content="hola"),
               human("ANTES-DEL-PRIMER-CIERRE", ts("08:00:01")),
               assistant("respuesta temprana", ts("08:00:05"))]
    records += _holding(request.param, path, first, ts("08:58:00"), ts("09:00:01"))
    records += [human("DESPUES-DEL-PRIMER-CIERRE", ts("09:05:00"))]
    transcript = write_transcript(path, records)
    return repo, transcript, previous, first


def close_again_through_the_close_agent(repo, transcript):
    """This session closes a second time, through its close agent."""
    second = gitmem_next(repo, "this session, second close", "09:20:00")
    append_records(transcript, held_close(transcript, SESSION_ID, second,
                                          ts("09:18:00"), ts("09:20:01")))
    return second


def test_should_return_whole_session_conversation_when_closing_twice(tmp_path, redo):
    repo, transcript, _, _ = redo

    result = run(tmp_path, repo, transcript)

    assert (len(result.user_turns_with("ANTES-DEL-PRIMER-CIERRE")),
            len(result.user_turns_with("DESPUES-DEL-PRIMER-CIERRE"))) == (1, 1), result.text


def test_should_return_whole_session_commits_when_closing_twice(tmp_path, redo):
    repo, transcript, _, first = redo

    result = run(tmp_path, repo, transcript)

    assert result.commits == ["work before the first close", first.subject,
                              "work after the first close"], result.text


def test_should_name_previous_session_close_as_boundary_when_closing_twice(tmp_path, redo):
    repo, transcript, previous, first = redo

    result = run(tmp_path, repo, transcript)
    boundary = result.header_lines("boundary:")

    assert (len(boundary), previous[:12] in boundary[0], first.sha[:12] in boundary[0]) == \
        (1, True, False), result.header


def test_should_skip_every_earlier_close_of_this_session_when_closing_a_third_time(tmp_path,
                                                                                    redo):
    repo, transcript, previous, _ = redo
    close_again_through_the_close_agent(repo, transcript)

    result = run(tmp_path, repo, transcript)

    assert (previous[:12] in result.header,
            len(result.user_turns_with("ANTES-DEL-PRIMER-CIERRE")),
            result.commits[0]) == (True, 1, "work before the first close"), result.text


def test_should_name_the_skipped_close_when_the_newest_close_is_this_sessions_own(tmp_path,
                                                                                 redo):
    repo, transcript, _, first = redo

    result = run(tmp_path, repo, transcript)
    naming = [line for line in result.header.split("\n")
              if first.sha[:12] in line and not line.startswith("boundary:")]

    assert len(naming) == 1, result.header


def test_should_name_the_newest_skipped_close_when_closing_a_third_time(tmp_path, redo):
    repo, transcript, _, _ = redo
    second = close_again_through_the_close_agent(repo, transcript)

    result = run(tmp_path, repo, transcript)
    naming = [line for line in result.header.split("\n")
              if second.sha[:12] in line and not line.startswith("boundary:")]

    assert len(naming) == 1, result.header


@pytest.mark.parametrize("where", ["close-agent", "orchestrator"])
def test_should_not_say_none_found_when_the_only_close_was_skipped(tmp_path, where):
    repo = make_repo(tmp_path)
    commit(repo, "work before the first close", "08:30:00")
    first = gitmem_next(repo, "this session, first close", "09:00:00")
    path = tmp_path / f"{SESSION_ID}.jsonl"
    transcript = write_transcript(path, [human("hola", ts("08:00:00"))]
                                  + _holding(where, path, first, ts("08:58:00"), ts("09:00:01"))
                                  + [human("otra vez", ts("09:05:00"))])

    result = run(tmp_path, repo, transcript)

    assert ("NONE FOUND" in result.header, first.sha[:12] in result.header,
            len(result.user_turns_with("hola"))) == (False, True, 1), result.text


# ── a close from before this session is the boundary, never skipped ─────


def test_should_keep_last_close_as_boundary_when_it_predates_the_transcript(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    last = commit(repo, "[NEXT] 🔜 the close right before this session", "07:30:00")
    commit(repo, "work in this session", "08:30:00")
    transcript = write_transcript(tmp_path / "s.jsonl", [
        queue_op("enqueue", ts("08:00:00"), content="hola"),
        human("hola", ts("08:00:01"))])

    result = run(tmp_path, repo, transcript)

    assert (last[:12] in result.header, result.commits) == \
        (True, ["work in this session"]), result.text
