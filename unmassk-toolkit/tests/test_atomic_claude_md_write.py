"""
Acceptance contract (test-first, RED) for the atomic-write fix to CLAUDE.md's
managed blocks -- docs/plan/fix-atomic-claude-md-write.md, Task 1.

BUG T1 (House diagnosis, already done): every writer of CLAUDE.md's managed
blocks opens the file with `open(claude_md, "w")` (or, in this codebase,
`open_no_follow_symlink(claude_md, "w")`, whose "w" mode still carries
O_TRUNC -- see lib/git_helpers.py's open_no_follow_symlink() docstring/
implementation). The instant that open() call returns, the file is already
truncated to 0 bytes -- there is no temp file, no os.replace(), no lock. A
crash / kill -9 / full-disk error anywhere between that open() and the
completion of the write leaves CLAUDE.md empty or partially written. The
correct atomic pattern (tempfile.mkstemp() in the SAME directory + a single
os.replace()) already exists in this repo at lib/boot_fetch_stamp.py
(_write_own_stamp(), ~lines 256-303) but was never applied to CLAUDE.md.

This file targets lib/install_apply.py::_update_claude_md() -- the
highest-traffic of the 4 affected writers (shared by git-memory-install.py,
git-memory-upgrade.py's apply_upgrade(), and git-memory-repair.py; the plan
names it explicitly as the target for Task 1 since Ultron has not yet built
the centralized helper lib/git_helpers.py Task 2 will add). The other 3
writers (hooks/session-start-crew.py, bin/git-memory-uninstall.py) are
Task 2's routing scope, not re-derived here -- once Ultron centralizes the
atomic helper in lib/git_helpers.py and routes all 4 writers through it,
this same contract exercises the shared code path they all use.

Contract (4 tests, one per plan bullet):
    1. TestAtomicityOnInterruptedWrite  -- a write that crashes AFTER the
       file has been opened for writing (the real danger window, since
       "w" mode truncates at open() time) must leave CLAUDE.md's ORIGINAL
       content intact -- never empty, never partial. RED today: the sabotage
       below lets the real (buggy) open_no_follow_symlink("w") truncate the
       file for real, then crashes before any bytes of the new content are
       written -- proving the file is empty afterward, not preserved.
    2. TestRoundTripSuccess -- a normal (non-interrupted) write leaves the
       COMPLETE, correct new content in place. Expected content is derived
       from the real production function (managed_blocks.upsert_managed_blocks),
       never hand-typed (§34). Likely already GREEN today (happy path) --
       a lock-in / regression guard, not a RED assertion.
    3. TestTempFileSameDirectory -- the temp file used during the write must
       be created in the SAME directory as CLAUDE.md (a cross-device
       os.replace() is not atomic). RED today: production writes with a
       plain open(), no tempfile.mkstemp() call is ever made -- the spy
       below records zero calls.
    4. TestSymlinkPathSafetyPreserved -- CLAUDE.md's existing symlink-reject
       behavior (open_no_follow_symlink) must survive the atomic rewrite:
       a symlink planted at CLAUDE.md must still be rejected, never
       followed, never silently replaced by os.replace() swapping the
       symlink's target transparently. Expected GREEN today (locks in the
       current good behavior as an explicit regression guard for Task 2's
       os.replace()-based rewrite).

Verify: run only this file, read the real exit code (never tail/head).

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity -- 4 tests, one per plan bullet. NO production code is touched
by this file. Only tests.
"""

import errno
import importlib.util
import json
import os
import sys
import tempfile

import pytest

from conftest import SOURCE_ROOT, UNINSTALL, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import git_helpers  # noqa: E402

from managed_blocks import upsert_managed_blocks  # noqa: E402

ORIGINAL_CONTENT = "# CLAUDE.md\n\nSome pre-existing user text that must survive a crash.\n"


# ── Helpers ──────────────────────────────────────────────────────────────


def _target_dir(tmp_path, name="repo"):
    """A plain target directory -- _update_claude_md(target) has no git
    dependency, so no git init is needed for these tests."""
    target = str(tmp_path / name)
    os.makedirs(target)
    return target


