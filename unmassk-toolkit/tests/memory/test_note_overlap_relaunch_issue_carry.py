"""R.17 3.4: the overlap and issue-gate relaunches keep every answer given.

Contract (plan 3.4, Cerberus F1/F2, Argus SEC-MED-001, D-164): the overlap
relaunch carries `--issue` and `--quote`; never `--work no` beside
`--issue N`; the issue-gate relaunch carries `--replaces`, `--why`, `--keys`,
`--origin`, so the two rejections never send each other back and forth.

Driven through `bin/gitmem` on a throwaway repo, with a fake `gh` on PATH.
"""

import os
import shlex
import sys

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    path_without_real_gh,
    pm_path,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH: subprocess.run(['gh', ...]) never resolves a file without .exe on Windows",
)

ZONES = ("install", "cache")
OLD_HEADLINE = "the cache sync skips nested plugin folders on install"
NEW_HEADLINE = "the cache sync skips nested plugin folders during install"
DESCRIPTION = "nested folders under the plugin cache are never copied by the sync"
QUOTE = "no abras issue para esto, lo arreglo yo a mano el lunes"
WHY = "picked the recursive walk over a flat copy"
KEYS = ("recursion", "plugincache")
REAL_ISSUE = "5"
MISSING_ISSUE = "999"
FILLED = {
    "--why": "filled why for the relaunch",
    "--description": DESCRIPTION,
    "--awaits": "the upstream installer release",
}

ALL_TYPES = ("D", "M", "R", "Q", "X", "I", "B")
GATE_TYPES = ("Q", "I")
# Answers each type needs before the overlap gate, except the issue gate.
BASE_ANSWERS = {
    "D": ["--why", WHY],
    "M": ["--stops", "no"],
    "R": ["--stops", "yes"],
    "Q": [],
    "X": [],
    "I": [],
    "B": ["--awaits", FILLED["--awaits"]],
}
INDEX_OF = {
    "D": "DECISIONS.md", "M": "MEMOS.md", "R": "RESTRICTIONS.md",
    "Q": "QUESTIONS.md", "X": "DISCARDED.md", "I": "INCIDENTS.md",
    "B": "BLOCKED.md",
}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def gh_env(tmp_path):
    gh_dir = tmp_path / "fake-gh-bin"
    gh_dir.mkdir()
    script = gh_dir / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['issue', 'view'] and a[2:3] == [%r]:\n"
        "    print('{\"number\": %s}'); sys.exit(0)\n"
        "if a[:2] == ['issue', 'view'] and a[2:3] == [%r]:\n"
        "    sys.stderr.write('GraphQL: Could not resolve to an issue or pull request with the number of %s. (repository.issue)')\n"
        "    sys.exit(1)\n"
        "sys.stderr.write('fake gh: unexpected ' + repr(a)); sys.exit(97)\n"
        % (REAL_ISSUE, REAL_ISSUE, MISSING_ISSUE, MISSING_ISSUE),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return {"PATH": str(gh_dir) + os.pathsep + path_without_real_gh()}


def _gitmem(args, repo, env):
    rc, out, err = run_gitmem_script(args, cwd=repo, env=env)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, combined


def _args(note_type, headline, *extra):
    return with_searched([
        "note", note_type, "--zones", *ZONES, headline,
        "--description", DESCRIPTION, *BASE_ANSWERS[note_type], *extra,
    ])


def _seed_old(repo, note_type, env):
    seed_zones_json(repo, list(ZONES))
    gate = ["--work", "no"] if note_type in GATE_TYPES else []
    rc, out = _gitmem(_args(note_type, OLD_HEADLINE, *gate), repo, env)
    assert rc == 0, f"seeding the old {note_type} failed: {out}"
    return extract_note_id(out)


def _relaunches(output):
    assert "Relanza:" in output, output
    after = output.rsplit("Relanza:", 1)[1]
    return [
        shlex.split(line.strip())[1:]
        for line in after.splitlines()
        if line.strip().startswith("gitmem note ")
    ]


def _single_relaunch(output):
    commands = _relaunches(output)
    assert len(commands) == 1, f"expected one gitmem note relaunch: {output}"
    return commands[0]


