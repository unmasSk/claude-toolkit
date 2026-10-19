"""Contract (I-007, House 2026-10-19): the merge gate reads a Git Bash drive
path (`/c/Users/me/proj`) as the session repo.

On Windows, Claude Code's shell is Git Bash, and Git Bash writes the absolute
path `C:\\Users\\me\\proj` as `/c/Users/me/proj`; bash and git both accept it.
Before the fix, `lib/merge_gate_target.py::_join_path` joined it with ntpath
as it came: ntpath.join(r"C:\\Users\\me\\proj", "/c/Users/me/proj") is
"C:/c/Users/me/proj", a directory that does not exist. So an everyday merge
into dev written as `git -C /c/<session repo> ...` or
`cd /c/<session repo> && ...` read as "runs elsewhere" -> unknown target ->
the heavy staging gate. D-129 says a path to the session repo is read like no
path, whatever its spelling. The translation now lives in
lib/git_bash_path.py::native_path (Windows only), shared by this gate and the
commit gate in hooks/customs.py. These tests pin that fix.

Expected values come from D-129 and from how Git Bash spells a drive path,
never from the gate's code.

How this runs on a Mac (no Windows here):
  - merge_gate_target's `os` is swapped for a view of the real one whose
    `name` is "nt" and whose `path` is ntpath -- the very module Windows uses
    as os.path -- and sys.platform reads "win32". A fix that checks
    `os.name == "nt"` in merge_gate_target or `sys.platform == "win32"`
    anywhere sees Windows. (A fix whose check reads `os.name` inside another
    module would not; that is the one shape this simulation cannot reach.)
  - git is the one thing that cannot run on Windows paths here, so
    merge_gate_target.run_git is a double that answers
    `rev-parse --show-toplevel` the way git for Windows does: the repo's
    top-level in forward slashes for any directory inside it, rc 128 for
    anything else.
  - The command goes through the same pieces, in the same order, as
    hooks/pre-merge-gate.py::_gate_decision: tokenize -> git_calls ->
    toplevel(cwd) -> runs_elsewhere.

The last class runs the real hook end to end, on Windows only (the user's
door): it is the same contract, checked through the hook itself.
"""

import ntpath
import os
import sys
from pathlib import Path

import pytest

import merge_gate_target as mgt
from test_pre_merge_gate import _assert_decision, _make_repo_on, _run_hook

# The session repo, as Claude Code's hook payload gives cwd on Windows.
SESSION_REPO = r"C:\Users\me\proj"
# The same directory as Git Bash writes it (by hand, from the rule: drive
# letter lowercased after a leading slash, forward slashes).
GIT_BASH_SESSION_REPO = "/c/Users/me/proj"


class _WindowsOs:
    """The real os module, seen as Windows: name "nt", path = ntpath."""

    name = "nt"
    path = ntpath
    sep = "\\"
    altsep = "/"

    def __getattr__(self, attr):
        return getattr(os, attr)


def _fake_windows_git(session_root):
    """run_git double: `rev-parse --show-toplevel` as git for Windows answers
    it -- the top-level in forward slashes from any directory inside the
    repo (either slash, any case), rc 128 from anywhere else."""
    root = ntpath.normcase(ntpath.normpath(session_root))
    calls = []

    def run_git(args, timeout=None, cwd=None, env=None, log_stderr_on_failure=False):
        calls.append((list(args), cwd))
        if list(args) != ["rev-parse", "--show-toplevel"] or not cwd:
            return 128, ""
        here = ntpath.normcase(ntpath.normpath(cwd))
        if here == root or here.startswith(root + "\\"):
            return 0, session_root.replace("\\", "/")
        return 128, ""

    run_git.calls = calls
    return run_git


@pytest.fixture
def windows(monkeypatch):
    """merge_gate_target as it runs on Windows, with the session repo at
    SESSION_REPO. Yields the run_git double (its .calls show git was asked)."""
    fake = _fake_windows_git(SESSION_REPO)
    monkeypatch.setattr(mgt, "os", _WindowsOs())
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setattr(mgt, "run_git", fake)
    mgt.toplevel.cache_clear()
    try:
        yield fake
    finally:
        mgt.toplevel.cache_clear()


def _where_each_call_runs(command, cwd=SESSION_REPO):
    """[(subcommand, runs_elsewhere)] for every git call in command, wired as
    hooks/pre-merge-gate.py::_gate_decision wires it."""
    tokens = mgt.tokenize(command)
    assert tokens is not None, f"setup invalid: {command!r} does not tokenize"
    session_top = mgt.toplevel(cwd)
    assert session_top is not None, "setup invalid: the simulated session repo has no top-level"
    return [(name, mgt.runs_elsewhere(tokens, sub, paths, cwd, session_top))
            for sub, name, paths in mgt.git_calls(tokens)]


