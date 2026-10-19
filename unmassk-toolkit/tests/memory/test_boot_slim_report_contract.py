"""RED contract -- issue #89, step 4.1: the slimmer boot report.

What the owner approved (review page, point 1):
  - Restrictions print their headline only, under ONE line saying where
    the full why is read: `gitmem search --id R-xxx` (D-094: nothing
    leaves without a pointer to its full version).
  - The issues part of COUNTS prints one line per OPEN issue that has live
    work notes. Discards (X notes) do not count; closed issues are out.
    Open/closed comes from the boot's existing single bounded GitHub call
    (R-025: never one call per issue); when that call fails, the section
    says so plainly.
  - Branch, blockers, questions, incidents and checks stay as they are.

The line text itself (labels, the per-issue title) is not fixed by the
contract, so it is not pinned: each test checks which issues are named,
how many times, in what order, and what is absent.

Notes enter through the real writer (`notes.write`) against a disposable
repo; GitHub is a double at the `subprocess.run` boundary the code
already uses (`boot_issue_state_support.patch_gh`), or the `gh`
executable stub for the entry-point test.
"""

import contextlib
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from .boot_hook_gh_stub import gh_stub  # noqa: F401  (a fixture)
from .boot_issue_state_support import (
    counts_section,
    issue_numbers_in,
    issue_record,
    lines_naming_issue,
    patch_gh,
    restrictions_section,
)
from .conftest import import_lib_memory_module, run_memory_script

_POINTER = "gitmem search --id R-"

_BASE_NOTE_FIELDS = dict(
    type="M",
    id="",
    zone1="product",
    zone2="boot-test",
    description="MARK_SLIM_DESCRIPTION not empty",
    timestamp=datetime(2026, 10, 19, 12, 0, tzinfo=timezone.utc),
)


@pytest.fixture
def boot():
    return import_lib_memory_module("boot")


@pytest.fixture
def notes():
    return import_lib_memory_module("notes")


@pytest.fixture
def make_note():
    model = import_lib_memory_module("model")

    def _make(**overrides):
        fields = dict(_BASE_NOTE_FIELDS)
        fields.update(overrides)
        return model.Note(**fields)

    return _make


@pytest.fixture
def ctx():
    model = import_lib_memory_module("model")
    config = import_lib_memory_module("config")
    validator = import_lib_memory_module("validator")
    zone = "slimzone"
    return validator.Context(
        zones={zone: model.Zone(name=zone, description="MARK zone", aliases=())},
        existing_in_zone=(),
        known_ids=frozenset(),
        config=config.Config(),
    )


@contextlib.contextmanager
def _cwd(path):
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


def _write(notes, make_note, ctx, root, **fields):
    note = make_note(zone1="slimzone", zone2="slimzone", **fields)
    with _cwd(root):
        result = notes.write(note, ctx)
    assert result.ok, f"seed failed: {result.git_error or result.rejections}"
    return result.note_id


def _render(boot, root):
    with _cwd(root):
        summary = boot.build()
        return summary, boot.render(summary)


# ---------------------------------------------------------------------------
# Restrictions
# ---------------------------------------------------------------------------


def test_should_print_restriction_headlines_only_when_they_carry_a_why(
    boot, notes, make_note, ctx, tmp_repo
):
    # Bug caught: the why still printed under each restriction, or the
    # pointer to it missing, duplicated, or placed after the rows.
    root = Path(tmp_repo)
    seeded = []
    for i in range(2):
        headline = f"MARK_SLIM_R{i} restriction headline {i}"
        why = f"MARK_SLIM_WHY{i} the reason restriction {i} exists"
        note_id = _write(notes, make_note, ctx, root, type="R", headline=headline, why=why)
        seeded.append((note_id, headline, why))

    _summary, rendered = _render(boot, root)
    section = restrictions_section(rendered)

    for note_id, headline, why in seeded:
        assert any(note_id in line and headline in line for line in section), section
        assert why not in rendered, f"the why of {note_id} is still printed:\n{rendered}"

    assert rendered.count(_POINTER) == 1, (
        f"exactly one line must say where the full why is read:\n{rendered}"
    )
    pointer_at = next(i for i, line in enumerate(section) if _POINTER in line)
    first_row_at = next(i for i, line in enumerate(section) if line.startswith("   R-"))
    assert pointer_at < first_row_at, (
        f"the pointer line must sit above the restrictions:\n" + "\n".join(section)
    )


def test_should_keep_blocker_awaits_and_question_and_incident_descriptions(
    boot, notes, make_note, ctx, tmp_repo
):
    # Golden, green on purpose. Bug caught: the slimming also cuts the
    # sections the owner said stay unchanged.
    root = Path(tmp_repo)
    _write(
        notes, make_note, ctx, root, type="B",
        headline="MARK_SLIM_B blocker stays", awaits="MARK_SLIM_AWAITS the client IT team",
    )
    _write(
        notes, make_note, ctx, root, type="Q",
        headline="MARK_SLIM_Q question stays", description="MARK_SLIM_QDESC still open",
    )
    _write(
        notes, make_note, ctx, root, type="I",
        headline="MARK_SLIM_I incident stays", description="MARK_SLIM_IDESC still burning",
    )

    _summary, rendered = _render(boot, root)

    assert "awaits: MARK_SLIM_AWAITS the client IT team" in rendered, rendered
    assert "MARK_SLIM_QDESC still open" in rendered, rendered
    assert "MARK_SLIM_IDESC still burning" in rendered, rendered


# ---------------------------------------------------------------------------
# Issues
# ---------------------------------------------------------------------------


