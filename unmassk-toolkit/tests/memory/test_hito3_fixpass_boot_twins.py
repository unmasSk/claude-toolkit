"""#105, D-148 (replaces D-147, 2026-10-19): the boot alarms a repeated
note id only while two or more copies of it are live.

- Two or more live copies: the CHECKS block does not say "✓  no duplicate
  IDs"; it names the id, lists each copy on one line (commit, zones,
  headline) and prints `gitmem remove <id> --commit <sha>`. Running that
  fix as printed clears the alarm on the next boot.
- One live copy left (the others archived), or none: the boot says
  nothing about the id, and the live copy shows in its own boot section
  like any other note (a live wall or incident is never hidden).

Twins are made the way they happen (two clones + union merge,
hito3_twins_support.make_twins); the expected commits, zones and headlines
are the ones this test wrote. Reader: `bin/memory/boot.py` run as a
process, the report read from the file the session reads.
"""

import re
from pathlib import Path

import pytest

from .boot_hook_gh_stub import gh_stub  # noqa: F401  (a fixture)
from .boot_hook_harness import POSIX_ONLY
from .conftest import import_lib_memory_module, pm_path, run_memory_script, seed_zones_json
from .hito3_twins_support import (
    NEWER_DATE,
    OLDER_DATE,
    BASE_DATE,
    git_ok,
    gitmem,
    make_twins,
    pasted_words,
    seed,
)

ZONES_HERE = ("install", "hooks")
ZONES_THERE = ("billing", "payroll")
ALL_ZONES = ["install", "hooks", "billing", "payroll"]
HEADLINES = {
    "M": ("installer keeps a copy of user hooks", "payroll exports carry a run key"),
    "I": ("installer clobbered a user hook", "payroll export doubled every salary"),
    "R": ("never overwrite a user hook on install", "never export payroll without a run key"),
}
THIRD_HEADLINE = "vacation balances reset on the first working morning"
THIRD_DATE = "2026-01-04T09:00:00+0000"
REMOVE_EXTRA = {"M": [], "I": ["--restriction", "no"], "R": []}
HEALTHY = "✓  no duplicate IDs"
SHORT_SHA = 7
FIX_RE = re.compile(r"`(gitmem remove [^`]+)`")
HEX_RE = re.compile(r"\b[0-9a-f]{7,40}\b")
SECTION_OF = {"I": "🔥 OPEN INCIDENTS", "R": "⚠️ RESTRICTIONS"}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _boot_report(repo, gh):
    """The boot report the session reads, after one real boot run."""
    gh.configure(issues={})
    rc, out, err = run_memory_script("boot.py", [], cwd=repo, env=gh.env())
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    return (Path(repo) / ".claude" / ".unmassk" / "boot-latest.txt").read_text(encoding="utf-8")


def _checks_block(repo, gh):
    """The CHECKS block of the boot report: from its title to the next blank line."""
    return _block(_boot_report(repo, gh), "CHECKS")


def _block(report, title):
    """The lines under the first line of `report` starting with `title`,
    up to the next section title (a non-blank line with no indent)."""
    lines = report.splitlines()
    heads = [i for i, line in enumerate(lines) if line.startswith(title)]
    assert heads, f"setup: the boot report has no {title!r} block:\n{report}"
    block = []
    for line in lines[heads[0] + 1:]:
        if line.strip() and not line.startswith(" "):
            break
        block.append(line)
    return "\n".join(line for line in block if line.strip())


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
    assert FIX_RE.search(checks), f"two live copies: the boot must print the remove fix:\n{checks}"
    for sha, zones, headline in notes:
        rows = [line for line in checks.splitlines() if sha[:SHORT_SHA] in line and headline in line]
        assert len(rows) == 1, (
            f"the note of commit {sha[:SHORT_SHA]} ({headline!r}) must be listed on one line:\n{checks}"
        )
        missing = [zone for zone in zones if zone not in rows[0]]
        assert not missing, (
            f"the line of commit {sha[:SHORT_SHA]} must carry its zones, missing {missing!r}: {rows[0]!r}"
        )


