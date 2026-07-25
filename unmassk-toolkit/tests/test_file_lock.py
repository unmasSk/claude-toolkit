"""
Acceptance contract (test-first, RED) for git_helpers.file_lock() -- the
cross-platform exclusive file lock that must serialize CLAUDE.md's
managed-block read-modify-write across concurrent writers.

BUG (T1, "the system breaking itself" -- see CLAUDE.md's threat model, and
docs/plan/fix-atomic-claude-md-write.md's own closing note: "Carrera
lost-update pre-existente diferida como candidato (memo eae0880)"):
the atomic-write fix already in this repo
(git_helpers.open_no_follow_symlink(path, "w", atomic=True), tempfile.mkstemp
+ os.replace) prevents a CRASH mid-write from leaving CLAUDE.md empty or
partial. It does NOT prevent a LOST UPDATE: two concurrent writers (two
overlapping boots, or boot + git-memory-upgrade + a manual user edit) each
read the same CLAUDE.md, each modify only their OWN managed block, and
whichever os.replace() lands last silently wins -- the OTHER writer's change
to ITS OWN block is thrown away with no error, no warning, nothing. This is
a plain data-loss bug, not a security concern (no attacker in this
project's threat model).

Confirmed before writing this contract: `grep -rn "fcntl|flock|msvcrt"
unmassk-toolkit/ --include="*.py"` (excluding tests/) = 0 hits. No lock of
any kind exists today.

Proposed API for Ultron (this file assumes and exercises this exact shape --
lib/git_helpers.py, next to open_no_follow_symlink):

    import contextlib

    @contextlib.contextmanager
    def file_lock(target_path: str):
        '''Cross-platform EXCLUSIVE advisory lock serializing a
        read-modify-write against target_path across processes.

        Lock file lives ADJACENT to target_path (e.g. f"{target_path}.lock"),
        never target_path itself -- CLAUDE.md's own content is never touched
        by the lock file's existence.

        Blocks (waits) until the lock is acquired -- no timeout param, no
        polling contract exposed to callers. Always releases on context
        exit, whether the `with` block exits normally OR via an exception
        propagating out of it (the exception itself is never swallowed).

        POSIX: fcntl.flock(fd, fcntl.LOCK_EX) (native blocking exclusive).
        Windows: msvcrt.locking(fd, msvcrt.LK_LOCK, 1) (blocking exclusive
        on a 1-byte region), looped internally past msvcrt's own ~10s
        per-call ceiling until acquired -- msvcrt has no single indefinite-
        block primitive the way flock does.

        `fcntl`/`msvcrt` are imported LAZILY inside their own sys.platform
        branch (same pattern as the rest of this module, see the
        sys.platform == "win32" branches already in this file) -- never at
        module top-level -- so importing git_helpers itself never raises
        ImportError on either platform, and neither primitive is ever
        referenced on the platform it doesn't apply to (no AttributeError).

        Intended call shape at every CLAUDE.md managed-block writer:
            with file_lock(claude_md_path):
                content = <read claude_md_path>
                new_content = upsert_managed_blocks(content)[0]
                with open_no_follow_symlink(claude_md_path, "w", atomic=True) as f:
                    f.write(new_content)
        '''

Run only this file:
    python3 -m pytest unmassk-toolkit/tests/test_file_lock.py -v

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity -- 5 tests covering: mutual exclusion + blocking (1), release on
exception (1), Windows branch selection -- structural only (1), the bug
baseline without a lock (1, expected GREEN today), the fix with the lock (1,
the heart, RED today). NO production code is touched by this file. Only
tests.
"""

import json
import os
import re
import subprocess
import sys
import time
import uuid

from conftest import SOURCE_ROOT

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


# ── Fixture content: a CLAUDE.md-style file with TWO independent managed
# blocks, one per simulated writer. Deliberately NOT the real 5-block
# managed_blocks.BLOCKS (those are a single all-or-nothing upsert with no
# per-writer divergence -- see managed_blocks.upsert_managed_blocks -- so
# two writers calling it always compute IDENTICAL content and could never
# demonstrate a lost update). This fixture mirrors the real shape (BEGIN/
# body/END markers, surrounding user text) at the granularity the race
# actually needs: two independently-owned regions in one file. ─────────────

