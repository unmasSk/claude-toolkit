"""#95 part 2c (D-098/D-124), what Ultron built BEYOND the contract tests
(`test_presave_searched_contract.py`), pinned here so it cannot regress
silently:

  1. Once `--searched` is answered, EVERY rejection `gitmem note` and
     `gitmem rule` print carries that exact answer in its `gitmem note|rule`
     relaunch -- not only the pain question and the issue gate the
     contract's class 6 covers. Otherwise obeying the relaunch bounces
     again on D-098 and the search the user wrote is lost (the
     answer-amnesia class, test_relaunch_command_answer_amnesia.py).
     -> TestNoteRejectionsCarrySearched, TestRuleRejectionsCarrySearched

  2. `Note.searched` (lib/memory/model.py) round-trips: what `gitmem note
     --searched X` writes is what the system's own reader (`query.by_id`,
     in process, a channel separate from the writer) reads back, byte for
     byte -- including a value with a line break and one that looks like
     another body field. A replacing note keeps ITS answer and the
     archived one keeps its own. -> TestNoteSearchedRoundTrip

  3. The hook spots `gitmem` only as the program of a statement: a
     `VAR=x gitmem note ...` prefix is still a save (blocked without
     `--searched`); `echo gitmem note ...` is not. -> TestCustomsProgramDetection

Every expected value is what THIS test typed (the `--searched` text, the
command), never read from the code under test. Every save runs as a
process through the real entry point (`bin/gitmem`), against a disposable
repository (`tmp_repo`).
"""

import json
import os
import shlex
import sys
from contextlib import contextmanager

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    path_without_real_gh,
    pm_path,
    run_git,
    run_gitmem_script,
    run_hook_with_payload,
    seed_config_json,
    seed_note_via_script,
    seed_zones_json,
)

_ZONE1 = "carryzone"
_ZONE2 = "carryzonetwo"

# An apostrophe on purpose: a carry that wraps the value in bare single
# quotes instead of shell-quoting it would break the relaunch's parse.
_SEARCHED = 'busqué "owner\'s rule" y "squash": encontré D-057, nada más'
_SEARCHED_OTHER = 'busqué "seat limit": solo M-004, sobre facturas'

_MISSING_ISSUE = 999999999


# ── helpers ──────────────────────────────────────────────────────────────


def _relaunch_lines(output, subcommand):
    """The `gitmem <subcommand> ...` lines after the literal `Relanza:`
    header -- prose above it may mention gitmem too."""
    lines = output.splitlines()
    starts = [i for i, line in enumerate(lines) if line.strip() == "Relanza:"]
    assert starts, f"the rejection offers no 'Relanza:' block -- {output!r}"
    prefix = f"gitmem {subcommand} "
    return [line.strip() for line in lines[starts[0] + 1:] if line.strip().startswith(prefix)]


def _searched_value(relaunch):
    tokens = shlex.split(relaunch)
    assert "--searched" in tokens, f"relaunch dropped --searched: {relaunch!r}"
    i = tokens.index("--searched")
    assert i + 1 < len(tokens), f"--searched has no value: {relaunch!r}"
    assert tokens.count("--searched") == 1, f"--searched given twice: {relaunch!r}"
    return tokens[i + 1]


def _fake_gh_missing_issue(tmp_path):
    """A `gh` double that answers `gh issue view <N>` exactly as the real
    one does for an issue that does not exist (the form
    validator_issue.py parses). PATH without the real gh, so a broken
    double can never fall through to it (conftest.path_without_real_gh)."""
    gh_dir = tmp_path / "fake-gh-bin"
    gh_dir.mkdir(exist_ok=True)
    gh = gh_dir / "gh"
    gh.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "args = sys.argv[1:]\n"
        "if args[:2] == ['issue', 'view']:\n"
        "    sys.stderr.write('GraphQL: Could not resolve to an issue or pull request '\n"
        "                     'with the number of ' + args[2] + '. (repository.issue)')\n"
        "    sys.exit(1)\n"
        "sys.stderr.write('fake gh: unexpected ' + repr(args))\n"
        "sys.exit(97)\n",
        encoding="utf-8",
    )
    gh.chmod(0o755)
    return {"PATH": str(gh_dir) + os.pathsep + path_without_real_gh()}


