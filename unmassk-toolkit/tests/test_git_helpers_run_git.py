"""
lib/git_helpers.py::run_git() — env kwarg, log_stderr_on_failure kwarg, and
POSIX/Windows process-group kill-on-timeout (Argus SEC-MED-001).

Salvaged from tests/test_boot_git_checks.py (2026-08-05): that file's own
target module, lib/boot_git_checks.py, was deleted outright with the rest
of the v1 memory system (docs/memoria-v2/PLAN-CONSTRUCCION.md) — every
other class in that file called boot_git_checks.* directly and died with
it. These 4 classes never touched boot_git_checks at all; they exercise
git_helpers.run_git() only — the general-purpose git subprocess wrapper
used everywhere in the codebase, confirmed still alive (lib/git_helpers.py
survives). Moved verbatim (not rewritten) into this dedicated,
honestly-named file instead of being deleted along with their old home, per
this project's rule that coverage of live code is never dropped just
because the file it happened to live in died.

Build mode: n/a (salvage move, linear). No production code is touched by
this file.
"""

import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import LIB_DIR

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import git_helpers

WINDOWS = sys.platform == "win32"


# ── run_git env kwarg: additive merge, no os.environ mutation ────────────


class TestRunGitEnvKwarg:
    def _make_repo(self, tmp_path):
        repo = str(tmp_path / "envkwarg_repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "a@test.com"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "A"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        return repo

    def test_env_kwarg_never_mutates_real_os_environ(self, tmp_path):
        repo = self._make_repo(tmp_path)
        sentinel = "UNMASSK_TEST_ENV_SENTINEL_MERGE_CHECK_9f2a"
        assert sentinel not in os.environ

        code, _out = git_helpers.run_git(["rev-parse", "--show-toplevel"], cwd=repo, env={sentinel: "1"})
        assert code == 0
        assert sentinel not in os.environ

    def test_env_none_behaves_identically_to_omitted(self, tmp_path):
        repo = self._make_repo(tmp_path)
        without_kwarg = git_helpers.run_git(["rev-parse", "--show-toplevel"], cwd=repo)
        with_none = git_helpers.run_git(["rev-parse", "--show-toplevel"], cwd=repo, env=None)
        assert without_kwarg == with_none

    def test_env_override_wins_over_poisoned_ambient_value(self, tmp_path, monkeypatch):
        repo = self._make_repo(tmp_path)
        monkeypatch.setenv("GIT_AUTHOR_NAME", "AMBIENT-POISON")

        code, out = git_helpers.run_git(
            ["var", "GIT_AUTHOR_IDENT"],
            cwd=repo,
            env={
                "GIT_AUTHOR_NAME": "Frescura Override",
                "GIT_AUTHOR_EMAIL": "fresh@test.com",
                "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
            },
        )
        assert code == 0
        assert "Frescura Override" in out
        assert "AMBIENT-POISON" not in out


# ── run_git log_stderr_on_failure: opt-in diagnostic breadcrumb ──────────


class TestRunGitLogStderrOnFailure:
    """lib/git_helpers.py:run_git()'s log_stderr_on_failure kwarg —
    subprocess.Popen is monkeypatched at the module level to force a
    controlled (returncode, stdout, stderr) triple without depending on a
    real git failure.
    """

    class _FakeProc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.pid = 424242
            self._stdout = stdout
            self._stderr = stderr

        def communicate(self, timeout=None):
            return self._stdout.encode("utf-8"), self._stderr.encode("utf-8")

    def _patch_popen(self, monkeypatch, returncode, stdout="", stderr=""):
        fake_proc = self._FakeProc(returncode, stdout, stderr)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)
        return fake_proc

    def test_failure_with_flag_true_prints_breadcrumb_with_prefix(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=128, stderr="fatal: not a git repository")

        code, out = git_helpers.run_git(["status"], log_stderr_on_failure=True)

        assert code == 128
        assert out == ""
        captured = capsys.readouterr()
        assert "[git_helpers] git 'status' exited 128: fatal: not a git repository" in captured.err

    def test_stderr_truncated_to_300_chars(self, monkeypatch, capsys):
        long_stderr = "E" * 500
        self._patch_popen(monkeypatch, returncode=1, stderr=long_stderr)

        git_helpers.run_git(["fetch"], log_stderr_on_failure=True)

        captured = capsys.readouterr()
        assert ("E" * 300) in captured.err
        assert ("E" * 301) not in captured.err

    def test_flag_false_stays_silent_on_failure(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="fatal: some failure")

        code, _out = git_helpers.run_git(["status"], log_stderr_on_failure=False)

        assert code == 1
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_omitted_defaults_to_silent_on_failure(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="fatal: some failure")

        code, _out = git_helpers.run_git(["status"])  # log_stderr_on_failure not passed

        assert code == 1
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_true_but_success_returncode_is_silent(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=0, stderr="hint: some advisory text")

        code, _out = git_helpers.run_git(["status"], log_stderr_on_failure=True)

        assert code == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_true_failure_but_empty_stderr_is_silent(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="")

        git_helpers.run_git(["status"], log_stderr_on_failure=True)

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_true_failure_but_whitespace_only_stderr_is_silent(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="   \n  ")

        git_helpers.run_git(["status"], log_stderr_on_failure=True)

        captured = capsys.readouterr()
        assert captured.err == ""


