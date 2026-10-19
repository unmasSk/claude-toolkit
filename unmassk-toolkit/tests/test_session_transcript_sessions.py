"""Contract tests: the close reads every session since the last close (D-144).

Fix pass after Moriarty's attack (plan docs/plan/fix-close-transcript.md).
Driven the way the close agent runs the script: no --transcript, so it finds
the transcripts itself in a disposable HOME laid out like Claude Code's
~/.claude/projects/<project>/ (top-level <session>.jsonl files, each with its
subagents under <session>/subagents/).
"""

import os
import re
import sys
import time

import pytest

from conftest import git_cmd, run_cmd
from session_transcript_harness import (
    SCRIPT, Run, commit, gitmem_next, held_close, make_repo,
)
from session_transcript_records_helpers import (
    assistant, human, owner_mid_turn, tool_answer, tool_call, ts, write_transcript,
)

SESSION_Z = "aaaaaaaa-0000-4000-8000-00000000000a"  # closed the session before
SESSION_A = "bbbbbbbb-0000-4000-8000-00000000000b"
SESSION_B = "cccccccc-0000-4000-8000-00000000000c"
HOUR = 3600


def project_folder(home, repo):
    """Where Claude Code keeps a project's transcripts: its path, non-alphanumerics as dashes."""
    return os.path.join(home, ".claude", "projects",
                        re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(repo)))


def session_path(folder, session_id):
    return os.path.join(folder, f"{session_id}.jsonl")


def write_session(folder, session_id, records, age_seconds):
    """One top-level transcript, last written `age_seconds` ago."""
    for record in records:
        if "sessionId" in record:
            record["sessionId"] = session_id
    path = write_transcript(session_path(folder, session_id), records)
    stamp = time.time() - age_seconds
    os.utime(path, (stamp, stamp))
    return path


def subagent_chatter(folder, session_id, text, when):
    """A subagent's own conversation, in its sidechain file."""
    records = [human(text, when), assistant(text, when)]
    for record in records:
        record.update({"isSidechain": True, "agentId": "a0000000000000001",
                       "sessionId": session_id})
    write_transcript(os.path.join(folder, session_id, "subagents",
                                  "agent-a0000000000000001.jsonl"), records)


def run_discovered(tmp_path, repo, home):
    out = str(tmp_path / "close-input.txt")
    rc, stdout, stderr = run_cmd([sys.executable, SCRIPT, "--repo", repo, "--out", out],
                                 cwd=repo, env={"HOME": home, "USERPROFILE": home})
    assert rc == 0, f"script failed rc={rc}: {stderr}"
    with open(out, encoding="utf-8") as handle:
        return Run(rc, stdout, stderr, handle.read())


def first_line_of_turn_with(result, phrase):
    turns = [turn for turn in result.turns if phrase in turn]
    assert len(turns) == 1, result.conversation
    return turns[0].split("\n", 1)[0]


def boundary_line(result):
    lines = result.header_lines("boundary:")
    assert len(lines) == 1, result.header
    return lines[0]


# ── a session that ended without a close, then the one being closed ─────

A_WORDS = ("PALABRA-A-UNO", "PALABRA-A-MITAD-DE-TURNO", "PALABRA-A-DOS")
B_WORDS = ("PALABRA-B-UNO", "PALABRA-B-DOS")


@pytest.fixture
def unclosed_then_current(tmp_path):
    """Z closed at 07:00. A ran 07:30-08:30 and ended without a close (or with
    /clear). B, from 09:00, is the session being closed now."""
    home = str(tmp_path / "home")
    repo = make_repo(tmp_path)
    folder = project_folder(home, repo)
    commit(repo, "old work", "05:00:00")
    z_close = gitmem_next(repo, "previous session close", "07:00:00")
    commit(repo, "work-of-session-A", "08:00:00")
    commit(repo, "work-of-session-B", "09:10:00")

    z_records = [human("PALABRA-Z-ANTES-DEL-CIERRE", ts("05:30:00")),
                 assistant("respuesta de Z", ts("05:30:05"))]
    z_records += held_close(session_path(folder, SESSION_Z), SESSION_Z, z_close,
                            ts("06:58:00"), ts("07:00:01"))
    write_session(folder, SESSION_Z, z_records, 5 * HOUR)

    a_records = [human(A_WORDS[0], ts("07:30:00")), assistant("respuesta A", ts("07:30:05"))]
    a_records += owner_mid_turn(A_WORDS[1], ts("07:45:00"))
    a_records += [human(A_WORDS[2], ts("08:30:00")), assistant("ok A", ts("08:30:05"))]
    write_session(folder, SESSION_A, a_records, 3 * HOUR)
    subagent_chatter(folder, SESSION_A, "TEXTO-DEL-SUBAGENTE-DE-A", ts("07:50:00"))

    write_session(folder, SESSION_B, [human(B_WORDS[0], ts("09:00:00")),
                                      assistant("respuesta B", ts("09:00:05")),
                                      human(B_WORDS[1], ts("09:20:00"))], 0)
    return run_discovered(tmp_path, repo, home)


