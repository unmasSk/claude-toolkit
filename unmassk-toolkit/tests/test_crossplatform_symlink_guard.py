"""
Test-first contract (Dante, before Ultron) for the Windows/macOS/Linux
compatibility fix — see docs/plan/fix-windows-crossplatform.md, Task 1.

Decisions already made (git-memory, not up for debate here):
  - 013b064 decision(plugin/portability): cross-platform is a hard requirement.
  - 75fdb2f decision(plugin/security): hybrid "option C" anti-symlink guard —
    POSIX keeps os.O_NOFOLLOW; Windows gets an os.path.islink() pre-open
    check PLUS an os.lstat()/os.fstat() identity comparison (TOCTOU guard);
    any rejection raises OSError, closes the fd, never returns it.

Code under test (two twins that MUST behave identically — see
_symlink_safe_open.py's own docstring: "Must be kept behaviorally identical
to git_helpers.open_no_follow_symlink()"):
  - lib/git_helpers.py:open_no_follow_symlink()
  - lib/_symlink_safe_open.py:open_no_follow_symlink_fallback()

Current bug (House F1, confirmed live in this dev environment — a real
win32 box): both twins reference `os.O_NOFOLLOW` UNCONDITIONALLY. That
attribute does not exist on Windows, so EVERY call (symlink or not) raises
`AttributeError: module 'os' has no attribute 'O_NOFOLLOW'`. AttributeError
is NOT a subclass of OSError, so it escapes every `except OSError` at every
call site as an unhandled crash. This file pins that invariant plus the
Windows-guard contract that replaces it.

Build mode: test-first (contract pass). This is acceptance-granularity —
the 7 behaviors that define "done" per the plan — not the exhaustive
branch/line suite. The EXHAUSTION PROTOCOL hardening pass runs AFTER
Ultron implements (Flow Verify step), against the real code.

NO production code is touched by this file. Only tests.
"""

import errno
import json
import os
import subprocess
import sys
import textwrap

import pytest

from conftest import LIB_DIR

import git_helpers
import _symlink_safe_open

TWIN_FUNCS = {
    "git_helpers.open_no_follow_symlink": git_helpers.open_no_follow_symlink,
    "_symlink_safe_open.open_no_follow_symlink_fallback": (
        _symlink_safe_open.open_no_follow_symlink_fallback
    ),
}


class _FakeStat:
    """Minimal duck-typed stand-in for os.stat_result — the (future)
    Windows TOCTOU guard only needs to compare (st_dev, st_ino), so a real
    stat_result is unnecessary ceremony."""

    def __init__(self, st_dev, st_ino):
        self.st_dev = st_dev
        self.st_ino = st_ino


# `real_symlink_capable` fixture lives in conftest.py (shared with
# test_boot_freshness_hardening.py) — auto-discovered by pytest, no import
# needed. See conftest.py for the docstring/rationale.


# ══════════════════════════════════════════════════════════════════════════
# Item 1 — POSIX guard unchanged (GUARD: passes now, must keep passing)
# ══════════════════════════════════════════════════════════════════════════


class TestPosixGuardUnchanged:
    """O_NOFOLLOW is real on POSIX today and Task 2 must not touch that
    branch. These are GUARD tests: expected GREEN now (on a POSIX host —
    skipped here since this dev box cannot create real symlinks, see
    `real_symlink_capable`) and GREEN after Task 2.
    """

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_existing_symlink_at_target_raises_oserror_eloop(
        self, tmp_path, target_open, real_symlink_capable
    ):
        """GUARD — real symlink at the final path component, real kernel
        O_NOFOLLOW enforcement. Not mockable (see fixture docstring)."""
        victim = tmp_path / "victim-posix.txt"
        victim.write_text("SENSITIVE ORIGINAL CONTENT", encoding='utf-8')
        link_path = tmp_path / "posix-guard-link.txt"
        os.symlink(str(victim), str(link_path))

        with pytest.raises(OSError) as exc_info:
            target_open(str(link_path), "w")

        assert exc_info.value.errno == errno.ELOOP, (
            f"expected ELOOP (symlink refused), got errno={exc_info.value.errno}"
        )
        assert victim.read_text(encoding='utf-8') == "SENSITIVE ORIGINAL CONTENT"

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_normal_file_opens_and_round_trips_on_posix(
        self, tmp_path, target_open, real_symlink_capable
    ):
        """GUARD — an ordinary (non-symlink) file must open, write, and
        read back correctly; untouched by the O_NOFOLLOW guard."""
        path = tmp_path / "posix-normal-file.txt"
        payload = "contenido normal sin symlink\n"

        with target_open(str(path), "w") as f:
            f.write(payload)
        with target_open(str(path), "r") as f:
            reread = f.read()

        assert reread == payload


