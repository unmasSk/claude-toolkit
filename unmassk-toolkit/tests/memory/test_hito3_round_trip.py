"""Round trip, #105 step 4.1 (D-145): what remove and note --discard write
is what `gitmem search` and `gitmem rezones` read back.

Three writers, each run through `bin/gitmem` on a throwaway repo:
a duplicated-id `remove --commit`, `remove --restriction new --replaces`,
and `note D --discard --replaces`. The expected state is never typed: it
is the index files the writer just left (read with `indexes.read` and
`indexes.read_archive`) and the note commits in git. The readers under
test are the commands a person runs.
"""

import re

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

_SAVED_ID_RE = re.compile(r"\b([A-Z]-\d+)\s+guardada")
_ZONE_HEADER_RE = re.compile(r"ZONA (\S+) · (\d+) vigentes · (\d+) archivadas")
_ID_HEADER_RE = re.compile(r"^\s*([A-Z]-\d+) · \S+ · (\S+)", re.MULTILINE)
_COHERENCE_RE = re.compile(r"\((\d+) líneas / (\d+) notas\)")
_NOTE_SUBJECT_RE = re.compile(r"^\[[A-Z]-\d+\]")
_LIVE_INDEXES = (
    "DECISIONS.md", "MEMOS.md", "RESTRICTIONS.md", "QUESTIONS.md",
    "DISCARDED.md", "INCIDENTS.md", "BLOCKED.md",
)
_ARCHIVED_WORD = "archivada"
_LIVE_WORD = "vigente"


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
    assert "Traceback" not in out + err, out + err
    return rc, out, out + err


def _git_ok(args, cwd):
    rc, out, err = run_git(args, cwd)
    assert rc == 0, f"git {args} failed in the test setup: {err}"
    return out


def _seed(repo, env, args):
    rc, out, combined = _gitmem(with_searched(["note", *args]), repo, env)
    assert rc == 0, f"seeding failed: {combined!r}"
    return extract_note_id(out)


# -- what the writer left: the expected side ---------------------------------

def _written_state(repo, indexes):
    """{(id, headline): (zones, 'live'|'archived')} from the index files."""
    pm = pm_path(repo)
    state = {}
    for name in _LIVE_INDEXES:
        for line in indexes.read(name, pm):
            state[(line.id, line.headline)] = ((line.zone1, line.zone2), "live")
    for line in indexes.read_archive(pm):
        state[(line.id, line.headline)] = ((line.zone1, line.zone2), "archived")
    return state


def _note_commit_count(repo):
    subjects = _git_ok(["log", "--format=%s"], repo).splitlines()
    return sum(1 for s in subjects if _NOTE_SUBJECT_RE.match(s))


def _live_index_line_count(repo, indexes):
    pm = pm_path(repo)
    return sum(len(list(indexes.read(name, pm))) for name in _LIVE_INDEXES)


# -- what the readers say -----------------------------------------------------

def _assert_id_search_matches(repo, env, state, note_id):
    """Every card `search --id` prints (one per note, if it prints several)
    carries the state the index files give that note's headline."""
    rc, out, combined = _gitmem(["search", "--id", note_id], repo, env)
    assert rc == 0, combined
    headers = list(_ID_HEADER_RE.finditer(out))
    assert headers and all(h.group(1) == note_id for h in headers), f"no header for {note_id}: {out!r}"
    ends = [h.start() for h in headers[1:]] + [len(out)]
    cards_shown = []
    for header, end in zip(headers, ends):
        card = out[header.end():end]
        shown = [h for (i, h) in state if i == note_id and h in card]
        assert len(shown) == 1, f"a card of search --id {note_id} must show one written headline: {card!r}"
        cards_shown.append(shown[0])
        written = state[(note_id, shown[0])][1]
        word = {"live": _LIVE_WORD, "archived": _ARCHIVED_WORD}[written]
        assert header.group(2) == word, (
            f"{note_id} {shown[0]!r} is {written} in the index files, "
            f"search --id says {header.group(2)!r}:\n{out}"
        )
    hidden = [h for (i, h), (_z, kind) in state.items()
              if i == note_id and kind == "live" and h not in cards_shown]
    assert not hidden, f"search --id {note_id} hides a live note: {hidden!r}\n{out}"
    return out