def _fill(tokens):
    filled = list(tokens)
    for i, token in enumerate(filled):
        if token == "...":
            assert filled[i - 1] in FILLED, f"unexpected hole after {filled[i - 1]!r}: {tokens}"
            filled[i] = FILLED[filled[i - 1]]
    return filled


def _flag_values(tokens, flag):
    return [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == flag]


def _keys_after(tokens):
    assert "--keys" in tokens, tokens
    start = tokens.index("--keys") + 1
    taken = []
    for token in tokens[start:]:
        if token.startswith("--"):
            break
        taken.append(token)
    return taken


def _live_ids(indexes, repo, note_type):
    return {line.id for line in indexes.read(INDEX_OF[note_type], pm_path(repo))}


class TestOverlapRelaunchKeepsTheIssueAnswer:
    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_carry_issue_none_and_quote_and_no_work_when_gate_type_overlaps(
        self, tmp_repo, gh_env, note_type
    ):
        _seed_old(tmp_repo, note_type, gh_env)
        rc, out = _gitmem(
            _args(note_type, NEW_HEADLINE, "--issue", "none", "--quote", QUOTE), tmp_repo, gh_env
        )
        assert rc != 0, f"the new {note_type} should bounce as overlapping: {out}"
        tokens = _single_relaunch(out)

        assert _flag_values(tokens, "--issue") == ["none"], tokens
        assert _flag_values(tokens, "--quote") == [QUOTE], tokens
        assert "--work" not in tokens, tokens

    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_save_with_the_quote_when_issue_none_relaunch_is_pasted(
        self, tmp_repo, gh_env, indexes, note_type
    ):
        old_id = _seed_old(tmp_repo, note_type, gh_env)
        _rc, out = _gitmem(
            _args(note_type, NEW_HEADLINE, "--issue", "none", "--quote", QUOTE), tmp_repo, gh_env
        )

        rc, saved = _gitmem(_fill(_single_relaunch(out)), tmp_repo, gh_env)

        assert rc == 0, f"the pasted relaunch bounced: {saved}"
        new_id = extract_note_id(saved)
        assert {old_id, new_id} <= _live_ids(indexes, tmp_repo, note_type)
        _rc_s, found = _gitmem(["search", "--id", new_id], tmp_repo, gh_env)
        assert QUOTE in found, found

    @pytest.mark.parametrize("note_type", ALL_TYPES)
    def test_should_carry_issue_number_and_no_work_when_type_overlaps(self, tmp_repo, gh_env, note_type):
        _seed_old(tmp_repo, note_type, gh_env)
        rc, out = _gitmem(_args(note_type, NEW_HEADLINE, "--issue", REAL_ISSUE), tmp_repo, gh_env)
        assert rc != 0, f"the new {note_type} should bounce as overlapping: {out}"
        tokens = _single_relaunch(out)

        assert _flag_values(tokens, "--issue") == [REAL_ISSUE], tokens
        assert "--work" not in tokens, tokens

    @pytest.mark.parametrize("note_type", ALL_TYPES)
    def test_should_keep_the_issue_link_when_issue_number_relaunch_is_pasted(
        self, tmp_repo, gh_env, note_type
    ):
        _seed_old(tmp_repo, note_type, gh_env)
        _rc, out = _gitmem(_args(note_type, NEW_HEADLINE, "--issue", REAL_ISSUE), tmp_repo, gh_env)

        rc, saved = _gitmem(_fill(_single_relaunch(out)), tmp_repo, gh_env)

        assert rc == 0, f"the pasted relaunch bounced: {saved}"
        new_id = extract_note_id(saved)
        _rc_s, found = _gitmem(["search", "--id", new_id], tmp_repo, gh_env)
        assert f"Issue: #{REAL_ISSUE}" in found, f"{new_id} lost its issue link: {found}"


