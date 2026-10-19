"""#105 fix pass after Moriarty (2026-10-19): what `gitmem remove` writes
when an id is duplicated, and the relaunches it prints.

- B2: twins with the same headline in different zones; `--commit <sha>`
  archives the note of that commit, not the other one.
- B3: a wall born from a duplicated incident whose other twin is already
  closed lives in the zones of the incident still open.
- `--replaces` naming the incident being closed is refused before any write.
- The long-headline relaunch keeps `--replaces` and `--commit`.
- m02: `indexes.remove(only=)` drops one byte-identical line, not all.

Expected values come from what each test wrote (zones, headlines, shas),
never from the code under test.
"""

import pytest

from .conftest import import_lib_memory_module, seed_zones_json
from .hito3_twins_support import (
    NEWER_DATE,
    OLDER_DATE,
    SAVED_ID_RE,
    archive_lines,
    flag_value,
    gitmem,
    live_lines,
    make_twins,
    pasted_words,
    relaunch_commands,
    seed,
    snapshot,
)

ZONES_A = ("billing", "payroll")
ZONES_B = ("reports", "ledger")
ZONES_INSTALL = ("install", "hooks")
ALL_ZONES = ["billing", "payroll", "reports", "ledger", "install", "hooks"]
SAME_HEADLINE = "export runs at midnight utc"
REASON = "billing export moved"
WALL_TEXT = "installer never overwrites a hook it did not write"
WALL_WHY = "user hooks were lost without a trace"
TOO_LONG = "F" * 96
SHORT_WALL = "installer keeps hooks it did not write"


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _zones(line):
    return (line.zone1, line.zone2)


class TestSameHeadlineTwinsInDifferentZones:
    """B2: notes_duplicate pairs index lines to commits by headline only."""

    @pytest.mark.parametrize("picked", ("here", "there"))
    @pytest.mark.parametrize("here_date,there_date", [
        (OLDER_DATE, NEWER_DATE), (NEWER_DATE, OLDER_DATE),
    ], ids=("here-older", "here-newer"))
    def test_should_archive_the_note_of_the_given_commit_when_twins_share_a_headline(
        self, tmp_repo, tmp_path, fake_home, indexes, picked, here_date, there_date
    ):
        zones = {"here": ZONES_A, "there": ZONES_B}
        note_id, shas = make_twins(
            tmp_repo, tmp_path, fake_home, "M",
            (ZONES_A, SAME_HEADLINE, here_date), (ZONES_B, SAME_HEADLINE, there_date), ALL_ZONES,
        )
        kept = "there" if picked == "here" else "here"

        rc, _out, combined = gitmem(["remove", note_id, REASON, "--commit", shas[picked]],
                                    tmp_repo, fake_home)

        assert rc == 0, combined
        archived = archive_lines(indexes, tmp_repo, note_id)
        assert [_zones(a) for a in archived] == [zones[picked]], (
            f"--commit {shas[picked][:10]} wrote {zones[picked]}; ARCHIVED.md has "
            f"{[_zones(a) for a in archived]}"
        )
        live = live_lines(indexes, tmp_repo, "M", note_id)
        assert [_zones(line) for line in live if line.headline == SAME_HEADLINE] == [zones[kept]]


class TestWallFromDuplicatedIncidentAfterOneTwinClosed:
    """B3: the wall takes the zones of the incident it closes, not of
    whichever twin git log returns first."""

    @pytest.mark.parametrize("closed_first", ("newer", "older"))
    def test_should_birth_the_wall_in_the_open_incident_zones_when_its_twin_was_closed_before(
        self, tmp_repo, tmp_path, fake_home, indexes, closed_first
    ):
        install = (ZONES_INSTALL, "installer clobbered a user hook", OLDER_DATE)
        payroll = (ZONES_A, "payroll export doubled every salary", NEWER_DATE)
        note_id, shas = make_twins(tmp_repo, tmp_path, fake_home, "I", install, payroll, ALL_ZONES)
        first = "there" if closed_first == "newer" else "here"
        rc, _out, combined = gitmem(
            ["remove", note_id, "first twin fixed", "--restriction", "no", "--commit", shas[first]],
            tmp_repo, fake_home,
        )
        assert rc == 0, f"setup: closing one twin failed: {combined}"
        still_open = live_lines(indexes, tmp_repo, "I", note_id)
        assert len(still_open) == 1, f"setup: one twin must stay open: {still_open!r}"

        rc, out, combined = gitmem(
            ["remove", note_id, "second twin fixed", "--restriction", "new",
             "--restriction-text", WALL_TEXT, "--why", WALL_WHY],
            tmp_repo, fake_home,
        )

        assert rc == 0, combined
        wall_ids = [i for i in SAVED_ID_RE.findall(out) if i.startswith("R-")]
        assert len(wall_ids) == 1, f"the new wall's id must be reported once: {out!r}"
        wall = live_lines(indexes, tmp_repo, "R", wall_ids[0])
        assert [_zones(w) for w in wall] == [_zones(still_open[0])], (
            f"the wall must live where the incident it closes lived ({_zones(still_open[0])}), "
            f"got {[_zones(w) for w in wall]}"
        )


