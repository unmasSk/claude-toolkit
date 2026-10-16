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
"""

import json
import os
import subprocess
import sys

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(_HOOKS_DIR)
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

force_utf8_streams()

_BOOT_SCRIPT = os.path.join(_TOOLKIT_ROOT, "bin", "memory", "boot.py")

try:
    raw = sys.stdin.read()
    try:
        payload = json.loads(raw) if raw else {}
    except ValueError:
        payload = {}

    cwd = payload.get("cwd") or os.getcwd()

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
                timeout=10,
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
                timeout=60,
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

    subprocess.run([sys.executable, _BOOT_SCRIPT], cwd=cwd)
except Exception:
    pass

sys.exit(0)
