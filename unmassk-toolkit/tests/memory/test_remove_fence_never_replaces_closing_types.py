"""R.17 4.2: the remove fence relaunch never offers to replace an I or an X.

Contract (D-164's Why, Moriarty's ABUSE 3): an I closes by its own protocol
and an X never dies. When `gitmem remove <I> --restriction new` bounces
because the new wall resembles ANOTHER live I or X in its zones, the
printed relaunch proposes `--replaces none`, and followed as printed it
closes the incident, saves the wall and leaves that other note live.

Driven through `bin/gitmem` on a throwaway repo, read back through the real
index reader.
"""

import pytest

from .conftest import import_lib_memory_module, pm_path
from .relaunch_fidelity_support import (
    flag_values,
    gitmem,
    relaunch_lines,
    seed,
    seed_zones,
    tokens_of,
)

ZONES = ("memory", "cache")
INCIDENT = "index write lost on crash"
INCIDENT_WHY = "no fsync before rename"
WALL = "index write lost on crash without fsync"
REASON = "fixed with fsync"
OTHER_HEADLINE = "index write lost on crash without fsync again"
# The index each closing type lives in while it is live (memory skill).
LIVE_INDEX = {"I": "INCIDENTS.md", "X": "DISCARDED.md"}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _seed_other(repo, other_type):
    given = {"--description": "index write lost on crash mid rename", "--why": INCIDENT_WHY, "--replaces": "none"}
    if other_type == "I":
        given["--work"] = "no"
    return seed(repo, None, other_type, OTHER_HEADLINE, given, zones=ZONES)


def _follow_the_printed_way(repo, other_type):
    """Runs the remove, then pastes each printed relaunch as is, at most twice."""
    seed_zones(repo)
    incident = seed(repo, None, "I", INCIDENT, {
        "--description": "index write lost on crash mid rename", "--why": INCIDENT_WHY, "--work": "no",
    }, zones=ZONES)
    other = _seed_other(repo, other_type)
    args = ["remove", incident, REASON, "--restriction", "new", "--restriction-text", WALL, "--why", INCIDENT_WHY]
    printed = []
    rc, out = gitmem(args, repo, None)
    first_out = out
    for _step in range(2):
        lines = relaunch_lines(out, prefix="gitmem remove ") if rc != 0 and "Relanza:" in out else []
        if not lines:
            break
        printed.append(tokens_of(lines[0]))
        rc, out = gitmem(printed[-1], repo, None)
    return incident, other, first_out, rc, out, printed


@pytest.mark.parametrize("other_type", ("I", "X"))
class TestFenceNeverReplacesAClosingType:
    def test_should_bounce_as_overlapping_the_other_note(self, tmp_repo, other_type):
        _incident, other, first_out, _rc, _out, _printed = _follow_the_printed_way(tmp_repo, other_type)

        assert "esto pisa a algo" in first_out and other in first_out, (
            f"precondition: the wall must overlap the other {other_type}: {first_out}"
        )

    def test_should_never_print_a_relaunch_that_replaces_the_other_note(self, tmp_repo, other_type):
        _incident, other, _first, _rc, _out, printed = _follow_the_printed_way(tmp_repo, other_type)

        assert [t for t in printed if flag_values(t, "--replaces") == [other]] == [], printed
        assert printed and flag_values(printed[0], "--replaces") == ["none"], printed

    def test_should_leave_the_other_note_live_when_the_printed_way_is_followed(
        self, tmp_repo, indexes, other_type
    ):
        incident, other, _first, rc, out, printed = _follow_the_printed_way(tmp_repo, other_type)

        assert rc == 0, f"the printed way ended refused: {printed}\n{out}"
        pm = pm_path(tmp_repo)
        assert incident in indexes.archived_ids(pm)
        assert other in [line.id for line in indexes.read(LIVE_INDEX[other_type], pm)], printed
        assert other not in indexes.archived_ids(pm), printed
