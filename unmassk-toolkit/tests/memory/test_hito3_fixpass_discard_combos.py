"""#105 fix pass after Moriarty (2026-10-19): `gitmem note D ... --discard`
combined with `--replaces`, `--promotes` and the overlap rejection.

- `--promotes Q --replaces D` (with or without `--discard`) must end in one
  consistent state: the old decision is archived exactly when a note says
  it replaces it.
- The overlap rejection's relaunch keeps `--discard`, `--keys` and
  `--promotes`; pasted, it writes the alternative and the keys.
- The same `--discard` pair given twice never writes two identical X.

Driven through `bin/gitmem` on a throwaway repo; read back from the index
files and the note commits.
"""

import pytest

from .conftest import SEARCHED_ANSWER, import_lib_memory_module, pm_path, seed_zones_json
from .hito3_twins_support import (
    flag_value,
    git_ok,
    gitmem,
    pasted_words,
    relaunch_commands,
    seed,
    snapshot,
)

ZONES = ("billing", "reports")
OLD_DECISION = "invoices rendered nightly by cron batch"
QUESTION = "should invoices render on demand"
NEW_DECISION = "invoices render on demand via a queue worker"
WHY = "customers wait a whole day for a corrected invoice"
DESCRIPTION = "A queue worker renders each invoice as soon as it is approved."
ALTERNATIVE = ("keep the cron twice a day", "still a twelve hour gap")
OVERLAPPING = "invoices rendered nightly by cron batch twice"
KEYS = ("pdf", "scheduler")  # not in any headline: normalize_keys drops headline words


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


def _ids(indexes, repo, index_name):
    return {line.id for line in indexes.read(index_name, pm_path(repo))}


def _bodies(repo):
    return git_ok(["log", "--format=%B%x00"], repo).split("\0")


def _decision(headline, *extra):
    return ["note", "D", "--zones", *ZONES, headline, "--why", WHY, "--description", DESCRIPTION, *extra]


@pytest.fixture
def decision_and_question(tmp_repo, fake_home):
    seed_zones_json(tmp_repo, list(ZONES))
    old_id, _ = seed(tmp_repo, fake_home, "D", ZONES, OLD_DECISION,
                     ["--description", "a cron renders every pending invoice", "--why", "the window was free",
                      "--keys", *KEYS])
    q_id, _ = seed(tmp_repo, fake_home, "Q", ZONES, QUESTION,
                   ["--description", "finance asked about on-demand invoices", "--work", "no"])
    return old_id, q_id


class TestPromotesWithReplaces:
    @pytest.mark.parametrize("discard", ([], ["--discard", *ALTERNATIVE]), ids=("plain", "with-discard"))
    def test_should_archive_the_old_decision_exactly_when_a_note_claims_to_replace_it(
        self, tmp_repo, fake_home, indexes, decision_and_question, discard
    ):
        old_id, q_id = decision_and_question

        rc, _out, combined = gitmem(
            [*_decision(NEW_DECISION, "--promotes", q_id, "--replaces", old_id, *discard),
             "--searched", SEARCHED_ANSWER],
            tmp_repo, fake_home,
        )

        old_live = old_id in _ids(indexes, tmp_repo, "DECISIONS.md")
        claimed = any(f"Replaces: {old_id}" in body for body in _bodies(tmp_repo))
        assert old_live != claimed, (
            f"rc={rc}: {old_id} live={old_live} while a note claims to replace it={claimed}; "
            f"either both happen or neither:\n{combined}"
        )
        q_live = q_id in _ids(indexes, tmp_repo, "QUESTIONS.md")
        new_written = any(line.headline == NEW_DECISION
                          for line in indexes.read("DECISIONS.md", pm_path(tmp_repo)))
        assert (rc == 0) == new_written == (not q_live) == claimed, (
            f"rc={rc} new={new_written} q_live={q_live} replaced={claimed}: one command, one outcome\n{combined}"
        )


class TestOverlapRejectionRelaunch:
    def _overlap_relaunch(self, repo, env, *extra):
        rc, _out, combined = gitmem(
            [*_decision(OVERLAPPING, "--keys", *KEYS, *extra), "--searched", SEARCHED_ANSWER],
            repo, env,
        )
        assert rc == 1, f"setup: the headline must overlap {OLD_DECISION!r}: {combined!r}"
        found = [pasted_words(c) for c in relaunch_commands(combined)]
        found = [w for w in found if w[:3] == ["gitmem", "note", "D"]]
        assert len(found) == 1, f"one `gitmem note D` relaunch expected:\n{combined}"
        return found[0]

    def test_should_keep_promotes_when_the_overlap_relaunch_is_printed(
        self, tmp_repo, fake_home, decision_and_question
    ):
        _old_id, q_id = decision_and_question

        words = self._overlap_relaunch(tmp_repo, fake_home, "--promotes", q_id,
                                       "--discard", *ALTERNATIVE)

        assert flag_value(words, "--promotes") == q_id, f"the relaunch dropped --promotes: {words!r}"

    def test_should_write_the_alternative_and_the_keys_when_the_overlap_relaunch_is_pasted(
        self, tmp_repo, fake_home, indexes, decision_and_question
    ):
        words = self._overlap_relaunch(tmp_repo, fake_home, "--discard", *ALTERNATIVE)
        filled = {"--why": WHY, "--description": DESCRIPTION, "--searched": SEARCHED_ANSWER}
        words = [filled.get(words[i - 1], w) if w == "..." else w for i, w in enumerate(words)]

        rc, _out, combined = gitmem(words[1:], tmp_repo, fake_home)

        assert rc == 0, f"the pasted relaunch must work: {combined!r}"
        discarded = [line.headline for line in indexes.read("DISCARDED.md", pm_path(tmp_repo))]
        assert ALTERNATIVE[0] in discarded, f"the relaunch dropped --discard: {discarded!r}\n{words!r}"
        new_body = next(b for b in _bodies(tmp_repo) if OVERLAPPING in b)
        keys_line = next((line for line in new_body.splitlines() if line.startswith("Keys:")), "")
        assert all(k in keys_line for k in KEYS), f"the relaunch dropped --keys: {new_body!r}\n{words!r}"


class TestDuplicateDiscardPair:
    def test_should_never_write_two_identical_alternatives_when_the_pair_is_given_twice(
        self, tmp_repo, fake_home, indexes, decision_and_question
    ):
        old_id, _q_id = decision_and_question
        before = snapshot(tmp_repo)

        rc, _out, combined = gitmem(
            [*_decision(NEW_DECISION, "--replaces", old_id, "--discard", *ALTERNATIVE,
                        "--discard", *ALTERNATIVE), "--searched", SEARCHED_ANSWER],
            tmp_repo, fake_home,
        )

        discarded = [line.headline for line in indexes.read("DISCARDED.md", pm_path(tmp_repo))]
        assert discarded.count(ALTERNATIVE[0]) <= 1, (
            f"rc={rc}: the same alternative written {discarded.count(ALTERNATIVE[0])} times:\n{combined}"
        )
        assert (rc == 0) == (snapshot(tmp_repo) != before), f"rc={rc} must match what was written"
