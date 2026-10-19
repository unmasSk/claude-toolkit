"""Red contract, #105 step 1.1 (D-145, R.3): `gitmem remove I-x ...
--restriction new ... --replaces R-y` closes the incident, archives R-y and
writes the new wall, all through `bin/gitmem` on a throwaway repo.

The scenario is Bilbo's: a new wall worded almost like a live one is
bounced without --replaces, so the incident cannot be closed today.
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

ZONES = ("install", "hooks")
OLD_WALL = "never delete the plugin cache during an active session"
WALL_WHY = "deleting the cache under a live session leaves every hook blocking with no fallback"
NEW_WALL = "never delete the plugin cache while any session is active"
REASON = "fixed by the installer guard"

_SAVED_ID_RE = re.compile(r"\b([A-Z]-\d+)\s+guardada")


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


def _seed(repo, env, args):
    rc, out, err, _ = _gitmem(with_searched(["note", *args]), repo, env)
    assert rc == 0, f"seeding failed: stdout={out!r} stderr={err!r}"
    match = _SAVED_ID_RE.search(out)
    assert match, f"no saved id in the seed output: {out!r}"
    return match.group(1)


@pytest.fixture
def incident_and_wall(tmp_repo, fake_home):
    seed_zones_json(tmp_repo, ZONES)
    wall_id = _seed(tmp_repo, fake_home, [
        "R", "--zones", *ZONES, OLD_WALL, "--description", OLD_WALL,
        "--why", WALL_WHY, "--stops", "yes",
    ])
    incident_id = _seed(tmp_repo, fake_home, [
        "I", "--zones", *ZONES, "a session hung after the plugin folder was wiped",
        "--description", "every Bash call blocked until the app was restarted",
        "--work", "no",
    ])
    return incident_id, wall_id


def _remove_args(incident_id, *extra):
    return [
        "remove", incident_id, REASON, "--restriction", "new",
        "--restriction-text", NEW_WALL, "--why", WALL_WHY, *extra,
    ]


def _snapshot(repo):
    pm = pm_path(repo)
    files = {p.name: p.read_bytes() for p in sorted(pm.glob("*.md"))}
    return files, _git_ok(["rev-parse", "HEAD"], repo)


class TestRemoveRestrictionNewReplacesAWall:
    def test_should_close_incident_archive_old_wall_and_write_new_when_remove_gets_replaces(
        self, tmp_repo, fake_home, incident_and_wall, indexes
    ):
        incident_id, wall_id = incident_and_wall
        pm = pm_path(tmp_repo)
        # Precondition: without --replaces the near-identical wall is bounced.
        rc, _out, _err, combined = _gitmem(_remove_args(incident_id), tmp_repo, fake_home)
        assert rc != 0, f"setup: the similar wall should be bounced without --replaces: {combined!r}"
        assert incident_id in {line.id for line in indexes.read("INCIDENTS.md", pm)}

        rc, out, _err, combined = _gitmem(
            _remove_args(incident_id, "--replaces", wall_id), tmp_repo, fake_home
        )

        assert rc == 0, combined
        assert "Traceback" not in combined
        saved = [found for found in _SAVED_ID_RE.findall(out) if found.startswith("R-")]
        assert len(saved) == 1, f"the new wall's id must be reported once: {out!r}"
        new_id = saved[0]
        assert new_id != wall_id

        assert incident_id not in {line.id for line in indexes.read("INCIDENTS.md", pm)}
        live_walls = {line.id: line.headline for line in indexes.read("RESTRICTIONS.md", pm)}
        assert live_walls == {new_id: NEW_WALL}, f"only the new wall stays live: {live_walls!r}"

        archived = {a.id: (a.destination, a.destination_detail) for a in indexes.read_archive(pm)}
        assert archived.get(incident_id) == ("closed", REASON), archived
        assert archived.get(wall_id) == ("replaced", new_id), archived

        body = _git_ok(["log", "-1", "--format=%B", "-F", f"--grep=[{new_id}]"], tmp_repo)
        assert f"Origin: {incident_id}" in body, f"the new wall must cite the incident: {body!r}"
        assert f"Replaces: {wall_id}" in body, f"the new wall must cite the old one: {body!r}"

    def test_should_change_nothing_when_replaces_names_no_live_wall(
        self, tmp_repo, fake_home, incident_and_wall, indexes
    ):
        incident_id, _wall_id = incident_and_wall
        before = _snapshot(tmp_repo)

        rc, _out, _err, combined = _gitmem(
            _remove_args(incident_id, "--replaces", "R-999"), tmp_repo, fake_home
        )

        assert rc == 1, f"an unknown --replaces target must be a rejection: {combined!r}"
        assert "unrecognized arguments" not in combined
        assert "Traceback" not in combined
        assert "R-999" in combined
        assert _snapshot(tmp_repo) == before, "a refused remove must not touch indexes or git"
        assert incident_id in {line.id for line in indexes.read("INCIDENTS.md", pm_path(tmp_repo))}