def _claude_md_path(target):
    return os.path.join(target, "CLAUDE.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _run_py(code, cwd, timeout=30):
    return run_cmd([sys.executable, "-c", code], cwd, timeout=timeout)


# ── Test 1: atomicity on interrupted write ────────────────────────────────


class TestAtomicityOnInterruptedWrite:
    def test_crash_after_open_preserves_original_content(self, tmp_path):
        """Simulate a crash/kill mid-write: the REAL open_no_follow_symlink("w")
        is called first (so, under today's buggy code, the real O_TRUNC
        truncation genuinely happens), then a simulated crash prevents any
        of the new content from being written. CLAUDE.md must retain its
        ORIGINAL content afterward -- never empty, never partial.

        Technique mirrors tests/test_crew_content_gate_v2.py's
        _run_sabotaged_producer(): monkeypatch install_apply.open_no_follow_symlink
        in an isolated subprocess. Unlike that file (which sabotages the
        OPEN itself, before any truncation occurs), this sabotages AFTER
        the real open() succeeds -- because "w" mode truncates at open()
        time, not at write() time, the true danger window starts the
        instant open() returns, which is exactly what this test proves is
        unsafe today.

        RED today: open_no_follow_symlink(claude_md, "w") truncates the
        file for real via O_TRUNC as part of its os.open() call (see
        lib/git_helpers.py). The crash happens after that truncation but
        before any new bytes land, so CLAUDE.md ends up empty (0 bytes),
        not equal to ORIGINAL_CONTENT.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)

        code = f"""
import sys, os, json
sys.path.insert(0, {LIB_DIR!r})
os.chdir({target!r})

import install_apply

_real_open = install_apply.open_no_follow_symlink

def _sabotaged_open(path, mode="w", encoding="utf-8", **kwargs):
    # Let the REAL open happen first -- under today's code this is the
    # exact moment "w" mode's O_TRUNC destroys the original content.
    real_f = _real_open(path, mode, encoding=encoding, **kwargs)
    if mode == "w" and os.path.basename(str(path)) == "CLAUDE.md":
        class _CrashesOnWrite:
            def __enter__(self_inner):
                return self_inner
            def __exit__(self_inner, exc_type, exc, tb):
                real_f.close()
                return False
            def write(self_inner, data):
                raise OSError("simulated crash mid-write (disk full / kill -9)")
        return _CrashesOnWrite()
    return real_f

install_apply.open_no_follow_symlink = _sabotaged_open

try:
    install_apply._update_claude_md({target!r})
    result = {{"raised": False}}
except OSError as e:
    result = {{"raised": True, "msg": str(e)}}
print(json.dumps(result))
"""
        rc, out, err = _run_py(code, target)
        assert rc == 0, f"sabotage subprocess itself must not crash. stdout={out!r} stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["raised"], (
            "sanity check on the sabotage setup: the simulated crash must actually "
            f"propagate as an OSError out of _update_claude_md(), or nothing was "
            f"interrupted. payload={payload!r}"
        )

        content_after = _read(claude_md)
        assert content_after == ORIGINAL_CONTENT, (
            "CLAUDE.md must retain its ORIGINAL content after a write interrupted "
            "mid-way -- it must never be left empty or partial. "
            f"Got {content_after!r} (len={len(content_after)}), "
            f"expected {ORIGINAL_CONTENT!r} (len={len(ORIGINAL_CONTENT)})."
        )


# ── Test 2: round-trip success (§34) ──────────────────────────────────────


class TestRoundTripSuccess:
    def test_normal_write_round_trips_full_new_content(self, tmp_path):
        """A normal (non-interrupted) write leaves the COMPLETE, correct new
        content in place -- read it back and compare against what the real
        production transform (managed_blocks.upsert_managed_blocks) says the
        result should be. Expected value is derived from the same real
        function the producer calls, never hand-typed (§34) -- computed
        HERE, in the test process, against the same ORIGINAL_CONTENT written
        to disk, so it is a genuine round-trip check.

        This is a lock-in / regression guard: expected to already be GREEN
        today (the happy path already works), and MUST remain GREEN once
        the atomic rewrite (temp + os.replace) lands in Task 2 -- the fix
        must change HOW the content is written, never WHAT is written.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)

        expected_new_content, _log = upsert_managed_blocks(ORIGINAL_CONTENT)

        code = f"""
import sys, os
sys.path.insert(0, {LIB_DIR!r})
os.chdir({target!r})
import install_apply
install_apply._update_claude_md({target!r})
"""
        rc, out, err = _run_py(code, target)
        assert rc == 0, f"_update_claude_md() must not crash on a normal write. stdout={out!r} stderr={err!r}"

        content_after = _read(claude_md)
        assert content_after == expected_new_content, (
            "a normal write must leave CLAUDE.md's content exactly equal to "
            "managed_blocks.upsert_managed_blocks(original)'s real output -- "
            f"round-trip mismatch. Got {content_after!r}, expected {expected_new_content!r}."
        )