class TestReplacesTheIncidentItself:
    def test_should_refuse_and_touch_nothing_when_replaces_names_the_incident_being_closed(
        self, tmp_repo, fake_home, indexes
    ):
        seed_zones_json(tmp_repo, ALL_ZONES)
        incident, _sha = seed(tmp_repo, fake_home, "I", ZONES_INSTALL, "installer clobbered a user hook")
        before = snapshot(tmp_repo)

        rc, _out, combined = gitmem(
            ["remove", incident, "fixed by the guard", "--restriction", "new",
             "--restriction-text", WALL_TEXT, "--why", WALL_WHY, "--replaces", incident],
            tmp_repo, fake_home,
        )

        assert rc == 1, f"--replaces <the incident itself> must be refused: {combined!r}"
        assert snapshot(tmp_repo) == before, (
            f"a refused remove must leave the incident open and nothing written:\n{combined}"
        )
        assert [line.headline for line in live_lines(indexes, tmp_repo, "I", incident)] == [
            "installer clobbered a user hook"
        ]


class TestHeadlineRejectionRelaunchKeepsEveryFlag:
    """8b3d: `_headline_rejection_for_remove` rebuilt the command by hand and
    dropped --replaces and --commit."""

    def _headline_relaunch(self, combined, incident):
        found = [pasted_words(c) for c in relaunch_commands(combined)]
        found = [w for w in found if w[:3] == ["gitmem", "remove", incident]]
        assert len(found) == 1, f"one `gitmem remove {incident}` relaunch expected:\n{combined}"
        return [SHORT_WALL if w.startswith("<titular") else w for w in found[0]]

    def test_should_carry_replaces_and_retire_the_old_wall_when_the_headline_relaunch_is_pasted(
        self, tmp_repo, fake_home, indexes
    ):
        seed_zones_json(tmp_repo, ALL_ZONES)
        old_wall, _ = seed(tmp_repo, fake_home, "R", ZONES_INSTALL, "never wipe the plugin cache")
        incident, _ = seed(tmp_repo, fake_home, "I", ZONES_INSTALL, "installer clobbered a user hook")
        rc, _out, combined = gitmem(
            ["remove", incident, "fixed", "--restriction", "new", "--restriction-text", TOO_LONG,
             "--why", WALL_WHY, "--replaces", old_wall],
            tmp_repo, fake_home,
        )
        assert rc == 1, f"a 96-character wall headline must be refused: {combined!r}"
        words = self._headline_relaunch(combined, incident)
        assert flag_value(words, "--replaces") == old_wall, f"the relaunch dropped --replaces: {words!r}"

        rc, out, combined = gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}"
        new_wall = [i for i in SAVED_ID_RE.findall(out) if i.startswith("R-")]
        assert [(a.destination, a.destination_detail) for a in archive_lines(indexes, tmp_repo, old_wall)] == [
            ("replaced", new_wall[0])
        ]

    def test_should_carry_commit_and_close_the_picked_twin_when_the_headline_relaunch_is_pasted(
        self, tmp_repo, tmp_path, fake_home, indexes
    ):
        install = (ZONES_INSTALL, "installer clobbered a user hook", OLDER_DATE)
        payroll = (ZONES_A, "payroll export doubled every salary", NEWER_DATE)
        incident, shas = make_twins(tmp_repo, tmp_path, fake_home, "I", install, payroll, ALL_ZONES)
        rc, _out, combined = gitmem(
            ["remove", incident, "fixed", "--restriction", "new", "--restriction-text", TOO_LONG,
             "--why", WALL_WHY, "--commit", shas["here"]],
            tmp_repo, fake_home,
        )
        assert rc == 1, f"a 96-character wall headline must be refused: {combined!r}"
        words = self._headline_relaunch(combined, incident)
        assert shas["here"].startswith(flag_value(words, "--commit").lower()), (
            f"the relaunch dropped --commit: {words!r}"
        )

        rc, _out, combined = gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}"
        assert [a.headline for a in archive_lines(indexes, tmp_repo, incident)] == [install[1]]


class TestIndexRemoveOnlyFirstIdenticalLine:
    """m02: with `only=`, `indexes.remove` drops the first identical line
    and keeps the second (two identical lines come from a cherry-pick)."""

    def test_should_remove_exactly_one_line_when_two_identical_lines_carry_the_id(
        self, tmp_path, indexes
    ):
        model = import_lib_memory_module("model")
        root = tmp_path / "project-memory"
        indexes.seed(root)
        twin = model.IndexLine(id="M-002", zone1="billing", zone2="payroll", headline=SAME_HEADLINE)
        other = model.IndexLine(id="M-001", zone1="billing", zone2="payroll", headline="other memo")
        for line in (twin, other, twin):
            indexes.insert(line, "MEMOS.md", root)

        removed = indexes.remove("M-002", "MEMOS.md", root, only=twin)

        assert removed == 1
        assert list(indexes.read("MEMOS.md", root)) == [other, twin]

