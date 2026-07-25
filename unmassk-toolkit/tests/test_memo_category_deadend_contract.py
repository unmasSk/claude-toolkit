"""
Acceptance contract (TEST-FIRST, RED before Ultron) — new Memo category "deadend".

Feature: a "dead-end memory" loop for the toolkit. Part of enabling it is a new
Memo category: `Memo: deadend - <text>` must validate cleanly, the same way
`preference|requirement|antipattern|stack` already do.

Today `lib/constants.py::MEMO_CATEGORIES` is
`{"preference", "requirement", "antipattern", "stack"}` — "deadend" is absent.
Both `hooks/pre-validate-commit-trailers.py` and
`hooks/post-validate-commit-trailers.py` have their own `validate_trailers()`
function with the identical gate:

    parts = trailers["Memo"].split(" - ", 1)
    if len(parts) < 2 or parts[0].strip() not in MEMO_CATEGORIES:
        errors.append(...)  # "Invalid Memo format" / "Memo: (invalid format ...)"

So a commit with `Memo: deadend - ...` is REJECTED by both hooks today.

Threat model note (per this project's CLAUDE.md): there is no external
attacker here — this only tests "the system against itself" (a real,
legitimate Memo category being wrongly rejected/accepted). No malicious-input
tests.

Direct-import technique (see
unmassk-toolkit-python-test-conventions.md): `validate_trailers()` is called
directly via `importlib.util.spec_from_file_location`, not via subprocess —
`check_hook_msg(..., as_claude=True)` cannot exercise trailer-content logic
because the "use the wrapper script" gate blocks any literal `git commit`
command unconditionally, before trailer validation ever runs.

RED contract (must fail today, for the right reason — "deadend" rejected):
    - TestConstantsMemoCategoriesIncludesDeadend::test_deadend_in_memo_categories
    - TestMemoCategoryDeadendAcceptance::test_deadend_category_accepted[pre]
    - TestMemoCategoryDeadendAcceptance::test_deadend_category_accepted[post]

GREEN controls (must pass before AND after the fix — no regression):
    - TestExistingMemoCategoriesStillAccepted::* (preference/requirement/antipattern/stack)
    - TestGarbageMemoCategoryStillRejected::* (a made-up category, e.g. "fake")
"""

import importlib.util
import os

import pytest

from conftest import PRE_HOOK, POST_HOOK, LIB_DIR

import sys
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from constants import MEMO_CATEGORIES  # noqa: E402  (sys.path mutated above)


# ── Direct-import helper (hyphenated filenames aren't import-able) ────────

def _load_hook_module(name, path):
    """Load a hyphenated hooks/*.py file as an importable module object.

    Fresh load every call (no sys.modules caching) so pre- and post- hook
    loads never collide, and no test can leak a monkeypatched attribute into
    another test via a shared module instance.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_HOOKS = [
    pytest.param(PRE_HOOK, "pre", id="pre"),
    pytest.param(POST_HOOK, "post", id="post"),
]


# ── Test A (RED today): "deadend" must be accepted ─────────────────────────

class TestConstantsMemoCategoriesIncludesDeadend:
    """The single source of truth (lib/constants.py) must list "deadend"."""

    def test_deadend_in_memo_categories(self):
        assert "deadend" in MEMO_CATEGORIES, (
            "lib/constants.py::MEMO_CATEGORIES must include 'deadend' for the "
            "dead-end memory loop feature; current set: "
            f"{sorted(MEMO_CATEGORIES)!r}"
        )


class TestMemoCategoryDeadendAcceptance:
    """`Memo: deadend - ...` must validate with zero errors, in BOTH hooks.

    branch="" (no issue reference in branch name) so the only trailer under
    test is Memo — no Issue: requirement is pulled in as noise.
    """

    @pytest.mark.parametrize("hook_path,hook_label", _HOOKS)
    def test_deadend_category_accepted(self, hook_path, hook_label):
        mod = _load_hook_module(f"_deadend_accept_{hook_label}", hook_path)
        trailers = {"Memo": "deadend - probamos X, no funciono, no repetir"}

        errors = mod.validate_trailers("memo", trailers, branch="")

        assert errors == [], (
            f"[{hook_label}-hook] 'Memo: deadend - ...' must produce zero "
            f"validation errors once 'deadend' is added to MEMO_CATEGORIES; "
            f"got {errors!r}"
        )


# ── GREEN controls: existing categories still accepted ─────────────────────

class TestExistingMemoCategoriesStillAccepted:
    """The 4 categories that validate today must keep validating.

    Parametrized off the REAL MEMO_CATEGORIES set (not a hardcoded literal
    list) so this test automatically tracks whatever the constant currently
    contains — per §"No Hardcoded Values", the source of truth is the
    constants module, never a duplicated string list in the test.
    """

    @pytest.mark.parametrize("hook_path,hook_label", _HOOKS)
    @pytest.mark.parametrize("category", sorted(MEMO_CATEGORIES))
    def test_existing_category_accepted(self, hook_path, hook_label, category):
        mod = _load_hook_module(f"_existing_accept_{hook_label}_{category}", hook_path)
        trailers = {"Memo": f"{category} - descripcion de prueba para {category}"}

        errors = mod.validate_trailers("memo", trailers, branch="")

        assert errors == [], (
            f"[{hook_label}-hook] existing category '{category}' must keep "
            f"validating with zero errors; got {errors!r}"
        )


class TestGarbageMemoCategoryStillRejected:
    """A category that was never valid must stay rejected — adding 'deadend'
    must not accidentally loosen the gate to accept anything."""

    @pytest.mark.parametrize("hook_path,hook_label", _HOOKS)
    def test_fake_category_rejected(self, hook_path, hook_label):
        mod = _load_hook_module(f"_garbage_reject_{hook_label}", hook_path)
        trailers = {"Memo": "fake - esta categoria nunca fue valida"}

        errors = mod.validate_trailers("memo", trailers, branch="")

        assert errors, (
            f"[{hook_label}-hook] garbage category 'fake' must still be "
            f"rejected — got zero errors"
        )
        assert any("Memo" in e for e in errors), (
            f"[{hook_label}-hook] the error must reference the Memo trailer; "
            f"got {errors!r}"
        )