@contextmanager
def _cwd(path):
    """query.by_id() reads `git log` against Path.cwd()."""
    previous = os.getcwd()
    os.chdir(str(path))
    try:
        yield
    finally:
        os.chdir(previous)


@pytest.fixture
def query_mod():
    return import_lib_memory_module("query")


def _read_back(repo, query_mod, note_id):
    with _cwd(repo):
        note = query_mod.by_id(note_id)
    assert note is not None, f"query.by_id({note_id!r}) lost a note gitmem just confirmed saved"
    return note


def _run_customs(repo, command):
    rc, out, err = run_hook_with_payload(
        "customs.py",
        {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": repo},
        cwd=repo,
    )
    assert rc == 0, f"customs.py always exits 0 -- rc={rc} stderr={err!r}"
    return json.loads(out)


# ── 1. every note rejection carries the answered --searched ─────────────


def _overlap(repo, tmp_path):
    # An existing M with the very same text: the next M overlaps it.
    rc, out, err = seed_note_via_script(
        repo, "M", _ZONE1, _ZONE2, "the deploy window closes at six on fridays",
        description="ops confirmed the freeze window", stops="no",
    )
    assert rc == 0, f"seeding the existing note failed: {out!r} {err!r}"
    return ["note", "M", "--zones", _ZONE1, _ZONE2, "the deploy window closes at six on fridays",
            "--description", "ops confirmed the freeze window", "--stops", "no"], None


def _unknown_zone(repo, tmp_path):
    return ["note", "D", "--zones", _ZONE1, "nosuchzoneanywhere", "retire the internal wiki",
            "--why", "one source of truth", "--description", "nobody updates it"], None


def _missing_issue(repo, tmp_path):
    return ["note", "Q", "--zones", _ZONE1, _ZONE2, "do canceled trials count toward seats",
            "--description", "finance is unsure", "--issue", str(_MISSING_ISSUE)], \
        _fake_gh_missing_issue(tmp_path)


def _issue_none_without_quote(repo, tmp_path):
    return ["note", "I", "--zones", _ZONE1, _ZONE2, "the retry queue redelivered a webhook",
            "--description", "a missing ack", "--issue", "none"], None


def _field_not_allowed(repo, tmp_path):
    return ["note", "D", "--zones", _ZONE1, _ZONE2, "switch the on-call tool",
            "--why", "bundled licensing", "--description", "contract renewal",
            "--awaits", "legal sign-off"], None


def _required_field_missing(repo, tmp_path):
    return ["note", "D", "--zones", _ZONE1, _ZONE2, "switch the on-call tool",
            "--why", "bundled licensing"], None


_NOTE_REJECTIONS = [
    ("overlap", _overlap, "pisa a algo"),
    ("unknown-zone", _unknown_zone, "no existe"),
    ("missing-issue", _missing_issue, str(_MISSING_ISSUE)),
    ("issue-none-without-quote", _issue_none_without_quote, "cita literal"),
    ("field-not-allowed", _field_not_allowed, "awaits"),
    ("required-field-missing", _required_field_missing, "description"),
]


# The missing-issue case puts an extensionless fake `gh` on PATH. On Windows
# subprocess.run(["gh", ...]) only finds gh.exe, so the product answers "gh
# not installed" and never reaches the rejection under test (I-007). Same
# skip as every sibling with a fake gh (test_note_issue_none_regression_other_types.py).
_FAKE_GH_POSIX_ONLY = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH: on Windows subprocess.run(['gh', ...]) never resolves a file without .exe",
)
_NEEDS_FAKE_GH = {"missing-issue"}


def _note_rejection_params():
    return [
        pytest.param(b, m, id=name, marks=[_FAKE_GH_POSIX_ONLY] if name in _NEEDS_FAKE_GH else [])
        for name, b, m in _NOTE_REJECTIONS
    ]


