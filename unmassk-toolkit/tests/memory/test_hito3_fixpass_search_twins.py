"""#105 fix pass after Moriarty (2026-10-19), reshaped to D-147 in step 5.1:
readers are not adapted to twins (a duplicated id is an error the boot
reports, see test_hito3_fixpass_boot_twins.py). What stays here:

- m08 (Moriarty's surviving mutant): `search --id` shows the live twin
  after `remove --commit`, with commit dates fixed so the result never
  rests on git log's tie order. Green guard of the shipped 4.1 fix.
- `search --id` typed in lowercase shows the same hanging notes (not a
  twin case: ids are compared normalized).

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