def _assert_zone_search_matches(repo, env, state, zone):
    in_zone = {key: kind for key, (zones, kind) in state.items() if zone in zones}
    live = sorted(h for (_i, h), kind in in_zone.items() if kind == "live")
    archived = sorted(h for (_i, h), kind in in_zone.items() if kind == "archived")

    rc, out, combined = _gitmem(["search", zone], repo, env)
    assert rc == 0, combined
    header = _ZONE_HEADER_RE.search(out)
    assert header and header.group(1) == zone, f"no zone header: {out!r}"
    assert (int(header.group(2)), int(header.group(3))) == (len(live), len(archived)), (
        f"zone {zone}: the index files hold {len(live)} live / {len(archived)} archived, "
        f"search says {header.group(2)} / {header.group(3)}:\n{out}"
    )
    missing = [h for h in live if h not in out]
    assert not missing, f"live notes missing from `search {zone}`: {missing!r}\n{out}"
    leaked = [h for h in archived if h not in live and h in out and _shown_as_live(out, h)]
    assert not leaked, f"archived notes shown as live in `search {zone}`: {leaked!r}\n{out}"

    rc, out, combined = _gitmem(["search", zone, "--todo"], repo, env)
    assert rc == 0, combined
    for headline in live:
        assert _shown_as_live(out, headline), (
            f"`search {zone} --todo` must show {headline!r} as live:\n{out}"
        )
    for headline in archived:
        assert _shown_as_archived(out, headline), (
            f"`search {zone} --todo` must show {headline!r} as archived:\n{out}"
        )


def _lines_with(out, headline):
    return [line for line in out.splitlines() if headline in line]


def _shown_as_live(out, headline):
    return any(_ARCHIVED_WORD not in line for line in _lines_with(out, headline))


def _shown_as_archived(out, headline):
    return any(_ARCHIVED_WORD in line for line in _lines_with(out, headline))


def _assert_rezones_agrees(repo, env, indexes):
    rc, out, combined = _gitmem(["rezones", "--verify"], repo, env)
    assert rc == 0, f"rezones --verify finds the write incoherent:\n{combined}"
    counts = _COHERENCE_RE.search(out)
    assert counts, f"no counts in rezones --verify: {out!r}"
    assert (int(counts.group(1)), int(counts.group(2))) == (
        _live_index_line_count(repo, indexes), _note_commit_count(repo)
    ), f"rezones --verify counts differ from the index files and git log:\n{out}"

    pm = pm_path(repo)
    before = {p.name: p.read_bytes() for p in sorted(pm.glob("*.md"))}
    head_before = _git_ok(["rev-parse", "HEAD"], repo)
    rc, _out, combined = _gitmem(["rezones"], repo, env)
    assert rc == 0, combined
    after = {p.name: p.read_bytes() for p in sorted(pm.glob("*.md"))}
    assert after == before, "rebuilding from git changed what the writer left"
    assert _git_ok(["rev-parse", "HEAD"], repo) == head_before, "rezones found something to repair"


# -- writer 1: duplicated id, remove --commit ---------------------------------

DUP_ZONES = ("billing", "payroll")
DUP_KEPT = "invoices are rounded half up before the ledger export"
DUP_PICKED = "vacation balances reset on the first working morning"
DUP_MEMO = ["--description", "seeded memo for the round trip", "--stops", "no"]


def _seed_memo(repo, env, headline):
    note_id = _seed(repo, env, ["M", "--zones", *DUP_ZONES, headline, *DUP_MEMO])
    return note_id, _git_ok(["rev-parse", "HEAD"], repo)


@pytest.fixture
def duplicated_memo(tmp_repo, tmp_path, fake_home):
    """Two live M lines with one id, made by two clones and a union merge."""
    seed_zones_json(tmp_repo, DUP_ZONES)
    _seed_memo(tmp_repo, fake_home, "base entry so the index file is tracked")
    other = str(tmp_path / "other")
    _git_ok(["clone", "-q", tmp_repo, other], str(tmp_path))
    seed_zones_json(other, DUP_ZONES)
    kept_id, _ = _seed_memo(tmp_repo, fake_home, DUP_KEPT)
    picked_id, picked_sha = _seed_memo(other, fake_home, DUP_PICKED)
    assert kept_id == picked_id, f"setup did not produce a duplicate: {kept_id} vs {picked_id}"
    attributes = tmp_path / "repo" / ".git" / "info" / "attributes"
    attributes.parent.mkdir(parents=True, exist_ok=True)
    attributes.write_text("*.md merge=union\n", encoding="utf-8")
    _git_ok(["fetch", "-q", other, "HEAD"], tmp_repo)
    _git_ok(["merge", "--no-edit", "FETCH_HEAD"], tmp_repo)
    return kept_id, picked_sha