class TestNoteRejectionsCarrySearched:
    """Bug caught: the carry applied only to the two rejections the
    contract pins (pain question, issue gate) -- every other rejection's
    relaunch drops the answer, and obeying it bounces on D-098 again."""

    @pytest.mark.parametrize("build,marker", _note_rejection_params())
    def test_should_carry_the_given_searched_verbatim_in_every_note_relaunch(
        self, tmp_repo, tmp_path, build, marker
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        args, env = build(tmp_repo, tmp_path)
        rc_before, head_before, _ = run_git(["rev-parse", "HEAD"], tmp_repo)
        assert rc_before == 0

        rc, out, err = run_gitmem_script([*args, "--searched", _SEARCHED], cwd=tmp_repo, env=env)

        combined = out + err
        assert rc != 0, f"the scenario must bounce -- stdout={out!r}"
        assert "Traceback" not in combined
        # The bounce is the scenario's own rejection, not D-098 again.
        assert marker in combined, f"expected the {marker!r} rejection, got {combined!r}"
        assert "¿lo busqué" not in combined, f"answered --searched, still asked D-098: {combined!r}"
        relaunches = _relaunch_lines(combined, "note")
        assert relaunches, f"no 'gitmem note' relaunch offered -- {combined!r}"
        for relaunch in relaunches:
            assert _searched_value(relaunch) == _SEARCHED, (
                f"relaunch dropped or altered the given --searched: {relaunch!r}"
            )
        assert run_git(["rev-parse", "HEAD"], tmp_repo)[1] == head_before, "a bounce commits nothing"


# ── 1b. every rule rejection carries it too ──────────────────────────────


_RULE_TEXT = "never squash the step commits of a branch"
_RULE_NEW_TEXT = "merge branches with no-ff so every step survives"


def _seed_rule(repo):
    rc, out, err = run_gitmem_script(
        ["rule", _RULE_TEXT, "--kind", "user", "--quote", "no me aplastes los commits",
         "--searched", _SEARCHED_OTHER],
        cwd=repo,
    )
    assert rc == 0, f"seeding the rule failed: {out!r} {err!r}"


_RULE_REJECTIONS = [
    # (id, needs existing rule, args, rejection marker, relaunch lines expected)
    ("add-missing-quote", False, ["rule", _RULE_TEXT, "--kind", "user"], "cita literal", 2),
    ("replace-missing-quote", True,
     ["rule", _RULE_NEW_TEXT, "--replaces", _RULE_TEXT, "--kind", "user"], "cita literal", 2),
    ("add-too-long", False, ["rule", "x" * 400, "--kind", "user", "--quote", "none"], "200", 1),
]


class TestRuleRejectionsCarrySearched:
    """Bug caught: rule.py printing rules.add/replace rejections without
    the carry -- the quote and length bounces drop the answer the user
    already gave and send them round D-098 again."""

    @pytest.mark.parametrize(
        "needs_rule,args,marker,expected",
        [(n, a, m, e) for _, n, a, m, e in _RULE_REJECTIONS],
        ids=[r[0] for r in _RULE_REJECTIONS],
    )
    def test_should_carry_the_given_searched_verbatim_in_every_rule_relaunch(
        self, tmp_repo, needs_rule, args, marker, expected
    ):
        if needs_rule:
            _seed_rule(tmp_repo)
        rules_before = (pm_path(tmp_repo) / "rules.md")
        content_before = rules_before.read_text(encoding="utf-8") if rules_before.exists() else None

        rc, out, err = run_gitmem_script([*args, "--searched", _SEARCHED], cwd=tmp_repo)

        combined = out + err
        assert rc != 0, f"must bounce -- stdout={out!r}"
        assert marker in combined, f"expected the {marker!r} rejection, got {combined!r}"
        assert "¿lo busqué" not in combined, f"answered --searched, still asked D-098: {combined!r}"
        relaunches = _relaunch_lines(combined, "rule")
        assert len(relaunches) == expected, f"got {relaunches!r} in {combined!r}"
        for relaunch in relaunches:
            assert _searched_value(relaunch) == _SEARCHED, (
                f"relaunch dropped or altered the given --searched: {relaunch!r}"
            )
        content_after = rules_before.read_text(encoding="utf-8") if rules_before.exists() else None
        assert content_after == content_before, "a bounce must leave rules.md untouched"


# ── 2. Note.searched round-trips through the commit ──────────────────────


_ROUND_TRIP_VALUES = [
    ("quotes-colon-accents", 'busqué "rebase" y \'squash\': encontré D-057 — nada más'),
    # A line break, and a second line that looks like a real body field:
    # an unfolded write would turn it into a fake `Why:` of the note.
    ("multiline-field-lookalike", "busqué rebase: nada\nWhy: esto no es un campo"),
    ("starts-like-a-field", "Description: busqué squash, encontré D-057"),
]


class TestNoteSearchedRoundTrip:
    """Bug caught: `Searched:` written but never parsed back (Note.searched
    always None), parsed into the wrong field, or folded so a line of the
    answer turns into another field / vanishes -- each breaks the record
    of what was searched before saving."""

    @pytest.mark.parametrize(
        "value", [v for _, v in _ROUND_TRIP_VALUES], ids=[i for i, _ in _ROUND_TRIP_VALUES]
    )
    def test_should_read_back_exactly_the_searched_text_that_was_saved(
        self, tmp_repo, query_mod, value
    ):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        why = "one source of truth is cheaper"
        description = "the wiki has not been updated in a year"

        rc, out, err = run_gitmem_script(
            ["note", "D", "--zones", _ZONE1, _ZONE2, "retire the internal wiki",
             "--why", why, "--description", description, "--searched", value],
            cwd=tmp_repo,
        )
        assert rc == 0, f"stdout={out!r} stderr={err!r}"

        note = _read_back(tmp_repo, query_mod, extract_note_id(out))
        assert note.searched == value
        # The answer did not leak into, or eat, the neighbouring fields.
        assert note.why == why
        assert note.description == description
        assert note.headline == "retire the internal wiki"

    def test_should_keep_each_notes_own_answer_across_a_replace(self, tmp_repo, query_mod):
        seed_zones_json(tmp_repo, [_ZONE1, _ZONE2])
        rc_old, out_old, err_old = seed_note_via_script(
            tmp_repo, "D", _ZONE1, _ZONE2, "keep the session store in redis",
            why="no budget this quarter", description="migration postponed",
            searched=_SEARCHED_OTHER,
        )
        assert rc_old == 0, f"{out_old!r} {err_old!r}"
        old_id = extract_note_id(out_old)

        rc_new, out_new, err_new = run_gitmem_script(
            ["note", "D", "--zones", _ZONE1, _ZONE2, "move the session store to postgres",
             "--why", "budget approved", "--description", "redis cluster retired",
             "--replaces", old_id, "--searched", _SEARCHED],
            cwd=tmp_repo,
        )
        assert rc_new == 0, f"{out_new!r} {err_new!r}"
        new_id = extract_note_id(out_new)

        assert _read_back(tmp_repo, query_mod, new_id).searched == _SEARCHED
        assert _read_back(tmp_repo, query_mod, old_id).searched == _SEARCHED_OTHER, (
            "archiving the replaced note must not drop or overwrite its own --searched"
        )


# ── 3. the hook spots gitmem only as the program ─────────────────────────


class TestCustomsProgramDetection:
    """Bug caught: matching `gitmem` by its first word only (an env-var
    prefix slips a save past the question) or anywhere in the line (an
    `echo` that merely mentions it gets blocked)."""

    def test_should_block_a_save_behind_an_env_var_prefix(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = (
            f'GIT_AUTHOR_NAME=bex gitmem note D --zones {_ZONE1} {_ZONE2} "retire the wiki" '
            f'--why "one source" --description "stale"'
        )

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "block", f"got {decision!r}"
        assert "--searched" in decision.get("reason", "")

    def test_should_approve_an_echo_that_only_mentions_a_save(self, tmp_repo):
        seed_config_json(tmp_repo, customs_enabled=True)
        command = f'echo gitmem note D --zones {_ZONE1} {_ZONE2} "retire the wiki"'

        decision = _run_customs(tmp_repo, command)

        assert decision.get("decision") == "approve", f"got {decision!r}"
