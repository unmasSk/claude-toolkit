---
name: trailer-content-validation
description: Wrapper-side Memo:/Remember: trailer CONTENT validation in bin/git-memory-commit.py — pattern and enum promotion
metadata:
  type: project
---

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
