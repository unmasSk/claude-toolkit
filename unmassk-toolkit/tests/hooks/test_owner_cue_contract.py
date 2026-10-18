"""Test-first contract for issue #95, part 2d: the owner cue (D-102, D-132).

D-102 (Bex, 2026-10-18, chosen by ear): when he is needed, play
`/System/Library/Sounds/Morse.aiff` three times, 0.3 s apart -- the command
tried on his Mac was `afplay Morse.aiff & sleep 0.3; afplay ... & sleep 0.3;
afplay ...`. One beep was too easy to miss; back-to-back plays left a gap;
0.15 s blurred them.

D-132: the cue rides Claude Code's Notification event, matcher
`permission_prompt|idle_prompt` -- exactly the two moments Claude waits on
him. A Stop hook (X-126) and a PreToolUse hook on AskUserQuestion (X-127)
were discarded. The hook never blocks or fails the notification, and does
nothing where afplay is missing.

HOW THE HOOK IS RUN. Exactly as Claude Code runs it: the `command` string of
the Notification entry that names `owner-cue.py` in `hooks/hooks.json`,
through a shell, with `CLAUDE_PLUGIN_ROOT` set and a real Notification
payload on stdin (shape from code.claude.com/docs/en/hooks). stdout/stderr go
to files, the hook runs in its own process group, and every fake afplay it
started is killed after the test.

NO TEST EVER PLAYS SOUND. The hook's PATH is a scratch dir (a `python3`
wrapper and, when the test wants one, a fake `afplay`) plus `/bin`. The real
afplay lives in `/usr/bin`, which is NOT on that PATH. The fake records
start time, argv and pid of every call, then sleeps (it "plays") for a set
time.

CONSTRAINTS THIS CONTRACT PUTS ON THE IMPLEMENTATION (declared for Ultron):
  - afplay is found through PATH (e.g. `shutil.which("afplay")`), never by
    the absolute path `/usr/bin/afplay`. A hard-coded path bypasses the fake
    -- the tests go red, and on a Mac they would also play through the
    speakers.
  - "Does nothing where afplay is missing" is decided by afplay's presence,
    not by `sys.platform`: these tests run on Linux CI with a fake afplay on
    PATH and expect it to be called there too.
  - The hook does not wait for playback to finish: with each play lasting
    3 s, the hook process must exit in under 2.5 s (the three launches,
    0.6 s of spacing, are fine). A stuck audio device must never hold the
    notification up to the hook timeout.
  - The filter on notification type is the matcher in hooks.json -- that is
    where Claude Code applies it. The script is not required to re-filter.

Windows: skipped -- `${CLAUDE_PLUGIN_ROOT}` in the command is POSIX shell
expansion and afplay does not exist there.
"""

import json
import os
import re
import signal
import subprocess
import sys
import time

import pytest

_PERL = "/usr/bin/perl"
_WARMUP_ARG = "--owner-cue-test-warmup"

pytestmark = [
    pytest.mark.skipif(
        sys.platform == "win32",
        reason="POSIX shell command + afplay; not applicable on Windows",
    ),
    pytest.mark.skipif(
        not os.path.isfile(_PERL),
        reason="the fake afplay is a Perl script (fast start, precise timing)",
    ),
]

_TESTS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TOOLKIT_ROOT = os.path.dirname(_TESTS_DIR)
_HOOKS_JSON = os.path.join(_TOOLKIT_ROOT, "hooks", "hooks.json")
_HOOK_FILE = "owner-cue.py"

# Expected values come from D-102 / D-132, never from the code under test.
_MORSE = "/System/Library/Sounds/Morse.aiff"
_PLAYS = 3
_GAP_MIN_S = 0.25          # D-102: 0.3 s apart; 0.15 s was rejected as blurred
_GAP_MAX_S = 0.9           # a play that waits for the previous one to end (3 s) is not "0.3 s apart"
_PLAY_SECONDS = 3.0        # how long the fake afplay "plays"
_RETURN_BOUND_S = 2.5      # hook must exit before a single play would end
_TRIGGERING_TYPES = ["permission_prompt", "idle_prompt"]
_OTHER_TYPES = ["auth_success", "elicitation_dialog", ""]