def _assert_silent_about(report, note_id):
    """D-148: with at most one live copy the boot says nothing about the id."""
    checks = _block(report, "CHECKS")
    assert HEALTHY in checks, (
        f"{note_id} has at most one live copy: the duplicate check must stay healthy:\n{checks}"
    )
    flagged = [line for line in report.splitlines() if "duplicate" in line.lower() and note_id in line]
    assert not flagged, f"the boot still flags {note_id}: {flagged!r}\n{checks}"
    assert "gitmem remove" not in report, (
        f"nothing is left to fix, yet the boot tells someone to remove something:\n{report}"
    )


def _printed_fix(checks, note_id, sha):
    """The argv of the remove fix the boot printed, for the copy of commit
    `sha`, filled the way a person fills it: `<id>`, `<sha>` (the short sha
    the boot listed for that copy), any other `<...>` and a `"..."` gap (the reason)."""
    listed = [token for line in checks.splitlines() for token in HEX_RE.findall(line)
              if sha.startswith(token)]
    assert listed, f"the boot lists no commit for the copy {sha[:SHORT_SHA]}:\n{checks}"
    fills = {"id": note_id, "sha": listed[0]}
    commands = [re.sub(r"<([^<>]+)>", lambda m: fills.get(m.group(1), "resolved"), command)
                for command in FIX_RE.findall(checks)]
    mine = [command for command in commands
            if any(sha.startswith(token) for token in HEX_RE.findall(command))]
    assert len(mine) == 1, f"one printed fix must name the copy {sha[:SHORT_SHA]}: {commands!r}"
    words = ["resolved" if word == "..." else word for word in pasted_words(mine[0])]
    assert words[:2] == ["gitmem", "remove"], f"the fix is not a gitmem remove: {words!r}"
    return words


def _triplets(repo, tmp_path, env):
    """Three live memos under one id, from three clones merged by union.
    Returns (id, [sha1, sha2, sha3])."""
    seed_zones_json(repo, ALL_ZONES)
    seed(repo, env, "M", ZONES_HERE, "base M entry so the index is tracked", None, BASE_DATE)
    others = [str(tmp_path / name) for name in ("other", "third")]
    for other in others:
        git_ok(["clone", "-q", repo, other], str(tmp_path))
        seed_zones_json(other, ALL_ZONES)
    written = [
        seed(repo, env, "M", ZONES_HERE, HEADLINES["M"][0], None, OLDER_DATE),
        seed(others[0], env, "M", ZONES_THERE, HEADLINES["M"][1], None, NEWER_DATE),
        seed(others[1], env, "M", ZONES_THERE, THIRD_HEADLINE, None, THIRD_DATE),
    ]
    assert len({note_id for note_id, _ in written}) == 1, f"setup: no shared id: {written!r}"
    attributes = pm_path(repo).parent.parent / ".git" / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text("*.md merge=union\n", encoding="utf-8")
    for other in others:
        git_ok(["fetch", "-q", other, "HEAD"], repo)
        git_ok(["merge", "--no-edit", "FETCH_HEAD"], repo)
    return written[0][0], [sha for _, sha in written]


