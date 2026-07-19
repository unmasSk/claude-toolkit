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

import json
import os
import sys

import pytest

from conftest import SOURCE_ROOT, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

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


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
