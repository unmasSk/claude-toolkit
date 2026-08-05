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

**Follow-up (2026-07-25, same day): raw-vs-sanitized validation gap
(Cerberus finding) + duplication cleanup.** `_validate_trailer_content()`
was checking the RAW `--trailer` value, but `build_commit_message()`
commits the SANITIZED one (`sanitize_trailer_value()` turns every control
byte into a space then strips). A description made only of control bytes
(e.g. `\x1b\x1b\x1b`) is non-empty under raw `str.strip()` (ESC isn't
whitespace to Python) but collapses to `""` once sanitized — so
`"Memo=preference - \x1b\x1b\x1b"` passed the raw check and silently
committed a bare `"Memo: preference -"` trailer with no description.
Verified live before writing the regression test: `git log -1 --format=%B`
showed exactly that empty trailer, rc=0. Added
`TestMemoDescriptionControlByteOnlySaneoRegression` (+ an anti-vacuity
probe asserting the raw value truly sanitizes to `"preference -"`, so the
rejection test can't pass for a trivial reason) and
`TestRememberDescriptionControlByteOnlySaneoRegression` (no probe repeat —
same mechanism, not Memo/Remember-specific) to the same file. **Ultron
landed the fix (validate `sanitize_trailer_value(value)`, not raw
`value`) WHILE this test-writing was in progress** — both regression
tests came up GREEN on first run, no RED phase observed by me (confirmed
via `git diff` on the wrapper: `sanitized = sanitize_trailer_value(value)`
now feeds the `" - "` split). Also fixed the duplication Cerberus flagged:
the file's local `REMEMBER_CATEGORIES = ("user", "claude")` stand-in
(dated from when there was no importable source of truth) is now a real
import `from constants import MEMO_CATEGORIES, REMEMBER_CATEGORIES` —
`lib/constants.py` had grown the constant in the meantime. Only the test
file changed; zero production edits by me.

**Follow-up (2026-07-25, same day): cleanup pass after the hook retirement
was finalized.** Once this wrapper contract was confirmed as the real
owner of Memo/Remember content validation, Ultron retired the now-dead
hook-side `validate_trailers()` for good: `post-validate-commit-trailers.py`
deleted outright, `pre-validate-commit-trailers.py` trimmed to keep ONLY
the "use the wrapper script" block gate (no `validate_trailers()` at all
anymore). That orphaned 24 tests across 4 files that had exercised the
retired hook logic — cleanup technique worth reusing next time a
validation layer gets consolidated like this:
1. **Before deleting any orphaned test, map it to its replacement.** Every
   one of the 14 tests in `test_memo_category_deadend_contract.py`
   (deadend acceptance, existing-category acceptance, garbage-category
   rejection, all parametrized `[pre]`/`[post]`) had an exact behavioral
   equivalent already GREEN in this file's
   `TestMemoCategoryHappyPathUnaffected`/`TestMemoCategoryValidationFailClosed`
   classes (the happy-path test already parametrizes over the real
   `MEMO_CATEGORIES` set, so it automatically covers "deadend" once that
   category exists — nothing needed porting). Do this mapping explicitly
   before deleting, not after — it's the only way to tell "safe to delete"
   from "would silently drop coverage."
2. **Removing a class can orphan its private helpers.** In
   `test_crown_retraction.py`, deleting `TestRetractCrownRequiresWhy` (the
   4 tests exercising the retired Why-on-Retract-Crown validation) also
   orphaned `_pre_hook_errors`/`_post_hook_errors`/`_run_pre_hook_full`/
   `_load_module` and the `PRE_HOOK_PATH`/`POST_HOOK_PATH` constants — none
   of them were used anywhere else in the file. Grep every helper the
   doomed class calls before deleting; a helper used ONLY by dead tests is
   itself dead and should go with them, or it silently rots as unreachable
   code.
3. **A hook-invoking test doesn't always mean the test was exercising real
   validation.** `test_integration.py::test_session_with_trailers` passed
   `msg_file` (a file path) as a positional CLI arg to a hook that only
   ever reads JSON from stdin — with no `input_text=`, stdin is empty,
   `json.load()` raises `JSONDecodeError`, caught, `sys.exit(0)`. So the
   surviving pre-hook half of that test was already only proving fail-open
   on malformed input, not "accepts commits with valid trailers" as its
   docstring claimed — a pre-existing test-quality gap, left alone (out of
   scope: only the dead post-hook invocation was removed, per the "don't
   fix bugs found while testing, report them" rule).
4. **Production-code residue found, NOT fixed (report-only, per scope):**
   `bin/git-memory-uninstall.py:56` and `lib/install_inspect.py:34` still
   list `"hooks/post-validate-commit-trailers.py"` in their hook
   inventories even though the file was deleted — neither was mentioned in
   the "already applied" production changes for this retirement. Flagged
   for Ultron/Cerberus, not touched (test-only pass).

**Restore (2026-08-04, DEUDA.md #16): the file and the function it tested
were both deleted together** (same commit removed `_validate_trailer_content()`
and this test file), leaving the description-emptiness half of the bug with
no red flag. Re-created from scratch, not from git history (`.pyc` was the
only surviving artifact, source was gone). Two things had genuinely changed
since 2026-07-25 and had to be re-verified from the current code, not
assumed from this file's older notes above:

1. **`MEMO_CATEGORIES`/`REMEMBER_CATEGORIES` no longer exist anywhere in
   the repo** (`grep -rn "MEMO_CATEGORIES\|REMEMBER_CATEGORIES"` across the
   whole tree: zero hits). `lib/constants.py::VALID_KEYS` never held them —
   the only place either concept ever lived was the inline literal inside
   the now-deleted `pre-validate-commit-trailers.py::validate_trailers()`.
   So the task's "category invalid → rebota" case has nothing left to
   validate against and was dropped entirely, per this session's explicit
   instruction: if the category concept is gone, write only the
   empty-description case. Confirmed via real git history that the
   `"category - description"` *shape* itself is still very much alive
   today (e.g. `Remember: claude - Bex las pidio...` in this repo's own
   recent commits) — only the enum to validate the category word against
   is gone, not the format.

2. **This project's threat model changed underneath the original 2026-07-25
   version of this file.** That version's most elaborate regression test
   (`TestMemoDescriptionControlByteOnlySaneoRegression`) used a
   control-byte-only description (`"preference - \x1b\x1b\x1b"`) to prove
   the "empty after saneo" gap — CLAUDE.md now states explicitly this repo
   has **no external attacker**, and control-byte/hostile-input tests are
   surplus. Re-derived a *non-hostile* way to exercise the same
   "looks non-empty raw, empty after `sanitize_trailer_value()`" nuance:
   an ordinary embedded newline from a paste (`"deadend - \n   "` — a
   blank second line), since `sanitize_trailer_value()` folds `\n` to a
   space and its own trailing `.strip()` collapses the result to `""`.
   Same mechanism the control-byte version proved, mundane input instead
   of an attack — matches this project's own reframing of §34/Argus
   material as "the system against itself," not against a hostile actor.

**Confirmed RED for the right reason, live 2026-08-04**: all 3 new tests
failed with `rc=0` and a real commit created (`git rev-list --count HEAD`
incremented) — `Memo=deadend -` and `Remember=claude -` both commit
cleanly today with zero validation, and the embedded-newline variant does
too. Both `[GUARDA]` control tests (`Memo=deadend - una descripcion real...`,
same for Remember) passed on the same run, proving the RED failures aren't
an artifact of a broken script invocation.

**Convention followed:** mirrored `test_git_memory_commit_subject_length.py`'s
`_make_repo`/`_commit_count` shape exactly (no explicit `git config
user.name/email` — conftest's `_DEFAULT_GIT_IDENTITY_ENV` fallback covers
it), used `run_script`/`git_cmd`/`run_cmd` from `conftest.py`, subprocess-only
(no import of the not-yet-written validation function). One operational
gotcha hit while researching: `pre-validate-commit-trailers.py`'s own
regex (`r"\bgit\b.*\bcommit\b"`) matches the literal substring
`"git-memory-commit"` typed inside a `grep` pattern from an agent Bash call
(since `-` is a non-word boundary, "git" and "commit" both read as
separate whole words) — this is the SAME false-positive class DEUDA.md B16
already documents for the word "merge". Workaround: only grep for the
`.py`-suffixed literal `"git-memory-commit.py"` so the hook's own
`uses_wrapper` check (which looks for that exact substring) short-circuits
before the word-boundary regex ever runs.
