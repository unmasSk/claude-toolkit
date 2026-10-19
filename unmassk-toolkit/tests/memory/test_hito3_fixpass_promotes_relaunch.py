"""#105 5.2 G3, behaviours the fix declared beyond its tests:

- `--promotes Q --replaces D` when D is not live, or when D is written
  twice: refused, nothing written, the question stays open.
- A relaunch printed for a note not yet written keeps `--keys`,
  `--promotes` and every `--discard` pair: the pain question, the issue
  gate, and the two `--promotes` target rejections. Each relaunch is pasted
  through a real shell and run; the state it leaves is read back.

Driven through `bin/gitmem` on a throwaway repo; expected values are what
each test wrote.
"""

import pytest

from .conftest import SEARCHED_ANSWER, import_lib_memory_module, pm_path, seed_zones_json
from .hito3_twins_support import (
    NEWER_DATE,
    OLDER_DATE,
    archive_lines,
    git_ok,
    gitmem,
    live_lines,
    make_twins,
    pasted_words,
    relaunch_commands,
    seed,
    snapshot,
)

ZONES = ("billing", "reports")
QUESTION = "should invoices render on demand"
NEW_DECISION = "invoices render on demand via a queue worker"
NEW_MEMO = "invoices render within a minute of approval"
WHY = "customers wait a whole day for a corrected invoice"
DESCRIPTION = "A queue worker renders each invoice as soon as it is approved."
ALTERNATIVE = ("keep the cron twice a day", "still a twelve hour gap")
KEYS = ("pdf", "scheduler")  # not in any headline: normalize_keys drops headline words
FILLED = {"--why": WHY, "--description": DESCRIPTION, "--searched": SEARCHED_ANSWER}
Q_PLACEHOLDER = "<ID de una Q real>"


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


@pytest.fixture
def question(tmp_repo, fake_home):
    seed_zones_json(tmp_repo, list(ZONES))
    q_id, _ = seed(tmp_repo, fake_home, "Q", ZONES, QUESTION,
                   ["--description", "finance asked about on-demand invoices", "--work", "no"])
    return q_id


def _decision(*extra):
    return ["note", "D", "--zones", *ZONES, NEW_DECISION, "--why", WHY, "--description", DESCRIPTION,
            *extra, "--searched", SEARCHED_ANSWER]


def _only_note_relaunch(combined, note_type, replace=()):
    """The single `gitmem note <type>` relaunch, pasted through a shell and
    with every `...` filled from the flag before it."""
    commands = list(relaunch_commands(combined))
    for old, new in replace:
        commands = [c.replace(old, new) for c in commands]
    found = [w for w in map(pasted_words, commands) if w[:3] == ["gitmem", "note", note_type]]
    assert len(found) == 1, f"one `gitmem note {note_type}` relaunch expected:\n{combined}"
    words = found[0]
    return [FILLED.get(words[i - 1], w) if w == "..." else w for i, w in enumerate(words)]


def _discard_pairs(words):
    return [tuple(words[i + 1:i + 3]) for i, w in enumerate(words) if w == "--discard"]


def _body_of(repo, headline):
    bodies = git_ok(["log", "--format=%B%x00"], repo).split("\0")
    return next(b for b in bodies if headline in b)


def _promoted_to(indexes, repo, q_id):
    return [(a.destination, a.destination_detail) for a in archive_lines(indexes, repo, q_id)]


def _saved_id(indexes, repo, index_name, headline):
    return next(line.id for line in indexes.read(index_name, pm_path(repo)) if line.headline == headline)


class TestPromotesWithReplacesRefused:
    def test_should_write_nothing_when_replaces_names_an_archived_decision(
        self, tmp_repo, fake_home, indexes, question
    ):
        old_id, _ = seed(tmp_repo, fake_home, "D", ZONES, "invoices rendered nightly by cron batch",
                         ["--description", "a cron renders every pending invoice", "--why", "free window"])
        rc, _out, combined = gitmem(["remove", old_id, "the cron was dropped"], tmp_repo, fake_home)
        assert rc == 0, f"setup: archiving {old_id} failed: {combined}"
        before = snapshot(tmp_repo)

        rc, _out, combined = gitmem(_decision("--promotes", question, "--replaces", old_id),
                                    tmp_repo, fake_home)

        assert rc == 1, f"--replaces an archived note must be refused: {combined!r}"
        assert old_id in combined, f"the refusal must name {old_id}: {combined!r}"
        assert snapshot(tmp_repo) == before, f"a refused promote must write nothing:\n{combined}"

    def test_should_write_nothing_and_list_both_commits_when_replaces_names_a_duplicated_decision(
        self, tmp_repo, tmp_path, fake_home, indexes
    ):
        extra = ["--description", "seeded decision", "--why", "seeded why"]
        old_id, shas = make_twins(
            tmp_repo, tmp_path, fake_home, "D",
            (ZONES, "invoices rendered nightly by cron batch", OLDER_DATE),
            (ZONES, "ledger closes on the first monday", NEWER_DATE), list(ZONES), extra,
        )
        q_id, _ = seed(tmp_repo, fake_home, "Q", ZONES, QUESTION,
                       ["--description", "finance asked about on-demand invoices", "--work", "no"])
        before = snapshot(tmp_repo)

        rc, _out, combined = gitmem(_decision("--promotes", q_id, "--replaces", old_id),
                                    tmp_repo, fake_home)

        assert rc == 1, f"--replaces a duplicated id must be refused: {combined!r}"
        missing = [s[:10] for s in shas.values() if s[:10] not in combined]
        assert not missing, f"the refusal must list each twin's commit, missing {missing}:\n{combined}"
        assert snapshot(tmp_repo) == before, f"a refused promote must write nothing:\n{combined}"


