#!/usr/bin/env python3
"""Notification hook: play Morse three times, 0.3 s apart (D-102, D-132).

hooks.json's matcher limits it to permission_prompt|idle_prompt. It never
waits for playback and never fails the notification; without afplay on PATH
it does nothing.
"""
import shutil
import subprocess
import sys
import time

_SOUND = "/System/Library/Sounds/Morse.aiff"
_PLAYS = 3
_GAP_S = 0.3


def main():
    afplay = shutil.which("afplay")
    if afplay is None:
        return
    for i in range(_PLAYS):
        if i:
            time.sleep(_GAP_S)
        try:
            # Detached, no inherited stdio: a stuck audio device must not hold
            # the hook (or Claude Code's pipe) open.
            subprocess.Popen(
                [afplay, _SOUND],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError as exc:
            print(f"owner-cue: afplay could not start: {exc}", file=sys.stderr)
            return


if __name__ == "__main__":
    main()
    sys.exit(0)
