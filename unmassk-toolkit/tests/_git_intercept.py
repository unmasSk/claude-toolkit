"""Shared git-invocation interceptor (issue #60 close-out, round 2).

Replaces the previous PATH-shadowing fake `git` executable (a bare
extensionless POSIX shim, or the `git.cmd` wrapper added in a first
Windows-fix attempt, commit 4b10931) with a direct patch of
`subprocess.Popen` itself.

House confirmed the PATH-shim approach can never work on Windows for this
project's call shape: `lib/git_helpers.py:run_git()` always calls
`subprocess.Popen(["git"] + args, ..., shell=False)`. On Windows that
resolves the child via CreateProcess, which for an extensionless name like
"git" only ever tries appending ".exe" to look it up on PATH — PATHEXT-
based fallback (which is what would ALSO try .cmd/.bat/...) is a cmd.exe
behavior, never consulted by CreateProcess directly. So neither a bare
`git` file nor a `git.cmd` wrapper is ever found by this call shape; the
real git.exe elsewhere on PATH silently wins instead. Not a crash or a
hang — an OBSERVATION blind spot (confirmed root cause of CI run
29110579481, then again of run 29122808531 after the git.cmd attempt):
`assert fetch_calls` fails on an empty log even though the boot under test
behaved correctly, and the inverse `assert not fetch_calls` passes
VACUOUSLY for the same reason (empty log either way).

Patching subprocess.Popen is invocation-path-independent: it intercepts
every git subprocess call this project's own code makes
(lib/git_helpers.py:run_git is the only call site) regardless of how (or
whether) the OS would ever have resolved a "git" PATH entry.

Two install vehicles, one shared implementation (make_intercepted_popen):

  A. Subprocess — a real boot run via tests/conftest.py's run_script(),
     which invokes `[sys.executable, script]` with no -S/-I flag. A
     per-test sitecustomize.py (see test_boot_freshness.py::
     _make_fake_git) is placed on the CHILD's PYTHONPATH. `site` imports
     sitecustomize.py automatically during interpreter startup, before
     session-start-boot.py's own top-level code ever runs, and it calls
     install_via_env() here — which reads the log path from the
     GIT_INTERCEPT_LOG_PATH env var (set on the child's env by the test)
     and installs the patch inside the CHILD process.
  B. In-process — a test that calls a lib/ function directly (e.g.
     boot_git_checks.fetch_memory_ref()), no subprocess involved at all.
     The test itself does:
         real_popen = subprocess.Popen
         monkeypatch.setattr(subprocess, "Popen",
                              make_intercepted_popen(real_popen, log_path))
     — pytest's monkeypatch auto-restores it, no install()/uninstall()
     bookkeeping needed. Patching the real `subprocess` module's own
     `Popen` attribute (not git_helpers.subprocess, not any re-exported
     reference) works regardless of how git_helpers.py imported
     `subprocess` — `import subprocess` binds the SAME module object from
     sys.modules, and `subprocess.Popen(...)` inside run_git() looks up
     `.Popen` on that shared object fresh at call time.

Contract (do not extend without re-reading this): every invocation whose
argv's first token is "git"/"git.exe" is logged
(`{"args": <args after "git">, "env": <the env this Popen call actually
received>}`, one JSON object per line, JSONL — args excludes the leading
"git" token, matching the shape the old fake-git-on-PATH shim produced,
so every pre-existing assertion like `r["args"][0] == "fetch"` keeps
working unchanged) and delegated UNCHANGED to the real subprocess.Popen —
args, kwargs (cwd, env, stdout, stderr, creationflags/start_new_session,
...) all pass through untouched. The ONLY behavioral deviation: a
`git fetch` invocation whose env carries FAKE_GIT_FETCH_HANG_SECONDS gets
its argv swapped for a real sleeping
`sys.executable -c "import time; time.sleep(N)"` child before delegating —
this exercises the REAL communicate(timeout=...) / process-group-kill path
in lib/git_helpers.py:run_git() against a genuinely hung real process,
without depending on real network behavior. No returncode/stdout/stderr is
ever synthesized anywhere in this module; every other command (git or not)
is passed straight through.
"""

import json
import os
import subprocess
import sys


def _looks_like_git(args_list):
    """True if args_list is a Popen argv invoking git — first token is
    literally "git"/"git.exe", or a path ending in one of those,
    case-insensitive. Matches the bare "git" literal every call site in
    this project uses today, and stays correct if a future call site ever
    passes a fully-qualified path instead."""
    if not args_list:
        return False
    first = os.path.basename(str(args_list[0])).lower()
    return first in ("git", "git.exe")


def _log_invocation(log_path, git_args, env):
    """Append one JSONL record. git_args excludes the leading "git" token
    — matches the shape the previous fake-git-on-PATH shim produced (its
    own sys.argv[1:] never included its own program name either), so
    every pre-existing assertion (`r["args"][0] == "fetch"`,
    `r["args"][1] == "origin"`) keeps working unchanged."""
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"args": list(git_args), "env": dict(env)}) + "\n")
    except OSError:
        pass


def make_intercepted_popen(real_popen, log_path):
    """Return a Popen-shaped callable: logs + transparently delegates
    every git invocation to real_popen, with the one env-gated fetch-hang
    substitution documented in the module docstring. Never synthesizes a
    returncode/stdout/stderr — every non-git invocation, and every git
    invocation with no FAKE_GIT_FETCH_HANG_SECONDS in its env, is passed
    through with args/kwargs completely unmodified."""

    def _intercepted_popen(args, *popen_args, **popen_kwargs):
        args_list = list(args) if not isinstance(args, (str, bytes)) else [args]

        if _looks_like_git(args_list):
            env_kwarg = popen_kwargs.get("env")
            observed_env = env_kwarg if env_kwarg is not None else os.environ
            git_args = args_list[1:]
            _log_invocation(log_path, git_args, observed_env)

            if git_args and git_args[0] == "fetch":
                hang = (observed_env or {}).get("FAKE_GIT_FETCH_HANG_SECONDS")
                if hang:
                    sleeper = [sys.executable, "-c", f"import time; time.sleep({float(hang)})"]
                    return real_popen(sleeper, *popen_args, **popen_kwargs)

        return real_popen(args, *popen_args, **popen_kwargs)

    return _intercepted_popen


_installed_for_log_path = None  # guards against double-wrapping subprocess.Popen


def install(log_path):
    """Install the interceptor in THIS process, patching the real
    subprocess.Popen attribute directly. Safe to call more than once with
    the SAME log_path (no-op after the first call) — sitecustomize.py can
    in principle be imported more than once if something re-execs site
    processing. Calling it again with a DIFFERENT log_path in the same
    process is a usage error (would silently orphan the first patch
    layer) and raises instead of guessing which one should win."""
    global _installed_for_log_path
    if _installed_for_log_path == log_path:
        return
    if _installed_for_log_path is not None:
        raise RuntimeError(
            "git interceptor already installed for a different log_path "
            "in this process"
        )
    real_popen = subprocess.Popen
    subprocess.Popen = make_intercepted_popen(real_popen, log_path)
    _installed_for_log_path = log_path


def install_via_env():
    """Entry point for the sitecustomize.py vehicle (A). No-op if
    GIT_INTERCEPT_LOG_PATH isn't set, so importing this module never has a
    side effect unless a test explicitly opted in via that env var."""
    log_path = os.environ.get("GIT_INTERCEPT_LOG_PATH")
    if log_path:
        install(log_path)
