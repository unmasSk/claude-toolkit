"""`gitmem remove --replaces` (D-145, R.3, #105).

`--replaces` without `--restriction new` is refused with nothing touched; an
archived target is refused before the close; `--replaces none` lets both
walls live; the fence-only retry after a failed wall save carries
`--replaces`; a wall bounced as similar relaunches `gitmem remove ...
--replaces`, never a loose `gitmem note R`. Driven through `bin/gitmem` on a
throwaway repo, read back through the real index readers.
"""

import os
import re
import shutil
import stat
import subprocess

import pytest

from .conftest import (
    SEARCHED_ANSWER,
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
_RETRY_PREFIX = "Relanza solo el muro con: "

# Refuses only the saves that stage RESTRICTIONS.md: the close goes through,
# the wall's own save fails (gitcmd commits without skipping hooks).
_REFUSE_WALL_HOOK = (
    b"#!/bin/sh\n"
    b"if git diff --cached --name-only | grep -q 'RESTRICTIONS.md'; then\n"
    b"  echo 'MARK_HOOK refusing the wall' >&2\n"
    b"  exit 1\n"
    b"fi\n"
    b"exit 0\n"
)


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _gitmem(args, cwd):
    rc, out, err = run_gitmem_script(args, cwd=cwd)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, out, combined


def _git_ok(args, cwd):
    rc, out, err = run_git(args, cwd)
    assert rc == 0, f"git {args} failed in the test setup: {err}"
    return out


def _seed(repo, args):
    rc, out, combined = _gitmem(with_searched(["note", *args]), repo)
    assert rc == 0, f"seeding failed: {combined!r}"
    match = _SAVED_ID_RE.search(out)
    assert match, f"no saved id in the seed output: {out!r}"
    return match.group(1)


def _seed_wall(repo):
    return _seed(repo, ["R", "--zones", *ZONES, OLD_WALL, "--description", OLD_WALL,
                        "--why", WALL_WHY, "--stops", "yes", "--origin", "none"])


def _seed_incident(repo):
    return _seed(repo, ["I", "--zones", *ZONES, "a session hung after the plugin folder was wiped",
                        "--description", "every Bash call blocked until the app was restarted",
                        "--work", "no"])


@pytest.fixture
def incident_and_wall(tmp_repo):
    seed_zones_json(tmp_repo, ZONES)
    wall_id = _seed_wall(tmp_repo)
    return _seed_incident(tmp_repo), wall_id


def _new_wall_args(incident_id, *extra):
    return ["remove", incident_id, REASON, "--restriction", "new",
            "--restriction-text", NEW_WALL, "--why", WALL_WHY, *extra]


def _snapshot(repo):
    files = {p.name: p.read_bytes() for p in sorted(pm_path(repo).glob("*.md"))}
    return files, _git_ok(["rev-parse", "HEAD"], repo), _git_ok(["status", "--porcelain"], repo)


def _live_ids(indexes, repo, index_name):
    return {line.id: line.headline for line in indexes.read(index_name, pm_path(repo))}


def _archived(indexes, repo):
    return {a.id: (a.destination, a.destination_detail) for a in indexes.read_archive(pm_path(repo))}


def _commit_body(repo, note_id):
    return _git_ok(["log", "-1", "--format=%B", "-F", f"--grep=[{note_id}]"], repo)


def _new_wall_id(out, old_id):
    saved = [found for found in _SAVED_ID_RE.findall(out) if found.startswith("R-") and found != old_id]
    assert len(saved) == 1, f"the new wall's id must be reported once: {out!r}"
    return saved[0]


def _pasted_words(command):
    """The argv a real shell builds from `command` pasted as printed."""
    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell on PATH"
    proc = subprocess.run([shell, "-c", "printf '%s\\0' " + command], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8").split("\0")[:-1]


def _relaunch_commands(output):
    commands, inside = [], False
    for line in output.splitlines():
        if line == "Relanza:":
            inside = True
            continue
        if inside and line.startswith("  "):
            commands.append(line.strip())
            continue
        inside = False
    return commands


def _flag_value(words, flag):
    assert words.count(flag) == 1, f"{flag} must appear exactly once: {words!r}"
    return words[words.index(flag) + 1]


class TestReplacesNeedsRestrictionNew:
    """Argus SEC-MED-001: --replaces is never dropped in silence."""

    def test_should_refuse_and_touch_nothing_when_an_incident_closes_with_restriction_no_and_replaces(
        self, tmp_repo, incident_and_wall, indexes
    ):
        incident_id, wall_id = incident_and_wall
        before = _snapshot(tmp_repo)

        rc, _out, combined = _gitmem(
            ["remove", incident_id, REASON, "--restriction", "no", "--replaces", wall_id], tmp_repo
        )

        assert rc == 1, f"--replaces without --restriction new must be refused: {combined!r}"
        assert "unrecognized arguments" not in combined
        assert "--replaces" in combined, f"the refusal must name --replaces: {combined!r}"
        assert _snapshot(tmp_repo) == before, "the incident must stay open and the wall live"

    def test_should_refuse_and_touch_nothing_when_a_memo_is_removed_with_replaces(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, ZONES)
        memo_args = ["--description", "seeded memo", "--stops", "no"]
        first = _seed(tmp_repo, ["M", "--zones", *ZONES, "the cache folder lives under the home dir", *memo_args])
        second = _seed(tmp_repo, ["M", "--zones", *ZONES, "hooks read their settings once per call", *memo_args])
        before = _snapshot(tmp_repo)

        rc, _out, combined = _gitmem(["remove", first, REASON, "--replaces", second], tmp_repo)

        assert rc == 1, f"--replaces on a plain remove must be refused: {combined!r}"
        assert "unrecognized arguments" not in combined
        assert "--replaces" in combined, f"the refusal must name --replaces: {combined!r}"
        assert _snapshot(tmp_repo) == before, "both memos must stay live"


class TestReplacesTargetChecks:
    """Ultron's «Beyond the tests»."""

    def test_should_touch_nothing_when_replaces_names_an_archived_wall(
        self, tmp_repo, incident_and_wall, indexes
    ):
        incident_id, wall_id = incident_and_wall
        rc, _out, combined = _gitmem(["remove", wall_id, "superseded by the installer"], tmp_repo)
        assert rc == 0, f"setup: archiving the wall failed: {combined!r}"
        before = _snapshot(tmp_repo)

        rc, _out, combined = _gitmem(_new_wall_args(incident_id, "--replaces", wall_id), tmp_repo)

        assert rc == 1, f"an archived --replaces target must be refused: {combined!r}"
        assert wall_id in combined
        assert _snapshot(tmp_repo) == before, "the incident must not be closed"

    def test_should_keep_both_walls_live_when_replaces_is_none(
        self, tmp_repo, incident_and_wall, indexes
    ):
        incident_id, wall_id = incident_and_wall

        rc, out, combined = _gitmem(_new_wall_args(incident_id, "--replaces", "none"), tmp_repo)

        assert rc == 0, combined
        new_id = _new_wall_id(out, wall_id)
        assert _live_ids(indexes, tmp_repo, "RESTRICTIONS.md") == {wall_id: OLD_WALL, new_id: NEW_WALL}
        assert _archived(indexes, tmp_repo) == {incident_id: ("closed", REASON)}
        body = _commit_body(tmp_repo, new_id)
        assert f"Origin: {incident_id}" in body and "Replaces: none" in body, body


class TestFenceRetryCarriesReplaces:
    """Ultron's «Beyond the tests»: the retry after a failed wall save."""

    def test_should_replace_the_old_wall_when_the_fence_retry_is_pasted(
        self, tmp_repo, incident_and_wall, indexes
    ):
        incident_id, wall_id = incident_and_wall
        hook = os.path.join(tmp_repo, ".git", "hooks", "pre-commit")
        with open(hook, "wb") as fh:
            fh.write(_REFUSE_WALL_HOOK)
        os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        rc, _out, combined = _gitmem(_new_wall_args(incident_id, "--replaces", wall_id), tmp_repo)
        assert rc == 1 and "MARK_HOOK" in combined, f"setup: the wall save was not refused: {combined!r}"
        assert _archived(indexes, tmp_repo) == {incident_id: ("closed", REASON)}, "setup: close not saved"
        retry = [line for line in combined.splitlines() if line.startswith(_RETRY_PREFIX)]
        assert len(retry) == 1, f"one fence-only retry expected:\n{combined}"
        words = _pasted_words(retry[0][len(_RETRY_PREFIX):])
        assert _flag_value(words, "--replaces") == wall_id, f"the retry dropped --replaces: {words!r}"
        searched = words.index("--searched") + 1
        words[searched] = SEARCHED_ANSWER  # the one gap the retry leaves to fill
        os.remove(hook)

        rc, out, combined = _gitmem(words[1:], tmp_repo)

        assert rc == 0, f"the pasted retry must work: {combined!r}"
        new_id = _new_wall_id(out, wall_id)
        assert _live_ids(indexes, tmp_repo, "RESTRICTIONS.md") == {new_id: NEW_WALL}
        assert _archived(indexes, tmp_repo)[wall_id] == ("replaced", new_id)
        assert f"Origin: {incident_id}" in _commit_body(tmp_repo, new_id)


class TestSimilarWallRelaunchUsesRemove:
    """Ultron's observation: the bounce of a similar wall relaunches `gitmem
    remove ... --replaces`, so the incident is closed with its wall."""

    def test_should_close_the_incident_and_replace_the_wall_when_the_similar_wall_relaunch_is_pasted(
        self, tmp_repo, incident_and_wall, indexes
    ):
        incident_id, wall_id = incident_and_wall
        before = _snapshot(tmp_repo)
        rc, _out, combined = _gitmem(_new_wall_args(incident_id), tmp_repo)
        assert rc == 1, f"setup: the similar wall should be bounced: {combined!r}"
        assert _snapshot(tmp_repo) == before

        commands = [_pasted_words(c) for c in _relaunch_commands(combined)]
        assert not [w for w in commands if w[:2] == ["gitmem", "note"]], (
            f"a loose `gitmem note` relaunch writes the wall without closing the incident:\n{combined}"
        )
        removes = [w for w in commands if w[:3] == ["gitmem", "remove", incident_id]]
        assert len(removes) == 1, f"one `gitmem remove {incident_id}` relaunch expected:\n{combined}"
        words = removes[0]
        assert words[3] == REASON, words
        assert _flag_value(words, "--restriction") == "new", words
        assert _flag_value(words, "--restriction-text") == NEW_WALL, words
        assert _flag_value(words, "--why") == WALL_WHY, words
        assert _flag_value(words, "--replaces") == wall_id, words

        rc, out, combined = _gitmem(words[1:], tmp_repo)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}"
        new_id = _new_wall_id(out, wall_id)
        assert _live_ids(indexes, tmp_repo, "RESTRICTIONS.md") == {new_id: NEW_WALL}
        assert _archived(indexes, tmp_repo) == {
            incident_id: ("closed", REASON), wall_id: ("replaced", new_id),
        }
