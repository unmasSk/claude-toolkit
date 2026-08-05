"""
Surviving coverage for issue #61's read-path retry contract.

Originally salvaged from test_issue61_breadcrumbs.py and
test_issue61_read_retry_contract.py (2 files, ~1800 lines combined) when
memory v2 (docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3) deleted lib/recall.py
and lib/boot_memory.py entirely, removed
git_helpers.py::commits_since_last_consolidation(), and retired the
hooks/precompact-snapshot.py hook — every test that drove those symbols
(_scan_commits(), extract_memory(), extract_glossary(),
commits_since_last_consolidation(), extract_memory_from_log(),
format_snapshot()) died with them. See git history for the deleted files.

Retired 2026-08-02 (5th Dante entry): TestGetTimelineReadRetryContract and
TestGetLastContextTimeReadRetryContract, which drove
boot_git_checks.get_timeline() / get_last_context_time(). Both functions
were deleted from lib/boot_git_checks.py that day (112 dead lines, zero
production callers), together with their re-export in lib/boot_checks.py.

2026-08-04 (DEUDA.md point 23): lib/bootstrap_commits.py itself was
retired — `grep -rn "bootstrap_commits" unmassk-toolkit/` confirmed zero
production callers of `scan_recent_commits()` anywhere in hooks/ or bin/,
only this test file and the now-deleted
test_bootstrap_commits_date_field_contract.py drove it. Its two internal
`run_git_read_retrying()` call sites were the SOLE remaining production
caller of that shared helper (`grep -rn "run_git_read_retrying"` confirmed
no other lib/hooks/bin file calls it after the memory-v2 deletions above).
The two test classes that used to reach the helper THROUGH
`scan_recent_commits()` (TestScanRecentCommitsReadRetryContract,
TestScanRecentCommitsBreadcrumb) are rewritten below to call
`lib/git_helpers.py::run_git_read_retrying()` DIRECTLY against a real git
repo — TestRunGitReadRetryingRealRepoContract and
TestRunGitReadRetryingBreadcrumb — preserving the same 3 core assertions:
a transient failure recovers via retry and round-trips real git data
(never a fabricated/mocked value); a genuine success makes exactly 1 call
with clean stderr; a persistent failure emits a visible breadcrumb and
returns the unchanged fail-safe `(code != 0, "")` shape, never a silent or
degraded value. TestRunGitReadRetryingDeadline (below) is untouched by
this pass — it always tested `git_helpers.run_git_read_retrying()`
directly via a fake clock and a fake `run_git_fn`, and never depended on
`bootstrap_commits` in the first place.

Build mode: n/a (retirement + salvage pass, linear). No production code is
touched by this file.
"""

import os
import sys

import pytest

from conftest import LIB_DIR, git_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import git_helpers  # noqa: E402


# ── Repo helpers ─────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, trailers=""):
    msg = subject
    if trailers:
        msg = subject + "\n\n" + trailers
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _make_broken_dir(tmp_path, name="not_a_repo"):
    """A real directory that EXISTS but is not a git repo in any ancestor."""
    broken = tmp_path / name
    broken.mkdir()
    return str(broken)


# ── run_git doubles (always delegate to the REAL function — never
#    reimplement the print/parsing, so the breadcrumb/behavior asserted is
#    genuine production code executing) ────────────────────────────────────

def _make_flaky_run_git(real_run_git, fail_times, broken_dir, match=None):
    """Double: the first `fail_times` calls matching `match(args)` (default:
    all) are redirected to `broken_dir` (real failure, rc=128); the rest
    pass through to the real function untouched.
    """
    state = {"n": 0}
    _match = match or (lambda args: True)

    def _flaky(args, **kwargs):
        if _match(args):
            state["n"] += 1
            if state["n"] <= fail_times:
                kwargs["cwd"] = broken_dir
        return real_run_git(args, **kwargs)

    return _flaky, state


def _make_counting_run_git(real_run_git):
    calls = {}

    def _counting(args, **kwargs):
        key = args[0] if args else ""
        calls[key] = calls.get(key, 0) + 1
        return real_run_git(args, **kwargs)

    return _counting, calls


