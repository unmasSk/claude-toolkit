"""#105 step 5.1, D-147 (2026-10-19): a duplicated note id is an error the
boot reports loudly, never a state the readers support.

The boot's duplicate check counts every id across the live indexes AND
ARCHIVED.md. Whenever one id appears more than once it does not say
"✓  no duplicate IDs": it names the id and lists each note under it, one
line per note with its commit, its zones and its headline, so the owner
can pick the one to fix with `gitmem remove <id> --commit <sha>`.

Twins are made the way they happen (two clones + union merge,
hito3_twins_support.make_twins); the expected commits, zones and headlines
are the ones this test wrote. Reader: `bin/memory/boot.py` run as a
process, the report read from the file the session reads.
"""

from pathlib import Path

import pytest

from .boot_hook_gh_stub import gh_stub  # noqa: F401  (a fixture)
from .boot_hook_harness import POSIX_ONLY
from .conftest import run_memory_script, seed_zones_json
from .hito3_twins_support import (
    NEWER_DATE,
    OLDER_DATE,
    gitmem,
    make_twins,
    seed,
)

ZONES_HERE = ("install", "hooks")
ZONES_THERE = ("billing", "payroll")
ALL_ZONES = ["install", "hooks", "billing", "payroll"]
HEADLINES = {
    "M": ("installer keeps a copy of user hooks", "payroll exports carry a run key"),
    "I": ("installer clobbered a user hook", "payroll export doubled every salary"),
}
REMOVE_EXTRA = {"M": [], "I": ["--restriction", "no"]}
HEALTHY = "✓  no duplicate IDs"
SHORT_SHA = 7


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _checks_block(repo, gh):
    """The CHECKS block of the boot report: from its title to the next blank line."""
    gh.configure(issues={})
    rc, out, err = run_memory_script("boot.py", [], cwd=repo, env=gh.env())
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    report = (Path(repo) / ".claude" / ".unmassk" / "boot-latest.txt").read_text(encoding="utf-8")
    lines = report.splitlines()
    assert "CHECKS" in lines, f"setup: the boot report has no CHECKS block:\n{report}"
    block = []
    for line in lines[lines.index("CHECKS") + 1:]:
        if not line.strip():
            break
        block.append(line)
    return "\n".join(block)


def _twins(repo, tmp_path, env, note_type):
    """Two notes under one id, `here` older, `there` newer. Returns
    (id, {"here": (sha, zones, headline), "there": (sha, zones, headline)})."""
    here_headline, there_headline = HEADLINES[note_type]
    note_id, shas = make_twins(
        repo, tmp_path, env, note_type,
        (ZONES_HERE, here_headline, OLDER_DATE), (ZONES_THERE, there_headline, NEWER_DATE),
        ALL_ZONES,
    )
    return note_id, {
        "here": (shas["here"], ZONES_HERE, here_headline),
        "there": (shas["there"], ZONES_THERE, there_headline),
    }


def _remove(repo, env, note_type, note_id, *extra):
    rc, _out, combined = gitmem(
        ["remove", note_id, "superseded by the guard", *REMOVE_EXTRA[note_type], *extra], repo, env,
    )
    assert rc == 0, f"setup: remove failed: {combined}"


def _assert_loud_and_listed(checks, note_id, notes):
    assert HEALTHY not in checks, (
        f"{note_id} is written twice but the boot says it is healthy:\n{checks}"
    )
    assert any(note_id in line and "duplicate" in line.lower() for line in checks.splitlines()), (
        f"the duplicate check must name {note_id}:\n{checks}"
    )
    for sha, zones, headline in notes:
        rows = [line for line in checks.splitlines() if sha[:SHORT_SHA] in line]
        assert len(rows) == 1, (
            f"the note of commit {sha[:SHORT_SHA]} ({headline!r}) must be listed on one line:\n{checks}"
        )
        missing = [part for part in (*zones, headline) if part not in rows[0]]
        assert not missing, (
            f"the line of commit {sha[:SHORT_SHA]} must carry its zones and headline, "
            f"missing {missing!r}: {rows[0]!r}"
        )


@POSIX_ONLY
class TestBootAlertsOnEveryDuplicatedId:
    @pytest.mark.parametrize("note_type", ("M", "I"))
    def test_should_alert_and_list_both_notes_when_two_live_notes_share_the_id(
        self, tmp_repo, tmp_path, fake_home, gh_stub, note_type  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, note_type)

        checks = _checks_block(tmp_repo, gh_stub)

        _assert_loud_and_listed(checks, note_id, (notes["here"], notes["there"]))

    @pytest.mark.parametrize("note_type", ("M", "I"))
    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_alert_and_list_both_notes_when_one_twin_is_live_and_the_other_archived(
        self, tmp_repo, tmp_path, fake_home, gh_stub, note_type, archived_is  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, note_type)
        archived = notes["there"] if archived_is == "newer" else notes["here"]
        _remove(tmp_repo, fake_home, note_type, note_id, "--commit", archived[0])

        checks = _checks_block(tmp_repo, gh_stub)

        _assert_loud_and_listed(checks, note_id, (notes["here"], notes["there"]))

    def test_should_alert_and_list_both_notes_when_both_twins_are_archived(
        self, tmp_repo, tmp_path, fake_home, gh_stub  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, "M")
        _remove(tmp_repo, fake_home, "M", note_id, "--commit", notes["there"][0])
        _remove(tmp_repo, fake_home, "M", note_id)

        checks = _checks_block(tmp_repo, gh_stub)

        _assert_loud_and_listed(checks, note_id, (notes["here"], notes["there"]))


@POSIX_ONLY
def test_should_stay_healthy_when_notes_were_removed_and_replaced_without_any_twin(
    tmp_repo, fake_home, gh_stub  # noqa: F811
):
    """Guard (green on purpose): a fix that reads ARCHIVED.md must not count a
    note archived by `remove` or `--replaces` as a second copy of its id."""
    seed_zones_json(tmp_repo, ALL_ZONES)
    memo, _ = seed(tmp_repo, fake_home, "M", ZONES_HERE, "installer keeps a copy of user hooks")
    old_wall, _ = seed(tmp_repo, fake_home, "R", ZONES_HERE, "never wipe the plugin cache")
    seed(tmp_repo, fake_home, "R", ZONES_HERE, "wipe the plugin cache only on install",
         ["--description", "the wall narrowed", "--why", "stale hooks", "--stops", "yes",
          "--origin", "none", "--replaces", old_wall])
    _remove(tmp_repo, fake_home, "M", memo)

    checks = _checks_block(tmp_repo, gh_stub)

    assert HEALTHY in checks, f"no id is written twice, the boot must say so:\n{checks}"