class TestDuplicatedIdRemoveCommitReadsBack:
    @pytest.fixture
    def after_remove(self, tmp_repo, fake_home, duplicated_memo, indexes):
        note_id, picked_sha = duplicated_memo
        rc, _out, combined = _gitmem(
            ["remove", note_id, "gone after the payroll rewrite", "--commit", picked_sha],
            tmp_repo, fake_home,
        )
        assert rc == 0, combined
        state = _written_state(tmp_repo, indexes)
        assert state[(note_id, DUP_KEPT)][1] == "live", f"setup: writer did not keep it: {state!r}"
        assert state[(note_id, DUP_PICKED)][1] == "archived", f"setup: writer did not archive it: {state!r}"
        return note_id, state

    def test_should_show_the_kept_note_as_live_when_search_by_id_after_remove_commit(
        self, tmp_repo, fake_home, after_remove
    ):
        note_id, state = after_remove
        _assert_id_search_matches(tmp_repo, fake_home, state, note_id)

    @pytest.mark.parametrize("zone", DUP_ZONES)
    def test_should_count_and_list_the_kept_note_as_live_when_search_zone_after_remove_commit(
        self, tmp_repo, fake_home, after_remove, zone
    ):
        _note_id, state = after_remove
        _assert_zone_search_matches(tmp_repo, fake_home, state, zone)

    def test_should_find_index_coherent_and_nothing_to_rebuild_when_rezones_after_remove_commit(
        self, tmp_repo, fake_home, after_remove, indexes
    ):
        _assert_rezones_agrees(tmp_repo, fake_home, indexes)


# -- writer 2: remove --restriction new --replaces ----------------------------

WALL_ZONES = ("install", "hooks")
OLD_WALL = "never delete the plugin cache during an active session"
NEW_WALL = "never delete the plugin cache while any session is active"
WALL_WHY = "deleting the cache under a live session leaves every hook blocking with no fallback"


class TestRemoveRestrictionReplacesReadsBack:
    @pytest.fixture
    def after_remove(self, tmp_repo, fake_home, indexes):
        seed_zones_json(tmp_repo, WALL_ZONES)
        old_wall = _seed(tmp_repo, fake_home, [
            "R", "--zones", *WALL_ZONES, OLD_WALL, "--description", OLD_WALL,
            "--why", WALL_WHY, "--stops", "yes",
        ])
        incident = _seed(tmp_repo, fake_home, [
            "I", "--zones", *WALL_ZONES, "a session hung after the plugin folder was wiped",
            "--description", "every Bash call blocked until the app was restarted", "--work", "no",
        ])
        rc, out, combined = _gitmem([
            "remove", incident, "fixed by the installer guard", "--restriction", "new",
            "--restriction-text", NEW_WALL, "--why", WALL_WHY, "--replaces", old_wall,
        ], tmp_repo, fake_home)
        assert rc == 0, combined
        new_wall = [i for i in _SAVED_ID_RE.findall(out) if i.startswith("R-")]
        assert len(new_wall) == 1, f"setup: the new wall's id is not in the output: {out!r}"
        state = _written_state(tmp_repo, indexes)
        assert state[(incident, "a session hung after the plugin folder was wiped")][1] == "archived"
        assert state[(old_wall, OLD_WALL)][1] == "archived"
        assert state[(new_wall[0], NEW_WALL)][1] == "live"
        return incident, old_wall, new_wall[0], state

    @pytest.mark.parametrize("which", ("incident", "old_wall", "new_wall"))
    def test_should_match_the_index_state_when_search_by_id_after_remove_replaces(
        self, tmp_repo, fake_home, after_remove, which
    ):
        incident, old_wall, new_wall, state = after_remove
        note_id = {"incident": incident, "old_wall": old_wall, "new_wall": new_wall}[which]
        _assert_id_search_matches(tmp_repo, fake_home, state, note_id)

    def test_should_name_the_replaced_wall_and_the_incident_when_search_new_wall_by_id(
        self, tmp_repo, fake_home, after_remove
    ):
        incident, old_wall, new_wall, state = after_remove
        out = _assert_id_search_matches(tmp_repo, fake_home, state, new_wall)
        assert re.search(rf"(?<![\w-]){re.escape(old_wall)}(?![\w-])", out), (
            f"search --id {new_wall} must name the wall it replaced ({old_wall}):\n{out}"
        )
        rc, out, combined = _gitmem(["search", "--id", incident], tmp_repo, fake_home)
        assert rc == 0, combined
        assert new_wall in out, f"search --id {incident} must show the wall born from it:\n{out}"

    @pytest.mark.parametrize("zone", WALL_ZONES)
    def test_should_count_live_and_archived_from_the_index_when_search_zone_after_remove_replaces(
        self, tmp_repo, fake_home, after_remove, zone
    ):
        *_ids, state = after_remove
        _assert_zone_search_matches(tmp_repo, fake_home, state, zone)

    def test_should_find_index_coherent_and_nothing_to_rebuild_when_rezones_after_remove_replaces(
        self, tmp_repo, fake_home, after_remove, indexes
    ):
        _assert_rezones_agrees(tmp_repo, fake_home, indexes)


