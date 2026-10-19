"""`gitmem note ... --discard` honours `--replaces`/`--promotes`; an invalid
discard writes nothing (D-145, R.13, R.7). Driven through `bin/gitmem` on a
throwaway repo, read back through the real index readers.
"""

from pathlib import Path

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

ZONES = ("billing", "reports")
LONG_HEADLINE = "x" * 120  # over the 80-character headline cap: a rejected discard


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _gitmem(repo, args):
    rc, out, err = run_gitmem_script(with_searched(args), cwd=repo)
    assert "Traceback" not in out and "Traceback" not in err, f"{out!r} {err!r}"
    return rc, out, err


def _seed(repo, args):
    rc, out, err = _gitmem(repo, args)
    assert rc == 0, f"seed failed: stdout={out!r} stderr={err!r}"
    return extract_note_id(out)


def _seed_decision(repo, headline, why, description):
    return _seed(repo, [
        "note", "D", "--zones", *ZONES, headline, "--why", why, "--description", description,
    ])


def _seed_question(repo, headline, description):
    return _seed(repo, [
        "note", "Q", "--zones", *ZONES, headline, "--description", description, "--work", "no",
    ])


def _decision_args(headline, why, description, discards, *extra):
    args = ["note", "D", "--zones", *ZONES, headline, "--why", why, "--description", description]
    for discard_headline, discard_why in discards:
        args += ["--discard", discard_headline, discard_why]
    return args + list(extra)


def _id_by_headline(indexes, index_name, pm, headline):
    matches = [line.id for line in indexes.read(index_name, pm) if line.headline == headline]
    assert len(matches) == 1, f"{headline!r} in {index_name}: {matches!r}"
    return matches[0]


def _head(repo):
    rc, out, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, err
    return out.strip()


def _snapshot(repo):
    """HEAD, the working tree state and the raw bytes of every memory file."""
    pm = Path(pm_path(repo))
    rc, status, err = run_git(["status", "--porcelain", "--untracked-files=all"], repo)
    assert rc == 0, err
    files = {path.name: path.read_bytes() for path in sorted(pm.glob("*.md"))}
    return _head(repo), status, files


class TestDiscardWithReplacesArchivesTheOldNote:
    def test_should_archive_the_replaced_decision_when_discard_is_given_too(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, list(ZONES))
        old_id = _seed_decision(
            tmp_repo,
            "invoices are rendered nightly by a cron batch",
            "the batch window was free at night",
            "Nightly cron renders every pending invoice in one pass.",
        )
        new_headline = "invoices render on demand through a queue worker"
        discard_headline = "keep the nightly cron and add a second run"

        rc, out, err = _gitmem(tmp_repo, _decision_args(
            new_headline,
            "customers wait a whole day for a corrected document",
            "Queue worker picks each invoice as soon as it is approved.",
            [(discard_headline, "two runs still leave a twelve hour gap")],
            "--replaces", old_id,
        ))
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        pm = pm_path(tmp_repo)
        new_id = _id_by_headline(indexes, "DECISIONS.md", pm, new_headline)
        _id_by_headline(indexes, "DISCARDED.md", pm, discard_headline)
        live = {line.id for line in indexes.read("DECISIONS.md", pm)}
        assert old_id not in live, f"{old_id} must leave DECISIONS.md: {sorted(live)!r}"
        archived = {line.id: line for line in indexes.read_archive(pm)}
        assert old_id in archived, f"{old_id} missing from ARCHIVED.md: {sorted(archived)!r}"
        assert archived[old_id].destination == "replaced"
        assert archived[old_id].destination_detail == new_id