class TestContradictionRelaunchKeepsIssueAndWorkApart:
    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_not_put_work_on_the_issue_line_when_both_were_given(self, tmp_repo, gh_env, note_type):
        seed_zones_json(tmp_repo, list(ZONES))
        rc, out = _gitmem(
            _args(note_type, NEW_HEADLINE, "--issue", REAL_ISSUE, "--work", "no"), tmp_repo, gh_env
        )
        assert rc != 0, out
        lines = _relaunches(out)
        issue_lines = [t for t in lines if "--issue" in t]
        work_lines = [t for t in lines if "--work" in t]

        assert issue_lines and work_lines, lines
        assert all("--work" not in t for t in issue_lines), issue_lines
        assert all("--issue" not in t for t in work_lines), work_lines


class TestIssueGateRelaunchKeepsTheOtherAnswers:
    @pytest.mark.parametrize("trigger", [[], ["--issue", "none"]], ids=["no-answer", "issue-none-no-quote"])
    def test_should_carry_replaces_and_keys_on_every_q_gate_line(self, tmp_repo, gh_env, trigger):
        seed_zones_json(tmp_repo, list(ZONES))
        rc, out = _gitmem(
            _args("Q", NEW_HEADLINE, *trigger, "--replaces", "none", "--keys", *KEYS), tmp_repo, gh_env
        )
        assert rc != 0, out
        lines = _relaunches(out)

        assert lines, out
        for tokens in lines:
            assert _flag_values(tokens, "--replaces") == ["none"], tokens
            assert set(KEYS) <= set(_keys_after(tokens)), tokens

    def test_should_carry_why_replaces_and_keys_on_every_i_gate_line(self, tmp_repo, gh_env):
        seed_zones_json(tmp_repo, list(ZONES))
        rc, out = _gitmem(
            _args("I", NEW_HEADLINE, "--why", WHY, "--replaces", "none", "--keys", *KEYS), tmp_repo, gh_env
        )
        assert rc != 0, out
        lines = _relaunches(out)

        assert lines, out
        for tokens in lines:
            assert _flag_values(tokens, "--why") == [WHY], tokens
            assert _flag_values(tokens, "--replaces") == ["none"], tokens
            assert set(KEYS) <= set(_keys_after(tokens)), tokens

    @pytest.mark.parametrize(
        "trigger",
        [["--work", "no"], ["--issue", "none"], ["--issue", MISSING_ISSUE]],
        ids=["work-not-allowed", "issue-none-not-allowed", "issue-not-found"],
    )
    def test_should_carry_why_keys_origin_and_replaces_when_d_bounces_on_the_issue_check(
        self, tmp_repo, gh_env, trigger
    ):
        old_id = _seed_old(tmp_repo, "D", gh_env)
        rc, out = _gitmem(
            _args("D", NEW_HEADLINE, *trigger, "--keys", *KEYS, "--origin", old_id, "--replaces", old_id),
            tmp_repo, gh_env,
        )
        assert rc != 0, out
        lines = _relaunches(out)

        assert lines, out
        for tokens in lines:
            assert _flag_values(tokens, "--why") == [WHY], tokens
            assert _flag_values(tokens, "--origin") == [old_id], tokens
            assert _flag_values(tokens, "--replaces") == [old_id], tokens
            assert set(KEYS) <= set(_keys_after(tokens)), tokens


class TestNoPingPongBetweenTheTwoRejections:
    @pytest.mark.parametrize("note_type", GATE_TYPES)
    def test_should_save_when_the_work_no_gate_relaunch_is_pasted_after_replaces_none(
        self, tmp_repo, gh_env, indexes, note_type
    ):
        old_id = _seed_old(tmp_repo, note_type, gh_env)
        _rc, out = _gitmem(_args(note_type, NEW_HEADLINE, "--replaces", "none"), tmp_repo, gh_env)
        work_lines = [t for t in _relaunches(out) if _flag_values(t, "--work") == ["no"]]
        assert len(work_lines) == 1, out

        rc, saved = _gitmem(_fill(work_lines[0]), tmp_repo, gh_env)

        assert rc == 0, f"the pasted gate relaunch bounced: {saved}"
        new_id = extract_note_id(saved)
        assert {old_id, new_id} <= _live_ids(indexes, tmp_repo, note_type)