# ── run_git() timeout: POSIX process-group kill (Argus SEC-MED-001) ──────

_FAKE_GIT_SPAWN_GRANDCHILD_TEMPLATE = '''#!/usr/bin/env python3
import sys, os, subprocess, time

pid_file = r"""__PID_FILE__"""
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(pid_file, "w") as f:
    f.write(str(grandchild.pid))
    f.flush()
    os.fsync(f.fileno())

time.sleep(60)
'''


def _make_fake_git_spawning_grandchild(tmp_path, pid_file):
    fake_dir = tmp_path / "fake_bin_grandchild"
    fake_dir.mkdir(exist_ok=True)
    fake_git_path = fake_dir / "git"
    script = _FAKE_GIT_SPAWN_GRANDCHILD_TEMPLATE.replace("__PID_FILE__", str(pid_file))
    fake_git_path.write_text(script, encoding="utf-8")
    os.chmod(fake_git_path, 0o755)
    return str(fake_dir)


def _wait_for_file(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(0.05)
    return False


def _pid_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but not ours — still alive
    return True


class TestPosixProcessTreeKillOnTimeout:
    """Argus SEC-MED-001: run_git()'s TimeoutExpired branch must kill the
    WHOLE process group (os.killpg on POSIX via start_new_session=True at
    spawn time), not just the direct "git" child — otherwise a hung
    ssh/askpass/credential-helper grandchild survives as an orphan.
    """

    @pytest.mark.skipif(
        WINDOWS,
        reason="POSIX process-group kill (os.killpg) has no meaning on Windows; "
        "the Windows path (_win32_kill_tree/taskkill) is exercised by "
        "TestWin32ProcessTreeKillOnTimeout below",
    )
    def test_timeout_kills_grandchild_process_not_just_direct_child(self, tmp_path):
        repo = tmp_path / "killtree_repo"
        repo.mkdir()

        pid_file = tmp_path / "grandchild.pid"
        fake_bin = _make_fake_git_spawning_grandchild(tmp_path, pid_file)

        start = time.monotonic()
        code, _out = git_helpers.run_git(
            ["fetch"],
            timeout=1,
            cwd=str(repo),
            env={"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")},
        )
        elapsed = time.monotonic() - start

        assert code == 1, "a timed-out run_git call must return exit code 1"
        assert elapsed < 6, f"run_git took {elapsed:.1f}s — timeout not bounding the hang"
        assert _wait_for_file(str(pid_file)), "grandchild never wrote its own pid — test setup broken"

        grandchild_pid = int(pid_file.read_text(encoding='utf-8').strip())

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _pid_is_alive(grandchild_pid):
            time.sleep(0.1)

        assert not _pid_is_alive(grandchild_pid), (
            f"grandchild pid {grandchild_pid} is still alive after run_git's "
            f"timeout — expected the WHOLE process group to be killed via "
            f"os.killpg(), not just the direct 'git' child"
        )


# ── run_git() timeout: Windows process-tree kill (Argus SEC-MED-001) ─────

_WIN32_SITECUSTOMIZE_SPAWN_GRANDCHILD_TEMPLATE = '''import subprocess, sys, os, time

pid_file = r"""__PID_FILE__"""
grandchild = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(60)"])
with open(pid_file, "w") as f:
    f.write(str(grandchild.pid))
    f.flush()
    os.fsync(f.fileno())

time.sleep(60)
'''


def _resolve_real_python_exe():
    """Return a real, standalone python.exe suitable for copying to a new
    path and running there as a fake "git.exe" — sys.base_exec_prefix
    always points at the base (non-venv) install, unlike sys.executable
    which may be a small venv launcher stub that can't run relocated.
    """
    candidate = os.path.join(sys.base_exec_prefix, "python.exe")
    if os.path.isfile(candidate):
        return candidate
    return sys.executable


