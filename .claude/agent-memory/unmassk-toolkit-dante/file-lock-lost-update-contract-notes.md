---
name: file-lock-lost-update-contract-notes
description: git_helpers.file_lock() T1 contract (test_file_lock.py) -- cross-process concurrency test design, sys.platform="win32" import trap, and why sleep-based race widening flaked while marker-based handoff didn't
metadata:
  type: feedback
---

Follow-up to the atomic-write work in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)'s
`fix-atomic-claude-md-write` entries. That fix (temp+os.replace) closed the
crash-mid-write hole but deliberately deferred the LOST-UPDATE race (two
concurrent writers each read-modify-write CLAUDE.md, last os.replace() wins,
the other's change is silently thrown away) -- see
`docs/plan/fix-atomic-claude-md-write.md`'s closing note, "Carrera
lost-update pre-existente diferida como candidato (memo eae0880)". This
session wrote the RED contract for the fix: `git_helpers.file_lock()`, a
cross-platform (`fcntl.flock`/`msvcrt.locking`) exclusive lock wrapping the
whole read-modify-write. Test file:
`unmassk-toolkit/tests/test_file_lock.py`.

**Gotcha: spoofing `sys.platform = "win32"` in a subprocess BEFORE any
stdlib module with a platform-conditional top-level import has been loaded
crashes with an unrelated `ModuleNotFoundError`, not the AttributeError you
meant to test.** `subprocess.py`'s own module body does `if sys.platform ==
"win32": import _winapi`. Setting `sys.platform = "win32"` first, then doing
`from git_helpers import file_lock` (which does `import subprocess` at its
own top level) triggers a FRESH import of `subprocess` under the spoofed
platform, which fails with `ModuleNotFoundError: No module named '_winapi'`
on a real POSIX box -- a completely different error than the one the test
was designed to catch (msvcrt/fcntl branch selection). **Fix**: explicitly
pre-import every stdlib module the module-under-test itself imports at its
own top level (here: `errno, os, signal, subprocess, tempfile, time`,
matching `git_helpers.py`'s own import list) BEFORE flipping `sys.platform`
-- this caches them in `sys.modules` under the real platform, so the
module-under-test's later `import subprocess` is a cache hit and never
re-executes that top-level body. General rule for any "structural,
this-platform-can't-run-it-for-real" test that spoofs `sys.platform`: grep
the target module's own top-level imports first and pre-import all of them.

**Gotcha (bigger, cost a full flaky-test round-trip): a plain ASYMMETRIC
`time.sleep()` race-widener between two real subprocesses is NOT reliably
deterministic, even with a barrier ensuring both start "at the same time".**
First attempt at the without-lock anti-lost-update test used: both writers
wait for a shared `go` file (itself gated behind both writing a `ready`
marker first, so the barrier release doesn't depend on process-launch
jitter), then both immediately `read()`, then writer A sleeps 1.0s before
writing while writer B sleeps 0s. Intent: B finishes almost instantly, A's
later write (based on a stale pre-B-write read) reverts B's change. This
FAILED on the very first live run -- **both** nonces ended up present,
meaning A's own read had somehow landed AFTER B's write had already
completed, despite the "simultaneous" barrier release. Root cause: the
`go`-file poll loop itself has ~10ms granularity (`time.sleep(0.01)` between
checks), and there is no guarantee both processes wake from that poll and
call `open(target).read()` within the same tens-of-milliseconds window --
under real OS scheduling (or a loaded CI box), that skew can exceed B's
entire read+regex+atomic-write time (which includes an `os.fsync()` --
not free). A "forced window" implemented purely as a one-sided sleep is
racing against unbounded scheduler jitter on the OTHER side, which is
exactly the kind of test the "no timing-dependent assertions" rule warns
against, even though the assertion itself wasn't a duration check. **Fix**:
replaced the sleep-only design with an explicit marker-file HANDOFF
(`_writer_code_late` / `_writer_code_early` in the test file): the "late"
writer (A) reads, signals `a_has_read`, then BLOCKS on a `b_has_written`
marker before it's allowed to write at all; the "early" writer (B) BLOCKS on
`a_has_read` before it's allowed to read-modify-write at all, and signals
`b_has_written` only once its own write has genuinely landed. This makes
the ordering (A's read predates B's write; A's write postdates B's write)
100% guaranteed by construction, independent of real wall-clock timing --
zero flakiness across 5 repeated live runs (~0.12s each, no sleep-driven
padding needed at all for correctness). A small `time.sleep()` gated by an
env var (`UNMASSK_TEST_FILELOCK_RACE_WINDOW_SECONDS`) is still layered in
between A's read and its signal, purely as literal fulfillment of "mete una
ventana forzada... env var o pequeño hook" -- it adds realistic margin but
carries none of the correctness burden anymore. **Rule going forward: when
two real subprocesses must race deterministically, prefer an explicit
marker-file handoff over an asymmetric sleep, even behind a barrier** -- a
barrier only synchronizes the START of the race, not what happens a few
milliseconds into it, and that gap is exactly where a "reliable" sleep-based
race quietly stops being reliable.

**Design note: don't reuse the real 5-block `managed_blocks.BLOCKS` /
`upsert_managed_blocks()` for a two-independent-writer concurrency fixture.**
`upsert_managed_blocks()` is a single all-or-nothing transform -- two
writers calling it always compute IDENTICAL output for the same input, so
there is no per-writer divergence to lose. The concurrency test needs two
writers each owning a DIFFERENT slice of the file; built a minimal two-block
CLAUDE.md-style fixture (`BEGIN block-a`/`BEGIN block-b`) instead, still
using the REAL `open_no_follow_symlink(path, "w", atomic=True)` write path
(so the test exercises real production write mechanics, just not the real
block CONTENT-transform, which is already covered elsewhere by
`test_atomic_claude_md_write.py` / `test_managed_blocks.py`).

**With-lock test doesn't need the marker handoff at all -- a plain
asymmetric sleep is fine once a real lock enforces mutual exclusion.**
`file_lock()` genuinely serializes the critical section, so whichever
writer wins the ACQUISITION race runs its entire read+sleep+write while
holding the lock; the other blocks entirely and only reads after the first
releases -- order-independent by construction. Kept `_writer_code_locked()`
(sleep-based) separate from `_writer_code_early`/`_writer_code_late`
(marker-based) rather than forcing one generator to serve both tests.

**Fase 3 (2026-07-25) — Moriarty's 3 T1 regressions on file_lock(), RED
contract in a sibling file (`test_file_lock_regressions.py`, base contract
in `test_file_lock.py` left untouched).** Two gotchas worth remembering for
any future "chmod a directory read-only, then exercise a production path"
regression test in this codebase:

1. **A fixture built via the real installer (`_install(repo)` /
   `git-memory-install.py --auto`) ALREADY leaves a stale `CLAUDE.md.lock`
   on disk as a side effect** — `install_apply.py`'s own write path also
   calls `file_lock()`, and the lock file is never unlinked after use (the
   same anti-pollution behavior under test elsewhere in this same file).
   `os.open(path, os.O_RDWR | os.O_CREAT, 0o600)` on a file that ALREADY
   EXISTS only needs write permission on the FILE itself (owner-writable,
   unaffected by the containing directory's mode) — `O_CREAT` only needs
   directory-write permission when the entry doesn't exist yet. Without
   explicitly deleting any pre-existing `<target>.lock` right before
   chmod'ing the directory read-only, the read-only-directory regression
   silently fails to reproduce at all — confirmed live: the crew hook
   exits 0 even under a chmod-555 repo root if a lock file happens to
   survive from the install step. General rule: whenever a test's fixture
   is built via a real production path that itself might create the exact
   adjacent artifact (lock file, temp file, cache entry) the regression
   needs to be ABSENT for, explicitly clear that artifact right before
   flipping the permission, never assume a fresh-looking fixture is
   fresh at the filesystem level.
2. **Root/ineffective-chmod detection via a live write-probe (not
   `os.geteuid() == 0`) is the more robust skip-guard.** Implemented
   `_make_dir_readonly_or_skip()`: chmod 0o555, then try to actually
   create+delete a probe file inside the directory — if that STILL
   succeeds (root, or a platform where chmod doesn't restrict the owner),
   restore permissions and `pytest.skip()` with an explicit reason instead
   of a false pass. This generalizes past the existing
   `@pytest.mark.skipif(sys.platform == "win32", ...)` convention (see
   `test_atomic_claude_md_write.py::TestPermissionPreservation` and
   `TestChmodFailureWarnsButWriteCompletes`) — kept BOTH here: the win32
   marker skips fast/cheap without ever touching the filesystem, the probe
   catches root-on-POSIX (confirmed via `os.geteuid()==501` locally, so
   never exercised live this session, but written defensively per the
   orchestrator's explicit instruction to guard for it).
3. **A Windows msvcrt deception test doesn't need to nail real Windows
   error-code semantics to prove the LOOP LOGIC is broken.** For the
   "`except OSError: continue` retries forever, even on a PERMANENT
   failure" regression, the fake `msvcrt.locking()` just needs to (a)
   ALWAYS raise the same OSError (any errno — used `errno.EIO`, documented
   as an arbitrary-but-plausible "permanent" choice, explicitly flagged
   UNVERIFIED against real Windows), and (b) count its own calls, raising
   a DISTINCT sentinel exception (`_LoopDetected`) past a generous
   threshold (10000 — cheap since there's no `sleep()` anywhere in the
   retry loop, so even 10k iterations run in milliseconds) so a genuinely
   unbounded implementation fails FAST with a clear message instead of
   actually hanging. Asserting a loose `calls < 10000` (not a tight bound
   like `<= 50`) avoids over-constraining Ultron's exact fix shape (a
   time-based deadline vs. a small fixed retry cap would both satisfy a
   loose bound; a tight one could fail a *correct* fix for the wrong
   reason).

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md).
