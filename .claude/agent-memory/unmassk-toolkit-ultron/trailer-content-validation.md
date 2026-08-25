---
name: trailer-content-validation
description: RETIRED SUBJECT (confirmed 2026-08-25) — the whole Memo:/Remember: trailer commit system (bin/git-memory-commit.py, hooks/pre-validate-commit-trailers.py, hooks/post-validate-commit-trailers.py, MEMO_CATEGORIES/REMEMBER_CATEGORIES) is gone, replaced by gitmem's own note-type commits ([note_id][zone]). Kept only for the general content-validation/enum-promotion pattern.
metadata:
  type: project
---

**RETIRED SUBJECT.** Every file and constant this entry names
(`bin/git-memory-commit.py`, `hooks/pre-validate-commit-trailers.py`,
`hooks/post-validate-commit-trailers.py`, `MEMO_CATEGORIES`,
`REMEMBER_CATEGORIES`) is gone — confirmed 2026-08-25 via `grep -rn
"MEMO_CATEGORIES\|REMEMBER_CATEGORIES"` across `lib/`/`bin/`/`hooks/`
(zero hits) and file-existence checks (all three files absent). The v1
`Memo:`/`Remember:` git-trailer commit mechanism this file documents was
replaced whole by the gitmem/memoria-v2 system (`bin/gitmem`,
`bin/memory/*.py`, `lib/memory/`) — notes have their own types
(D/M/R/Q/X/I/B) and commit format, documented in the `memoria-v2-*.md`
files in this same directory, not trailers on an otherwise-plain commit.
Kept below only for the general, still-transferable pattern (validate
producer-side content before the commit, not just downstream in a
PreToolUse hook; promote a hardcoded literal to a shared constant) — no
current code to point at.

## Producer-side content validation moved into the wrapper (2026-07-25)

`unmassk-toolkit/bin/git-memory-commit.py` did NOT validate the CONTENT of
`--trailer "Memo=..."` / `--trailer "Remember=..."` values before creating
a commit. The only content check that existed lived in
`hooks/pre-validate-commit-trailers.py::validate_trailers()` — a Claude-Code
PreToolUse hook that intercepts the raw Bash `git commit` string. It never
fires for: (a) the wrapper's own in-process trailer building, (b) a plain
subprocess/human invocation of the wrapper, (c) any test. So a malformed
`Memo:`/`Remember:` (bad category, missing ` - ` separator, or empty
description) committed successfully every time the wrapper was called
directly — silent memory corruption per this project's threat model (system
against itself, not an attacker).

**Fix pattern** — `_validate_trailer_content(key, value) -> str | None` +
`_check_trailer_content(trailers: list[str]) -> None` in
`bin/git-memory-commit.py`, called in `main()` right after path validation
and BEFORE `_process_trailers()` (which has side effects — `gh issue
create` for `Next:`) and before `build_commit_message()`/`_do_commit()`.
Fail-closed: `sys.exit(2)` with a stderr message naming the invalid
category and listing valid ones (`"|".join(sorted(categories))`) — no
commit is created. Table-driven: `_TRAILER_CONTENT_ENUMS = {"Memo":
MEMO_CATEGORIES, "Remember": REMEMBER_CATEGORIES}`, both from
`lib/constants.py` (never hardcoded — the pytest contract parametrizes off
the same import to prevent drift). Reused `sanitize_trailer_value()`
(`lib/parsing.py`) for the reflected value/category in the error message —
already imported in this file for the co-author sanitizer.

**Enum promotion**: `REMEMBER_CATEGORIES = {"user", "claude"}` used to only
exist as an inline literal `("user", "claude")` inside
`hooks/pre-validate-commit-trailers.py::validate_trailers()` — no
importable source of truth. Promoted to `lib/constants.py` next to
`MEMO_CATEGORIES`; the hook's one literal-tuple comparison
(`parts[0].strip() not in (...)`) was swapped to import and use the new
constant — hook's error-message text and surrounding logic left untouched
(scope: data promotion only, not a hook rewrite). `hooks/post-validate-commit-trailers.py`
has a `Memo:` check but no `Remember:` check — nothing to touch there.

**Test technique** (`tests/test_wrapper_trailer_content_validation_contract.py`):
black-box subprocess invocation of the wrapper in a scratch git repo
(`run_script`/`git_cmd` from conftest), asserting on `(exit code, commit
count)` — not a direct import of the validation function, because at RED
time nothing existed to import. Same shape as
`test_git_memory_commit_subject_length.py`.

**Empty-description edge case**: `"deadend - "` (valid category, trailing
space, no description) is caught by treating "missing separator" and
"empty description after strip" as the SAME error branch
(`len(parts) < 2 or not parts[1].strip()`) — simpler than two branches and
sufficient since no test asserts a distinct message for that case.

