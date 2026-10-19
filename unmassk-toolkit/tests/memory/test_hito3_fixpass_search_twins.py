"""#105 fix pass after Moriarty (2026-10-19): `gitmem search` reads twins
(two notes under one id) per note, on every view.

- m08: `search --id` shows the live twin after `remove --commit`, with
  commit dates fixed so the result never rests on git log's tie order.
- `search --id` on an id two live notes share shows both.
- Word search after `remove --commit`: the live twin reads live, and the
  hit marker sits on the note that holds the word.
- `search <zone> --chain`: the live twin is never labelled closed.
- Decision twins (clusters) after `remove --commit`.
- `search --id` typed in lowercase shows the same hanging notes.

Expected side: the index files after the write and the headlines this
file wrote; readers: the commands a person runs.
"""

import pytest

from .conftest import import_lib_memory_module, seed_zones_json
from .test_hito3_round_trip import _assert_id_search_matches, _written_state
from .hito3_twins_support import (
    NEWER_DATE,
    OLDER_DATE,
    archive_lines,
    gitmem,
    live_lines,
    make_twins,
    seed,
)

ZONES = ("install", "hooks")
ALL_ZONES = ["install", "hooks"]
ALPHA = "alpha memo about plugin caches"
BETA = "beta memo about hook folders"
HIT = "›"
ARCHIVED_WORD = "archivada"
CLOSED_WORD = "cerrada"


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _search(repo, env, *args):
    rc, out, combined = gitmem(["search", *args], repo, env)
    assert rc == 0, combined
    return out


def _lines_with(out, text):
    return [line for line in out.splitlines() if text in line]


def _twins_one_archived(repo, tmp_path, env, indexes, note_type, archived_is):
    """ALPHA (older) and BETA (newer) under one id; the `archived_is` one
    ("newer"/"older") archived with `remove --commit`. Returns (id, live, archived)."""
    note_id, shas = make_twins(repo, tmp_path, env, note_type,
                               (ZONES, ALPHA, OLDER_DATE), (ZONES, BETA, NEWER_DATE), ALL_ZONES)
    sha = shas["there"] if archived_is == "newer" else shas["here"]
    rc, _out, combined = gitmem(["remove", note_id, "superseded", "--commit", sha], repo, env)
    assert rc == 0, combined
    live = [line.headline for line in live_lines(indexes, repo, note_type, note_id)]
    archived = [line.headline for line in archive_lines(indexes, repo, note_id)]
    assert len(live) == 1 and len(archived) == 1, f"setup: {live!r} {archived!r}"
    return note_id, live[0], archived[0]


class TestSearchByIdAfterRemoveCommit:
    """m08: `report.build_note` must pick the live twin; with the archived
    twin newer, `query.by_id` alone returns the archived one."""

    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_show_the_live_twin_as_live_when_search_by_id_after_remove_commit(
        self, tmp_repo, tmp_path, fake_home, indexes, archived_is
    ):
        note_id, _live, _archived = _twins_one_archived(
            tmp_repo, tmp_path, fake_home, indexes, "M", archived_is
        )

        state = _written_state(tmp_repo, indexes)

        _assert_id_search_matches(tmp_repo, fake_home, state, note_id)


class TestSearchByIdOnTwoLiveTwins:
    def test_should_show_both_notes_when_two_live_notes_share_the_id(
        self, tmp_repo, tmp_path, fake_home
    ):
        note_id, _shas = make_twins(tmp_repo, tmp_path, fake_home, "M",
                                    (ZONES, ALPHA, OLDER_DATE), (ZONES, BETA, NEWER_DATE), ALL_ZONES)

        out = _search(tmp_repo, fake_home, "--id", note_id)

        missing = [h for h in (ALPHA, BETA) if h not in out]
        assert not missing, f"search --id {note_id} hides a live note sharing the id: {missing!r}\n{out}"


