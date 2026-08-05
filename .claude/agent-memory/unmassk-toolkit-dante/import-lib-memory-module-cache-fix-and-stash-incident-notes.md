---
name: import-lib-memory-module-cache-fix-and-stash-incident-notes
description: unmassk-memory (v2) fix for import_lib_memory_module() returning a NEW module/class per call (dataclass identity bug hit twice, test_format.py + test_indexes.py) — content-hash cache, verified live; PLUS a mid-session git stash incident and its recovery
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/conftest.py`, explicit one-off
permission to touch only this file (feat/memoria-v2, 2026-08-02, same
day as [zones-contract-notes](zones-contract-notes.md) and
[indexes-contract-and-shared-dir-incident-notes](indexes-contract-and-shared-dir-incident-notes.md)).

**The bug:** `import_lib_memory_module()` never cached anything — every
call built a brand-new module object via `spec_from_file_location` +
`exec_module()`, even for the exact same file. A frozen dataclass's
generated `__eq__` checks `self.__class__ is other.__class__` before
comparing fields, so two independently-loaded copies of `model.py`
produced two different `Zone`/`Note`/`IndexLine` classes — `result ==
expected` failed even against a fully correct implementation. Two
colleagues hit this independently and both worked around it the same
way (compare fields one-by-one instead of `==`): `test_format.py`'s
`_assert_fields_match` and `test_indexes.py`'s `_assert_fields_match`/
`_assert_lines_match` (documented in
[indexes-contract-and-shared-dir-incident-notes](indexes-contract-and-shared-dir-incident-notes.md)).
Two independent workarounds for the same root cause is the signal the
orchestrator read correctly as "fix the floor."

**The fix:** a module-level `_MODULE_CACHE = {}` dict keyed by
`module_name`, storing `(content_hash, module)`. On each call: open the
target file, sha256 its bytes, compare against the cached hash for
that name. Same hash → return the cached module object (same classes,
`==` works normally). Different or absent hash → load fresh via the
existing `spec_from_file_location`/`exec_module` path and update the
cache entry.

**Why content hash, not `os.path.getmtime()`:** mtime resolution is
1 second on some filesystems; a test that rewrites the same module
within that window (exactly the "colleague reloads mid-session" case
the task asked to protect) could keep a stale mtime and serve the old
cached object. A content hash has no timing assumption at all — same
bytes always means same object, different bytes (regardless of how
fast the rewrite happened) always forces a reload. No flaky-test risk
(this repo's Hard Rules ban timing-dependent assertions; the same
principle applies to caching, not just assertions).

**The three conditions, verified:**

1. **`FileNotFoundError` stays clean.** The file is opened
   (`open(path, "rb")`) to compute the hash BEFORE touching the cache
   or building any spec — a genuinely missing module raises the exact
   same `FileNotFoundError`/`[Errno 2]` it always did, just one call
   frame earlier (from the explicit `open()` instead of from inside
   `exec_module()`'s internal `get_data()`). Confirmed live against 4
   real currently-missing modules in the shared `lib/memory/` dir
   across two separate runs (`rejection.py`, `indexes.py`, `gitcmd.py`
   before colleagues finished them; `validator.py` still missing at
   verification time) — same exception type, same message shape, both
   before and after the fix.
2. **Nothing sticks between tests.** A scratchpad probe (never written
   into `lib/memory/` — see the hard rule below) replicated the exact
   mechanism against a throwaway `model.py`: loaded once, rewrote the
   file with a different `Zone` shape (added a field), loaded again —
   the second load returned a DIFFERENT module object with the NEW
   field, not the stale cached one. A third load with the file
   unchanged from the second write returned the SAME object as the
   second load (cache stability once content stops moving).
3. **Rest of the toolkit suite doesn't move.** Measured by temporarily
   swapping `conftest.py` between the pre-fix and post-fix content
   in-place (git stash was tried first and caused a real incident, see
   below — do NOT use it for this kind of before/after diff again) and
   running both back-to-back to minimize the window for concurrent
   colleagues' commits to skew the count: `unmassk-toolkit/tests
   --collect-only -q` → **832 tests collected, both before and after**.
   `unmassk-toolkit/tests/memory -q` → **41 passed, 11 errors, both
   before and after** (the 11 errors are colleagues' own in-progress
   RED contracts for `validator.py`, unrelated to this fix).

**Colleagues' workarounds confirmed still passing, untouched:**
`pytest unmassk-toolkit/tests/memory/test_format.py
unmassk-toolkit/tests/memory/test_indexes.py -v` → 9/9 passed.
`_assert_fields_match`/`_assert_lines_match` still present in both
files (grepped, not removed) — correctly not removed, since the task
said they're not mine to touch and they still work. They are now
*redundant* in the narrow sense that a plain `==` would also work
post-fix (confirmed live: loading the real `lib/memory/model.py`
twice via `import_lib_memory_module("model")` now returns
`model_a is model_b == True`), but harmless to leave — same
"defensive even after the root cause is fixed" call already made once
before for `zones.py`'s Row 5 in
[zones-contract-notes](zones-contract-notes.md). Flagged, not
touched — that decision belongs to the orchestrator, not to me.

**INCIDENT during verification — read this before ever using `git
stash` for a quick before/after measurement in a live multi-agent
session again.** Tried `git stash push --keep-index -- <file> -m
"<message>"` to snapshot the pre-fix conftest.py for a clean A/B
measurement. The `-m` flag was placed AFTER the `--` pathspec
terminator, so git tried to treat `-m` and the message string as
pathspecs, they matched nothing, and the push silently produced NO new
stash entry. The immediately following `git stash pop` therefore
popped whatever WAS already on the stash stack — a stale, unrelated
entry from 2026-07-09 (`"pre-pull 2026-07-09: borrador local CHANGELOG
#55 (superseded por release 1.18.0 remota)"`), sitting there for
weeks, nothing to do with this session. That old stash only ever
touched `CHANGELOG.md` (confirmed via `git stash show --stat
stash@{0}`, 1 file, 10 insertions) — it collided with the real,
current `CHANGELOG.md` (which has since diverged completely, up to a
real v1.25.0 entry) and produced a genuine 3-way merge conflict
(`UU CHANGELOG.md`, `<<<<<<< Updated upstream` / `>>>>>>> Stashed
changes` markers). Because of the conflict, git correctly did NOT drop
the stash — `stash@{0}` was still intact and listed afterward, so
nothing was lost, only the working tree got polluted.

