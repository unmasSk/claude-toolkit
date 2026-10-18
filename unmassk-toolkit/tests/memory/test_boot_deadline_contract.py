"""Test-first contract for issue #95, phase 1: the boot finishes inside
the SessionStart hook timeout (I-005, D-130).

I-005: `health_plans.plans_unreflected` asked GitHub once per issue ever
cited, one call after another. With 37 issues at about 0.87 s each, the
boot passed the 30 s timeout of the SessionStart hook, Claude Code killed
it, and the session started with no briefing and no warning.

D-130: one GitHub query for every issue, under a total time bound; on
failure the check reports through `plans_unreflected_error`, never an
invented result. `boot_launcher.py` keeps its own deadline below the hook
timeout and prints a loud `[memory]` notice when the boot overruns.

HOW THE HOOK IS RUN. Exactly as Claude Code runs it: the `command` string
of the SessionStart entry in `hooks/hooks.json`, through a shell, with
`CLAUDE_PLUGIN_ROOT` set, the SessionStart payload on stdin, from a
disposable git repo. The hook's own `timeout` is read from the same
`hooks.json` -- a separate source from the code under test. The elapsed
time is measured up to the hook PROCESS exit (stdout goes to a file, not
a pipe), so a child left running in the background cannot hide or fake
the measurement.

THE `gh` STUB. A real executable named `gh`, first on the hook's PATH; any
directory holding a real `gh` is removed from that PATH
(`path_without_real_gh`), so no test ever reaches GitHub. It logs every
invocation and answers like the real tool for the two read commands the
check can use:
  - `gh issue view N --json <fields>`  (today's per-issue call)
  - `gh issue list [--state open|closed|all] [--limit N] --json <fields>`
    with the REAL defaults of gh: `--state open`, `--limit 30`.
Anything else (`gh api graphql`, `--jq`, `--search`...) exits 2 with
"unsupported invocation" -- if the implementation needs another command,
the stub is extended by a fresh Dante, never guessed at here.
Every issue's `updatedAt` is a year in the future on purpose: "last
activity" is the last comment, or the creation date when there is none
(health_plans.py docstring). An implementation that reads `updatedAt`
instead would hide every unreflected commit, and the correctness test
goes red.

KNOBS ULTRON MUST EXPOSE (no test sleeps 30 s for real). Read from the
environment at run time; a value that is not a number falls back to the
default, never to a crash or a silent no-op:
  - `UNMASSK_GH_DEADLINE_SECONDS`  -- total bound of the GitHub query in
    `plans_unreflected`.
  - `UNMASSK_BOOT_DEADLINE_SECONDS` -- `boot_launcher.py`'s own deadline
    for `bin/memory/boot.py`.
Their defaults must sit below the hook's 30 s; that is checked by the
real boot in step 1.3 of the plan, not here (it would need a 30 s wait).

Windows: skipped for the same structural reason as every other fake-`gh`
test in this suite (`subprocess.run(["gh", ...])` never resolves a file
without `.exe` there).
"""

import json
import os
import re
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from .conftest import (
    HOOKS_DIR,
    import_lib_memory_module,
    make_session_start_payload,
    path_without_real_gh,
    run_git,
)

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "fake gh on PATH: on Windows subprocess.run(['gh', ...]) without "
        "shell=True never resolves a file without .exe -- same skip as "
        "test_ci_skip_marker.py / test_work_issue_field.py"
    ),
)

_TOOLKIT_ROOT = os.path.dirname(HOOKS_DIR)
_HOOKS_JSON = os.path.join(HOOKS_DIR, "hooks.json")

_GH_KNOB = "UNMASSK_GH_DEADLINE_SECONDS"
_BOOT_KNOB = "UNMASSK_BOOT_DEADLINE_SECONDS"

# Startup cost of a boot on a tiny repo, measured 2026-10-19 on the
# owner's machine: installer 0.4 s + boot ~1 s. The margin is generous on
# purpose (slower CI runner), and still far below what the old serial
# loop costs in every test that uses it.
_STARTUP_MARGIN_S = 5.0

