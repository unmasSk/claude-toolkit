"""Red contract, #105 step 1.1 (D-145): an id shared by two live notes.

remove, replace (--replaces) and promote (--promotes) refuse it, list each
note with its commit and headline, and touch nothing; `remove --commit
<sha>` archives exactly that note; a successful remove says how many notes
it archived.

The duplicate is made the way it happens in real use: two clones each
write the next id with `gitmem note`, then a merge keeps both index lines.
Everything runs through `bin/gitmem` against a throwaway repo, with HOME
pointed at a throwaway folder.
"""

import re

import pytest

from .conftest import (
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

ZONES = ("billing", "payroll")
HEADLINE_MAIN = "invoices are rounded half up before the ledger export"
HEADLINE_BRANCH = "vacation balances reset on the first working morning"
REASON = "no longer relevant after the ledger rewrite"

_SAVED_ID_RE = re.compile(r"([A-Z]-\d+)\s+guardada")


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _gitmem(args, cwd, env):
    rc, out, err = run_gitmem_script(args, cwd=cwd, env=env)
    return rc, out, err, out + err


def _git_ok(args, cwd):
    rc, out, err = run_git(args, cwd)
    assert rc == 0, f"git {args} failed in the test setup: {err}"
    return out


def _seed(repo, env, note_type, headline, extra=()):
    args = ["note", note_type, "--zones", *ZONES, headline, *extra]
    rc, out, err, _ = _gitmem(with_searched(args), repo, env)
    assert rc == 0, f"seeding {note_type} failed: stdout={out!r} stderr={err!r}"
    match = _SAVED_ID_RE.search(out)
    assert match, f"no saved id in the seed output: {out!r}"
    sha = _git_ok(["rev-parse", "HEAD"], repo)
    subject = _git_ok(["log", "-1", "--format=%s", sha], repo)
    assert headline in subject, f"HEAD is not the note commit: {subject!r}"
    return match.group(1), sha


def _seed_duplicate(repo, tmp_path, env, indexes, note_type, extra):
    """Two live index lines with the same id, each from its own commit.

    Returns (id, {headline: sha}).
    """
    seed_zones_json(repo, ZONES)
    _seed(repo, env, note_type, "base entry so the index file is tracked", extra)

    # A clone, not a worktree: gitmem does not run inside a worktree today.
    other = str(tmp_path / "other")
    _git_ok(["clone", "-q", repo, other], str(tmp_path))
    seed_zones_json(other, ZONES)

    id_main, sha_main = _seed(repo, env, note_type, HEADLINE_MAIN, extra)
    id_branch, sha_branch = _seed(other, env, note_type, HEADLINE_BRANCH, extra)
    assert id_main == id_branch, (
        f"setup did not produce a duplicate: {id_main} vs {id_branch}"
    )

    attributes = tmp_path / "repo" / ".git" / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text("*.md merge=union\n", encoding="utf-8")
    _git_ok(["fetch", "-q", other, "HEAD"], repo)
    _git_ok(["merge", "--no-edit", "FETCH_HEAD"], repo)

    index_name = {"M": "MEMOS.md", "Q": "QUESTIONS.md"}[note_type]
    live = [line for line in indexes.read(index_name, pm_path(repo)) if line.id == id_main]
    assert sorted(line.headline for line in live) == sorted([HEADLINE_MAIN, HEADLINE_BRANCH]), (
        f"setup: the merge did not leave both lines live: {live!r}"
    )
    return id_main, {HEADLINE_MAIN: sha_main, HEADLINE_BRANCH: sha_branch}


def _snapshot(repo):
    pm = pm_path(repo)
    files = {p.name: p.read_bytes() for p in sorted(pm.glob("*.md"))}
    head = _git_ok(["rev-parse", "HEAD"], repo)
    status = _git_ok(["status", "--porcelain"], repo)
    return files, head, status


def _assert_nothing_touched(repo, before):
    files_before, head_before, status_before = before
    files_after, head_after, status_after = _snapshot(repo)
    assert head_after == head_before, "a refused command made a commit"
    assert status_after == status_before, f"a refused command left changes: {status_after!r}"
    for name, content in files_before.items():
        assert files_after.get(name) == content, f"a refused command changed {name}"
    assert set(files_after) == set(files_before), "a refused command created an index file"


def _assert_lists_both_candidates(combined, shas):
    for headline, sha in shas.items():
        assert headline in combined, f"the refusal does not list {headline!r}: {combined!r}"
        assert sha[:7] in combined, f"the refusal does not give the commit {sha[:7]}: {combined!r}"


@pytest.fixture
def memo_duplicate(tmp_repo, tmp_path, fake_home, indexes):
    note_id, shas = _seed_duplicate(
        tmp_repo, tmp_path, fake_home, indexes, "M",
        ["--description", "seeded memo for the duplicate-id contract", "--stops", "no"],
    )
    return note_id, shas


class TestRemoveRefusesADuplicatedId:
    def test_should_change_nothing_and_list_both_notes_when_remove_id_is_duplicated(
        self, tmp_repo, fake_home, memo_duplicate
    ):
        note_id, shas = memo_duplicate
        before = _snapshot(tmp_repo)

        rc, _out, _err, combined = _gitmem(["remove", note_id, REASON], tmp_repo, fake_home)

        assert rc != 0, f"a duplicated id must be refused: {combined!r}"
        assert "Traceback" not in combined
        _assert_lists_both_candidates(combined, shas)
        assert "--commit" in combined, f"the refusal must say to pick one with --commit: {combined!r}"
        _assert_nothing_touched(tmp_repo, before)


class TestRemoveCommitPicksExactlyOneNote:
    @pytest.mark.parametrize("picked,kept", [
        (HEADLINE_BRANCH, HEADLINE_MAIN),
        (HEADLINE_MAIN, HEADLINE_BRANCH),
    ])
    def test_should_archive_only_the_picked_note_when_remove_gets_commit_sha(
        self, tmp_repo, fake_home, memo_duplicate, indexes, picked, kept
    ):
        note_id, shas = memo_duplicate
        head_before = _git_ok(["rev-parse", "HEAD"], tmp_repo)

        rc, _out, _err, combined = _gitmem(
            ["remove", note_id, REASON, "--commit", shas[picked]], tmp_repo, fake_home
        )

        assert rc == 0, combined
        pm = pm_path(tmp_repo)
        live = [line.headline for line in indexes.read("MEMOS.md", pm) if line.id == note_id]
        assert live == [kept], f"only the other note must stay live: {live!r}"
        archived = [a for a in indexes.read_archive(pm) if a.id == note_id]
        assert [(a.headline, a.destination, a.destination_detail) for a in archived] == [
            (picked, "closed", REASON)
        ], f"exactly the picked note must be archived: {archived!r}"
        commits = _git_ok(["rev-list", "--count", f"{head_before}..HEAD"], tmp_repo)
        assert commits == "1", f"one remove is one commit, got {commits}"

    def test_should_refuse_and_change_nothing_when_commit_sha_matches_neither_note(
        self, tmp_repo, fake_home, memo_duplicate
    ):
        note_id, _shas = memo_duplicate
        unrelated_sha = _git_ok(["rev-list", "--max-parents=0", "HEAD"], tmp_repo)
        before = _snapshot(tmp_repo)

        rc, _out, _err, combined = _gitmem(
            ["remove", note_id, REASON, "--commit", unrelated_sha], tmp_repo, fake_home
        )

        assert rc == 1, f"a sha that is not one of the notes must be a rejection: {combined!r}"
        assert "unrecognized arguments" not in combined
        assert "Traceback" not in combined
        _assert_nothing_touched(tmp_repo, before)


class TestRemoveSaysHowManyItArchived:
    def test_should_report_one_archived_note_when_remove_succeeds(
        self, tmp_repo, fake_home, indexes
    ):
        seed_zones_json(tmp_repo, ZONES)
        note_id, _sha = _seed(
            tmp_repo, fake_home, "M", HEADLINE_MAIN,
            ["--description", "seeded memo for the count contract", "--stops", "no"],
        )

        archive_before = len(indexes.read_archive(pm_path(tmp_repo)))

        rc, out, _err, combined = _gitmem(["remove", note_id, REASON], tmp_repo, fake_home)

        assert rc == 0, combined
        archive_after = indexes.read_archive(pm_path(tmp_repo))
        assert [a.id for a in archive_after[archive_before:]] == [note_id], (
            f"setup: remove must add exactly one ARCHIVED.md line for {note_id}"
        )
        said = re.search(r"notas archivadas: (\d+)", out)
        assert said, f"a successful remove must say how many notes it archived: {out!r}"
        assert int(said.group(1)) == len(archive_after) - archive_before, (
            f"remove said {said.group(1)}, ARCHIVED.md grew by {len(archive_after) - archive_before}: {out!r}"
        )


class TestReplaceRefusesADuplicatedTarget:
    def test_should_change_nothing_and_list_both_notes_when_replaces_target_is_duplicated(
        self, tmp_repo, fake_home, memo_duplicate
    ):
        note_id, shas = memo_duplicate
        before = _snapshot(tmp_repo)

        rc, _out, _err, combined = _gitmem(
            with_searched([
                "note", "M", "--zones", *ZONES, "overtime claims need a manager signature",
                "--description", "replacement memo", "--stops", "no", "--replaces", note_id,
            ]),
            tmp_repo, fake_home,
        )

        assert rc != 0, f"replacing a duplicated id must be refused: {combined!r}"
        assert "Traceback" not in combined
        _assert_lists_both_candidates(combined, shas)
        _assert_nothing_touched(tmp_repo, before)


class TestPromoteRefusesADuplicatedTarget:
    def test_should_change_nothing_and_list_both_questions_when_promotes_target_is_duplicated(
        self, tmp_repo, tmp_path, fake_home, indexes
    ):
        question_id, shas = _seed_duplicate(
            tmp_repo, tmp_path, fake_home, indexes, "Q",
            ["--description", "seeded question for the duplicate-id contract", "--work", "no"],
        )
        before = _snapshot(tmp_repo)

        rc, _out, _err, combined = _gitmem(
            with_searched([
                "note", "M", "--zones", *ZONES, "overtime claims need a manager signature",
                "--description", "answer memo", "--stops", "no", "--promotes", question_id,
            ]),
            tmp_repo, fake_home,
        )

        assert rc != 0, f"promoting a duplicated id must be refused: {combined!r}"
        assert "Traceback" not in combined
        _assert_lists_both_candidates(combined, shas)
        _assert_nothing_touched(tmp_repo, before)
