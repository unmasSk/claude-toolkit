"""
Test-first contract (Dante, before Ultron) for the F6 hard-link bypass
closure -- issue #53, design owned by Argus (decision 51a3c44):

    "Argus disenó el cierre (parametro opt-in reject_hardlinks + chequeo
    st_nlink>1) pero destapó que open_no_follow_symlink protege tambien
    ficheros de USUARIO (CLAUDE.md, package.json, .gitignore,
    settings.json, scopes) donde un hard-link legitimo (p.ej. entre git
    worktrees) daria falso positivo."

Background: F6 is a residual documented (and, until now, deliberately
accepted) in both twins' docstrings -- a hard link planted at a guarded
path is indistinguishable from an ordinary file to os.path.islink() (not
a reparse point, just another directory entry for the same inode) and to
POSIX O_NOFOLLOW (which only rejects a symlink AT the final path
component, not a second hard link to an existing inode). Closing it was
deliberately deferred out of the v1.16.1 cross-platform fix (51a3c44)
because it touches the POSIX branch of an already-clean, already-verified
core security function and needs call-site-level scoping to avoid false
positives on legitimate user files (a hard link between git worktrees
pointing at the same CLAUDE.md/settings.json/package.json/.gitignore/
scopes file is a NORMAL, legitimate setup, not an attack).

Design fixed as contract here (decided by Argus/orchestrator, not by me):
  - New OPT-IN parameter `reject_hardlinks: bool = False` added to BOTH
    twins:
      lib/git_helpers.py:open_no_follow_symlink()
      lib/_symlink_safe_open.py:open_no_follow_symlink_fallback()
    Default False means every EXISTING call site (none of which pass this
    parameter today) keeps its exact current behavior -- purely additive,
    not a behavior change for any current caller.
  - When reject_hardlinks=True: raise OSError if the opened file has
    st_nlink > 1, checked on the ALREADY-OPEN file descriptor via
    os.fstat(fd) -- never via os.stat(path) -- to avoid a TOCTOU gap
    between the check and the open (same discipline the existing Windows
    identity guard already applies for the symlink-swap race).
  - Must behave identically on both twins (POSIX O_NOFOLLOW branch AND the
    Windows hybrid pre-check+lstat/fstat branch) -- same twin-parity
    discipline as test_crossplatform_symlink_guard.py.

Platform coverage note: unlike os.symlink() (needs Developer Mode /
SeCreateSymbolicLinkPrivilege on Windows), os.link() needs no special
privilege on POSIX or Windows -- confirmed live on this dev box (real
Windows). These tests do NOT monkeypatch sys.platform: they run the
REAL, unmocked branch for whatever host OS pytest is actually on (Windows
here -> exercises the real Windows hybrid branch for real; a POSIX CI run
of this same file exercises the real O_NOFOLLOW branch for real). This
mirrors TestPosixGuardUnchanged's approach in
test_crossplatform_symlink_guard.py, guarded the same way via a
`real_*_capable` skip fixture (see conftest.py::real_hardlink_capable)
rather than silently assumed to work everywhere.

Build mode: test-first (CONTRACT pass, before Ultron). Acceptance
granularity only -- the behaviors that define "done" for issue #53 -- NOT
the exhaustive branch/error-path suite. The EXHAUSTION PROTOCOL hardening
pass runs AFTER Ultron implements (Flow Verify step), against the real
code, and is deliberately NOT applied in this file.

§34 (Producer-Consumer / anti-fixture-fabrication): every hard link in
this file is created for real via os.link() inside the test itself (the
producer) through `_make_hardlinked_pair()` below. The expected
`st_nlink` is NEVER hardcoded to a literal "2" -- it is always read back
via a real os.stat() call on the file this test JUST linked, immediately
before any assertion that depends on it.

Independent-channel rejection verification: rather than asserting on a
specific errno (this codebase already documents ELOOP as deliberately
REUSED across two semantically different Windows rejections -- see
git_helpers.py's own docstring -- so a bare errno match would not by
itself prove the hard-link check fired for the hard-link reason), each
"rejects" test is paired with a "same fixture, only reject_hardlinks
flips" differential control (Test*TrueRejects vs Test*FalseAllows /
Test*Omitted): the ONLY variable that changes between a raise and a clean
open is the reject_hardlinks flag, on a file that is independently
confirmed via os.path.islink()==False (rules out the pre-existing symlink
guard firing instead) and a real st_nlink>1 read back before the call.
That isolates the cause. Additionally, the raised OSError's message is
checked for hard-link vocabulary as a second, independent signal.

NO production code is touched by this file. Only tests.

RED-now expectation: every test that passes reject_hardlinks=True or
reject_hardlinks=False as an explicit keyword argument currently fails
with `TypeError: ...unexpected keyword argument 'reject_hardlinks'` --
that IS the correct RED-for-the-right-reason signal (the parameter does
not exist yet on either twin). Tests that call the twins WITHOUT the new
parameter at all (regression coverage for existing call sites) are
GUARDs: expected GREEN now and GREEN after Ultron implements.
"""

import os

import pytest