_PLAN_LINE_RE = re.compile(r"plan #(\d+): (\d+) commits? sin reflejar")
_PLANS_ERROR_TEXT = "no se pudo comprobar si hay planes sin reflejar"

_PAST_CREATED = "2020-01-01T00:00:00Z"
_PAST_COMMENT = "2021-06-01T00:00:00Z"


def _future_iso():
    return (datetime.now(timezone.utc) + timedelta(days=365)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )


# --------------------------------------------------------------------------
# The gh stub
# --------------------------------------------------------------------------

_GH_STUB_SOURCE = r'''#!/usr/bin/env python3
"""Fake gh -- Dante, issue #95 test double. Mimics the real tool's
answers for `issue view` and `issue list`; never contacts GitHub."""
import json
import os
import sys
import time

cfg_path = os.environ["GH_STUB_CONFIG"]
with open(cfg_path, encoding="utf-8") as fh:
    cfg = json.load(fh)
args = sys.argv[1:]
with open(cfg["log"], "a", encoding="utf-8") as fh:
    fh.write(json.dumps(args) + "\n")

time.sleep(cfg["latency"])
mode = cfg["mode"]
if mode == "hang":
    time.sleep(cfg["hang_seconds"])
elif mode == "fail":
    sys.stderr.write("HTTP 502: Bad Gateway (https://api.github.com/graphql)\n")
    sys.exit(1)
elif mode == "garbage":
    sys.stdout.write("<html><body>rate limited</body></html>\n")
    sys.exit(0)
elif mode == "wrong_shape":
    sys.stdout.write('{"data": null}\n')
    sys.exit(0)

issues = {int(k): v for k, v in cfg["issues"].items()}
KNOWN_FIELDS = {"number", "state", "createdAt", "updatedAt", "comments"}


def unsupported():
    sys.stderr.write(
        "fake gh (Dante #95 test double): unsupported invocation " + repr(args) + "\n"
    )
    sys.exit(2)


def parse_flags(rest, value_flags):
    out = {}
    i = 0
    while i < len(rest):
        token = rest[i]
        if "=" in token and token.startswith("--"):
            name, value = token.split("=", 1)
            i += 1
        else:
            name = token
            if i + 1 >= len(rest):
                unsupported()
            value = rest[i + 1]
            i += 2
        if name not in value_flags:
            unsupported()
        out[value_flags[name]] = value
    return out


def project(number, fields):
    unknown = [f for f in fields if f not in KNOWN_FIELDS]
    if unknown:
        sys.stderr.write("Unknown JSON field: " + repr(unknown[0]) + "\n")
        sys.exit(1)
    record = dict(issues[number])
    record["number"] = number
    return {f: record[f] for f in fields}


if args[:2] == ["issue", "view"] and len(args) >= 3:
    number_text = args[2].lstrip("#")
    if not number_text.isdigit():
        unsupported()
    flags = parse_flags(args[3:], {"--json": "json", "--repo": "repo", "-R": "repo"})
    if "json" not in flags:
        unsupported()
    number = int(number_text)
    if number not in issues:
        sys.stderr.write(
            "GraphQL: Could not resolve to an issue or pull request with the "
            "number of " + str(number) + ". (repository.issue)\n"
        )
        sys.exit(1)
    sys.stdout.write(json.dumps(project(number, flags["json"].split(","))))
    sys.exit(0)

if args[:2] == ["issue", "list"]:
    flags = parse_flags(
        args[2:],
        {
            "--json": "json",
            "--state": "state",
            "-s": "state",
            "--limit": "limit",
            "-L": "limit",
            "--repo": "repo",
            "-R": "repo",
        },
    )
    if "json" not in flags:
        unsupported()
    state = flags.get("state", "open").lower()
    limit = int(flags.get("limit", "30"))
    chosen = [
        n for n in sorted(issues, reverse=True)
        if state == "all" or issues[n]["state"].lower() == state
    ][:limit]
    fields = flags["json"].split(",")
    sys.stdout.write(json.dumps([project(n, fields) for n in chosen]))
    sys.exit(0)

unsupported()
'''


