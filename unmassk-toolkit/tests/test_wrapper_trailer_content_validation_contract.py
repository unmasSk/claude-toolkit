"""
Acceptance contract (TEST-FIRST, RED before Ultron) — move trailer CONTENT
validation for `Memo:`/`Remember:` into the producer, `bin/git-memory-commit.py`.

Today `git-memory-commit.py` (the wrapper every commit is supposed to go
through) does not validate the CONTENT of a `--trailer "Memo=..."` or
`--trailer "Remember=..."` value at all before committing. The only content
validation that exists anywhere in this codebase lives in
`hooks/pre-validate-commit-trailers.py` / `hooks/post-validate-commit-trailers.py`
(`validate_trailers()`), which are Claude-Code PreToolUse/PostToolUse hooks —
they intercept the raw Bash `command` string, not the wrapper's own
in-process logic, and (per this project's `unmassk-toolkit-python-test-conventions.md`
memory) the "use the wrapper script" gate blocks any literal `git commit`
command unconditionally before trailer content is ever inspected, and the
hooks only fire at all when driven through the Claude Code harness. A plain
invocation of the wrapper (subprocess, or a human, or a test) never goes
through them — confirmed empirically below.

Verified RED baseline (2026-07-25, run manually against the current script
before writing this file): all of the following commit successfully today
(rc=0, commit created) even though every one is invalid content:
  - `memo` with `Memo=notarealcategory - some description` (category outside
    `MEMO_CATEGORIES`)
  - `memo` with `Memo=deadend` (no ` - ` separator, no description at all)
  - `memo` with `Memo=deadend - ` (empty description) — note this case is
    NOT even caught by the EXISTING hook's `validate_trailers()`, which only
    checks `len(parts) < 2 or parts[0] not in MEMO_CATEGORIES` and never
    inspects whether the description half is empty. This confirms the
    wrapper contract below is strictly NEW behavior, not just relocating
    existing logic.
  - `remember` with `Remember=bogus - some text` (category outside the
    hook's `("user", "claude")` enum)

Target (Ultron implements AFTER this file is RED): before building/creating
the commit, the wrapper validates every `Memo:`/`Remember:` trailer's
content and fails NOISY (exit != 0, clear stderr message, NO commit
created) on invalid content. Valid categories:
  - Memo: `lib/constants.py::MEMO_CATEGORIES` (single source of truth,
    imported below — never hardcoded here).
  - Remember: `lib/constants.py::REMEMBER_CATEGORIES` (real named constant,
    added by Ultron after this contract was first written — imported below
    alongside `MEMO_CATEGORIES`, same pattern for both).

Threat model note (per this project's CLAUDE.md): this is the system
against itself (a legitimate-looking-but-malformed trailer silently
corrupting memory content), not an external attacker. No malicious-input
cases.

Technique: black-box subprocess invocation of the wrapper in a scratch git
repo (`conftest.run_script`/`git_cmd`, same shape as
`test_git_memory_commit_subject_length.py`), asserting on (exit code, commit
count) — NOT a direct import of a validation function, because Ultron has
not written one yet; there is nothing to import. `run_cmd`'s `cwd` argument
pins every git/script invocation to the scratch repo explicitly (never the
real toolkit repo).

RED today (must fail for the stated reason):
    - TestMemoCategoryValidationFailClosed::test_invalid_category_rejected_no_commit
    - TestMemoCategoryValidationFailClosed::test_invalid_category_error_names_category_and_lists_valid
    - TestMemoCategoryValidationFailClosed::test_missing_separator_rejected_no_commit
    - TestMemoCategoryValidationFailClosed::test_empty_description_rejected_no_commit
    - TestRememberCategoryValidationFailClosed::test_invalid_category_rejected_no_commit
    - TestRememberCategoryValidationFailClosed::test_missing_separator_rejected_no_commit
    - TestRememberCategoryValidationFailClosed::test_empty_description_rejected_no_commit

GREEN controls today, must stay GREEN after the fix (no regression):
    - TestMemoCategoryHappyPathUnaffected::test_valid_category_accepted[*]
    - TestRememberCategoryHappyPathUnaffected::test_valid_category_accepted[*]

REGRESSION (Cerberus finding, 2026-07-25): `_validate_trailer_content()`
above checks the RAW `--trailer` value, but `build_commit_message()`
commits the SANITIZED value (`sanitize_trailer_value()` turns every
control byte into a space, then strips). A description made ENTIRELY of
control bytes (e.g. `\x1b\x1b\x1b`) is non-empty as a raw string --
`str.strip()` does not touch ESC -- so the raw-value check passes it as a
valid "category - description", while the sanitized value that actually
lands in the commit is bare `"preference -"` with NO description: silent,
permanent loss of the memory content. Ultron is moving the validation to
run on the sanitized value (fail closed instead). Until that fix lands
these are RED (rc=0, commit created, empty description silently
committed); GREEN once the wrapper validates post-sanitize content:
    - TestMemoDescriptionControlByteOnlySaneoRegression::test_control_byte_only_description_rejected_no_commit
    - TestRememberDescriptionControlByteOnlySaneoRegression::test_control_byte_only_description_rejected_no_commit
  (test_control_byte_only_description_sanitizes_to_empty is an anti-vacuity
  probe, not part of the RED/GREEN contract -- it must pass unconditionally,
  today and after the fix, since it only exercises sanitize_trailer_value().)
"""

