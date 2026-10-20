"""R.17 4.2: an overlap relaunch never offers to replace an I, X, Q or B.

Contract (D-164's Why, Moriarty's ABUSE 3): a Q, X, I or B never replaces
and is never replaced -- X never dies, Q is promoted, I closes by its own
protocol, B is resolved. So when a new D, M or R bounces as overlapping,
the printed relaunch proposes `--replaces <id>` only for a D, M or R
candidate; with only I, X, Q or B candidates it proposes `--replaces none`,
and pasted as printed it leaves the old note live.

Expected exits typed by hand from D-164, never read from vocabulary.TYPES.
Driven through `bin/gitmem` on a throwaway repo, read back through the real
index reader.
"""

import sys

import pytest

from .conftest import import_lib_memory_module, pm_path
from .relaunch_fidelity_support import (
    ANCHOR_ZONES,
    DESCRIPTION,
    KEYS,
    NEW_HEADLINE,
    OLD_HEADLINE,
    WHY,
    flag_values,
    gh_env,  # noqa: F401 -- pytest fixture
    gitmem,
    note_args,
    seed,
    seed_zones,
    single_relaunch,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH: subprocess.run(['gh', ...]) never resolves a file without .exe on Windows",
)

# D-164, typed by hand.
REPLACE_BY_ID = ("D", "M", "R")
CLOSES_BY_OWN_PROTOCOL = ("I", "X", "Q", "B")
# The index each closing type lives in while it is live (memory skill).
LIVE_INDEX = {"I": "INCIDENTS.md", "X": "DISCARDED.md", "Q": "QUESTIONS.md", "B": "BLOCKED.md"}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _given(note_type, anchor_id):
    """The answers each type needs to get as far as the overlap gate."""
    given = {"--description": DESCRIPTION, "--keys": KEYS}
    if note_type in ("D", "R", "X", "I"):
        given["--why"] = WHY
    if note_type in ("R", "X"):
        given["--origin"] = anchor_id
    if note_type in ("M", "R"):
        given["--stops"] = "no" if note_type == "M" else "yes"
    if note_type in ("Q", "I"):
        given["--work"] = "no"
    if note_type == "B":
        given["--awaits"] = "the upstream installer release"
    return given


def _anchor(repo, env):
    seed_zones(repo)
    return seed(
        repo, env, "D", "an unrelated anchor decision",
        {"--description": "anchor", "--why": "anchor", "--keys": ("anchornote",)},
        zones=ANCHOR_ZONES,
    )


def _bounce(repo, env, new_type, anchor_id):
    rc, out = gitmem(note_args(new_type, NEW_HEADLINE, _given(new_type, anchor_id)), repo, env)
    assert rc != 0, f"the new {new_type} should bounce as overlapping: {out}"
    assert "esto pisa a algo" in out, f"expected the overlap rejection: {out}"
    return out, single_relaunch(out)


def _live_ids(indexes, repo, index_name):
    return [line.id for line in indexes.read(index_name, pm_path(repo))]


@pytest.mark.parametrize("old_type", CLOSES_BY_OWN_PROTOCOL)
@pytest.mark.parametrize("new_type", REPLACE_BY_ID)
class TestOnlyClosingCandidates:
    def test_should_offer_replaces_none_when_every_candidate_closes_by_its_own_protocol(
        self, tmp_repo, gh_env, new_type, old_type
    ):
        anchor_id = _anchor(tmp_repo, gh_env)
        old_id = seed(tmp_repo, gh_env, old_type, OLD_HEADLINE, _given(old_type, anchor_id))

        _out, tokens = _bounce(tmp_repo, gh_env, new_type, anchor_id)

        assert flag_values(tokens, "--replaces") == ["none"], (old_id, tokens)

    def test_should_leave_the_old_note_live_when_the_relaunch_is_pasted_as_printed(
        self, tmp_repo, gh_env, indexes, new_type, old_type
    ):
        anchor_id = _anchor(tmp_repo, gh_env)
        old_id = seed(tmp_repo, gh_env, old_type, OLD_HEADLINE, _given(old_type, anchor_id))
        _out, tokens = _bounce(tmp_repo, gh_env, new_type, anchor_id)

        rc, out = gitmem(tokens, tmp_repo, gh_env)

        assert rc == 0, f"the printed relaunch was refused: {tokens}\n{out}"
        assert old_id in _live_ids(indexes, tmp_repo, LIVE_INDEX[old_type]), out
        assert old_id not in indexes.archived_ids(pm_path(tmp_repo)), out


@pytest.mark.parametrize("closing_type", ("I", "X"))
class TestMixedCandidates:
    def test_should_offer_the_replaceable_candidate_when_a_closing_one_is_listed_first(
        self, tmp_repo, gh_env, closing_type
    ):
        anchor_id = _anchor(tmp_repo, gh_env)
        old_d = seed(tmp_repo, gh_env, "D", OLD_HEADLINE, _given("D", anchor_id))
        closing_id = seed(
            tmp_repo, gh_env, closing_type, OLD_HEADLINE, {**_given(closing_type, anchor_id), "--replaces": "none"}
        )

        out, tokens = _bounce(tmp_repo, gh_env, "D", anchor_id)

        listing = out.split("Relanza:", 1)[0]
        assert listing.index(closing_id) < listing.index(old_d), (
            f"precondition: the {closing_type} must be listed before the D: {out}"
        )
        assert flag_values(tokens, "--replaces") == [old_d], tokens