# ══════════════════════════════════════════════════════════════════════════
# Item 2 — Windows guard: os.path.islink() pre-open check (RED now)
# ══════════════════════════════════════════════════════════════════════════


class TestWindowsIslinkGuardMocked:
    """Windows has no O_NOFOLLOW; the fix's first line of defense is an
    explicit `os.path.islink()` check BEFORE opening. Mocked so this runs
    on any host OS, per the plan's requirement (no real symlink needed;
    this dev box has no privilege to create one anyway).

    RED now: neither twin calls os.path.islink() anywhere — the mock is
    inert — so the call falls straight through to the unconditional
    `os.O_NOFOLLOW` reference and raises AttributeError (F1), which
    `pytest.raises(OSError)` below does NOT catch, surfacing as an
    unhandled-AttributeError test failure. That IS the correct RED signal.

    GREEN after Task 2: islink()==True must raise OSError before os.open()
    is ever called (spied via `open_calls`).
    """

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    @pytest.mark.parametrize("mode", ["r", "w"])
    def test_islink_true_raises_oserror_without_opening_file(
        self, monkeypatch, tmp_path, target_open, mode
    ):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "windows-guard-target.txt"
        path.write_text("original content", encoding='utf-8')
        monkeypatch.setattr(os.path, "islink", lambda p: True)

        open_calls = []
        real_open = os.open

        def spy_open(*args, **kwargs):
            open_calls.append((args, kwargs))
            return real_open(*args, **kwargs)

        monkeypatch.setattr(os, "open", spy_open)

        with pytest.raises(OSError):
            target_open(str(path), mode)

        assert not open_calls, (
            "os.open() must never be called once os.path.islink() reports "
            "True — the guard must fail BEFORE opening, not open-then-check"
        )
        assert path.read_text(encoding='utf-8') == "original content"


# ══════════════════════════════════════════════════════════════════════════
# Item 4 — invariant: OSError (or subclass) only, never AttributeError,
# never a silent falsy return (RED now, on this Windows box)
# ══════════════════════════════════════════════════════════════════════════


class TestExceptionInvariantAcrossPlatforms:
    """The heart of F1: this test makes NO mocking assumption about
    platform — it runs the REAL, current, unmodified code path for
    whatever OS this pytest process is actually on.

    RED now on real Windows (confirmed in this dev environment): raises
    AttributeError on an ORDINARY file, no symlink involved at all.
    Already GREEN on POSIX today (O_NOFOLLOW exists there) — this is a
    GUARD on POSIX and a RED-to-GREEN contract on Windows, both enforced
    by the same assertion.
    """

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_never_raises_attributeerror_or_returns_falsy_on_normal_file(
        self, tmp_path, target_open
    ):
        path = tmp_path / "plain-file-no-symlink.txt"
        path.write_text("hello", encoding='utf-8')

        try:
            f = target_open(str(path), "r")
        except AttributeError as e:
            pytest.fail(
                "open_no_follow_symlink raised AttributeError on a NORMAL "
                "file (no symlink involved) instead of either opening it "
                "successfully or raising OSError — this is the exact F1 "
                f"crash (os.O_NOFOLLOW missing on win32): {e!r}"
            )
        try:
            assert f is not None and f is not False, (
                "must never silently return None/False on success — a "
                "caller checking `if not fh:` would treat this as an "
                "absent file and mask the real error"
            )
            assert f.read() == "hello"
        finally:
            f.close()


# ══════════════════════════════════════════════════════════════════════════
# Item 5 — twin parity: same scenario, same result on BOTH implementations
# ══════════════════════════════════════════════════════════════════════════


