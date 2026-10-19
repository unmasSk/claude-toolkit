"""Test-first contract for issue #95, phase 1: the boot finishes inside
the SessionStart hook timeout (I-005, D-130).

I-005: `health_plans.plans_unreflected` asked GitHub once per issue ever
cited, one call after another. With 37 issues at about 0.87 s each, the
boot passed the 30 s timeout of the SessionStart hook, Claude Code killed
it, and the session started with no briefing and no warning.

D-130: one GitHub query for every issue, under a total time bound; on
failure the check reports through `plans_unreflected_error`, never an
invented result. `boot_launcher.py` keeps its own deadline below the hook
timeout and prints a loud `[memory]` notice when the boot overruns.

The hook runner, the fake `gh` and the overrun tools live in
`boot_hook_harness.py`, `boot_hook_gh_stub.py` and `boot_overrun_tools.py`
(split 2026-10-19, Yoda's size finding). This file keeps the batched
GitHub query: cost, correctness and failure. The launcher's own deadline
is in `test_boot_deadline_launcher.py`, the overrun marker in
`test_boot_deadline_overrun_marker.py`.
"""

import pytest

from . import gh_graphql_fake
from .boot_hook_gh_stub import (  # noqa: F401  (gh_stub is a fixture)
    _PAST_COMMENT,
    _all_unreflected,
    _future_iso,
    _issue,
    _seed_citations,
    gh_stub,
)
from .boot_hook_harness import (
    _GH_KNOB,
    _PLANS_ERROR_TEXT,
    _STARTUP_MARGIN_S,
    POSIX_ONLY,
    _assert_full_briefing,
    _boot_hook_entry,
    _plan_lines,
    _run_boot_hook,
)
from .conftest import import_lib_memory_module, run_git

pytestmark = POSIX_ONLY


# ==========================================================================
# 1. The boot finishes well inside the hook timeout, whatever the history
# ==========================================================================