@pytest.mark.parametrize("word", A_WORDS)
def test_should_output_every_owner_word_of_a_session_that_ended_without_a_close(
        unclosed_then_current, word):
    assert len(unclosed_then_current.user_turns_with(word)) == 1, \
        unclosed_then_current.conversation


@pytest.mark.parametrize("word", B_WORDS)
def test_should_output_the_closing_sessions_words_when_an_earlier_session_is_read(
        unclosed_then_current, word):
    assert len(unclosed_then_current.user_turns_with(word)) == 1, \
        unclosed_then_current.conversation


def test_should_order_the_turns_of_both_sessions_by_time(unclosed_then_current):
    conversation = unclosed_then_current.conversation
    positions = [conversation.find(word) for word in A_WORDS + B_WORDS]

    assert (positions[0] >= 0, positions == sorted(positions)) == (True, True), conversation


@pytest.mark.parametrize("word,session", [(word, SESSION_A) for word in A_WORDS]
                         + [(word, SESSION_B) for word in B_WORDS])
def test_should_label_each_turn_with_its_session(unclosed_then_current, word, session):
    first_line = first_line_of_turn_with(unclosed_then_current, word)

    assert session[:8] in first_line, first_line


def test_should_leave_out_a_session_whose_records_all_predate_the_last_close(
        unclosed_then_current):
    assert not unclosed_then_current.anywhere_in_conversation("PALABRA-Z-ANTES-DEL-CIERRE"), \
        unclosed_then_current.conversation


def test_should_leave_out_subagent_sidechains_of_every_session(unclosed_then_current):
    assert not unclosed_then_current.anywhere_in_conversation("TEXTO-DEL-SUBAGENTE-DE-A"), \
        unclosed_then_current.conversation


def test_should_list_the_commits_of_both_sessions_since_the_last_close(unclosed_then_current):
    assert unclosed_then_current.commits == ["work-of-session-A", "work-of-session-B"], \
        unclosed_then_current.text


def test_should_not_stop_the_close_when_an_unclosed_session_is_read(unclosed_then_current):
    assert unclosed_then_current.stop_lines() == [], unclosed_then_current.header


# ── two sessions open at once, neither closed: turns interleave by time ──


def test_should_interleave_the_turns_of_overlapping_sessions_by_time(tmp_path):
    home = str(tmp_path / "home")
    repo = make_repo(tmp_path)
    folder = project_folder(home, repo)
    commit(repo, "[NEXT] ⏩️ previous session close", "06:00:00")
    commit(repo, "work", "07:20:00")
    write_session(folder, SESSION_B, [human("SOLAPE-B-07-30", ts("07:30:00"))], 2 * HOUR)
    write_session(folder, SESSION_A, [human("SOLAPE-A-07-10", ts("07:10:00")),
                                      human("SOLAPE-A-07-50", ts("07:50:00"))], 0)

    result = run_discovered(tmp_path, repo, home)
    positions = [result.conversation.find(word)
                 for word in ("SOLAPE-A-07-10", "SOLAPE-B-07-30", "SOLAPE-A-07-50")]

    assert (positions[1] >= 0, positions == sorted(positions)) == (True, True), \
        result.conversation


# ── a parallel window's close is not this session's own ─────────────────

