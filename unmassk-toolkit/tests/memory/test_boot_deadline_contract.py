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
invocation and answers like the real tool for:
  - `gh api graphql -F/-f key=value ... -f query=...` -- the one request
    the check makes since the fix pass (Cerberus F1): one alias per cited
    issue. Answered by `gh_graphql_fake.py` (same double as the
    in-process tests): only the aliases asked come back, `comments(last:
    K)` vs `first: K` honoured, a missing issue comes back `null` with
    exit 1 and gh's own stderr line.
  - `gh issue view N --json <fields>` (the old per-issue call), kept so a
    regression to N+1 calls fails on TIME, not on an unsupported command.
Anything else (`issue list`, `--jq`, `--search`...) exits 2 with
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

import ast
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from . import gh_graphql_fake
from .conftest import (
    HOOKS_DIR,
    import_lib_memory_module,
    make_session_start_payload,
    path_without_real_gh,
    run_git,
)
from .test_boot_launcher_install_outside_git import _memory_notice_first_lines

pytestmark = pytest.mark.skipif(
    sys.platform == "win32",
    reason=(
        "fake gh on PATH: on Windows subprocess.run(['gh', ...]) without "
        "shell=True never resolves a file without .exe -- same skip as "
        "test_ci_skip_marker.py / test_work_issue_field.py"
    ),
)

_TOOLKIT_ROOT = os.path.dirname(HOOKS_DIR)
_BOOT_SCRIPT = os.path.join(_TOOLKIT_ROOT, "bin", "memory", "boot.py")
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
answers for `api graphql` and `issue view`; never contacts GitHub."""
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

if args[:2] == ["api", "graphql"]:
    sys.path.insert(0, cfg["helper_dir"])
    import gh_graphql_fake

    rc, out, err = gh_graphql_fake.answer(args, issues)
    sys.stdout.write(out)
    sys.stderr.write(err)
    sys.exit(rc)

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
                    "helper_dir": str(Path(__file__).parent),
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

    def report_path_lines(self):
        """`[memory]` lines naming the report by its ABSOLUTE path (git
        resolves the root to its real path, hence `realpath`)."""
        absolute = os.path.realpath(self.report_path())
        return [line for line in self.memory_lines() if absolute in line]

    def describe(self):
        return (
            f"rc={self.rc} elapsed={self.elapsed:.2f}s killed={self.killed}\n"
            f"--- stdout ---\n{self.stdout}\n--- stderr ---\n{self.stderr}"
        )


def _run_boot_hook(repo, tmp_path, gh_stub, *, kill_after, extra_env=None, session_cwd=None):
    """Run the registered SessionStart command through a shell, payload on
    stdin, and time it until the hook process exits. If it is still
    running after `kill_after` seconds, its whole process group is killed
    (the test then reports `killed=True`). Any leftover child (a hanging
    fake `gh`) is killed when the hook returns, so nothing outlives the
    test."""
    command, hook_timeout = _boot_hook_entry()
    env = {k: v for k, v in os.environ.items() if k not in (_GH_KNOB, _BOOT_KNOB)}
    home = tmp_path / "home"
    home.mkdir(parents=True, exist_ok=True)
    env.update(gh_stub.env())
    env["CLAUDE_PLUGIN_ROOT"] = _TOOLKIT_ROOT
    env["HOME"] = str(home)  # the installer writes ~/.local/bin/gitmem
    env.update(extra_env or {})

    tmp_path.mkdir(parents=True, exist_ok=True)
    out_path = tmp_path / "hook.stdout"
    err_path = tmp_path / "hook.stderr"
    session_cwd = session_cwd or repo
    payload = json.dumps(make_session_start_payload(session_cwd))
    with open(out_path, "wb") as out, open(err_path, "wb") as err:
        start = time.monotonic()
        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=session_cwd,
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


def _boot_py_pointer_prefixes():
    """First static text of every `[memory]` line `bin/memory/boot.py`
    prints on a NORMAL boot, read from its AST (never hand-typed)."""
    with open(_BOOT_SCRIPT, encoding="utf-8") as fh:
        prefixes = _memory_notice_first_lines(ast.parse(fh.read()))
    assert prefixes, "setup invalid: no [memory] print found in bin/memory/boot.py"
    return prefixes


def _assert_overrun_notice(run, deadline):
    """Cerberus F4: what the hook printed is an overrun notice, not a
    normal briefing -- a `[memory]` line names the deadline this test set,
    and none of boot.py's normal pointer lines is there."""
    lines = run.memory_lines()
    assert any(f"{deadline:g}" in line for line in lines), (
        f"no [memory] line names the {deadline:g} s deadline\n" + run.describe()
    )
    prefixes = _boot_py_pointer_prefixes()
    normal = [line for line in lines if line.lower().startswith(tuple(prefixes))]
    assert normal == [], (
        "an overrun printed boot.py's normal pointer line\n" + run.describe()
    )


