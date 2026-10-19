"""`gitmem note D ... --discard` refused: the relaunch drops every refused
alternative and keeps the rest (D-145, R.7), in two shapes the fix pass
handled without a test: an abbreviated `--disc` flag, which argparse
accepts, and more than one refused alternative in one command.

Driven through `bin/gitmem` on a throwaway repo; every relaunch is pasted
through a real shell and run; the result is read back with the index readers.
"""

import shutil
import subprocess

import pytest

from .conftest import (
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

ZONES = ("billing", "reports")
HEADLINE = "invoices render through a queue worker"
WHY = "customers wait a whole day for a corrected document"
DESCRIPTION = "A queue worker renders each invoice as soon as it is approved."
# Over the 80-character headline cap: the validator refuses these alternatives.
REFUSED_ONE = ("x" * 120, "too long to be a headline")
REFUSED_TWO = ("y" * 120, "also too long to be a headline")
KEPT = ("render invoices on demand from the web request", "a slow render blocks checkout")


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


@pytest.fixture
def fake_home(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    return {"HOME": str(home), "USERPROFILE": str(home)}


@pytest.fixture
def repo(tmp_repo):
    seed_zones_json(tmp_repo, list(ZONES))
    return tmp_repo


def _gitmem(repo, args, env):
    rc, out, err = run_gitmem_script(args, cwd=repo, env=env)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, combined


def _decision(*discard_words):
    return with_searched([
        "note", "D", "--zones", *ZONES, HEADLINE, "--why", WHY, "--description", DESCRIPTION,
        *discard_words,
    ])


def _snapshot(repo):
    rc, status, err = run_git(["status", "--porcelain", "--untracked-files=all"], repo)
    assert rc == 0, err
    rc, head, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, err
    return head, status, {p.name: p.read_bytes() for p in sorted(pm_path(repo).glob("*.md"))}


def _pasted_words(command):
    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell on PATH"
    proc = subprocess.run([shell, "-c", "printf '%s\\0' " + command], capture_output=True)
    assert proc.returncode == 0, proc.stderr
    return proc.stdout.decode("utf-8").split("\0")[:-1]


def _relaunch_commands(output):
    commands, inside = [], False
    for line in output.splitlines():
        if line == "Relanza:":
            inside = True
            continue
        if inside and line.startswith("  "):
            commands.append(line.strip())
            continue
        inside = False
    return commands


def _discard_pairs(words):
    """Every (headline, why) a pasted relaunch passes, under any prefix of --discard."""
    return [
        tuple(words[i + 1:i + 3]) for i, w in enumerate(words)
        if len(w) >= 4 and "--discard".startswith(w)
    ]


def _refuse_then_paste(repo, env, args):
    """Run `args`, check it wrote nothing, return the one pasted D relaunch's words."""
    before = _snapshot(repo)
    rc, combined = _gitmem(repo, args, env)
    assert rc != 0, f"setup: a refused alternative must refuse the command: {combined}"
    assert _snapshot(repo) == before, "a refused act writes nothing"
    commands = [_pasted_words(c) for c in _relaunch_commands(combined)]
    decisions = [w for w in commands if w[:3] == ["gitmem", "note", "D"]]
    assert len(decisions) == 1, f"one relaunch of the whole decision expected:\n{combined}"
    return decisions[0], combined


def _written(repo, indexes):
    pm = pm_path(repo)
    decisions = [line.headline for line in indexes.read("DECISIONS.md", pm)]
    discards = [line.headline for line in indexes.read("DISCARDED.md", pm)]
    return decisions, discards


class TestAbbreviatedDiscardFlag:
    def test_should_drop_the_refused_pair_when_it_was_given_with_an_abbreviated_flag(
        self, repo, fake_home, indexes
    ):
        words, combined = _refuse_then_paste(repo, fake_home, _decision("--disc", *REFUSED_ONE))

        assert _discard_pairs(words) == [], (
            f"the refused pair given as --disc must leave the relaunch:\n{combined}"
        )
        rc, pasted = _gitmem(repo, words[1:], fake_home)

        assert rc == 0, f"the pasted relaunch must save the decision:\n{pasted}"
        assert _written(repo, indexes) == ([HEADLINE], []), "the decision once, no alternative"

    def test_should_keep_a_valid_pair_when_only_the_abbreviated_one_is_refused(
        self, repo, fake_home, indexes
    ):
        words, combined = _refuse_then_paste(
            repo, fake_home, _decision("--disc", *REFUSED_ONE, "--discard", *KEPT)
        )

        assert _discard_pairs(words) == [KEPT], (
            f"only the refused pair leaves the relaunch:\n{combined}"
        )
        rc, pasted = _gitmem(repo, words[1:], fake_home)

        assert rc == 0, f"the pasted relaunch must save the decision:\n{pasted}"
        assert _written(repo, indexes) == ([HEADLINE], [KEPT[0]])


class TestSeveralRefusedAlternatives:
    def test_should_list_every_refused_pair_and_drop_them_all_in_one_relaunch(
        self, repo, fake_home, indexes
    ):
        words, combined = _refuse_then_paste(repo, fake_home, _decision(
            "--discard", *REFUSED_ONE, "--discard", *KEPT, "--discard", *REFUSED_TWO,
        ))

        for refused in (REFUSED_ONE, REFUSED_TWO):
            assert refused[0] in combined, f"the refusal must list {refused[0][:10]}...:\n{combined}"
        assert _discard_pairs(words) == [KEPT], (
            f"both refused pairs leave the relaunch, the valid one stays:\n{combined}"
        )
        rc, pasted = _gitmem(repo, words[1:], fake_home)

        assert rc == 0, f"the pasted relaunch must save the decision:\n{pasted}"
        assert _written(repo, indexes) == ([HEADLINE], [KEPT[0]])
