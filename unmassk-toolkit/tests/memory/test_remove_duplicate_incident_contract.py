"""`gitmem remove` on a duplicated incident id (D-145, #105).

`--commit` picks one incident, also with `--restriction new` (the wall is
born in the picked incident's zones); every relaunch printed on the way
works when pasted as-is; `--commit` takes a unique sha prefix of at least 4
characters; `--replaces` refuses a duplicated target before closing.

The duplicate is made the way it happens in real use: two clones each write
the next id with `gitmem note`, then a union merge keeps both index lines.
"""

import hashlib
import re
import shutil
import subprocess

import pytest

from .conftest import (
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

ZONES_MAIN = ("billing", "payroll")
ZONES_BRANCH = ("billing", "ledger")
ALL_ZONES = ["billing", "payroll", "ledger"]
HEADLINE_MAIN = "invoices were exported twice after the nightly retry"
HEADLINE_BRANCH = "ledger totals drifted after a partial import"
REASON = "fixed by the idempotent export key"
WALL_TEXT = "every export carries an idempotency key checked before writing"
WALL_WHY = "a retried export without a key books the same invoice twice"
OLD_WALL = "exports never run twice for the same night"
INCIDENT_EXTRA = ["--description", "the customer saw two identical invoices", "--work", "no"]

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
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, out, combined


def _git_ok(args, cwd):
    rc, out, err = run_git(args, cwd)
    assert rc == 0, f"git {args} failed in the test setup: {err}"
    return out


def _seed(repo, env, note_type, zones, headline, extra):
    args = ["note", note_type, "--zones", *zones, headline, *extra]
    rc, out, combined = _gitmem(with_searched(args), repo, env)
    assert rc == 0, f"seeding {note_type} failed: {combined!r}"
    match = _SAVED_ID_RE.search(out)
    assert match, f"no saved id in the seed output: {out!r}"
    return match.group(1), _git_ok(["rev-parse", "HEAD"], repo)


def _forge_shared_prefix(clone, target_sha, length=4):
    """Rewrite the clone's HEAD commit (same tree, same message, another
    committer time) until its sha starts with `target_sha[:length]`.
    """
    raw = subprocess.run(
        ["git", "cat-file", "commit", "HEAD"], cwd=clone, capture_output=True, check=True
    ).stdout
    head_lines = raw.split(b"\n")
    index = next(i for i, line in enumerate(head_lines) if line.startswith(b"committer "))
    who, stamp, tz = head_lines[index].rsplit(b" ", 2)
    for shift in range(1, 20_000_000):
        head_lines[index] = b" ".join((who, str(int(stamp) + shift).encode(), tz))
        body = b"\n".join(head_lines)
        sha = hashlib.sha1(b"commit %d\0" % len(body) + body).hexdigest()
        if sha[:length] == target_sha[:length]:
            break
    else:
        raise AssertionError("setup: no commit with a shared prefix found")
    written = subprocess.run(
        ["git", "hash-object", "-t", "commit", "-w", "--stdin"],
        cwd=clone, input=body, capture_output=True, check=True,
    ).stdout.decode().strip()
    assert written == sha, f"setup: git wrote {written}, expected {sha}"
    _git_ok(["update-ref", "HEAD", sha], clone)
    return sha


def _seed_duplicate(repo, tmp_path, env, indexes, note_type, extra,
                    zones_main=ZONES_MAIN, zones_branch=ZONES_BRANCH, forge_prefix=False):
    """Two live index lines with one id, each from its own commit, each in
    its own zone pair. Returns (id, {headline: sha}, {headline: (zone1, zone2)}).
    """
    seed_zones_json(repo, ALL_ZONES)
    _seed(repo, env, note_type, zones_main, f"base {note_type} entry so the index is tracked", extra)

    other = str(tmp_path / "other")  # a clone: gitmem does not run in a worktree
    _git_ok(["clone", "-q", repo, other], str(tmp_path))
    seed_zones_json(other, ALL_ZONES)

    id_main, sha_main = _seed(repo, env, note_type, zones_main, HEADLINE_MAIN, extra)
    id_branch, sha_branch = _seed(other, env, note_type, zones_branch, HEADLINE_BRANCH, extra)
    assert id_main == id_branch, f"setup did not produce a duplicate: {id_main} vs {id_branch}"
    if forge_prefix:
        sha_branch = _forge_shared_prefix(other, sha_main)

    attributes = tmp_path / "repo" / ".git" / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text("*.md merge=union\n", encoding="utf-8")
    _git_ok(["fetch", "-q", other, "HEAD"], repo)
    _git_ok(["merge", "--no-edit", "FETCH_HEAD"], repo)

    index_name = {"I": "INCIDENTS.md", "R": "RESTRICTIONS.md"}[note_type]
    live = {
        line.headline: (line.zone1, line.zone2)
        for line in indexes.read(index_name, pm_path(repo)) if line.id == id_main
    }
    assert set(live) == {HEADLINE_MAIN, HEADLINE_BRANCH}, f"setup: both lines must be live: {live!r}"
    return id_main, {HEADLINE_MAIN: sha_main, HEADLINE_BRANCH: sha_branch}, live


@pytest.fixture
def incident_duplicate(tmp_repo, tmp_path, fake_home, indexes):
    return _seed_duplicate(tmp_repo, tmp_path, fake_home, indexes, "I", INCIDENT_EXTRA)


def _snapshot(repo):
    files = {p.name: p.read_bytes() for p in sorted(pm_path(repo).glob("*.md"))}
    return files, _git_ok(["rev-parse", "HEAD"], repo), _git_ok(["status", "--porcelain"], repo)


def _posix_shell():
    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell on PATH: cannot paste a relaunch like a person does"
    return shell


def _pasted_words(command):
    """The argv a real shell builds from `command` pasted as printed."""
    proc = subprocess.run(
        [_posix_shell(), "-c", "printf '%s\\0' " + command], capture_output=True
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8").split("\0")[:-1]


def _relaunch_commands(output):
    """Every command line of every `Relanza:` block in `output`."""
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


def _relaunch_for_commit(output, note_id, sha):
    """The pasted words of the one `gitmem remove <id>` relaunch whose
    `--commit` names `sha`."""
    found = []
    for command in _relaunch_commands(output):
        words = _pasted_words(command)
        if words[:3] != ["gitmem", "remove", note_id] or "--commit" not in words:
            continue
        value = _flag_value(words, "--commit")
        if len(value) >= 4 and sha.startswith(value.lower()):
            found.append(words)
    assert len(found) == 1, f"one relaunch with --commit {sha[:10]} expected:\n{output}"
    return found[0]


def _live(indexes, repo, index_name, note_id):
    return {line.headline: line for line in indexes.read(index_name, pm_path(repo)) if line.id == note_id}


def _archived(indexes, repo, note_id):
    return [(a.headline, a.destination, a.destination_detail)
            for a in indexes.read_archive(pm_path(repo)) if a.id == note_id]


def _new_wall(out):
    saved = [found for found in _SAVED_ID_RE.findall(out) if found.startswith("R-")]
    assert len(saved) == 1, f"the new wall's id must be reported once: {out!r}"
    return saved[0]


def _commit_body(repo, note_id):
    return _git_ok(["log", "-1", "--format=%B", "-F", f"--grep=[{note_id}]"], repo)


class TestIncidentCommitPicksOne:
    """Cerberus F2: --commit through the incident path."""

    @pytest.mark.parametrize("picked,kept", [
        (HEADLINE_BRANCH, HEADLINE_MAIN), (HEADLINE_MAIN, HEADLINE_BRANCH),
    ])
    def test_should_archive_only_the_picked_incident_when_restriction_no_gets_commit(
        self, tmp_repo, fake_home, incident_duplicate, indexes, picked, kept
    ):
        note_id, shas, _zones = incident_duplicate
        head_before = _git_ok(["rev-parse", "HEAD"], tmp_repo)

        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "no", "--commit", shas[picked]],
            tmp_repo, fake_home,
        )

        assert rc == 0, combined
        assert list(_live(indexes, tmp_repo, "INCIDENTS.md", note_id)) == [kept]
        assert _archived(indexes, tmp_repo, note_id) == [(picked, "closed", REASON)]
        assert _git_ok(["rev-list", "--count", f"{head_before}..HEAD"], tmp_repo) == "1"

    @pytest.mark.parametrize("picked,kept", [
        (HEADLINE_BRANCH, HEADLINE_MAIN), (HEADLINE_MAIN, HEADLINE_BRANCH),
    ])
    def test_should_birth_the_wall_in_the_picked_incident_zones_when_restriction_new_gets_commit(
        self, tmp_repo, fake_home, incident_duplicate, indexes, picked, kept
    ):
        note_id, shas, zones = incident_duplicate

        rc, out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "new", "--restriction-text", WALL_TEXT,
             "--why", WALL_WHY, "--commit", shas[picked]],
            tmp_repo, fake_home,
        )

        assert rc == 0, combined
        assert list(_live(indexes, tmp_repo, "INCIDENTS.md", note_id)) == [kept]
        assert _archived(indexes, tmp_repo, note_id) == [(picked, "closed", REASON)]
        wall_id = _new_wall(out)
        wall = _live(indexes, tmp_repo, "RESTRICTIONS.md", wall_id)[WALL_TEXT]
        assert (wall.zone1, wall.zone2) == zones[picked], "the wall must live where the picked incident lived"
        assert f"Origin: {note_id}" in _commit_body(tmp_repo, wall_id)