**Recovery, verified clean:** `git stash show --stat` first to confirm
scope (only CHANGELOG.md, not something wider); `git checkout --ours
-- CHANGELOG.md` to restore the pre-pop content (the "ours" side of a
stash-pop 3-way merge is the working tree state immediately before the
stash was applied — exactly what's needed to undo it); `git add
CHANGELOG.md` to clear the unmerged (`UU`) index state (bookkeeping
only, not a commit — the task's "no commitear" rule is about `git
commit`, not clearing a conflict's index stage). Verified after: zero
conflict markers left in the file, `git status --porcelain --
CHANGELOG.md` empty (file back to matching HEAD, which is what it was
before the mistake — it had no independent uncommitted change of its
own), `stash@{0}` still present and untouched in `git stash list` (not
mine to drop — it predates this session and isn't related to this
task). The ~110 OTHER modified/untracked files visible in the full
`git status` throughout this incident were **not** caused by the
stash pop — confirmed via `git stash show --stat` showing the popped
stash only ever touched one file, and independently by the task's own
briefing describing a live multi-agent session where many colleagues
are simultaneously rewriting `lib/memory/*.py`, `tests/memory/*.py`,
`docs/memoria-v2/*.md`, agent definitions, hooks, etc. — legitimate
concurrent WIP, not something I touched.

**How to apply — general rule going forward, any project:** never use
`git stash` for an ad-hoc before/after code comparison in a repo with
other live uncommitted work (own or a teammate's), especially in a
multi-agent session where a `-m` typo or any other stash-command
mistake can silently pop an unrelated, unowned stash instead of the
one just (attempted-but-failed-to-be) pushed. Prefer a manual
save-aside-and-restore of the specific file's content (`cp` to
scratchpad, `Write`/edit in place, restore from the scratchpad copy)
— zero git state involved, zero risk of touching a stash or branch
that isn't the current task's own. If `git stash` is ever genuinely
needed, always run `git stash list` immediately before AND after to
confirm exactly one new entry appeared and it is the intended one —
never chain `push` and `pop` in the same breath without that check in
between.

Verification commands used (matching the task's literal ask):
`python3 -m pytest unmassk-toolkit/tests/memory -v` → 41 passed, 11
errors (colleagues' unrelated in-progress RED contracts).
`python3 -m pytest unmassk-toolkit/tests --collect-only -q` → 832
tests collected, unchanged before/after the fix. Only file touched in
the repo (besides this memory file and the incident recovery of
`CHANGELOG.md` back to its original state): `unmassk-toolkit/tests/
memory/conftest.py` (100 insertions, `git diff --stat` confirmed). No
mutation-check write ever touched the real `lib/memory/` — the RED
(FileNotFoundError) and identity/reload probes ran from the session
scratchpad against a throwaway `model.py`, per the standing hard rule
in [mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md).

Reference: [zones-contract-notes](zones-contract-notes.md),
[indexes-contract-and-shared-dir-incident-notes](indexes-contract-and-shared-dir-incident-notes.md),
[mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md),
[memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)
