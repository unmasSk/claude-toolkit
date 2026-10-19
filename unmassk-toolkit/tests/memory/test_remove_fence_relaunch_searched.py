"""Yoda's T3 on #95 step 2: the relaunch `gitmem remove ... --restriction
new` prints when the fence cannot be written must carry `--searched`.

`bin/memory/remove.py::_fence_retry_command` promises a command that can be
pasted as-is. Since D-098 every `gitmem note` save needs `--searched`; a
relaunch without it bounces once more, and the owner is left with a closed
incident and no fence.

HOW THE FENCE WRITE IS MADE TO FAIL, without touching production code: the
pre-check (`validator.validate_note`) passes, the incident is closed, and
then the fence's own commit is refused by a real `commit-msg` hook in the
disposable repo. The hook refuses only a message that carries
`Origin: <incident id>` -- the fence's, never the close's -- and leaves a
marker file as setup proof. This is the path the docstring of
`test_remove_script.py` (line ~295) records as untested: "the pre-check
passes but the real write of the fence fails later (e.g. a git error)".

TWO THINGS WRITTEN APART, COMPARED: the command remove.py PRINTS, against
what `gitmem note` really ACCEPTS: the printed command is run as printed,
only the `--searched` value replaced by this test's own answer, and the
saved commit is read back (headline, why, origin, searched).

Windows: commit-msg hooks are shell scripts here; skipped there like the
other POSIX-hook tests.
"""

import os
import shlex
import stat
import sys

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_note_via_script,
    seed_zones_json,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32", reason="POSIX commit-msg hook as a shell script"
)

_ZONES = ("payments", "retries3")
_FENCE_TEXT = "MARK_FENCE retry loops must always carry a hard cap"
_FENCE_WHY = "MARK_WHY retries without a cap keep taking the API down"
_MY_SEARCHED = 'busqué "retry cap" en la memoria: nada sobre el limite'
_RELAUNCH_PREFIX = "Relanza solo el muro con:"


def _seed_incident(repo):
    seed_zones_json(repo, list(_ZONES))
    rc, out, err = seed_note_via_script(
        repo, "I", *_ZONES, "MARK the payments API went down from a retry loop",
        description="MARK_ROOTCAUSE a stray retry loop hammered the payments API",
        work="no",
    )
    assert rc == 0, f"setup invalid: incident not seeded: {out!r} {err!r}"
    return extract_note_id(out)


def _refuse_fence_commits(repo, incident_id, marker):
    """A real `commit-msg` hook refusing the fence's commit only."""
    hook = os.path.join(repo, ".git", "hooks", "commit-msg")
    os.makedirs(os.path.dirname(hook), exist_ok=True)
    with open(hook, "w", encoding="utf-8") as fh:
        fh.write(
            "#!/bin/sh\n"
            f"if grep -q '^Origin: {incident_id}' \"$1\"; then\n"
            f"  echo refused >> '{marker}'\n"
            "  echo 'commit-msg: fence refused by the Dante #95 test hook' >&2\n"
            "  exit 1\n"
            "fi\n"
            "exit 0\n"
        )
    os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return hook


def _printed_relaunch(output):
    lines = [line for line in output.splitlines() if _RELAUNCH_PREFIX in line]
    assert len(lines) == 1, f"no single fence relaunch line printed:\n{output}"
    return shlex.split(lines[0].split(_RELAUNCH_PREFIX, 1)[1])


def _answer_searched(tokens, answer):
    """The printed tokens with only the `--searched` value replaced."""
    filled = list(tokens)
    index = filled.index("--searched")
    filled[index + 1] = answer
    return filled


class TestFenceRelaunchCarriesSearched:
    def test_should_save_the_fence_when_the_printed_relaunch_is_obeyed(self, tmp_path, tmp_repo):
        # Bug caught (Yoda T3, remove.py:198-205): the relaunch omits
        # `--searched`, so pasting it bounces on D-098 and the incident,
        # already closed, stays without its fence.
        incident_id = _seed_incident(tmp_repo)
        marker = tmp_path / "fence-refused.txt"
        hook = _refuse_fence_commits(tmp_repo, incident_id, marker)

        rc, out, err = run_gitmem_script(
            [
                "remove", incident_id, "fixed by capping the retry loop",
                "--restriction", "new",
                "--restriction-text", _FENCE_TEXT,
                "--why", _FENCE_WHY,
            ],
            cwd=tmp_repo,
        )

        assert marker.is_file(), (
            f"setup invalid: the fence commit never reached the hook: rc={rc} "
            f"stdout={out!r} stderr={err!r}"
        )
        assert rc == 1, f"stdout={out!r} stderr={err!r}"
        tokens = _printed_relaunch(out + err)
        assert tokens[:3] == ["gitmem", "note", "R"], tokens
        assert "--searched" in tokens, (
            f"the fence relaunch lacks --searched; pasted as-is it bounces "
            f"on D-098: {shlex.join(tokens)}"
        )

        os.remove(hook)  # the git failure is over: obey the command now
        head_before = run_git(["rev-parse", "HEAD"], tmp_repo)[1]
        rc2, out2, err2 = run_gitmem_script(
            _answer_searched(tokens, _MY_SEARCHED)[1:], cwd=tmp_repo
        )

        assert rc2 == 0, f"obeying the printed relaunch failed: {out2!r} {err2!r}"
        fence_id = extract_note_id(out2)
        assert run_git(["rev-parse", "HEAD"], tmp_repo)[1] != head_before
        query = import_lib_memory_module("query")
        previous = os.getcwd()
        os.chdir(tmp_repo)
        try:
            fence = query.by_id(fence_id)
        finally:
            os.chdir(previous)
        assert fence is not None, f"{fence_id} not found in the real history"
        # Every field the relaunch writes, each against the value this test
        # typed (the remove command) or answered (--searched).
        assert (fence.type, fence.headline, fence.description, fence.why) == (
            "R", _FENCE_TEXT, _FENCE_TEXT, _FENCE_WHY
        )
        assert fence.origin == (incident_id,)
        assert (fence.zone1, fence.zone2) == _ZONES
        assert (fence.keys, fence.replaces, fence.awaits, fence.issue, fence.quote) == (
            (), None, None, None, None
        )
        assert fence.searched == _MY_SEARCHED
        restrictions = (pm_path(tmp_repo) / "RESTRICTIONS.md").read_text(encoding="utf-8")
        assert restrictions.count(_FENCE_TEXT) == 1, restrictions