class TestDuplicateRefusalRelaunchWorksForAnIncident:
    """Cerberus F1: the refusal's relaunch keeps every flag the owner gave."""

    def test_should_close_the_picked_incident_when_the_restriction_no_relaunch_is_pasted(
        self, tmp_repo, fake_home, incident_duplicate, indexes
    ):
        note_id, shas, _zones = incident_duplicate
        before = _snapshot(tmp_repo)
        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "no"], tmp_repo, fake_home
        )
        assert rc == 1, f"a duplicated incident must be refused: {combined!r}"
        assert _snapshot(tmp_repo) == before, "a refused remove must touch nothing"

        words = _relaunch_for_commit(combined, note_id, shas[HEADLINE_BRANCH])
        assert words[3] == REASON, words
        assert _flag_value(words, "--restriction") == "no", f"the relaunch dropped --restriction: {words!r}"

        rc, _out, combined = _gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work as printed: {combined!r}"
        assert list(_live(indexes, tmp_repo, "INCIDENTS.md", note_id)) == [HEADLINE_MAIN]
        assert _archived(indexes, tmp_repo, note_id) == [(HEADLINE_BRANCH, "closed", REASON)]

    def test_should_close_and_birth_the_wall_when_the_restriction_new_relaunch_is_pasted(
        self, tmp_repo, fake_home, incident_duplicate, indexes
    ):
        note_id, shas, zones = incident_duplicate
        old_wall, _sha = _seed(tmp_repo, fake_home, "R", ZONES_BRANCH, OLD_WALL,
                               ["--description", OLD_WALL, "--why", WALL_WHY, "--stops", "yes", "--origin", "none"])
        before = _snapshot(tmp_repo)
        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "new", "--restriction-text", WALL_TEXT,
             "--why", WALL_WHY, "--replaces", old_wall],
            tmp_repo, fake_home,
        )
        assert rc == 1, f"a duplicated incident must be refused: {combined!r}"
        assert _snapshot(tmp_repo) == before, "a refused remove must touch nothing"

        words = _relaunch_for_commit(combined, note_id, shas[HEADLINE_BRANCH])
        assert words[3] == REASON, words
        assert _flag_value(words, "--restriction") == "new", words
        assert _flag_value(words, "--restriction-text") == WALL_TEXT, words
        assert _flag_value(words, "--why") == WALL_WHY, words
        assert _flag_value(words, "--replaces") == old_wall, words

        rc, out, combined = _gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work as printed: {combined!r}"
        assert _archived(indexes, tmp_repo, note_id) == [(HEADLINE_BRANCH, "closed", REASON)]
        wall_id = _new_wall(out)
        wall = _live(indexes, tmp_repo, "RESTRICTIONS.md", wall_id)[WALL_TEXT]
        assert (wall.zone1, wall.zone2) == zones[HEADLINE_BRANCH]
        assert _archived(indexes, tmp_repo, old_wall) == [(OLD_WALL, "replaced", wall_id)]


