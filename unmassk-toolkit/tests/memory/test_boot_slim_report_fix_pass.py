"""Issue #89, fix pass of phase 4 -- the issues part of the boot report.

1. Code Ultron declared beyond the RED contract (each issue line's text,
   and the list when GitHub cannot be asked), now pinned.
2. One cited number GitHub does not return (deleted, transferred, or a PR
   number in an `Issue:` trailer) must not sink the whole check: the
   others are still checked, and only the missing one is flagged.

Expected titles and headlines are the values each test configures or
writes itself; GitHub is the shared double (`gh_graphql_fake`), which
answers a number it does not hold the way real gh does for a PR number:
`null` alias, NOT_FOUND error, exit 1.
"""

from pathlib import Path

from .boot_issue_state_support import (
    counts_section,
    issue_record,
    lines_naming_issue,
    patch_gh,
)
from .test_boot_slim_report_contract import (  # noqa: F401  (fixtures)
    _render,
    _write,
    boot,
    ctx,
    make_note,
    notes,
)


def _warnings(section):
    return [line for line in section if "⚠" in line]


# ---------------------------------------------------------------------------
# 1. Beyond the tests: the text of each issue line
# ---------------------------------------------------------------------------


def test_should_show_each_issues_github_title_when_github_answered(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: the line shows the note's headline (or nothing) instead
    # of the title GitHub returned, or titles swapped between issues.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, headline="MARK_FP_H60 note headline", issue=60)
    _write(notes, make_note, ctx, root, headline="MARK_FP_H61 note headline", issue=61)
    patch_gh(
        monkeypatch,
        {
            60: issue_record("OPEN", "MARK_FP_T60 github title sixty"),
            61: issue_record("OPEN", "MARK_FP_T61 github title sixty-one"),
        },
    )

    _summary, rendered = _render(boot, root)
    section = counts_section(rendered)
    joined = "\n".join(section)

    (line60,) = lines_naming_issue(section, 60)
    (line61,) = lines_naming_issue(section, 61)
    assert "MARK_FP_T60 github title sixty" in line60, joined
    assert "MARK_FP_T61 github title sixty-one" in line61, joined
    assert "MARK_FP_H60" not in joined and "MARK_FP_H61" not in joined, joined


def test_should_list_issues_under_the_warning_with_first_note_headline_when_github_fails(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: with GitHub down the live issues vanish (work hidden),
    # an issue takes one line per note, the line borrows a later note's
    # headline, or the lines sit above the "not checked" warning.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, headline="MARK_FP_FIRST70 first note", issue=70)
    _write(notes, make_note, ctx, root, headline="MARK_FP_LATER70 later note", issue=70)
    _write(notes, make_note, ctx, root, headline="MARK_FP_ONLY71 only note", issue=71)
    patch_gh(monkeypatch, fail=True)

    summary, rendered = _render(boot, root)
    section = counts_section(rendered)
    joined = "\n".join(section)

    lines70 = lines_naming_issue(section, 70)
    lines71 = lines_naming_issue(section, 71)
    assert len(lines70) == 1 and len(lines71) == 1, joined
    assert "MARK_FP_FIRST70" in lines70[0], joined
    assert "MARK_FP_LATER70" not in joined, joined
    assert "MARK_FP_ONLY71" in lines71[0], joined
    warning_at = section.index(_warnings(section)[0])
    assert warning_at < section.index(lines70[0]) < section.index(lines71[0]), joined
    assert summary.open_issues == 2


def test_should_not_warn_in_counts_when_github_fails_and_no_issue_is_listed(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: a "list not checked" warning over an empty list. The
    # only cited issue carries a discard, so GitHub IS asked (and fails)
    # but nothing is listed; the failure still shows in CHECKS.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, type="X", headline="MARK_FP_X80 discard", issue=80)
    calls = patch_gh(monkeypatch, fail=True)

    summary, rendered = _render(boot, root)
    section = counts_section(rendered)

    assert len(calls) == 1, "setup invalid: GitHub was never asked"
    assert summary.issues == ()
    assert _warnings(section) == [], "\n".join(section)
    assert summary.health.plans_unreflected_error is not None


# ---------------------------------------------------------------------------
# 2. One number GitHub does not return
# ---------------------------------------------------------------------------


def _seed_one_missing(notes, make_note, ctx, root, monkeypatch):
    """#50 open, #51 closed, #52 cited but unknown to GitHub."""
    _write(notes, make_note, ctx, root, headline="MARK_FP_H50 open work", issue=50)
    _write(notes, make_note, ctx, root, headline="MARK_FP_H51 closed work", issue=51)
    _write(notes, make_note, ctx, root, headline="MARK_FP_H52 cites a PR", issue=52)
    return patch_gh(
        monkeypatch,
        {
            50: issue_record("OPEN", "MARK_FP_T50 open title"),
            51: issue_record("CLOSED", "MARK_FP_T51 closed title"),
        },
    )


def test_should_still_check_the_others_when_one_cited_number_is_missing(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught (health_plans.py:219-227 before the fix): one number
    # GitHub does not return throws away every answer, so the closed #51
    # is listed again and #50 loses its GitHub title.
    root = Path(tmp_repo)
    calls = _seed_one_missing(notes, make_note, ctx, root, monkeypatch)

    _summary, rendered = _render(boot, root)
    section = counts_section(rendered)
    joined = "\n".join(section)

    assert len(calls) == 1, f"one GitHub call per boot (R-025), saw {len(calls)}"
    assert lines_naming_issue(section, 51) == [], joined
    assert "MARK_FP_H51" not in joined, joined
    (line50,) = lines_naming_issue(section, 50)
    assert "MARK_FP_T50 open title" in line50, joined


def test_should_still_count_unreflected_plans_of_the_others_when_one_is_missing(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: the plans check dropped for every issue because one
    # number did not come back. Each seeded note is one commit citing its
    # issue, newer than the issue's only activity (created 2020, no
    # comments): #50 has one unreflected commit; #52 has no answer to compare with.
    root = Path(tmp_repo)
    _seed_one_missing(notes, make_note, ctx, root, monkeypatch)

    summary, _rendered = _render(boot, root)

    plans = dict(summary.health.plans_unreflected)
    assert plans.get(50) == 1 and 52 not in plans, (
        summary.health.plans_unreflected,
        summary.health.plans_unreflected_error,
    )


def test_should_name_only_the_missing_number_when_one_cited_number_is_missing(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: the missing number goes unnamed (a trailer pointing at
    # nothing, silently), or COUNTS still warns that the whole list is
    # unchecked although GitHub answered for every other issue.
    root = Path(tmp_repo)
    _seed_one_missing(notes, make_note, ctx, root, monkeypatch)

    _summary, rendered = _render(boot, root)
    report_warnings = _warnings(rendered.splitlines())
    counts_warnings = _warnings(counts_section(rendered))

    assert any(lines_naming_issue([w], 52) for w in report_warnings), rendered
    assert all(lines_naming_issue([w], 52) for w in counts_warnings), counts_warnings
