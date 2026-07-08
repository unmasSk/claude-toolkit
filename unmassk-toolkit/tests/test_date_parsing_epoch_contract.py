"""
Issue #55 -- contract tests for the fragile `git log %aI` +
datetime.fromisoformat() date-parsing pattern.

Five sites share this shape (Yoda/Bex triage, issue #55):
  - bin/git-memory-gc.py:73 (parse_date()), :88 (the %aI pretty-format call)
  - bin/git-memory-doctor.py:91 (parse_date()), :187 (check_hook_execution's
    %aI call), :220 (check_gc_status's %aI call)

All wrap (or would wrap) any parse failure in a bare
`except (ValueError, IndexError): return None` -- so an old/quirky git
whose %aI output isn't cleanly ISO-8601-parseable degrades SILENTLY (date
becomes None) instead of raising. That silence has an observable cost: any
downstream heuristic gated on "if commit date is truthy" (gc.py's H2 stale-
blocker TTL, doctor.py's GC-last-run / stale-blocker-count checks) quietly
stops firing for that commit instead of reporting the real value.

RECONCILED (same session, after an adversarial round surfaced a
contradiction and the orchestrator reviewed the design): lib/
bootstrap_commits.py:28 was wrongly folded into this six-site list in the
first round. It has no parse_date() at all -- the date string is stored
unparsed, purely for presentation in bin/git-memory-bootstrap.py --json
("structured output for Claude to present to the user", per that script's
own module docstring). It never had the %aI+fromisoformat CRASH this issue
fixes at the other five sites, so it is excluded from the %at migration.
Its contract is the opposite of the other five: %aI (readable ISO-8601) is
correct, %at (a raw epoch digit string) is the bug -- see
TestBootstrapCommitsDateFieldContract and
TestBootstrapJsonDateFieldReadableForPresentation below for the reasoning
and Ultron's pending revert back to %aI.

lib/boot_git_checks.py's time_ago() already solved exactly this problem for
its own callers by switching the git log token from %aI to %at (unix
epoch -- a plain digit string, robust across git versions/locales/timezone
formatting) and parsing it with `int(...)` instead of `fromisoformat()`.
The contract fixed by this file: every site above must adopt the same %at +
robust-parse shape.

Build mode: test-first (Dante writes the RED contract, Ultron implements
until green). No production code is touched here -- see Dante's Absolute
Prohibition #1 and CLAUDE.md's build-mode note.

Not tested (with reason): bin/git-memory-doctor.py:187
(check_hook_execution()'s %aI call). Read directly: the function fetches
the date field but never parses or otherwise consumes it (only `body =
parts[2]` is used) -- there is no observable behavior difference to pin
today, so no test is written for it. Flagged here for Ultron to migrate
alongside the other five sites for consistency, not because a test proves
a break there.

Failure-mode reproduction technique for the end-to-end tests: a fake `git`
executable shadowing PATH (same pattern as
tests/test_boot_freshness.py::_make_fake_git, documented in
.claude/agent-memory/unmassk-toolkit-dante/mock-patterns.md) that rewrites
any literal "%aI" token inside a `--pretty=format:` argument to inert
literal text before delegating to the real git binary -- this reproduces
exactly what an old git release that doesn't recognize the %aI directive
would do (an unrecognized/unexpanded placeholder is emitted as literal
text, never expanded), without needing a real ancient git binary on this
machine. %at is never touched by this rewrite, so once a site migrates to
%at, the exact same "hostile" PATH is provably harmless to it -- proving
the fix, not just that today's code is broken.
"""

import json
import os
import re
import shutil
import sys
import time
import importlib.util
from datetime import datetime, timezone

import pytest

from conftest import (
    BIN_DIR, LIB_DIR,
    git_cmd, run_script, DOCTOR, GC, BOOTSTRAP, run_doctor_json,
)

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from bootstrap_commits import scan_recent_commits  # noqa: E402
from date_parsing import parse_date  # noqa: E402


# ── Helpers ──────────────────────────────────────────────────────────────