# ── Test 3: temp file lives in the same directory ─────────────────────────


class TestTempFileSameDirectory:
    def test_temp_file_created_in_same_directory_as_claude_md(self, tmp_path):
        """The temp file used during the write must be created in the SAME
        directory as CLAUDE.md -- tempfile.mkstemp()+os.replace() is only
        atomic when both paths are on the same filesystem/device; a temp
        file in e.g. the system tmpdir would make os.replace() cross
        devices and lose its atomicity guarantee. Mirrors the real pattern
        already used by lib/boot_fetch_stamp.py::_write_own_stamp()
        (tempfile.mkstemp(dir=runtime_dir, ...) + os.replace()).

        tempfile.mkstemp is patched as a SPY (delegates to the real
        function, only records call args) so this works regardless of
        which lib module ends up calling it once Ultron centralizes the
        helper (plan Task 2: lib/git_helpers.py).

        RED today: install_apply._update_claude_md() writes via a plain
        open_no_follow_symlink(claude_md, "w") -- no tempfile.mkstemp()
        call is ever made, so the spy records zero calls.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)
        real_dir = os.path.dirname(os.path.realpath(claude_md))

        code = f"""
import sys, os, json, tempfile
sys.path.insert(0, {LIB_DIR!r})
os.chdir({target!r})

calls = []
_real_mkstemp = tempfile.mkstemp

def _spy_mkstemp(*args, **kwargs):
    calls.append({{"dir": kwargs.get("dir")}})
    return _real_mkstemp(*args, **kwargs)

tempfile.mkstemp = _spy_mkstemp

import install_apply
install_apply._update_claude_md({target!r})

print(json.dumps({{"calls": calls}}))
"""
        rc, out, err = _run_py(code, target)
        assert rc == 0, f"_update_claude_md() must not crash. stdout={out!r} stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])
        calls = payload["calls"]

        assert calls, (
            "no tempfile.mkstemp() call was made during the write -- the atomic "
            "temp-file-then-replace pattern (see lib/boot_fetch_stamp.py) is not "
            f"in use yet. calls={calls!r}"
        )
        matching = [c for c in calls if c.get("dir") and os.path.realpath(c["dir"]) == real_dir]
        assert matching, (
            f"tempfile.mkstemp() must be called with dir={real_dir!r} (the SAME "
            "directory as CLAUDE.md) so the final os.replace() stays on one "
            f"filesystem and remains atomic. calls={calls!r}"
        )


# ── Test 4: symlink path-safety is preserved ──────────────────────────────


class TestSymlinkPathSafetyPreserved:
    def test_symlinked_claude_md_write_is_rejected_not_followed(self, tmp_path, real_symlink_capable):
        """CLAUDE.md's existing symlink-reject behavior must survive the
        atomic rewrite: a symlink planted at CLAUDE.md pointing outside the
        target directory must still be REJECTED (nothing written through
        it, the symlink itself is not silently replaced by os.replace()
        swapping the directory entry). This locks in the invariant Task 2
        must preserve -- os.replace() itself does not follow a symlink at
        the destination (it swaps the directory entry), so a naive
        temp+os.replace() rewrite could silently turn CLAUDE.md from "a
        symlink to some external file" into "a real file with the new
        managed blocks", replacing the semantic without ever raising --
        the opposite of today's fail-closed reject.

        Expected GREEN today: open_no_follow_symlink() already rejects the
        symlink before this rewrite exists. This test's purpose is to
        pin that behavior in place as an explicit regression guard.
        """
        target = _target_dir(tmp_path)
        outside_target = str(tmp_path / "outside_target.txt")
        outside_content = "OUTSIDE CONTENT -- must never be touched by CLAUDE.md's write.\n"
        _write(outside_target, outside_content)

        claude_md = _claude_md_path(target)
        os.symlink(outside_target, claude_md)
        assert os.path.islink(claude_md), "sanity check: CLAUDE.md must genuinely be a symlink"

        code = f"""
import sys, os, json
sys.path.insert(0, {LIB_DIR!r})
os.chdir({target!r})
import install_apply
try:
    install_apply._update_claude_md({target!r})
    result = {{"raised": False}}
except OSError as e:
    result = {{"raised": True, "msg": str(e)}}