# ── hooks.json readers ──────────────────────────────────────────────────────

def _load_hooks():
    with open(_HOOKS_JSON, encoding="utf-8") as f:
        return json.load(f)["hooks"]


def _groups_running_cue(event_groups):
    return [
        g for g in event_groups
        if any(_HOOK_FILE in h.get("command", "") for h in g.get("hooks", []))
    ]


def _cue_group():
    groups = _groups_running_cue(_load_hooks().get("Notification", []))
    assert len(groups) == 1, (
        f"expected exactly one Notification entry running {_HOOK_FILE}, found {len(groups)}"
    )
    return groups[0]


def _matches(group, notification_type):
    """Claude Code semantics: no matcher (or empty/'*') matches everything."""
    matcher = group.get("matcher")
    if matcher in (None, "", "*"):
        return True
    return re.fullmatch(matcher, notification_type) is not None


def _cue_command():
    hooks = [h for h in _cue_group()["hooks"] if _HOOK_FILE in h.get("command", "")]
    return hooks[0]["command"]


# ── fakes and runner ────────────────────────────────────────────────────────

def make_payload(notification_type, cwd):
    """A Notification payload with the fields Claude Code documents."""
    return {
        "session_id": "owner-cue-test-session",
        "transcript_path": os.path.join(cwd, "transcript.jsonl"),
        "cwd": cwd,
        "permission_mode": "default",
        "hook_event_name": "Notification",
        "message": "Claude needs your permission to use Bash",
        "title": "Claude Code",
        "notification_type": notification_type,
    }


def make_bin(tmp_path, with_afplay, play_seconds=_PLAY_SECONDS):
    """Scratch bin dir: a python3 wrapper and, optionally, a fake afplay.

    Returns (bin_dir, log_path). The log has one JSON line per afplay call.
    """
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "afplay.log"

    py = bin_dir / "python3"
    py.write_text(f'#!/bin/sh\nexec "{sys.executable}" "$@"\n', encoding="utf-8")
    py.chmod(0o755)

    if with_afplay:
        fake = bin_dir / "afplay"
        # Perl, not Python: the fake records its start time, and Python's
        # cold start (~0.15 s on the first call) would skew the 0.3 s gaps.
        fake.write_text(
            f"#!{_PERL}\n"
            "use strict; use Time::HiRes qw(time sleep);\n"
            "my $t = time();\n"
            f"exit 0 if @ARGV && $ARGV[0] eq '{_WARMUP_ARG}';\n"
            "my @a = map { my $s = $_; $s =~ s/\\\\/\\\\\\\\/g; $s =~ s/\"/\\\\\"/g; \"\\\"$s\\\"\" } @ARGV;\n"
            f"open(my $f, '>>', {json.dumps(str(log_path))}) or die;\n"
            "printf $f \"{\\\"t\\\": %.6f, \\\"argv\\\": [%s], \\\"pid\\\": %d}\\n\", $t, join(', ', @a), $$;\n"
            "close $f;\n"
            f"sleep({play_seconds!r});\n",
            encoding="utf-8",
        )
        fake.chmod(0o755)
        # The first exec of a freshly written script is slow on macOS (the
        # OS checks the new file): warm it up once so that cost is not
        # charged to the first play's start time.
        subprocess.run([str(fake), _WARMUP_ARG], check=True, timeout=10)
    return bin_dir, log_path


def read_calls(log_path):
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8").splitlines()
    return [json.loads(line) for line in lines if line.strip()]


def wait_for_calls(log_path, count, deadline_s=5.0):
    end = time.monotonic() + deadline_s
    calls = read_calls(log_path)
    while len(calls) < count and time.monotonic() < end:
        time.sleep(0.05)
        calls = read_calls(log_path)
    return calls


class HookRun:
    def __init__(self, rc, elapsed, stdout, stderr):
        self.rc = rc
        self.elapsed = elapsed
        self.stdout = stdout
        self.stderr = stderr


