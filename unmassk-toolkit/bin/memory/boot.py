#!/usr/bin/env python3
"""Session-start entry point: writes the boot report to a file and prints where it is."""

import os
import sys
import time

# Start time: a report written later belongs to a newer session and the failure marker must not overwrite it.
_STARTED = time.time()

_BIN_MEMORY_DIR = os.path.dirname(os.path.abspath(__file__))
_TOOLKIT_ROOT = os.path.dirname(os.path.dirname(_BIN_MEMORY_DIR))
_LIB_MEMORY_DIR = os.path.join(_TOOLKIT_ROOT, "lib", "memory")
if _LIB_MEMORY_DIR not in sys.path:
    sys.path.insert(0, _LIB_MEMORY_DIR)

from utf8 import force_utf8_streams  # noqa: E402  (import after sys.path)

force_utf8_streams()

import boot as boot_lib  # noqa: E402
import boot_common  # noqa: E402
import gitcmd  # noqa: E402
import notes  # noqa: E402


def main(argv):
    """Write the boot report to a file and print only the load order and its path."""
    report = boot_lib.render(boot_lib.build())

    destination = boot_common.report_path(notes.repo_root())
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Atomic: an interrupted boot never leaves a half-written report.
    gitcmd.atomic_write(destination, report)

    # The load order goes before the report path on purpose.
    print("[memory] BEFORE ANSWERING THE USER, in this order:")
    print('  1. Skill tool with skill="unmassk-core"      (TOOL CALL, not bash)')
    print('  2. Skill tool with skill="unmassk-memory"    (TOOL CALL, not bash)')
    print('  3. Skill tool with skill="unmassk-standards" (TOOL CALL, not bash)')
    print("  4. Read the report below whole and give the user the menu of the day.")
    print("  Do not greet or answer anything before the four steps are done.")
    print("")
    print(f"[memory] the boot report is at {destination}")
    print("Read it whole before doing anything. It is not summarised.")
    return 0


def _leave_a_failure_marker(exc: Exception) -> None:
    """Replace the previous report with a failure notice so it is not read as this session's."""
    try:
        boot_common.write_failure_marker(
            notes.repo_root(),
            "EL ARRANQUE FALLÓ",
            f"{exc}\n\n"
            "No hay informe de esta sesión. Lo que había aquí antes era de\n"
            "una sesión anterior y se ha sustituido por este aviso para que\n"
            "nadie lo lea como si fuera de hoy.\n",
            started=_STARTED,
        )
    except Exception:
        # If even this cannot be written, the stderr line below remains.
        pass


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # never a stack trace
        _leave_a_failure_marker(exc)
        print(f"boot.py: {exc}", file=sys.stderr)
        sys.exit(1)
