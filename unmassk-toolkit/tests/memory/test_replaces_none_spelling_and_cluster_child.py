"""R.17 4.2: `none` in `--replaces` is a word, whatever its case, and never a pointer.

Contract (D-164; the owner's rule that every compared text is lowercased):
`--replaces None` or `NONE` is the coexist answer, saved as `Replaces: none`,
both notes live. Moriarty's BREAK 7. A note saved with `--replaces none`
that shows as the child of a cluster is shown with no `replaces none` pointer
(Moriarty's surviving mutant M10, report_render.py cluster child).

Driven through `bin/gitmem` on a throwaway repo; read back with plain git,
the real index reader and `gitmem search`.
"""

import pytest

from .conftest import extract_note_id, import_lib_memory_module, pm_path
from .relaunch_fidelity_support import (
    DESCRIPTION,
    NEW_HEADLINE,
    OLD_HEADLINE,
    WHY,
    gitmem,
    note_args,
    saved_fields,
    seed,
    seed_zones,
)

KEYS = ("recursion", "walker")
GIVEN = {
    "D": {"--description": DESCRIPTION, "--why": WHY, "--keys": KEYS},
    "X": {"--description": DESCRIPTION, "--keys": KEYS},
    "Q": {"--description": DESCRIPTION, "--keys": KEYS, "--work": "no"},
}
# Index file of each type, typed by hand from the memory skill's table.
INDEX_OF = {"D": "DECISIONS.md", "X": "DISCARDED.md", "Q": "QUESTIONS.md"}


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


class TestReplacesNoneIgnoresCase:
    @pytest.mark.parametrize("note_type,spelling", [("X", "None"), ("D", "NONE"), ("Q", "None")])
    def test_should_coexist_and_store_lowercase_none_when_replaces_none_is_capitalised(
        self, tmp_repo, indexes, note_type, spelling
    ):
        seed_zones(tmp_repo)
        old_id = seed(tmp_repo, None, note_type, OLD_HEADLINE, GIVEN[note_type])

        rc, out = gitmem(
            note_args(note_type, NEW_HEADLINE, {**GIVEN[note_type], "--replaces": spelling}), tmp_repo, None
        )

        assert rc == 0, f"--replaces {spelling} was not taken as none: {out}"
        new_id = extract_note_id(out)
        live = {line.id for line in indexes.read(INDEX_OF[note_type], pm_path(tmp_repo))}
        assert {old_id, new_id} <= live
        assert old_id not in indexes.archived_ids(pm_path(tmp_repo))
        assert saved_fields(tmp_repo, new_id)["Replaces"] == "none"


class TestClusterChildShowsNoNonePointer:
    def test_should_show_no_replaces_none_when_a_coexisting_note_is_a_cluster_child(self, tmp_repo):
        seed_zones(tmp_repo)
        zones = ("memory", "docs")
        first = seed(tmp_repo, None, "D", "docs build on every push",
                     {"--description": "ci builds docs", "--why": "fresh docs", "--keys": ("docsci",)}, zones=zones)
        second = seed(tmp_repo, None, "D", "docs build on every push to main",
                      {"--description": "ci builds docs on main", "--why": "fresh docs", "--keys": ("docsci",),
                       "--replaces": "none"}, zones=zones)
        seed(tmp_repo, None, "X", "build docs nightly instead",
             {"--description": "too stale", "--why": "stale for a day", "--keys": ("nightly",),
              "--origin": (first, second)}, zones=zones)

        rc, view = gitmem(["search", "docs"], tmp_repo, None)

        assert rc == 0, view
        assert second in view, view
        assert "replaces none" not in view, view
