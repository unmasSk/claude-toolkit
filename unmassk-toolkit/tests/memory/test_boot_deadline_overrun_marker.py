"""Issue #95 (I-005, D-130, fix pass): after a boot overrun, what the hook
says about the report is true, and the marker lands on the same file
boot.py points to. Split out of `test_boot_deadline_contract.py`
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
    POSIX_ONLY,
    _assert_failure_marker,
    _assert_full_briefing,
    _assert_overrun_notice,
    _boot_py_pointer_prefixes,
    _run_boot_hook,
)
from .boot_overrun_tools import _overrunning_boot

pytestmark = POSIX_ONLY


class TestOverrunSaysWhatHappenedToTheMarker:
    def test_should_not_claim_the_marker_replaced_the_report_when_the_write_fails(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Argus SEC-LOW-001): the hook says the report "holds
        # only this failure" while the write failed and yesterday's report
        # is still there, to be read as today's. Three runs on one repo:
        # a normal boot (the previous session's report), an overrun with
        # the report folder read-only, and an overrun with it writable
        # again. The line about the report must differ between the two
        # overruns.
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))
        normal = _run_boot_hook(tmp_repo, tmp_path / "normal", gh_stub, kill_after=60)
        _assert_full_briefing(normal)
        previous = normal.report()
        # The previous session's report: older than both overruns below.
        old = time.time() - 3600
        os.utime(normal.report_path(), (old, old))

        deadline = 2.5
        failed_env, failed_slow_log = _overrunning_boot(
            tmp_path / "read-only", gh_stub, deadline
        )
        replaced_env, replaced_slow_log = _overrunning_boot(
            tmp_path / "writable", gh_stub, deadline
        )
        report_dir = normal.report_path().parent
        report_dir.chmod(0o555)
        try:
            failed = _run_boot_hook(
                tmp_repo,
                tmp_path / "read-only",
                gh_stub,
                kill_after=25,
                extra_env=failed_env,
            )
        finally:
            report_dir.chmod(0o755)
        after_failed_write = failed.report()
        replaced = _run_boot_hook(
            tmp_repo,
            tmp_path / "writable",
            gh_stub,
            kill_after=25,
            extra_env=replaced_env,
        )

        assert failed_slow_log.is_file() and replaced_slow_log.is_file(), (
            "setup invalid: an overrun was not forced by boot.py's slow git log"
        )
        assert after_failed_write == previous, (
            "setup invalid: the read-only folder did not stop the marker write"
        )
        _assert_overrun_notice(failed, deadline)
        failed_lines = failed.report_path_lines()
        assert len(failed_lines) == 1, (
            "after a failed marker write, no [memory] line names the report "
            "that is still there\n" + failed.describe()
        )
        _assert_failure_marker(replaced)
        replaced_lines = replaced.report_path_lines()
        assert len(replaced_lines) == 1, replaced.describe()
        assert failed_lines != replaced_lines, (
            "the hook says the same thing whether or not the old report was "
            f"replaced: {failed_lines[0]!r}"
        )


class TestBothWritersShareOneReportPath:
    def test_should_mark_the_same_file_boot_py_points_to_when_cwd_is_a_subfolder(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Cerberus F3): the launcher's overrun marker and
        # boot.py's report written to different places (e.g. the launcher
        # using the session cwd instead of the repository root), so the
        # stale-report protection marks a file nobody reads. The session
        # starts in a subfolder, where the two can drift apart.
        _seed_citations(tmp_repo, {3: 1})
        subfolder = Path(tmp_repo, "src", "deep")
        subfolder.mkdir(parents=True)
        gh_stub.configure(issues=_all_unreflected([3]))
        normal = _run_boot_hook(
            tmp_repo, tmp_path / "normal", gh_stub, kill_after=60,
            session_cwd=str(subfolder),
        )
        _assert_full_briefing(normal)
        pointed = normal.report_path_lines()
        assert len(pointed) == 1, (
            "boot.py, started from a subfolder, did not point to the report "
            "at the repository root\n" + normal.describe()
        )
        assert pointed[0].lower().startswith(tuple(_boot_py_pointer_prefixes())), pointed
        old = time.time() - 3600  # the previous session's report
        os.utime(normal.report_path(), (old, old))

        deadline = 2.5
        env, slow_log_started = _overrunning_boot(tmp_path / "overrun", gh_stub, deadline)
        overrun = _run_boot_hook(
            tmp_repo,
            tmp_path / "overrun",
            gh_stub,
            kill_after=25,
            extra_env=env,
            session_cwd=str(subfolder),
        )

        assert slow_log_started.is_file(), "setup invalid\n" + overrun.describe()
        _assert_overrun_notice(overrun, deadline)
        named = overrun.report_path_lines()
        assert len(named) == 1, (
            f"boot.py points to the report at the root ({pointed[0]!r}); the "
            f"overrun does not name that file\n" + overrun.describe()
        )
        _assert_failure_marker(overrun)
        assert not Path(subfolder, ".claude").exists(), (
            "the overrun wrote a report under the session's subfolder"
        )