import os

from conftest import BIN_DIR, LIB_DIR, git_cmd, run_cmd, run_script

import sys
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from constants import MEMO_CATEGORIES, REMEMBER_CATEGORIES  # noqa: E402  (sys.path mutated above)
from parsing import sanitize_trailer_value  # noqa: E402  (sys.path mutated above)

COMMIT_SCRIPT = os.path.join(BIN_DIR, "git-memory-commit.py")


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit_count(repo):
    rc, out, _ = run_cmd(["git", "rev-list", "--count", "HEAD"], repo)
    return int(out.strip())


# ── Memo: content validation ────────────────────────────────────────────

class TestMemoCategoryValidationFailClosed:
    """[RED] Invalid Memo: trailer content must be rejected by the wrapper
    itself, before any commit is created."""

    def test_invalid_category_rejected_no_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "test", "garbage category", "--trailer",
             "Memo=notarealcategory - some description"],
        )
        assert rc != 0, f"commit with an out-of-enum Memo category must fail closed: rc={rc} out={out!r} err={err!r}"
        assert _commit_count(repo) == before, "no commit should have been created for an invalid Memo category"

    def test_invalid_category_error_names_category_and_lists_valid(self, tmp_path):
        repo = _make_repo(tmp_path)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "test", "garbage category", "--trailer",
             "Memo=notarealcategory - some description"],
        )
        assert "notarealcategory" in err, f"error should name the invalid category that was passed: {err!r}"
        assert any(c in err for c in sorted(MEMO_CATEGORIES)), (
            f"error should list at least one of the valid categories {sorted(MEMO_CATEGORIES)!r}: {err!r}"
        )

    def test_missing_separator_rejected_no_commit(self, tmp_path):
        """`Memo=deadend` with no ` - description` at all — malformed format."""
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "test", "no separator", "--trailer", "Memo=deadend"],
        )
        assert rc != 0, f"Memo value with no ' - ' separator must fail closed: rc={rc} out={out!r} err={err!r}"
        assert _commit_count(repo) == before, "no commit should have been created for a malformed Memo value"

    def test_empty_description_rejected_no_commit(self, tmp_path):
        """`Memo=deadend - ` (valid category, empty description) — must also
        be rejected. Not even the existing hook's validate_trailers() checks
        this today (confirmed by reading its code); this is a strictly new
        gate."""
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "test", "empty description", "--trailer", "Memo=deadend - "],
        )
        assert rc != 0, f"Memo value with an empty description must fail closed: rc={rc} out={out!r} err={err!r}"
        assert _commit_count(repo) == before, "no commit should have been created for an empty Memo description"


class TestMemoCategoryHappyPathUnaffected:
    """[GREEN control] Every real category, with a real description, must
    keep committing successfully — both today and after the fix.

    Parametrized off the REAL MEMO_CATEGORIES set (never a hardcoded literal
    list) so this test automatically tracks the constant's current contents.
    """

    def test_valid_category_accepted(self, tmp_path):
        for category in sorted(MEMO_CATEGORIES):
            repo = _make_repo(tmp_path, name=f"repo_{category}")
            before = _commit_count(repo)
            rc, out, err = run_script(
                COMMIT_SCRIPT, repo,
                ["memo", "test", f"valid {category}", "--trailer",
                 f"Memo={category} - descripcion valida para {category}"],
            )
            assert rc == 0, f"valid Memo category {category!r} must still be accepted: err={err!r}"
            assert _commit_count(repo) == before + 1, f"a commit should have been created for valid category {category!r}"