def test_should_print_one_line_per_open_issue_however_many_live_notes_it_has(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: one line per note (today: an issue with three notes takes
    # three lines), or issues out of number order.
    root = Path(tmp_repo)
    for i in range(3):
        _write(notes, make_note, ctx, root, headline=f"MARK_SLIM_ELEVEN note {i}", issue=11)
    _write(
        notes, make_note, ctx, root, type="D",
        headline="MARK_SLIM_SEVEN decision", why="MARK_SLIM_SEVEN_WHY", issue=7,
    )
    calls = patch_gh(
        monkeypatch,
        {7: issue_record("OPEN", "seven"), 11: issue_record("OPEN", "eleven")},
    )

    summary, rendered = _render(boot, root)
    section = counts_section(rendered)

    assert len(calls) == 1, f"one GitHub call per boot (R-025), saw {len(calls)}"
    assert len(lines_naming_issue(section, 11)) == 1, "\n".join(section)
    assert len(lines_naming_issue(section, 7)) == 1, "\n".join(section)
    assert issue_numbers_in(section) == [7, 11], "\n".join(section)
    assert summary.open_issues == 2


def test_should_leave_out_a_closed_issue_even_when_it_has_live_notes(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: a closed issue (#88 in the owner's report) still listed
    # because its notes were never archived.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_CLOSED work note", issue=20)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_OPEN work note", issue=21)
    patch_gh(
        monkeypatch,
        {20: issue_record("CLOSED", "twenty"), 21: issue_record("OPEN", "twentyone")},
    )

    summary, rendered = _render(boot, root)
    section = counts_section(rendered)

    assert lines_naming_issue(section, 20) == [], "\n".join(section)
    assert "MARK_SLIM_CLOSED" not in "\n".join(section), "\n".join(section)
    assert len(lines_naming_issue(section, 21)) == 1, "\n".join(section)
    assert summary.open_issues == 1


def test_should_not_count_discarded_notes_as_work_on_an_open_issue(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: an X (discard) note keeps an issue on the list, or lends
    # its headline to the issue's line.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, type="X", headline="MARK_SLIM_X30 only a discard", issue=30)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_M31 real work", issue=31)
    _write(notes, make_note, ctx, root, type="X", headline="MARK_SLIM_X31 discard too", issue=31)
    patch_gh(
        monkeypatch,
        {30: issue_record("OPEN", "thirty"), 31: issue_record("OPEN", "thirtyone")},
    )

    summary, rendered = _render(boot, root)
    section = counts_section(rendered)
    joined = "\n".join(section)

    assert lines_naming_issue(section, 30) == [], joined
    assert len(lines_naming_issue(section, 31)) == 1, joined
    assert "MARK_SLIM_X30" not in joined and "MARK_SLIM_X31" not in joined, joined
    assert summary.open_issues == 1


def test_should_ask_github_once_for_every_issue_with_notes(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Green on purpose (R-025 guard). Bug caught: fetching open/closed with
    # a second call, or one call per issue (I-005: the boot overran 30 s).
    root = Path(tmp_repo)
    for number in (3, 4, 5):
        _write(notes, make_note, ctx, root, headline=f"MARK_SLIM_ONE note {number}", issue=number)
    calls = patch_gh(monkeypatch, {n: issue_record("OPEN", f"i{n}") for n in (3, 4, 5)})

    _render(boot, root)

    from .gh_graphql_fake import requested_issue_numbers

    assert len(calls) == 1, f"expected one GitHub call, saw {calls!r}"
    assert sorted(requested_issue_numbers(calls[0][1:])) == [3, 4, 5]


def test_should_say_so_in_the_issues_section_when_github_cannot_be_asked(
    boot, notes, make_note, ctx, tmp_repo, monkeypatch
):
    # Bug caught: with GitHub down, the list looks like a checked list of
    # open issues and nobody can tell it was never checked.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_DOWN work note", issue=5)
    patch_gh(monkeypatch, fail=True)

    _summary, rendered = _render(boot, root)  # must not raise
    section = counts_section(rendered)

    warnings = [line for line in section if "⚠" in line]
    assert warnings, f"no warning in the issues section:\n" + "\n".join(section)
    assert any("GitHub" in line or "gh" in line.split() for line in warnings), warnings


def test_boot_script_lists_only_open_issues_with_live_work_notes(
    notes, make_note, ctx, tmp_repo, gh_stub  # noqa: F811
):
    # Entry point: `bin/memory/boot.py` run as a process with a fake `gh`
    # on PATH, the report read from the file the session reads.
    root = Path(tmp_repo)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_E41 first", issue=41)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_E41 second", issue=41)
    _write(notes, make_note, ctx, root, headline="MARK_SLIM_E42 on a closed issue", issue=42)
    _write(notes, make_note, ctx, root, type="X", headline="MARK_SLIM_E43 discard", issue=43)
    gh_stub.configure(
        issues={
            41: issue_record("OPEN", "forty-one"),
            42: issue_record("CLOSED", "forty-two"),
            43: issue_record("OPEN", "forty-three"),
        }
    )

    rc, out, err = run_memory_script("boot.py", [], cwd=tmp_repo, env=gh_stub.env())
    assert rc == 0, f"stdout={out!r} stderr={err!r}"
    report = (root / ".claude" / ".unmassk" / "boot-latest.txt").read_text(encoding="utf-8")
    section = counts_section(report)

    graphql_calls = [c for c in gh_stub.calls() if c[:2] == ["api", "graphql"]]
    assert len(gh_stub.calls()) == 1 and len(graphql_calls) == 1, gh_stub.calls()
    assert issue_numbers_in(section) == [41], "\n".join(section)
