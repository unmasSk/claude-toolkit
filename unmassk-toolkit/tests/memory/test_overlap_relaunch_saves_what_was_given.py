"""R.17 4.2: the overlap relaunch, pasted as printed, saves what the user gave.

Contract (D-164 and the orchestrator's rule for step 4.2): a relaunch pasted
as printed, with only the holes the user must fill, saves exactly what the
user first gave -- never a placeholder as content, never a field dropped --
and offers only fields the type takes. Moriarty's BREAK 1, 3 and 4, ABUSE 1
and 4, his DECEPTION 2 (tests compared with their own filler), and the
`--quote` carry Ultron added in 3.4.

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
    OLD_HEADLINE,
    QUOTE,
    REAL_ISSUE,
    WHY,
    expected_fields,
    flag_values,
    gh_env,  # noqa: F401 -- pytest fixture
    gitmem,
    note_args,
    placeholders_saved,
    saved_fields,
    seed,
    seed_zones,
    single_relaunch,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH: subprocess.run(['gh', ...]) never resolves a file without .exe on Windows",
)

ALL_TYPES = ("D", "M", "R", "Q", "X", "I", "B")
# D-164, typed by hand: D, M, R replace the old note by id; the rest coexist.
REPLACE_BY_ID = ("D", "M", "R")
# The memory skill's field table: types that take --why.
TAKES_WHY = ("D", "R", "X", "I")
AWAITS_WITH_QUOTES = 'Bex dice "espera al lunes"'


def _base_given(note_type, anchor_id):
    """Every field the type takes, as the user first typed them."""
    given = {"--description": DESCRIPTION, "--keys": KEYS}
    if note_type in TAKES_WHY:
        given["--why"] = WHY
    if note_type in ("D", "M", "R", "X"):
        given["--origin"] = anchor_id
    if note_type in ("M", "R"):
        given["--stops"] = "no" if note_type == "M" else "yes"
    if note_type in ("Q", "I"):
        given["--work"] = "no"
    if note_type == "B":
        given["--awaits"] = AWAITS
    return given


def _setup(repo, env, note_type):
    """Seeds an anchor (for --origin) and an old note the new one overlaps."""
    seed_zones(repo)
    anchor_id = seed(
        repo, env, "D", "an unrelated anchor decision",
        {"--description": "anchor", "--why": "anchor", "--keys": ("anchornote",)},
        zones=ANCHOR_ZONES,
    )
    old_id = seed(repo, env, note_type, OLD_HEADLINE, _base_given(note_type, anchor_id))
    return anchor_id, old_id


def _bounce(repo, env, note_type, headline, given):
    rc, out = gitmem(note_args(note_type, headline, given), repo, env)
    assert rc != 0, f"the new {note_type} should bounce as overlapping: {out}"
    assert "esto pisa a algo" in out, f"expected the overlap rejection: {out}"
    return single_relaunch(out)


def _exit_for(note_type, old_id):
    return old_id if note_type in REPLACE_BY_ID else "none"


def _without(given, *flags):
    return {f: v for f, v in given.items() if f not in flags}


# (id, type, headline, change to the base answers)
SCENARIOS = [
    *[(f"base-{t}", t, NEW_HEADLINE, {}) for t in ALL_TYPES],
    ("Q-work-no-with-quote", "Q", NEW_HEADLINE, {"--quote": QUOTE}),
    ("I-issue-number-with-quote", "I", NEW_HEADLINE, {"--work": None, "--issue": REAL_ISSUE, "--quote": QUOTE}),
    ("D-headline-names-issue", "D", NEW_HEADLINE + " with the --issue flag", {"--issue": REAL_ISSUE}),
    ("I-headline-names-quote", "I", NEW_HEADLINE + " lost the --quote flag",
     {"--work": None, "--issue": "none", "--quote": QUOTE}),
    ("Q-headline-names-work", "Q", NEW_HEADLINE + " with the --work flag", {}),
    ("B-awaits-with-quotes", "B", NEW_HEADLINE, {"--awaits": AWAITS_WITH_QUOTES}),
]


def _given_for(note_type, anchor_id, change):
    given = {**_base_given(note_type, anchor_id), **change}
    return {f: v for f, v in given.items() if v is not None}


class TestPastedAsPrintedSavesTheFirstInvocation:
    @pytest.mark.parametrize("note_type,headline,change", [s[1:] for s in SCENARIOS], ids=[s[0] for s in SCENARIOS])
    def test_should_save_exactly_the_given_fields_when_overlap_relaunch_is_pasted_as_printed(
        self, tmp_repo, gh_env, note_type, headline, change
    ):
        anchor_id, old_id = _setup(tmp_repo, gh_env, note_type)
        given = _given_for(note_type, anchor_id, change)
        tokens = _bounce(tmp_repo, gh_env, note_type, headline, given)

        rc, out = gitmem(tokens, tmp_repo, gh_env)

        assert rc == 0, f"the relaunch pasted as printed bounced: {tokens}\n{out}"
        new_id = extract_note_id(out)
        assert saved_fields(tmp_repo, new_id) == expected_fields(given, _exit_for(note_type, old_id))

    @pytest.mark.parametrize("note_type", ("R", "X", "I"))
    def test_should_save_no_placeholder_when_relaunch_with_a_hole_is_pasted_unfilled(
        self, tmp_repo, gh_env, note_type
    ):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, note_type)
        given = _without(_base_given(note_type, anchor_id), "--why")
        tokens = _bounce(tmp_repo, gh_env, note_type, NEW_HEADLINE, given)

        gitmem(tokens, tmp_repo, gh_env)

        assert placeholders_saved(tmp_repo) == [], "a relaunch hole was saved as the user's content"


class TestOverlapRelaunchKeepsTheGivenText:
    @pytest.mark.parametrize("note_type", ALL_TYPES)
    def test_should_carry_the_given_description_when_type_overlaps(self, tmp_repo, gh_env, note_type):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, note_type)
        tokens = _bounce(tmp_repo, gh_env, note_type, NEW_HEADLINE, _base_given(note_type, anchor_id))

        assert flag_values(tokens, "--description") == [DESCRIPTION], tokens

    @pytest.mark.parametrize("note_type", TAKES_WHY)
    def test_should_carry_the_given_why_when_type_overlaps(self, tmp_repo, gh_env, note_type):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, note_type)
        tokens = _bounce(tmp_repo, gh_env, note_type, NEW_HEADLINE, _base_given(note_type, anchor_id))

        assert flag_values(tokens, "--why") == [WHY], tokens

    @pytest.mark.parametrize(
        "note_type,change",
        [("Q", {"--quote": QUOTE}), ("I", {"--work": None, "--issue": REAL_ISSUE, "--quote": QUOTE})],
        ids=["Q-work-no", "I-issue-number"],
    )
    def test_should_carry_the_quote_when_it_came_with_work_no_or_an_issue_number(
        self, tmp_repo, gh_env, note_type, change
    ):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, note_type)
        tokens = _bounce(tmp_repo, gh_env, note_type, NEW_HEADLINE, _given_for(note_type, anchor_id, change))

        assert flag_values(tokens, "--quote") == [QUOTE], tokens

    def test_should_keep_awaits_one_shell_word_when_it_holds_double_quotes(self, tmp_repo, gh_env):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, "B")
        given = _given_for("B", anchor_id, {"--awaits": AWAITS_WITH_QUOTES})
        tokens = _bounce(tmp_repo, gh_env, "B", NEW_HEADLINE, given)

        assert flag_values(tokens, "--awaits") == [AWAITS_WITH_QUOTES], tokens


class TestHeadlineNamingAFlagDropsNothing:
    @pytest.mark.parametrize(
        "note_type,headline,change,flag,values",
        [
            ("D", NEW_HEADLINE + " with the --issue flag", {"--issue": REAL_ISSUE}, "--issue", [REAL_ISSUE]),
            ("I", NEW_HEADLINE + " lost the --quote flag", {"--work": None, "--issue": "none", "--quote": QUOTE},
             "--quote", [QUOTE]),
            ("I", NEW_HEADLINE + " lost the --issue flag", {"--work": None, "--issue": "none", "--quote": QUOTE},
             "--issue", ["none"]),
            ("Q", NEW_HEADLINE + " with the --work flag", {}, "--work", ["no"]),
        ],
        ids=["D-issue", "I-quote", "I-issue-none", "Q-work"],
    )
    def test_should_carry_the_answer_when_the_headline_names_its_flag(
        self, tmp_repo, gh_env, note_type, headline, change, flag, values
    ):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, note_type)
        tokens = _bounce(tmp_repo, gh_env, note_type, headline, _given_for(note_type, anchor_id, change))

        assert flag_values(tokens, flag) == values, tokens

    def test_should_carry_promotes_when_the_headline_names_it(self, tmp_repo, gh_env):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, "D")
        question = seed(tmp_repo, gh_env, "Q", "should the copier recurse at all",
                        {"--description": "open question", "--keys": ("depthlimit",), "--work": "no"})
        given = {**_base_given("D", anchor_id), "--promotes": question}
        tokens = _bounce(tmp_repo, gh_env, "D", NEW_HEADLINE + " via --promotes", given)

        assert flag_values(tokens, "--promotes") == [question], tokens

    def test_should_carry_discard_when_the_headline_names_it(self, tmp_repo, gh_env):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, "D")
        pair = ("a flat copy of the cache", "loses every nested folder")
        given = {**_base_given("D", anchor_id), "--discard": pair}
        tokens = _bounce(tmp_repo, gh_env, "D", NEW_HEADLINE + " with --discard", given)

        assert "--discard" in tokens, tokens
        at = tokens.index("--discard")
        assert tuple(tokens[at + 1:at + 3]) == pair, tokens


class TestOverlapRelaunchOffersOnlyFieldsTheTypeTakes:
    @pytest.mark.parametrize(
        "note_type,flag,value",
        [("Q", "--origin", "anchor"), ("B", "--origin", "anchor"), ("D", "--awaits", "awaits")],
        ids=["Q-origin", "B-origin", "D-awaits"],
    )
    def test_should_leave_out_a_field_the_type_does_not_take(self, tmp_repo, gh_env, note_type, flag, value):
        anchor_id, _old_id = _setup(tmp_repo, gh_env, note_type)
        given = {**_base_given(note_type, anchor_id), flag: {"anchor": anchor_id, "awaits": AWAITS}[value]}
        tokens = _bounce(tmp_repo, gh_env, note_type, NEW_HEADLINE, given)

        assert flag not in tokens, f"{note_type} does not take {flag}: {tokens}"
