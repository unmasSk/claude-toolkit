"""
Constants contract — new Memo category "deadend".

Feature: a "dead-end memory" loop for the toolkit. Part of enabling it was a
new Memo category: `Memo: deadend - <text>` must validate cleanly, the same
way `preference|requirement|antipattern|stack` already do.

`lib/constants.py::MEMO_CATEGORIES` is the single source of truth and now
includes "deadend" — this file's only remaining job is to guard that fact
(a regression here means the whole dead-end memory feature silently stops
being a valid category anywhere it's checked).

RETIRED (2026-07-25): this file used to also exercise
`hooks/pre-validate-commit-trailers.py` / `hooks/post-validate-commit-trailers.py`'s
`validate_trailers()` directly (14 tests: TestMemoCategoryDeadendAcceptance,
TestExistingMemoCategoriesStillAccepted, TestGarbageMemoCategoryStillRejected)
to prove "deadend"/existing categories are accepted and garbage categories
are rejected by the hooks. That validation layer was dead code in the
wrapper's path (the hooks only fire on a raw Bash `command` string via the
Claude Code harness, never on a plain wrapper invocation) and has since been
retired: post-validate-commit-trailers.py was deleted outright, and
pre-validate-commit-trailers.py was trimmed to keep ONLY the "use the
wrapper script" block (validate_trailers() no longer exists in either
file).

Confirmed equivalent coverage now lives in
tests/test_wrapper_trailer_content_validation_contract.py, which validates
trailer CONTENT in the real producer (bin/git-memory-commit.py):
  - TestMemoCategoryHappyPathUnaffected::test_valid_category_accepted
    parametrizes over the REAL `MEMO_CATEGORIES` set (which already
    includes "deadend"), covering exactly what
    TestMemoCategoryDeadendAcceptance + TestExistingMemoCategoriesStillAccepted
    used to cover (deadend acceptance + all other categories still
    accepted) — no case lost.
  - TestMemoCategoryValidationFailClosed::test_invalid_category_rejected_no_commit
    + test_invalid_category_error_names_category_and_lists_valid cover an
    out-of-enum category being rejected (using "notarealcategory" instead
    of "fake" — same class of case, and the error-message assertion there
    is strictly stronger: it names the invalid category AND lists a valid
    one, vs. the old test's bare "Memo" substring check) — no case lost,
    nothing ported.
"""

import sys

from conftest import LIB_DIR

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from constants import MEMO_CATEGORIES  # noqa: E402  (sys.path mutated above)


class TestConstantsMemoCategoriesIncludesDeadend:
    """The single source of truth (lib/constants.py) must list "deadend"."""

    def test_deadend_in_memo_categories(self):
        assert "deadend" in MEMO_CATEGORIES, (
            "lib/constants.py::MEMO_CATEGORIES must include 'deadend' for the "
            "dead-end memory loop feature; current set: "
            f"{sorted(MEMO_CATEGORIES)!r}"
        )