class TestDiscardWithPromotesPromotesTheQuestion:
    def test_should_promote_the_question_when_discard_is_given_too(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, list(ZONES))
        q_id = _seed_question(
            tmp_repo,
            "should refunds above a threshold need a second approver",
            "Finance asked whether large refunds need four eyes.",
        )
        new_headline = "large refunds go through a dual approval step"
        discard_headline = "flag large refunds for a monthly audit instead"

        rc, out, err = _gitmem(tmp_repo, _decision_args(
            new_headline,
            "a monthly audit finds the mistake after the money left",
            "Refunds over the limit wait for a second finance approver.",
            [(discard_headline, "the money is gone before anyone looks")],
            "--promotes", q_id,
        ))
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        pm = pm_path(tmp_repo)
        new_id = _id_by_headline(indexes, "DECISIONS.md", pm, new_headline)
        _id_by_headline(indexes, "DISCARDED.md", pm, discard_headline)
        live_questions = {line.id for line in indexes.read("QUESTIONS.md", pm)}
        assert q_id not in live_questions, f"{q_id} must leave QUESTIONS.md"
        archived = {line.id: line for line in indexes.read_archive(pm)}
        assert q_id in archived, f"{q_id} missing from ARCHIVED.md: {sorted(archived)!r}"
        assert archived[q_id].destination == "promoted"
        assert archived[q_id].destination_detail == new_id


class TestInvalidDiscardWritesNothing:
    """One invalid discard: no decision, no other discard, no commit, rc != 0."""

    def _seed_base(self, repo):
        seed_zones_json(repo, list(ZONES))
        return _seed_decision(
            repo,
            "exports are stored as gzip csv files",
            "every consumer already reads csv",
            "Report exports land as compressed csv in object storage.",
        )

    def test_should_write_nothing_when_the_only_discard_is_invalid(self, tmp_repo):
        self._seed_base(tmp_repo)
        before = _snapshot(tmp_repo)

        rc, out, err = _gitmem(tmp_repo, _decision_args(
            "violet octopus caching layer for dashboards",
            "dashboards reload the same aggregates every minute",
            "A cache sits in front of the dashboard aggregates.",
            [(LONG_HEADLINE, "because")],
        ))

        assert rc != 0, f"an invalid discard must fail: stdout={out!r}"
        assert _snapshot(tmp_repo) == before, f"nothing may be written: stdout={out!r}"

    def test_should_write_neither_decision_nor_valid_discard_when_a_later_one_is_invalid(
        self, tmp_repo
    ):
        self._seed_base(tmp_repo)
        before = _snapshot(tmp_repo)

        rc, out, err = _gitmem(tmp_repo, _decision_args(
            "nightly digest emails batch per timezone",
            "one global send wakes half the customers at night",
            "Digest emails go out at eight local time per timezone.",
            [
                ("send every digest at midnight utc", "half the customers get it at night"),
                (LONG_HEADLINE, "because"),
            ],
        ))

        assert rc != 0, f"an invalid discard must fail: stdout={out!r}"
        assert _snapshot(tmp_repo) == before, f"nothing may be written: stdout={out!r}"

    def test_should_leave_the_old_note_live_when_replaces_comes_with_an_invalid_discard(
        self, tmp_repo, indexes
    ):
        old_id = self._seed_base(tmp_repo)
        before = _snapshot(tmp_repo)

        rc, out, err = _gitmem(tmp_repo, _decision_args(
            "exports move to parquet with snappy",
            "analysts query exports directly and csv scans are slow",
            "Report exports land as parquet files in object storage.",
            [(LONG_HEADLINE, "because")],
            "--replaces", old_id,
        ))

        assert rc != 0, f"an invalid discard must fail: stdout={out!r}"
        assert _snapshot(tmp_repo) == before, f"nothing may be written: stdout={out!r}"
        live = {line.id for line in indexes.read("DECISIONS.md", pm_path(tmp_repo))}
        assert old_id in live


class TestAllValidDiscardsAreWritten:
    """With every discard valid, the decision and each discard are written."""

    def test_should_write_the_decision_and_every_discard_when_all_are_valid(
        self, tmp_repo, indexes
    ):
        seed_zones_json(tmp_repo, list(ZONES))
        decision_headline = "tax rates come from the provider api"
        discards = [
            ("hardcode the tax table per country", "rates change several times a year"),
            ("let accounting upload a spreadsheet", "an upload nobody remembers goes stale"),
        ]

        rc, out, err = _gitmem(tmp_repo, _decision_args(
            decision_headline,
            "the provider already tracks every rate change",
            "Invoices ask the tax provider for the current rate.",
            discards,
        ))
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        pm = pm_path(tmp_repo)
        _id_by_headline(indexes, "DECISIONS.md", pm, decision_headline)
        discarded = {line.headline for line in indexes.read("DISCARDED.md", pm)}
        assert discarded == {headline for headline, _why in discards}
