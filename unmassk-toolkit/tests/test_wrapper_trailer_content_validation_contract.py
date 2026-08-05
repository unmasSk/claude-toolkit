"""
RED acceptance contract (test-first, DEUDA.md #16): restore trailer-content
validation to `bin/git-memory-commit.py` for the *description-emptiness*
half of the retired `_validate_trailer_content()`.

History: `_validate_trailer_content()` left the wrapper in the same commit
(`578177a`, on top of `e2dafbe`) that retired the Memo/Remember category
enum. The plan (`PLAN-CONSTRUCCION.md` §5.3) only authorized removing the
category check — but that one function did two unrelated things, and only
one of them was ever approved to go:

1. validate the category against a known list — AUTHORIZED, correctly
   removed.
2. reject a trailer whose description is empty once
   `sanitize_trailer_value()` has run on it — NEVER authorized, lost as a
   side effect of removing (1).

This wrapper is still the live write path for every `Memo:`/`Remember:`
entry until the v2 memory system replaces it (CLAUDE.md, "el sistema viejo
sigue siendo la vía de escritura viva"). Today it commits
`Memo: deadend -` (trailing dash, no description at all) with rc=0 — no
gate at all, verified live before writing this file (see below).

**Category checking is intentionally NOT covered by this file.** Verified
by reading the current source before writing a single test:
`grep -rn "MEMO_CATEGORIES\\|REMEMBER_CATEGORIES"` across the whole repo
returns nothing — `lib/constants.py` (the single source of truth for
trailer keys, `VALID_KEYS`) has never held either constant. The old
`MEMO_CATEGORIES` enum and the `("user", "claude")` Remember tuple only
ever existed as inline literals inside the now-deleted
`hooks/pre-validate-commit-trailers.py::validate_trailers()` (confirmed
retired per this same file's git history and the sibling regression file
`test_trailer_newline_regression.py`'s retirement note). There is no
importable category list left to validate against, and per this
project's Hard Rules ("no hardcoded values" — never duplicate a category
list as string literals with nothing to import it from), inventing one
here would be exactly the anti-pattern this rule exists to prevent. So:
only case 2 (empty description after saneo) is covered — case 1 does not
exist as a testable concept in the current codebase.

**No hostile/control-byte input** (per this project's CLAUDE.md: "No hay
atacante externo... nada de bytes de control ni de entradas hostiles.
Esto es un descuido de uso normal."). The two failure shapes below are
both plausible everyday slips, not attacks:
  - forgetting to type a description at all after the trailing dash
    (`"deadend -"`) — the exact shape reproduced live in DEUDA.md #16 and
    in the deleted test this file replaces.
  - pasting text that leaves only a blank line after the dash
    (`"deadend - \\n   "`) — looks non-empty as a raw string (it has
    length), but `sanitize_trailer_value()` collapses the embedded
    newline to a space and its own trailing `.strip()` reduces the whole
    thing to nothing. This is the "tras sanear" (post-sanitize) half of
    the bug DEUDA.md #16 names explicitly, produced with an ordinary
    stray newline from a paste — not a control byte.

Technique: black-box subprocess only (`run_script`), same shape as the
sibling `test_git_memory_commit_subject_length.py` — no direct import of
a not-yet-written validation function. "No commit was created" is proven
by comparing `git rev-list --count HEAD` before and after against a real
temporary repository, not by trusting the exit code alone (two
independently-written signals, per this project's round-trip rule).

[GUARDA] (must still pass after the fix lands, so a naive
"always reject" implementation cannot satisfy this contract):
    - test_memo_with_real_description_still_commits
    - test_remember_with_real_description_still_commits
"""

import os

from conftest import BIN_DIR, git_cmd, run_cmd, run_script

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


class TestMemoEmptyDescriptionAfterSaneoFailsClosed:
    """A Memo trailer whose description is empty once sanitized must be
    rejected: non-zero exit AND no commit created."""

    def test_bare_trailing_dash_no_description_is_rejected(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)

        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "toolkit-bin", "probe", "--trailer", "Memo=deadend -"],
        )

        assert rc != 0, (
            f"a Memo trailer with no description at all must be rejected: "
            f"rc={rc}, out={out!r}, err={err!r}"
        )
        assert err.strip() != "", "a rejection must fail loud, not silently exit non-zero"
        assert _commit_count(repo) == before, (
            "no commit must be created when the description is empty — "
            f"count was {before}, now {_commit_count(repo)}"
        )

    def test_description_that_is_only_a_blank_line_is_rejected_after_saneo(self, tmp_path):
        # Raw value LOOKS non-empty (it has length: a newline plus spaces),
        # but sanitize_trailer_value() folds the embedded "\n" to a space
        # and its trailing .strip() reduces the whole description to "" --
        # the exact "tras sanear" gap DEUDA.md #16 names. An ordinary
        # newline from pasted text, not a control byte.
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)

        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "toolkit-bin", "probe", "--trailer", "Memo=deadend - \n   "],
        )

        assert rc != 0, (
            f"a description that sanitizes down to empty must be rejected: "
            f"rc={rc}, out={out!r}, err={err!r}"
        )
        assert err.strip() != "", "a rejection must fail loud, not silently exit non-zero"
        assert _commit_count(repo) == before, (
            "no commit must be created when the description sanitizes to empty — "
            f"count was {before}, now {_commit_count(repo)}"
        )

    def test_memo_with_real_description_still_commits(self, tmp_path):
        """[GUARDA] A Memo trailer with an actual description must keep
        working -- this is what stops an "always reject" implementation
        from trivially satisfying the two tests above."""
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)

        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["memo", "toolkit-bin", "probe",
             "--trailer", "Memo=deadend - una descripcion real y no vacia"],
        )

        assert rc == 0, f"a real description must be accepted: rc={rc}, out={out!r}, err={err!r}"
        assert _commit_count(repo) == before + 1


class TestRememberEmptyDescriptionAfterSaneoFailsClosed:
    """Same defect, same fix, on the Remember trailer -- real commits in
    this repo's own history use the identical 'claude - description' /
    'user - description' shape (e.g. `Remember: claude - ...`), so the
    same emptiness gap applies here too."""

    def test_bare_trailing_dash_no_description_is_rejected(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)

        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["remember", "toolkit-bin", "probe", "--trailer", "Remember=claude -"],
        )

        assert rc != 0, (
            f"a Remember trailer with no description at all must be rejected: "
            f"rc={rc}, out={out!r}, err={err!r}"
        )
        assert err.strip() != "", "a rejection must fail loud, not silently exit non-zero"
        assert _commit_count(repo) == before, (
            "no commit must be created when the description is empty — "
            f"count was {before}, now {_commit_count(repo)}"
        )

    def test_remember_with_real_description_still_commits(self, tmp_path):
        """[GUARDA] mirrors test_memo_with_real_description_still_commits."""
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)

        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["remember", "toolkit-bin", "probe",
             "--trailer", "Remember=claude - una descripcion real y no vacia"],
        )

        assert rc == 0, f"a real description must be accepted: rc={rc}, out={out!r}, err={err!r}"
        assert _commit_count(repo) == before + 1