class TestIncidentQuestionKeepsCommit:
    """Cerberus F1: the incident question's relaunch keeps --commit."""

    def test_should_close_the_picked_incident_when_the_question_relaunch_is_pasted(
        self, tmp_repo, fake_home, incident_duplicate, indexes
    ):
        note_id, shas, _zones = incident_duplicate
        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--commit", shas[HEADLINE_BRANCH]], tmp_repo, fake_home
        )
        assert rc == 1, f"an incident without --restriction must ask: {combined!r}"

        no_relaunch = [
            words for words in map(_pasted_words, _relaunch_commands(combined))
            if words[:3] == ["gitmem", "remove", note_id] and "no" in words
        ]
        assert len(no_relaunch) == 1, f"one `--restriction no` relaunch expected:\n{combined}"
        words = [REASON if word == "..." else word for word in no_relaunch[0]]
        assert "--commit" in words, f"the question's relaunch dropped --commit: {words!r}"

        rc, _out, combined = _gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}"
        assert list(_live(indexes, tmp_repo, "INCIDENTS.md", note_id)) == [HEADLINE_MAIN]
        assert _archived(indexes, tmp_repo, note_id) == [(HEADLINE_BRANCH, "closed", REASON)]


class TestCommitPrefix:
    """Ultron's «Beyond the tests»: --commit takes a unique prefix of 4+ characters."""

    def test_should_archive_the_picked_incident_when_commit_is_a_short_unique_prefix(
        self, tmp_repo, fake_home, incident_duplicate, indexes
    ):
        note_id, shas, _zones = incident_duplicate
        picked, other = shas[HEADLINE_BRANCH], shas[HEADLINE_MAIN]
        length = next(n for n in range(4, 41) if picked[:n] != other[:n])

        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "no", "--commit", picked[:length]],
            tmp_repo, fake_home,
        )

        assert rc == 0, combined
        assert _archived(indexes, tmp_repo, note_id) == [(HEADLINE_BRANCH, "closed", REASON)]

    def test_should_refuse_and_touch_nothing_when_commit_prefix_is_under_four_characters(
        self, tmp_repo, fake_home, incident_duplicate
    ):
        note_id, shas, _zones = incident_duplicate
        before = _snapshot(tmp_repo)

        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "no", "--commit", shas[HEADLINE_BRANCH][:3]],
            tmp_repo, fake_home,
        )

        assert rc == 1, f"a 3-character prefix must be refused: {combined!r}"
        assert _snapshot(tmp_repo) == before

    def test_should_refuse_and_touch_nothing_when_commit_prefix_matches_both_notes(
        self, tmp_repo, tmp_path, fake_home, indexes
    ):
        note_id, shas, _zones = _seed_duplicate(
            tmp_repo, tmp_path, fake_home, indexes, "I", INCIDENT_EXTRA, forge_prefix=True
        )
        main, branch = shas[HEADLINE_MAIN], shas[HEADLINE_BRANCH]
        assert main[:4] == branch[:4] and main != branch, "setup: the two shas must share 4 characters"
        before = _snapshot(tmp_repo)

        rc, _out, combined = _gitmem(
            ["remove", note_id, REASON, "--restriction", "no", "--commit", main[:4]],
            tmp_repo, fake_home,
        )

        assert rc == 1, f"an ambiguous prefix must be refused: {combined!r}"
        assert _snapshot(tmp_repo) == before
        for headline, sha in shas.items():
            assert headline in combined and sha[:7] in combined, f"both notes must be listed:\n{combined}"


class TestReplacesRefusesADuplicatedWall:
    """Ultron's «Beyond the tests»: a duplicated --replaces target closes nothing."""

    def test_should_touch_nothing_when_remove_replaces_a_duplicated_wall(
        self, tmp_repo, tmp_path, fake_home, indexes
    ):
        wall_id, shas, _zones = _seed_duplicate(
            tmp_repo, tmp_path, fake_home, indexes, "R",
            ["--description", "seeded wall", "--why", WALL_WHY, "--stops", "yes"],
        )
        incident_id, _sha = _seed(tmp_repo, fake_home, "I", ZONES_MAIN,
                                  "a nightly export ran twice", INCIDENT_EXTRA)
        before = _snapshot(tmp_repo)

        rc, _out, combined = _gitmem(
            ["remove", incident_id, REASON, "--restriction", "new", "--restriction-text", WALL_TEXT,
             "--why", WALL_WHY, "--replaces", wall_id],
            tmp_repo, fake_home,
        )

        assert rc == 1, f"a duplicated --replaces target must be refused: {combined!r}"
        assert _snapshot(tmp_repo) == before, "the incident must not be closed"
        for headline, sha in shas.items():
            assert headline in combined and sha[:7] in combined, f"both walls must be listed:\n{combined}"
