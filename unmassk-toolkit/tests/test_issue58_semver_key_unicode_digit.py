"""
Regression for issue #58 -- bin/release_validators.py::_semver_key (L65).

Bug: the pre-release identifier's numeric-branch check used bare
`ident.isdigit()`, which returns True for non-ASCII Unicode digit
characters too (e.g. full-width '１２３', which `int()` also
happily parses as 123). A pre-release identifier built from full-width
digits therefore took the NUMERIC comparison branch `(0, int(ident))`
instead of the ALPHANUMERIC branch `(1, ident)` semver 2.0.0 SS11.4.3
requires for anything that isn't a genuine ASCII numeric identifier --
producing a wrong sort order between two pre-release versions whose only
difference is digit script.

Fix: `(0, int(ident)) if ident.isascii() and ident.isdigit() else (1, ident)`
-- only genuine ASCII digits take the numeric branch now.

Channel: direct unit call to `_semver_key()` (a pure function, no I/O,
value is in isolation -- no need for the full release.py subprocess/git
flow the neighboring TestSemverNumericOrdering/TestT12PreReleaseSemver
classes in test_release.py use, since `_semver_key()` never re-validates
its input against SEMVER_RE internally). Import path mirrors
test_release.py's own `sys.path.insert(0, _REPO_ROOT)` pattern for
resolving `bin` as a namespace package regardless of invocation cwd
(issue #50).

Expected values are never hand-typed as tuple literals -- every assertion
either (a) compares two REAL `_semver_key()` outputs against each other
(ordering, derived at test time, not guessed), or (b) is the ORDERING
behavior semver's own spec mandates (alphanumeric identifiers always
outrank numeric ones, regardless of numeric value) -- verified live before
writing this file: simulating the pre-fix `ident.isdigit()`-only branch
selection flips `fullwidth > ascii_200` from True (fixed) to False (buggy),
confirming this is the bug-detecting comparison, not an incidental one.

Project scope note: this is a self-inflicted correctness bug (wrong
release-version sort order), not an attacker scenario -- per this
project's CLAUDE.md threat model, no adversarial framing applies.

Build mode: linear (fix already applied by Ultron at L65). Only tests
here -- no production code changed.
"""

import os
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_THIS_DIR)      # unmassk-toolkit/
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)     # git root

if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

from bin.release_validators import _semver_key  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════
# Full-width Unicode digit identifiers must sort as ALPHANUMERIC.
# ══════════════════════════════════════════════════════════════════════════


class TestIssue58FullWidthDigitIdentifierSortsAsAlphanumeric:
    def test_fullwidth_identifier_outranks_ascii_numeric_of_higher_value(self):
        """The exact regression signature: full-width '１２３'
        (numeric value 123) vs ASCII '200' (numeric value 200, strictly
        greater). Pre-fix (numeric-vs-numeric): 123 < 200, so fullwidth
        would sort LOWER. Post-fix (alphanumeric-vs-numeric): alphanumeric
        always outranks numeric per semver SS11.4.3, so fullwidth must sort
        HIGHER despite its digits being numerically smaller -- this is what
        makes a guard bypass observable rather than vacuous."""
        fullwidth = _semver_key("1.0.0-１２３")
        ascii_higher_value = _semver_key("1.0.0-200")

        assert fullwidth > ascii_higher_value, (
            "Issue #58: a full-width-digit pre-release identifier must sort as "
            "alphanumeric (outranking any numeric identifier, regardless of digit "
            f"value). Got fullwidth={fullwidth!r} ascii_200={ascii_higher_value!r}"
        )

    def test_fullwidth_identifier_outranks_every_ascii_numeric_identifier(self):
        """Broader proof than the single-value case above: an alphanumeric
        identifier must outrank EVERY numeric identifier, not just one
        arbitrarily chosen value -- derived by comparing against the
        highest of a spread of real ASCII-numeric _semver_key() outputs."""
        fullwidth = _semver_key("1.0.0-１２３")
        ascii_candidates = [_semver_key(f"1.0.0-{n}") for n in (0, 9, 42, 200, 999999)]

        assert fullwidth > max(ascii_candidates), (
            f"Full-width identifier must outrank every ASCII-numeric identifier. "
            f"Got fullwidth={fullwidth!r} max(ascii_candidates)={max(ascii_candidates)!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Regression guard: ordinary ASCII digit identifiers must keep taking the
# numeric branch -- the ascii()+isdigit() guard must not over-reject.
# ══════════════════════════════════════════════════════════════════════════


class TestIssue58AsciiDigitsStillTakeNumericBranch:
    def test_ascii_numeric_identifiers_compare_by_value_not_lexicographically(self):
        """9 (ASCII numeric) must sort before 10 (ASCII numeric) -- proves
        the numeric branch is still reached and still compares by int
        value, not string ('10' < '9' lexicographically)."""
        nine = _semver_key("1.0.0-9")
        ten = _semver_key("1.0.0-10")

        assert nine < ten, (
            f"ASCII-numeric pre-release identifiers must compare by value: "
            f"9 < 10. Got nine={nine!r} ten={ten!r}"
        )

    def test_ascii_numeric_identifier_outranked_by_ascii_alphanumeric(self):
        """Semver SS11.4.3: numeric identifiers always have lower precedence
        than alphanumeric identifiers, for plain ASCII too -- '9' must sort
        below 'rc1' regardless of any digit-script concern. Regression
        guard that the ascii()+isdigit() fix didn't accidentally flip this
        pre-existing, unrelated ordering rule."""
        ascii_numeric = _semver_key("1.0.0-9")
        ascii_alnum = _semver_key("1.0.0-rc1")

        assert ascii_numeric < ascii_alnum, (
            f"ASCII numeric identifier must still be outranked by an ASCII "
            f"alphanumeric one. Got ascii_numeric={ascii_numeric!r} ascii_alnum={ascii_alnum!r}"
        )


if __name__ == "__main__":
    import pytest

    sys.exit(pytest.main([__file__, "-v"]))
