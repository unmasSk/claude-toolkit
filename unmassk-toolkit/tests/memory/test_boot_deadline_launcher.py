"""Issue #95, phase 1 (I-005, D-130): `boot_launcher.py` keeps its own
deadline under the SessionStart hook timeout, counts the first-boot
install inside it, and prints its `[memory]` notice before a slow git can
hold it hostage. Split out of `test_boot_deadline_contract.py`
(2026-10-19, Yoda's size finding); the harness is described in
`boot_hook_harness.py`.
"""

import os
import time
from pathlib import Path

from .boot_hook_gh_stub import (  # noqa: F401  (gh_stub is a fixture)
    _all_unreflected,
    _seed_citations,
    gh_stub,
)
from .boot_hook_harness import (
    _BOOT_KNOB,
    _GH_KNOB,
    _STARTUP_MARGIN_S,
    POSIX_ONLY,
    _assert_failure_marker,
    _assert_full_briefing,
    _assert_overrun_notice,
    _boot_hook_entry,
    _plan_lines,
    _run_boot_hook,
)
from .boot_overrun_tools import (
    _overrun_env,
    _overrunning_boot,
    _seed_stale_report,
    _slow_git_env,
    _slow_install_env,
)

pytestmark = POSIX_ONLY


# ==========================================================================
# 3. The boot overruns anyway: a loud [memory] notice before the hook dies
# ==========================================================================


class TestLauncherFailsLoudOnOverrun:
    def test_should_print_memory_notice_before_deadline_when_boot_overruns(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: the launcher waits on boot.py with no deadline, Claude
        # Code kills it at 30 s and the session gets nothing (I-005).
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        deadline = 2.5
        env, slow_log_started = _overrunning_boot(tmp_path, gh_stub, deadline)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=25, extra_env=env)

        assert slow_log_started.is_file(), (
            "setup invalid: boot.py's git log was never slowed\n" + run.describe()
        )
        assert not run.killed and run.elapsed < deadline + _STARTUP_MARGIN_S, (
            f"with {_BOOT_KNOB}={deadline} the hook took {run.elapsed:.1f}s\n"
            + run.describe()
        )
        assert run.rc == 0, run.describe()
        _assert_overrun_notice(run, deadline)
        assert len(run.report_path_lines()) == 1, (
            "no [memory] line naming the report by its absolute path\n"
            + run.describe()
        )

    def test_should_not_leave_previous_report_untouched_when_boot_overruns(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: yesterday's boot-latest.txt left in place after a
        # killed boot, read next as if it were today's (House, I-005: the
        # failure marker only covered exceptions, never a kill).
        _seed_citations(tmp_repo, {3: 1})
        report_dir = Path(tmp_repo, ".claude", ".unmassk")
        report_dir.mkdir(parents=True)
        stale = "BLOQUEANTES -- stale report from a previous session, Dante #95\n"
        (report_dir / "boot-latest.txt").write_text(stale, encoding="utf-8")
        # The stale report is older than this boot: back-date it, so the
        # concurrent-boot guard (a report written AFTER this boot started
        # is another session's and is kept) can never apply here.
        old = time.time() - 3600
        os.utime(report_dir / "boot-latest.txt", (old, old))
        gh_stub.configure(issues=_all_unreflected([3]))
        deadline = 2.5
        env, slow_log_started = _overrunning_boot(tmp_path, gh_stub, deadline)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=25, extra_env=env)

        assert slow_log_started.is_file(), "setup invalid\n" + run.describe()
        assert not run.killed and run.elapsed < deadline + _STARTUP_MARGIN_S, (
            run.describe()
        )
        current = run.report()
        assert current != stale, "previous session's report left as if current"
        _assert_failure_marker(run)

    def test_should_complete_normally_when_boot_knob_is_not_a_number(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: float("later") raising inside the launcher's
        # swallow-everything try -- boot.py never runs, nothing printed.
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=60, extra_env={_BOOT_KNOB: "later"}
        )

        _assert_full_briefing(run)
        assert _plan_lines(run.report()) == {3: 1}, run.report()


# ==========================================================================
# 4. The deadline counts the WHOLE hook, the first-boot install included
# ==========================================================================
# (how the install is slowed: `boot_overrun_tools.py`)


