"""Forcing a boot overrun without touching production code: a slow
first-boot installer and a slow `git` on the hook's PATH (issue #95,
I-005, D-130). Not a test module.
"""

import os
import shutil
import time
from pathlib import Path

from .boot_hook_harness import _BOOT_KNOB, _GH_KNOB


def _overrun_env(boot_deadline):
    # The gh bound is set far above the launcher's deadline so the plans
    # check cannot save the boot by itself: only the launcher can. The
    # overrun itself is forced by a slow `git log` inside boot.py
    # (`_overrunning_boot`, below): since the Moriarty fix pass a
    # hanging gh is cut to what is left and no longer overruns.
    return {_BOOT_KNOB: str(boot_deadline), _GH_KNOB: "60"}


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


# HOW GIT IS SLOWED without touching production code: a `git` wrapper
# first on the hook's PATH. It execs the real git for everything, except:
#   - `git log` run BY bin/memory/boot.py (its parent process), when
#     `slow_boot_log` is on: the way to force an overrun since the
#     Moriarty fix pass. A hanging gh no longer overruns (the network
#     steps share what is left of the deadline and are skipped when
#     nothing is left), but boot.py reads the log locally, uncut by any
#     network budget -- a slow disk or a huge history. The installer's own
#     `git log` (first boot) is NOT slowed, so the overrun is boot.py's.
#   - `git rev-parse --show-toplevel` when its trigger holds:
#       - "after_log": the slowed boot `git log` has started. boot.py is
#         then blocked on it, so the only `rev-parse` left is the
#         launcher's marker step, after the cut (Argus SEC-MED-001).
#       - "first_call": the very first `rev-parse --show-toplevel` of the
#         hook, which is the launcher's install-step check when the repo
#         has no manifest (Ultron's declared bound, min(10, time left)).
# The wrapper is Python and sleeps in-process (no child `sleep`), so a
# `subprocess.run(timeout=...)` that kills it really frees the hook. It
# leaves a marker file first: setup proof that the slow step happened.

_SLOW_GIT_SOURCE = r'''#!/usr/bin/env python3
import os, subprocess, sys, time
REAL_GIT = %r
args = sys.argv[1:]


def parent_is_boot_py():
    parent = subprocess.run(
        ["ps", "-o", "args=", "-p", str(os.getppid())],
        capture_output=True, text=True,
    ).stdout
    return os.path.join("bin", "memory", "boot.py") in parent


if args[:1] == ["log"] and os.environ.get("SLOW_GIT_BOOT_LOG") == "1" and parent_is_boot_py():
    with open(os.environ["SLOW_GIT_LOG_MARKER"], "a", encoding="utf-8") as fh:
        fh.write("slow boot git log started\n")
    time.sleep(float(os.environ["SLOW_GIT_SECONDS"]))
if args[:2] == ["rev-parse", "--show-toplevel"] and os.environ.get("SLOW_GIT_WHEN"):
    when = os.environ["SLOW_GIT_WHEN"]
    seen = os.environ["SLOW_GIT_SEEN"]
    trigger = (
        os.path.exists(os.environ["SLOW_GIT_LOG_MARKER"])
        if when == "after_log"
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


class SlowGit:
    """The env for the hook plus the two setup-proof marker files."""

    def __init__(self, env, rev_parse_marker, boot_log_marker):
        self.env = env
        self.rev_parse_marker = rev_parse_marker
        self.boot_log_marker = boot_log_marker


def _slow_git(tmp_path, gh_stub, *, when=None, slow_boot_log=False, seconds=60.0):
    real_git = shutil.which("git")
    assert real_git, "setup invalid: no real git on PATH"
    wrapper_dir = tmp_path / "slow-git-bin"
    wrapper_dir.mkdir(parents=True)
    wrapper = wrapper_dir / "git"
    wrapper.write_text(_SLOW_GIT_SOURCE % os.path.realpath(real_git), encoding="utf-8")
    wrapper.chmod(0o755)
    rev_parse_marker = tmp_path / "slow-git-started.txt"
    boot_log_marker = tmp_path / "slow-boot-log-started.txt"
    env = {
        "PATH": str(wrapper_dir) + os.pathsep + gh_stub.env()["PATH"],
        "SLOW_GIT_WHEN": when or "",
        "SLOW_GIT_BOOT_LOG": "1" if slow_boot_log else "0",
        "SLOW_GIT_SEEN": str(tmp_path / "slow-git-seen.txt"),
        "SLOW_GIT_LOG_MARKER": str(boot_log_marker),
        "SLOW_GIT_MARKER": str(rev_parse_marker),
        "SLOW_GIT_SECONDS": str(seconds),
    }
    return SlowGit(env, rev_parse_marker, boot_log_marker)


def _slow_git_env(tmp_path, gh_stub, *, when, seconds=60.0):
    slow = _slow_git(
        tmp_path, gh_stub, when=when, slow_boot_log=(when == "after_log"), seconds=seconds
    )
    return slow.env, slow.rev_parse_marker


def _overrunning_boot(tmp_path, gh_stub, boot_deadline):
    """Env that makes bin/memory/boot.py overrun `boot_deadline`: its
    `git log` sleeps 60 s. Returns (env, marker proving the slow log ran)."""
    slow = _slow_git(tmp_path, gh_stub, slow_boot_log=True)
    return {**_overrun_env(boot_deadline), **slow.env}, slow.boot_log_marker


def _seed_stale_report(repo):
    report_dir = Path(repo, ".claude", ".unmassk")
    report_dir.mkdir(parents=True, exist_ok=True)
    stale = "BLOQUEANTES -- stale report from a previous session, Dante #95\n"
    (report_dir / "boot-latest.txt").write_text(stale, encoding="utf-8")
    old = time.time() - 3600  # a previous session's: older than any boot here
    os.utime(report_dir / "boot-latest.txt", (old, old))
    return stale