class TestRelaunchKeepsFlags:
    def test_should_write_the_keys_when_the_pain_question_relaunch_is_pasted(
        self, tmp_repo, fake_home
    ):
        seed_zones_json(tmp_repo, list(ZONES))
        rc, _out, combined = gitmem(
            ["note", "M", "--zones", *ZONES, NEW_MEMO, "--description", DESCRIPTION,
             "--keys", *KEYS, "--searched", SEARCHED_ANSWER], tmp_repo, fake_home)
        assert rc == 1, f"setup: an M without --stops must ask the pain question: {combined!r}"
        words = _only_note_relaunch(combined, "M")

        rc, _out, combined = gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}\n{words!r}"
        keys_line = next((ln for ln in _body_of(tmp_repo, NEW_MEMO).splitlines() if ln.startswith("Keys:")), "")
        assert all(k in keys_line for k in KEYS), f"the relaunch dropped --keys: {keys_line!r}\n{words!r}"

    def test_should_promote_the_question_when_the_pain_question_relaunch_is_pasted(
        self, tmp_repo, fake_home, indexes, question
    ):
        rc, _out, combined = gitmem(
            ["note", "M", "--zones", *ZONES, NEW_MEMO, "--description", DESCRIPTION,
             "--promotes", question, "--searched", SEARCHED_ANSWER], tmp_repo, fake_home)
        assert rc == 1, f"setup: an M without --stops must ask the pain question: {combined!r}"
        words = _only_note_relaunch(combined, "M")

        rc, _out, combined = gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}\n{words!r}"
        memo = _saved_id(indexes, tmp_repo, "MEMOS.md", NEW_MEMO)
        assert _promoted_to(indexes, tmp_repo, question) == [("promoted", memo)], (
            f"the relaunch dropped --promotes: {words!r}"
        )
        assert live_lines(indexes, tmp_repo, "Q", question) == []

    def test_should_write_the_alternative_when_the_issue_gate_relaunch_is_pasted(
        self, tmp_repo, fake_home, indexes
    ):
        seed_zones_json(tmp_repo, list(ZONES))
        rc, _out, combined = gitmem(_decision("--work", "no", "--discard", *ALTERNATIVE),
                                    tmp_repo, fake_home)
        assert rc == 1, f"setup: --work on a D must be refused: {combined!r}"
        words = _only_note_relaunch(combined, "D")
        assert _discard_pairs(words) == [ALTERNATIVE], f"--discard must ride once: {words!r}"

        rc, _out, combined = gitmem([*words[1:], "--why", WHY], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}\n{words!r}"
        discarded = [line.headline for line in indexes.read("DISCARDED.md", pm_path(tmp_repo))]
        assert discarded == [ALTERNATIVE[0]]
        assert NEW_DECISION in [line.headline for line in indexes.read("DECISIONS.md", pm_path(tmp_repo))]

    @pytest.mark.parametrize("bad_target", ("Q-999", "D-001"), ids=("dangling", "not-a-question"))
    def test_should_promote_and_discard_when_the_promotes_target_relaunch_is_pasted(
        self, tmp_repo, fake_home, indexes, question, bad_target
    ):
        rc, _out, combined = gitmem(_decision("--promotes", bad_target, "--discard", *ALTERNATIVE),
                                    tmp_repo, fake_home)
        assert rc == 1, f"setup: --promotes {bad_target} must be refused: {combined!r}"
        words = _only_note_relaunch(combined, "D", replace=((Q_PLACEHOLDER, question),))
        assert words.count("--promotes") == 1, f"--promotes must appear once: {words!r}"
        assert _discard_pairs(words) == [ALTERNATIVE], f"--discard must ride once: {words!r}"

        rc, _out, combined = gitmem([*words[1:], "--why", WHY], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}\n{words!r}"
        decision = _saved_id(indexes, tmp_repo, "DECISIONS.md", NEW_DECISION)
        assert _promoted_to(indexes, tmp_repo, question) == [("promoted", decision)]
        discarded = [line.headline for line in indexes.read("DISCARDED.md", pm_path(tmp_repo))]
        assert discarded == [ALTERNATIVE[0]]
