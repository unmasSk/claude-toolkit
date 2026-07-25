---
name: wrapper-trailer-content-validation-contract-notes
description: Acceptance contract (RED, test-first) moving Memo:/Remember: trailer content validation into bin/git-memory-commit.py itself, not just the PreToolUse hooks
metadata:
  type: project
---

Task (2026-07-25): write a RED acceptance contract for a new feature — move
`Memo:`/`Remember:` trailer CONTENT validation (category + " - description"
format) into the producer itself, `bin/git-memory-commit.py`, so it fails
closed regardless of how the script is invoked.

**Key finding: the wrapper has ZERO trailer-content validation today, even
though `hooks/pre-validate-commit-trailers.py`/`post-validate-commit-trailers.py`
already implement `validate_trailers()` with (most of) this exact logic.**
Those hooks are Claude-Code PreToolUse/PostToolUse hooks that intercept the
raw Bash `command` string — they never fire on a plain subprocess call to
the wrapper (confirmed empirically: `git-memory-commit.py memo test "..."
--trailer "Memo=notarealcategory - x"` commits successfully, rc=0, in a
scratch repo with no hooks installed). This is a real, separate contract,
not a duplicate of existing hook coverage — reuses the sibling test file's
established distinction (see
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)'s
"as_claude gotcha").

**Second finding, more important: the existing hook's `validate_trailers()`
does NOT catch an empty description either.** Its gate is `len(parts) < 2 or
parts[0].strip() not in MEMO_CATEGORIES` — a value like `"deadend - "` has
`parts = ["deadend", ""]`, `len==2`, category valid → hook says zero errors.
Verified live (scratch commit) that today's wrapper happily commits `Memo:
deadend -` (trailing dash, no description) with rc=0. So the "empty
description must be rejected" case in this contract is strictly NEW
behavior beyond anything already implemented anywhere in the codebase —
worth flagging explicitly in a RED-contract report so nobody assumes it's
just "port the hook's check into the wrapper."

**Remember: category enum has no `lib/constants.py` source of truth.**
`MEMO_CATEGORIES` is a real named constant; the Remember equivalent
(`("user", "claude")`) only exists as an inline literal inside
`hooks/pre-validate-commit-trailers.py::validate_trailers()`. Reproduced as
a local test tuple with a comment explaining there's nothing importable to
reuse — flagged for Ultron/Alexandria as a possible follow-up (promote it to
`constants.py` as `REMEMBER_CATEGORIES` the same way `MEMO_CATEGORIES`
already is), but out of scope to fix here since this is a test-only pass.

**File:** `unmassk-toolkit/tests/test_wrapper_trailer_content_validation_contract.py`
— 4 Memo RED tests (invalid category rejected + names category/lists valid,
missing separator rejected, empty description rejected), 3 Remember RED
tests (same 3 shapes, no message-content assertion — task only mandated
message-content checking for Memo), 1 Memo GREEN control parametrized over
the REAL `MEMO_CATEGORIES` set, 1 Remember GREEN control over `("user",
"claude")`. All 7 RED tests confirmed failing for the right reason (rc=0,
commit created) against the current script; both GREEN controls pass today.

**Technique: black-box subprocess only, no direct import** — unlike the
sibling `test_trailer_newline_regression.py` (imports `build_commit_message`
directly via `importlib.util.spec_from_file_location`), this contract can't
import a validation function because Ultron hasn't written one yet. Used
`conftest.run_script`/`git_cmd` (same shape as
`test_git_memory_commit_subject_length.py`) with `tmp_path`-scoped scratch
repos — `run_cmd`'s `cwd=` param pins every git/script call explicitly, so
nothing lands in the real toolkit repo even though the harness resets cwd
between Bash tool calls.

See also [deadend-memo-round-trip-contract-notes](deadend-memo-round-trip-contract-notes.md)
and [trailer-newline-collapse-regression-notes](trailer-newline-collapse-regression-notes.md)
for sibling Memo/trailer contract tests in the same file family, and
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md)
for the `_make_repo`/`run_script`/`as_claude` conventions reused here.