# ── The contract: the Git Bash spelling of the session repo ──────────────


class TestGitBashDrivePathIsTheSessionRepo:
    """Bug caught: `/c/...` joined as it comes (C:/c/...), so the session
    repo reads as another directory and a merge into dev hits the heavy
    gate."""

    @pytest.mark.parametrize("command", [
        f"git -C {GIT_BASH_SESSION_REPO} switch dev && git -C {GIT_BASH_SESSION_REPO} merge --no-ff feat/x",
        f"cd {GIT_BASH_SESSION_REPO} && git switch dev && git merge --no-ff feat/x",
        f"git -C {GIT_BASH_SESSION_REPO}/ merge --no-ff feat/x",
        f"git -C {GIT_BASH_SESSION_REPO}/sub merge --no-ff feat/x",
        f"cd {GIT_BASH_SESSION_REPO}/sub && git merge --no-ff feat/x",
    ], ids=["git-C-switch-merge", "cd-switch-merge", "git-C-trailing-slash",
            "git-C-subfolder", "cd-subfolder"])
    def test_should_read_git_bash_drive_path_as_the_session_repo(self, windows, command):
        calls = _where_each_call_runs(command)

        assert calls, f"setup invalid: no git call found in {command!r}"
        assert calls == [(name, False) for name, _ in calls], (
            f"{command!r}: {GIT_BASH_SESSION_REPO} is Git Bash's spelling of the "
            f"session repo {SESSION_REPO} -- every call runs there (D-129); "
            f"got {calls}"
        )


# ── GREEN on purpose: the simulation works, and the fix must not overreach ─


class TestSimulationAndBoundaries:
    """Green with or without the fix. The controls prove the Windows
    simulation reads a native path as the session repo, so a failure above
    means the translation is missing and nothing else. The guards fail if
    the translation does too much."""

    @pytest.mark.parametrize("path", [
        "C:/Users/me/proj",
        '"C:\\Users\\me\\proj"',
        "'C:\\Users\\me\\proj'",
        ".",
    ], ids=["forward-slash", "double-quoted", "single-quoted", "dot"])
    def test_control_should_read_native_spellings_as_the_session_repo(self, windows, path):
        command = f"git -C {path} switch dev && git -C {path} merge --no-ff feat/x"

        calls = _where_each_call_runs(command)

        assert calls == [("switch", False), ("merge", False)], (
            f"{command!r}: the simulation should already read this native "
            f"spelling as the session repo; got {calls}"
        )
        assert windows.calls, "the git double was never asked -- the simulation is not wired"

    def test_should_keep_another_drive_elsewhere(self, windows):
        """Bug caught: a translation that drops or fixes the drive letter
        (`/d/...` read as C:)."""
        command = "git -C /d/Users/me/proj merge --no-ff feat/x"

        calls = _where_each_call_runs(command)

        assert calls == [("merge", True)], f"{command!r}: drive D is not the session repo; got {calls}"

    def test_should_keep_a_folder_whose_name_starts_with_a_letter_elsewhere(self, windows):
        """Bug caught: a translation that takes any one-letter prefix as a
        drive (`/cache/...` -> `C:ache/...`). `/cache` is a folder, not
        drive C."""
        command = "git -C /cache/Users/me/proj merge --no-ff feat/x"

        calls = _where_each_call_runs(command)

        assert calls == [("merge", True)], f"{command!r}: not drive C; got {calls}"


# ── The user's door: the real hook on Windows ────────────────────────────


def _git_bash_spelling(path):
    """`C:\\x\\y` as Git Bash writes it: `/c/x/y`."""
    p = Path(path)
    assert p.drive, f"setup invalid: {path!r} has no drive letter"
    return f"/{p.drive[0].lower()}{p.as_posix()[len(p.drive):]}"


@pytest.mark.skipif(
    sys.platform != "win32",
    reason="/c/... is Git Bash's spelling of a Windows drive path; no drive C: on macOS/Linux",
)
class TestRealHookOnWindows:
    """Same contract through hooks/pre-merge-gate.py, as Claude Code calls
    it. UNVERIFIED until it runs on windows-latest."""

    @pytest.mark.parametrize("command_tpl", [
        "git -C {path} switch dev && git -C {path} merge --no-ff feat/x",
        "cd {path} && git switch dev && git merge --no-ff feat/x",
    ])
    def test_should_approve_merge_into_dev_through_git_bash_path(self, tmp_path, command_tpl):
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x"])
        command = command_tpl.format(path=_git_bash_spelling(repo))

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} -- Git Bash spelling of the session repo, target dev (D-129)")
