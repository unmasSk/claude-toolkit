---
name: gitcmd-lock-cleanup
description: flock()+unlink() lock-file cleanup race in gitcmd.py::file_lock() — inode-recheck-on-acquire pattern, POSIX vs Windows delete order, and how the fix was proven non-vacuous
metadata:
  type: project
---

`unmassk-toolkit/lib/memory/gitcmd.py::file_lock()` used to leave its
`<path>.lock` file behind forever (DEUDA.md punto 9 — the eight stray
`.lock` files next to the eight indices in `.claude/project-memory/`).
A prior agent looked at it and correctly refused to just add
`os.unlink()` on release: `flock()` locks an **open file description**
tied to an inode, not a path. Deleting the path while still holding the
lock lets a process that arrives right after create a *new* inode at
the same path and lock it **uncontended** while the first process is
still "inside" — two processes in the critical section at once.

**The fix (implemented 2026-08-03):** on **acquire**, after `flock()`
returns, compare `(st_dev, st_ino)` of the just-opened `fd`
(`os.fstat`) against `(st_dev, st_ino)` of the current dentry at that
path (`os.stat`, catching `FileNotFoundError`/`OSError` as "no match").
Mismatch = "ghost inode" (someone deleted, maybe recreated, the file
while this process was blocked in `flock()`) → release, close, reopen,
retry. Only a match means this process is the *live* holder. See
`_acquire_live_lock()`/`_release_live_lock()`/`_same_file()` in
gitcmd.py.

**Delete order is platform-dependent, and that's a deliberate,
documented split, not an inconsistency:**
- POSIX: unlink **before** releasing the flock. Safe because only the
  current holder ever reaches the release path for a given lock_path
  (mutual exclusion), so nothing else can be mid-unlink at the same
  time.
- Windows: unlink **after** releasing and closing the fd. `os.open()`
  doesn't request `FILE_SHARE_DELETE`, so `os.unlink()` on an
  open file raises `PermissionError` in practice on Windows. Safety
  doesn't depend on this ordering (the acquire-side inode check is
  what prevents double-entry on both platforms) — only cleanliness
  does: under real contention, Windows can leave the `.lock` around
  more often before it disappears. Declared gap, not hidden: this repo
  has no Windows CI to verify it live.

**Proving the test isn't vacuous, without touching production or the
real repo:** copied the *pre-fix* `gitcmd.py` into the scratchpad
(`old_gitcmd_check/gitcmd_old.py`) with the "naive" fix a lesser
implementation would ship — unlink **after** release, no inode check —
and ran the exact same multi-process race driver against it standalone
(no pytest, no repo). Result: 5/6 processes hit `MUTEX_BREACH` on
**every one of 15 rounds**. The real fix (with the inode recheck) ran
clean 10/10 with zero breaches and zero leftover `.lock` files. This is
the same "write a fake/broken version, confirm the test catches it,
discard it" discipline already used for test-emptiness checks
elsewhere in this project, applied to a *real* prior version instead of
a fabricated stub — and it must run in the scratchpad, never inside
`lib/memory/` (see the HARD RULE at the top of MEMORY.md and the
2026-08-02 incident in [lessons.md](lessons.md)).

**Test pattern for a flock+unlink race:** it must be **real processes**
(`subprocess.Popen`), not threads — the race is specifically about the
path's dentry disappearing while a *different process's* `fd` still
references the old inode; a thread in the same process doesn't
reproduce that half of it. Use a "busy marker" file created/removed
inside the critical section as the mutual-exclusion witness (if a
process finds the marker already there, that's a live double-entry —
print a sentinel and exit non-zero), run many processes × many
iterations so the exact unlink-vs-reopen timing window gets crossed on
its own, and assert both "no double-entry ever" **and** "no `.lock`
left on disk" in the same test — that's the two halves of this task in
one assertion pair.