class _FakeTimeModule:
    """Replaces the NAME `time` bound in git_helpers's own namespace
    (`import time` at module level) — never touches the real stdlib `time`
    module globally. run_git_read_retrying() resolves time.monotonic()/
    time.sleep() as names in git_helpers's namespace at call time, so
    swapping only that reference (`monkeypatch.setattr(git_helpers, "time",
    fake)`) intercepts the clock only inside that module.
    """

    def __init__(self, start=0.0):
        self._t = start
        self.sleep_calls = []

    def monotonic(self):
        return self._t

    def sleep(self, seconds):
        self.sleep_calls.append(seconds)  # never sleeps for real

    def advance(self, dt):
        self._t += dt
        return self._t


# ── lib/git_helpers.py -- run_git_read_retrying() (SEC-HIGH-001, clock deadline) ─
#
# Direct test of the shared helper -- where ALL the deadline logic lives,
# isolated from any specific call site (unit-level: the value is in the
# pure loop logic, not the wiring). Clock controlled via _FakeTimeModule
# above -- never a real 10s sleep.


class TestRunGitReadRetryingDeadline:
    def test_hanging_first_attempt_never_starts_a_second_attempt(self, monkeypatch):
        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        call_count = {"n": 0}

        def _hanging_run_git(args, **kwargs):
            call_count["n"] += 1
            # Simulates a real hang: the call itself consumes ~all of the
            # GIT_TIMEOUT budget before returning (a real run_git() returns
            # (1, "") after its own internal timeout -- same shape here,
            # without a real sleep).
            fake_time.advance(git_helpers.GIT_TIMEOUT)
            return 1, ""

        code, output = git_helpers.run_git_read_retrying(_hanging_run_git, ["log", "--all"])

        assert call_count["n"] == 1, (
            f"An attempt that exhausts the clock budget must not trigger "
            f"a 2nd attempt -- {call_count['n']} calls were made to "
            f"run_git_fn (expected worst case: ~1x GIT_TIMEOUT, not "
            f"{git_helpers.READ_RETRY_ATTEMPTS}x)"
        )
        assert (code, output) == (1, ""), f"Fail-safe return must be unchanged -- got {(code, output)!r}"

    def test_anti_vacuity_fast_failures_still_get_full_retry_budget(self, monkeypatch):
        """Proves the assertion above genuinely distinguishes "hang" from
        "fast failure": if each attempt only consumes a tiny fraction of
        the budget, the helper MUST reach the full READ_RETRY_ATTEMPTS --
        it doesn't vacuously cut off at 1 always, only when the budget is
        genuinely exhausted.
        """
        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        call_count = {"n": 0}

        def _fast_failing_run_git(args, **kwargs):
            call_count["n"] += 1
            fake_time.advance(0.01)  # fast failure, not a hang
            return 1, ""

        code, output = git_helpers.run_git_read_retrying(_fast_failing_run_git, ["log", "--all"])

        assert call_count["n"] == git_helpers.READ_RETRY_ATTEMPTS, (
            f"Fast failures (never exhausting the clock budget) must "
            f"exhaust the normal {git_helpers.READ_RETRY_ATTEMPTS} "
            f"attempts -- {call_count['n']} were made"
        )
        assert (code, output) == (1, "")

    def test_slow_then_would_be_hanging_second_attempt_gets_capped_timeout(
        self, monkeypatch,
    ):
        """Repair pass after Moriarty: the earlier deadline test
        (test_hanging_first_attempt_never_starts_a_second_attempt) only
        covered "the 1st attempt hangs" -- blocked by the "don't start a
        new attempt if less than READ_RETRY_MIN_ATTEMPT_SECONDS remains"
        gate. The real hole Moriarty demonstrated: attempt 1 SLOW-BUT-REAL
        (fails after consuming almost the whole budget, e.g. 9.3s of 10s)
        leaves ~0.7s of budget -- enough for the gate to still allow a 2nd
        attempt to start (0.7s > READ_RETRY_MIN_ATTEMPT_SECONDS = 0.5s).
        Without a PER-ATTEMPT cap, that 2nd attempt could hang for another
        full GIT_TIMEOUT (total ~2x, exactly the scenario SEC-HIGH-001
        wanted closed). Ultron's real fix: every attempt receives
        `timeout=max(0.1, min(remaining_budget, GIT_TIMEOUT))` -- the 2nd
        attempt here must receive ~0.7s, not 10s.
        """
        fake_time = _FakeTimeModule(start=1000.0)
        monkeypatch.setattr(git_helpers, "time", fake_time)

        received_timeouts = []

        def _slow_then_hanging_run_git(args, **kwargs):
            received_timeouts.append(kwargs.get("timeout"))
            if len(received_timeouts) == 1:
                # Attempt 1: slow but real -- consumes ~9.3s of the 10s
                # budget before failing (not a pure hang).
                fake_time.advance(9.3)
                return 1, ""
            # Attempt 2 (and any later one, if the gate failed to block
            # it): simulates hanging -- a real run_git() would kill it at
            # its own timeout (the capped value it received in kwargs), so
            # the clock advances by EXACTLY that timeout, never the full
            # GIT_TIMEOUT.
            fake_time.advance(kwargs.get("timeout") or git_helpers.GIT_TIMEOUT)
            return 1, ""

        start = fake_time.monotonic()
        code, output = git_helpers.run_git_read_retrying(_slow_then_hanging_run_git, ["log", "--all"])
        total_elapsed = fake_time.monotonic() - start

        assert len(received_timeouts) == 2, (
            f"Expected EXACTLY 2 attempts -- the 1st (slow, exhausts "
            f"~9.3s) and the 2nd (starts with ~0.7s remaining, 'hangs' "
            f"until that remainder is exhausted -- a 3rd has no budget "
            f"left to start). {len(received_timeouts)} were made, "
            f"timeouts received={received_timeouts!r}"
        )
        assert received_timeouts[0] == pytest.approx(git_helpers.GIT_TIMEOUT, abs=0.01), (
            f"The 1st attempt starts with the full budget -- expected "
            f"timeout≈{git_helpers.GIT_TIMEOUT}, got {received_timeouts[0]!r}"
        )
        assert received_timeouts[1] is not None and received_timeouts[1] < git_helpers.GIT_TIMEOUT * 0.9, (
            f"THE CENTRAL POINT OF THIS TEST: the 2nd attempt must receive "
            f"a timeout CAPPED to the REMAINING budget (~0.7s), NOT the "
            f"full GIT_TIMEOUT ({git_helpers.GIT_TIMEOUT}s) -- if it "
            f"received the full GIT_TIMEOUT, a real hang on the 2nd "
            f"attempt could cost another full GIT_TIMEOUT (~2x total), "
            f"exactly the hole Moriarty demonstrated. Got "
            f"{received_timeouts[1]!r}"
        )
        assert total_elapsed <= git_helpers.GIT_TIMEOUT * 1.1, (
            f"The total simulated clock must not exceed ~1x GIT_TIMEOUT "
            f"({git_helpers.GIT_TIMEOUT}s) -- got {total_elapsed!r}s. A "
            f"total close to 2x GIT_TIMEOUT would indicate the 2nd "
            f"attempt was left to hang without the per-attempt cap (the "
            f"bug Moriarty demonstrated before this fix)."
        )
        assert (code, output) == (1, ""), f"Fail-safe return must be unchanged -- got {(code, output)!r}"