def run_hook(tmp_path, bin_dir, stdin_text):
    """Run the hooks.json command for the cue, as Claude Code does."""
    command = _cue_command()
    stdin_file = tmp_path / "stdin.json"
    stdin_file.write_text(stdin_text, encoding="utf-8")
    out_file = tmp_path / "stdout.txt"
    err_file = tmp_path / "stderr.txt"
    env = {
        "PATH": f"{bin_dir}{os.pathsep}/bin",
        "HOME": str(tmp_path),
        "CLAUDE_PLUGIN_ROOT": _TOOLKIT_ROOT,
        "CLAUDE_PROJECT_DIR": str(tmp_path),
    }
    with open(stdin_file, "rb") as fin, open(out_file, "wb") as fout, \
            open(err_file, "wb") as ferr:
        start = time.monotonic()
        proc = subprocess.Popen(
            command, shell=True, stdin=fin, stdout=fout, stderr=ferr,
            env=env, cwd=str(tmp_path), start_new_session=True,
        )
        try:
            rc = proc.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(proc.pid, signal.SIGKILL)
            rc = proc.wait()
        elapsed = time.monotonic() - start
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass
    return HookRun(
        rc, elapsed,
        out_file.read_text(encoding="utf-8", errors="replace"),
        err_file.read_text(encoding="utf-8", errors="replace"),
    )