print(json.dumps(result))
"""
        rc, out, err = _run_py(code, target)
        assert rc == 0, f"sabotage subprocess itself must not crash. stdout={out!r} stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["raised"], (
            "a symlink planted at CLAUDE.md must be rejected (raise), never "
            f"silently followed or replaced. payload={payload!r}"
        )

        assert os.path.islink(claude_md), (
            "CLAUDE.md must still be the SAME symlink after a rejected write -- "
            "an atomic os.replace() must not silently swap the symlink's "
            "directory entry for a real file."
        )
        assert _read(outside_target) == outside_content, (
            "the external file the symlink points to must never be modified by "
            "a rejected CLAUDE.md write."
        )


# ═══════════════════════════════════════════════════════════════════════════
# Hardening pass (test-first, 2nd entry): Ultron implemented the atomic
# helper (lib/git_helpers.py::_AtomicWriteNoFollowSymlink,
# open_no_follow_symlink(..., atomic=True)) and routed all 4 writers through
# it (commits e261867/7a432d1). The 4-test contract above is now GREEN
# (verified live above, 4/4 passed). This section fixes the Cerberus/Argus
# follow-ups from that same round: permission preservation (ROB-MED-002),
# close()-without-commit fail-loud + no-orphan (ROB-MED-003), fdopen-failure
# no-orphan (ROB-LOW-004), the atomic=True mode guard, and the uninstall
# regression (ROB-MED-001, remove_claude_md_block() must not abort the rest
# of uninstall when the atomic write itself fails).
#
# These tests are expected to PASS against the code as it stands NOW (this
# is a verify/hardening pass, not a fresh RED contract) -- per the
# orchestrator's instruction, a failure here means a real gap, not an
# intentional RED baseline. Mutation-checked where noted, to prove each
# assertion is actually exercising the guard it claims and isn't vacuously
# true. NO production code is touched by this file. Only tests.
# ═══════════════════════════════════════════════════════════════════════════


def _tmp_orphans(target_dir):
    """List any leftover atomic-write temp files (".<basename>.<rand>.tmp",
    tempfile.mkstemp()'s own naming shape from _AtomicWriteNoFollowSymlink)
    in target_dir. Used to prove no orphan survives a failure path."""
    return [n for n in os.listdir(target_dir) if n.endswith(".tmp")]


# ── Test: permission preservation (ROB-MED-002) ──────────────────────────


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits only")
class TestPermissionPreservation:
    def test_existing_file_mode_is_preserved_after_atomic_write(self, tmp_path):
        """A pre-existing CLAUDE.md at mode 0644 must STAY at 0644 after a
        normal atomic write -- tempfile.mkstemp() always creates its temp
        file at 0600, so without an explicit chmod-to-match step, the final
        os.replace() would silently narrow every atomically-rewritten
        CLAUDE.md from whatever mode it had (e.g. group-readable 0644) down
        to 0600 on every single write. This is the blocking permission-
        regression Cerberus/Argus flagged (ROB-MED-002).
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)
        os.chmod(claude_md, 0o644)
        assert oct(os.stat(claude_md).st_mode & 0o777) == oct(0o644), (
            "sanity check: fixture must genuinely start at 0644"
        )

        with git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True) as f:
            f.write("new content\n")

        mode_after = os.stat(claude_md).st_mode & 0o777
        assert oct(mode_after) == oct(0o644), (
            f"CLAUDE.md's mode must be preserved across an atomic write -- "
            f"expected 0o644, got {oct(mode_after)}. A silent narrowing to "
            "0600 (tempfile.mkstemp()'s default) would lock out any "
            "group/other reader the file previously allowed."
        )

    def test_new_file_gets_default_0600(self, tmp_path):
        """A brand-new CLAUDE.md (no pre-existing file to preserve a mode
        from) keeps mkstemp's own default of 0600 -- consistent with every
        other write-mode open_no_follow_symlink() call in this module. This
        is the control case for the preservation test above: preservation
        only kicks in when a prior file exists.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        assert not os.path.exists(claude_md), "sanity check: must genuinely be new"

        with git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True) as f:
            f.write("brand new content\n")

        mode_after = os.stat(claude_md).st_mode & 0o777
        assert oct(mode_after) == oct(0o600), (
            f"a brand-new file must default to 0600 (mkstemp's own default), "
            f"got {oct(mode_after)}"
        )

    def test_mutation_check_without_chmod_preservation_mode_would_be_0600(self, tmp_path):
        """Mutation-check performed manually (not committed as a permanent
        test): temporarily stripped the `if sys.platform != "win32" and
        os.path.exists(self._path): ... os.chmod(self._tmp_path,
        existing_mode)` block from
        git_helpers.py::_AtomicWriteNoFollowSymlink.__exit__ (replaced with
        a bare `pass`), reran
        test_existing_file_mode_is_preserved_after_atomic_write ALONE, and
        confirmed it FAILED with mode_after == 0o600 instead of 0o644 --
        proving the assertion genuinely exercises the chmod-preservation
        code path and isn't vacuously true. Production file was restored
        to its original content immediately after (verified via `git diff`
        showing zero changes) before this report was written. This test
        function is a documentation placeholder for that manual check, not
        a self-mutating test -- it makes the same real assertion again so
        the check is re-runnable by inspection.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)
        os.chmod(claude_md, 0o644)

        with git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True) as f:
            f.write("new content\n")

        assert oct(os.stat(claude_md).st_mode & 0o777) == oct(0o644)