class GhStub:
    """A `gh` executable on disk plus its configuration and call log."""

    def __init__(self, tmp_path):
        self.dir = tmp_path / "fake-gh-bin"
        self.dir.mkdir()
        exe = self.dir / "gh"
        exe.write_text(_GH_STUB_SOURCE, encoding="utf-8")
        exe.chmod(0o755)
        self.config_path = tmp_path / "gh-stub-config.json"
        self.log_path = tmp_path / "gh-stub-calls.log"
        self.configure()

    def configure(self, *, issues=None, mode="ok", latency=0.0, hang_seconds=0.0):
        self.config_path.write_text(
            json.dumps(
                {
                    "log": str(self.log_path),
                    "mode": mode,
                    "latency": latency,
                    "hang_seconds": hang_seconds,
                    "issues": {str(k): v for k, v in (issues or {}).items()},
                }
            ),
            encoding="utf-8",
        )

    def env(self):
        return {
            "PATH": str(self.dir) + os.pathsep + path_without_real_gh(),
            "GH_STUB_CONFIG": str(self.config_path),
        }

    def calls(self):
        if not self.log_path.exists():
            return []
        return [
            json.loads(line)
            for line in self.log_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]


@pytest.fixture
def gh_stub(tmp_path):
    return GhStub(tmp_path)


def _issue(*, state="OPEN", created=_PAST_CREATED, comment_dates=()):
    return {
        "state": state,
        "createdAt": created,
        "updatedAt": _future_iso(),
        "comments": [
            {"createdAt": d, "body": "progress note", "author": {"login": "bex"}}
            for d in comment_dates
        ],
    }


def _all_unreflected(numbers):
    """Every issue created in the past with no comment: every commit that
    cites it counts as unreflected."""
    return {n: _issue() for n in numbers}


# --------------------------------------------------------------------------
# Seeding the disposable repo
# --------------------------------------------------------------------------


def _cite(repo, issue_number, times=1):
    for i in range(times):
        rc, _out, err = run_git(
            [
                "commit",
                "--allow-empty",
                "-m",
                f"work on #{issue_number} ({i})\n\nIssue: #{issue_number}",
            ],
            repo,
        )
        assert rc == 0, f"seeding commit failed: {err}"


def _seed_citations(repo, citations):
    """`citations`: {issue_number: number of commits citing it}."""
    for number, times in citations.items():
        _cite(repo, number, times)


# --------------------------------------------------------------------------
# Running the hook as Claude Code runs it
# --------------------------------------------------------------------------


def _boot_hook_entry():
    with open(_HOOKS_JSON, encoding="utf-8") as fh:
        config = json.load(fh)
    for group in config["hooks"]["SessionStart"]:
        for hook in group["hooks"]:
            if "boot_launcher.py" in hook["command"]:
                return hook["command"], float(hook["timeout"])
    raise AssertionError("no SessionStart entry runs boot_launcher.py in hooks.json")


class HookRun:
    def __init__(self, rc, elapsed, stdout, stderr, killed, hook_timeout, repo):
        self.rc = rc
        self.elapsed = elapsed
        self.stdout = stdout
        self.stderr = stderr
        self.killed = killed
        self.hook_timeout = hook_timeout
        self.repo = repo

    def memory_lines(self):
        return [line for line in self.stdout.splitlines() if line.startswith("[memory]")]

    def report_path(self):
        return Path(self.repo, ".claude", ".unmassk", "boot-latest.txt")

    def report(self):
        return self.report_path().read_text(encoding="utf-8")

    def describe(self):
        return (
            f"rc={self.rc} elapsed={self.elapsed:.2f}s killed={self.killed}\n"
            f"--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"
        )


