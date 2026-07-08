"""
Hardening pass (Dante, AFTER Ultron implemented) for the Windows/macOS/Linux
compatibility fix — see docs/plan/fix-windows-crossplatform.md.

The base contract (test_crossplatform_symlink_guard.py) is GREEN: 14 passed,
4 skipped (POSIX-real-symlink tests skip on this Windows dev box by design).
This file does NOT touch that file — it only adds coverage for branches and
error paths of the real, now-implemented code that the acceptance-granularity
contract pass didn't need to reach:

  - lib/git_helpers.py:_open_no_follow_symlink_windows()
  - lib/_symlink_safe_open.py:_open_no_follow_symlink_windows()  (twin)
  - lib/git_helpers.py:run_git()  (encoding="utf-8" addition)

Reuses TWIN_FUNCS and _FakeStat from the base contract file rather than
duplicating them (both are plain module-level names, importable the same
way the base file already imports `from conftest import LIB_DIR`).
"""

import errno
import json
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import LIB_DIR, git_cmd

import git_helpers
import _symlink_safe_open

from test_crossplatform_symlink_guard import TWIN_FUNCS, _FakeStat


# ══════════════════════════════════════════════════════════════════════════
# Group 1 — brand-new path (O_CREAT), no prior lstat identity to compare
# (F5 residual, documented but never directly exercised by the base
# contract's mocked scenarios, which always pre-create the target file)
# ══════════════════════════════════════════════════════════════════════════


