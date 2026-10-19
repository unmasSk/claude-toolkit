"""Contract tests for the close-session extractor: the window — `--since` bounds
the commits and the conversation, read right in every form or refused out loud,
and an empty window is said without stopping the close.

Plan docs/plan/fix-close-transcript.md, step 1.1 (c, d); Yoda 2026-10-19 (--since forms).
"""

import pytest

from session_transcript_harness import commit, make_repo, run, run_raw
from session_transcript_records_helpers import assistant, human, ts, write_transcript


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


# ── (c) --since bounds the commits as well as the conversation ──────────


def test_should_include_commits_after_since_when_since_predates_last_close(tmp_path,
                                                                           two_close_repo):
    result = run(tmp_path, two_close_repo, _late_transcript(tmp_path),
                 "--since", "2026-10-19T09:30:00")

    assert result.commits == ["C between the closes", "[NEXT] 🔜 close two",
                              "F just after close two", "E latest"], result.text


def test_should_exclude_commits_before_since_when_since_follows_last_close(tmp_path,
                                                                           two_close_repo):
    result = run(tmp_path, two_close_repo, _late_transcript(tmp_path),
                 "--since", "2026-10-19T11:30:00")

    assert result.commits == ["E latest"], result.text


# ── --since written with a zone or a space: right, or refused out loud ──
# Each case puts one commit and one owner message on each side of the instant
# --since names; reading the text as plain characters puts one of them on the
# wrong side.

SINCE_FORMS = [
    # 10:00+02:00 is 08:00 UTC: a text compare drops everything before 10:00.
    ("2026-10-19T10:00:00+02:00", "07:30:00", "08:30:00",
     ts("07:30:00"), ts("08:30:00")),
    # A trailing Z: a text compare drops 08:30:00 itself and 08:30:00.100.
    ("2026-10-19T08:30:00Z", "08:00:00", "08:30:00",
     ts("08:00:00"), "2026-10-19T08:30:00.100Z"),
    # A space for the T: a text compare keeps the whole day.
    ("2026-10-19 08:00", "07:00:00", "08:30:00",
     ts("07:00:00"), ts("08:30:00")),
]


@pytest.mark.parametrize("since,commit_before,commit_after,said_before,said_after",
                         SINCE_FORMS, ids=["zone-offset", "zone-z", "space"])
def test_should_read_since_right_or_refuse_it_out_loud(tmp_path, since, commit_before,
                                                       commit_after, said_before, said_after):
    repo = make_repo(tmp_path)
    commit(repo, "[NEXT] 🔜 previous session close", "05:00:00")
    commit(repo, "COMMIT-ANTES-DEL-LIMITE", commit_before)
    commit(repo, "COMMIT-DESPUES-DEL-LIMITE", commit_after)
    transcript = write_transcript(tmp_path / "s.jsonl", [
        human("DICHO-ANTES-DEL-LIMITE", said_before),
        human("DICHO-DESPUES-DEL-LIMITE", said_after)])

    rc, stderr, result = run_raw(tmp_path, repo, transcript, "--since", since)
    refused = rc != 0 and "--since" in stderr
    read_right = result is not None and (
        result.commits, len(result.user_turns_with("DICHO-DESPUES-DEL-LIMITE")),
        result.anywhere_in_conversation("DICHO-ANTES-DEL-LIMITE"),
    ) == (["COMMIT-DESPUES-DEL-LIMITE"], 1, False)

    assert refused or read_right, (rc, stderr, result and result.text)


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
                 "--since", "2026-10-19T12:10:00")

    assert (result.commits in ([], ["(none)"]), len(result.commit_notes()),
            result.stop_lines()) == (True, 1, []), result.text


def test_should_not_note_about_commits_when_the_window_has_some(tmp_path):
    repo = make_repo(tmp_path)
    commit(repo, "[DECISION][x] 🧭 earlier work", "06:00:00")
    commit(repo, "[NEXT] 🔜 previous session close", "07:00:00")
    commit(repo, "work after the close", "08:30:00")
    transcript = write_transcript(tmp_path / "s.jsonl", [human("hola", ts("08:00:00"))])

    result = run(tmp_path, repo, transcript)

    assert (result.commits, result.commit_notes(), result.stop_lines()) == \
        (["work after the close"], [], []), result.text
