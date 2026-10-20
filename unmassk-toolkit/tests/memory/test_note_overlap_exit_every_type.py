"""R.17, D-164: every type can answer an overlap.

Contract (D-164, written by the owner's orchestrator, not read from code):
`--replaces none` (both live) is valid for all seven types; `--replaces <id>`
stays D, M and R only. The overlap bounce and its relaunch show only the
exits and fields the type accepts, so the relaunch pasted as printed (its
`"..."` holes filled) saves.

Driven through `bin/gitmem` on a throwaway repo; read back through the real
index reader, `gitmem search --id` and `gitmem rezones --verify`.
`remove`'s new-fence path is guarded by
`test_remove_replaces_guard_contract.py` (similar-wall relaunch pasted).
"""

import shlex

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

ZONES = ("install", "cache")
OLD_HEADLINE = "the cache sync skips nested plugin folders on install"
NEW_HEADLINE = "the cache sync skips nested plugin folders during install"
DESCRIPTION = "nested folders under the plugin cache are never copied by the sync"
FILLED = {
    "--why": "filled why for the relaunch",
    "--description": DESCRIPTION,
    "--awaits": "the upstream installer release",
}

# D-164, typed by hand: who may name an id, who may only coexist.
REPLACE_BY_ID = ("D", "M", "R")
COEXIST_ONLY = ("Q", "X", "I", "B")
ALL_TYPES = REPLACE_BY_ID + COEXIST_ONLY
# Types that take no --why (D-164: "hoy a una Q le mete --why").
NO_WHY = ("M", "Q", "B")
# Index file of each type, typed by hand from the memory skill's table.
INDEX_OF = {
    "D": "DECISIONS.md", "M": "MEMOS.md", "R": "RESTRICTIONS.md",
    "Q": "QUESTIONS.md", "X": "DISCARDED.md", "I": "INCIDENTS.md",
    "B": "BLOCKED.md",
}
# The answer each type needs before the overlap gate is reached.
TYPE_ANSWERS = {
    "D": ["--why", "picked the recursive walk over a flat copy"],
    "M": ["--stops", "no"],
    "R": ["--stops", "yes"],
    "Q": ["--work", "no"],
    "X": [],
    "I": ["--work", "no"],
    "B": ["--awaits", FILLED["--awaits"]],
}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _gitmem(args, repo):
    rc, out, err = run_gitmem_script(args, cwd=repo)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, combined


def _note_args(note_type, headline, *extra):
    return with_searched([
        "note", note_type, "--zones", *ZONES, headline,
        "--description", DESCRIPTION, *TYPE_ANSWERS[note_type], *extra,
    ])


def _seed_old(repo, note_type):
    seed_zones_json(repo, list(ZONES))
    rc, out = _gitmem(_note_args(note_type, OLD_HEADLINE), repo)
    assert rc == 0, f"seeding the old {note_type} failed: {out}"
    return extract_note_id(out)


def _bounce(repo, note_type):
    rc, out = _gitmem(_note_args(note_type, NEW_HEADLINE), repo)
    assert rc != 0, f"the new {note_type} should bounce as overlapping: {out}"
    return out


def _relaunch(output):
    assert "Relanza:" in output, output
    after = output.rsplit("Relanza:", 1)[1]
    commands = [line.strip() for line in after.splitlines() if line.strip().startswith("gitmem note ")]
    assert len(commands) == 1, f"expected one gitmem note relaunch: {output}"
    return shlex.split(commands[0])[1:]


def _fill(tokens):
    filled = list(tokens)
    for i, token in enumerate(filled):
        if token == "...":
            assert filled[i - 1] in FILLED, f"unexpected hole after {filled[i - 1]!r}: {tokens}"
            filled[i] = FILLED[filled[i - 1]]
    return filled


def _flag_values(tokens, flag):
    return [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == flag]


def _live_ids(indexes, repo, note_type):
    return {line.id for line in indexes.read(INDEX_OF[note_type], pm_path(repo))}


def _archived(indexes, repo):
    return indexes.archived_ids(pm_path(repo))