BEGIN_A = "<!-- BEGIN block-a (managed block) -->"
END_A = "<!-- END block-a -->"
BEGIN_B = "<!-- BEGIN block-b (managed block) -->"
END_B = "<!-- END block-b -->"

INITIAL_CONTENT = (
    "# CLAUDE.md\n\n"
    "Some pre-existing user text that must survive untouched.\n\n"
    f"{BEGIN_A}\n"
    "initial-a\n"
    f"{END_A}\n\n"
    f"{BEGIN_B}\n"
    "initial-b\n"
    f"{END_B}\n"
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _popen_py(code, cwd):
    """Launch `python3 -c code` as a REAL background subprocess (Popen, not
    subprocess.run/run_cmd) -- needed so two writers genuinely run
    concurrently instead of sequentially. Caller owns wait/communicate."""
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
    """Wait for a subprocess with a hard bound. A lock that leaked (never
    released) would otherwise hang this test forever -- turn that into a
    fast, clear failure instead of a suite-wide stall."""
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        out, err = proc.communicate()
        raise AssertionError(
            f"subprocess did not finish within {timeout}s -- likely a "
            f"deadlock (lock acquired but never released). "
            f"partial stdout={out!r} partial stderr={err!r}"
        ) from None
    return proc.returncode, out, err


def _wait_for_files(paths, procs, timeout=15):
    """Deterministic barrier: block until every path in `paths` exists (each
    subprocess writes its own "ready" marker as its first action), so the
    parent only releases the shared GO signal once every writer is
    genuinely alive and waiting -- never dependent on process-launch
    scheduling jitter. On timeout, kills both subprocesses and surfaces
    their stderr so far -- e.g. an AttributeError from a not-yet-implemented
    file_lock shows up directly in the failure message instead of only as
    an opaque "never signaled ready"."""
    deadline = time.time() + timeout
    while not all(os.path.exists(p) for p in paths):
        if time.time() > deadline:
            errs = []
            for p in procs:
                p.kill()
                try:
                    _, err = p.communicate(timeout=5)
                except subprocess.TimeoutExpired:
                    err = "<did not exit even after kill()>"
                errs.append(err)
            raise AssertionError(
                f"subprocess(es) never signaled ready within {timeout}s: "
                f"{paths!r}. subprocess stderr so far: {errs!r}"
            )
        time.sleep(0.01)


def _writer_code_locked(*, target, begin, end, nonce, race_delay, ready_path, go_path, use_lock):
    """Generate the `python -c` source for one concurrent read-modify-write
    writer used by the WITH-LOCK test. Shape mirrors the real production
    pattern already used by lib/install_apply.py::_update_claude_md() /
    hooks/session-start-crew.py: read the full file, transform only the
    writer's own slice, write the full content back via the real
    open_no_follow_symlink(..., atomic=True).

    use_lock is the ONLY variable between the without-lock baseline and the
    with-lock fix test below -- contextlib.nullcontext() is used instead of
    an if/else with hand-maintained indentation, so both code paths are
    byte-identical except for which context manager wraps the critical
    section.

    A plain asymmetric sleep (race_delay) between read and write is safe to
    use HERE (unlike the without-lock baseline below, which needs an
    explicit signal-based handoff -- see its own docstring for why): once
    file_lock() genuinely serializes the critical section, the ORDER in
    which A and B happen to acquire the lock is irrelevant to the outcome
    -- whichever goes second always reads the first's already-committed
    update, no matter how long either one sleeps inside its own turn.
    use_lock=False here exists only as this generator's other caller
    (none currently) would need it -- the without-lock test uses the two
    choreographed generators below instead, specifically because a plain
    sleep-based race is NOT reliably deterministic without a lock (see
    postmortem in this file's git history: an earlier version of this test
    flaked because process-wake jitter on the GO-poll loop let the
    "delayed" writer's read land AFTER the "early" writer's write had
    already completed, silently turning the intended lost-update race into
    an uneventful sequential update).
    """
    if use_lock:
        lock_import = "from git_helpers import file_lock\n"
        lock_ctx = f"file_lock({target!r})"
    else:
        lock_import = "import contextlib\n"
        lock_ctx = "contextlib.nullcontext()"
    return f"""
import sys, os, re, time
sys.path.insert(0, {LIB_DIR!r})
{lock_import}from git_helpers import open_no_follow_symlink

open({ready_path!r}, "w").close()

deadline = time.time() + 15
while not os.path.exists({go_path!r}):
    if time.time() > deadline:
        raise RuntimeError("GO signal never arrived within 15s")
    time.sleep(0.01)

with {lock_ctx}:
    with open({target!r}, encoding="utf-8") as f:
        content = f.read()

    time.sleep({race_delay!r})

    pattern = re.compile(re.escape({begin!r}) + r".*?" + re.escape({end!r}), re.DOTALL)
    new_content = pattern.sub({begin!r} + "\\n" + {nonce!r} + "\\n" + {end!r}, content)

    with open_no_follow_symlink({target!r}, "w", atomic=True) as out:
        out.write(new_content)
"""


_RACE_WINDOW_ENV = "UNMASSK_TEST_FILELOCK_RACE_WINDOW_SECONDS"


def _writer_code_early(*, target, begin, end, nonce, ready_path, go_path, peer_has_read_path, own_written_path):
    """The WITHOUT-LOCK baseline's "early" writer (B): must not write until
    the "late" writer (A, see _writer_code_late) has already completed ITS
    read -- enforced by an explicit marker file, not a sleep. This is what
    guarantees A's eventual write is based on a read that predates B's
    write, regardless of real-world process-scheduling jitter (a plain
    one-sided sleep was tried first and flaked for exactly that reason --
    see _writer_code_locked's docstring). Signals own_written_path once its
    own write has actually landed, so A (which waits on that exact path)
    can never write before B has genuinely finished."""
    return f"""
import sys, os, re, time
sys.path.insert(0, {LIB_DIR!r})
from git_helpers import open_no_follow_symlink

open({ready_path!r}, "w").close()

deadline = time.time() + 15
while not os.path.exists({go_path!r}):
    if time.time() > deadline:
        raise RuntimeError("GO signal never arrived within 15s")
    time.sleep(0.01)

deadline = time.time() + 15
while not os.path.exists({peer_has_read_path!r}):
    if time.time() > deadline:
        raise RuntimeError("peer_has_read marker never arrived within 15s")
    time.sleep(0.01)

with open({target!r}, encoding="utf-8") as f:
    content = f.read()

pattern = re.compile(re.escape({begin!r}) + r".*?" + re.escape({end!r}), re.DOTALL)
new_content = pattern.sub({begin!r} + "\\n" + {nonce!r} + "\\n" + {end!r}, content)

with open_no_follow_symlink({target!r}, "w", atomic=True) as out:
    out.write(new_content)

open({own_written_path!r}, "w").close()
"""


def _writer_code_late(*, target, begin, end, nonce, ready_path, go_path, own_read_path, peer_written_path):
    """The WITHOUT-LOCK baseline's "late" writer (A): reads first (its
    `content` is captured BEFORE the early writer, B, ever writes), signals
    that its read is done (unblocking B, see _writer_code_early), then
    WAITS for B's write to actually land before performing its own write.
    This ordering (A's write strictly after B's write, both based on a
    `content` value strictly before B's write) is what makes the lost
    update 100% deterministic: A's write silently reverts B's change, every
    single run, independent of process-scheduling jitter.

    The env var {_RACE_WINDOW_ENV!r} (Bex's ask: "mete una ventana forzada
    entre read y write... env var o pequeño hook") adds a small, tunable
    real delay between A's read and A signaling "read done" -- purely
    extra realistic margin; the actual correctness guarantee comes from the
    marker-based handoff above, not from this sleep's duration.
    """
    return f"""
import sys, os, re, time
sys.path.insert(0, {LIB_DIR!r})
from git_helpers import open_no_follow_symlink

open({ready_path!r}, "w").close()

deadline = time.time() + 15
while not os.path.exists({go_path!r}):
    if time.time() > deadline:
        raise RuntimeError("GO signal never arrived within 15s")
    time.sleep(0.01)

with open({target!r}, encoding="utf-8") as f:
    content = f.read()

time.sleep(float(os.environ.get({_RACE_WINDOW_ENV!r}, "0.05")))
open({own_read_path!r}, "w").close()

deadline = time.time() + 15
while not os.path.exists({peer_written_path!r}):
    if time.time() > deadline:
        raise RuntimeError("peer_written marker never arrived within 15s")
    time.sleep(0.01)

pattern = re.compile(re.escape({begin!r}) + r".*?" + re.escape({end!r}), re.DOTALL)
new_content = pattern.sub({begin!r} + "\\n" + {nonce!r} + "\\n" + {end!r}, content)

with open_no_follow_symlink({target!r}, "w", atomic=True) as out:
    out.write(new_content)
"""


# ── 1. Helper contract: mutual exclusion + blocking ───────────────────────


class TestFileLockBasicContract:
    def test_second_process_blocks_until_first_releases(self, tmp_path):
        """A second process attempting file_lock() on the SAME target must
        not acquire it until the first process's `with` block exits
        (releases). Proven by the strict ORDER of events in a shared
        append-only log -- never by timing thresholds (no wall-clock
        assertions, no flakiness from scheduler variance).

        Ordering between A and B is itself deterministic (not a race): B
        only starts trying to acquire once A has ALREADY signaled it holds
        the lock (a_holds_lock.ready), so this proves blocking behavior
        unconditionally, not "usually wins the race".

        RED today: git_helpers has no file_lock attribute -- both
        subprocesses crash with AttributeError before writing any event,
        events == [].
        """
        target = str(tmp_path / "CLAUDE.md")
        _write(target, "original content, must be untouched by the lock file\n")
        log_path = str(tmp_path / "events.log")
        _write(log_path, "")
        a_holds_ready = str(tmp_path / "a_holds_lock.ready")

        hold_seconds = 1.0

        code_a = f"""
import sys, time
sys.path.insert(0, {LIB_DIR!r})
from git_helpers import file_lock

with file_lock({target!r}):
    with open({log_path!r}, "a", encoding="utf-8") as f:
        f.write("A_ACQUIRED\\n")
    open({a_holds_ready!r}, "w").close()
    time.sleep({hold_seconds!r})
    with open({log_path!r}, "a", encoding="utf-8") as f:
        f.write("A_RELEASED\\n")
"""
        code_b = f"""
import sys, os, time
sys.path.insert(0, {LIB_DIR!r})
from git_helpers import file_lock

deadline = time.time() + 10
while not os.path.exists({a_holds_ready!r}):
    if time.time() > deadline:
        raise RuntimeError("A never signaled it holds the lock")
    time.sleep(0.01)

with file_lock({target!r}):
    with open({log_path!r}, "a", encoding="utf-8") as f:
        f.write("B_ACQUIRED\\n")
"""
        proc_a = _popen_py(code_a, str(tmp_path))
        proc_b = _popen_py(code_b, str(tmp_path))
        rc_a, out_a, err_a = _wait(proc_a, timeout=20)
        rc_b, out_b, err_b = _wait(proc_b, timeout=20)

        assert rc_a == 0, f"process A must not crash. stdout={out_a!r} stderr={err_a!r}"
        assert rc_b == 0, f"process B must not crash. stdout={out_b!r} stderr={err_b!r}"

        events = [line for line in _read(log_path).splitlines() if line]
        assert events == ["A_ACQUIRED", "A_RELEASED", "B_ACQUIRED"], (
            "B must only acquire the lock AFTER A releases it -- a "
            f"different event order proves B did not actually block: {events!r}"
        )

        assert _read(target) == "original content, must be untouched by the lock file\n", (
            "the lock helper must never write to the target file itself -- "
            "only to its own adjacent lock file."
        )

    def test_lock_released_when_body_exits_via_exception(self, tmp_path):
        """The lock must be released even when the `with` block's body
        raises -- otherwise one crashing writer would permanently deadlock
        every future writer. Proven by reacquiring the SAME lock
        immediately afterward: fcntl flock / msvcrt locking are associated
        with the open file description, not the process, so even a second
        acquisition from the SAME process genuinely exercises release, not
        merely "didn't need to block". Bounded by the subprocess-level
        timeout -- a leaked lock hangs the reacquire past the bound and the
        subprocess is killed, turning a would-be indefinite hang into a
        fast, clear failure.

        RED today: git_helpers has no file_lock attribute -- AttributeError
        before either `with` block is even entered.
        """
        target = str(tmp_path / "CLAUDE.md")
        _write(target, "content\n")

        code = f"""
import sys, json
sys.path.insert(0, {LIB_DIR!r})
from git_helpers import file_lock

raised = False
try:
    with file_lock({target!r}):
        raise RuntimeError("boom -- simulated crash mid read-modify-write")
except RuntimeError:
    raised = True

# If the first lock leaked, this second acquisition hangs forever --
# bounded by the parent test's subprocess timeout below.
reacquired = False
with file_lock({target!r}):
    reacquired = True

print(json.dumps({{"raised": raised, "reacquired": reacquired}}))
"""
        proc = _popen_py(code, str(tmp_path))
        rc, out, err = _wait(proc, timeout=15)
        assert rc == 0, f"stdout={out!r} stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["raised"] is True, (
            "file_lock() must never swallow an exception raised inside its "
            f"`with` block. payload={payload!r}"
        )
        assert payload["reacquired"] is True, (
            "the lock must be released even though the body raised -- a "
            f"second acquisition must succeed. payload={payload!r}"
        )

    def test_windows_branch_uses_msvcrt_not_fcntl_no_attribute_error(self, tmp_path):
        """Structural-only check of the sys.platform == 'win32' branch. This
        machine is not Windows, so REAL msvcrt locking semantics (does it
        actually block a second process, does it actually release) are
        UNVERIFIED here -- CI covers that for real on windows-latest (see
        docs/plan/fix-atomic-claude-md-write.md's cross-platform gate).
        This only proves: (a) file_lock() selects msvcrt.locking() -- not
        fcntl -- when sys.platform is 'win32', and (b) doing so does not
        raise AttributeError/ImportError from referencing a real, unimported
        native module. A FAKE msvcrt is injected into sys.modules for this;
        the real `fcntl` module is left untouched and reachable, so a wrong
        implementation that still called fcntl.flock on "win32" would not
        be masked -- it would just silently pass this specific assertion
        while genuinely misbehaving on real Windows, which is exactly why
        this is flagged as structural, not a substitute for the Windows CI
        run.

        RED today: git_helpers has no file_lock attribute.
        """
        target = str(tmp_path / "CLAUDE.md")
        _write(target, "content\n")
        calls_path = str(tmp_path / "msvcrt_calls.json")

        code = f"""
import sys, types, json
# Pre-import every stdlib module git_helpers.py imports at its own top
# level, BEFORE spoofing sys.platform below -- subprocess.py's own top-level
# body does `if sys.platform == "win32": import _winapi`, so importing it
# for the FIRST time under a spoofed "win32" would crash with
# ModuleNotFoundError: No module named '_winapi' on this real POSIX
# machine. Importing it now (while sys.platform is still the real one)
# caches it in sys.modules, so git_helpers.py's later `import subprocess`
# is a cache hit and never re-executes that top-level body.
import errno, os, signal, subprocess, tempfile, time

fake_msvcrt = types.ModuleType("msvcrt")
calls = []

def _fake_locking(fd, mode, nbytes):
    calls.append({{"mode": mode, "nbytes": nbytes}})

fake_msvcrt.locking = _fake_locking
fake_msvcrt.LK_LOCK = 1
fake_msvcrt.LK_UNLCK = 0
sys.modules["msvcrt"] = fake_msvcrt

sys.platform = "win32"
sys.path.insert(0, {LIB_DIR!r})
from git_helpers import file_lock

with file_lock({target!r}):
    pass

with open({calls_path!r}, "w", encoding="utf-8") as f:
    json.dump(calls, f)
"""
        proc = _popen_py(code, str(tmp_path))
        rc, out, err = _wait(proc, timeout=15)
        assert rc == 0, (
            "the Windows-branch subprocess must not crash (e.g. "
            "AttributeError from referencing fcntl, or msvcrt, on the wrong "
            f"branch). stdout={out!r} stderr={err!r}"
        )

        calls = json.loads(_read(calls_path))
        assert calls, (
            "file_lock() must call msvcrt.locking() when sys.platform is "
            f"'win32' -- got zero calls (wrong branch taken). calls={calls!r}"
        )


