---
name: write-work-known-content-none-fallback-contract-notes
description: write_work() known_content=None RED contract -- documented "fall back to disk" contract vs actual "expect absent" implementation, plus the uncaught IsADirectoryError sibling bug
metadata:
  type: feedback
---

Task: pin, in RED, that `lib/memory/notes_commit.py::write_work()` treats a
`None` entry in `known_content` as "this path is expected to have NO
content" (entry fingerprint fixed to `None`), while the only two real
callers (`bin/memory/work.py` lines 73-76, `bin/memory/wip.py` lines 85-88)
document `None` as "couldn't read this path right now (missing, permission)
-- `write_work()` then falls back to its own disk read for that path, same
behavior as before this fix, not a regression." Two tests added to
`unmassk-toolkit/tests/memory/test_notes.py` (not a new file -- `write_work()`
is already tested at lib level directly in this file, confirmed by grep
before adding anything).

**Root cause, confirmed by reading the code, not assumed:** `write_work()`
builds `entry_fingerprints` from `known_content` when it's not `None`
(overall param), setting each per-path entry to `None` whenever that path's
individual `known_content[i]` is `None`. The later comparison
(`_content_fingerprint(path) != entry_fingerprints[path]`) reads the REAL
disk state -- for a path that exists, this is never `None`, so it mismatches
the fixed `None` entry and the path lands in `changed_since_entry`, producing
the false "otro proceso lo escribio" rejection even in a single-process call
with nobody else touching anything. The fix that matches the documented
contract is: when `known_content[i]` is `None`, the entry fingerprint for
that path should be computed by *reading the disk right there* (i.e. the
same thing `_content_fingerprint(path)` already does), not fixed to `None`.

**Checked before writing anything (per task's explicit ask): does `None` have
a legitimate "expect absent" meaning anywhere in production?** Grepped
`known_content` across the whole repo outside `tests/` -- the only two real
callers are `work.py`/`wip.py`, both documenting the exact same "couldn't
read, fall back" semantics, word for word. No other caller, no doc in
`docs/memoria-v2/` (`PIEZAS.md`, `CALENDARIO.md`) assigns `None` any other
meaning. Confirmed: no legitimate "absent" use exists today -- the contract
tests are correct as written, not a misunderstanding on my part.

**Second, sibling bug found while reading `_content_fingerprint()`
(notes_commit.py lines ~296-300):** it only catches `FileNotFoundError`. A
directory path (e.g. a `-- src/` typo) makes `path.read_bytes()` raise
`IsADirectoryError` in the callers -- caught by their `except OSError`,
appended as `None` to `known_content` -- same code path as the fallback bug
above. Inside `write_work()`, `_content_fingerprint(dir_path)` then calls
`open(dir_path, "rb")`, which raises `IsADirectoryError` uncaught, escaping
`write_work()` entirely instead of returning a clean `WriteResult(ok=False,
...)`. Confirmed live: pytest shows the raw `IsADirectoryError` traceback
originating at `notes_commit.py:297`. `PIEZAS.md` Sec.10's common contract
for the ten scripts says none of them ever prints a raw stack trace --
`work.py`'s own top-level `except Exception` in `__main__` happens to catch
this at the CLI layer and print a clean one-liner, but the *library*
function `write_work()` itself still lets the exception escape, which is
what the task asked to fix at this level (my test calls `notes.write_work()`
directly, not through the CLI wrapper).

**No documented exact error text for the directory case** -- the task said
not to invent one if the contract doesn't fix it, so the second test asserts
behavior only: no uncaught exception escapes `write_work()` (asserted via
`try`/`except Exception: pytest.fail(...)`, which turns an ERROR into a
readable FAILED with the real exception type/message in the assertion text,
rather than letting pytest report a bare traceback), `result.ok is False`,
and `result.git_error` is non-empty (a real cause, not silence).

**Real-repo technique reused from [[write-work-missing-lock-contract-notes]]
and [[deuda27-write-work-two-process-race-notes]]:** both new tests use the
real `tmp_repo` git fixture, `_cwd(root)`, and `run_git()` -- no mocking of
git or of `write_work()` itself. First test asserts `result.ok`, the real
commit count delta via `git rev-list --count HEAD`, and the real committed
content via `git show HEAD:<name>` -- never trusts what `write_work()`
claims about itself.

Both confirmed RED for the right reason (not import/fixture noise): full
`tests/memory` suite re-run after adding these two -- 283 passed, 3 failed
(the 2 new RED here + 1 pre-existing, unrelated failure in
`test_rule_script.py::TestSimilarExistingRuleIsWarnedBeforeAdding` --
confirmed out of scope, different file, different subsystem, not touched).

See also: [[write-work-missing-lock-contract-notes]],
[[deuda27-write-work-two-process-race-notes]],
[[mutation-check-collision-incident-ids]].
