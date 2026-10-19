"""No test writes the HOME pytest was launched with (R.2): the session runs
under a throwaway HOME set by conftest._isolated_home."""

import os

import pytest

from conftest import HOME_BEFORE_ISOLATION, INSTALL, git_cmd, run_script


def _snapshot(path):
    """(bytes, mtime_ns) of a file, or None when it does not exist."""
    if not os.path.isfile(path):
        return None
    with open(path, "rb") as f:
        return f.read(), os.stat(path).st_mtime_ns


def _launcher(home):
    return os.path.join(home, ".local", "bin", "gitmem")


@pytest.fixture(scope="module")
def home_seen_by_a_module_fixture():
    return os.path.expanduser("~")


def test_should_run_under_a_throwaway_home_when_any_test_runs():
    home = os.path.expanduser("~")
    assert home != HOME_BEFORE_ISOLATION
    assert os.path.isdir(home)


def test_should_give_module_fixtures_the_throwaway_home_too(home_seen_by_a_module_fixture):
    assert home_seen_by_a_module_fixture != HOME_BEFORE_ISOLATION
    assert home_seen_by_a_module_fixture == os.path.expanduser("~")


def test_should_write_the_launcher_under_the_throwaway_home_when_install_runs(tmp_path):
    real_launcher = _launcher(HOME_BEFORE_ISOLATION)
    before = _snapshot(real_launcher)
    repo = str(tmp_path / "repo")
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)

    rc, _, err = run_script(INSTALL, repo, ["--auto"])

    assert rc == 0, err
    assert os.path.isfile(_launcher(os.path.expanduser("~")))
    assert _snapshot(real_launcher) == before
