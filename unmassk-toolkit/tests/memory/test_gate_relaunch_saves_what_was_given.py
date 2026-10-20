"""R.17 4.2: the issue-gate and pain-question relaunches keep what was given.

Contract (D-164, D-066 and the orchestrator's rule for step 4.2): a relaunch
pasted as printed, with only the holes the user must fill, saves exactly what
the user first gave -- never a placeholder as content, never a field dropped
-- and carries only fields the type takes. Moriarty's BREAK 2, his surviving
mutant M11, ABUSE 4 on the gate path, and what Ultron added in 3.4 with no
test: pain-question relaunches keep `--issue N`; B's `--awaits` is carried.

Expected values are the first invocation's arguments, never a filler.
Driven through `bin/gitmem` on a throwaway repo, read back with plain git.
"""

import sys

import pytest

from .conftest import extract_note_id
from .relaunch_fidelity_support import (
    ANCHOR_ZONES,
    AWAITS,
    DESCRIPTION,
    KEYS,
    NEW_HEADLINE,
    QUOTE,
    REAL_ISSUE,
    WHY,
    expected_fields,
    flag_values,
    gh_env,  # noqa: F401 -- pytest fixture
    gitmem,
    note_args,
    placeholders_saved,
    relaunch_lines,
    saved_fields,
    seed,
    seed_zones,
    single_relaunch,
    tokens_of,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH: subprocess.run(['gh', ...]) never resolves a file without .exe on Windows",
)

GATE_TYPES = ("Q", "I")
# The memory skill's field table: of the gate types, only I takes --why.
GATE_GIVEN = {
    "Q": {"--description": DESCRIPTION, "--keys": KEYS},
    "I": {"--description": DESCRIPTION, "--why": WHY, "--keys": KEYS},
}
AWAITS_WITH_QUOTES = 'Bex dice "espera al lunes"'


def _bounce(repo, env, note_type, given):
    seed_zones(repo)
    rc, out = gitmem(note_args(note_type, NEW_HEADLINE, given), repo, env)
    assert rc != 0, f"the {note_type} should bounce on its gate: {out}"
    return out


def _lines(output):
    return [tokens_of(line) for line in relaunch_lines(output)]


def _line_with(output, flag, value):
    found = [t for t in _lines(output) if flag_values(t, flag) == [value]]
    assert len(found) == 1, f"expected one relaunch line with {flag} {value}: {output}"
    return found[0]


class TestQuoteGivenBeforeTheIssueAnswer:
    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_carry_the_given_quote_on_the_issue_none_line(self, tmp_repo, gh_env, note_type):
        out = _bounce(tmp_repo, gh_env, note_type, {**GATE_GIVEN[note_type], "--quote": QUOTE})

        tokens = _line_with(out, "--issue", "none")

        assert flag_values(tokens, "--quote") == [QUOTE], tokens

    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_save_the_owner_quote_when_the_issue_none_line_is_pasted_as_printed(
        self, tmp_repo, gh_env, note_type
    ):
        given = {**GATE_GIVEN[note_type], "--quote": QUOTE}
        tokens = _line_with(_bounce(tmp_repo, gh_env, note_type, given), "--issue", "none")

        rc, out = gitmem(tokens, tmp_repo, gh_env)

        assert rc == 0, f"the issue-none line pasted as printed bounced: {tokens}\n{out}"
        assert saved_fields(tmp_repo, extract_note_id(out)) == expected_fields(given)


class TestPlaceholderIsNeverSavedAsContent:
    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_save_no_placeholder_when_missing_quote_relaunch_is_pasted_unfilled(
        self, tmp_repo, gh_env, note_type
    ):
        tokens = single_relaunch(
            _bounce(tmp_repo, gh_env, note_type, {**GATE_GIVEN[note_type], "--issue": "none"})
        )

        gitmem(tokens, tmp_repo, gh_env)

        assert placeholders_saved(tmp_repo) == [], "a relaunch hole was saved as the owner's words"