from conftest import LIB_DIR  # noqa: F401  (kept for parity with sibling test files)

import git_helpers  # noqa: F401  (imported for parity/clarity; TWIN_FUNCS carries the actual refs)
import _symlink_safe_open  # noqa: F401

from test_crossplatform_symlink_guard import TWIN_FUNCS


def _make_hardlinked_pair(tmp_path, name_prefix, content="original content — hard-link contract\n"):
    """Create a REAL file plus a REAL second hard link to it via os.link()
    -- never faked or mocked, a hard link is a filesystem-level guarantee
    that cannot be meaningfully simulated (same reasoning conftest.py's
    real_symlink_capable fixture documents for symlinks).

    Returns (primary_path, sibling_path, nlink_before) where nlink_before
    is read back via a real os.stat() call on the file this call just
    linked -- never hardcoded to a literal "2".
    """
    primary = tmp_path / f"{name_prefix}-primary.txt"
    sibling = tmp_path / f"{name_prefix}-sibling.txt"
    primary.write_text(content, encoding="utf-8")
    os.link(str(primary), str(sibling))
    nlink_before = os.stat(str(primary)).st_nlink
    assert not os.path.islink(str(primary)), (
        "sanity check: a hard link must never be reported as a symlink by "
        "os.path.islink() -- if this fails, the fixture itself is wrong, "
        "not the code under test"
    )
    return str(primary), str(sibling), nlink_before


def _looks_like_hardlink_rejection_message(exc: OSError) -> bool:
    """Second, independent signal that the raised OSError is actually
    about the hard-link count, not a coincidental unrelated OSError."""
    msg = str(exc).lower()
    return "hard" in msg and "link" in msg


