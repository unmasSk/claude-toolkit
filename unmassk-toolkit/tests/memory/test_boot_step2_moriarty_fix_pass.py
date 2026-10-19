"""Fix pass after Moriarty's attack on issue #95 step 2 -- one test class
per finding, each reproducing his scenario through the door the owner
uses (the SessionStart hook as hooks.json runs it, boot.py itself).

  T2  network stalled on BOTH `git fetch` and `gh`: the two inner bounds
      (10 s + 15 s) added up to the launcher's 25 s, the boot was killed
      and the session got no briefing at all.
  T3  the worst-case overrun ended at ~28 s, a hair under Claude Code's
      30 s kill (covered in test_boot_deadline_launcher.py, default-
      deadline test, now asserting >= 4 s to spare).
  T3  two sessions booting the same repo: one's failure notice replaced
      the other's good report, read next as "the boot failed".

The two save-command findings (customs asking on `--help`, the boot
report teaching a save without `--searched`) live in
test_boot_step2_moriarty_save_hints.py (split 2026-10-19, Yoda's size
finding). The first-message reminder finding lives in
tests/test_first_message_reminder_points_to_report.py (it uses the
top-level tests' UserPromptSubmit harness).

Windows: skipped like every fake-`gh` / `ps`-based test in this suite.
"""

import os
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

from .boot_hook_gh_stub import (  # noqa: F401  (gh_stub is a fixture)
    _all_unreflected,
    _seed_citations,
    gh_stub,
)
from .boot_hook_harness import (
    _PLANS_ERROR_TEXT,
    _assert_failure_marker,
    _assert_full_briefing,
    _assert_overrun_notice,
    _boot_hook_entry,
    _boot_py_pointer_prefixes,
    _run_boot_hook,
)
from .boot_overrun_tools import _overrunning_boot
from .conftest import (
    BIN_MEMORY_DIR,
    run_git,
    run_memory_script,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason="fake gh on PATH and a `ps`-based git wrapper: POSIX only, same "
    "skip as boot_hook_harness.py",
)

# The owner's bar for this pass: the hook ends with at least this much
# room under Claude Code's kill (hooks.json timeout).
_SPARE_S = 4.0


def _back_date(path):
    """A previous session's report: an hour older than any boot here."""
    old = time.time() - 3600
    os.utime(path, (old, old))


# ==========================================================================
# T2 -- the network stalls on both fetch and gh: a full briefing anyway
# ==========================================================================


class StalledHttpRemote:
    """A local HTTP "remote" that accepts every connection and never
    answers a byte -- what `git fetch` sees on a dead network link. No
    real network involved."""

    def __init__(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.bind(("127.0.0.1", 0))
        self._sock.listen(16)
        self._sock.settimeout(0.2)
        self._held = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._accept, daemon=True)
        self._thread.start()
        self.url = f"http://127.0.0.1:{self._sock.getsockname()[1]}/project.git"

    def _accept(self):
        while not self._stop.is_set():
            try:
                conn, _addr = self._sock.accept()
            except (socket.timeout, OSError):
                continue
            self._held.append(conn)  # held open, never read, never answered

    @property
    def connections(self):
        return len(self._held)

    def close(self):
        self._stop.set()
        self._thread.join(timeout=2)
        for conn in self._held:
            conn.close()
        self._sock.close()


@pytest.fixture
def stalled_remote():
    remote = StalledHttpRemote()
    yield remote
    remote.close()


_NO_PROXY_ENV = {
    # A proxy on the test machine would answer instead of the stalled
    # socket; git/curl treat an empty value as "no proxy".
    "http_proxy": "",
    "https_proxy": "",
    "HTTP_PROXY": "",
    "HTTPS_PROXY": "",
    "all_proxy": "",
    "ALL_PROXY": "",
    "NO_PROXY": "127.0.0.1,localhost",
    "no_proxy": "127.0.0.1,localhost",
}


