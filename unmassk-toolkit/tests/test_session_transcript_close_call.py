"""Contract tests: only a `gitmem next` call makes a close this session's own.

Fix pass after Yoda (plan docs/plan/fix-close-transcript.md): a Bash call that
merely mentions "next" (`gitmem search next ...`) and whose output shows another
window's close on a line of its own is not holding that close.
"""

import pytest

from conftest import git_cmd
from session_transcript_harness import (
    commit, gitmem_next, held_close_top_level, make_repo, run,
)
from session_transcript_records_helpers import (
    SESSION_ID, assistant, human, tool_answer, tool_call, ts, write_transcript,
)


def _setup(tmp_path):
    """Previous close at 07:00; another window closed at 09:00 with the real
    `gitmem next`; this session started at 08:00. Returns (repo, other close)."""
    repo = make_repo(tmp_path)
    commit(repo, "old work", "06:00:00")
    commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    commit(repo, "work before the other close", "08:30:00")
    other = gitmem_next(repo, "close of another window", "09:00:00")
    commit(repo, "work after the other close", "09:10:00")
    return repo, other


def _transcript(tmp_path, middle):
    records = [human("PALABRA-INICIO", ts("08:00:00")),
               assistant("respuesta inicial", ts("08:00:05"))]
    records += middle
    records += [human("PALABRA-FINAL", ts("09:15:00"))]
    return write_transcript(tmp_path / f"{SESSION_ID}.jsonl", records)


def _subjects_alone(repo):
    """What `git log --format=%s -3` really prints: each subject on its own line."""
    rc, output, err = git_cmd(["log", "--format=%s", "-3"], repo)
    assert rc == 0, err
    return output


SEARCHES = pytest.mark.parametrize("command", [
    "gitmem search next && git log --format=%s -3",
    "gitmem search next --chain && git log --format=%s -3",
], ids=["search-next", "search-chain-next"])


@SEARCHES
def test_should_not_hold_a_close_seen_in_a_search_call_output(tmp_path, command):
    repo, other = _setup(tmp_path)
    output = _subjects_alone(repo)
    tool_id = "toolu_search00000000000000001"
    transcript = _transcript(tmp_path, [tool_call(command, ts("09:05:00"), tool_id),
                                        tool_answer(output, ts("09:05:01"), tool_id)])

    result = run(tmp_path, repo, transcript)

    assert (other.subject in output.splitlines(), result.commits) == (
        True, ["work after the other close"]), result.text


def test_should_hold_a_close_written_by_its_own_gitmem_next_call(tmp_path):
    repo, other = _setup(tmp_path)
    transcript = _transcript(tmp_path, held_close_top_level(
        SESSION_ID, other, ts("08:58:00"), ts("09:00:01")))

    result = run(tmp_path, repo, transcript)

    assert result.commits == ["work before the other close", other.subject,
                              "work after the other close"], result.text
