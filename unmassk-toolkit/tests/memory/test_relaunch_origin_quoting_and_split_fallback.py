"""R.17 4.2: two relaunch pieces Ultron added beyond the tests.

1. `--origin` is shell-quoted in a relaunch: a non-id origin holding a
   space and a quote, pasted as printed, saves the origin the user gave
   (one value, the same text) -- never split into several, never a refused
   paste.
2. note.py reads which flags a relaunch already carries from its shell
   words; when the relaunch cannot be split into shell words (a quote in a
   zone name), it still sees the flags: the rejection is shown, nothing
   crashes, and a flag already in the relaunch is not added twice.

Expected values are the first invocation's arguments, typed by the test.
Driven through `bin/gitmem` on a throwaway repo, read back with plain git.
"""

import os
import sys

import pytest

from .conftest import extract_note_id, path_without_real_gh, seed_zones_json
from .relaunch_fidelity_support import (
    ANCHOR_ZONES,
    DESCRIPTION,
    KEYS,
    NEW_HEADLINE,
    OLD_HEADLINE,
    WHY,
    gh_env,  # noqa: F401 -- pytest fixture
    gitmem,
    note_args,
    relaunch_lines,
    saved_fields,
    seed,
    seed_zones,
    single_relaunch,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH: subprocess.run(['gh', ...]) never resolves a file without .exe on Windows",
)

FREE_ORIGIN = "Bex's old wiki page"
QUOTED_ZONE = "bex's"
MISSING_ISSUE = "7"


class TestOriginShellQuoted:
    def _bounce(self, repo, env):
        seed_zones(repo)
        seed(repo, env, "D", "an unrelated anchor decision",
             {"--description": "anchor", "--why": "anchor", "--keys": ("anchornote",)}, zones=ANCHOR_ZONES)
        base = {"--description": DESCRIPTION, "--why": WHY, "--keys": KEYS}
        seed(repo, env, "D", OLD_HEADLINE, base)
        given = {**base, "--origin": FREE_ORIGIN}
        rc, out = gitmem(note_args("D", NEW_HEADLINE, given), repo, env)
        assert rc != 0 and "esto pisa a algo" in out, f"expected the overlap rejection: {out}"
        return single_relaunch(out)

    def test_should_print_the_origin_as_one_shell_word(self, tmp_repo, gh_env):
        tokens = self._bounce(tmp_repo, gh_env)

        origin_at = tokens.index("--origin")
        assert tokens[origin_at + 1] == FREE_ORIGIN, tokens
        assert tokens[origin_at + 2].startswith("--"), tokens

    def test_should_save_the_given_origin_when_the_relaunch_is_pasted_as_printed(self, tmp_repo, gh_env):
        tokens = self._bounce(tmp_repo, gh_env)

        rc, out = gitmem(tokens, tmp_repo, gh_env)

        assert rc == 0, f"the printed relaunch was refused: {tokens}\n{out}"
        assert saved_fields(tmp_repo, extract_note_id(out))["Origin"] == FREE_ORIGIN


@pytest.fixture
def missing_issue_gh(tmp_path):
    """Fake `gh` on PATH answering every issue as real gh does for a missing one."""
    gh_dir = tmp_path / "missing-issue-gh-bin"
    gh_dir.mkdir()
    script = gh_dir / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "sys.stderr.write('GraphQL: Could not resolve to an issue or pull request with the number of '\n"
        "                 + sys.argv[3] + '. (repository.issue)\\n')\n"
        "sys.exit(1)\n",
        encoding="utf-8",
    )
    script.chmod(0o755)
    return {"PATH": str(gh_dir) + os.pathsep + path_without_real_gh()}


class TestUnsplittableRelaunch:
    def test_should_show_the_rejection_and_carry_the_issue_once_when_a_zone_holds_a_quote(
        self, tmp_repo, missing_issue_gh
    ):
        seed_zones_json(tmp_repo, [QUOTED_ZONE, "cache"])
        args = note_args("Q", NEW_HEADLINE, {"--description": DESCRIPTION, "--issue": MISSING_ISSUE},
                         zones=(QUOTED_ZONE, "cache"))

        rc, out = gitmem(args, tmp_repo, missing_issue_gh)

        assert rc != 0, out
        assert f"#{MISSING_ISSUE} no existe" in out, f"expected the missing-issue rejection: {out}"
        lines = relaunch_lines(out)
        assert len(lines) == 1, out
        assert lines[0].split().count("--issue") == 1, lines[0]
        assert QUOTED_ZONE in lines[0], f"precondition: the zone with a quote is in the relaunch: {lines[0]}"