def _run_boot_hook(repo, tmp_path, gh_stub, *, kill_after, extra_env=None):
    """Run the registered SessionStart command through a shell, payload on
    stdin, and time it until the hook process exits. If it is still
    running after `kill_after` seconds, its whole process group is killed
    (the test then reports `killed=True`). Any leftover child (a hanging
    fake `gh`) is killed when the hook returns, so nothing outlives the
    test."""
    command, hook_timeout = _boot_hook_entry()
    env = {k: v for k, v in os.environ.items() if k not in (_GH_KNOB, _BOOT_KNOB)}
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    env.update(gh_stub.env())
    env["CLAUDE_PLUGIN_ROOT"] = _TOOLKIT_ROOT
    env["HOME"] = str(home)  # the installer writes ~/.local/bin/gitmem
    env.update(extra_env or {})

    out_path = tmp_path / "hook.stdout"
    err_path = tmp_path / "hook.stderr"
    payload = json.dumps(make_session_start_payload(repo))
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        start = time.monotonic()
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=repo,
            env=env,
            stdin=subprocess.PIPE,
            stdout=out,
            stderr=err,
            start_new_session=True,
        )
        proc.stdin.write(payload.encode("utf-8"))
        proc.stdin.close()
        killed = False
        try:
            rc = proc.wait(timeout=kill_after)
        except subprocess.TimeoutExpired:
            killed = True
            os.killpg(proc.pid, signal.SIGKILL)
            rc = proc.wait()
        elapsed = time.monotonic() - start
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    return HookRun(
        rc,
        elapsed,
        out_path.read_text(encoding="utf-8", errors="replace"),
        err_path.read_text(encoding="utf-8", errors="replace"),
        killed,
        hook_timeout,
        repo,
    )


def _plan_lines(report_text):
    return {int(n): int(k) for n, k in _PLAN_LINE_RE.findall(report_text)}


def _assert_full_briefing(run):
    """The briefing was written and the session was pointed at it: a
    `[memory]` line on stdout and a report with its CHECKS block."""
    assert run.rc == 0, run.describe()
    assert run.memory_lines(), "no [memory] line on stdout\n" + run.describe()
    assert run.report_path().is_file(), "boot-latest.txt not written\n" + run.describe()
    assert "CHECKS" in run.report(), run.report()


# ==========================================================================
# 1. The boot finishes well inside the hook timeout, whatever the history
# ==========================================================================


