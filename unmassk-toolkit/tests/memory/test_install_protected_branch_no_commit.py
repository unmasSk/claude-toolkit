"""D-157 contract (test-first): the installer makes no commit on a
protected branch, leaves its changes in the working tree, and the boot
report says so in one line. On a trunk repo's main and on a work branch
it still commits, as before.

"Protected" is the rule `gitmem work`/`wip` apply (R-015): repo_type
"gitflow" in .claude/project-memory/config.json and the branch is main or
master. Every repo here is a real throwaway repo; repo_type comes from the
installer's own deduction (a `develop` branch next to main -> gitflow), the
shape a real gitflow project has.

Doors: the SessionStart hook as Claude Code runs it (first install, then
the report), and session-start-crew.py (the upgrade that rewrites
CLAUDE.md when the managed block changes).
"""

import json
import os
import subprocess
import sys
import unicodedata

import pytest

from .boot_hook_gh_stub import gh_stub  # noqa: F401  (fixture)
from .boot_hook_harness import POSIX_ONLY, _run_boot_hook
from .conftest import HOOKS_DIR, run_git

pytestmark = POSIX_ONLY

_TOOLKIT_ROOT = os.path.dirname(HOOKS_DIR)
_INSTALLER = os.path.join(_TOOLKIT_ROOT, "bin", "git-memory-install.py")
_CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")