## Description-emptiness half restored without the category enum (2026-08-04, DEUDA.md #16)

The whole `_validate_trailer_content()` function (category enum + empty-
description) was retired by mistake in 578177a/e2dafbe — the plan only
authorized dropping the category check, but both checks lived in one
function and left together. `MEMO_CATEGORIES`/`REMEMBER_CATEGORIES` are
gone from the codebase entirely (confirmed by repo-wide grep before
writing anything) and `lib/constants.py::VALID_KEYS` never held them — so
there is nothing to re-import and the category half is **not** restorable
without inventing a hardcoded list, which the project's own rule forbids.
Fix: re-added only the description-emptiness half, renamed the two
functions' bodies but kept their names identical to the historical ones so
future greps still find them. `_TRAILER_CONTENT_KEYS = {"Memo",
"Remember"}` (a set, not an enum-value dict this time — no
`_TRAILER_CONTENT_ENUMS` needed since there's nothing to look up per key
beyond "does this key get content-checked at all"). Logic:
`sanitized.partition(" - ")` — if no `" - "` separator or the description
part is empty after `.strip()`, reject. This one `partition` call also
correctly rejects a bare trailing dash with no trailing space (`"deadend
-"`, no space after the `-`) because `" - "` (3 chars) never matches — no
special-casing needed for that shape vs. the "collapses to empty after
sanitize" shape; both fall through the same branch. `sys.exit(2)`,
stderr names the trailer key and the sanitized value. Wired into `main()`
right before `build_commit_message()` (no `_process_trailers()`/`gh issue
create` step exists in this file to worry about ordering against —
that's a different piece).

Once the wrapper (`bin/git-memory-commit.py`) owned content validation
end-to-end (see above), the hook-layer trailer/type validation became dead
weight per Bilbo's map: `hooks/pre-validate-commit-trailers.py`'s
`validate_trailers()`/`parse_commit_type()` branch was only reachable via
`extract_commit_message()`, which requires the literal string `'git commit'`
in the Bash command — the wrapper never produces that (it calls
`subprocess.run(["git", "commit", ...])`, invisible to the Bash-matcher
hook), so the branch was unreachable for Claude and warn-only for humans.
`hooks/post-validate-commit-trailers.py`'s `"git commit" in command` gate
was 100% dead for the same reason (git subprocess is invisible to the
Bash-matcher PostToolUse hook). Fix: trimmed `pre-validate-commit-trailers.py`
down to stdin read + the direct-`git commit`/`git log` block (the ONLY live
enforcement — forces wrapper usage), removed now-unused imports
(`constants`, `git_helpers.run_git`, most of `parsing`, `colors.YELLOW`) —
kept only `colors.RED/RESET`. `git rm`'d `post-validate-commit-trailers.py`
entirely and removed its `PostToolUse` block from `hooks/hooks.json`.

**Hidden 4th-file break found only by running the full suite**:
`bin/git-memory-doctor.py`'s `EXPECTED_HOOKS` list (health-check registry,
distinct from `OLD_HOOK_FILES` in `bin/git-memory-uninstall.py` /
`lib/install_inspect.py` — those are v1-installer-leftover cleanup lists,
unaffected by this) still named the deleted file, so `git memory doctor`
would permanently report a false "missing hook" — caught concretely by
`tests/test_integration.py::test_upgrade_creates_backup` failing with
`'error' != 'error'` / `"5/6 in cache — missing: post-validate-commit-trailers"`.
Fixed by removing that one line from `EXPECTED_HOOKS`. Rule: when deleting a
hook file, grep for every "list of files this project expects to exist"
registry (health checks, install/uninstall manifests) — `git rm` alone does
not surface these; only a full-suite test run does.

Full-suite result after the change: 24 failed, 1144 passed, 2 skipped (no
unrelated pre-existing flake — e.g. the usual `test_release.py` 9-failure
noise — surfaced in this run; all 24 trace directly to this diff). Orphaned
tests, all Dante's lane, not fixed here: `tests/test_post_validate_commit_trailers.py`
(all 4, file gone), `tests/test_crown_retraction.py` (4, exercised post-hook's
now-removed `validate_trailers()`), `tests/test_memo_category_deadend_contract.py`
(14, parametrized over both hooks' now-removed/deleted `validate_trailers()`),
`tests/test_integration.py::test_session_with_trailers` (invokes the deleted
post-hook directly), `tests/test_drift.py::test_post_hook_exit_code` (same —
invokes the deleted post-hook path directly, gets a launcher "no such file"
rc=2 instead of the expected fail-open rc=0).
