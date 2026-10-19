"""`gitmem note D ... --discard` when something goes wrong (D-145, R.13, R.7).

A refused alternative relaunches the whole decision, never a loose X: the
pasted relaunch writes the decision and leaves no orphan X. A git failure
after the decision commit names the decision that already landed. Driven
through `bin/gitmem` on a throwaway repo, read back through the real index
readers.
"""

import os
import re
import shutil
import stat
import subprocess

import pytest

from .conftest import (
    extract_note_id,
    import_lib_memory_module,
    pm_path,
    run_git,
    run_gitmem_script,
    seed_zones_json,
    with_searched,
)

ZONES = ("billing", "reports")
OLD_HEADLINE = "invoices are rendered nightly by a cron batch"
OLD_WHY = "the batch window was free at night"
OLD_DESCRIPTION = "Nightly cron renders every pending invoice in one pass."
NEW_HEADLINE = "invoices render through a queue worker"
NEW_WHY = "customers wait a whole day for a corrected document"
NEW_DESCRIPTION = "A queue worker renders each invoice as soon as it is approved."
DISCARD = ("render invoices on demand from the web request", "a slow render blocks the checkout page")

# Refuses only the saves that stage DISCARDED.md: the decision lands, every
# alternative's own save fails (gitcmd commits without skipping hooks).
_REFUSE_DISCARD_HOOK = (
    b"#!/bin/sh\n"
    b"if git diff --cached --name-only | grep -q 'DISCARDED.md'; then\n"
    b"  echo 'MARK_HOOK refusing the discard' >&2\n"
    b"  exit 1\n"
    b"fi\n"
    b"exit 0\n"
)


@pytest.fixture
def indexes():
    return import_lib_memory_module("indexes")


def _gitmem(repo, args):
    rc, out, err = run_gitmem_script(args, cwd=repo)
    combined = out + err
    assert "Traceback" not in combined, combined
    return rc, out, combined


def _decision_args(headline, why, description, *extra):
    return with_searched([
        "note", "D", "--zones", *ZONES, headline, "--why", why, "--description", description,
        "--discard", *DISCARD, *extra,
    ])


def _snapshot(repo):
    rc, status, err = run_git(["status", "--porcelain", "--untracked-files=all"], repo)
    assert rc == 0, err
    rc, head, err = run_git(["rev-parse", "HEAD"], repo)
    assert rc == 0, err
    return head, status, {p.name: p.read_bytes() for p in sorted(pm_path(repo).glob("*.md"))}


def _pasted_words(command):
    """The argv a real shell builds from `command` pasted as printed."""
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


def _flag_value(words, flag):
    assert words.count(flag) == 1, f"{flag} must appear exactly once: {words!r}"
    return words[words.index(flag) + 1]


@pytest.fixture
def decision_with_discard(tmp_repo, indexes):
    seed_zones_json(tmp_repo, list(ZONES))
    rc, out, combined = _gitmem(tmp_repo, _decision_args(OLD_HEADLINE, OLD_WHY, OLD_DESCRIPTION))
    assert rc == 0, f"seed failed: {combined!r}"
    old_id = extract_note_id(out)
    discarded = [line.id for line in indexes.read("DISCARDED.md", pm_path(tmp_repo))]
    assert len(discarded) == 1, f"setup: one X expected: {discarded!r}"
    return old_id, discarded[0]


class TestRefusedAlternativeKeepsTheDecision:
    """Cerberus F1 (discard path): re-deciding with --replaces and the same discard."""

    def test_should_write_the_decision_without_an_orphan_x_when_the_relaunch_is_pasted(
        self, tmp_repo, decision_with_discard, indexes
    ):
        old_id, old_x = decision_with_discard
        before = _snapshot(tmp_repo)
        rc, _out, combined = _gitmem(tmp_repo, _decision_args(
            NEW_HEADLINE, NEW_WHY, NEW_DESCRIPTION, "--replaces", old_id,
        ))
        assert rc != 0, f"setup: the repeated discard should be refused: {combined!r}"
        assert _snapshot(tmp_repo) == before, "a refused act writes nothing"

        commands = [_pasted_words(c) for c in _relaunch_commands(combined)]
        assert not [w for w in commands if w[:3] == ["gitmem", "note", "X"]], (
            f"a loose X relaunch drops the decision:\n{combined}"
        )
        decisions = [w for w in commands if w[:3] == ["gitmem", "note", "D"]]
        assert len(decisions) == 1, f"one relaunch of the whole decision expected:\n{combined}"
        words = decisions[0]
        assert NEW_HEADLINE in words, words
        assert _flag_value(words, "--why") == NEW_WHY, words
        assert _flag_value(words, "--description") == NEW_DESCRIPTION, words
        assert _flag_value(words, "--replaces") == old_id, words

        rc, out, combined = _gitmem(tmp_repo, words[1:])

        assert rc == 0, f"the pasted relaunch must work: {combined!r}"
        pm = pm_path(tmp_repo)
        new_ids = [line.id for line in indexes.read("DECISIONS.md", pm) if line.headline == NEW_HEADLINE]
        assert len(new_ids) == 1, f"the decision must be written once: {new_ids!r}"
        archived = {a.id: (a.destination, a.destination_detail) for a in indexes.read_archive(pm)}
        assert archived.get(old_id) == ("replaced", new_ids[0]), archived
        assert [line.id for line in indexes.read("DISCARDED.md", pm)] == [old_x], (
            "the old X stays, and no second X for the same alternative"
        )


class TestGitFailureAfterTheDecisionSaysWhatLanded:
    """Argus: a git failure after the decision commit names what is already saved."""

    def test_should_name_the_saved_decision_when_the_discard_save_fails(self, tmp_repo, indexes):
        seed_zones_json(tmp_repo, list(ZONES))
        hook = os.path.join(tmp_repo, ".git", "hooks", "pre-commit")
        with open(hook, "wb") as fh:
            fh.write(_REFUSE_DISCARD_HOOK)
        os.chmod(hook, os.stat(hook).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

        rc, _out, combined = _gitmem(tmp_repo, _decision_args(OLD_HEADLINE, OLD_WHY, OLD_DESCRIPTION))

        assert rc == 1, combined
        assert "MARK_HOOK" in combined, f"setup: the discard save was not refused: {combined!r}"
        pm = pm_path(tmp_repo)
        landed = [line.id for line in indexes.read("DECISIONS.md", pm) if line.headline == OLD_HEADLINE]
        assert len(landed) == 1, f"setup: the decision should have landed: {landed!r}"
        assert not list(indexes.read("DISCARDED.md", pm)), "setup: no X should have landed"
        assert re.search(rf"(?<![\w-]){re.escape(landed[0])}(?![\w-])", combined), (
            f"the failure must name {landed[0]}, already saved, so a retry does not write it twice:\n{combined}"
        )
