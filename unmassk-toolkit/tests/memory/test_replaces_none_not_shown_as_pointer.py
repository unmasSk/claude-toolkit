"""R.17 3.4: a note stored with `--replaces none` points at nothing.

Contract (plan 3.4, Cerberus pre-existing, Argus SEC-LOW-001): `none` means
"both live", never a note called "none"; `gitmem search` never shows
`(↺ none)`, `sustituye a none` or `replaces none` for it. A real
`--replaces <id>` keeps its marks.

Driven through `bin/gitmem` on a throwaway repo.
"""

import pytest

from .conftest import extract_note_id, run_gitmem_script, seed_zones_json, with_searched

ZONES = ("install", "cache")
WORD = "nested"
OLD_HEADLINE = "the cache sync skips nested plugin folders on install"
NEW_HEADLINE = "the cache sync skips nested plugin folders during install"
DESCRIPTION = "nested folders under the plugin cache are never copied by the sync"
ANSWERS = {
    "D": ["--why", "picked the recursive walk over a flat copy"],
    "M": ["--stops", "no"],
    "R": ["--stops", "yes"],
    "Q": ["--work", "no"],
    "X": [],
    "I": ["--work", "no"],
    "B": ["--awaits", "the upstream installer release"],
}
NONE_POINTERS = ("(↺ none)", "sustituye a none", "replaces none")


def _gitmem(args, repo):
    rc, out, err = run_gitmem_script(args, cwd=repo)
    combined = out + err
    assert "Traceback" not in combined, combined
    assert rc == 0, combined
    return combined


def _save(repo, note_type, headline, *extra):
    out = _gitmem(with_searched([
        "note", note_type, "--zones", *ZONES, headline,
        "--description", DESCRIPTION, *ANSWERS[note_type], *extra,
    ]), repo)
    return extract_note_id(out)


def _seed_pair(repo, note_type, replaces):
    seed_zones_json(repo, list(ZONES))
    old_id = _save(repo, note_type, OLD_HEADLINE)
    answer = old_id if replaces == "id" else "none"
    new_id = _save(repo, note_type, NEW_HEADLINE, "--replaces", answer)
    return old_id, new_id


def _views(repo, new_id):
    return {
        "search --id": _gitmem(["search", "--id", new_id], repo),
        "zone search": _gitmem(["search", ZONES[0]], repo),
        "word search": _gitmem(["search", WORD], repo),
        "chain view": _gitmem(["search", WORD, "--chain"], repo),
    }


class TestReplacesNoneIsNotAPointer:
    @pytest.mark.parametrize("note_type", ["D", "M", "R", "Q", "X", "I", "B"])
    def test_should_show_no_none_pointer_in_any_search_view_when_note_coexists(self, tmp_repo, note_type):
        _old_id, new_id = _seed_pair(tmp_repo, note_type, "none")

        views = _views(tmp_repo, new_id)

        leaks = {
            view: marker
            for view, text in views.items()
            for marker in NONE_POINTERS
            if marker in text
        }
        assert leaks == {}, f"{new_id} (--replaces none) shown as pointing at a note called none: {leaks}"
        assert new_id in views["search --id"] and new_id in views["zone search"], views


class TestReplacesByIdKeepsItsMarks:
    @pytest.mark.parametrize("note_type", ["D", "M", "R"])
    def test_should_still_show_the_replaced_id_when_note_replaces_by_id(self, tmp_repo, note_type):
        old_id, new_id = _seed_pair(tmp_repo, note_type, "id")

        views = _views(tmp_repo, new_id)

        assert f"sustituye a {old_id}" in views["search --id"], views["search --id"]
        assert f"(↺ {old_id})" in views["word search"], views["word search"]