class TestNetworkStallStillGivesAFullBriefing:
    def test_should_write_full_briefing_with_both_warnings_when_fetch_and_gh_both_hang(
        self, tmp_repo, tmp_path, gh_stub, stalled_remote
    ):
        # Bug caught (Moriarty T2): fetch's own 10 s and gh's own 15 s
        # added up to the launcher's whole deadline; with both stalled the
        # launcher killed boot.py and the session started with no briefing
        # -- from one ordinary cause, a slow network. Default deadline,
        # nothing shortened: this is the real scenario, timed for real.
        _seed_citations(tmp_repo, {3: 1})
        assert run_git(["remote", "add", "origin", stalled_remote.url], tmp_repo)[0] == 0
        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=60)
        _command, hook_timeout = _boot_hook_entry()

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=hook_timeout + 5,
            extra_env=_NO_PROXY_ENV,
        )

        assert stalled_remote.connections >= 1, (
            "setup invalid: git fetch never reached the stalled remote\n" + run.describe()
        )
        assert len(gh_stub.calls()) == 1, (
            "setup invalid: gh was never launched, so it never hung\n" + run.describe()
        )
        assert not run.killed and run.elapsed <= hook_timeout - _SPARE_S, (
            f"with fetch and gh both stalled the hook took {run.elapsed:.1f}s; "
            f"it must end with {_SPARE_S:g}s to spare under the {hook_timeout:g}s "
            "kill\n" + run.describe()
        )
        _assert_full_briefing(run)
        pointers = [
            line for line in run.memory_lines()
            if line.lower().startswith(tuple(_boot_py_pointer_prefixes()))
        ]
        assert pointers, (
            "the hook did not print boot.py's normal pointer: it is an "
            "overrun notice, not a briefing\n" + run.describe()
        )
        report = run.report()
        warnings = [line for line in report.splitlines() if "⚠" in line]
        assert any("fetch" in line.lower() for line in warnings), (
            "the briefing does not warn that the fetch failed -- it reads as "
            "fresh while the remote was never reached\n" + report
        )
        assert _PLANS_ERROR_TEXT in report, (
            "the briefing does not say the plans check could not run\n" + report
        )


# ==========================================================================
# T3 -- two sessions boot the same repo: a failure never buries a good report
# ==========================================================================


class TestConcurrentBootsKeepTheGoodReport:
    def test_should_keep_the_other_sessions_report_when_this_boot_overruns(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Moriarty RACE): B overruns while A, started later,
        # boots fine and tells its session "the report is at ...". B's
        # marker step then replaced A's good report with "THE BOOT DID NOT
        # FINISH", and A's Claude told the owner a successful boot failed.
        # A solo overrun first: it must still replace an older report, and
        # its line is what "replaced" sounds like.
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        installed = _run_boot_hook(tmp_repo, tmp_path / "install", gh_stub, kill_after=60)
        _assert_full_briefing(installed)
        _back_date(installed.report_path())

        solo_env, solo_slow = _overrunning_boot(tmp_path / "solo", gh_stub, 2.5)
        solo = _run_boot_hook(tmp_repo, tmp_path / "solo", gh_stub, kill_after=25, extra_env=solo_env)
        assert solo_slow.is_file(), "setup invalid\n" + solo.describe()
        _assert_failure_marker(solo)
        solo_lines = solo.report_path_lines()
        assert len(solo_lines) == 1, solo.describe()

        b_deadline = 8.0
        b_env, b_slow = _overrunning_boot(tmp_path / "b", gh_stub, b_deadline)
        result = {}

        def run_b():
            result["start"] = time.monotonic()
            result["run"] = _run_boot_hook(
                tmp_repo, tmp_path / "b", gh_stub, kill_after=40, extra_env=b_env
            )

        b_thread = threading.Thread(target=run_b)
        b_thread.start()
        try:
            waited_until = time.monotonic() + 15
            while not b_slow.is_file() and time.monotonic() < waited_until:
                time.sleep(0.05)
            assert b_slow.is_file(), "setup invalid: B never reached its slow git log"
            a = _run_boot_hook(tmp_repo, tmp_path / "a", gh_stub, kill_after=60)
            a_done = time.monotonic()
            a_report = a.report()
        finally:
            b_thread.join(timeout=60)
        b = result["run"]

        _assert_full_briefing(a)
        assert a_done < result["start"] + b_deadline, (
            "setup invalid: A finished after B's cut, so there was no race"
        )
        _assert_overrun_notice(b, b_deadline)
        assert a.report() == a_report, (
            "B's failure notice replaced the good report A had just pointed "
            "its session to:\n" + a.report()
        )
        b_lines = b.report_path_lines()
        assert len(b_lines) == 1, b.describe()
        assert b_lines != solo_lines, (
            "B tells its session the report was replaced by its failure "
            f"notice, as a solo overrun does: {b_lines[0]!r}"
        )