@POSIX_ONLY
class TestBootAlarmsWhileTwoCopiesAreLive:
    @pytest.mark.parametrize("note_type", ("M", "I"))
    def test_should_alert_list_both_and_print_the_fix_when_two_live_notes_share_the_id(
        self, tmp_repo, tmp_path, fake_home, gh_stub, note_type  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, note_type)

        checks = _checks_block(tmp_repo, gh_stub)

        _assert_loud_and_listed(checks, note_id, (notes["here"], notes["there"]))

    def test_should_keep_alerting_when_one_of_three_copies_is_removed_and_two_stay_live(
        self, tmp_repo, tmp_path, fake_home, gh_stub  # noqa: F811
    ):
        note_id, shas = _triplets(tmp_repo, tmp_path, fake_home)
        _remove(tmp_repo, fake_home, "M", note_id, "--commit", shas[2])

        checks = _checks_block(tmp_repo, gh_stub)

        _assert_loud_and_listed(checks, note_id, (
            (shas[0], ZONES_HERE, HEADLINES["M"][0]), (shas[1], ZONES_THERE, HEADLINES["M"][1]),
        ))

    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_stop_telling_anyone_to_remove_anything_when_the_printed_fix_is_run(
        self, tmp_repo, tmp_path, fake_home, gh_stub, indexes, archived_is  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, "M")
        archived = notes["there"] if archived_is == "newer" else notes["here"]
        kept = notes["here"] if archived_is == "newer" else notes["there"]
        words = _printed_fix(_checks_block(tmp_repo, gh_stub), note_id, archived[0])

        rc, _out, combined = gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the fix the boot printed must work as printed: {words!r}\n{combined}"
        live = [line.headline for line in indexes.read("MEMOS.md", pm_path(tmp_repo)) if line.id == note_id]
        assert live == [kept[2]], f"the fix must archive exactly the copy it names: {live!r}"
        _assert_silent_about(_boot_report(tmp_repo, gh_stub), note_id)


@POSIX_ONLY
class TestBootSilentOnceAtMostOneCopyIsLive:
    @pytest.mark.parametrize("note_type", ("M", "I"))
    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_say_nothing_about_the_id_when_one_twin_is_live_and_the_other_archived(
        self, tmp_repo, tmp_path, fake_home, gh_stub, note_type, archived_is  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, note_type)
        archived = notes["there"] if archived_is == "newer" else notes["here"]
        _remove(tmp_repo, fake_home, note_type, note_id, "--commit", archived[0])

        _assert_silent_about(_boot_report(tmp_repo, gh_stub), note_id)

    def test_should_say_nothing_about_the_id_when_both_twins_are_archived(
        self, tmp_repo, tmp_path, fake_home, gh_stub  # noqa: F811
    ):
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, "M")
        _remove(tmp_repo, fake_home, "M", note_id, "--commit", notes["there"][0])
        _remove(tmp_repo, fake_home, "M", note_id)

        _assert_silent_about(_boot_report(tmp_repo, gh_stub), note_id)

    @pytest.mark.parametrize("note_type", ("I", "R"))
    @pytest.mark.parametrize("archived_is", ("newer", "older"))
    def test_should_show_the_live_copy_in_its_own_section_when_its_twin_was_archived(
        self, tmp_repo, tmp_path, fake_home, gh_stub, note_type, archived_is  # noqa: F811
    ):
        """A live incident or wall is never hidden because its id is also archived."""
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, note_type)
        archived = notes["there"] if archived_is == "newer" else notes["here"]
        kept = notes["here"] if archived_is == "newer" else notes["there"]
        _remove(tmp_repo, fake_home, note_type, note_id, "--commit", archived[0])

        section = _block(_boot_report(tmp_repo, gh_stub), SECTION_OF[note_type])

        rows = [line for line in section.splitlines() if note_id in line]
        assert len(rows) == 1 and kept[2] in rows[0], (
            f"the live copy {note_id} {kept[2]!r} must show once in its section:\n{section}"
        )
        assert archived[2] not in section, f"the archived copy shows as live:\n{section}"

    def test_should_count_both_archive_lines_when_one_id_was_archived_twice(
        self, tmp_repo, tmp_path, fake_home, gh_stub  # noqa: F811
    ):
        """G1: the "archived" figure counts ARCHIVED.md lines, not distinct
        ids. This test archives two notes under one id and leaves only the
        base memo live."""
        note_id, notes = _twins(tmp_repo, tmp_path, fake_home, "M")
        _remove(tmp_repo, fake_home, "M", note_id, "--commit", notes["there"][0])
        _remove(tmp_repo, fake_home, "M", note_id)

        checks = _checks_block(tmp_repo, gh_stub)

        assert "1 live + 2 archived" in checks, (
            f"two notes were archived and one stays live; the boot must say so:\n{checks}"
        )


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