# -- writer 3: note D --discard --replaces ------------------------------------

DEC_ZONES = ("billing", "reports")
OLD_DECISION = "invoices are rendered nightly by a cron batch"
NEW_DECISION = "invoices render through a queue worker"
OLD_ALTERNATIVE = ("render invoices on demand from the web request", "a slow render blocks checkout")
NEW_ALTERNATIVE = ("render invoices in a separate reporting job", "reporting load would contend")


def _decision(headline, why, description, alternative, *extra):
    return [
        "D", "--zones", *DEC_ZONES, headline, "--why", why, "--description", description,
        "--discard", *alternative, *extra,
    ]


class TestDiscardReplacesReadsBack:
    @pytest.fixture
    def after_discard(self, tmp_repo, fake_home, indexes):
        seed_zones_json(tmp_repo, DEC_ZONES)
        old_id = _seed(tmp_repo, fake_home, _decision(
            OLD_DECISION, "the batch window was free", "Nightly cron renders each invoice.",
            OLD_ALTERNATIVE,
        ))
        new_id = _seed(tmp_repo, fake_home, _decision(
            NEW_DECISION, "customers wait a whole day", "A queue worker renders each invoice.",
            NEW_ALTERNATIVE, "--replaces", old_id,
        ))
        state = _written_state(tmp_repo, indexes)
        assert state[(old_id, OLD_DECISION)][1] == "archived", f"setup: {state!r}"
        assert state[(new_id, NEW_DECISION)][1] == "live", f"setup: {state!r}"
        discards = sorted(i for (i, h) in state if h in (OLD_ALTERNATIVE[0], NEW_ALTERNATIVE[0]))
        assert len(discards) == 2, f"setup: one X per decision expected: {state!r}"
        return old_id, new_id, discards, state

    def test_should_match_the_index_state_for_every_note_when_search_by_id_after_discard_replaces(
        self, tmp_repo, fake_home, after_discard
    ):
        old_id, new_id, discards, state = after_discard
        for note_id in (old_id, new_id):
            _assert_id_search_matches(tmp_repo, fake_home, state, note_id)
        out = _assert_id_search_matches(tmp_repo, fake_home, state, new_id)
        assert re.search(rf"(?<![\w-]){re.escape(old_id)}(?![\w-])", out), (
            f"search --id {new_id} must name the decision it replaced ({old_id}):\n{out}"
        )

    def test_should_hang_each_alternative_from_its_own_decision_when_search_by_id(
        self, tmp_repo, fake_home, after_discard
    ):
        old_id, new_id, _discards, _state = after_discard
        for decision_id, alternative in ((old_id, OLD_ALTERNATIVE), (new_id, NEW_ALTERNATIVE)):
            rc, out, combined = _gitmem(["search", "--id", decision_id], tmp_repo, fake_home)
            assert rc == 0, combined
            assert alternative[0] in out, (
                f"search --id {decision_id} must show the alternative it discarded:\n{out}"
            )

    @pytest.mark.parametrize("zone", DEC_ZONES)
    def test_should_count_live_and_archived_from_the_index_when_search_zone_after_discard_replaces(
        self, tmp_repo, fake_home, after_discard, zone
    ):
        *_ids, state = after_discard
        _assert_zone_search_matches(tmp_repo, fake_home, state, zone)

    def test_should_find_index_coherent_and_nothing_to_rebuild_when_rezones_after_discard_replaces(
        self, tmp_repo, fake_home, after_discard, indexes
    ):
        _assert_rezones_agrees(tmp_repo, fake_home, indexes)
