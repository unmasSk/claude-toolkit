"""R.17 4.2: a wall born from the incident it closes is not offered to replace it.

Contract (D-164; remove.py's own refusal: the wall is born from the incident,
`Origin:`, it never replaces it): when `gitmem remove <I> --restriction new`
bounces because the new wall resembles the very incident being closed, the
relaunch pasted as printed closes the incident and saves the wall born from
it. Moriarty's ABUSE 2: the relaunch said `--replaces <the incident>`, which
remove itself refuses, with no way out printed.

Driven through `bin/gitmem` on a throwaway repo; read back through the real
index reader and plain git.
"""

import pytest

from .conftest import import_lib_memory_module, pm_path
from .relaunch_fidelity_support import (
    flag_values,
    gitmem,
    relaunch_lines,
    saved_fields,
    seed,
    seed_zones,
    tokens_of,
)

ZONES = ("memory", "cache")
INCIDENT = "index write lost on crash"
INCIDENT_WHY = "no fsync before rename"
WALL = "index write lost on crash without fsync"
REASON = "fixed with fsync"


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _follow_the_printed_way(repo):
    """Runs the remove, then pastes each printed relaunch as is, at most twice.

    Returns the incident id, the last return code and every relaunch printed.
    """
    seed_zones(repo)
    incident = seed(repo, None, "I", INCIDENT, {
        "--description": "index write lost on crash mid rename", "--why": INCIDENT_WHY, "--work": "no",
    }, zones=ZONES)
    args = ["remove", incident, REASON, "--restriction", "new", "--restriction-text", WALL, "--why", INCIDENT_WHY]
    printed = []
    rc, out = gitmem(args, repo, None)
    for _step in range(2):
        lines = relaunch_lines(out, prefix="gitmem remove ") if rc != 0 and "Relanza:" in out else []
        if not lines:
            break
        printed.append(tokens_of(lines[0]))
        rc, out = gitmem(printed[-1], repo, None)
    return incident, rc, out, printed


class TestFenceRelaunchNeverReplacesItsOwnIncident:
    def test_should_never_print_a_relaunch_that_replaces_the_incident_being_closed(self, tmp_repo):
        incident, _rc, _out, printed = _follow_the_printed_way(tmp_repo)

        assert [t for t in printed if flag_values(t, "--replaces") == [incident]] == [], printed

    def test_should_close_the_incident_and_save_the_wall_when_the_printed_way_is_followed(
        self, tmp_repo, indexes
    ):
        incident, rc, out, printed = _follow_the_printed_way(tmp_repo)

        assert rc == 0, f"the printed way ended refused: {printed}\n{out}"
        pm = pm_path(tmp_repo)
        assert incident in indexes.archived_ids(pm)
        walls = [line.id for line in indexes.read("RESTRICTIONS.md", pm)]
        assert len(walls) == 1, walls
        assert saved_fields(tmp_repo, walls[0])["Origin"] == incident