def _load_hyphenated_module(path, name):
    """Load a hyphenated bin/*.py script as an importable module.

    Same pattern documented in
    .claude/agent-memory/unmassk-toolkit-dante/unmassk-toolkit-python-test-conventions.md
    -- these scripts have no side effects outside `if __name__ ==
    "__main__": main()`, so exec_module() is safe.
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_FAKE_OLD_GIT_TEMPLATE = '''#!/usr/bin/env python3
import sys, subprocess

args = sys.argv[1:]
patched = []
for a in args:
    if a.startswith("--pretty=format:") and "%aI" in a:
        # Simulate an old/quirky git that does not recognize the %aI
        # directive: an unrecognized pretty-format placeholder is emitted
        # as literal text, never expanded to a date. %at (if present) is
        # left untouched -- it is a much older, universally-supported
        # token, so any site that migrates to it is unaffected by this
        # simulation.
        a = a.replace("%aI", "OLDGIT-UNSUPPORTED-DATE-TOKEN")
    patched.append(a)

real_git = r"""__REAL_GIT__"""
result = subprocess.run([real_git] + patched)
sys.exit(result.returncode)
'''


def _make_old_git_no_aI(tmp_path):
    """Build a fake `git` on PATH that cannot expand %aI (see module
    docstring). Returns the directory to prepend to PATH."""
    real_git = shutil.which("git")
    assert real_git, "real git binary not found on PATH -- cannot build fake git wrapper"
    fake_dir = tmp_path / "fake_bin_no_aI"
    fake_dir.mkdir(exist_ok=True)
    fake_git_path = fake_dir / "git"
    script = _FAKE_OLD_GIT_TEMPLATE.replace("__REAL_GIT__", real_git)
    fake_git_path.write_text(script, encoding="utf-8")
    os.chmod(fake_git_path, 0o755)
    return str(fake_dir)


def _run_doctor_json_with_env(cwd, env):
    """Same shape as conftest.run_doctor_json(), but accepts an env
    override (needed for the PATH-shadowing fake-git tests below). Not
    added as a new kwarg to conftest.run_doctor_json() itself -- that
    helper's signature is relied on by ~50+ existing call sites across the
    suite; see unmassk-toolkit-python-test-conventions.md's scope-
    discipline note on not silently expanding a widely-used shared
    helper's contract for one new caller.
    """
    rc, out, err = run_script(DOCTOR, cwd, ["--json"], env=env)
    try:
        return json.loads(out), rc
    except json.JSONDecodeError:
        return {
            "status": "error", "checks": [],
            "_debug": f"doctor.py --json rc={rc} stdout={out!r} stderr={err!r}",
        }, rc


def _find_check(parsed, component):
    for c in parsed.get("checks", []):
        if c.get("component") == component:
            return c.get("message")
    return None


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _real_epoch_of_head(repo):
    """Read the REAL %at epoch git just emitted for HEAD -- never hand-typed
    (unmassk-standards §34): the expected value in the epoch-contract tests
    below is derived from this real producer, not fabricated."""
    rc, out, err = git_cmd(["log", "-1", "--pretty=format:%at"], repo)
    assert rc == 0 and out.isdigit(), (
        f"setup failed reading real git %at: rc={rc} out={out!r} err={err!r}"
    )
    return out


def _real_iso_of_head(repo):
    """Read the REAL %aI ISO-8601 date git just emitted for HEAD -- never
    hand-typed (unmassk-standards §34). Used by the bootstrap_commits.py
    contract below: that module is presentation-only (never parses the
    date), so %aI -- not %at -- is its correct, single contract."""
    rc, out, err = git_cmd(["log", "-1", "--pretty=format:%aI"], repo)
    assert rc == 0 and out and not out.isdigit(), (
        f"setup failed reading real git %aI: rc={rc} out={out!r} err={err!r}"
    )
    return out


# ── ISO-8601 fallback branch: ground truth for both parse_date()s ────────
#
# Cerberus follow-up (issue #55, 1 suggestion): the ISO-8601 fallback
# branch added alongside the %at migration --
#   dt = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
#   if dt.tzinfo is None:
#       dt = dt.replace(tzinfo=timezone.utc)
# -- is unreachable from any caller in this repo today (every git log call
# site now emits %at), kept only for external/legacy callers. If someone
# deletes the `.replace(tzinfo=...)` line tomorrow, naive/aware datetime
# mixing regresses silently with no test catching it. These two ISO cases
# close that gap. Expected values are built via `datetime.fromisoformat()`
# in this file, never hand-typed (unmassk-standards §34) -- the only
# transformation applied afterward mirrors production's own naive-defaults-
# to-UTC semantic, not a duplicated re-implementation of parse_date() itself.
_ISO_NAIVE = "2026-03-13T08:00:00"
_ISO_WITH_OFFSET = "2026-03-13T08:00:00+02:00"

_ISO_FALLBACK_CASES = [
    (
        _ISO_NAIVE,
        datetime.fromisoformat(_ISO_NAIVE).replace(tzinfo=timezone.utc),
        timezone.utc,
    ),
    (
        _ISO_WITH_OFFSET,
        datetime.fromisoformat(_ISO_WITH_OFFSET),
        datetime.fromisoformat(_ISO_WITH_OFFSET).tzinfo,
    ),
]
_ISO_FALLBACK_IDS = ["iso_naive_becomes_utc_aware", "iso_with_offset_preserves_instant"]


# ── parse_date() epoch contract: gc.py ──────────────────────────────────


class TestGcParseDateEpochContract:
    """bin/git-memory-gc.py:70 parse_date() only ever tries
    datetime.fromisoformat(). Once gc.py migrates its git log call to %at
    (this contract), parse_date() -- or whatever replaces it -- must
    correctly resolve a real unix-epoch string (exactly what %at emits) to
    the same moment in time git itself recorded.
    """

    def test_parse_date_resolves_real_epoch_string(self, tmp_path):
        repo = _make_repo(tmp_path)
        real_epoch = _real_epoch_of_head(repo)

        gc_mod = _load_hyphenated_module(GC, "contract_gc_epoch_55")
        result = gc_mod.parse_date(real_epoch)

        expected = datetime.fromtimestamp(int(real_epoch), tz=timezone.utc)
        assert result == expected, (
            f"parse_date({real_epoch!r}) returned {result!r} -- expected "
            f"{expected!r} (the real epoch git just emitted for HEAD via "
            "%at). Current parse_date() only tries fromisoformat(), which "
            "raises ValueError on a bare digit string and is swallowed to "
            "None -- exactly the silent degradation issue #55 describes."
        )

    @pytest.mark.parametrize(
        "date_str, expected, expected_tzinfo",
        _ISO_FALLBACK_CASES,
        ids=_ISO_FALLBACK_IDS,
    )
    def test_parse_date_iso_fallback_stays_tz_aware(self, date_str, expected, expected_tzinfo):
        """The %at branch is gc.py's primary path now, but the ISO-8601
        fallback (`fromisoformat()` + naive-defaults-to-UTC) still ships for
        external/legacy callers. Pins its tz-handling so a future edit that
        drops the `dt.replace(tzinfo=timezone.utc)` naive guard regresses
        loudly instead of silently reintroducing naive/aware mixing.
        """
        gc_mod = _load_hyphenated_module(GC, "contract_gc_iso_fallback_55")
        result = gc_mod.parse_date(date_str)

        assert result == expected, (
            f"parse_date({date_str!r}) returned {result!r} -- expected "
            f"{expected!r} (built via datetime.fromisoformat() on the same "
            "input, not hand-typed)"
        )
        assert result.tzinfo == expected_tzinfo, (
            f"parse_date({date_str!r}) returned tzinfo={result.tzinfo!r} -- "
            f"expected {expected_tzinfo!r}. A naive ISO string must become "
            "UTC-aware; an offset-aware ISO string must keep its original "
            "offset -- neither should collapse into naive/aware mixing."
        )


# ── parse_date() epoch contract: doctor.py ──────────────────────────────


class TestDoctorParseDateEpochContract:
    """Same duplicated parse_date() shape as gc.py's, in
    bin/git-memory-doctor.py:84."""

    def test_parse_date_resolves_real_epoch_string(self, tmp_path):
        repo = _make_repo(tmp_path)
        real_epoch = _real_epoch_of_head(repo)

        doctor_mod = _load_hyphenated_module(DOCTOR, "contract_doctor_epoch_55")
        result = doctor_mod.parse_date(real_epoch)

        expected = datetime.fromtimestamp(int(real_epoch), tz=timezone.utc)
        assert result == expected, (
            f"parse_date({real_epoch!r}) returned {result!r} -- expected "
            f"{expected!r} (the real epoch git just emitted for HEAD via "
            "%at). Current parse_date() only tries fromisoformat(), which "
            "raises ValueError on a bare digit string and is swallowed to "
            "None -- exactly the silent degradation issue #55 describes."
        )

    @pytest.mark.parametrize(
        "date_str, expected, expected_tzinfo",
        _ISO_FALLBACK_CASES,
        ids=_ISO_FALLBACK_IDS,
    )
    def test_parse_date_iso_fallback_stays_tz_aware(self, date_str, expected, expected_tzinfo):
        """Same duplicated ISO-8601 fallback shape as gc.py's -- see
        TestGcParseDateEpochContract.test_parse_date_iso_fallback_stays_tz_aware.
        """
        doctor_mod = _load_hyphenated_module(DOCTOR, "contract_doctor_iso_fallback_55")
        result = doctor_mod.parse_date(date_str)

        assert result == expected, (
            f"parse_date({date_str!r}) returned {result!r} -- expected "
            f"{expected!r} (built via datetime.fromisoformat() on the same "
            "input, not hand-typed)"
        )
        assert result.tzinfo == expected_tzinfo, (
            f"parse_date({date_str!r}) returned tzinfo={result.tzinfo!r} -- "
            f"expected {expected_tzinfo!r}. A naive ISO string must become "
            "UTC-aware; an offset-aware ISO string must keep its original "
            "offset -- neither should collapse into naive/aware mixing."
        )


# ── bootstrap_commits.py date-field contract ────────────────────────────


class TestBootstrapCommitsDateFieldContract:
    """lib/bootstrap_commits.py:28 has no parse_date() at all -- the date
    string is stored unparsed in each commit dict's "date" key, feeding
    bin/git-memory-bootstrap.py --json, whose own module docstring
    describes its output as "structured output for Claude to present to
    the user." Because nothing here ever parses the field, it never had
    the %aI+fromisoformat CRASH issue #55 fixes at the other five sites --
    it was wrongly folded into that migration in an earlier round of this
    same issue (see the RECONCILED note in this file's module docstring).
    The correct, single contract for this field is %aI (readable
    ISO-8601): a raw %at epoch digit string is the bug here, not the fix.
    """

    def test_recent_commit_date_is_real_iso_string(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        real_iso = _real_iso_of_head(repo)

        monkeypatch.chdir(repo)
        result = scan_recent_commits(depth=1)

        assert result is not None, "scan_recent_commits() returned None -- fixture broken"
        assert result["recent"], "no commits scanned -- fixture broken"
        got_date = result["recent"][0]["date"]
        assert got_date == real_iso, (
            "contract not yet met: lib/bootstrap_commits.py's git log call "
            f"does not emit %aI -- got {got_date!r}, expected the real "
            f"ISO-8601 date {real_iso!r} from "
            "`git log --pretty=format:%aI` on the same commit (this module "
            "never parses the date; it is presentation-only, per "
            "bin/git-memory-bootstrap.py's own docstring)"
        )


# ── End-to-end degradation: gc.py stale-blocker heuristic ───────────────


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="bare extensionless 'git' shim is not PATH-resolved on Windows",
)
class TestGcStaleBlockerSurvivesOldGit:
    """find_stale_items()'s H2 heuristic (bin/git-memory-gc.py:220) skips
    ANY commit whose parsed date is falsy -- `if not commit["date"]:
    continue` -- unconditionally, before even H3's explicit-resolution
    override runs. An old git that can't expand %aI makes every commit's
    date None, so a genuinely-stale Blocker: silently never gets flagged
    for GC. Migrating to %at (a token this simulation never touches) with
    robust digit parsing is the fix.
    """

    def test_stale_blocker_flagged_even_when_aI_is_unsupported(self, tmp_path):
        repo = _make_repo(tmp_path)
        marker = "xyzoldgitblockermarker55"
        stale_epoch = int(time.time()) - 40 * 86400
        git_cmd(
            ["commit", "--allow-empty", "-m",
             f"🚧 wip(feature): blocked\n\nBlocker: {marker}"],
            repo,
            env={
                "GIT_AUTHOR_DATE": f"@{stale_epoch}",
                "GIT_COMMITTER_DATE": f"@{stale_epoch}",
            },
        )

        # Setup sanity: with real, unmodified git, a real 40-day-old
        # Blocker: must already be flagged today -- if this fails, the
        # fixture is broken, not the contract under test.
        rc, out, err = run_script(GC, repo, ["--dry-run"])
        assert rc == 0, f"gc.py --dry-run failed: {err}"
        assert marker in out, (
            "test setup error: a real 40-day-old Blocker: was not detected "
            f"as stale with real git. stdout={out!r} stderr={err!r}"
        )

        # Contract: an old git that can't expand %aI must not hide it.
        fake_bin = _make_old_git_no_aI(tmp_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}
        rc2, out2, err2 = run_script(GC, repo, ["--dry-run"], env=env)
        assert rc2 == 0, f"gc.py --dry-run failed under old-git sim: {err2}"
        assert marker in out2, (
            "contract not yet met: an old git that cannot expand %aI makes "
            f"parse_date() return None, and H2 silently drops {marker!r} "
            "instead of flagging it stale. Fix: migrate to %at with robust "
            "digit parsing, mirroring lib/boot_git_checks.py's time_ago(). "
            f"stdout={out2!r}"
        )


# ── End-to-end degradation: doctor.py GC status ─────────────────────────


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="bare extensionless 'git' shim is not PATH-resolved on Windows",
)
class TestDoctorGcStatusSurvivesOldGit:
    """bin/git-memory-doctor.py:check_gc_status() has the identical shape
    as gc.py's H2 (same duplicated parse_date(), same "falsy date is
    silently skipped" guard) for BOTH its stale-blocker count and its
    "days since last GC" figure.
    """

    def test_stale_blocker_count_survives_old_git(self, tmp_path):
        repo = _make_repo(tmp_path)
        stale_epoch = int(time.time()) - 40 * 86400
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "🚧 wip(feature): blocked\n\nBlocker: doctor stale blocker 55"],
            repo,
            env={
                "GIT_AUTHOR_DATE": f"@{stale_epoch}",
                "GIT_COMMITTER_DATE": f"@{stale_epoch}",
            },
        )

        parsed_control, rc = run_doctor_json(repo)
        control_msg = _find_check(parsed_control, "Stale blockers")
        assert control_msg is not None and control_msg != "none", (
            "test setup error: a real 40-day-old Blocker: was not counted "
            "as stale by doctor.py with real git. "
            f"checks={parsed_control.get('checks')!r}"
        )

        fake_bin = _make_old_git_no_aI(tmp_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}
        parsed_old, rc2 = _run_doctor_json_with_env(repo, env=env)
        old_msg = _find_check(parsed_old, "Stale blockers")
        assert old_msg is not None and old_msg != "none", (
            "contract not yet met: doctor.py reports 'none' stale blockers "
            "under an old git that can't expand %aI, even though a real "
            "40-day-old Blocker: exists. "
            f"checks={parsed_old.get('checks')!r}"
        )

    def test_gc_last_run_date_survives_old_git(self, tmp_path):
        repo = _make_repo(tmp_path)
        gc_epoch = int(time.time()) - 10 * 86400
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "🔧 chore(memory): gc — 1 items cleaned\n\n"
             "Why: automated memory garbage collection\nResolved-Next: x55"],
            repo,
            env={
                "GIT_AUTHOR_DATE": f"@{gc_epoch}",
                "GIT_COMMITTER_DATE": f"@{gc_epoch}",
            },
        )

        parsed_control, rc = run_doctor_json(repo)
        control_msg = _find_check(parsed_control, "GC")
        assert control_msg and re.search(r"last run \d+ days? ago", control_msg), (
            "test setup error: a real GC commit was not detected by "
            f"doctor.py with real git. got {control_msg!r}"
        )

        fake_bin = _make_old_git_no_aI(tmp_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}
        parsed_old, rc2 = _run_doctor_json_with_env(repo, env=env)
        old_msg = _find_check(parsed_old, "GC")
        assert old_msg and re.search(r"last run \d+ days? ago", old_msg), (
            "contract not yet met: doctor.py reports GC 'never run' under "
            "an old git that can't expand %aI, even though a real GC "
            f"commit exists 10 days ago. got {old_msg!r}"
        )


# ── Adversarial round (Argus + Moriarty), issue #55 follow-up ───────────
#
# Five confirmed bugs on top of the %at migration above. Test-first: these
# must FAIL against unmodified HEAD (except BUG-2, documented honestly
# below). No production code touched here -- see Dante's Absolute
# Prohibition #1.


# ── BUG-1 (Argus SEC-LOW-001): parse_date() crashes on non-string input ──


class TestParseDateNonStringInputContract:
    """lib/date_parsing.py::parse_date()'s docstring promises "Returns ...
    or None if parsing fails" -- for ANY input. But `date_str.isdigit()`
    is called unconditionally inside the try block, and AttributeError is
    NOT one of the caught exception types (`except (ValueError, TypeError,
    OSError, OverflowError)`). None, an int, or a list all have no
    `.isdigit` attribute, so each one crashes with an uncaught
    AttributeError instead of degrading to None.
    """

    @pytest.mark.parametrize(
        "bad_input",
        [None, 123456, ["a"]],
        ids=["none", "int", "list"],
    )
    def test_returns_none_instead_of_raising(self, bad_input):
        result = parse_date(bad_input)
        assert result is None, (
            f"parse_date({bad_input!r}) should return None per its own "
            "docstring contract ('or None if parsing fails'), not raise -- "
            f"got {result!r}"
        )


# ── BUG-2 (Argus SEC-LOW-002): no explicit length guard before int() ────


class TestParseDateLengthGuardContract:
    """lib/date_parsing.py::parse_date() has no explicit upper bound on
    input length before calling `int(date_str)` on a digit string. A real
    unix epoch never needs more than ~12-19 digits (year 9999 is epoch
    253402300799, 12 digits; a 64-bit signed epoch tops out at 19 digits).
    This class pins the CONTRACT an explicit length guard (e.g.
    `len(date_str) > 20: return None`) would enforce, as a regression net
    for whatever Ultron adds.

    Honesty note (Dante, unmassk-standards -- no fabricated red): on this
    runtime (CPython 3.11+, `sys.get_int_max_str_digits() == 4300` by
    default), an oversized digit string ALREADY returns None today -- not
    via an explicit length guard, but as an accidental side effect of two
    unrelated safety nets stacking:
      1. CPython's own int-from-string digit-count limit raises
         ValueError above 4300 digits (verified: a 4301-digit "9" string
         raises `ValueError: Exceeds the limit (4300 digits)...`).
      2. Independently of (1) -- verified below by temporarily calling
         `sys.set_int_max_str_digits(0)` to remove that limit entirely --
         `datetime.fromtimestamp()` raises OverflowError for any epoch
         outside its representable range, and every "9"*N string tested
         here lands outside it regardless of N.
    Both exception types are already in parse_date()'s except tuple, so
    every case below is GREEN today, not RED. It does not currently prove
    a bug -- only that today's *accidental* behavior already matches the
    *intended explicit* contract. Kept in the suite so it (a) documents
    the contract for Ultron's future explicit guard, (b) stays green
    unchanged once that guard exists, and (c) would catch a REAL
    regression if either accidental safety net were ever weakened (e.g.
    `sys.set_int_max_str_digits()` raised elsewhere in the process, or a
    future refactor swapped `datetime.fromtimestamp` for something with a
    wider representable range).
    """

    @pytest.mark.parametrize(
        "length",
        [21, 25, 100, 5000, 50000],
        ids=["21_digits", "25_digits", "100_digits", "5000_digits", "50000_digits"],
    )
    def test_oversized_digit_string_returns_none(self, length):
        result = parse_date("9" * length)
        assert result is None, (
            f"parse_date('9'*{length}) returned {result!r} -- a digit "
            "string this long can never represent a real epoch and must "
            "resolve to None (today via OverflowError/ValueError; "
            "the intended contract is an explicit upfront length guard)."
        )

    def test_oversized_digit_string_returns_none_without_interpreter_digit_limit(self):
        """Isolates whether OverflowError ALONE (not CPython's own
        int-string-conversion limit) already protects parse_date() --
        proves the None result for a 50000-digit string is not solely an
        artifact of `sys.get_int_max_str_digits()`.
        """
        original_limit = sys.get_int_max_str_digits()
        sys.set_int_max_str_digits(0)
        try:
            result = parse_date("9" * 50000)
        finally:
            sys.set_int_max_str_digits(original_limit)
        assert result is None, (
            f"parse_date('9'*50000) returned {result!r} with CPython's "
            "int-string-conversion limit disabled -- OverflowError from "
            "datetime.fromtimestamp() alone should still catch this."
        )


# ── BUG-3 (Moriarty): bootstrap --json presents a raw epoch, not a ──────
# ── readable date ─────────────────────────────────────────────────────


class TestBootstrapJsonDateFieldReadableForPresentation:
    """lib/bootstrap_commits.py::scan_recent_commits() never parses its
    "date" field -- it is stored verbatim in each commit dict, and the
    real consumer, bin/git-memory-bootstrap.py --json, documents itself as
    producing "structured output for Claude to present to the user"
    (module docstring). An earlier round of issue #55 wrongly migrated
    this git log call from %aI to %at, leaving a bare epoch digit string
    ("1783538049") in place of a readable ISO-8601 string
    ("2026-07-08T21:06:47+02:00") -- not presentable as-is. Reconciled
    (see this file's module docstring, RECONCILED note): the single
    correct contract for this field is the real %aI string, not %at.

    This is the end-to-end counterpart of
    TestBootstrapCommitsDateFieldContract (which pins the same contract
    directly on scan_recent_commits()) -- this class instead exercises the
    full bin/git-memory-bootstrap.py --json wiring (script invocation +
    JSON serialization), proving the contract survives the entire path a
    real caller uses, not just the library call.
    """

    def test_recent_commit_date_is_real_iso_not_raw_epoch(self, tmp_path):
        repo = _make_repo(tmp_path)
        real_iso = _real_iso_of_head(repo)

        rc, out, err = run_script(BOOTSTRAP, repo, ["--json"])
        assert rc in (0, 1), f"bootstrap.py --json crashed: rc={rc} err={err!r}"
        parsed = json.loads(out)

        commits = parsed.get("commits")
        assert commits and commits.get("recent"), (
            f"test setup error: no commits in --json output -- {parsed!r}"
        )
        got_date = commits["recent"][0]["date"]

        assert got_date == real_iso, (
            "contract not yet met: bootstrap --json's "
            f"commits.recent[0].date is {got_date!r}, expected the real "
            f"readable ISO-8601 date {real_iso!r} from "
            "`git log --pretty=format:%aI` on the same commit. A bare "
            "epoch digit string is not presentable to a user per this "
            "script's own docstring ('structured output for Claude to "
            "present to the user')."
        )


# ── BUG-4 (Moriarty): overflow-future GC commit reported as "never run" ─


class TestDoctorGcNeverRunFalseOnUnparseableFutureDate:
    """bin/git-memory-doctor.py::check_gc_status() -- a real, fsck-clean
    commit backdated to an impossible future date
    (`GIT_AUTHOR_DATE="@253402300800 +0000"`, one second past
    `datetime.max`) makes `parse_date()` correctly return None (caught
    ValueError: "year must be in 1..9999, not 10000"). But
    check_gc_status()'s `if "gc" in subject... and last_gc is None:
    last_gc = date` then binds `last_gc = None` -- and with only ONE gc
    commit in range, `last_gc` stays None for the rest of the scan. The
    result: doctor.py's --json output is byte-for-byte IDENTICAL to a
    repo that never ran GC at all ("never run"), even though a real GC
    commit genuinely exists in history. The unparseable date silently
    erases all trace of the commit instead of being surfaced.
    """

    def test_gc_commit_with_unparseable_future_date_is_not_indistinguishable_from_never_run(
        self, tmp_path
    ):
        # Baseline: a repo with genuinely ZERO gc commits. "never run" is
        # the CORRECT message here -- this is what "never run" is
        # supposed to mean, and proves the fixture/message shape is right
        # before introducing the impossible-date variable.
        baseline_repo = _make_repo(tmp_path, name="baseline")
        parsed_baseline, _ = run_doctor_json(baseline_repo)
        baseline_msg = _find_check(parsed_baseline, "GC")
        assert baseline_msg == "never run", (
            "test setup error: a repo with genuinely zero GC commits "
            f"should say 'never run' -- got {baseline_msg!r}"
        )

        # Repro: one real, fsck-clean GC commit with an impossible future
        # date -- the only GC commit in this repo's history.
        overflow_repo = _make_repo(tmp_path, name="overflow")
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "🔧 chore(memory): gc — 1 items cleaned\n\n"
             "Why: automated memory garbage collection\nResolved-Next: xoverflow55"],
            overflow_repo,
            env={
                "GIT_AUTHOR_DATE": "@253402300800 +0000",
                "GIT_COMMITTER_DATE": "@253402300800 +0000",
            },
        )
        rc_fsck, _, err_fsck = git_cmd(["fsck", "--full"], overflow_repo)
        assert rc_fsck == 0, (
            f"test setup error: overflow-dated commit is not fsck-clean -- "
            f"rc={rc_fsck} err={err_fsck!r} (fixture broken, not the "
            "contract under test)"
        )

        parsed_overflow, _ = run_doctor_json(overflow_repo)
        overflow_msg = _find_check(parsed_overflow, "GC")
        assert overflow_msg != "never run", (
            "contract not yet met: a real, fsck-clean GC commit exists "
            "(backdated to an impossible future date) but doctor.py "
            "reports the exact same 'never run' message as a repo with "
            f"zero GC commits ever -- got {overflow_msg!r}. An unparseable "
            "date must leave some observable trace instead of being "
            "silently indistinguishable from 'GC never ran'."
        )


# ── BUG-5 (Moriarty): negative "days ago" for a future-but-valid date ───


class TestDoctorGcNegativeDaysAgoClamped:
    """bin/git-memory-doctor.py::check_gc_status() line ~266:
    `gc_days_ago = (now - last_gc).days if last_gc else None` has no
    clamp when `last_gc > now`. A real, fsck-clean commit backdated (well,
    forward-dated) to exactly one year in the future produces a NEGATIVE
    `.days` value, surfaced verbatim to the user as
    "last run -365 days ago" -- nonsensical, never a acceptable output
    shape for a diagnostic message.
    """

    def test_future_dated_gc_commit_never_reports_negative_days_ago(self, tmp_path):
        repo = _make_repo(tmp_path)
        future_epoch = int(time.time()) + 365 * 86400
        git_cmd(
            ["commit", "--allow-empty", "-m",
             "🔧 chore(memory): gc — 1 items cleaned\n\n"
             "Why: automated memory garbage collection\nResolved-Next: xfuture55"],
            repo,
            env={
                "GIT_AUTHOR_DATE": f"@{future_epoch} +0000",
                "GIT_COMMITTER_DATE": f"@{future_epoch} +0000",
            },
        )
        rc_fsck, _, err_fsck = git_cmd(["fsck", "--full"], repo)
        assert rc_fsck == 0, (
            f"test setup error: future-dated commit is not fsck-clean -- "
            f"rc={rc_fsck} err={err_fsck!r} (fixture broken, not the "
            "contract under test)"
        )

        parsed, _ = run_doctor_json(repo)
        msg = _find_check(parsed, "GC")
        assert msg is not None, (
            f"test setup error: no 'GC' check in --json output -- "
            f"checks={parsed.get('checks')!r}"
        )
        assert not re.search(r"-\d+\s*days?\s*ago", msg), (
            f"contract not yet met: doctor.py reported a negative "
            f"days-ago figure -- {msg!r}. A future-dated last GC run must "
            "be clamped to a sensible value (e.g. 0) or use a distinct "
            "message, never '-N days ago'."
        )
