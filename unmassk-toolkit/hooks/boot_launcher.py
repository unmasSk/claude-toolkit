#!/usr/bin/env python3
"""hooks/boot_launcher.py -- SessionStart: launches bin/memory/boot.py.

No logic of its own: every real decision (what is shown, in what order,
what happens in a freshly installed project or on a branch with no
commits) lives in bin/memory/boot.py / lib/memory/boot.py.

The repository is resolved from `payload["cwd"]` when present (same
pattern as hooks/pre-merge-gate.py), otherwise from the process's
inherited cwd.

A boot failure never blocks the session: memory helps, it never blocks
(same principle as hooks/session-start-boot.py, "Exit codes: 0: Always").
Every exception -- boot.py fails, the directory does not exist, stdin is
empty or malformed -- is swallowed silently; the session starts anyway.
The one exception to the silence: the hook (installer + boot.py)
running past the launcher's own deadline, which is reported loudly (D-130).
"""

import json
import os
import subprocess
import sys
import time

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(_HOOKS_DIR)
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)
import boot_common  # noqa: E402

force_utf8_streams()

_BOOT_SCRIPT = os.path.join(_TOOLKIT_ROOT, "bin", "memory", "boot.py")

# The launcher's own deadline for the whole hook -- first-boot installer
# included -- [D-130, I-005]: below the 30 s SessionStart timeout in
# hooks.json, because a hook Claude Code kills prints nothing at all.
_BOOT_DEADLINE_ENV = "UNMASSK_BOOT_DEADLINE_SECONDS"
_BOOT_DEADLINE_DEFAULT = 25.0
# The SessionStart `timeout` in hooks.json, and the time kept back under
# it for printing and exiting once the overrun marker step is done.
_HOOK_TIMEOUT = 30.0
_EXIT_MARGIN = 2.0


def _report_overrun(cwd, deadline, elapsed):
    """The installer or boot.py was killed: say so loudly FIRST, then try
    to replace the previous session's report with a failure marker (so
    nobody reads it as today's), within what is left under the hook
    timeout, and say whether that worked."""
    print(
        f"[memory] THE BOOT DID NOT FINISH within {deadline:g} s: there is no "
        "briefing for this session. Tell the user in your first line, then run "
        f"python3 {_BOOT_SCRIPT} by hand.",
        flush=True,
    )
    destination = boot_common.report_path(cwd)
    try:
        budget = _HOOK_TIMEOUT - _EXIT_MARGIN - elapsed()
        if budget <= 0:
            raise TimeoutError("no time left under the hook timeout")
        found = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=budget,
            encoding="utf-8",
            errors="replace",
        )
        if found.returncode != 0:
            raise RuntimeError("not a git repository")
        root = found.stdout.strip()
        destination = boot_common.report_path(root)
        boot_common.write_failure_marker(
            root,
            "THE BOOT DID NOT FINISH",
            f"The boot (installer + bin/memory/boot.py) was stopped after {deadline:g} s.\n"
            "There is no report for this session. What was here before belonged\n"
            "to an earlier session and has been replaced by this notice so that\n"
            "nobody reads it as today's.\n",
        )
    except Exception:
        print(
            f"[memory] {destination} could NOT be replaced: whatever it holds "
            "is from an earlier session. Do not read it as today's."
        )
        return
    print(f"[memory] {destination} now holds only this failure notice.")


try:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw else {}
    except ValueError:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()
    deadline = boot_common.env_seconds(_BOOT_DEADLINE_ENV, _BOOT_DEADLINE_DEFAULT)
    started = time.monotonic()
    overrun = False

    def _remaining():
        return deadline - (time.monotonic() - started)

    # If this project has never been through the installer, install it
    # HERE, on its own, before reading memory [owner's decision,
    # 2026-08-06: "I just have to walk in, say good morning and have it
    # tell me what to do"].
    #
    # Why here and not waiting for someone to ask: without the installer
    # the project stays half-set-up forever and NOTHING pulls it out. With
    # no `config.json` the system assumes the main branch is protected and
    # rejects the first work commit of the day -- measured over the
    # owner's 14 repositories, 11 would hit it on day one. Without the
    # eight indexes, the `.gitignore` and the launcher on the PATH, every
    # new session starts from zero. The installer is idempotent (run twice
    # in a row: same result, nothing duplicated) and never overwrites a key
    # that already exists.
    #
    # Any failure is swallowed, like everything else in this file: memory
    # helps, it never blocks. If the install fails, boot goes on and the
    # report is written anyway -- the gap is then called out by the report
    # itself, which already knows how to say memory is not mounted.
    _INSTALLER = os.path.join(_TOOLKIT_ROOT, "bin", "git-memory-install.py")
    manifest = os.path.join(cwd, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest) and os.path.isfile(_INSTALLER):
        try:
            # Outside a git repository there is nothing to install:
            # silent, no failure notice.
            inside = subprocess.run(
                ["git", "rev-parse", "--show-toplevel"],
                cwd=cwd,
                capture_output=True,
                timeout=max(0.01, min(10, _remaining())),
            )
            if inside.returncode != 0:
                raise RuntimeError("not a git repository")
            # encoding="utf-8", errors="replace": without `encoding=`,
            # `text=True` decodes with the console codec (cp1252 on
            # Windows), and the installer prints emojis that do not exist
            # in that codec -- decoding blows up in a separate reader
            # thread, outside this try/except [House, 2026-08-08].
            # `errors="replace"` is not optional: the installer's output
            # is not ours to control.
            done = subprocess.run(
                [sys.executable, _INSTALLER, "--auto"],
                cwd=cwd,
                capture_output=True,
                text=True,
                timeout=max(0.01, _remaining()),
                encoding="utf-8",
                errors="replace",
            )
            if done.returncode == 0:
                print(
                    "[memory] this project was not installed and has just "
                    "been installed automatically: gitmem on the PATH, the "
                    "eight indexes and the repository configuration."
                )
            else:
                print(
                    "[memory] this project is NOT installed and the "
                    "automatic install failed. Run it by hand:\n"
                    f"  python3 {_INSTALLER} --auto"
                )
        except subprocess.TimeoutExpired:
            # Only the deadline running out is an overrun; git's own 10 s
            # cap expiring early stays silent, as before.
            overrun = _remaining() <= 0
        except Exception:
            pass

    # `flush` before handing the output to the subprocess, and it is not
    # cosmetic: `bin/memory/boot.py` writes straight to the real
    # descriptor, while what is printed here stays in Python's buffer
    # until the process dies. Without this, the "just installed itself"
    # notice landed AFTER the whole report -- the very line that explains
    # why the project changed, read last and out of context [verified by
    # running it, 2026-08-06].
    sys.stdout.flush()

    if not overrun and _remaining() > 0:
        try:
            subprocess.run(
                [sys.executable, _BOOT_SCRIPT], cwd=cwd, timeout=_remaining()
            )
        except subprocess.TimeoutExpired:
            overrun = True
    else:
        overrun = True
    if overrun:
        _report_overrun(cwd, deadline, lambda: time.monotonic() - started)
except Exception:
    pass

sys.exit(0)