_CRASH_SITECUSTOMIZE = r'''
import builtins, os, sys, time
if os.path.basename(sys.argv[0] if sys.argv else "") == "boot.py" and os.environ.get("CRASH_BOOT_GO"):
    _real_import = builtins.__import__

    def _import(name, *args, **kwargs):
        module = _real_import(name, *args, **kwargs)
        if name == "boot" and hasattr(module, "build") and not getattr(module, "_dante_crash", False):
            module._dante_crash = True

            def build():
                with open(os.environ["CRASH_BOOT_WAITING"], "w", encoding="utf-8") as fh:
                    fh.write("waiting\n")
                until = time.time() + 30
                while not os.path.exists(os.environ["CRASH_BOOT_GO"]) and time.time() < until:
                    time.sleep(0.05)
                raise RuntimeError("dante: injected boot crash")

            module.build = build
        return module

    builtins.__import__ = _import
'''


def _crashing_boot(tmp_path, repo):
    """Start bin/memory/boot.py so that it crashes inside `boot.build()`
    when the GO file appears. Production code untouched: a
    `sitecustomize.py` swaps `build` in the child only."""
    site = tmp_path / "crash-site"
    site.mkdir()
    (site / "sitecustomize.py").write_text(_CRASH_SITECUSTOMIZE, encoding="utf-8")
    go = tmp_path / "crash-go"
    waiting = tmp_path / "crash-waiting"
    env = dict(os.environ)
    previous = env.get("PYTHONPATH")
    env["PYTHONPATH"] = str(site) + (os.pathsep + previous if previous else "")
    env["CRASH_BOOT_GO"] = str(go)
    env["CRASH_BOOT_WAITING"] = str(waiting)
    proc = subprocess.Popen(
        [sys.executable, os.path.join(BIN_MEMORY_DIR, "boot.py")],
        cwd=repo,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return proc, go, waiting


def _wait_for(path, seconds=15):
    until = time.monotonic() + seconds
    while not path.exists() and time.monotonic() < until:
        time.sleep(0.05)
    return path.exists()


def _report(repo):
    return Path(repo, ".claude", ".unmassk", "boot-latest.txt")


class TestCrashingBootKeepsTheGoodReport:
    def test_should_keep_the_other_sessions_report_when_this_boot_crashes(
        self, tmp_repo, tmp_path
    ):
        # Bug caught (Moriarty RACE, boot.py's own writer): boot.py
        # crashes after another session's boot wrote a good report, and
        # its "EL ARRANQUE FALLÓ" marker replaces it.
        proc, go, waiting = _crashing_boot(tmp_path, tmp_repo)
        try:
            assert _wait_for(waiting), "setup invalid: the crashing boot never started"
            rc, out, err = run_memory_script("boot.py", [], cwd=tmp_repo)
            assert rc == 0, f"setup: the other session's boot failed: {out}{err}"
            good = _report(tmp_repo).read_text(encoding="utf-8")
            assert "CHECKS" in good, good
            go.write_text("go\n", encoding="utf-8")
            _out, crash_err = proc.communicate(timeout=60)
        finally:
            if proc.poll() is None:
                proc.kill()
        assert proc.returncode == 1 and "dante: injected boot crash" in crash_err, (
            f"setup invalid: boot.py did not crash as injected: rc={proc.returncode} "
            f"stderr={crash_err!r}"
        )

        assert _report(tmp_repo).read_text(encoding="utf-8") == good, (
            "the crashing boot's failure marker replaced the report another "
            "session had just written"
        )

    def test_should_still_replace_an_older_report_when_this_boot_crashes(
        self, tmp_repo, tmp_path
    ):
        # Bug caught: the concurrency guard so wide that a crash never
        # marks anything -- yesterday's report stays, read as today's.
        rc, out, err = run_memory_script("boot.py", [], cwd=tmp_repo)
        assert rc == 0, f"setup: the earlier boot failed: {out}{err}"
        yesterday = _report(tmp_repo).read_text(encoding="utf-8")
        _back_date(_report(tmp_repo))
        proc, go, waiting = _crashing_boot(tmp_path, tmp_repo)
        go.write_text("go\n", encoding="utf-8")
        try:
            _out, crash_err = proc.communicate(timeout=60)
        finally:
            if proc.poll() is None:
                proc.kill()
        assert "dante: injected boot crash" in crash_err, f"setup invalid: {crash_err!r}"

        now = _report(tmp_repo).read_text(encoding="utf-8")
        assert now != yesterday, "yesterday's report left in place after a crash"
        assert "CHECKS" not in now and "dante: injected boot crash" in now, now