# ══════════════════════════════════════════════════════════════════════════
# Case 1 — reject_hardlinks=True rejects a file with st_nlink > 1 (RED now)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestRejectHardlinksTrueRejectsMultilinkFile:
    """Contract: reject_hardlinks=True must raise OSError for a file whose
    open fd reports st_nlink > 1, on BOTH twins.

    RED now: neither twin accepts a `reject_hardlinks` keyword argument at
    all -- calling with it raises TypeError, not OSError. GREEN after
    Ultron implements the parameter and the fstat(fd).st_nlink check.
    """

    @pytest.mark.parametrize("mode", ["r", "w"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_multilink_file_raises_oserror_with_reject_hardlinks_true(
        self, tmp_path, target_open, mode
    ):
        primary, sibling, nlink_before = _make_hardlinked_pair(
            tmp_path, f"reject-true-{mode}"
        )
        assert nlink_before > 1, (
            f"fixture setup invariant broken: expected st_nlink>1 after a "
            f"real os.link(), got {nlink_before}"
        )

        with pytest.raises(OSError) as exc_info:
            target_open(primary, mode, reject_hardlinks=True)

        assert _looks_like_hardlink_rejection_message(exc_info.value), (
            f"OSError raised but its message doesn't mention hard links -- "
            f"got: {exc_info.value!r}. This must be rejected FOR the "
            f"nlink>1 reason, not some other coincidental OSError."
        )
        # Independent-channel content check: content survives via the
        # SIBLING path (different filename, same inode) using a plain,
        # unguarded open() -- proves the rejected call never truncated the
        # shared inode's content, even for mode="w".
        with open(sibling, "r", encoding="utf-8") as f:
            assert f.read() == "original content — hard-link contract\n"


# ══════════════════════════════════════════════════════════════════════════
# Case 2 — reject_hardlinks=True allows a normal (st_nlink == 1) file (RED now)
# ══════════════════════════════════════════════════════════════════════════


class TestRejectHardlinksTrueAllowsSingleLinkFile:
    """Contract: reject_hardlinks=True must NOT reject an ordinary file
    (st_nlink == 1, no hard link involved) -- the guard is scoped to
    multi-link files only, on BOTH twins.

    RED now: same TypeError-on-unknown-kwarg reason as Case 1.
    """

    @pytest.mark.parametrize("mode", ["r", "w"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_single_link_file_opens_and_round_trips_with_reject_hardlinks_true(
        self, tmp_path, target_open, mode
    ):
        path = tmp_path / f"single-link-{mode}.txt"
        payload = "normal file, no hard link, reject_hardlinks=True\n"
        path.write_text(payload, encoding="utf-8")
        nlink_before = os.stat(str(path)).st_nlink
        assert nlink_before == 1, (
            f"fixture setup invariant broken: a freshly-written plain file "
            f"must have st_nlink==1, got {nlink_before}"
        )

        f = target_open(str(path), mode, reject_hardlinks=True)
        try:
            if mode == "r":
                assert f.read() == payload
            else:
                f.write("appended after guard check\n")
        finally:
            f.close()


# ══════════════════════════════════════════════════════════════════════════
# Case 3a — reject_hardlinks=False (explicit) does NOT reject st_nlink > 1
# (RED now — differential control paired with Case 1)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestRejectHardlinksExplicitFalseAllowsMultilinkFile:
    """Contract: explicitly passing reject_hardlinks=False on a multi-link
    file must NOT raise -- protects legitimate user files (CLAUDE.md,
    settings.json, package.json, .gitignore, scopes) where a hard link
    between git worktrees is a legitimate setup, not an attack.

    This is the differential control for Case 1: SAME fixture shape
    (multi-link file), only the flag changes. Together, Case 1 raising and
    this NOT raising isolates reject_hardlinks as the actual cause of the
    Case 1 rejection.

    RED now: same TypeError-on-unknown-kwarg reason (the parameter itself
    doesn't exist yet, so even passing False by name fails before any
    guard logic runs).
    """

    @pytest.mark.parametrize("mode", ["r", "w"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_multilink_file_opens_with_reject_hardlinks_explicit_false(
        self, tmp_path, target_open, mode
    ):
        primary, sibling, nlink_before = _make_hardlinked_pair(
            tmp_path, f"reject-false-{mode}"
        )
        assert nlink_before > 1

        f = target_open(primary, mode, reject_hardlinks=False)
        try:
            if mode == "r":
                assert f.read() == "original content — hard-link contract\n"
            else:
                f.write("appended with reject_hardlinks=False\n")
        finally:
            f.close()


# ══════════════════════════════════════════════════════════════════════════
# Case 3b / Case 4 — parameter OMITTED entirely: existing call sites keep
# their exact current behavior on a multi-link file (GUARD — GREEN now
# AND after Ultron; this is the regression-protection case)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestRejectHardlinksParamOmittedPreservesCurrentBehavior:
    """Regression GUARD: every call site in this codebase today calls
    open_no_follow_symlink()/open_no_follow_symlink_fallback() WITHOUT any
    reject_hardlinks argument at all. This must keep behaving exactly as
    it does today -- opening a multi-link file without raising -- both
    BEFORE Ultron adds the parameter (proving the new contract is purely
    additive) and AFTER (proving Ultron didn't flip the default or make it
    apply implicitly).

    Expected GREEN now. Expected GREEN after Task implementation. If this
    ever goes RED after implementation, the default silently changed
    behavior for every existing call site -- a regression, not a feature.
    """

    @pytest.mark.parametrize("mode", ["r", "w"])
    @pytest.mark.parametrize("target_open", TWIN_FUNCS.values(), ids=TWIN_FUNCS.keys())
    def test_multilink_file_opens_when_parameter_is_never_passed(
        self, tmp_path, target_open, mode
    ):
        primary, sibling, nlink_before = _make_hardlinked_pair(
            tmp_path, f"reject-omitted-{mode}"
        )
        assert nlink_before > 1

        f = target_open(primary, mode)
        try:
            if mode == "r":
                assert f.read() == "original content — hard-link contract\n"
            else:
                f.write("appended with parameter omitted entirely\n")
        finally:
            f.close()


# ══════════════════════════════════════════════════════════════════════════
# Case 5 — twin parity: both twins must agree for the SAME scenario
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestTwinParityHardlinkReject:
    """git_helpers.open_no_follow_symlink and
    _symlink_safe_open.open_no_follow_symlink_fallback must raise the same
    exception TYPE for the same reject_hardlinks=True/multilink scenario,
    and must agree (both succeed) for the same reject_hardlinks=False
    scenario -- same twin-parity discipline as
    test_crossplatform_symlink_guard.py::TestTwinParity.

    RED now: both twins currently raise TypeError identically (parity
    itself holds -- neither twin has drifted from the other), so the
    type-equality-to-TypeError succeeds but the type-equality-to-OSError
    assertion fails. That is the correct RED signal: parity is not the
    missing piece, the feature itself is.
    """

    def test_reject_true_multilink_same_outcome_on_both_twins(self, tmp_path):
        results = {}
        for name, fn in TWIN_FUNCS.items():
            primary, sibling, nlink_before = _make_hardlinked_pair(
                tmp_path, f"parity-true-{name.replace('.', '_')}"
            )
            assert nlink_before > 1
            try:
                fn(primary, "w", reject_hardlinks=True)
            except Exception as e:
                results[name] = type(e)
            else:
                results[name] = None

        distinct_outcomes = set(results.values())
        assert len(distinct_outcomes) == 1, (
            f"the two twins diverged for the SAME reject_hardlinks=True "
            f"multilink scenario: {results} -- they must be byte-identical "
            f"in behavior"
        )
        assert distinct_outcomes == {OSError}, (
            f"both twins must raise OSError for a reject_hardlinks=True "
            f"multilink hit, got {results}"
        )

    def test_reject_false_multilink_same_outcome_on_both_twins(self, tmp_path):
        results = {}
        for name, fn in TWIN_FUNCS.items():
            primary, sibling, nlink_before = _make_hardlinked_pair(
                tmp_path, f"parity-false-{name.replace('.', '_')}"
            )
            assert nlink_before > 1
            try:
                f = fn(primary, "w", reject_hardlinks=False)
                f.write("parity false\n")
                f.close()
            except Exception as e:
                results[name] = type(e)
            else:
                results[name] = None

        assert set(results.values()) == {None}, (
            f"the two twins diverged for the SAME reject_hardlinks=False "
            f"multilink scenario (must both succeed): {results}"
        )