# ── 2. Anti-lost-update baseline: TODAY's bug, no file_lock needed ────────


class TestAntiLostUpdateWithoutLock:
    def test_concurrent_writers_without_lock_lose_an_update(self, tmp_path):
        """Baseline characterizing today's bug -- expected to already be
        GREEN, no file_lock() call anywhere in this test. Two real
        subprocesses concurrently read-modify-write the SAME CLAUDE.md-style
        file, each touching only its OWN managed block.

        Determinism comes from an explicit marker-based handoff between the
        two writers (_writer_code_late / _writer_code_early), not from
        timing: A (late) reads first and only signals "read done" after a
        forced env-var-configurable delay; B (early) is gated to never
        write before that signal, and always signals back once its own
        write has genuinely landed; A then waits for THAT signal before
        performing its own write. This guarantees, on every single run
        regardless of scheduler jitter: A's `content` was captured strictly
        before B's write, and A's write happens strictly after B's write --
        so A's write silently reverts block-b to its pre-B-write state
        while still landing its own change to block-a. (An earlier version
        of this test used a plain one-sided sleep instead of this
        marker-based handoff and flaked: process-wake jitter on the
        GO-poll loop occasionally let A's read land AFTER B's write had
        already completed, turning the intended lost-update race into an
        uneventful sequential update -- see _writer_code_locked's
        docstring for the full postmortem.)

        Expected values are never hand-typed: each writer generates its own
        nonce (uuid4), and the assertions read the FINAL file back off disk
        and compare against those exact nonces (§34) -- not an invented
        string.
        """
        target = str(tmp_path / "CLAUDE.md")
        _write(target, INITIAL_CONTENT)
        go_path = str(tmp_path / "go")
        ready_a = str(tmp_path / "ready_a")
        ready_b = str(tmp_path / "ready_b")
        a_has_read = str(tmp_path / "a_has_read")
        b_has_written = str(tmp_path / "b_has_written")

        nonce_a = f"updated-a-{uuid.uuid4().hex}"
        nonce_b = f"updated-b-{uuid.uuid4().hex}"

        code_a = _writer_code_late(
            target=target, begin=BEGIN_A, end=END_A, nonce=nonce_a,
            ready_path=ready_a, go_path=go_path,
            own_read_path=a_has_read, peer_written_path=b_has_written,
        )
        code_b = _writer_code_early(
            target=target, begin=BEGIN_B, end=END_B, nonce=nonce_b,
            ready_path=ready_b, go_path=go_path,
            peer_has_read_path=a_has_read, own_written_path=b_has_written,
        )

        proc_a = _popen_py(code_a, str(tmp_path))
        proc_b = _popen_py(code_b, str(tmp_path))
        _wait_for_files([ready_a, ready_b], [proc_a, proc_b])
        _write(go_path, "")

        rc_a, out_a, err_a = _wait(proc_a, timeout=20)
        rc_b, out_b, err_b = _wait(proc_b, timeout=20)
        assert rc_a == 0, f"writer A must not crash. stdout={out_a!r} stderr={err_a!r}"
        assert rc_b == 0, f"writer B must not crash. stdout={out_b!r} stderr={err_b!r}"

        final_content = _read(target)

        assert nonce_a in final_content, (
            "writer A's own update to its own block must land -- it was "
            f"the last writer chronologically. final_content={final_content!r}"
        )
        assert nonce_b not in final_content, (
            "without a lock, writer B's update must be silently LOST -- "
            "A's later write, based on a stale pre-B-write read, overwrites "
            f"it with no error and no warning. final_content={final_content!r}"
        )
        assert "initial-b" in final_content, (
            "the lost update must cleanly revert block-b to its ORIGINAL "
            f"content (a silent overwrite, not corruption). final_content={final_content!r}"
        )
        assert "Some pre-existing user text" in final_content, (
            "surrounding user text outside both blocks must survive "
            f"untouched throughout. final_content={final_content!r}"
        )


