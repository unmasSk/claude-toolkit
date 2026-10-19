"""#105 fix pass after Moriarty (B1, 2026-10-19): after `gitmem remove <id>
--commit <sha>` archives one of two twins, the boot report still lists the
twin that stays live.

The seam of the plan names the boot as a reader of what remove writes; the
round trip (4.1) never read it. Expected side: the live lines of the index
files after the write (`indexes.read`), never typed. Reader: `bin/memory/
boot.py` run as a process, the report read from the file the session reads.
"""

from pathlib import Path

import pytest

from .boot_hook_gh_stub import gh_stub  # noqa: F401  (a fixture)
from .boot_hook_harness import POSIX_ONLY
from .conftest import import_lib_memory_module, run_memory_script
from .hito3_twins_support import (
    NEWER_DATE,
    OLDER_DATE,
    archive_lines,
    gitmem,
    live_lines,
    make_twins,
)

ZONES_HERE = ("install", "hooks")
ZONES_THERE = ("billing", "payroll")
ALL_ZONES = ["install", "hooks", "billing", "payroll"]
HEADLINES = {
    "R": ("never wipe the plugin cache mid session", "tags rule kept until the guard ships"),
    "I": ("installer clobbered a user hook", "payroll export doubled every salary"),
    "Q": ("should the installer back up user hooks", "should payroll exports carry a run key"),
}
REMOVE_EXTRA = {"R": [], "I": ["--restriction", "no"], "Q": []}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _boot_report(repo, gh):
    gh.configure(issues={})
    rc, out, err = run_memory_script("boot.py", [], cwd=repo, env=gh.env())
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    return (Path(repo) / ".claude" / ".unmassk" / "boot-latest.txt").read_text(encoding="utf-8")


@POSIX_ONLY
@pytest.mark.parametrize("note_type", ("R", "I", "Q"))
@pytest.mark.parametrize("picked", ("newer", "older"))
def test_should_list_the_live_twin_in_the_boot_when_its_twin_was_archived_by_commit(
    tmp_repo, tmp_path, fake_home, indexes, gh_stub, note_type, picked  # noqa: F811
):
    here_headline, there_headline = HEADLINES[note_type]
    note_id, shas = make_twins(
        tmp_repo, tmp_path, fake_home, note_type,
        (ZONES_HERE, here_headline, OLDER_DATE), (ZONES_THERE, there_headline, NEWER_DATE),
        ALL_ZONES,
    )
    sha = shas["there"] if picked == "newer" else shas["here"]
    rc, _out, combined = gitmem(
        ["remove", note_id, "superseded by the guard", *REMOVE_EXTRA[note_type], "--commit", sha],
        tmp_repo, fake_home,
    )
    assert rc == 0, combined
    live = [line.headline for line in live_lines(indexes, tmp_repo, note_type, note_id)]
    archived = [line.headline for line in archive_lines(indexes, tmp_repo, note_id)]
    assert len(live) == 1 and len(archived) == 1, f"setup: one twin each way: {live!r} {archived!r}"

    report = _boot_report(tmp_repo, gh_stub)

    assert f"base {note_type} entry so the index is tracked" in report, (
        f"setup: the boot must list live {note_type} headlines at all:\n{report}"
    )
    assert live[0] in report, (
        f"{note_id} {live[0]!r} is live in the index files but the boot does not show it:\n{report}"
    )
    assert archived[0] not in report, (
        f"{note_id} {archived[0]!r} is archived but the boot shows it:\n{report}"
    )