def _make_fake_win32_git_spawning_grandchild(tmp_path, pid_file):
    """Windows counterpart to _make_fake_git_spawning_grandchild() — a fake
    "git.exe" that spawns a real, independent grandchild, writes its pid to
    `pid_file`, then hangs. The fake "git.exe" is a literal copy of a real
    Python interpreter binary; a PYTHONPATH-injected sitecustomize.py does
    the actual work (imported automatically during interpreter startup,
    before argv[1] is ever opened as a script file).

    Returns (fake_bin_dir, sitepkg_dir) — caller puts fake_bin_dir on the
    real process's PATH and passes sitepkg_dir via run_git's own
    env={"PYTHONPATH": ...} kwarg.
    """
    fake_dir = tmp_path / "fake_bin_grandchild_win32"
    fake_dir.mkdir(exist_ok=True)
    fake_git_path = fake_dir / "git.exe"
    shutil.copy(_resolve_real_python_exe(), str(fake_git_path))

    sitepkg_dir = tmp_path / "sitepkg_grandchild_win32"
    sitepkg_dir.mkdir(exist_ok=True)
    script = _WIN32_SITECUSTOMIZE_SPAWN_GRANDCHILD_TEMPLATE.replace("__PID_FILE__", str(pid_file))
    (sitepkg_dir / "sitecustomize.py").write_text(script, encoding="utf-8")

    return str(fake_dir), str(sitepkg_dir)


def _win32_pid_is_alive(pid):
    """tasklist-based liveness check. encoding="oem" (not UTF-8) because
    tasklist's console output uses the OEM/ANSI codepage.
    """
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        encoding="oem",
        errors="replace",
        timeout=5,
    )
    return str(pid) in result.stdout


class TestWin32ProcessTreeKillOnTimeout:
    """Argus SEC-MED-001, Windows counterpart to
    TestPosixProcessTreeKillOnTimeout above — proves run_git()'s
    TimeoutExpired branch on win32 (_win32_kill_tree(), `taskkill /F /T
    /PID`) kills the whole process tree rooted at the "git" process it
    launched, not just the direct child. No mocking of subprocess.run,
    taskkill, or _win32_kill_tree — a real fake "git.exe" spawns a real,
    independent grandchild and this test proves via a real tasklist query
    that it is dead after run_git's timeout fires.

    Windows' CreateProcess (invoked when Popen() is given a bare command
    name like "git" with shell=False) resolves the executable via the
    CALLING process's own live PATH block, NOT the env= kwarg passed to
    run_git — so this test monkeypatches the TEST PROCESS's own
    os.environ["PATH"] before calling run_git, and passes the fake's
    sitepkg dir through run_git's own env={"PYTHONPATH": ...} kwarg.
    """

    @pytest.mark.skipif(
        not WINDOWS,
        reason="Windows-only: exercises _win32_kill_tree()/taskkill, the "
        "win32 counterpart to POSIX os.killpg() tested in "
        "TestPosixProcessTreeKillOnTimeout",
    )
    def test_timeout_kills_grandchild_process_not_just_direct_child_win32(self, tmp_path, monkeypatch):
        repo = tmp_path / "killtree_repo_win32"
        repo.mkdir()

        pid_file = tmp_path / "grandchild_win32.pid"
        fake_bin, sitepkg = _make_fake_win32_git_spawning_grandchild(tmp_path, pid_file)
        monkeypatch.setenv("PATH", fake_bin + os.pathsep + os.environ.get("PATH", ""))

        start = time.monotonic()
        code, _out = git_helpers.run_git(
            ["fetch"],
            timeout=1,
            cwd=str(repo),
            env={"PYTHONPATH": sitepkg},
        )
        elapsed = time.monotonic() - start

        assert code == 1, "a timed-out run_git call must return exit code 1"
        assert elapsed < 6, f"run_git took {elapsed:.1f}s — timeout not bounding the hang"
        assert _wait_for_file(str(pid_file)), "grandchild never wrote its own pid — test setup broken"

        grandchild_pid = int(pid_file.read_text(encoding='utf-8').strip())

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _win32_pid_is_alive(grandchild_pid):
            time.sleep(0.1)

        assert not _win32_pid_is_alive(grandchild_pid), (
            f"grandchild pid {grandchild_pid} is still alive after run_git's "
            f"timeout — expected the WHOLE process tree to be killed via "
            f"taskkill /F /T /PID, not just the direct 'git.exe' child"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