def _assert_failure_marker(run):
    """Cerberus F4: the report file is a failure marker, not a report."""
    assert run.report_path().is_file(), "no boot-latest.txt\n" + run.describe()
    marker = run.report()
    assert marker.strip(), "report emptied instead of marked"
    assert "CHECKS" not in marker, "the marker carries a briefing's CHECKS block:\n" + marker


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

    def test_should_ask_github_only_for_the_cited_issues_when_the_repo_has_many_more(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bug caught (Cerberus F1): a query that reads every issue of the
        # repository, or a numeric range up to the highest cited number,
        # so its cost grows with the repository's whole history instead
        # of with what the commits cite.
        cited = {5: 1, 17: 2, 42: 1, 99: 1}
        _seed_citations(tmp_repo, cited)
        gh_stub.configure(issues=_all_unreflected(range(1, 121)))

        run = _run_boot_hook(tmp_repo, tmp_path, gh_stub, kill_after=60)

        _assert_full_briefing(run)
        calls = gh_stub.calls()
        assert len(calls) == 1, calls
        asked = gh_graphql_fake.requested_issue_numbers(calls[0])
        assert sorted(asked) == sorted(cited), (
            f"GitHub was asked for {sorted(asked)}; the commits cite only "
            f"{sorted(cited)}"
        )
        assert _plan_lines(run.report()) == cited, run.report()

    def test_should_report_exact_unreflected_counts_when_over_30_issues_and_half_closed(
        self, tmp_repo, tmp_path, gh_stub
    ):
        # Bugs caught: closed issues dropped; reading `updatedAt` instead
        # of the last comment; asking `comments(first: 1)` (the OLDEST
        # comment) instead of the last; ignoring comments and using
        # `createdAt` only; counting commits wrong for an issue cited twice.
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
        # Cerberus F2 removed the cited list from a GENERAL gh failure; a
        # cited issue GitHub does not return is still named, so the owner
        # knows which trailer points at nothing.
        error_lines = [line for line in report.splitlines() if _PLANS_ERROR_TEXT in line]
        assert any("#7" in line for line in error_lines), error_lines

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
        deadline = 2.5

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=25, extra_env=_overrun_env(deadline)
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
        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=25)
        deadline = 2.5

        run = _run_boot_hook(
            tmp_repo, tmp_path, gh_stub, kill_after=25, extra_env=_overrun_env(deadline)
        )

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
#
# On a project's first boot (no `.claude/.unmassk/manifest.json`)
# `boot_launcher.py` runs `bin/git-memory-install.py --auto` BEFORE boot.py,
# inside the same 30 s hook, with its own `timeout=60`. A deadline that
# only wraps boot.py leaves that step outside it: a slow install, and
# Claude Code kills the hook in silence -- the very failure of I-005.
#
# HOW THE INSTALL IS SLOWED without touching production code: a
# `sitecustomize.py` on the hook's PYTHONPATH. Python imports it at start-up
# in every interpreter of the hook; it sleeps only when the script being run
# is the installer (`sys.argv[0]`), and leaves a marker file first so the
# test can prove the slow step really was the installer, inside this hook.
# The installer then carries on and works normally.

_SLOW_INSTALL_SITECUSTOMIZE = r'''
import os, sys, time
if os.path.basename(sys.argv[0] if sys.argv else "") == "git-memory-install.py":
    with open(os.environ["SLOW_INSTALL_MARKER"], "a", encoding="utf-8") as fh:
        fh.write("installer started\n")
    time.sleep(float(os.environ["SLOW_INSTALL_SECONDS"]))
'''


def _slow_install_env(tmp_path, seconds):
    site_dir = tmp_path / "slow-install-site"
    site_dir.mkdir()
    (site_dir / "sitecustomize.py").write_text(
        _SLOW_INSTALL_SITECUSTOMIZE, encoding="utf-8"
    )
    marker = tmp_path / "slow-install-started.txt"
    previous = os.environ.get("PYTHONPATH")
    pythonpath = str(site_dir) + (os.pathsep + previous if previous else "")
    env = {
        "PYTHONPATH": pythonpath,
        "SLOW_INSTALL_MARKER": str(marker),
        "SLOW_INSTALL_SECONDS": str(seconds),
    }
    return env, marker


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
#
# HOW GIT IS SLOWED without touching production code: a `git` wrapper
# first on the hook's PATH. It execs the real git for everything, except
# `git rev-parse --show-toplevel` when its trigger holds:
#   - "after_gh": the gh stub has been called (its log exists). boot.py is
#     then blocked on the hanging gh, so the only `rev-parse` left is the
#     launcher's marker step, after the cut (Argus SEC-MED-001).
#   - "first_call": the very first `rev-parse --show-toplevel` of the
#     hook, which is the launcher's install-step check when the repo has no
#     manifest (Ultron's declared bound, min(10, time left)).
# The wrapper is Python and sleeps in-process (no child `sleep`), so a
# `subprocess.run(timeout=...)` that kills it really frees the hook. It
# leaves a marker file first: setup proof that the slow step happened.