class TestTwinParity:
    """git_helpers.open_no_follow_symlink and
    _symlink_safe_open.open_no_follow_symlink_fallback must raise the same
    exception TYPE for the same input — _symlink_safe_open.py's own
    docstring requires "kept behaviorally identical". This guards against
    Ultron fixing one twin and forgetting the other in Task 2.

    RED now: both twins raise AttributeError today (they ARE identical —
    parity itself holds), so the type-equality-to-AttributeError succeeds
    but the type-equality-to-OSError assertion fails. That is the correct
    RED signal: parity is not the missing piece, correctness is.
    """

    def test_islink_guard_scenario_same_outcome_on_both_twins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "parity-islink.txt"
        path.write_text("x", encoding='utf-8')
        monkeypatch.setattr(os.path, "islink", lambda p: True)

        results = {}
        for name, fn in TWIN_FUNCS.items():
            try:
                fn(str(path), "w")
            except Exception as e:
                results[name] = type(e)
            else:
                results[name] = None

        distinct_outcomes = set(results.values())
        assert len(distinct_outcomes) == 1, (
            f"the two twins diverged for the SAME islink-guard scenario: "
            f"{results} — they must be byte-identical in behavior"
        )
        assert distinct_outcomes == {OSError}, (
            f"both twins must raise OSError for a Windows islink-guard hit, "
            f"got {results}"
        )

    def test_toctou_scenario_same_outcome_on_both_twins(self, monkeypatch, tmp_path):
        monkeypatch.setattr(sys, "platform", "win32")
        path = tmp_path / "parity-toctou.txt"
        path.write_text("x", encoding='utf-8')
        monkeypatch.setattr(os.path, "islink", lambda p: False)
        monkeypatch.setattr(os, "lstat", lambda p: _FakeStat(st_dev=1, st_ino=100))
        monkeypatch.setattr(os, "fstat", lambda fd: _FakeStat(st_dev=1, st_ino=999))

        results = {}
        for name, fn in TWIN_FUNCS.items():
            try:
                fn(str(path), "w")
            except Exception as e:
                results[name] = type(e)
            else:
                results[name] = None

        distinct_outcomes = set(results.values())
        assert len(distinct_outcomes) == 1, (
            f"the two twins diverged for the SAME TOCTOU scenario: {results}"
        )
        assert distinct_outcomes == {OSError}, (
            f"both twins must raise OSError for a TOCTOU identity mismatch, "
            f"got {results}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Item 6 — encoding round-trip: Spanish accents + commit emojis, byte-for-byte
# ══════════════════════════════════════════════════════════════════════════


class TestEncodingRoundTrip:
    """SEC-MED-NEW-02's read guard and SEC-CRIT-001's write guard must
    preserve UTF-8 content exactly through the write -> reread seam, using
    this project's own real alphabet (Spanish accents/ñ per CLAUDE.md's
    Communication rule + the commit-emoji vocabulary seen in `git log`:
    🔧 chore, 📝 docs, ✨ feat, 📌 memo, 👑 crown).

    The expected value is never a hand-retyped duplicate (unmassk-standards
    §34) — `payload` is written once and the assertion compares the reread
    content against that SAME variable, not a second independently-typed
    literal.

    RED now on Windows only: blocked by the F1 AttributeError before the
    encoding logic is ever reached. Already GREEN on POSIX today, since
    both twins already default encoding="utf-8" explicitly. GREEN
    everywhere after Task 2.
    """

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_write_then_read_preserves_accents_and_commit_emojis_byte_for_byte(
        self, tmp_path, target_open
    ):
        path = tmp_path / "roundtrip-encoding.txt"
        payload = (
            "🔧 chore(unmassk-toolkit): versión de mantenimiento\n"
            "📝 docs(plugin): documentación del consolidador — corazón, señal, año\n"
            "✨ feat(plugin/memory): disparador automático de la Corona 👑\n"
            "📌 memo(tests): atención al romperse por símbolo nuevo\n"
        )

        with target_open(str(path), "w") as f:
            f.write(payload)

        with target_open(str(path), "r") as f:
            reread = f.read()

        assert reread == payload


# ══════════════════════════════════════════════════════════════════════════
# Item 8 — issue #54, T3: errors= parameter, surrogate escape contract
# ══════════════════════════════════════════════════════════════════════════
#
# Regression test for issue #54: both twins gained an `errors: str = "strict"`
# parameter (default unchanged — no behavior change for any existing call
# site, none of which pass it). Before this fix, a write-mode caller whose
# text contains a lone surrogate (e.g. "\udc80", half of a broken Unicode
# pair — this codebase's git-log decoding can produce one from a malformed
# source) raised `UnicodeEncodeError` from inside `os.fdopen(...).write()`
# — a ValueError subclass, NOT an OSError — violating the "only OSError
# escapes this function" contract every existing caller relies on. Passing
# `errors="backslashreplace"` must make the write succeed instead.
#
# Per unmassk-standards §34: the expected transformed text is never
# hand-typed. It is derived by running Python's own (independent, not
# owned by this codebase) `str.encode(..., errors="backslashreplace")`
# codec on the same payload variable inside the test itself — the exact
# codec `os.fdopen(..., errors="backslashreplace")` delegates to
# internally, so this is a real, live, independently-computed contract,
# not a fixture.


class TestErrorsParameterSurrogateEscape:
    """Item 8 — issue #54, T3."""

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_backslashreplace_writes_lone_surrogate_without_raising_and_rereads_clean(
        self, tmp_path, target_open
    ):
        path = tmp_path / "surrogate-backslashreplace.txt"
        payload = "bad-\udc80-surrogate"
        # Derived from Python's own codec, not hand-typed — the same
        # transformation os.fdopen(errors="backslashreplace") performs.
        expected = payload.encode("utf-8", errors="backslashreplace").decode("utf-8")

        with target_open(str(path), "w", errors="backslashreplace") as f:
            f.write(payload)  # must NOT raise UnicodeEncodeError

        with target_open(str(path), "r") as f:
            reread = f.read()  # plain strict-UTF-8 read — must not raise either

        assert reread == expected, (
            f"backslashreplace-escaped surrogate must re-read cleanly through "
            f"a normal strict-UTF-8 read: expected {expected!r}, got {reread!r}"
        )

    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_default_errors_still_strict_raises_unicodeencodeerror_on_surrogate(
        self, tmp_path, target_open
    ):
        """Guard: the new `errors=` parameter must default to "strict" — no
        behavior change for the (many) existing call sites that never pass
        it. A lone surrogate must still raise UnicodeEncodeError exactly as
        it did before issue #54's fix landed."""
        path = tmp_path / "surrogate-default-strict.txt"
        payload = "bad-\udc80-surrogate"

        with pytest.raises(UnicodeEncodeError):
            with target_open(str(path), "w") as f:
                f.write(payload)


# ══════════════════════════════════════════════════════════════════════════
# Item 7 — cp1252 unmasking: explicit encoding must not depend on PYTHONUTF8
# ══════════════════════════════════════════════════════════════════════════


class TestEncodingIndependentOfPythonUtf8Env:
    """This dev machine (and most CI) runs with PYTHONUTF8=1, which
    silently repairs any call site that forgot an explicit `encoding=...`
    by forcing UTF-8 mode process-wide (House's F2/F3 diagnosis: "hoy
    enmascarado por PYTHONUTF8=1"). Running the SAME round-trip in a fresh
    subprocess with PYTHONUTF8 explicitly disabled proves the guarantee
    comes from open_no_follow_symlink's own explicit `encoding="utf-8"`
    argument, not from an ambient environment variable a real end user's
    machine may not have set.

    The child process communicates back via `json.dumps` with the default
    `ensure_ascii=True` — this keeps the parent<->child pipe pure ASCII so
    a mangled *console* codepage in the harness itself can never masquerade
    as a mangled *file* round-trip, which is the only thing this test
    means to measure.

    RED now on Windows: the subprocess crashes (non-zero exit, AttributeError
    in stderr) before ever reaching the round-trip. GREEN after Task 2.
    """

    @pytest.mark.parametrize(
        "twin_module,twin_func",
        [
            ("git_helpers", "open_no_follow_symlink"),
            ("_symlink_safe_open", "open_no_follow_symlink_fallback"),
        ],
    )
    def test_roundtrip_survives_with_pythonutf8_unset(
        self, tmp_path, twin_module, twin_func
    ):
        path = tmp_path / "cp1252-unmask.txt"
        payload = "🔧 chore: corazón, señal, año — cp1252 sin PYTHONUTF8\n"

        code = textwrap.dedent(f"""
            import sys, json
            sys.path.insert(0, {repr(str(LIB_DIR))})
            from {twin_module} import {twin_func} as target_open

            payload = {payload!r}
            path = {repr(str(path))}
            with target_open(path, "w") as f:
                f.write(payload)
            with target_open(path, "r") as f:
                reread = f.read()
            print(json.dumps({{"payload": payload, "reread": reread}}))
        """)

        env = dict(os.environ)
        env.pop("PYTHONUTF8", None)
        env["PYTHONUTF8"] = "0"

        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True, text=True, encoding='utf-8', timeout=30, env=env,
        )

        assert result.returncode == 0, (
            f"subprocess crashed with PYTHONUTF8=0 for {twin_module}."
            f"{twin_func}:\nstdout={result.stdout}\nstderr={result.stderr}"
        )
        data = json.loads(result.stdout)
        assert data["reread"] == data["payload"]
