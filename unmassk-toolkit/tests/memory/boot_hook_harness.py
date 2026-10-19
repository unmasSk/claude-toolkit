"""Running the SessionStart boot hook exactly as Claude Code runs it, for
the issue #95 boot-deadline tests (I-005, D-130). Not a test module.

HOW THE HOOK IS RUN. Exactly as Claude Code runs it: the `command` string
of the SessionStart entry in `hooks/hooks.json`, through a shell, with
`CLAUDE_PLUGIN_ROOT` set, the SessionStart payload on stdin, from a
disposable git repo. The hook's own `timeout` is read from the same
`hooks.json` -- a separate source from the code under test. The elapsed
time is measured up to the hook PROCESS exit (stdout goes to a file, not
a pipe), so a child left running in the background cannot hide or fake
the measurement.

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
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

from .conftest import HOOKS_DIR, make_session_start_payload
from .test_boot_launcher_install_outside_git import _memory_notice_first_lines

POSIX_ONLY = pytest.mark.skipif(
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