class TestWordSearchAfterRemoveCommit:
    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_show_the_live_twin_as_live_when_its_word_is_searched(
        self, tmp_repo, tmp_path, fake_home, indexes, archived_is
    ):
        _id, live, _archived = _twins_one_archived(
            tmp_repo, tmp_path, fake_home, indexes, "M", archived_is
        )
        word = live.split()[0]  # "alpha" or "beta": only in that twin

        out = _search(tmp_repo, fake_home, word)

        shown = _lines_with(out, live)
        assert shown and all(ARCHIVED_WORD not in line for line in shown), (
            f"`search {word}` must show {live!r} as live:\n{out}"
        )

    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_not_mark_the_live_twin_as_the_hit_when_only_the_archived_twin_holds_the_word(
        self, tmp_repo, tmp_path, fake_home, indexes, archived_is
    ):
        _id, live, archived = _twins_one_archived(
            tmp_repo, tmp_path, fake_home, indexes, "M", archived_is
        )
        word = archived.split()[0]

        out = _search(tmp_repo, fake_home, word, "--todo")

        marked_live = [line for line in _lines_with(out, live) if HIT in line]
        assert not marked_live, (
            f"`search {word} --todo` marks {live!r} as the hit, but only {archived!r} holds the word:\n{out}"
        )
        assert any(HIT in line for line in _lines_with(out, archived)), (
            f"`search {word} --todo` must mark the note that holds the word, {archived!r}:\n{out}"
        )


class TestChainAfterRemoveCommit:
    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_not_label_the_live_twin_closed_when_search_zone_chain(
        self, tmp_repo, tmp_path, fake_home, indexes, archived_is
    ):
        _id, live, _archived = _twins_one_archived(
            tmp_repo, tmp_path, fake_home, indexes, "M", archived_is
        )

        out = _search(tmp_repo, fake_home, ZONES[0], "--chain")

        shown = _lines_with(out, live)
        assert shown, f"`search {ZONES[0]} --chain` hides the live note {live!r}:\n{out}"
        assert all(CLOSED_WORD not in line for line in shown), (
            f"`search {ZONES[0]} --chain` labels the live note {live!r} closed:\n{out}"
        )


class TestDecisionTwinsInTheZoneReport:
    """Decisions go through clusters.group, which reads archived state per id."""

    def test_should_list_both_decisions_when_two_live_decisions_share_the_id(
        self, tmp_repo, tmp_path, fake_home
    ):
        make_twins(tmp_repo, tmp_path, fake_home, "D",
                   (ZONES, ALPHA, OLDER_DATE), (ZONES, BETA, NEWER_DATE), ALL_ZONES)

        out = _search(tmp_repo, fake_home, ZONES[0])

        missing = [h for h in (ALPHA, BETA) if h not in out]
        assert not missing, f"`search {ZONES[0]}` collapses decision twins: {missing!r}\n{out}"

    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_show_the_live_decision_twin_as_live_when_search_zone_todo_after_remove_commit(
        self, tmp_repo, tmp_path, fake_home, indexes, archived_is
    ):
        _id, live, archived = _twins_one_archived(
            tmp_repo, tmp_path, fake_home, indexes, "D", archived_is
        )

        out = _search(tmp_repo, fake_home, ZONES[0], "--todo")

        live_shown = _lines_with(out, live)
        assert live_shown and all(ARCHIVED_WORD not in line for line in live_shown), (
            f"`search {ZONES[0]} --todo` must show the decision {live!r} as live:\n{out}"
        )
        assert any(ARCHIVED_WORD in line for line in _lines_with(out, archived)), (
            f"`search {ZONES[0]} --todo` must show the decision {archived!r} as archived:\n{out}"
        )


class TestSearchByIdCase:
    def test_should_show_the_same_hanging_alternative_when_the_id_is_typed_in_lowercase(
        self, tmp_repo, fake_home
    ):
        seed_zones_json(tmp_repo, ALL_ZONES)
        alternative = "keep the cache across sessions"
        decision, _sha = seed(tmp_repo, fake_home, "D", ZONES, "wipe the plugin cache on install",
                              ["--description", "the installer wipes the cache", "--why", "stale hooks",
                               "--discard", alternative, "stale hooks survive"])
        upper = _search(tmp_repo, fake_home, "--id", decision)
        assert alternative in upper, f"setup: search --id {decision} must show its alternative:\n{upper}"

        lower = _search(tmp_repo, fake_home, "--id", decision.lower())

        assert alternative in lower, (
            f"search --id {decision.lower()} finds the note but not what hangs from it:\n{lower}"
        )