class TestCoexistOnlyTypesBounceWithExitsTheyAccept:
    @pytest.mark.parametrize("note_type", COEXIST_ONLY)
    def test_should_relaunch_with_replaces_none_never_an_id_when_type_overlaps(self, tmp_repo, note_type):
        old_id = _seed_old(tmp_repo, note_type)
        out = _bounce(tmp_repo, note_type)
        tokens = _relaunch(out)

        assert _flag_values(tokens, "--replaces") == ["none"], tokens
        assert old_id in out, "the bounce must still name the note it overlaps"

    @pytest.mark.parametrize("note_type", COEXIST_ONLY)
    def test_should_not_offer_the_replace_by_id_exit_when_type_overlaps(self, tmp_repo, note_type):
        _seed_old(tmp_repo, note_type)
        out = _bounce(tmp_repo, note_type)
        body = out.rsplit("Relanza:", 1)[0]

        assert "--replaces <id>" not in body, body
        assert "--replaces none" in body, body

    @pytest.mark.parametrize("note_type", NO_WHY)
    def test_should_not_put_why_in_relaunch_when_type_takes_no_why(self, tmp_repo, note_type):
        _seed_old(tmp_repo, note_type)
        tokens = _relaunch(_bounce(tmp_repo, note_type))

        assert "--why" not in tokens, tokens


class TestPastedRelaunchSaves:
    @pytest.mark.parametrize("note_type", COEXIST_ONLY)
    def test_should_save_and_keep_both_live_when_coexist_relaunch_is_pasted(self, tmp_repo, indexes, note_type):
        old_id = _seed_old(tmp_repo, note_type)
        tokens = _fill(_relaunch(_bounce(tmp_repo, note_type)))

        rc, out = _gitmem(tokens, tmp_repo)

        assert rc == 0, f"the pasted relaunch bounced: {out}"
        new_id = extract_note_id(out)
        assert {old_id, new_id} <= _live_ids(indexes, tmp_repo, note_type)
        assert old_id not in _archived(indexes, tmp_repo)

    @pytest.mark.parametrize("note_type", REPLACE_BY_ID)
    def test_should_replace_the_old_note_when_id_relaunch_is_pasted(self, tmp_repo, indexes, note_type):
        old_id = _seed_old(tmp_repo, note_type)
        tokens = _relaunch(_bounce(tmp_repo, note_type))
        assert _flag_values(tokens, "--replaces") == [old_id], tokens

        rc, out = _gitmem(_fill(tokens), tmp_repo)

        assert rc == 0, f"the pasted relaunch bounced: {out}"
        new_id = extract_note_id(out)
        live = _live_ids(indexes, tmp_repo, note_type)
        assert new_id in live and old_id not in live
        assert old_id in _archived(indexes, tmp_repo)


class TestReplacesNoneSavesForEveryType:
    @pytest.mark.parametrize("note_type", ALL_TYPES)
    def test_should_save_both_live_and_findable_when_replaces_none_given(self, tmp_repo, indexes, note_type):
        old_id = _seed_old(tmp_repo, note_type)

        rc, out = _gitmem(_note_args(note_type, NEW_HEADLINE, "--replaces", "none"), tmp_repo)

        assert rc == 0, f"--replaces none bounced for {note_type}: {out}"
        new_id = extract_note_id(out)
        assert {old_id, new_id} <= _live_ids(indexes, tmp_repo, note_type)
        assert old_id not in _archived(indexes, tmp_repo)
        rc_s, found = _gitmem(["search", "--id", new_id], tmp_repo)
        assert rc_s == 0 and new_id in found and NEW_HEADLINE in found, found
        rc_v, verify = _gitmem(["rezones", "--verify"], tmp_repo)
        assert rc_v == 0, f"index check went red after the save: {verify}"


class TestReplacesByIdStaysForbiddenOutsideDMR:
    @pytest.mark.parametrize("note_type", COEXIST_ONLY)
    def test_should_reject_and_archive_nothing_when_type_names_an_id(self, tmp_repo, indexes, note_type):
        old_id = _seed_old(tmp_repo, note_type)
        before = _live_ids(indexes, tmp_repo, note_type)

        rc, out = _gitmem(_note_args(note_type, NEW_HEADLINE, "--replaces", old_id), tmp_repo)

        assert rc != 0, f"{note_type} must not take --replaces <id>: {out}"
        assert "replaces" in out, out
        assert _live_ids(indexes, tmp_repo, note_type) == before
        assert old_id not in _archived(indexes, tmp_repo)


class TestReplaceByIdTypesKeepTheirExits:
    @pytest.mark.parametrize("note_type", REPLACE_BY_ID)
    def test_should_still_offer_both_exits_when_type_overlaps(self, tmp_repo, note_type):
        _seed_old(tmp_repo, note_type)
        body = _bounce(tmp_repo, note_type).rsplit("Relanza:", 1)[0]

        assert "--replaces <id>" in body, body
        assert "--replaces none" in body, body