_SLOW_GIT_SOURCE = r'''#!/usr/bin/env python3
import os, sys, time
REAL_GIT = %r
args = sys.argv[1:]
if args[:2] == ["rev-parse", "--show-toplevel"]:
    when = os.environ["SLOW_GIT_WHEN"]
    seen = os.environ["SLOW_GIT_SEEN"]
    trigger = (
        os.path.exists(os.environ["SLOW_GIT_AFTER_FILE"])
        if when == "after_gh"
        else not os.path.exists(seen)
    )
    with open(seen, "a", encoding="utf-8") as fh:
        fh.write("rev-parse\n")
    if trigger:
        with open(os.environ["SLOW_GIT_MARKER"], "a", encoding="utf-8") as fh:
            fh.write("slow rev-parse started\n")
        time.sleep(float(os.environ["SLOW_GIT_SECONDS"]))
os.execv(REAL_GIT, [REAL_GIT] + args)
'''


def _slow_git_env(tmp_path, gh_stub, *, when, seconds=60.0):
    real_git = shutil.which("git")
    assert real_git, "setup invalid: no real git on PATH"
    wrapper_dir = tmp_path / "slow-git-bin"
    wrapper_dir.mkdir()
    wrapper = wrapper_dir / "git"
    wrapper.write_text(_SLOW_GIT_SOURCE % os.path.realpath(real_git), encoding="utf-8")
    wrapper.chmod(0o755)
    marker = tmp_path / "slow-git-started.txt"
    env = {
        "PATH": str(wrapper_dir) + os.pathsep + gh_stub.env()["PATH"],
        "SLOW_GIT_WHEN": when,
        "SLOW_GIT_SEEN": str(tmp_path / "slow-git-seen.txt"),
        "SLOW_GIT_AFTER_FILE": str(gh_stub.log_path),
        "SLOW_GIT_MARKER": str(marker),
        "SLOW_GIT_SECONDS": str(seconds),
    }
    return env, marker


def _seed_stale_report(repo):
    report_dir = Path(repo, ".claude", ".unmassk")
    report_dir.mkdir(parents=True, exist_ok=True)
    stale = "BLOQUEANTES -- stale report from a previous session, Dante #95\n"
    (report_dir / "boot-latest.txt").write_text(stale, encoding="utf-8")
    return stale


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
        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=60)
        deadline = 2.5
        git_env, slow_git_started = _slow_git_env(tmp_path, gh_stub, when="after_gh")

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
        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=60)
        git_env, slow_git_started = _slow_git_env(tmp_path, gh_stub, when="after_gh")
        _command, hook_timeout = _boot_hook_entry()

        run = _run_boot_hook(
            tmp_repo,
            tmp_path,
            gh_stub,
            kill_after=hook_timeout + 5,
            extra_env={_GH_KNOB: "60", **git_env},
        )

        assert slow_git_started.is_file(), "setup invalid\n" + run.describe()
        assert not run.killed and run.elapsed < hook_timeout, (
            f"the hook took {run.elapsed:.1f}s with a slow git after the cut; "
            f"Claude Code kills it at {hook_timeout:g}s\n" + run.describe()
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

        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=60)
        deadline = 2.5
        report_dir = normal.report_path().parent
        report_dir.chmod(0o555)
        try:
            failed = _run_boot_hook(
                tmp_repo,
                tmp_path / "read-only",
                gh_stub,
                kill_after=25,
                extra_env=_overrun_env(deadline),
            )
        finally:
            report_dir.chmod(0o755)
        after_failed_write = failed.report()
        replaced = _run_boot_hook(
            tmp_repo,
            tmp_path / "writable",
            gh_stub,
            kill_after=25,
            extra_env=_overrun_env(deadline),
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

        gh_stub.configure(issues=_all_unreflected([3]), mode="hang", hang_seconds=60)
        deadline = 2.5
        overrun = _run_boot_hook(
            tmp_repo,
            tmp_path / "overrun",
            gh_stub,
            kill_after=25,
            extra_env=_overrun_env(deadline),
            session_cwd=str(subfolder),
        )

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