# What a first install writes and must reach git: observed in a real
# install commit (2026-10-20), typed here by hand -- never read from
# install_apply._INSTALL_CREATES.
_INSTALL_FILES = (
    ".gitignore",
    "CLAUDE.md",
    ".claude/project-memory/config.json",
    ".claude/project-memory/ARCHIVED.md",
    ".claude/project-memory/BLOCKED.md",
    ".claude/project-memory/DECISIONS.md",
    ".claude/project-memory/DISCARDED.md",
    ".claude/project-memory/INCIDENTS.md",
    ".claude/project-memory/MEMOS.md",
    ".claude/project-memory/QUESTIONS.md",
    ".claude/project-memory/RESTRICTIONS.md",
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


def _git(repo, *args):
    rc, out, err = run_git(list(args), repo)
    assert rc == 0, f"git {' '.join(args)} failed in setup: {err}"
    return out.strip()


def _new_repo(tmp_path, main="main", gitflow=True, work_branch=None):
    """A repo with one commit on `main`; `develop` next to it when
    `gitflow`, so the installer deduces repo_type gitflow by itself."""
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    _git(repo, "init", "-q", "-b", main)
    _git(repo, "commit", "-q", "--allow-empty", "-m", "init")
    if gitflow:
        _git(repo, "branch", "develop")
    if work_branch:
        _git(repo, "checkout", "-q", "-b", work_branch)
    return repo


def _norm(text):
    text = unicodedata.normalize("NFKD", text.lower())
    return "".join(c for c in text if not unicodedata.combining(c))


def _install_left_uncommitted_lines(report_text):
    """Report lines that speak of the install and of it not reaching
    git. Wording stays the implementer's; both concepts on ONE line."""
    found = []
    for line in report_text.splitlines():
        n = _norm(line)
        if "instal" in n and any(w in n for w in ("commit", "confirm", "git")):
            found.append(line)
    return found


def _commit_count(repo):
    return int(_git(repo, "rev-list", "--all", "--count"))


def _status(repo):
    rc, out, err = run_git(["status", "--porcelain", "--untracked-files=all"], repo)
    assert rc == 0, err
    return out


def _boot(repo, tmp_path, gh_stub, name="boot"):
    run = _run_boot_hook(repo, tmp_path / name, gh_stub, kill_after=60)
    assert run.rc == 0, run.describe()
    assert run.report_path().is_file(), "no boot report\n" + run.describe()
    return run


def _installed_gitflow_repo_on_main(tmp_path):
    """A gitflow project already installed (through a work branch merged
    into main) whose committed CLAUDE.md carries an older managed block:
    the next upgrade rewrites CLAUDE.md, exactly the fe040683 shape.
    The manifest is gitignored, so stamping it old leaves the tree clean."""
    repo = _new_repo(tmp_path, work_branch="feature/setup")
    done = subprocess.run(
        [sys.executable, _INSTALLER, "--auto"], cwd=repo,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "feature/setup" == _git(repo, "rev-parse", "--abbrev-ref", "HEAD")
    if _status(repo).strip():
        _git(repo, "add", "--", *_INSTALL_FILES)
        _git(repo, "commit", "-q", "-m", "setup: install on a work branch")
    _git(repo, "checkout", "-q", "main")
    _git(repo, "merge", "-q", "--ff-only", "feature/setup")
    with open(os.path.join(repo, ".claude", "project-memory", "config.json"), encoding="utf-8") as fh:
        assert json.load(fh)["repo_type"] == "gitflow", "setup invalid: not deduced gitflow"

    claude_md = os.path.join(repo, "CLAUDE.md")
    with open(claude_md, encoding="utf-8") as fh:
        text = fh.read()
    end = "<!-- END unmassk-toolkit -->"
    assert end in text, "setup invalid: no managed block in CLAUDE.md"
    with open(claude_md, "w", encoding="utf-8") as fh:
        fh.write(text.replace(end, "A line from an older toolkit version.\n" + end, 1))
    _git(repo, "commit", "-q", "-m", "older toolkit block", "--", "CLAUDE.md")
    assert _status(repo).strip() == "", "setup invalid: tree not clean"

    # The plugin was updated since: the installed manifest lags behind,
    # which is what makes the SessionStart upgrade run the installer.
    manifest = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
    with open(manifest, encoding="utf-8") as fh:
        data = json.load(fh)
    data["version"] = "0.0.1"
    with open(manifest, "w", encoding="utf-8") as fh:
        json.dump(data, fh)
    return repo


def _run_crew(repo, tmp_path):
    home = tmp_path / "crew-home"
    home.mkdir(exist_ok=True)
    env = dict(os.environ, HOME=str(home), USERPROFILE=str(home),
               CLAUDE_PLUGIN_ROOT=_TOOLKIT_ROOT)
    done = subprocess.run(
        [sys.executable, _CREW_HOOK], cwd=repo, env=env, input="{}",
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        timeout=60,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    return done


# --------------------------------------------------------------------------
# Protected branch: first install through the boot
# --------------------------------------------------------------------------


@pytest.mark.parametrize("main", ["main", "master"])
def test_should_make_no_commit_when_install_runs_on_protected_branch(
    tmp_path, gh_stub, main
):
    # Bug caught: the install commit still lands on a gitflow main/master.
    repo = _new_repo(tmp_path, main=main)
    head, count = _git(repo, "rev-parse", "HEAD"), _commit_count(repo)

    run = _boot(repo, tmp_path, gh_stub)

    assert _git(repo, "rev-parse", "HEAD") == head, (
        f"a commit landed on protected {main}:\n"
        + _git(repo, "log", "--oneline", "-3") + "\n" + run.describe()
    )
    assert _commit_count(repo) == count


def test_should_leave_every_install_file_in_the_tree_when_on_protected_branch(
    tmp_path, gh_stub
):
    # Bug caught: skipping the commit also drops or reverts what the install wrote.
    repo = _new_repo(tmp_path)

    _boot(repo, tmp_path, gh_stub)

    status = _status(repo)
    missing = [f for f in _INSTALL_FILES if not os.path.isfile(os.path.join(repo, f))]
    unlisted = [f for f in _INSTALL_FILES if f not in status]
    assert missing == [] and unlisted == [], (
        f"missing on disk: {missing}; not shown as changes: {unlisted}\n{status}"
    )


def test_should_not_stage_install_files_when_on_protected_branch(tmp_path, gh_stub):
    # Bug caught: files left `git add`ed ride into the owner's next commit unasked.
    repo = _new_repo(tmp_path)

    _boot(repo, tmp_path, gh_stub)

    assert _git(repo, "diff", "--cached", "--name-only") == "", (
        "install files left staged on protected main:\n" + _status(repo)
    )


def test_should_say_so_in_one_report_line_when_install_left_changes_on_protected_branch(
    tmp_path, gh_stub
):
    # Bug caught: changes left behind in silence (the boot never mentions them).
    repo = _new_repo(tmp_path)

    run = _boot(repo, tmp_path, gh_stub)

    lines = _install_left_uncommitted_lines(run.report())
    assert len(lines) == 1, (
        f"expected exactly one report line about the uncommitted install, got {lines}\n"
        + run.report()
    )


# --------------------------------------------------------------------------
# Not protected: commits as before (green today on purpose)
# --------------------------------------------------------------------------


def test_should_commit_install_files_when_trunk_repo_on_main(tmp_path, gh_stub):
    # Bug caught: the new gate also stops the commit where the project works on main.
    repo = _new_repo(tmp_path, gitflow=False)
    head = _git(repo, "rev-parse", "HEAD")

    _boot(repo, tmp_path, gh_stub)

    assert _git(repo, "rev-parse", "HEAD~1") == head
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(committed) == sorted(_INSTALL_FILES)
    assert _status(repo) == ""


def test_should_commit_install_files_when_gitflow_repo_on_work_branch(tmp_path, gh_stub):
    # Bug caught: the gate treats every branch of a gitflow repo as protected.
    repo = _new_repo(tmp_path, work_branch="feature/x")
    head = _git(repo, "rev-parse", "HEAD")

    _boot(repo, tmp_path, gh_stub)

    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD") == "feature/x"
    assert _git(repo, "rev-parse", "HEAD~1") == head
    committed = _git(repo, "show", "--name-only", "--format=", "HEAD").splitlines()
    assert sorted(committed) == sorted(_INSTALL_FILES)


def test_should_carry_no_uncommitted_install_line_when_install_committed(tmp_path, gh_stub):
    # Bug caught: the line is printed on every boot, protected or not.
    repo = _new_repo(tmp_path, gitflow=False)

    run = _boot(repo, tmp_path, gh_stub)

    assert _install_left_uncommitted_lines(run.report()) == [], run.report()


# --------------------------------------------------------------------------
# Protected branch: an upgrade that rewrites CLAUDE.md
# --------------------------------------------------------------------------


def test_should_leave_rewritten_claude_md_uncommitted_when_upgrade_runs_on_protected_branch(
    tmp_path,
):
    # Bug caught: the gate covers the first install but not the upgrade path.
    repo = _installed_gitflow_repo_on_main(tmp_path)
    head = _git(repo, "rev-parse", "HEAD")

    crew = _run_crew(repo, tmp_path)

    assert _git(repo, "rev-parse", "HEAD") == head, (
        "the upgrade committed on protected main:\n"
        + _git(repo, "log", "--oneline", "-3") + "\n" + crew.stdout
    )
    assert _status(repo).strip() == "M CLAUDE.md", (
        "CLAUDE.md should be left rewritten and unstaged:\n" + _status(repo)
        + "\n" + crew.stdout
    )


def test_should_say_so_in_next_boot_report_after_upgrade_left_changes_on_protected_branch(
    tmp_path, gh_stub
):
    # Bug caught: only the first-install path tells the boot; an upgrade's leftovers go unsaid.
    repo = _installed_gitflow_repo_on_main(tmp_path)
    _run_crew(repo, tmp_path)

    run = _boot(repo, tmp_path, gh_stub)

    lines = _install_left_uncommitted_lines(run.report())
    assert len(lines) == 1, (
        f"expected exactly one report line about the uncommitted install, got {lines}\n"
        + run.report()
    )


# --------------------------------------------------------------------------
# The marker the protected install leaves for the boot
# --------------------------------------------------------------------------


def _install_left_uncommitted_files(report_text):
    """The indented lines under the uncommitted-install report line."""
    lines = report_text.splitlines()
    flagged = _install_left_uncommitted_lines(report_text)
    heads = [i for i, line in enumerate(lines) if line in flagged]
    assert len(heads) == 1, f"expected one uncommitted-install line:\n{report_text}"
    files = []
    for line in lines[heads[0] + 1:]:
        if not line.strip().startswith("- "):
            break
        files.append(line.strip()[2:])
    return files


def test_should_not_blame_install_for_owner_edit_when_install_later_committed_on_work_branch(
    tmp_path, gh_stub
):
    # Bug caught: the marker survives the install that commits on an open
    # branch, so the owner's own later edit to an install file is reported
    # as an install left uncommitted.
    repo = _new_repo(tmp_path)
    first = _boot(repo, tmp_path, gh_stub, name="boot-main")
    assert len(_install_left_uncommitted_lines(first.report())) == 1, (
        "setup invalid: the protected install left no report line\n" + first.report()
    )

    _git(repo, "checkout", "-q", "-b", "feature/x")
    done = subprocess.run(
        [sys.executable, _INSTALLER, "--auto"], cwd=repo,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert _status(repo) == "", "setup invalid: the open-branch install did not commit\n" + _status(repo)

    with open(os.path.join(repo, ".gitignore"), "a", encoding="utf-8") as fh:
        fh.write("owner-scratch/\n")

    run = _boot(repo, tmp_path, gh_stub, name="boot-feature")

    assert _install_left_uncommitted_lines(run.report()) == [], run.report()


def test_should_list_every_install_file_when_git_status_fails_at_boot(tmp_path, gh_stub):
    # Bug caught: a failed `git status` turns the warning into silence
    # while the install files still sit uncommitted.
    repo = _new_repo(tmp_path)
    _boot(repo, tmp_path, gh_stub, name="boot-install")
    rc, _, err = run_git(["status", "--porcelain"], repo)
    assert rc == 0, "setup invalid: git status failing before the corruption: " + err

    # A corrupt index: `git status` fails, `git log` still answers.
    with open(os.path.join(repo, ".git", "index"), "wb") as fh:
        fh.write(b"not an index")
    rc, _, _ = run_git(["status", "--porcelain"], repo)
    assert rc != 0, "setup invalid: git status still succeeds on the corrupt index"

    run = _boot(repo, tmp_path, gh_stub, name="boot-after")

    assert sorted(_install_left_uncommitted_files(run.report())) == sorted(_INSTALL_FILES), run.report()
