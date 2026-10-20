"""Shared helpers of the R.17 step 4.2 relaunch-fidelity tests. Not a test module.

The rule under test: a relaunch pasted as printed, with only the holes the
user must fill, saves exactly what the user first gave -- never a
placeholder as content, never a field dropped. The expected values come
from the first invocation's arguments, typed by the test, never from the
relaunch or from a filler.
"""

import os
import re
import shlex

import pytest

from .conftest import (
    extract_note_id,
    path_without_real_gh,
    run_git,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

ZONES = ("install", "cache")
ANCHOR_ZONES = ("memory", "docs")
OLD_HEADLINE = "the cache sync skips nested plugin folders on install"
NEW_HEADLINE = "the cache sync skips nested plugin folders during install"
DESCRIPTION = "nested folders under the plugin cache are never copied by the sync"
WHY = "picked the recursive walk over a flat copy"
KEYS = ("recursion", "walker")
QUOTE = "no abras issue para esto, lo arreglo yo a mano el lunes"
AWAITS = "the upstream installer release"
REAL_ISSUE = "5"

# Flag -> commit-body field, from the memory skill's field table.
FIELD_OF = {
    "--why": "Why",
    "--description": "Description",
    "--origin": "Origin",
    "--awaits": "Awaits",
    "--quote": "Quote",
    "--replaces": "Replaces",
}
_PLACEHOLDER = re.compile(r"^(\.\.\.|<[^>]*>)$")


@pytest.fixture
def gh_env(tmp_path):
    """Fake `gh` on PATH: issue 5 exists, anything else is an error."""
    gh_dir = tmp_path / "fake-gh-bin"
    gh_dir.mkdir()
    script = gh_dir / "gh"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import sys\n"
        "a = sys.argv[1:]\n"
        "if a[:2] == ['issue', 'view'] and a[2:3] == [%r]:\n"
        "    print('{\"number\": %s}'); sys.exit(0)\n"
        "sys.stderr.write('fake gh: unexpected ' + repr(a)); sys.exit(97)\n"
        % (REAL_ISSUE, REAL_ISSUE),
        encoding="utf-8",
    )
    script.chmod(0o755)
    return {"PATH": str(gh_dir) + os.pathsep + path_without_real_gh()}


def gitmem(args, repo, env):
    rc, out, err = run_gitmem_script(args, cwd=repo, env=env)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, combined


def note_args(note_type, headline, given, zones=ZONES):
    """`gitmem note` argv from `given` (flag -> value, or tuple of values)."""
    args = ["note", note_type, "--zones", *zones, headline]
    for flag, value in given.items():
        args += [flag, *value] if isinstance(value, tuple) else [flag, value]
    return with_searched(args)


def seed(repo, env, note_type, headline, given, zones=ZONES):
    rc, out = gitmem(note_args(note_type, headline, given, zones), repo, env)
    assert rc == 0, f"seeding {note_type} {headline!r} failed: {out}"
    return extract_note_id(out)


def seed_zones(repo):
    seed_zones_json(repo, [*ZONES, *ANCHOR_ZONES])


def relaunch_lines(output, prefix="gitmem note "):
    """Every relaunch line printed after the last `Relanza:`, raw text."""
    assert "Relanza:" in output, output
    after = output.rsplit("Relanza:", 1)[1]
    return [line.strip() for line in after.splitlines() if line.strip().startswith(prefix)]


def tokens_of(line):
    """The argv a shell gives `gitmem` for a pasted line."""
    return shlex.split(line)[1:]


def single_relaunch(output, prefix="gitmem note "):
    lines = relaunch_lines(output, prefix)
    assert len(lines) == 1, f"expected one relaunch line: {output}"
    return tokens_of(lines[0])


def flag_values(tokens, flag):
    return [tokens[i + 1] for i, t in enumerate(tokens[:-1]) if t == flag]


def note_bodies(repo):
    """Every commit message of the throwaway repo, read with plain git."""
    rc, out, err = run_git(["log", "--format=%B%x1e"], repo)
    assert rc == 0, err
    return [body.strip() for body in out.split("\x1e") if body.strip()]


def saved_fields(repo, note_id):
    """The fields of `note_id`'s own commit, read with plain git.

    The `Description: Searched: ...` line is the `--searched` answer, not
    the description, and is left out.
    """
    bodies = [b for b in note_bodies(repo) if b.startswith(f"[{note_id}]")]
    assert len(bodies) == 1, f"expected one commit for {note_id}: {bodies}"
    fields = {}
    for line in bodies[0].splitlines()[1:]:
        name, sep, value = line.partition(": ")
        if not sep or (name == "Description" and value.startswith("Searched: ")):
            continue
        assert name not in fields, f"{note_id} has two {name} lines: {bodies[0]}"
        fields[name] = value
    return fields


def expected_fields(given, replaces=None):
    """The commit fields `given` (the user's first invocation) must produce."""
    fields = {FIELD_OF[f]: v for f, v in given.items() if f in FIELD_OF}
    if "--keys" in given:
        fields["Keys"] = ", ".join(given["--keys"])
    if given.get("--issue") not in (None, "none"):
        fields["Issue"] = f"#{given['--issue']}"
    if replaces is not None:
        fields["Replaces"] = replaces
    return fields


def placeholders_saved(repo):
    """Every `Field: value` line in the repo whose value is a relaunch hole."""
    return [
        line
        for body in note_bodies(repo)
        for line in body.splitlines()
        if _PLACEHOLDER.match(line.partition(": ")[2])
    ]
