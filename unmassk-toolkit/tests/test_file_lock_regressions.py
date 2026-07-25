"""
Regression contract (test-first, RED) for 3 REAL breaks Moriarty found in
git_helpers.file_lock() and its callers, on top of the base contract in
test_file_lock.py (do not touch that file -- these are additive, sibling
coverage):

  T1-1 (session-start-crew.py): file_lock() wraps the ENTIRE read-diff-write
       cycle unconditionally, including the "content already canonical, zero
       writes needed" no-op path. On a repo whose containing directory is not
       writable (read-only mount, permission drift, restrictive umask), the
       lock file's own `os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)`
       raises PermissionError BEFORE the hook ever gets to check whether a
       write is even needed -- crashing a boot that would otherwise have been
       a pure no-op read.

  T1-2 (git-memory-uninstall.py): remove_claude_md_block()'s `with
       file_lock(claude_md):` is not wrapped in any try/except -- a
       PermissionError raised at lock-acquisition time propagates straight
       out of remove_claude_md_block() and out of main(), aborting the WHOLE
       uninstall (remove_manifest(), remove_old_install_files() never run)
       instead of degrading gracefully the way the write-failure path a few
       lines later already does (see ROB-MED-001 in
       test_atomic_claude_md_write.py -- that test sabotages
       tempfile.mkstemp AFTER the lock is already held; this file sabotages
       the LOCK ACQUISITION itself, a step earlier, which today's try/except
       around the write does not cover at all).

  T1-3 (Windows branch, deception): `while True: try: msvcrt.locking(...);
       break except OSError: continue` retries on ANY OSError, forever, with
       no distinction between transient contention (someone else holds the
       lock, will release) and a PERMANENT failure (disk I/O error, etc.)
       that will never resolve no matter how many times it's retried. Every
       real caller (session-start-crew.py, git-memory-uninstall.py, upgrade)
       hangs forever on a permanently-failing lock.

  Anti-pollution (Cerberus finding, folded in here rather than a 4th
  standalone class elsewhere): file_lock() creates `f"{target_path}.lock"`
  adjacent to CLAUDE.md and never removes it -- it shows up as a permanent
  untracked file in `git status --porcelain` at the project root after the
  very first write.

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity -- one test per finding, each derived from a REAL subprocess run
against the REAL hooks/bin scripts (never a hand-simulated stand-in for
their control flow). NO production code is touched by this file. Only
tests.

Deliberately NOT covered here (per the orchestrator's own "if fragile, leave
a note instead of coding it" allowance): file_lock()'s reentrancy. A single
process calling file_lock() on the same target twice (e.g. a future bug
where a writer nested inside another writer's `with` block) self-deadlocks
today -- fcntl.flock()/msvcrt.locking() are not reentrant, and this module
has no re-entrant/RLock-style guard. Encoding this as an automated test
means deliberately writing a self-deadlocking subprocess and racing a hard
kill against it purely to prove "yes, it hangs" -- that reproduces the
existing, expected (if under-documented) semantics of the underlying OS
primitives rather than a NEW regression, and every value it could prove is
already implied by the "Blocks... until the lock is acquired" contract in
file_lock()'s own docstring. Left as a note for Ultron instead: the
docstring should gain one explicit sentence -- "file_lock() is NOT
reentrant; do not call it from inside a `with file_lock(x):` block already
holding a lock on the same x, even across nested function calls -- doing so
deadlocks the process against itself."

Run only this file:
    python3 -m pytest unmassk-toolkit/tests/test_file_lock_regressions.py -v
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, UNINSTALL, run_script, git_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import any_block_outdated  # noqa: E402

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")


# ── Repo / IO helpers (self-contained, mirrors conventions already used by
# test_crew_content_gate_v2.py / test_atomic_claude_md_write.py) ───────────


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _install(repo):
    """Real producer, happy path: writes canonical CLAUDE.md + manifest.json
    via the real installer -- never a hand-typed stand-in."""
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"install --auto failed: {out}\n{err}"


def _claude_md_path(repo):
    return os.path.join(repo, "CLAUDE.md")


def _manifest_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "manifest.json")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _remove_stale_lock(repo):
    """Delete CLAUDE.md.lock if it already exists.

    Gotcha discovered live while writing this contract: git-memory-
    install.py's own real producer path ALSO calls file_lock() (same
    anti-pollution behavior the standalone class below documents -- the
    lock file is never unlinked after use), so a fixture built via
    _install(repo) already has a `CLAUDE.md.lock` sitting on disk BEFORE
    the read-only-directory regression is ever exercised. `os.open(path,
    os.O_RDWR | os.O_CREAT, 0o600)` on a file that ALREADY EXISTS only
    needs write permission on the FILE itself (still owner-writable,
    unaffected by the containing directory's mode) -- O_CREAT only
    matters, and only needs directory-write permission, when the entry
    does not exist yet. Without this cleanup step, chmod'ing the
    directory read-only silently fails to reproduce the regression at
    all (confirmed live: the crew hook exits 0 even on a read-only repo
    if a lock file happens to survive from a prior writer) -- callers
    that build their fixture via _install() must call this right before
    _make_dir_readonly_or_skip() to guarantee the lock file is genuinely
    absent and must be freshly CREATED under read-only conditions.
    """
    lock_path = _claude_md_path(repo) + ".lock"
    if os.path.exists(lock_path):
        os.unlink(lock_path)


def _run_crew(repo):
    return run_script(CREW_HOOK, repo)


def _run_uninstall_auto(repo):
    return run_script(UNINSTALL, repo, ["--auto"])


def _popen_py(code, cwd):
    return subprocess.Popen(
        [sys.executable, "-c", code],
        cwd=cwd,
        env=os.environ.copy(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def _wait(proc, timeout):
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError(
            f"subprocess did not finish within {timeout}s -- likely a "
            f"deadlock. partial stdout={out!r} partial stderr={err!r}"
        ) from None
    return proc.returncode, out, err


def _make_dir_readonly_or_skip(path):
    """chmod `path` to 0o555 (read+execute, no write) and verify the
    write-protection genuinely took effect with a real probe file BEFORE
    trusting it. If the probe write still succeeds (test process running as
    root -- POSIX permission bits don't apply to root -- or a platform that
    doesn't enforce owner-chmod at all), restore permissions immediately and
    SKIP with an explicit reason instead of producing a false pass. This is
    the orchestrator's own explicit instruction for this exact case.

    Caller owns restoring `path`'s mode in a `finally` block regardless of
    outcome (this helper only sets read-only up, on the success path).
    """
    os.chmod(path, 0o555)
    probe = os.path.join(path, ".dante_readonly_probe")
    try:
        fd = os.open(probe, os.O_RDWR | os.O_CREAT, 0o600)
        os.close(fd)
        os.unlink(probe)
    except OSError:
        return  # genuinely read-only -- proceed with the real regression test
    os.chmod(path, 0o755)
    pytest.skip(
        "directory write-protection is ineffective in this environment "
        "(running as root, or a platform that doesn't enforce owner chmod) "
        "-- cannot exercise this read-only-directory regression here"
    )


# ── T1-1: session-start-crew.py must not crash on a read-only, already-up-to
# -date repo (file_lock() acquisition itself fails before the "is a write
# even needed" check ever runs) ────────────────────────────────────────────


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX permission bits only -- chmod does not restrict the owning process on Windows",
)
class TestCrewBootReadOnlyRepoNoOpRegression:
    def test_up_to_date_boot_on_readonly_repo_exits_gracefully(self, tmp_path):
        """Fixture: a repo already fully installed with genuinely canonical
        CLAUDE.md content (real installer, not hand-typed) -- session-start-
        crew.py's own content-gate would take the "All managed blocks up to
        date" no-write branch if it ever got there. It never does: `with
        file_lock(str(claude_md)):` (hooks/session-start-crew.py:66) is
        entered unconditionally, BEFORE the existence check, the read, or
        the diff -- so on a read-only project root, the very first thing
        that happens is `os.open(f"{claude_md}.lock", os.O_RDWR |
        os.O_CREAT, 0o600)` raising PermissionError, crashing a boot that
        needed to perform zero writes.

        RED today: rc != 0, stderr contains an unhandled PermissionError
        traceback (no try/except anywhere in session-start-crew.py wraps
        the `with file_lock(...)` statement itself).

        Expected fixed behavior: rc == 0, no traceback, the exact same
        "[crew] All managed blocks up to date" message the no-op path
        already prints today when there's nothing to write and nothing
        blocks it.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        content_before = _read(_claude_md_path(repo))
        assert not any_block_outdated(content_before), (
            "precondition: a fresh install --auto must produce genuinely "
            "canonical content -- this test's fixture must start with ZERO "
            "writes needed, isolating the read-only-directory regression "
            "from any real content-diverges-so-a-write-was-needed case"
        )

        _remove_stale_lock(repo)
        _make_dir_readonly_or_skip(repo)
        try:
            rc, stdout, stderr = _run_crew(repo)
        finally:
            os.chmod(repo, 0o755)

        combined = stdout + "\n" + stderr
        assert "Traceback" not in combined, (
            f"session-start-crew.py must not crash with an unhandled "
            f"exception on a read-only, already-up-to-date repo. "
            f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        )
        assert rc == 0, (
            f"session-start-crew.py must exit 0 on a read-only, "
            f"already-up-to-date repo (a pure no-op read must never fail "
            f"just because the directory happens to be unwritable). "
            f"stdout={stdout!r} stderr={stderr!r}"
        )
        assert "All managed blocks up to date" in stdout, (
            "a genuinely no-op boot (content already canonical) must still "
            "report the same up-to-date message it does on a writable "
            f"repo, even when the directory is read-only. stdout={stdout!r}"
        )


# ── T1-2: git-memory-uninstall.py --auto must degrade gracefully (warn, not
# abort) when file_lock() acquisition fails, and still run the REMAINING
# uninstall steps ────────────────────────────────────────────────────────


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="POSIX permission bits only -- chmod does not restrict the owning process on Windows",
)
class TestUninstallReadOnlyRepoDegradesGracefully:
    def test_auto_uninstall_survives_readonly_claude_md_and_completes(self, tmp_path):
        """Fixture: a real installed repo (manifest.json + canonical
        CLAUDE.md via the real installer), then real user text prepended
        outside the managed blocks so remove_claude_md_block() takes its
        WRITE branch, not its "content becomes empty -> unlink the whole
        file" early-return branch (a fixture built from ONLY managed blocks
        would silently dodge the write path entirely -- see this project's
        own documented gotcha in
        unmassk-toolkit-python-test-conventions.md's
        "fix-atomic-claude-md-write, hardening pass" entry; the identical
        real block content from the real installer is kept, only the
        wrapping user-text literal is added, same technique
        test_atomic_claude_md_write.py's ROB-MED-001 test already uses).

        bin/git-memory-uninstall.py::remove_claude_md_block()'s `with
        file_lock(claude_md):` (line ~126) has NO try/except around it --
        unlike the write step a few lines later (which DOES catch OSError
        and returns False, per ROB-MED-001). A PermissionError raised at
        lock ACQUISITION time -- one step earlier than the write --
        propagates straight out of remove_claude_md_block(), out of
        main(), aborting the whole uninstall before remove_manifest() or
        remove_old_install_files() ever run.

        RED today: rc != 0, unhandled traceback, manifest.json survives
        (remove_manifest() never reached).

        Expected fixed behavior: rc == 0, "Uninstall complete" printed,
        AND -- verified via the INDEPENDENT channel of the manifest file's
        real on-disk presence, not just stdout text -- manifest.json is
        actually gone, proving the later steps genuinely ran rather than
        the process merely not crashing.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        claude_md = _claude_md_path(repo)
        canonical_content = _read(claude_md)
        _write(claude_md, "# User notes\n\nKeep this line.\n\n" + canonical_content)

        manifest_path = _manifest_path(repo)
        assert os.path.isfile(manifest_path), (
            "precondition: manifest.json must exist before uninstall runs"
        )

        # See _remove_stale_lock()'s own docstring: the real installer above
        # already exercises file_lock() as a side effect and leaves
        # CLAUDE.md.lock behind (anti-pollution finding) -- without removing
        # it first, the read-only-directory regression below would silently
        # fail to reproduce (os.open() on an EXISTING file doesn't need
        # directory-write permission at all).
        _remove_stale_lock(repo)
        _make_dir_readonly_or_skip(repo)
        try:
            rc, stdout, stderr = _run_uninstall_auto(repo)
        finally:
            os.chmod(repo, 0o755)

        combined = stdout + "\n" + stderr
        assert "Traceback" not in combined, (
            f"git-memory-uninstall.py --auto must not crash with an "
            f"unhandled exception when CLAUDE.md's directory is read-only "
            f"-- it must degrade gracefully and keep going. "
            f"rc={rc} stdout={stdout!r} stderr={stderr!r}"
        )
        assert rc == 0, (
            f"uninstall --auto must exit 0 (degrade, not abort) when only "
            f"the CLAUDE.md step fails due to a read-only directory. "
            f"stdout={stdout!r} stderr={stderr!r}"
        )
        assert "Uninstall complete" in stdout, (
            f"the uninstall flow must reach its normal completion message "
            f"even though the CLAUDE.md step failed. stdout={stdout!r}"
        )
        assert not os.path.isfile(manifest_path), (
            "remove_manifest() must still have run (and succeeded -- "
            ".claude/.unmassk/ itself is NOT read-only, only the repo "
            "root is) even though remove_claude_md_block() failed earlier "
            "in the SAME main() -- proving the abort didn't take out the "
            f"rest of the flow. manifest still present at {manifest_path!r}"
        )


# ── T1-3: Windows branch deception -- a PERMANENT locking error must raise,
# not retry forever ─────────────────────────────────────────────────────────


class TestWindowsPermanentLockingErrorMustRaiseNotLoopForever:
    def test_permanent_locking_error_raises_within_bounded_attempts(self, tmp_path):
        """git_helpers.file_lock()'s Windows branch does `while True: try:
        msvcrt.locking(fd, msvcrt.LK_LOCK, 1); break except OSError:
        continue` -- an INDISCRIMINATE catch-and-retry with NO bound and NO
        distinction between transient contention (another process
        genuinely holds the lock and will eventually release it -- worth
        retrying) and a PERMANENT failure (e.g. an I/O error on the lock
        file itself) that will NEVER resolve no matter how many times it's
        retried. Every real caller (session-start-crew.py,
        git-memory-uninstall.py, git-memory-upgrade.py) would hang forever.

        Reproduced with a FAKE msvcrt injected into sys.modules -- same
        structural-spoof technique (including the pre-import-stdlib-
        modules-before-spoofing-sys.platform gotcha) as
        test_file_lock.py::test_windows_branch_uses_msvcrt_not_fcntl_no_attribute_error
        -- whose locking() ALWAYS raises OSError(errno.EIO, ...): an I/O
        error is an unambiguous PERMANENT failure signature, never a
        "someone else holds this lock right now" contention signal. Real
        Windows msvcrt error-code semantics for distinguishing "permanent"
        from "lock currently held, try again" are UNVERIFIED here -- this
        machine is not Windows, and CI's windows-latest run is the only
        place that distinction is ever exercised for real. What IS proven
        here is the retry LOOP's own logic (pure Python, platform-
        independent code once sys.platform is spoofed): it must give up
        and re-raise within a bounded number of attempts instead of
        spinning on an error that provably never changes.

        Anti-hang design (the orchestrator's explicit ask: never let a
        deadlock/infinite-loop repro hang the suite): the fake counts its
        own calls and, if file_lock() is STILL retrying past a generous
        LOOP_THRESHOLD (far more attempts than any reasonable bounded-retry
        fix would ever need -- this is a tight loop with no sleep, so even
        thousands of calls take milliseconds), raises a DISTINCT sentinel
        exception (_LoopDetected) instead of OSError -- turning "this
        would hang forever" into a fast, explicit, deterministic
        assertion failure rather than an actual hang. A hard
        subprocess-level timeout is layered on top as a second,
        independent backstop in case the sentinel technique itself were
        ever bypassed.

        RED today: `except OSError: continue` never distinguishes --
        every one of the fake's calls raises the same permanent OSError,
        so the loop runs until the sentinel fires at LOOP_THRESHOLD,
        reported as outcome == "looped_forever", never
        "raised_os_error".
        """
        target = str(tmp_path / "CLAUDE.md")
        _write(target, "content\n")
        result_path = str(tmp_path / "result.json")

        code = f"""
import sys, types, json, errno
# Pre-import every stdlib module git_helpers.py imports at its own top
# level BEFORE spoofing sys.platform -- subprocess.py's own top-level body
# does `if sys.platform == "win32": import _winapi`, so importing it for
# the FIRST time under a spoofed "win32" would crash with
# ModuleNotFoundError: No module named '_winapi' on this real POSIX
# machine. Importing it now (real platform still active) caches it in
# sys.modules so git_helpers.py's later `import subprocess` is a cache
# hit and never re-executes that top-level body.
import os as _os, signal as _signal, subprocess as _subprocess, tempfile as _tempfile, time as _time

sys.path.insert(0, {LIB_DIR!r})

LOOP_THRESHOLD = 10000
calls = {{"count": 0}}


class _LoopDetected(Exception):
    pass


fake_msvcrt = types.ModuleType("msvcrt")


def _fake_locking(fd, mode, nbytes):
    calls["count"] += 1
    if calls["count"] > LOOP_THRESHOLD:
        raise _LoopDetected(
            f"file_lock() retried past {{LOOP_THRESHOLD}} attempts on an "
            "error that provably never changes -- this would hang forever "
            "in real life"
        )
    raise OSError(errno.EIO, "simulated PERMANENT lock failure (I/O error, not contention)")


fake_msvcrt.locking = _fake_locking
fake_msvcrt.LK_LOCK = 1
fake_msvcrt.LK_UNLCK = 0
sys.modules["msvcrt"] = fake_msvcrt

sys.platform = "win32"
from git_helpers import file_lock

outcome = None
try:
    with file_lock({target!r}):
        pass
    outcome = "acquired_no_error"
except _LoopDetected:
    outcome = "looped_forever"
except OSError:
    outcome = "raised_os_error"

with open({result_path!r}, "w", encoding="utf-8") as f:
    json.dump({{"outcome": outcome, "calls": calls["count"]}}, f)
"""
        proc = _popen_py(code, str(tmp_path))
        rc, out, err = _wait(proc, timeout=20)
        assert rc == 0, (
            "the spoofing subprocess itself must not crash with an "
            f"unrelated error. stdout={out!r} stderr={err!r}"
        )

        result = json.loads(_read(result_path))
        assert result["outcome"] == "raised_os_error", (
            "file_lock() must give up and RAISE an OSError-derived "
            "exception when msvcrt.locking() keeps failing with a "
            f"PERMANENT error -- got outcome={result['outcome']!r} after "
            f"{result['calls']} attempts (today's `except OSError: "
            "continue` retries indiscriminately forever on ANY OSError, "
            "so this either loops until the anti-hang sentinel fires, or "
            "never terminates at all)."
        )
        assert result["calls"] < 10000, (
            f"file_lock() must give up within a BOUNDED number of retry "
            f"attempts, not exhaust {result['calls']} of them before "
            "raising -- an effectively-unbounded retry loop hangs every "
            "real caller indefinitely on a genuinely permanent failure."
        )


# ── Anti-pollution: the .lock file must not surface as a permanent
# untracked artifact in `git status --porcelain` (Cerberus finding) ────────


class TestLockFileDoesNotPolluteGitStatus:
    def test_lock_file_not_untracked_after_real_writer_runs(self, tmp_path):
        """Run a REAL production writer (session-start-crew.py creating
        CLAUDE.md from scratch on a fresh repo -- this genuinely exercises
        file_lock(), since the `with file_lock(...)` wraps the create-new-
        file branch too, not just the update branch) and check the
        resulting `git status --porcelain` at the project root, derived
        live from the real git binary -- never a hand-typed expectation of
        what git would report.

        file_lock() creates `f"{{target_path}}.lock"` adjacent to
        CLAUDE.md (`os.open(lock_path, os.O_RDWR | os.O_CREAT, 0o600)`)
        and closes the fd on exit, but never os.unlink()s it -- the lock
        file is meant to be reused by every future writer, so deleting it
        after use would be wrong (a race: unlinking while file B on the
        SAME inode still holds it open is fine POSIX-wise, but recreating
        it on every call defeats the whole point of a stable, shared lock
        path). It should instead live somewhere already excluded from git
        (e.g. under `.claude/.unmassk/`) or be added to `.gitignore` --
        either way, it must never show up as a permanent untracked file
        sitting right next to CLAUDE.md at the project root.

        RED today: `CLAUDE.md.lock` appears in `git status --porcelain`
        output as an untracked ("??") entry.
        """
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must succeed. stdout={stdout!r} stderr={stderr!r}"
        assert os.path.isfile(_claude_md_path(repo)), (
            "sanity check: CLAUDE.md must have been created for real -- "
            "otherwise file_lock() was never genuinely exercised by this run"
        )

        rc2, status_out, status_err = git_cmd(["status", "--porcelain"], repo)
        assert rc2 == 0, f"git status --porcelain must succeed. stderr={status_err!r}"
        assert "CLAUDE.md.lock" not in status_out, (
            "the lock file must not surface as an untracked artifact in "
            f"git status --porcelain -- got: {status_out!r}. It must "
            "either live under an already-git-ignored directory (e.g. "
            ".claude/.unmassk/) or be added to .gitignore."
        )