def _parallel(tmp_path, a_extra):
    """A is being closed; it started at 06:00. B, another window, closed at 06:40
    and its transcript holds that close. `a_extra(repo, b_close)` adds records to A."""
    home = str(tmp_path / "home")
    repo = make_repo(tmp_path)
    folder = project_folder(home, repo)
    commit(repo, "old work", "04:00:00")
    commit(repo, "[NEXT] ⏩️ earlier close", "05:00:00")
    commit(repo, "work-B1", "06:20:00")
    b_close = gitmem_next(repo, "close of parallel session B", "06:40:00")

    b_records = [human("PALABRA-B", ts("06:10:00")), assistant("respuesta B", ts("06:10:05"))]
    b_records += held_close(session_path(folder, SESSION_B), SESSION_B, b_close,
                            ts("06:38:00"), ts("06:40:01"))
    write_session(folder, SESSION_B, b_records, 3 * HOUR)

    a_records = [human("PALABRA-A-TEMPRANA", ts("06:00:00")),
                 assistant("respuesta A", ts("06:00:05"))]
    a_records += a_extra(repo, b_close)
    a_records += [human("PALABRA-A-TARDIA", ts("07:05:00"))]
    commit(repo, "work-A-after-B-closed", "07:10:00")
    write_session(folder, SESSION_A, a_records, 0)
    return run_discovered(tmp_path, repo, home), b_close


def _nothing(_repo, _close):
    return []


def _ran(command, repo):
    """A Bash call of A whose output is what `git log --oneline -3` really prints."""
    rc, output, err = git_cmd(["log", "--oneline", "-3"], repo)
    assert rc == 0, err
    tool_id = "toolu_gitlog0000000000000001"
    return [tool_call(command, ts("06:50:00"), tool_id),
            tool_answer(output, ts("06:50:01"), tool_id)]


def _saw_it_in_git_log(repo, _close):
    """A ran `git log` after B closed and saw B's close: mentioning is not holding."""
    return _ran("git log --oneline -3", repo)


def _saw_it_after_a_gitmem_search(repo, _close):
    """`gitmem search next` is not `gitmem next`: B's close in its output is not A's."""
    return _ran("gitmem search next && git log --oneline -3", repo)


PARALLEL = pytest.mark.parametrize(
    "a_extra", [_nothing, _saw_it_in_git_log, _saw_it_after_a_gitmem_search],
    ids=["not-mentioned", "seen-in-git-log", "seen-after-gitmem-search"])


@PARALLEL
def test_should_take_a_parallel_windows_close_as_the_boundary(tmp_path, a_extra):
    result, b_close = _parallel(tmp_path, a_extra)

    assert b_close.sha[:12] in boundary_line(result), result.header


@PARALLEL
def test_should_not_name_a_parallel_windows_close_as_skipped(tmp_path, a_extra):
    result, b_close = _parallel(tmp_path, a_extra)
    naming = [line for line in result.header.split("\n")
              if b_close.sha[:12] in line and not line.startswith("boundary:")]

    assert naming == [], result.header


@PARALLEL
def test_should_list_only_commits_after_a_parallel_windows_close(tmp_path, a_extra):
    result, _ = _parallel(tmp_path, a_extra)

    assert result.commits == ["work-A-after-B-closed"], result.text


# ── the transcript taken as "this session" is the one written to last ───


def test_should_skip_only_the_closes_held_by_the_newest_transcript(tmp_path):
    """C is being closed a second time; an older session Z sits in the folder."""
    home = str(tmp_path / "home")
    repo = make_repo(tmp_path)
    folder = project_folder(home, repo)
    commit(repo, "old work", "05:00:00")
    previous = commit(repo, "[NEXT] ⏩️ previous session close", "07:00:00")
    commit(repo, "work before the first close", "08:30:00")
    first = gitmem_next(repo, "this session, first close", "09:00:00")
    write_session(folder, SESSION_Z, [human("PALABRA-Z", ts("05:30:00"))], 5 * HOUR)
    c_records = [human("PALABRA-C-ANTES", ts("08:00:00"))]
    c_records += held_close(session_path(folder, SESSION_B), SESSION_B, first,
                            ts("08:58:00"), ts("09:00:01"))
    c_records += [human("PALABRA-C-DESPUES", ts("09:05:00"))]
    write_session(folder, SESSION_B, c_records, 0)

    result = run_discovered(tmp_path, repo, home)

    assert (previous[:12] in boundary_line(result),
            len(result.user_turns_with("PALABRA-C-ANTES")),
            result.commits) == (True, 1, ["work before the first close", first.subject]), \
        result.text