class TestGateRelaunchCarriesOnlyFieldsTheTypeTakes:
    def test_should_leave_origin_out_of_every_q_gate_line(self, tmp_repo, gh_env):
        seed_zones(tmp_repo)
        anchor = seed(tmp_repo, gh_env, "D", "an unrelated anchor decision",
                      {"--description": "anchor", "--why": "anchor", "--keys": ("anchornote",)},
                      zones=ANCHOR_ZONES)
        out = _bounce(tmp_repo, gh_env, "Q", {**GATE_GIVEN["Q"], "--origin": anchor})

        lines = _lines(out)

        assert lines, out
        assert [t for t in lines if "--origin" in t] == [], lines

    def test_should_leave_awaits_out_when_d_bounces_on_work(self, tmp_repo, gh_env):
        given = {"--description": DESCRIPTION, "--why": WHY, "--keys": KEYS, "--awaits": AWAITS, "--work": "no"}

        tokens = single_relaunch(_bounce(tmp_repo, gh_env, "D", given))

        assert "--awaits" not in tokens, tokens


class TestPainQuestionRelaunchKeepsTheIssue:
    def test_should_carry_the_issue_number_on_both_pain_lines(self, tmp_repo, gh_env):
        out = _bounce(tmp_repo, gh_env, "M", {"--description": DESCRIPTION, "--keys": KEYS, "--issue": REAL_ISSUE})

        lines = _lines(out)

        assert [flag_values(t, "--stops") for t in lines] == [["no"], ["yes"]], lines
        assert [flag_values(t, "--issue") for t in lines] == [[REAL_ISSUE], [REAL_ISSUE]], lines

    def test_should_save_the_given_fields_when_the_memo_line_is_pasted_as_printed(self, tmp_repo, gh_env):
        given = {"--description": DESCRIPTION, "--keys": KEYS, "--issue": REAL_ISSUE}
        tokens = _line_with(_bounce(tmp_repo, gh_env, "M", given), "--stops", "no")

        rc, out = gitmem(tokens, tmp_repo, gh_env)

        assert rc == 0, f"the memo line pasted as printed bounced: {tokens}\n{out}"
        assert saved_fields(tmp_repo, extract_note_id(out)) == expected_fields(given)


class TestBlockerAwaitsOnTheGateRelaunch:
    @pytest.mark.parametrize("trigger", [{"--work": "no"}, {"--issue": "none"}], ids=["work", "issue-none"])
    def test_should_carry_the_given_awaits_when_b_bounces_on_the_gate(self, tmp_repo, gh_env, trigger):
        given = {"--description": DESCRIPTION, "--keys": KEYS, "--awaits": AWAITS, **trigger}

        tokens = single_relaunch(_bounce(tmp_repo, gh_env, "B", given))

        assert flag_values(tokens, "--awaits") == [AWAITS], tokens

    def test_should_keep_awaits_one_shell_word_when_it_holds_double_quotes(self, tmp_repo, gh_env):
        given = {"--description": DESCRIPTION, "--keys": KEYS, "--awaits": AWAITS_WITH_QUOTES, "--work": "no"}

        tokens = single_relaunch(_bounce(tmp_repo, gh_env, "B", given))

        assert flag_values(tokens, "--awaits") == [AWAITS_WITH_QUOTES], tokens

    def test_should_save_the_given_fields_when_b_gate_relaunch_is_pasted_as_printed(self, tmp_repo, gh_env):
        given = {"--description": DESCRIPTION, "--keys": KEYS, "--awaits": AWAITS}
        tokens = single_relaunch(_bounce(tmp_repo, gh_env, "B", {**given, "--work": "no"}))

        rc, out = gitmem(tokens, tmp_repo, gh_env)

        assert rc == 0, f"the B relaunch pasted as printed bounced: {tokens}\n{out}"
        assert saved_fields(tmp_repo, extract_note_id(out)) == expected_fields(given)