class TestBootTimeDoesNotGrowWithCitedIssues:
    def test_should_finish_well_inside_hook_timeout_when_40_issues_cited_and_gh_is_slow(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: one GitHub call per issue (I-005). 40 x 0.4 s = 16 s
        # of gh alone; a single batched query costs 0.4 s.
        numbers = range(1, 41)
        _seed_citations(tmp_repo, {n: 1 for n in numbers})
        gh_stub.configure(issues=_all_unreflected(numbers), latency=0.4)
        _command, hook_timeout = _boot_hook_entry()
        bound = hook_timeout / 3  # "well inside" the 30 s the hook gets

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=bound + 2)

        assert not run.killed and run.elapsed < bound, (
            f"boot took {run.elapsed:.1f}s with 40 cited issues; must stay "
            f"under {bound:.0f}s (hook timeout {hook_timeout:.0f}s). "
            f"gh calls: {len(gh_stub.calls())}\n" + run.describe()
        )
        _assert_full_briefing(run)
        assert _plan_lines(run.report()) == {n: 1 for n in numbers}

    def test_should_ask_github_once_whether_5_or_40_issues_are_cited(
        self, tmp_path, gh_stub
    ):
        # Bug caught: cost proportional to history (N+1 calls), or a
        # batch split per issue. D-130: one query for all issues.
        counts = {}
        for how_many in (5, 40):
            repo = tmp_path / f"repo-{how_many}"
            repo.mkdir()
            assert run_git(["init"], str(repo))[0] == 0
            assert run_git(["commit", "--allow-empty", "-m", "init"], str(repo))[0] == 0
            numbers = range(1, how_many + 1)
            _seed_citations(str(repo), {n: 1 for n in numbers})
            if gh_stub.log_path.exists():
                gh_stub.log_path.unlink()
            gh_stub.configure(issues=_all_unreflected(numbers), latency=0.05)

            run_dir = tmp_path / f"run-{how_many}"
            run_dir.mkdir()
            run = _run_boot_hook(str(repo), run_dir, gh_stub, kill_after=60)
            _assert_full_briefing(run)
            counts[how_many] = len(gh_stub.calls())

        assert counts == {5: 1, 40: 1}, (
            f"gh invocations by number of cited issues: {counts}; D-130 "
            "says one GitHub query for every issue"
        )

    def test_should_ask_github_only_for_the_cited_issues_when_the_repo_has_many_more(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Cerberus F1): a query that reads every issue of the
        # repository, or a numeric range up to the highest cited number,
        # so its cost grows with the repository's whole history instead
        # of with what the commits cite.
        cited = {5: 1, 17: 2, 42: 1, 99: 1}
        _seed_citations(tmp_repo, cited)
        gh_stub.configure(issues=_all_unreflected(range(1, 121)))

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        calls = gh_stub.calls()
        assert len(calls) == 1, calls
        asked = gh_graphql_fake.requested_issue_numbers(calls[0])
        assert sorted(asked) == sorted(cited), (
            f"GitHub was asked for {sorted(asked)}; the commits cite only "
            f"{sorted(cited)}"
        )
        assert _plan_lines(run.report()) == cited, run.report()

    def test_should_report_exact_unreflected_counts_when_over_30_issues_and_half_closed(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bugs caught: closed issues dropped; reading `updatedAt` instead
        # of the last comment; asking `comments(first: 1)` (the OLDEST
        # comment) instead of the last; ignoring comments and using
        # `createdAt` only; counting commits wrong for an issue cited twice.
        issues = {}
        citations = {}
        expected = {}
        for n in range(1, 41):
            closed = n % 2 == 0
            if n % 3 == 0:
                # Last comment AFTER every commit: reflected, no line.
                issues[n] = _issue(
                    state="CLOSED" if closed else "OPEN",
                    comment_dates=(_PAST_COMMENT, _future_iso()),
                )
            elif n % 5 == 0:
                # Last comment in the past: commits after it are unreflected.
                issues[n] = _issue(
                    state="CLOSED" if closed else "OPEN", comment_dates=(_PAST_COMMENT,)
                )
            else:
                issues[n] = _issue(state="CLOSED" if closed else "OPEN")
            citations[n] = 2 if n % 4 == 1 else 1
            if n % 3 != 0:
                expected[n] = citations[n]
        _seed_citations(tmp_repo, citations)
        gh_stub.configure(issues=issues, latency=0.0)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        assert _PLANS_ERROR_TEXT not in run.report(), run.report()
        assert _plan_lines(run.report()) == expected, run.report()

    def test_should_not_call_github_when_no_commit_cites_an_issue(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: a batched query fired unconditionally -- a wasted
        # second on every boot, and an error line on a repo with no plans.
        gh_stub.configure(issues={}, latency=0.0)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        assert gh_stub.calls() == []
        assert _PLANS_ERROR_TEXT not in run.report(), run.report()


# ==========================================================================
# 2. GitHub cannot answer: an error line, never an invented result
# ==========================================================================


_THREE_CITED = {3: 1, 7: 2, 11: 1}


class TestGithubFailureIsReportedNotInvented:
    @pytest.mark.parametrize("mode", ["fail", "garbage", "wrong_shape"])
    def test_should_write_error_line_and_rest_of_briefing_when_gh_cannot_answer(
        self, tmp_repo, tmp_path, gh_stub, mode
    ):
        # Bug caught: a failed query read as "nothing unreflected" (empty
        # result) or as made-up counts, or the whole boot dying with it.
        _seed_citations(tmp_repo, _THREE_CITED)
        gh_stub.configure(issues=_all_unreflected(_THREE_CITED), mode=mode)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        report = run.report()
        assert _PLANS_ERROR_TEXT in report, report
        assert _plan_lines(report) == {}, report
        assert "duplicate IDs" in report, report  # the rest of CHECKS still ran

    def test_should_check_the_others_and_name_the_one_missing_from_the_answer(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: a batched answer that lacks a cited issue (deleted,
        # transferred, a PR number) silently read as "reflected", or --
        # #89 phase 4 fix pass -- throwing away the answers for every
        # other issue. #3 and #11 came back: their plans are still counted.
        _seed_citations(tmp_repo, _THREE_CITED)
        issues = _all_unreflected(_THREE_CITED)
        del issues[7]
        gh_stub.configure(issues=issues)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        report = run.report()
        assert _plan_lines(report) == {3: 1, 11: 1}, report
        # The cited issue GitHub does not return is named, so the owner
        # knows which trailer points at nothing.
        warning_lines = [line for line in report.splitlines() if "⚠" in line]
        assert any("#7" in line for line in warning_lines), warning_lines

    def test_should_give_up_within_the_bound_when_gh_hangs(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: no total bound on the GitHub query (only today's
        # 10 s per call), so a hanging GitHub eats the hook's 30 s.
        _seed_citations(tmp_repo, _THREE_CITED)
        gh_stub.configure(
            issues=_all_unreflected(_THREE_CITED), mode="hang", hang_seconds=25
        )
        gh_bound = 1.0

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=25,
            extra_env={_GH_KNOB: str(gh_bound)},
        )

        assert not run.killed and run.elapsed < gh_bound + _STARTUP_MARGIN_S, (
            f"with {_GH_KNOB}={gh_bound} and a hanging gh the boot took "
            f"{run.elapsed:.1f}s\n" + run.describe()
        )
        _assert_full_briefing(run)
        report = run.report()
        assert _PLANS_ERROR_TEXT in report, report
        assert _plan_lines(report) == {}, report

    def test_should_fall_back_to_default_bound_when_gh_knob_is_not_a_number(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: float("soon") blowing up inside the check -- the
        # owner sees an error line every boot for a typo, or worse, the
        # check is skipped.
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=60, extra_env={_GH_KNOB: "soon"}
        )

        _assert_full_briefing(run)
        assert _PLANS_ERROR_TEXT not in run.report(), run.report()
        assert _plan_lines(run.report()) == {3: 1}, run.report()


class TestHealthBuildCarriesTheError:
    """Unit level: the field the task names. `health.build()` in-process,
    against the same stub; the hook tests above see only the rendered
    text."""

    @pytest.mark.parametrize("mode", ["fail", "garbage", "wrong_shape"])
    def test_should_set_plans_unreflected_error_and_empty_result_when_gh_cannot_answer(
        self, tmp_repo, gh_stub, monkeypatch, mode
    ):
        # Bug caught: `plans_unreflected_error` left None while the result
        # is empty -- the renderer then shows no warning at all.
        health = import_lib_memory_module("health")
        _seed_citations(tmp_repo, _THREE_CITED)
        gh_stub.configure(issues=_all_unreflected(_THREE_CITED), mode=mode)
        for key, value in gh_stub.env().items():
            monkeypatch.setenv(key, value)
        monkeypatch.chdir(tmp_repo)

        report = health.build()

        assert report.plans_unreflected == ()
        assert isinstance(report.plans_unreflected_error, str)
        assert report.plans_unreflected_error.strip()