# ── Test: crash inside `with` leaves no orphan, direct unit test ─────────


class TestCrashCleanupNoOrphan:
    def test_exception_inside_with_preserves_original_and_leaves_no_orphan(self, tmp_path):
        """DIRECT unit test on _AtomicWriteNoFollowSymlink (no subprocess,
        no proxy/wrapper) -- Cerberus flagged that the existing
        TestAtomicityOnInterruptedWrite (subprocess sabotage of
        open_no_follow_symlink itself) does not exercise the REAL atomic
        class's own cleanup path, and its sabotage technique leaves a
        dangling .tmp behind by construction (the proxy never creates a
        real tempfile.mkstemp() file at all). This test instead calls the
        real atomic writer directly and raises INSIDE the real `with`
        block, then checks both (a) CLAUDE.md's original content survived
        untouched and (b) zero .tmp files remain in the directory
        afterward -- the __exit__() exception branch must close and
        os.unlink() the temp file, never leave it orphaned.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)

        with pytest.raises(RuntimeError, match="simulated crash"):
            with git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True) as f:
                f.write("partial content that must never land")
                raise RuntimeError("simulated crash mid-write")

        content_after = _read(claude_md)
        assert content_after == ORIGINAL_CONTENT, (
            "CLAUDE.md must retain its ORIGINAL content when the `with` block "
            f"raises mid-write. Got {content_after!r}."
        )
        orphans = _tmp_orphans(target)
        assert orphans == [], (
            f"no .tmp file must survive a crash inside the `with` block -- "
            f"found orphan(s): {orphans!r}"
        )


# ── Test: close() fail-loud (ROB-MED-003) ─────────────────────────────────


class TestCloseFailLoud:
    def test_direct_close_without_commit_raises_and_leaves_no_orphan(self, tmp_path):
        """Calling .close() directly (bypassing the `with` block entirely)
        must raise OSError (errno.EBADF) rather than silently succeeding --
        a silent no-op close would let a caller believe an unfinished write
        had succeeded while the buffered content was simply abandoned. Must
        also leave zero .tmp orphans -- close() cleans up before raising.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)

        f = git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True)
        f.write("abandoned content")

        with pytest.raises(OSError) as exc_info:
            f.close()
        assert exc_info.value.errno == errno.EBADF, (
            f"direct close() without commit must raise OSError(errno.EBADF), "
            f"got errno={exc_info.value.errno!r}"
        )

        assert _read(claude_md) == ORIGINAL_CONTENT, (
            "an abandoned (never committed) write must never touch CLAUDE.md's "
            "original content"
        )
        orphans = _tmp_orphans(target)
        assert orphans == [], f"direct close() must not leave a .tmp orphan: {orphans!r}"

    def test_close_after_normal_with_exit_is_a_noop(self, tmp_path):
        """A close() call AFTER a normal `with`-block exit (already
        committed) must behave like a plain file object's idempotent
        .close() -- no exception, no side effect -- since the write already
        landed via os.replace() inside __exit__().
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)

        with git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True) as f:
            f.write("committed content\n")
            committed_f = f

        committed_f.close()  # must not raise

        assert _read(claude_md) == "committed content\n"


# ── Test: fdopen() failure leaves no orphan (ROB-LOW-004) ─────────────────


class TestFdopenFailureLeavesNoOrphan:
    def test_fdopen_failure_in_init_cleans_up_temp_file(self, tmp_path, monkeypatch):
        """If os.fdopen() itself raises inside _AtomicWriteNoFollowSymlink.__init__
        (e.g. a bad encoding name), the already-created tempfile.mkstemp()
        temp file (and its raw fd) must not be leaked -- __init__ must close
        the fd and unlink the temp file before letting the original
        exception propagate.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)

        def _raising_fdopen(*args, **kwargs):
            raise OSError("simulated fdopen failure")

        monkeypatch.setattr(os, "fdopen", _raising_fdopen)

        with pytest.raises(OSError, match="simulated fdopen failure"):
            git_helpers.open_no_follow_symlink(claude_md, "w", atomic=True)

        orphans = _tmp_orphans(target)
        assert orphans == [], (
            f"an os.fdopen() failure in __init__ must not leak the temp file "
            f"mkstemp() already created: found orphan(s) {orphans!r}"
        )
        assert not os.path.exists(claude_md), (
            "CLAUDE.md itself must never be created when the write never even "
            "got past __init__"
        )