class TestNewFileOCreatSkipsIdentityCheck:
    """When the target path does not exist yet, `_open_no_follow_symlink_windows`
    must skip both os.lstat() (pre) and os.fstat()-comparison (post) entirely
    — there is nothing to compare a brand-new file's identity against. This
    pins the exact F5 residual documented in git_helpers.py's docstring."""

    @pytest.mark.parametrize("mode", ["w", "a"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_new_file_skips_lstat_and_fstat_and_opens(
        self, monkeypatch, tmp_path, target_open, mode
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / f"new-file-{mode}.txt"
        assert not path.exists()

        # os.path.islink() itself calls os.lstat() internally on Windows
        # (confirmed empirically) — stub it directly so the spies below only
        # ever see _open_no_follow_symlink_windows()'s OWN explicit
        # lstat/fstat calls, not islink()'s unrelated implementation detail.
        monkeypatch.setattr(os.path, "islink", lambda p: False)

        real_lstat = os.lstat
        lstat_calls = []

        def spy_lstat(p):
            lstat_calls.append(p)
            return real_lstat(p)

        real_fstat = os.fstat
        fstat_calls = []

        def spy_fstat(fd):
            fstat_calls.append(fd)
            return real_fstat(fd)

        monkeypatch.setattr(os, "lstat", spy_lstat)
        monkeypatch.setattr(os, "fstat", spy_fstat)

        with target_open(str(path), mode) as f:
            f.write("hello")

        assert lstat_calls == [], (
            "brand-new path must never call os.lstat() — there is no prior "
            "identity to capture (F5 residual)"
        )
        assert fstat_calls == [], (
            "with no prior identity captured, no post-open os.fstat() "
            "comparison should run either"
        )
        assert path.exists()


# ══════════════════════════════════════════════════════════════════════════
# Group 2 — existing file, identity matches (the "everything is fine" case)
# The base contract only ever exercises the MISMATCH branch (mode="w") and
# the real-success branch incidentally for mode="r" via
# TestExceptionInvariantAcrossPlatforms. Modes w/a were never proven to
# succeed when identity genuinely matches.
# ══════════════════════════════════════════════════════════════════════════


class TestExistingFileIdentityMatchSucceeds:
    @pytest.mark.parametrize("mode", ["r", "w", "a"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_existing_file_real_identity_match_opens_without_raising(
        self, monkeypatch, tmp_path, target_open, mode
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / f"existing-match-{mode}.txt"
        path.write_text("original\n", encoding='utf-8')

        real_lstat = os.lstat
        lstat_calls = []

        def spy_lstat(p):
            lstat_calls.append(p)
            return real_lstat(p)

        real_fstat = os.fstat
        fstat_calls = []

        def spy_fstat(fd):
            fstat_calls.append(fd)
            return real_fstat(fd)

        monkeypatch.setattr(os, "lstat", spy_lstat)
        monkeypatch.setattr(os, "fstat", spy_fstat)

        f = target_open(str(path), mode)
        try:
            if mode == "r":
                assert f.read() == "original\n"
            else:
                f.write("more\n")
        finally:
            f.close()

        assert lstat_calls, (
            "an existing path must capture prior identity via os.lstat() "
            "before opening"
        )
        assert fstat_calls, (
            "an existing path must verify post-open identity via os.fstat()"
        )


class TestAppendModePreservesExistingContent:
    """Functional regression for the O_APPEND branch specifically — proves
    mode="a" through the Windows guard appends rather than truncating,
    distinguishing it from mode="w" (which the base contract already
    covers via TestEncodingRoundTrip, always on a fresh file)."""

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_append_mode_through_windows_guard_does_not_truncate(
        self, monkeypatch, tmp_path, target_open
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "append-target.txt"
        path.write_text("first line\n", encoding='utf-8')

        with target_open(str(path), "a") as f:
            f.write("second line\n")

        assert path.read_text(encoding='utf-8') == "first line\nsecond line\n"


# ══════════════════════════════════════════════════════════════════════════
# Group 3 — TOCTOU mismatch parametrized across ALL open modes, not just "w"
# ══════════════════════════════════════════════════════════════════════════


class TestToctouMismatchAllModes:
    @pytest.mark.parametrize("mode", ["r", "w", "a"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_lstat_fstat_mismatch_raises_and_closes_fd(
        self, monkeypatch, tmp_path, target_open, mode
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / f"toctou-{mode}.txt"
        path.write_text("original", encoding='utf-8')

        monkeypatch.setattr(os.path, "islink", lambda p: False)
        monkeypatch.setattr(os, "lstat", lambda p: _FakeStat(st_dev=1, st_ino=100))
        monkeypatch.setattr(os, "fstat", lambda fd: _FakeStat(st_dev=1, st_ino=999))

        opened_fds = []
        real_open = os.open

        def spy_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened_fds.append(fd)
            return fd

        closed_fds = []
        real_close = os.close

        def spy_close(fd):
            closed_fds.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "open", spy_open)
        monkeypatch.setattr(os, "close", spy_close)

        with pytest.raises(OSError):
            target_open(str(path), mode)

        assert opened_fds, "a real fd must be opened before the identity check can run"
        assert closed_fds == opened_fds, (
            f"mode={mode!r}: every fd opened during a rejected TOCTOU race "
            f"must be closed before raising — opened={opened_fds}, "
            f"closed={closed_fds}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Group 4 — error propagation: os.lstat() / os.open() raising mid-guard
# ══════════════════════════════════════════════════════════════════════════


class TestLstatRaisesMidGuard:
    """Simulates a file deleted between os.path.exists() and os.lstat()
    (real TOCTOU race, distinct from the identity-mismatch race already
    covered). Nothing in _open_no_follow_symlink_windows wraps this call in
    try/except, so the exception should propagate as-is (FileNotFoundError,
    already an OSError subclass) and os.open() must never be reached."""

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_lstat_raises_propagates_before_open_is_called(
        self, monkeypatch, tmp_path, target_open
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "lstat-raises.txt"
        path.write_text("x", encoding='utf-8')  # must exist so os.path.exists() takes the lstat branch

        monkeypatch.setattr(os.path, "islink", lambda p: False)

        def raising_lstat(p):
            raise FileNotFoundError(2, "No such file or directory (raced deletion)")

        monkeypatch.setattr(os, "lstat", raising_lstat)

        open_calls = []
        real_open = os.open

        def spy_open(*args, **kwargs):
            open_calls.append((args, kwargs))
            return real_open(*args, **kwargs)

        monkeypatch.setattr(os, "open", spy_open)

        with pytest.raises(OSError):
            target_open(str(path), "w")

        assert not open_calls, (
            "os.open() must never be reached once the pre-open os.lstat() "
            "call itself raises"
        )


class TestOsOpenRaisesMidGuard:
    """Simulates os.open() itself failing (e.g. permission denied). Nothing
    wraps this call either, so the OSError raised by os.open() must reach
    the caller unmodified — not swallowed, not converted, not masked."""

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_os_open_raises_propagates_cleanly_as_oserror(
        self, monkeypatch, tmp_path, target_open
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "open-raises.txt"  # brand-new path -> no lstat branch
        monkeypatch.setattr(os.path, "islink", lambda p: False)

        def raising_open(*args, **kwargs):
            raise PermissionError(13, "Permission denied (simulated)")

        monkeypatch.setattr(os, "open", raising_open)

        with pytest.raises(OSError) as exc_info:
            target_open(str(path), "w")

        assert exc_info.value.errno == 13


# ══════════════════════════════════════════════════════════════════════════
# Group 5 — REGRESSION FIXED: os.fstat() raising no longer leaks the fd
#
# Was a DISCOVERED GAP (xfail-marked report, not fixed by Dante — see
# dante.md, Absolute Prohibition #4). Ultron closed it by wrapping the
# identity-comparison AND the ftruncate() call in a single
# `try: ... except BaseException: os.close(fd); raise` block, so ANY
# post-open failure (not just the (dev, ino) mismatch branch) now closes
# the fd before propagating. The xfail(strict=True) marker is removed —
# this is now a normal regression pin, not a report of a known gap.
# ══════════════════════════════════════════════════════════════════════════


class TestFstatFailureFdLeak:
    """git_helpers.py:200-218 / _symlink_safe_open.py:80-98 (identical in
    both twins): `os.close(fd)` used to be reachable only from inside the
    `if (dev, ino) mismatch` branch of the TOCTOU check, so a transient
    os.fstat(fd) failure (e.g. the file descriptor os.open() just handed
    back becoming momentarily unstattable) would leak the fd — the
    exception propagated without ever reaching `os.close(fd)`.

    Fixed: both twins now wrap `post_identity = os.fstat(fd)` (and the
    subsequent `os.ftruncate(fd, 0)`) in `try: ... except BaseException:
    os.close(fd); raise`. This test pins that the fd IS closed even when
    os.fstat() raises — regression coverage for the fix, not a report of a
    gap."""

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_fstat_raises_still_closes_the_fd(self, monkeypatch, tmp_path, target_open):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "fstat-raises.txt"
        path.write_text("original", encoding='utf-8')

        monkeypatch.setattr(os.path, "islink", lambda p: False)
        monkeypatch.setattr(os, "lstat", lambda p: _FakeStat(st_dev=1, st_ino=100))

        def raising_fstat(fd):
            raise OSError(5, "simulated fstat failure")

        monkeypatch.setattr(os, "fstat", raising_fstat)

        opened_fds = []
        real_open = os.open

        def spy_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened_fds.append(fd)
            return fd

        closed_fds = []
        real_close = os.close

        def spy_close(fd):
            closed_fds.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "open", spy_open)
        monkeypatch.setattr(os, "close", spy_close)

        with pytest.raises(OSError):
            target_open(str(path), "w")

        assert opened_fds, "a real fd must have been opened before fstat could be attempted"
        assert closed_fds == opened_fds, (
            f"fd leak: os.fstat() raised but the fd was never closed before "
            f"the exception propagated — opened={opened_fds}, "
            f"closed={closed_fds}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Group 5b — REGRESSION FIXED: Hallazgo 1 (Argus SEC-MED-NEW-03) — deferred
# truncate. mode="w" on an EXISTING file used to call os.ftruncate(fd, 0)
# unconditionally at open() time, BEFORE the lstat/fstat identity check
# could reject a TOCTOU race — so a rejected race still destroyed the
# victim's content, even though the caller correctly saw an OSError and no
# fd. Fixed: os.ftruncate(fd, 0) now runs only after the identity check
# passes, inside the same try/except BaseException block covered above.
# ══════════════════════════════════════════════════════════════════════════


class TestDeferredTruncateOnIdentityMismatch:
    """git_helpers.py:200-218 / _symlink_safe_open.py:80-98: on a TOCTOU
    identity mismatch (mode="w", existing file), the destructive
    os.ftruncate(fd, 0) must NEVER be reached — the mismatch is detected
    and raised before truncation is attempted. Proven two ways: (1) a spy
    on os.ftruncate asserting zero calls, and (2) the file's real on-disk
    content is untouched, in case a future change calls ftruncate via a
    path this spy doesn't intercept."""

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_mismatch_raises_before_ftruncate_and_content_survives(
        self, monkeypatch, tmp_path, target_open
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "deferred-truncate-target.txt"
        original_content = "SENSITIVE ORIGINAL CONTENT — must not be truncated"
        path.write_text(original_content, encoding='utf-8')

        monkeypatch.setattr(os.path, "islink", lambda p: False)
        monkeypatch.setattr(os, "lstat", lambda p: _FakeStat(st_dev=1, st_ino=100))
        monkeypatch.setattr(os, "fstat", lambda fd: _FakeStat(st_dev=1, st_ino=999))

        real_ftruncate = os.ftruncate
        ftruncate_calls = []

        def spy_ftruncate(fd, length):
            ftruncate_calls.append((fd, length))
            return real_ftruncate(fd, length)

        monkeypatch.setattr(os, "ftruncate", spy_ftruncate)

        opened_fds = []
        real_open = os.open

        def spy_open(*args, **kwargs):
            fd = real_open(*args, **kwargs)
            opened_fds.append(fd)
            return fd

        closed_fds = []
        real_close = os.close

        def spy_close(fd):
            closed_fds.append(fd)
            real_close(fd)

        monkeypatch.setattr(os, "open", spy_open)
        monkeypatch.setattr(os, "close", spy_close)

        with pytest.raises(OSError):
            target_open(str(path), "w")

        assert ftruncate_calls == [], (
            "os.ftruncate() must never be called when the TOCTOU identity "
            f"check rejects the open — calls recorded: {ftruncate_calls}"
        )
        assert opened_fds, "a real fd must be opened before the identity check can run"
        assert closed_fds == opened_fds, (
            f"the fd opened during a rejected mismatch must be closed — "
            f"opened={opened_fds}, closed={closed_fds}"
        )
        assert path.read_text(encoding='utf-8') == original_content, (
            "the target file's content must survive a rejected TOCTOU race "
            "unchanged — a destructive truncate-before-check would corrupt it"
        )


# ══════════════════════════════════════════════════════════════════════════
# Group 6 — twin parity for the new scenarios above (both twins must agree)
# ══════════════════════════════════════════════════════════════════════════


class TestTwinParityHardening:
    def test_new_file_o_creat_same_outcome_on_both_twins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        outcomes = {}
        for name, fn in TWIN_FUNCS.items():
            path = tmp_path / f"parity-new-{name.replace('.', '_')}.txt"
            try:
                f = fn(str(path), "w")
                f.write("x")
                f.close()
            except Exception as e:
                outcomes[name] = type(e)
            else:
                outcomes[name] = None

        assert set(outcomes.values()) == {None}, (
            f"the two twins diverged opening a brand-new file: {outcomes}"
        )

    def test_lstat_raises_same_exception_type_on_both_twins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setattr(os.path, "islink", lambda p: False)

        def raising_lstat(p):
            raise FileNotFoundError(2, "raced deletion")

        monkeypatch.setattr(os, "lstat", raising_lstat)

        outcomes = {}
        for name, fn in TWIN_FUNCS.items():
            path = tmp_path / f"parity-lstat-{name.replace('.', '_')}.txt"
            path.write_text("x", encoding='utf-8')
            try:
                fn(str(path), "w")
            except Exception as e:
                outcomes[name] = type(e)
            else:
                outcomes[name] = None

        distinct = set(outcomes.values())
        assert len(distinct) == 1, f"the two twins diverged: {outcomes}"
        assert distinct == {FileNotFoundError}, outcomes


# ══════════════════════════════════════════════════════════════════════════
# Group 7 — run_git()'s new encoding="utf-8" argument
# ══════════════════════════════════════════════════════════════════════════


class TestRunGitEncodingUtf8:
    def test_run_git_passes_encoding_utf8_and_text_true_to_subprocess(
        self, monkeypatch
    ):
        """Mock-verification: confirm the NEW encoding="utf-8" kwarg is
        actually threaded through to the underlying subprocess call, not
        just documented.

        SEC-MED-001 (Argus, issue #49 repair round) switched run_git()'s
        internals from subprocess.run(...) to subprocess.Popen(...) +
        proc.communicate(...), so a process-group SIGKILL (os.killpg) can
        target a hung descendant (ssh/askpass/credential-helper) on timeout
        — subprocess.run's own TimeoutExpired handling only ever kills the
        direct child, leaving orphans that can still pop an interactive
        dialog out of context. This test now mocks subprocess.Popen instead
        of subprocess.run — same behavioral assertion (encoding/text kwargs
        threaded through, return contract preserved), updated for the new
        (still fully documented) internal call shape.
        """
        calls = []

        class _FakePopen:
            def __init__(self, cmd, **kwargs):
                calls.append(kwargs)
                self.returncode = 0

            def communicate(self, timeout=None):
                return "ok\n", ""

        monkeypatch.setattr(subprocess, "Popen", _FakePopen)

        code, out = git_helpers.run_git(["status"])

        assert len(calls) == 1
        assert calls[0].get("encoding") == "utf-8"
        assert calls[0].get("text") is True
        assert code == 0
        assert out == "ok"

    def test_run_git_unicode_decode_error_returns_1_empty_not_raising(
        self, monkeypatch
    ):
        """Regression pin for the documented, deliberately-accepted decision
        in run_git()'s except clause: a ValueError subclass (including
        UnicodeDecodeError, should git ever emit non-UTF-8 bytes despite the
        explicit encoding="utf-8") collapses to the same (1, "") "git
        failed" contract every caller already handles — it must not raise
        and crash the caller. Mocks subprocess.Popen (see this class's first
        test for why — SEC-MED-001, issue #49 repair round).
        """

        class _FakePopen:
            def __init__(self, cmd, **kwargs):
                self.returncode = None

            def communicate(self, timeout=None):
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        monkeypatch.setattr(subprocess, "Popen", _FakePopen)

        code, out = git_helpers.run_git(["log"])

        assert code == 1
        assert out == ""

    def test_run_git_unicode_decode_error_emits_stderr_diagnostic(
        self, monkeypatch, capsys
    ):
        """Companion to test_run_git_unicode_decode_error_returns_1_empty_not_raising:
        that test only pins the (1, "") return contract. This test closes the
        remaining gap — the dedicated `except UnicodeDecodeError` branch in
        run_git() is also supposed to leave a diagnostic breadcrumb on stderr
        (`[git_helpers] git '<subcommand>' output was not valid UTF-8 ...`)
        instead of failing silently like the generic except below it. Mocks
        subprocess.Popen (see this class's first test for why — SEC-MED-001,
        issue #49 repair round).
        """

        class _FakePopen:
            def __init__(self, cmd, **kwargs):
                self.returncode = None

            def communicate(self, timeout=None):
                raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")

        monkeypatch.setattr(subprocess, "Popen", _FakePopen)

        code, out = git_helpers.run_git(["log"])

        assert code == 1
        assert out == ""

        captured = capsys.readouterr()
        assert captured.err.startswith("[git_helpers]")
        assert "not valid UTF-8" in captured.err
        assert "'log'" in captured.err

    def test_run_git_round_trips_utf8_accents_and_emoji_through_real_git(
        self, tmp_repo
    ):
        """Real round-trip (unmassk-standards §34): the expected value is
        the SAME `subject` variable used to create the real commit via a
        real `git commit` subprocess (the actual producer) — never a second,
        independently hand-typed literal. Reread through run_git() (the
        consumer) via a real `git log`, not a mock.

        Adversarial (Moriarty T1 finding): the naive in-process version of
        this test passed even with run_git()'s explicit `encoding="utf-8"`
        kwarg deleted, because this dev machine (and most CI) runs with the
        ambient PYTHONUTF8=1, which silently repairs any subprocess.run()
        call site that forgot an explicit `encoding=` by forcing UTF-8 mode
        process-wide — so the test was proving "this machine's env is
        UTF-8", not "run_git() is UTF-8-safe". Fixed the same way
        TestEncodingIndependentOfPythonUtf8Env (test_crossplatform_symlink_guard.py)
        fixed the analogous gap for open_no_follow_symlink(): the round-trip
        itself runs in a CHILD process with PYTHONUTF8 forced to "0" (and
        PYTHONLEGACYWINDOWSFSENCODING unset), so if run_git() ever loses its
        explicit encoding="utf-8", Python's implicit text-decoding falls back
        to the locale's ANSI codepage (cp1252 on this kind of Windows
        install) and the reread subject comes back mojibake, failing the
        final assert — independent of whatever PYTHONUTF8 the outer pytest
        process happens to run under.

        The child communicates back via `json.dumps` with the default
        `ensure_ascii=True` — this keeps the parent<->child pipe pure ASCII
        (all non-ASCII chars \\uXXXX-escaped) so a mangled *console* codepage
        in the harness itself can never masquerade as a mangled *file*
        round-trip, which is the only thing this test means to measure. The
        accented/emoji `subject` itself is never embedded in the child's `-c`
        argv (only the ASCII tmp_repo path and LIB_DIR are) — it stays in the
        parent process and is only compared against the child's decoded-back
        JSON output.
        """
        subject = (
            "🔧 chore(hardening): commit con acentos y emoji — "
            "corazón, señal, año 👑"
        )
        rc, _, _ = git_cmd(["commit", "--allow-empty", "-m", subject], tmp_repo)
        assert rc == 0

        code_snippet = textwrap.dedent(f"""
            import sys, json
            sys.path.insert(0, {repr(str(LIB_DIR))})
            import git_helpers

            code, output = git_helpers.run_git(
                ["log", "-1", "--format=%s"], cwd={repr(tmp_repo)}
            )
            print(json.dumps({{"code": code, "output": output}}))
        """)

        env = dict(os.environ)
        env.pop("PYTHONLEGACYWINDOWSFSENCODING", None)
        env["PYTHONUTF8"] = "0"

        result = subprocess.run(
            [sys.executable, "-c", code_snippet],
            capture_output=True, text=True, encoding='utf-8', timeout=30, env=env,
        )

        assert result.returncode == 0, (
            f"subprocess crashed with PYTHONUTF8=0:\n"
            f"stdout={result.stdout}\nstderr={result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["code"] == 0
        assert data["output"] == subject