class TestMemoDescriptionControlByteOnlySaneoRegression:
    """[REGRESSION — Cerberus] The category/separator check above validates
    the RAW `--trailer` value, before sanitize_trailer_value() runs. A
    description made ENTIRELY of control bytes (e.g. \\x1b\\x1b\\x1b) is
    non-empty as a raw string -- str.strip() does not touch ESC -- so
    `_validate_trailer_content()` sees a valid "category - description"
    shape and lets it through. But build_commit_message() commits the
    SANITIZED value (sanitize_trailer_value() converts every control byte
    to a space, then strips the result), and an all-control-byte
    description sanitizes down to nothing: the trailer actually written to
    git is bare "Memo: preference -" with NO description at all -- silent,
    permanent loss of the memory content, never surfaced as an error.

    Without Ultron's fix (validate the SANITIZED value, not the raw one)
    `test_control_byte_only_description_rejected_no_commit` is RED: rc=0
    and a commit IS created carrying the empty "Memo: preference -"
    trailer (confirmed live against the current script before writing
    this). GREEN once the wrapper validates post-sanitize content and
    fails closed instead.
    """

    def test_control_byte_only_description_sanitizes_to_empty(self):
        """Anti-vacuity: prove the raw description used below is not
        accidentally a valid non-empty description once sanitized -- if
        this failed, the rejection test below would pass for the wrong
        (trivial) reason."""
        raw_description = "\x1b\x1b\x1b"
        assert raw_description.strip(), (
            "raw control bytes must look non-empty pre-sanitize via str.strip() "
            "-- that gap is exactly what the raw-value validator misses"
        )
        sanitized = sanitize_trailer_value(f"preference - {raw_description}")
        assert sanitized == "preference -", (
            f"expected the control-byte description to sanitize away to nothing, got {sanitized!r}"
        )

    def test_control_byte_only_description_rejected_no_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "test", "control byte only description", "--trailer",
             "Memo=preference - \x1b\x1b\x1b"],
        )
        assert rc != 0, (
            "a Memo description made only of control bytes sanitizes to empty "
            f"and must fail closed: rc={rc} out={out!r} err={err!r}"
        )
        assert _commit_count(repo) == before, (
            "no commit should have been created -- without the fix this silently "
            "commits a bare 'Memo: preference -' trailer with no description"
        )


# ── Remember: content validation ────────────────────────────────────────

class TestRememberCategoryValidationFailClosed:
    """[RED] Invalid Remember: trailer content must be rejected by the
    wrapper itself, before any commit is created — same shape as Memo:."""

    def test_invalid_category_rejected_no_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["remember", "test", "garbage category", "--trailer",
             "Remember=bogus - some text"],
        )
        assert rc != 0, f"commit with an out-of-enum Remember category must fail closed: rc={rc} out={out!r} err={err!r}"
        assert _commit_count(repo) == before, "no commit should have been created for an invalid Remember category"

    def test_missing_separator_rejected_no_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["remember", "test", "no separator", "--trailer", "Remember=user"],
        )
        assert rc != 0, f"Remember value with no ' - ' separator must fail closed: rc={rc} out={out!r} err={err!r}"
        assert _commit_count(repo) == before, "no commit should have been created for a malformed Remember value"

    def test_empty_description_rejected_no_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["remember", "test", "empty description", "--trailer", "Remember=user - "],
        )
        assert rc != 0, f"Remember value with an empty description must fail closed: rc={rc} out={out!r} err={err!r}"
        assert _commit_count(repo) == before, "no commit should have been created for an empty Remember description"


class TestRememberCategoryHappyPathUnaffected:
    """[GREEN control] Both real categories, with a real description, must
    keep committing successfully — both today and after the fix."""

    def test_valid_category_accepted(self, tmp_path):
        for category in REMEMBER_CATEGORIES:
            repo = _make_repo(tmp_path, name=f"repo_{category}")
            before = _commit_count(repo)
            rc, out, err = run_script(
                COMMIT_SCRIPT, repo,
                ["remember", "test", f"valid {category}", "--trailer",
                 f"Remember={category} - texto de prueba valido"],
            )
            assert rc == 0, f"valid Remember category {category!r} must still be accepted: err={err!r}"
            assert _commit_count(repo) == before + 1, f"a commit should have been created for valid category {category!r}"


class TestRememberDescriptionControlByteOnlySaneoRegression:
    """[REGRESSION — Cerberus] Same failure mode as
    TestMemoDescriptionControlByteOnlySaneoRegression above, for Remember:
    trailers -- the raw-value validator lets an all-control-byte
    description through, but the sanitized value committed to git is bare
    "Remember: user -" with no description. See that class's docstring for
    the full mechanism; not repeating the anti-vacuity probe here since it
    only exercises sanitize_trailer_value(), which is not Memo/Remember
    specific."""

    def test_control_byte_only_description_rejected_no_commit(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["remember", "test", "control byte only description", "--trailer",
             "Remember=user - \x1b\x1b\x1b"],
        )
        assert rc != 0, (
            "a Remember description made only of control bytes sanitizes to empty "
            f"and must fail closed: rc={rc} out={out!r} err={err!r}"
        )
        assert _commit_count(repo) == before, (
            "no commit should have been created -- without the fix this silently "
            "commits a bare 'Remember: user -' trailer with no description"
        )