@pytest.fixture
def reap(tmp_path):
    """Kill every fake afplay still 'playing' after the test."""
    logs = []
    yield logs.append
    time.sleep(0.2)
    for log_path in logs:
        for call in read_calls(log_path):
            try:
                os.kill(call["pid"], signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass


# ── Registration: hooks.json ────────────────────────────────────────────────

class TestRegistration:
    def test_should_register_exactly_one_notification_entry_for_the_cue(self):
        # Bug caught: cue not wired at all, or wired twice (double beep x2).
        _cue_group()

    @pytest.mark.parametrize("notification_type", _TRIGGERING_TYPES)
    def test_should_match_when_claude_waits_on_the_owner(self, notification_type):
        # Bug caught: matcher typo -> the cue never sounds when he is needed.
        assert _matches(_cue_group(), notification_type)

    @pytest.mark.parametrize("notification_type", _OTHER_TYPES)
    def test_should_not_match_other_notification_types(self, notification_type):
        # Bug caught: no matcher / '.*' -> beeps on every notification.
        assert not _matches(_cue_group(), notification_type)

    def test_should_not_register_the_cue_under_any_other_event(self):
        # Bug caught: X-126 (Stop) / X-127 (PreToolUse) wired back in ->
        # beeps at the end of every turn, when he is not needed.
        others = {
            event: len(_groups_running_cue(groups))
            for event, groups in _load_hooks().items()
            if event != "Notification"
        }
        assert {e: n for e, n in others.items() if n} == {}

    def test_should_point_the_command_at_a_shipped_file(self):
        # Bug caught: hooks.json names a file that does not exist.
        rel = re.search(r"\$\{CLAUDE_PLUGIN_ROOT\}/(\S+)", _cue_command()).group(1)
        assert rel == f"hooks/{_HOOK_FILE}"
        assert os.path.isfile(os.path.join(_TOOLKIT_ROOT, rel))


# ── Behaviour: the hook run through its hooks.json command ──────────────────

class TestCuePlays:
    @pytest.mark.parametrize("notification_type", _TRIGGERING_TYPES)
    def test_should_play_morse_exactly_three_times_when_notified(
            self, tmp_path, reap, notification_type):
        # Bug caught: wrong sound, wrong count, nothing played.
        bin_dir, log_path = make_bin(tmp_path, with_afplay=True)
        reap(log_path)
        payload = json.dumps(make_payload(notification_type, str(tmp_path)))

        run = run_hook(tmp_path, bin_dir, payload)
        calls = wait_for_calls(log_path, _PLAYS)
        time.sleep(1.0)  # room for a fourth play to show up if there is one
        calls = read_calls(log_path)

        assert run.rc == 0, run.stderr
        assert [c["argv"] for c in calls] == [[_MORSE]] * _PLAYS

    def test_should_space_the_three_plays_0_3_seconds_apart(self, tmp_path, reap):
        # Bug caught: no sleep (one blurred blip), 0.15 s (rejected by ear),
        # or each play waiting for the previous one to end (a slow 3-beat).
        bin_dir, log_path = make_bin(tmp_path, with_afplay=True)
        reap(log_path)
        payload = json.dumps(make_payload("permission_prompt", str(tmp_path)))

        run = run_hook(tmp_path, bin_dir, payload)
        calls = wait_for_calls(log_path, _PLAYS)

        assert run.rc == 0, run.stderr
        assert len(calls) == _PLAYS
        starts = sorted(c["t"] for c in calls)
        gaps = [round(b - a, 3) for a, b in zip(starts, starts[1:])]
        assert all(_GAP_MIN_S <= g <= _GAP_MAX_S for g in gaps), gaps


class TestNeverBlocks:
    @pytest.mark.parametrize("play_seconds", [_PLAY_SECONDS, 60.0],
                             ids=["normal-playback", "stuck-audio-device"])
    def test_should_exit_zero_before_playback_ends(self, tmp_path, reap, play_seconds):
        # Bug caught: hook waits on afplay (`wait`) -> holds the notification
        # for the length of the sound, or up to the timeout if audio hangs.
        bin_dir, log_path = make_bin(tmp_path, with_afplay=True,
                                     play_seconds=play_seconds)
        reap(log_path)
        payload = json.dumps(make_payload("idle_prompt", str(tmp_path)))

        run = run_hook(tmp_path, bin_dir, payload)
        wait_for_calls(log_path, _PLAYS)

        assert run.rc == 0, run.stderr
        assert run.elapsed < _RETURN_BOUND_S, f"hook took {run.elapsed:.2f}s"

    def test_should_do_nothing_and_exit_zero_when_afplay_is_missing(self, tmp_path):
        # Bug caught: FileNotFoundError traceback / non-zero exit on a machine
        # without afplay (Linux, a stripped Mac).
        bin_dir, _ = make_bin(tmp_path, with_afplay=False)
        payload = json.dumps(make_payload("permission_prompt", str(tmp_path)))

        run = run_hook(tmp_path, bin_dir, payload)

        assert run.rc == 0, run.stderr
        assert "Traceback" not in run.stderr
        assert run.elapsed < _RETURN_BOUND_S

    def test_should_exit_zero_and_say_why_when_afplay_cannot_start(self, tmp_path):
        # Bug caught: afplay is on PATH (shutil.which finds it) but exec fails
        # -- broken install, interpreter gone -- and the OSError from Popen
        # escapes as a traceback + exit 1, failing the notification (D-132:
        # "never fails the notification"). Also caught: the failure swallowed
        # in silence, so nobody learns why the cue never sounds.
        bin_dir, _ = make_bin(tmp_path, with_afplay=False)
        broken = bin_dir / "afplay"
        # Executable bit set, so PATH lookup finds it; the interpreter in the
        # shebang does not exist, so exec raises OSError. No sound possible.
        broken.write_text("#!/nonexistent/owner-cue-test-interpreter\n",
                          encoding="utf-8")
        broken.chmod(0o755)
        payload = json.dumps(make_payload("permission_prompt", str(tmp_path)))

        run = run_hook(tmp_path, bin_dir, payload)

        assert run.rc == 0, run.stderr
        assert "Traceback" not in run.stderr, run.stderr
        assert run.elapsed < _RETURN_BOUND_S, f"hook took {run.elapsed:.2f}s"
        assert "afplay" in run.stderr, f"stderr does not say why: {run.stderr!r}"

    @pytest.mark.parametrize("stdin_text", ["", "{not json", "[]"],
                             ids=["empty", "garbage", "not-an-object"])
    def test_should_exit_zero_on_unreadable_stdin(self, tmp_path, reap, stdin_text):
        # Bug caught: json.loads crash -> the notification shows a hook error.
        bin_dir, log_path = make_bin(tmp_path, with_afplay=True)
        reap(log_path)

        run = run_hook(tmp_path, bin_dir, stdin_text)

        assert run.rc == 0, run.stderr
        assert "Traceback" not in run.stderr
        assert run.elapsed < _RETURN_BOUND_S