# ── Test: atomic=True guard rejects non-"w" modes ─────────────────────────


class TestAtomicGuardRejectsNonWriteMode:
    def test_atomic_true_with_read_mode_raises_value_error(self, tmp_path):
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)

        with pytest.raises(ValueError):
            git_helpers.open_no_follow_symlink(claude_md, "r", atomic=True)

    def test_atomic_true_with_append_mode_raises_value_error(self, tmp_path):
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        _write(claude_md, ORIGINAL_CONTENT)

        with pytest.raises(ValueError):
            git_helpers.open_no_follow_symlink(claude_md, "a", atomic=True)


# ── Test: uninstall's remove_claude_md_block() survives a write failure ──
# (ROB-MED-001)


class TestUninstallAtomicWriteFailureDoesNotAbort:
    def test_remove_claude_md_block_returns_false_and_does_not_propagate(self, tmp_path):
        """MED-001 (Cerberus): if the atomic write inside
        remove_claude_md_block() fails (e.g. mkstemp() can't create a temp
        file in the containing directory), the function must catch OSError,
        print a warning, and return False -- never propagate the exception
        and never abort the rest of the uninstall flow (remove_manifest(),
        remove_old_install_files(), etc. must still run afterward in
        main()). Reproduced via a real, isolated subprocess that
        monkeypatches tempfile.mkstemp to fail globally, loads the real
        hyphenated bin/git-memory-uninstall.py via importlib (mirrors this
        codebase's own convention for hyphenated-filename scripts), and
        calls remove_claude_md_block() directly.
        """
        target = _target_dir(tmp_path)
        claude_md = _claude_md_path(target)
        # Real canonical content WITH managed blocks present AND user text
        # outside the blocks -- if the blocks were the ONLY content,
        # remove_claude_md_block() would collapse to "" and take its
        # separate os.unlink()-the-whole-file early-return branch (a
        # DIFFERENT code path that never reaches the atomic write / mkstemp
        # at all), never exercising the write-failure branch this test
        # targets. The leading user text guarantees content survives block
        # removal and the function reaches its atomic write step.
        canonical_content, _log = upsert_managed_blocks("# User notes\n\nKeep this line.\n")
        _write(claude_md, canonical_content)

        code = f"""
import sys, os, json, tempfile, importlib.util
sys.path.insert(0, {LIB_DIR!r})
os.chdir({target!r})

def _failing_mkstemp(*args, **kwargs):
    raise OSError(13, "simulated: permission denied creating temp file")

tempfile.mkstemp = _failing_mkstemp

spec = importlib.util.spec_from_file_location("uninstall_mod", {UNINSTALL!r})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

result = mod.remove_claude_md_block({target!r})
print(json.dumps({{"result": result}}))
"""
        rc, out, err = _run_py(code, target)
        assert rc == 0, (
            f"remove_claude_md_block() must not crash/propagate the write failure "
            f"out of the subprocess. stdout={out!r} stderr={err!r}"
        )
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["result"] is False, (
            "remove_claude_md_block() must return False (not raise, not return "
            f"True) when the atomic write itself fails. payload={payload!r}"
        )

        # CLAUDE.md must be left as-is (write failed before any replace) --
        # the function's own docstring/comment says "left as-is" on failure.
        content_after = _read(claude_md)
        assert content_after == canonical_content, (
            "CLAUDE.md must be left untouched when the write fails -- the "
            f"original content must survive. Got {content_after!r}."
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