class TestDeadlineCountsTheInstallStep:
    def test_should_print_memory_notice_within_deadline_when_first_boot_install_is_slow(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: the launcher's deadline wraps only boot.py; the
        # first-boot installer (timeout=60) runs before it, uncounted, so a
        # slow install still overruns the 30 s hook and the session gets
        # nothing (Ultron, boot_launcher.py:84-92, #95).
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        assert not Path(tmp_repo, ".claude", ".unmassk", "manifest.json").exists(), (
            "setup invalid: the repo already has a manifest, the installer "
            "would not run"
        )
        deadline = 2.5
        install_seconds = 20.0
        slow_env, marker = _slow_install_env(tmp_path, install_seconds)
        _command, hook_timeout = _boot_hook_entry()

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=hook_timeout + 5,
            extra_env={**slow_env, _BOOT_KNOB: str(deadline)},
        )

        assert marker.is_file(), (
            "setup invalid: the slowed installer never ran inside the hook\n"
            + run.describe()
        )
        assert not run.killed and run.elapsed < deadline + _STARTUP_MARGIN_S, (
            f"with {_BOOT_KNOB}={deadline} and an install that takes "
            f"{install_seconds:g}s, the hook took {run.elapsed:.1f}s: the "
            "deadline does not count the install step\n" + run.describe()
        )
        assert run.rc == 0, run.describe()
        _assert_overrun_notice(run, deadline)
        assert len(run.report_path_lines()) == 1, run.describe()
        _assert_failure_marker(run)
        # Ultron's declared wording (D-130: the deadline covers the whole
        # hook): the marker says the installer was part of what got
        # stopped, and after how long -- a marker that blamed boot.py alone
        # sends the owner to the wrong script when the install was slow.
        marker = run.report()
        assert "install" in marker.lower() and "boot.py" in marker, marker
        assert f"{deadline:g}" in marker, marker


# ==========================================================================
# 5. After the cut: the notice comes first, the marker step stays bounded,
#    and what the hook says about the marker is true (fix pass, #95)
# ==========================================================================
# (how git is slowed: `boot_overrun_tools.py`)


class TestOverrunNoticeIsNotHeldHostageByGit:
    def test_should_have_printed_the_notice_before_the_marker_step_when_git_is_slow(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Argus SEC-MED-001): the notice printed AFTER the
        # marker step's `git rev-parse` (or not flushed), so a slow git
        # pushes it past the moment Claude Code kills the hook and the
        # session gets nothing. The hook is killed here while git sleeps:
        # whatever was not on stdout by then never will be.
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        deadline = 2.5
        git_env, slow_git_started = _slow_git_env(tmp_path, gh_stub, when="after_log")

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=deadline + _STARTUP_MARGIN_S,
            extra_env={**_overrun_env(deadline), **git_env},
        )

        assert slow_git_started.is_file(), (
            "setup invalid: the marker step's git rev-parse was never slowed\n"
            + run.describe()
        )
        _assert_overrun_notice(run, deadline)

    def test_should_end_inside_the_hook_timeout_with_default_deadline_when_git_is_slow(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bugs caught (Argus SEC-MED-001 and his "defaults below 30 s"
        # gap): the marker step's git call bounded by git's own 10 s cap
        # instead of the time left under the hook timeout (25 + 10 > 30),
        # or a default deadline that does not leave room under the 30 s
        # of hooks.json. Runs with the DEFAULT deadline, so it takes about
        # as long as the hook timeout.
        stale = _seed_stale_report(tmp_repo)
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        git_env, slow_git_started = _slow_git_env(tmp_path, gh_stub, when="after_log")
        _command, hook_timeout = _boot_hook_entry()

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=hook_timeout + 5,
            extra_env={_GH_KNOB: "60", **git_env},
        )

        assert slow_git_started.is_file(), "setup invalid\n" + run.describe()
        # Moriarty fix pass (#95 step 2): ending under the kill is not
        # enough -- the old 25 s + 2 s margin ended at ~28 s, a hair from
        # the kill on a loaded machine. The owner's bar for this pass: the
        # worst-case overrun ends with at least 4 s to spare.
        spare = 4.0
        assert not run.killed and run.elapsed <= hook_timeout - spare, (
            f"the hook took {run.elapsed:.1f}s with a slow git after the cut; "
            f"Claude Code kills it at {hook_timeout:g}s and the overrun must end "
            f"with at least {spare:g}s to spare\n" + run.describe()
        )
        assert run.rc == 0, run.describe()
        assert len(run.report_path_lines()) == 1, run.describe()
        assert run.report() == stale, (
            "setup invalid: the marker was written although git never answered"
        )

    def test_should_cut_the_install_step_git_check_at_the_deadline_when_git_is_slow(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Ultron's declared bound, untested until now): the
        # first-boot `git rev-parse` before the installer bounded by a
        # fixed 10 s instead of min(10, time left), so a slow git eats the
        # deadline and the hook overruns it.
        assert not Path(tmp_repo, ".claude", ".unmassk", "manifest.json").exists(), (
            "setup invalid: the install step would not run"
        )
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        deadline = 2.5
        git_env, slow_git_started = _slow_git_env(tmp_path, gh_stub, when="first_call")

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=30,
            extra_env={_BOOT_KNOB: str(deadline), **git_env},
        )

        assert slow_git_started.is_file(), "setup invalid\n" + run.describe()
        assert not run.killed and run.elapsed < deadline + _STARTUP_MARGIN_S, (
            f"with {_BOOT_KNOB}={deadline} and a slow git before the "
            f"installer, the hook took {run.elapsed:.1f}s\n" + run.describe()
        )
        assert run.rc == 0, run.describe()
        _assert_overrun_notice(run, deadline)
        _assert_failure_marker(run)