# ── lib/git_helpers.py -- run_git_read_retrying() against a REAL repo ───
#
# Not a fake clock/fake run_git_fn like the class above -- this exercises
# the helper wired to the REAL git_helpers.run_git() against a real,
# on-disk git repo, proving retry recovers a genuine transient failure and
# returns genuinely round-tripped git data (unmassk-standards §34: the
# producer is real `git log`, never a hand-typed fixture standing in for
# it). Until 2026-08-04 this coverage lived at
# lib/bootstrap_commits.py::scan_recent_commits() (2 internal call sites);
# that module is retired (DEUDA.md #23, zero production callers), so this
# now calls run_git_read_retrying() directly -- see the module docstring.


class TestRunGitReadRetryingRealRepoContract:
    def test_retry_recovers_transient_failure_returns_real_commit_round_trip(
        self, tmp_path, monkeypatch,
    ):
        """A transient failure on the 1st attempt must recover via retry
        and return the REAL commit this test wrote (round-trip §34), not
        an empty/degraded result.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: issue61directretrymarker")
        monkeypatch.chdir(repo)
        broken = _make_broken_dir(tmp_path)

        real_run_git = git_helpers.run_git
        flaky, state = _make_flaky_run_git(real_run_git, fail_times=1, broken_dir=broken)

        code, output = git_helpers.run_git_read_retrying(
            flaky, ["log", "-n", "20", "--pretty=format:%h\x1f%s"],
        )

        assert code == 0, (
            f"A transient failure on the 1st attempt must recover via "
            f"retry -- got code={code!r}, calls={state['n']}"
        )
        assert "issue61directretrymarker" in output, (
            f"Expected the REAL commit this test wrote in the round-"
            f"tripped output, not an empty/degraded result -- "
            f"output={output!r}"
        )

    def test_genuine_success_no_retry_no_warn(self, tmp_path, monkeypatch, capsys):
        """Anti-false-positive control: a genuine success (rc=0) must make
        exactly 1 call and leave stderr clean -- no retry, no WARN.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: alpha")
        _commit(repo, "chore: beta")
        monkeypatch.chdir(repo)

        real_run_git = git_helpers.run_git
        counting, calls = _make_counting_run_git(real_run_git)

        code, output = git_helpers.run_git_read_retrying(
            counting, ["log", "-n", "20", "--pretty=format:%h\x1f%s"],
        )

        assert code == 0
        assert "chore: alpha" in output and "chore: beta" in output, (
            f"Expected both real commits round-tripped -- output={output!r}"
        )
        assert calls.get("log") == 1, (
            f"A genuine success (rc=0) must not retry -- {calls.get('log')} "
            f"calls were made"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr must stay clean -- got: {captured.err!r}"


# ── lib/git_helpers.py -- run_git_read_retrying() breadcrumb (mechanism A) ─
#
# Proves the `log_stderr_on_failure=True` breadcrumb survives a REAL,
# persistent failure (never retried away) and that the fail-safe return
# shape (code != 0, "") is left unchanged -- never a silent/degraded value.


class TestRunGitReadRetryingBreadcrumb:
    def test_persistent_failure_breadcrumb_and_failsafe_return_unchanged(
        self, tmp_path, monkeypatch, capsys,
    ):
        broken = _make_broken_dir(tmp_path)
        monkeypatch.chdir(broken)

        code, output = git_helpers.run_git_read_retrying(
            git_helpers.run_git,
            ["log", "-n", "20", "--pretty=format:%h\x1f%s"],
            log_stderr_on_failure=True,
        )

        assert code != 0 and output == "", (
            f"A total, persistent git failure must fail-safe to "
            f"(code != 0, '') unchanged -- got {(code, output)!r}"
        )
        captured = capsys.readouterr()
        assert "[git_helpers] git 'log' exited 128" in captured.err, (
            f"Expected the breadcrumb in stderr -- got: {captured.err!r}"
        )

    def test_anti_vacuity_valid_repo_returns_real_data_with_clean_stderr(
        self, tmp_path, monkeypatch, capsys,
    ):
        """Anti-vacuity control: a healthy repo must return the REAL
        commit (not an empty/degraded value) AND leave stderr clean.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "chore: alpha")
        monkeypatch.chdir(repo)

        code, output = git_helpers.run_git_read_retrying(
            git_helpers.run_git,
            ["log", "-n", "20", "--pretty=format:%h\x1f%s"],
            log_stderr_on_failure=True,
        )

        assert code == 0
        assert "chore: alpha" in output, (
            f"Expected the real commit round-tripped -- output={output!r}"
        )
        captured = capsys.readouterr()
        assert captured.err == "", f"stderr must stay clean on success -- got: {captured.err!r}"