class TestBootTimeDoesNotGrowWithCitedIssues:
    def test_should_finish_well_inside_hook_timeout_when_40_issues_cited_and_gh_is_slow(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: one GitHub call per issue (I-005). 40 x 0.4 s = 16 s
        # of gh alone; a single batched query costs 0.4 s.
        numbers = range(1, 41)
        _seed_citations(tmp_repo, {n: 1 for n in numbers})
        gh_stub.configure(issues=_all_unreflected(numbers), latency=0.4)
        _command, hook_timeout = _boot_hook_entry()
        bound = hook_timeout / 3  # "well inside" the 30 s the hook gets

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=bound + 2)

        assert not run.killed and run.elapsed < bound, (
            f"boot took {run.elapsed:.1f}s with 40 cited issues; must stay "
            f"under {bound:.0f}s (hook timeout {hook_timeout:.0f}s). "
            f"gh calls: {len(gh_stub.calls())}\n" + run.describe()
        )
        _assert_full_briefing(run)
        assert _plan_lines(run.report()) == {n: 1 for n in numbers}

    def test_should_ask_github_once_whether_5_or_40_issues_are_cited(
        self, tmp_path, gh_stub
    ):
        # Bug caught: cost proportional to history (N+1 calls), or a
        # batch split per issue. D-130: one query for all issues.
        counts = {}
        for how_many in (5, 40):
            repo = tmp_path / f"repo-{how_many}"
            repo.mkdir()
            assert run_git(["init"], str(repo))[0] == 0
            assert run_git(["commit", "--allow-empty", "-m", "init"], str(repo))[0] == 0
            numbers = range(1, how_many + 1)
            _seed_citations(str(repo), {n: 1 for n in numbers})
            if gh_stub.log_path.exists():
                gh_stub.log_path.unlink()
            gh_stub.configure(issues=_all_unreflected(numbers), latency=0.05)

            run_dir = tmp_path / f"run-{how_many}"
            run_dir.mkdir()
            run = _run_boot_hook(str(repo), run_dir, gh_stub, kill_after=60)
            _assert_full_briefing(run)
            counts[how_many] = len(gh_stub.calls())

        assert counts == {5: 1, 40: 1}, (
            f"gh invocations by number of cited issues: {counts}; D-130 "
            "says one GitHub query for every issue"
        )

    def test_should_report_exact_unreflected_counts_when_over_30_issues_and_half_closed(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bugs caught: `gh issue list` without `--state all` (closed issues
        # vanish) or without a `--limit` above 30 (the real default cuts
        # the answer); reading `updatedAt` instead of the last comment;
        # ignoring comments and using `createdAt` only; counting commits
        # wrong for an issue cited twice.
        issues = {}
        citations = {}
        expected = {}
        for n in range(1, 41):
            closed = n % 2 == 0
            if n % 3 == 0:
                # Last comment AFTER every commit: reflected, no line.
                issues[n] = _issue(
                    state="CLOSED" if closed else "OPEN",
                    comment_dates=(_PAST_COMMENT, _future_iso()),
                )
            elif n % 5 == 0:
                # Last comment in the past: commits after it are unreflected.
                issues[n] = _issue(
                    state="CLOSED" if closed else "OPEN", comment_dates=(_PAST_COMMENT,)
                )
            else:
                issues[n] = _issue(state="CLOSED" if closed else "OPEN")
            citations[n] = 2 if n % 4 == 1 else 1
            if n % 3 != 0:
                expected[n] = citations[n]
        _seed_citations(tmp_repo, citations)
        gh_stub.configure(issues=issues, latency=0.0)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        assert _PLANS_ERROR_TEXT not in run.report(), run.report()
        assert _plan_lines(run.report()) == expected, run.report()

    def test_should_not_call_github_when_no_commit_cites_an_issue(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: a batched query fired unconditionally -- a wasted
        # second on every boot, and an error line on a repo with no plans.
        gh_stub.configure(issues={}, latency=0.0)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        assert gh_stub.calls() == []
        assert _PLANS_ERROR_TEXT not in run.report(), run.report()


# ==========================================================================
# 2. GitHub cannot answer: an error line, never an invented result
# ==========================================================================


_THREE_CITED = {3: 1, 7: 2, 11: 1}


class TestGithubFailureIsReportedNotInvented:
    @pytest.mark.parametrize("mode", ["fail", "garbage", "wrong_shape"])
    def test_should_write_error_line_and_rest_of_briefing_when_gh_cannot_answer(
        self, tmp_repo, tmp_path, gh_stub, mode
    ):
        # Bug caught: a failed query read as "nothing unreflected" (empty
        # result) or as made-up counts, or the whole boot dying with it.
        _seed_citations(tmp_repo, _THREE_CITED)
        gh_stub.configure(issues=_all_unreflected(_THREE_CITED), mode=mode)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        report = run.report()
        assert _PLANS_ERROR_TEXT in report, report
        assert _plan_lines(report) == {}, report
        assert "duplicate IDs" in report, report  # the rest of CHECKS still ran

    def test_should_report_error_when_a_cited_issue_is_missing_from_the_answer(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: a batched answer that lacks a cited issue (deleted,
        # transferred, cut by a limit) silently read as "reflected".
        _seed_citations(tmp_repo, _THREE_CITED)
        issues = _all_unreflected(_THREE_CITED)
        del issues[7]
        gh_stub.configure(issues=issues)

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        report = run.report()
        assert _PLANS_ERROR_TEXT in report, report
        assert _plan_lines(report) == {}, report

    def test_should_give_up_within_the_bound_when_gh_hangs(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: no total bound on the GitHub query (only today's
        # 10 s per call), so a hanging GitHub eats the hook's 30 s.
        _seed_citations(tmp_repo, _THREE_CITED)
        gh_stub.configure(
            issues=_all_unreflected(_THREE_CITED), mode="hang", hang_seconds=25
        )
        gh_bound = 1.0

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=25,
            extra_env={_GH_KNOB: str(gh_bound)},
        )

        assert not run.killed and run.elapsed < gh_bound + _STARTUP_MARGIN_S, (
            f"with {_GH_KNOB}={gh_bound} and a hanging gh the boot took "
            f"{run.elapsed:.1f}s\n" + run.describe()
        )
        _assert_full_briefing(run)
        report = run.report()
        assert _PLANS_ERROR_TEXT in report, report
        assert _plan_lines(report) == {}, report

    def test_should_fall_back_to_default_bound_when_gh_knob_is_not_a_number(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: float("soon") blowing up inside the check -- the
        # owner sees an error line every boot for a typo, or worse, the
        # check is skipped.
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]))

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=60, extra_env={_GH_KNOB: "soon"}
        )

        _assert_full_briefing(run)
        assert _PLANS_ERROR_TEXT not in run.report(), run.report()
        assert _plan_lines(run.report()) == {3: 1}, run.report()


class TestHealthBuildCarriesTheError:
    """Unit level: the field the task names. `health.build()` in-process,
    against the same stub; the hook tests above see only the rendered
    text."""

    @pytest.mark.parametrize("mode", ["fail", "garbage", "wrong_shape"])
    def test_should_set_plans_unreflected_error_and_empty_result_when_gh_cannot_answer(
        self, tmp_repo, gh_stub, monkeypatch, mode
    ):
        # Bug caught: `plans_unreflected_error` left None while the result
        # is empty -- the renderer then shows no warning at all.
        health = import_lib_memory_module("health")
        _seed_citations(tmp_repo, _THREE_CITED)
        gh_stub.configure(issues=_all_unreflected(_THREE_CITED), mode=mode)
        for key, value in gh_stub.env().items():
            monkeypatch.setenv(key, value)
        monkeypatch.chdir(tmp_repo)

        report = health.build()

        assert report.plans_unreflected == ()
        assert isinstance(report.plans_unreflected_error, str)
        assert report.plans_unreflected_error.strip()


# ==========================================================================
# 3. The boot overruns anyway: a loud [memory] notice before the hook dies
# ==========================================================================


def _overrun_env(boot_deadline):
    # The gh bound is set far above the launcher's deadline so the plans
    # check cannot save the boot by itself: only the launcher can.
    return {_BOOT_KNOB: str(boot_deadline), _GH_KNOB: "60"}


class TestLauncherFailsLoudOnOverrun:
    def test_should_print_memory_notice_before_deadline_when_boot_overruns(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught: the launcher waits on boot.py with no deadline, Claude
        # Code kills it at 30 s and the session gets nothing (I-005).
        _seed_citations(tmp_repo, {3: 1})
        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=25)
        deadline = 2.0

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=25, extra_env=_overrun_env(deadline)
        )

        assert not run.killed and run.elapsed < deadline + _STARTUP_MARGIN_S, (
            f"with {_BOOT_KNOB}={deadline} the hook took {run.elapsed:.1f}s\n"
            + run.describe()
        )
        assert run.rc == 0, run.describe()
        notices = [line for line in run.memory_lines() if "boot-latest.txt" in line]
        assert notices, (
            "no [memory] line naming boot-latest.txt after an overrun\n"
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
        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=25)
        deadline = 2.0

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=25, extra_env=_overrun_env(deadline)
        )

        assert not run.killed and run.elapsed < deadline + _STARTUP_MARGIN_S, (
            run.describe()
        )
        current = run.report()
        assert current != stale, "previous session's report left as if current"
        assert current.strip(), "report emptied instead of marked"

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