# ── 3. Anti-lost-update fix: the heart of this contract ───────────────────


class TestAntiLostUpdateWithLock:
    def test_concurrent_writers_with_lock_preserve_both_updates(self, tmp_path):
        """The fix: wrapping the exact same two-writer race in file_lock()
        must serialize the read-modify-write so NEITHER update is lost, no
        matter which writer happens to win the lock-acquisition race.
        Identical setup to TestAntiLostUpdateWithoutLock above -- same
        fixture, same asymmetric race-delay technique, same nonce-based
        (never hand-typed) expected values -- with use_lock=True as the
        ONLY difference, proving the LOCK is what changes the outcome, not
        the fixture or the race-widening technique.

        Whichever writer acquires file_lock() first runs its ENTIRE
        read-modify-write (including its own race_delay) while holding the
        lock; the other blocks at acquisition and only reads once the first
        has released -- so it always sees the first writer's update already
        applied. This makes the with-lock outcome order-independent by
        construction: both nonces must be present regardless of which
        writer wins the race to acquire.

        RED today: git_helpers has no file_lock attribute -- both
        subprocesses crash with AttributeError before ever reaching their
        read-modify-write, so neither nonce would ever land.
        """
        target = str(tmp_path / "CLAUDE.md")
        _write(target, INITIAL_CONTENT)
        go_path = str(tmp_path / "go")
        ready_a = str(tmp_path / "ready_a")
        ready_b = str(tmp_path / "ready_b")

        nonce_a = f"updated-a-{uuid.uuid4().hex}"
        nonce_b = f"updated-b-{uuid.uuid4().hex}"

        code_a = _writer_code_locked(
            target=target, begin=BEGIN_A, end=END_A, nonce=nonce_a,
            race_delay=1.0, ready_path=ready_a, go_path=go_path, use_lock=True,
        )
        code_b = _writer_code_locked(
            target=target, begin=BEGIN_B, end=END_B, nonce=nonce_b,
            race_delay=0.0, ready_path=ready_b, go_path=go_path, use_lock=True,
        )

        proc_a = _popen_py(code_a, str(tmp_path))
        proc_b = _popen_py(code_b, str(tmp_path))
        _wait_for_files([ready_a, ready_b], [proc_a, proc_b])
        _write(go_path, "")

        rc_a, out_a, err_a = _wait(proc_a, timeout=20)
        rc_b, out_b, err_b = _wait(proc_b, timeout=20)
        assert rc_a == 0, f"writer A must not crash. stdout={out_a!r} stderr={err_a!r}"
        assert rc_b == 0, f"writer B must not crash. stdout={out_b!r} stderr={err_b!r}"

        final_content = _read(target)

        assert nonce_a in final_content, (
            f"writer A's update must survive under the lock. final_content={final_content!r}"
        )
        assert nonce_b in final_content, (
            "writer B's update must ALSO survive under the lock -- this is "
            "the EXACT update that gets silently lost in the without-lock "
            f"baseline above. final_content={final_content!r}"
        )
        assert "Some pre-existing user text" in final_content, (
            "surrounding user text outside both blocks must survive "
            f"untouched. final_content={final_content!r}"
        )

        # Full precision: neither block is a partial/merged mess -- each
        # contains EXACTLY its own writer's nonce, nothing else, nothing
        # from the other writer bled across the boundary.
        m_a = re.search(re.escape(BEGIN_A) + r"\n(.*?)\n" + re.escape(END_A), final_content, re.DOTALL)
        m_b = re.search(re.escape(BEGIN_B) + r"\n(.*?)\n" + re.escape(END_B), final_content, re.DOTALL)
        assert m_a is not None and m_a.group(1) == nonce_a, (
            f"block-a must equal EXACTLY nonce_a, no more no less. "
            f"got={m_a.group(1) if m_a else None!r} expected={nonce_a!r}"
        )
        assert m_b is not None and m_b.group(1) == nonce_b, (
            f"block-b must equal EXACTLY nonce_b, no more no less. "
            f"got={m_b.group(1) if m_b else None!r} expected={nonce_b!r}"
        )
