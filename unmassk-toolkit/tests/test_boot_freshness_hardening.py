"""
Hardening pass for boot memory freshness (multi-machine, issue #49) — EXHAUSTION
PROTOCOL run, AFTER Ultron's real implementation (wips 98862f1, 578ffc6, 9990410
over Dante's contract 63573e1). The 12-test acceptance contract in
test_boot_freshness.py already proves the 8 plan behaviors end-to-end via full
boot subprocesses; this file drives the individual functions DIRECTLY (unit/
branch/error-path granularity) against the real, already-implemented code:

  - lib/boot_git_checks.py: fetch_memory_ref, get_ahead_behind,
    _format_age_seconds, render_memoria_stamp, _build_pull_directive_lines,
    _has_toolkit_memory
  - lib/boot_memory.py: extract_memory(ref=), resolve_boot_memory,
    _label_remote_provenance, _merge_diverged_memory
  - lib/boot_glossary_cache.py: _resolve_origin_sha, _read_glossary_cache
    (migration: old cache missing the "origin_sha" field)
  - lib/git_helpers.py: run_git's env= kwarg
  - bin/git-memory-commit.py: _check_behind_warn_only

Test surface declaration (EXHAUSTION PROTOCOL step 1): 15 functions, ~45
branches, 15 distinct error/fail-open paths. Excluded from direct testing
here (already covered by the acceptance contract at integration granularity,
or by other pre-existing test files, or out of scope for this feature):
render_branch_section() (full rendering already covered by contract tests
2/3/7), extract_glossary()/_crown_replace() (pre-existing, unrelated to #49),
_write_glossary_cache()/extract_glossary_cached() (I/O orchestration already
covered by test_boot_output.py's TestGlossaryCache; only the NEW
_resolve_origin_sha()/_read_glossary_cache() freshness-key logic is #49's own
surface), _resolve_sanitized_branch() (pre-existing, unchanged by #49).

Direct-call strategy per unmassk-toolkit-python-test-conventions.md /
mock-patterns.md:
  - Pure functions (_format_age_seconds, render_memoria_stamp,
    _build_pull_directive_lines, _label_remote_provenance,
    _merge_diverged_memory, _resolve_origin_sha(None)) — imported and called
    directly, in-process, no git/filesystem needed.
  - Functions taking an explicit project_root/cwd param (fetch_memory_ref,
    _has_toolkit_memory) — called directly with a real tmp_path repo, no
    chdir needed.
  - Functions relying on ambient process cwd (get_ahead_behind, run_git
    calls with no cwd=) — called with `monkeypatch.chdir()`, which pytest
    restores automatically after each test — safe against cross-test bleed.
  - Functions gated by lib/boot_glossary_cache.py's PROCESS-GLOBAL
    `_project_root_cache` (_read_glossary_cache→_get_project_root) — the
    global is explicitly reset to None before each call that needs a
    different repo, exactly like the module's own real callers would see on
    a fresh process (see test_security_regression.py's
    _call_write_glossary_cache_fallback() docstring for the full rationale
    on why this module cannot be safely re-imported under a throwaway name).
  - bin/git-memory-commit.py's _check_behind_warn_only() — hyphenated
    filename, loaded via importlib.util.spec_from_file_location under a
    FRESH throwaway name per call (no stably-named-module risk — each load
    is a brand new module object, safe to monkeypatch `mod.run_git`
    directly).

All git-dependent test setups here use REAL git repos and REAL git
subprocess calls (bare remotes, real clones, real fetches) — no git command
is ever mocked; only git_helpers.run_git is monkeypatched, and only in the
handful of tests that specifically need to inject a malformed/unexpected
return value or an exception to prove a fail-open path (documented inline
each time, per unmassk-standards §34 / this project's own anti-fixture-
fabrication conventions).

Build mode: test-first, hardening pass (Flow Verify / step 5). No production
code is touched by this file. One genuine bug was found while writing these
tests (get_ahead_behind's non-numeric-token path) — reported via an
`xfail(strict=True)` test, NOT fixed here (Absolute Prohibition #4 — Ultron
fixes, Dante reports).
"""

import importlib.util
import json
import os
import subprocess
import sys
import time

import pytest

from conftest import BIN_DIR, LIB_DIR, run_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import boot_git_checks
import boot_glossary_cache
import boot_memory
import git_helpers
from constants import MEMORY_TYPES
from parsing import sanitize_trailer_value, scan_trailers_memory

from test_boot_freshness import (
    BOOT_HOOK,
    COMMIT_SCRIPT,
    WINDOWS,
    _clone_machine_b,
    _commit_real,
    _git,
    _line_with,
    _make_fake_git,
    _push_commits_from_b,
    _read_fake_git_log,
    _run_boot_combined,
    _setup_freshness_repo,
)

COMMIT_SCRIPT_PATH = os.path.join(BIN_DIR, "git-memory-commit.py")


# ── Shared helpers ───────────────────────────────────────────────────────


def _make_gated_repo(tmp_path, name="gated_repo"):
    """Minimal repo satisfying _has_toolkit_memory()'s gate via manifest.json
    only — lighter than test_boot_freshness.py's _setup_freshness_repo()
    (which also runs the full installer) since these tests call
    fetch_memory_ref()/_has_toolkit_memory() directly and never render a
    full boot.
    """
    repo = str(tmp_path / name)
    os.makedirs(repo)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "a@test.com"], repo)
    _git(["config", "user.name", "A"], repo)
    _git(["commit", "--allow-empty", "-m", "init"], repo)
    unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
    os.makedirs(unmassk_dir, exist_ok=True)
    with open(os.path.join(unmassk_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"version": "1.0.0"}, f)
    return repo


def _add_bare_remote(repo, tmp_path, name="bare.git"):
    bare = str(tmp_path / name)
    subprocess.run(["git", "init", "--bare", "-b", "main", bare], capture_output=True, check=True)
    _git(["remote", "add", "origin", bare], repo)
    _git(["push", "-u", "origin", "main"], repo)
    return bare


def _load_commit_module():
    """Fresh throwaway load of bin/git-memory-commit.py (hyphenated
    filename — importlib pattern per unmassk-toolkit-python-test-
    conventions.md). A brand-new module object every call, unlike
    lib/boot_memory.py & co. — no stably-named-module contamination risk,
    safe to monkeypatch `mod.run_git` directly per test.
    """
    spec = importlib.util.spec_from_file_location(
        "git_memory_commit_hardening_probe", COMMIT_SCRIPT_PATH
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ── fetch_memory_ref: every status branch + timeout + exception ─────────


class TestFetchMemoryRefStates:
    """lib/boot_git_checks.py:fetch_memory_ref() — direct calls (real
    project_root param, no chdir needed) covering every one of its 5
    documented `status` values plus the two paths that only the docstring
    promises ("never raises"): an unexpected exception, and a real hung
    fetch bounded by FETCH_TIMEOUT_SECONDS. All confirmed empirically
    against the real function before being written as assertions (session
    2026-07-06 hardening pass).
    """

    def test_no_toolkit_memory_returns_skipped_gate(self, tmp_path):
        repo = str(tmp_path / "no_memory_repo")
        os.makedirs(repo)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "a@test.com"], repo)
        _git(["config", "user.name", "A"], repo)
        _git(["commit", "--allow-empty", "-m", "init"], repo)

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result == {"status": "skipped_gate", "age_seconds": None}

    def test_none_project_root_returns_skipped_gate(self):
        result = boot_git_checks.fetch_memory_ref(None)
        assert result == {"status": "skipped_gate", "age_seconds": None}

    def test_no_remote_configured_returns_no_remote(self, tmp_path):
        repo = _make_gated_repo(tmp_path)
        result = boot_git_checks.fetch_memory_ref(repo)
        assert result == {"status": "no_remote", "age_seconds": None}

    def test_detached_head_returns_failed(self, tmp_path):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        head_sha = _git(["rev-parse", "HEAD"], repo).stdout.strip()
        _git(["checkout", head_sha], repo)
        assert _git(["branch", "--show-current"], repo).stdout.strip() == ""

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result == {"status": "failed", "age_seconds": None}

    def test_successful_fetch_returns_fetched_with_zero_age(self, tmp_path):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result == {"status": "fetched", "age_seconds": 0.0}
        assert os.path.isfile(os.path.join(repo, ".git", "FETCH_HEAD"))

    def test_immediate_second_call_is_rate_limited(self, tmp_path):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)

        first = boot_git_checks.fetch_memory_ref(repo)
        assert first["status"] == "fetched"

        second = boot_git_checks.fetch_memory_ref(repo)
        assert second["status"] == "rate_limited"
        assert second["age_seconds"] is not None
        assert second["age_seconds"] < boot_git_checks.FETCH_RATE_LIMIT_SECONDS

    @staticmethod
    def _own_stamp_path(repo):
        """v1->v2 RE-BASE (issue #60 AMENDMENT v2, decision 90d096d):
        every test below that used to os.utime() .git/FETCH_HEAD now
        targets this file instead — the boot's own success stamp is the
        SOLE age/rate-limit source since v2. The remote/branch identity
        stored in the stamp (still "origin"/"main" throughout this class'
        seeding helper, `_add_bare_remote`) keeps matching across every
        test here, so aging the file's mtime alone is a faithful re-seed
        of "how long ago was the last confirmed successful sync",
        unchanged in semantic from the old FETCH_HEAD-mtime mechanic.
        """
        return os.path.join(repo, ".claude", ".unmassk", "boot-fetch-stamp.json")

    def test_stale_fetch_head_past_window_allows_refetch(self, tmp_path):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        boot_git_checks.fetch_memory_ref(repo)  # seed the own stamp

        stamp_path = self._own_stamp_path(repo)
        assert os.path.isfile(stamp_path), "seeding call must have written the own stamp"
        stale_time = time.time() - (boot_git_checks.FETCH_RATE_LIMIT_SECONDS + 60)
        os.utime(stamp_path, (stale_time, stale_time))

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result["status"] == "fetched"

    def test_age_just_inside_window_is_rate_limited(self, tmp_path):
        """Issue #60 hardening gap: no existing test pins the EXACT
        rate-limit boundary (`0 <= age < FETCH_RATE_LIMIT_SECONDS` in
        `_check_own_stamp_rate_limit`). Existing coverage only exercises
        age~0s ("immediate second call") and age=window+60s (comfortably
        stale) — never the two seconds straddling the literal edge. 299s
        (one second inside the 300s window) must still rate-limit, and
        the resulting stamp must carry the "remote (synced ... ago)"
        wording issue #60 introduced — not just the right status field.
        """
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        boot_git_checks.fetch_memory_ref(repo)  # seed a real own stamp

        stamp_path = self._own_stamp_path(repo)
        assert os.path.isfile(stamp_path), "seeding call must have written the own stamp"
        just_inside = time.time() - (boot_git_checks.FETCH_RATE_LIMIT_SECONDS - 1)  # 299s old
        os.utime(stamp_path, (just_inside, just_inside))

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result["status"] == "rate_limited", (
            f"299s (one second inside the {boot_git_checks.FETCH_RATE_LIMIT_SECONDS}s "
            f"window) must still rate-limit. Got: {result}"
        )
        assert result["age_seconds"] is not None
        assert result["age_seconds"] < boot_git_checks.FETCH_RATE_LIMIT_SECONDS

        stamp = boot_git_checks.render_memoria_stamp(result)
        assert stamp.startswith("MEMORY: remote (synced "), stamp
        assert "LOCAL" not in stamp and "skipped" not in stamp

    def test_age_just_outside_window_forces_refetch(self, tmp_path):
        """301s old (one second past the 300s window) must NOT rate-limit
        — a real refetch is attempted; since the remote is still live it
        succeeds, flipping status back to 'fetched'. Complements the 299s
        boundary test above — together they pin both sides of the literal
        `< FETCH_RATE_LIMIT_SECONDS` edge, which no prior test exercised
        this tightly.
        """
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        boot_git_checks.fetch_memory_ref(repo)  # seed a real own stamp

        stamp_path = self._own_stamp_path(repo)
        assert os.path.isfile(stamp_path), "seeding call must have written the own stamp"
        just_outside = time.time() - (boot_git_checks.FETCH_RATE_LIMIT_SECONDS + 1)  # 301s old
        os.utime(stamp_path, (just_outside, just_outside))

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result["status"] == "fetched", (
            f"301s (one second past the {boot_git_checks.FETCH_RATE_LIMIT_SECONDS}s "
            f"window) must trigger a real refetch, not stay rate-limited. Got: {result}"
        )

    def test_fetch_failure_returns_failed_with_prior_age(self, tmp_path):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        boot_git_checks.fetch_memory_ref(repo)  # seed a real own stamp first

        # Deterministic, no-network failure — same technique as the
        # acceptance contract's fetch-failed test: point origin at a path
        # that never existed. The remote NAME stays "origin" (only its URL
        # changes), so the stamp's stored identity still matches and its
        # age is genuinely preserved through the failed refetch below.
        _git(["remote", "set-url", "origin", str(tmp_path / "does-not-exist.git")], repo)
        stamp_path = self._own_stamp_path(repo)
        assert os.path.isfile(stamp_path), "seeding call must have written the own stamp"
        stale_time = time.time() - (boot_git_checks.FETCH_RATE_LIMIT_SECONDS + 60)
        os.utime(stamp_path, (stale_time, stale_time))

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result["status"] == "failed"
        assert result["age_seconds"] is not None  # prior successful fetch's age, preserved

    def test_unexpected_exception_is_caught_and_returns_failed(self, tmp_path, monkeypatch):
        """The outer `except Exception` in fetch_memory_ref() must catch
        ANY unexpected failure from its own run_git() calls, not just
        ordinary non-zero exit codes. Poisons git_helpers.run_git itself
        (the real module attribute — fetch_memory_ref's `from git_helpers
        import run_git` is a deferred, function-body import, so this takes
        effect immediately) to simulate a cause the gate/rate-limit checks
        can't anticipate.
        """
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)

        def _raise(*_args, **_kwargs):
            raise RuntimeError("simulated unexpected failure")

        monkeypatch.setattr(git_helpers, "run_git", _raise)

        result = boot_git_checks.fetch_memory_ref(repo)
        assert result == {"status": "failed", "age_seconds": None}

    @pytest.mark.skipif(WINDOWS, reason="fake-git PATH-shadowing needs a POSIX-executable named exactly 'git'")
    def test_hung_fetch_is_bounded_by_timeout_and_returns_failed(self, tmp_path, monkeypatch):
        """Direct-call complement to the acceptance contract's full-boot
        hardening test: proves fetch_memory_ref() ITSELF is responsible for
        the bounded timeout (not something downstream in session-start-
        boot.py papering over a hang), by calling it directly with a fake
        `git` that hangs on `fetch` for far longer than FETCH_TIMEOUT_SECONDS.
        """
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)

        log_path = str(tmp_path / "fake_git_log.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        monkeypatch.setenv("PATH", fake_bin + os.pathsep + os.environ.get("PATH", ""))
        # Must safely OUTLAST FETCH_TIMEOUT_SECONDS, or the fake fetch just
        # finishes on its own (fake git exits 0 after its sleep) before
        # run_git's own timeout ever fires — proving nothing about the
        # timeout itself. The process gets killed at ~FETCH_TIMEOUT_SECONDS
        # regardless of how long this is set to, so a large margin costs
        # nothing in wall-clock time.
        monkeypatch.setenv(
            "FAKE_GIT_FETCH_HANG_SECONDS", str(boot_git_checks.FETCH_TIMEOUT_SECONDS + 20)
        )

        start = time.monotonic()
        result = boot_git_checks.fetch_memory_ref(repo)
        elapsed = time.monotonic() - start

        assert result["status"] == "failed"
        assert elapsed < boot_git_checks.FETCH_TIMEOUT_SECONDS + 5, (
            f"fetch_memory_ref took {elapsed:.1f}s — timeout not bounding the hang "
            f"(expected bound ~{boot_git_checks.FETCH_TIMEOUT_SECONDS}s)"
        )

        records = _read_fake_git_log(log_path)
        fetch_records = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert fetch_records, "the fake git was never invoked for fetch — cannot verify the timeout was exercised"


# ── _read_own_stamp_age: malformed-evidence PINNING (Cerberus S3, round 3) ──


class TestReadOwnStampAgeDirectCalls:
    """Cerberus S3 (round 3, decision 787b698): `_read_own_stamp_age()`
    already promises, in its own docstring, to collapse several malformed-
    evidence shapes to None — corrupt JSON, wrong top-level shape (not a
    dict), a symlink planted at the stamp path, a hard link at the stamp
    path — but nothing pinned those promises directly before this pass.

    All 4 tests are PINNING, not contract: they are expected to be GREEN
    from the very first run. The underlying guards already exist in the
    code as written — json.loads()'s ValueError, the isinstance(dict)
    check, and open_no_follow_symlink()'s O_NOFOLLOW +
    reject_hardlinks=True. This class exists so a future regression in any
    of those guards fails loudly here, at the unit level, instead of only
    being noticed indirectly through a full-boot behavior test.

    Direct calls, no chdir/subprocess needed — _read_own_stamp_age()
    takes an explicit project_root and doesn't touch git at all, so a
    plain directory (not even a git repo) is sufficient.
    """

    @staticmethod
    def _stamp_repo(tmp_path, name="stamp_repo"):
        repo = str(tmp_path / name)
        unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
        os.makedirs(unmassk_dir, exist_ok=True)
        return repo, os.path.join(unmassk_dir, boot_git_checks._OWN_STAMP_FILENAME)

    def test_corrupt_json_returns_none(self, tmp_path):
        repo, stamp_path = self._stamp_repo(tmp_path)
        with open(stamp_path, "w", encoding="utf-8") as f:
            f.write("{not valid json::")

        age = boot_git_checks._read_own_stamp_age(repo, "origin", "main")
        assert age is None

    def test_wrong_shape_list_returns_none(self, tmp_path):
        repo, stamp_path = self._stamp_repo(tmp_path)
        with open(stamp_path, "w", encoding="utf-8") as f:
            json.dump(["origin", "main"], f)

        age = boot_git_checks._read_own_stamp_age(repo, "origin", "main")
        assert age is None

    def test_symlink_planted_returns_none(self, tmp_path):
        repo, stamp_path = self._stamp_repo(tmp_path)
        victim = tmp_path / "victim_stamp.json"
        victim.write_text(
            json.dumps(
                {
                    "schema_version": boot_git_checks._OWN_STAMP_SCHEMA_VERSION,
                    "remote": "origin",
                    "branch": "main",
                }
            ),
            encoding="utf-8",
        )
        if os.path.lexists(stamp_path):
            os.remove(stamp_path)
        try:
            os.symlink(str(victim), stamp_path)
        except OSError:
            pytest.skip("real symlink privilege not available in this environment")

        age = boot_git_checks._read_own_stamp_age(repo, "origin", "main")
        assert age is None

    def test_hard_link_returns_none(self, tmp_path):
        repo, stamp_path = self._stamp_repo(tmp_path)
        victim = tmp_path / "victim_stamp_hardlink.json"
        victim.write_text(
            json.dumps(
                {
                    "schema_version": boot_git_checks._OWN_STAMP_SCHEMA_VERSION,
                    "remote": "origin",
                    "branch": "main",
                }
            ),
            encoding="utf-8",
        )
        try:
            os.link(str(victim), stamp_path)
        except OSError:
            pytest.skip("hard-link creation not available in this environment (e.g. cross-device tmp_path)")

        age = boot_git_checks._read_own_stamp_age(repo, "origin", "main")
        assert age is None


# ── get_ahead_behind: every branch, including one genuine bug found ──────


class TestGetAheadBehind:
    """lib/boot_git_checks.py:get_ahead_behind() — real repos wherever git
    state matters; the two guard-clause cases (no branch / detached-HEAD
    sentinel) are pure and need no repo at all.
    """

    def test_no_branch_short_circuits_without_git_call(self):
        assert boot_git_checks.get_ahead_behind("") == (0, 0, None)

    def test_detached_head_sentinel_short_circuits(self):
        assert boot_git_checks.get_ahead_behind("(detached HEAD)") == (0, 0, None)

    def test_no_upstream_configured_returns_zero_zero_none(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)  # no remote at all
        monkeypatch.chdir(repo)
        assert boot_git_checks.get_ahead_behind("main") == (0, 0, None)

    def test_upstream_tracking_ref_deleted_collapses_to_no_upstream(self, tmp_path, monkeypatch):
        """Confirmed empirically (session 2026-07-06): deleting the
        remote-tracking ref file while the branch's remote/merge config
        stays intact makes `git rev-parse --abbrev-ref @{u}` itself fail
        (exit 128, "unknown revision") — get_ahead_behind() can't
        distinguish this from "no upstream at all" because both hit the
        same `code_ref != 0` branch, and that is the correct, safe
        collapse (never crashes, never reports fake ahead/behind numbers).
        """
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        monkeypatch.chdir(repo)
        assert boot_git_checks.get_ahead_behind("main")[2] == "origin/main"  # sanity baseline

        ref_path = os.path.join(repo, ".git", "refs", "remotes", "origin", "main")
        os.remove(ref_path)

        assert boot_git_checks.get_ahead_behind("main") == (0, 0, None)

    def test_real_ahead_behind_counts(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, 2)
        _git(["fetch", "origin"], repo_a)
        monkeypatch.chdir(repo_a)

        assert boot_git_checks.get_ahead_behind("main") == (0, 2, "origin/main")

    def test_non_numeric_rev_list_output_should_fail_open_but_raises(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        monkeypatch.chdir(repo_a)

        real_run_git = git_helpers.run_git

        def _fake_run_git(args, timeout=10, cwd=None, env=None):
            if args and args[0] == "rev-list" and "--left-right" in args:
                return 0, "abc def"
            return real_run_git(args, timeout=timeout, cwd=cwd, env=env)

        monkeypatch.setattr(git_helpers, "run_git", _fake_run_git)

        result = boot_git_checks.get_ahead_behind("main")
        assert result == (0, 0, "origin/main")


# ── _format_age_seconds: pure boundary cases ─────────────────────────────


class TestFormatAgeSeconds:
    @pytest.mark.parametrize(
        "seconds, expected",
        [
            (0, "0s"),
            (59, "59s"),
            (60, "1min"),
            (3599, "59min"),
            (3600, "1h"),
            (-100, "0s"),  # clock skew: mtime in the future clamps to 0, never negative
        ],
    )
    def test_boundaries(self, seconds, expected):
        assert boot_git_checks._format_age_seconds(seconds) == expected


# ── render_memoria_stamp: 5 states x boundary ages ───────────────────────


class TestRenderMemoriaStamp:
    @pytest.mark.parametrize(
        "fetch_state, expected",
        [
            ({"status": "fetched", "age_seconds": 0.0}, "MEMORY: remote (fetched 0s ago)"),
            ({"status": "fetched", "age_seconds": None}, "MEMORY: remote (fetched 0s ago)"),
            ({"status": "fetched", "age_seconds": 125.0}, "MEMORY: remote (fetched 2min ago)"),
            # Issue #60 relabel: rate-limited means "memory is fresh, FETCH_HEAD
            # < 300s old" — a GOOD state, not a failure. Must read as "remote"
            # (not "LOCAL") and never use the word "skipped" (reads as failure).
            ({"status": "rate_limited", "age_seconds": 45.0}, "MEMORY: remote (synced 45s ago)"),
            ({"status": "rate_limited", "age_seconds": None}, "MEMORY: remote (synced ? ago)"),
            ({"status": "skipped_gate", "age_seconds": None}, "MEMORY: LOCAL — unverified (never synced with origin)"),
            ({"status": "skipped_gate", "age_seconds": 500.0}, "MEMORY: LOCAL — last fetch 8min ago, unverified"),
            ({"status": "no_remote", "age_seconds": 7300.0}, "MEMORY: LOCAL — last fetch 2h ago, unverified"),
            ({"status": "failed", "age_seconds": 3600.0}, "MEMORY: LOCAL — last fetch 1h ago, unverified"),
            ({"status": "totally_unknown_future_status", "age_seconds": None}, "MEMORY: LOCAL — unverified (never synced with origin)"),
            ({"status": "totally_unknown_future_status", "age_seconds": 10.0}, "MEMORY: LOCAL — last fetch 10s ago, unverified"),
        ],
    )
    def test_states_and_ages(self, fetch_state, expected):
        assert boot_git_checks.render_memoria_stamp(fetch_state) == expected


# ── _build_pull_directive_lines: dirty vs clean ──────────────────────────


class TestBuildPullDirectiveLines:
    def test_dirty_tree_warns_and_does_not_propose_first_action(self):
        lines = boot_git_checks._build_pull_directive_lines(7, is_dirty=True)
        assert len(lines) == 1
        assert "7" in lines[0]
        assert "DIRTY" in lines[0]
        assert "do NOT pull" in lines[0]
        assert "FIRST action" not in lines[0]

    def test_clean_tree_proposes_pull_as_first_action(self):
        lines = boot_git_checks._build_pull_directive_lines(3, is_dirty=False)
        assert len(lines) == 1
        assert "3" in lines[0]
        assert "FIRST action" in lines[0]
        assert "git pull" in lines[0]
        assert "DIRTY" not in lines[0]


# ── _has_toolkit_memory: every gate signal ───────────────────────────────


class TestHasToolkitMemory:
    def test_manifest_present_is_sufficient(self, tmp_path):
        repo = str(tmp_path / "r1")
        os.makedirs(os.path.join(repo, ".claude", ".unmassk"))
        with open(os.path.join(repo, ".claude", ".unmassk", "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"version": "1.0.0"}, f)
        assert boot_git_checks._has_toolkit_memory(repo) is True

    def test_claude_md_marker_without_manifest_is_sufficient(self, tmp_path):
        repo = str(tmp_path / "r2")
        os.makedirs(repo)
        with open(os.path.join(repo, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write("<!-- BEGIN unmassk-toolkit -->\nfoo\n<!-- END unmassk-toolkit -->\n")
        assert boot_git_checks._has_toolkit_memory(repo) is True

    def test_claude_md_without_marker_is_insufficient(self, tmp_path):
        repo = str(tmp_path / "r3")
        os.makedirs(repo)
        with open(os.path.join(repo, "CLAUDE.md"), "w", encoding="utf-8") as f:
            f.write("just some project notes\n")
        assert boot_git_checks._has_toolkit_memory(repo) is False

    def test_neither_signal_present_is_false(self, tmp_path):
        repo = str(tmp_path / "r4")
        os.makedirs(repo)
        assert boot_git_checks._has_toolkit_memory(repo) is False

    def test_symlinked_claude_md_is_treated_as_absent(self, tmp_path, real_symlink_capable):
        """SEC guard reused from needs_install()'s own pattern: a symlinked
        CLAUDE.md must never be followed to decide the fetch gate.
        """
        repo = str(tmp_path / "r5")
        os.makedirs(repo)
        victim = tmp_path / "victim.md"
        victim.write_text("<!-- BEGIN unmassk-toolkit -->\nfoo\n<!-- END unmassk-toolkit -->\n", encoding='utf-8')
        os.symlink(str(victim), os.path.join(repo, "CLAUDE.md"))
        assert boot_git_checks._has_toolkit_memory(repo) is False


# ── _fetch_head_age_seconds ───────────────────────────────────────────────


# _fetch_head_age_seconds() REMOVED (issue #60 AMENDMENT v2, decision
# 90d096d, session 2026-07-10): its only two callers in lib/boot_git_checks.py
# — the old FETCH_HEAD-mtime rate-limit gate and the "fetched" status's
# fresh_age re-measurement — were both replaced by the own-success-stamp
# mechanism (_read_own_stamp_age() / _write_own_stamp() /
# _check_own_stamp_rate_limit()), leaving the helper with zero real callers
# anywhere in the codebase (confirmed via grep). Per the plan's explicit
# instruction ("si queda sin usos reales, elimínala — nada de código
# muerto"), the function itself and this TestFetchHeadAgeSeconds class
# (its only remaining reference) were deleted together, not just stopped
# being called. No replacement test needed: the new stamp helpers'
# equivalent missing/fresh-file behavior is already covered end-to-end by
# TestFetchMemoryRefStates above and the acceptance contract's
# TestOwnSuccessStampNotFetchHeadMtime in test_boot_freshness.py.


# ── extract_memory(ref=): nonexistent ref fails open ─────────────────────


class TestExtractMemoryRefParam:
    def test_nonexistent_ref_returns_empty_dict_no_traceback(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)
        monkeypatch.chdir(repo)

        result = boot_memory.extract_memory(ref="totally-nonexistent-ref-xyz-9f2a")
        assert result == {}


# ── resolve_boot_memory: every ahead/behind combination ──────────────────


class TestResolveBootMemory:
    def test_no_upstream_reads_local_head(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)
        marker = "RESOLVE-NO-UPSTREAM-MARKER"
        _commit_real(repo, "context", "freshness", "local only", {"Next": marker})
        monkeypatch.chdir(repo)

        result = boot_memory.resolve_boot_memory(0, 0, None)
        assert any(marker in item["display"] for item in result.get("pending", []))
        assert "[source: remote]" not in json.dumps(result.get("pending", []))

    def test_up_to_date_with_upstream_reads_local_head_unlabeled(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        marker = "RESOLVE-UP-TO-DATE-MARKER"
        _commit_real(repo_a, "context", "freshness", "a up to date", {"Next": marker})
        _git(["push", "origin", "main"], repo_a)
        monkeypatch.chdir(repo_a)

        result = boot_memory.resolve_boot_memory(0, 0, "origin/main")
        assert any(marker in item["display"] for item in result.get("pending", []))
        assert "[source: remote]" not in json.dumps(result.get("pending", []))

    def test_strictly_ahead_reads_local_head_unlabeled(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        marker = "RESOLVE-AHEAD-MARKER"
        _commit_real(repo, "context", "freshness", "unpushed ahead commit", {"Next": marker})
        monkeypatch.chdir(repo)

        result = boot_memory.resolve_boot_memory(1, 0, "origin/main")
        assert any(marker in item["display"] for item in result.get("pending", []))
        assert "[source: remote]" not in json.dumps(result.get("pending", []))

    def test_strictly_behind_reads_and_labels_remote_head(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        marker = "RESOLVE-BEHIND-MARKER"
        _push_commits_from_b(repo_b, 1, next_marker=marker)
        _git(["fetch", "origin"], repo_a)
        monkeypatch.chdir(repo_a)

        result = boot_memory.resolve_boot_memory(0, 1, "origin/main")
        matches = [item for item in result.get("pending", []) if marker in item["display"]]
        assert matches, f"expected {marker} in {result.get('pending')}"
        assert "[source: remote]" in matches[0]["display"]

    def test_diverged_reads_and_labels_both_sides(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        local_marker = "RESOLVE-DIVERGED-LOCAL-MARKER"
        remote_marker = "RESOLVE-DIVERGED-REMOTE-MARKER"
        _commit_real(repo_a, "context", "freshness", "a's unpushed", {"Next": local_marker})
        _push_commits_from_b(repo_b, 1, next_marker=remote_marker)
        _git(["fetch", "origin"], repo_a)
        monkeypatch.chdir(repo_a)

        result = boot_memory.resolve_boot_memory(1, 1, "origin/main")
        pending_display = [item["display"] for item in result.get("pending", [])]
        local_matches = [d for d in pending_display if local_marker in d]
        remote_matches = [d for d in pending_display if remote_marker in d]
        assert local_matches and "[source: remote]" not in local_matches[0]
        assert remote_matches and "[source: remote]" in remote_matches[0]


# ── _label_remote_provenance: empty / anti-spoof / unicode ───────────────


class TestLabelRemoteProvenance:
    def test_empty_dict_returns_empty_dict(self):
        assert boot_memory._label_remote_provenance({}) == {}

    def test_content_already_containing_label_still_gets_labeled_again(self):
        """Anti-spoof guard-shape check: the function unconditionally
        appends REMOTE_PROVENANCE_LABEL — it never skips labeling just
        because the source text happens to already contain that substring
        (e.g. a malicious commit's own Next: text). This proves the label
        can never be silently dropped/deduped in a way that would let
        already-remote content pass through UNLABELED — only that it may
        (harmlessly, cosmetically) be duplicated.
        """
        already_labeled = {
            "last_context": "abc123 msg" + boot_memory.REMOTE_PROVENANCE_LABEL,
            "pending": [],
            "blockers": [],
            "decisions": [],
            "memos": [],
            "remembers": [],
            "tombstones": set(),
        }
        result = boot_memory._label_remote_provenance(already_labeled)
        assert result["last_context"].count(boot_memory.REMOTE_PROVENANCE_LABEL.strip()) == 2
        assert result["last_context"].startswith("abc123 msg")

    def test_unicode_content_survives_labeling(self):
        memory = {
            "last_context": "café \U0001F600 sha123",
            "pending": [],
            "blockers": [],
            "decisions": [],
            "memos": [],
            "remembers": [],
            "tombstones": set(),
        }
        result = boot_memory._label_remote_provenance(memory)
        assert result["last_context"] == "café \U0001F600 sha123" + boot_memory.REMOTE_PROVENANCE_LABEL


# ── _merge_diverged_memory: empty-side combinations ──────────────────────


class TestMergeDivergedMemory:
    _EMPTY = {"pending": [], "blockers": [], "decisions": [], "memos": [], "remembers": [], "tombstones": set()}

    def _full(self, tag):
        return {
            "pending": [{"sha": tag, "scope": "s", "text": tag, "display": f"{tag}: t", "issue": None, "timestamp": 0}],
            "blockers": [f"{tag}-blocker"],
            "decisions": [(f"({tag})", f"{tag}-decision", False)],
            "memos": [],
            "remembers": [],
            "tombstones": set(),
        }

    def test_both_empty_produces_empty_merge(self):
        merged = boot_memory._merge_diverged_memory(dict(self._EMPTY), dict(self._EMPTY))
        assert merged["pending"] == []
        assert merged["blockers"] == []
        assert merged["decisions"] == []

    def test_local_empty_remote_full_labels_only_remote_side(self):
        merged = boot_memory._merge_diverged_memory(dict(self._EMPTY), self._full("R"))
        assert len(merged["pending"]) == 1
        assert boot_memory.REMOTE_PROVENANCE_LABEL in merged["pending"][0]["display"]
        assert boot_memory.REMOTE_PROVENANCE_LABEL in merged["blockers"][0]
        assert boot_memory.REMOTE_PROVENANCE_LABEL in merged["decisions"][0][1]

    def test_local_full_remote_empty_keeps_local_unlabeled(self):
        merged = boot_memory._merge_diverged_memory(self._full("L"), dict(self._EMPTY))
        assert len(merged["pending"]) == 1
        assert boot_memory.REMOTE_PROVENANCE_LABEL not in merged["pending"][0]["display"]
        assert boot_memory.REMOTE_PROVENANCE_LABEL not in merged["blockers"][0]


# ── _crown_replace: same-scope duplicates (Cerberus, issue #49 repair) ───


class TestCrownReplaceMultiMatch:
    """_crown_replace() used to replace only the FIRST non-crowned match for
    a scope and return immediately, leaving any LATER duplicate for the same
    scope stale. Within a single extract_memory()/extract_glossary() call
    this was always equivalent to "there is only one match" (decision_scopes/
    memo_scopes dedupe per scope before crown-replace ever runs) — but
    resolve_boot_memory()'s diverged case (_merge_diverged_memory()
    concatenates local's list with the remote-labeled side's list) CAN
    legitimately produce two entries sharing the same scope label. A crown
    must beat EVERY non-crowned entry for its scope, not just the first one
    encountered.
    """

    def test_replaces_first_match_and_drops_later_duplicate_for_same_scope(self):
        entries = [
            ("(auth)", "local stale text", False),
            ("(auth)", "remote stale text [source: remote]", False),
            ("(other)", "untouched", False),
        ]
        boot_memory._crown_replace(entries, "(auth)", "crowned text")

        assert entries == [
            ("(auth)", "crowned text", True),
            ("(other)", "untouched", False),
        ]

    def test_no_match_leaves_entries_untouched(self):
        entries = [("(other)", "untouched", False)]
        boot_memory._crown_replace(entries, "(auth)", "crowned text")
        assert entries == [("(other)", "untouched", False)]

    def test_single_match_still_replaces_in_place(self):
        entries = [("(auth)", "old", False), ("(other)", "x", False)]
        boot_memory._crown_replace(entries, "(auth)", "new crowned")
        assert entries == [("(auth)", "new crowned", True), ("(other)", "x", False)]

    def test_tombstoned_crown_text_is_a_no_op_even_with_duplicates(self):
        from parsing import normalize

        entries = [("(memo1)", "a", False), ("(memo1)", "b", False)]
        tombstones = {normalize("retired crowned text")}
        boot_memory._crown_replace(entries, "(memo1)", "retired crowned text", tombstones)
        assert entries == [("(memo1)", "a", False), ("(memo1)", "b", False)]

    def test_existing_crowned_entry_for_scope_is_never_touched(self):
        """A THIRD entry for the same scope that is already crowned must be
        left alone by both branches (it doesn't match `not ris_crown`) —
        crown-replace only ever contests non-crowned duplicates.
        """
        entries = [
            ("(auth)", "already crowned", True),
            ("(auth)", "stale non-crowned", False),
        ]
        boot_memory._crown_replace(entries, "(auth)", "new crowned text")
        assert entries == [
            ("(auth)", "already crowned", True),
            ("(auth)", "new crowned text", True),
        ]


# ── _resolve_origin_sha: freshness key ignores local HEAD, tracks origin ──


class TestResolveOriginSha:
    def test_none_upstream_returns_none(self):
        assert boot_glossary_cache._resolve_origin_sha(None) is None

    def test_changes_when_origin_advances_but_local_head_unchanged(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        monkeypatch.chdir(repo_a)

        sha_before = boot_glossary_cache._resolve_origin_sha("origin/main")
        head_before = _git(["rev-parse", "HEAD"], repo_a).stdout.strip()

        _git(["commit", "--allow-empty", "-m", "chore: b advances origin"], repo_b)
        _git(["push", "origin", "main"], repo_b)
        _git(["fetch", "origin"], repo_a)

        sha_after = boot_glossary_cache._resolve_origin_sha("origin/main")
        head_after = _git(["rev-parse", "HEAD"], repo_a).stdout.strip()

        assert head_after == head_before, "test setup error: local HEAD must not move"
        assert sha_after != sha_before, "origin_sha must change when origin advances"


# ── _read_glossary_cache: migration (old cache missing origin_sha) ───────


class TestReadGlossaryCacheMigration:
    """Issue #49 added an `origin_sha` field to the cache schema without
    bumping schema_version (still 1). A cache written by the PRE-#49 code
    (no `origin_sha` key at all) must not crash the reader — and must stay
    valid exactly when the new field's absence doesn't actually create a
    mismatch (no upstream configured, matching cache.get(...) defaulting to
    None), while correctly going stale (never crashing) once a real
    upstream now resolves to a real sha the old cache never recorded.
    """

    def _write_old_style_cache(self, repo, head_sha):
        from datetime import datetime, timezone

        cache_dir = os.path.join(repo, ".claude", ".unmassk")
        os.makedirs(cache_dir, exist_ok=True)
        old_cache = {
            "schema_version": 1,
            "head_sha": head_sha,
            # Deliberately no "origin_sha" key — pre-#49 cache shape.
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "decisions": [],
            "memos": [],
            "remembers": [],
            "tombstones": [],
        }
        with open(os.path.join(cache_dir, "glossary-cache.json"), "w", encoding="utf-8") as f:
            json.dump(old_cache, f)

    def test_old_cache_without_origin_sha_stays_valid_when_no_upstream(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)
        monkeypatch.chdir(repo)
        boot_glossary_cache._project_root_cache = None
        head_sha = _git(["rev-parse", "HEAD"], repo).stdout.strip()
        self._write_old_style_cache(repo, head_sha)

        result = boot_glossary_cache._read_glossary_cache(upstream_ref=None)
        assert result is not None, "an old cache with no upstream configured must still validate"

    def test_old_cache_without_origin_sha_becomes_stale_not_crash_once_upstream_exists(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)
        monkeypatch.chdir(repo)
        boot_glossary_cache._project_root_cache = None
        head_sha = _git(["rev-parse", "HEAD"], repo).stdout.strip()
        self._write_old_style_cache(repo, head_sha)

        _add_bare_remote(repo, tmp_path)
        boot_glossary_cache._project_root_cache = None

        result = boot_glossary_cache._read_glossary_cache(upstream_ref="origin/main")
        assert result is None, "a cache missing origin_sha must be treated as stale once a real upstream resolves"


# ── run_git env kwarg: additive merge, no os.environ mutation ────────────


class TestRunGitEnvKwarg:
    def _make_repo(self, tmp_path):
        repo = str(tmp_path / "envkwarg_repo")
        os.makedirs(repo)
        subprocess.run(["git", "init", "-q", "-b", "main", repo], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.email", "a@test.com"], check=True)
        subprocess.run(["git", "-C", repo, "config", "user.name", "A"], check=True)
        subprocess.run(["git", "-C", repo, "commit", "-q", "--allow-empty", "-m", "init"], check=True)
        return repo

    def test_env_kwarg_never_mutates_real_os_environ(self, tmp_path):
        repo = self._make_repo(tmp_path)
        sentinel = "UNMASSK_TEST_ENV_SENTINEL_MERGE_CHECK_9f2a"
        assert sentinel not in os.environ

        code, _out = git_helpers.run_git(["rev-parse", "--show-toplevel"], cwd=repo, env={sentinel: "1"})
        assert code == 0
        assert sentinel not in os.environ

    def test_env_none_behaves_identically_to_omitted(self, tmp_path):
        repo = self._make_repo(tmp_path)
        without_kwarg = git_helpers.run_git(["rev-parse", "--show-toplevel"], cwd=repo)
        with_none = git_helpers.run_git(["rev-parse", "--show-toplevel"], cwd=repo, env=None)
        assert without_kwarg == with_none

    def test_env_override_wins_over_poisoned_ambient_value(self, tmp_path, monkeypatch):
        repo = self._make_repo(tmp_path)
        monkeypatch.setenv("GIT_AUTHOR_NAME", "AMBIENT-POISON")

        code, out = git_helpers.run_git(
            ["var", "GIT_AUTHOR_IDENT"],
            cwd=repo,
            env={
                "GIT_AUTHOR_NAME": "Frescura Override",
                "GIT_AUTHOR_EMAIL": "fresh@test.com",
                "GIT_AUTHOR_DATE": "2020-01-01T00:00:00+0000",
            },
        )
        assert code == 0
        assert "Frescura Override" in out
        assert "AMBIENT-POISON" not in out


# ── run_git log_stderr_on_failure: opt-in diagnostic breadcrumb ──────────


class TestRunGitLogStderrOnFailure:
    """lib/git_helpers.py:run_git()'s log_stderr_on_failure kwarg (~L348,
    ~L414-423) — new observability path added for boot-freshness's
    get_timeline()/get_last_context_time() callers, zero prior test
    coverage (Cerberus review follow-up). subprocess.Popen is monkeypatched
    at the module level (the same `subprocess` module object git_helpers
    imported — sys.modules is a singleton, so patching the attribute here
    reaches git_helpers's own `subprocess.Popen(...)` call without needing
    to reach into git_helpers's namespace) to force a controlled
    (returncode, stdout, stderr) triple without depending on a real git
    failure, per this task's explicit ask. The `_patched_run_git` fakes
    used elsewhere (test_boot_output.py, test_crown.py,
    test_crown_retraction.py, test_consolidation_trigger.py,
    test_boot_freshness_regression.py) monkeypatch run_git ITSELF and do
    not accept this new kwarg — untouched here; these tests call the REAL
    git_helpers.run_git directly instead, so the fakes' signatures are
    irrelevant to this class.

    Test surface (EXHAUSTION PROTOCOL step 1): 1 function's new branch —
    a single compound conditional with 4 operands (log_stderr_on_failure,
    proc.returncode != 0, stderr truthy, stderr.strip() truthy) plus the
    [:300] truncation formatting. 7 scenarios cover every short-circuit
    combination that can flip the outcome (print vs. silent) plus the
    truncation boundary. Excluded: the rest of run_git (env= merge, POSIX/
    Windows kill-tree, timeout) — already covered by TestRunGitEnvKwarg
    above and test_boot_freshness_regression.py's process-group-kill
    tests; out of scope for this task.
    """

    class _FakeProc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.pid = 424242
            self._stdout = stdout
            self._stderr = stderr

        def communicate(self, timeout=None):
            # SEC-CRIT-16 (issue #59): run_git() now captures raw bytes
            # from a real Popen (no text=True/encoding=) and decodes them
            # itself with bytes.decode("utf-8") — so this fake must mimic
            # a real subprocess and return bytes, not str, or run_git's
            # `.decode("utf-8")` call raises AttributeError on a str.
            return self._stdout.encode("utf-8"), self._stderr.encode("utf-8")

    def _patch_popen(self, monkeypatch, returncode, stdout="", stderr=""):
        fake_proc = self._FakeProc(returncode, stdout, stderr)
        monkeypatch.setattr(subprocess, "Popen", lambda *a, **kw: fake_proc)
        return fake_proc

    def test_failure_with_flag_true_prints_breadcrumb_with_prefix(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=128, stderr="fatal: not a git repository")

        code, out = git_helpers.run_git(["status"], log_stderr_on_failure=True)

        assert code == 128
        assert out == ""
        captured = capsys.readouterr()
        assert "[git_helpers] git 'status' exited 128: fatal: not a git repository" in captured.err

    def test_stderr_truncated_to_300_chars(self, monkeypatch, capsys):
        long_stderr = "E" * 500
        self._patch_popen(monkeypatch, returncode=1, stderr=long_stderr)

        git_helpers.run_git(["fetch"], log_stderr_on_failure=True)

        captured = capsys.readouterr()
        assert ("E" * 300) in captured.err
        assert ("E" * 301) not in captured.err

    def test_flag_false_stays_silent_on_failure(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="fatal: some failure")

        code, _out = git_helpers.run_git(["status"], log_stderr_on_failure=False)

        assert code == 1
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_omitted_defaults_to_silent_on_failure(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="fatal: some failure")

        code, _out = git_helpers.run_git(["status"])  # log_stderr_on_failure not passed

        assert code == 1
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_true_but_success_returncode_is_silent(self, monkeypatch, capsys):
        # A successful git call can still write hint/advisory text to
        # stderr (git does this for some commands even on rc=0) — the
        # breadcrumb must only fire on genuine failure, not merely because
        # stderr is non-empty.
        self._patch_popen(monkeypatch, returncode=0, stderr="hint: some advisory text")

        code, _out = git_helpers.run_git(["status"], log_stderr_on_failure=True)

        assert code == 0
        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_true_failure_but_empty_stderr_is_silent(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="")

        git_helpers.run_git(["status"], log_stderr_on_failure=True)

        captured = capsys.readouterr()
        assert captured.err == ""

    def test_flag_true_failure_but_whitespace_only_stderr_is_silent(self, monkeypatch, capsys):
        self._patch_popen(monkeypatch, returncode=1, stderr="   \n  ")

        git_helpers.run_git(["status"], log_stderr_on_failure=True)

        captured = capsys.readouterr()
        assert captured.err == ""


# ── _check_behind_warn_only: every fail-open branch + the warn itself ────


class TestCheckBehindWarnOnly:
    def _make_repo(self, tmp_path, name="commit_behind_repo"):
        repo = str(tmp_path / name)
        os.makedirs(repo)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "a@test.com"], repo)
        _git(["config", "user.name", "A"], repo)
        _git(["commit", "--allow-empty", "-m", "init"], repo)
        return repo

    def test_non_memory_type_never_calls_run_git(self, tmp_path, monkeypatch):
        repo = self._make_repo(tmp_path)
        monkeypatch.chdir(repo)
        mod = _load_commit_module()
        assert "wip" not in MEMORY_TYPES

        def _boom(*_a, **_kw):
            raise AssertionError("run_git must not be called for non-memory types")

        mod.run_git = _boom
        mod._check_behind_warn_only("wip")  # must not raise

    def test_behind_zero_is_silent(self, tmp_path, monkeypatch, capsys):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        monkeypatch.chdir(repo_a)
        mod = _load_commit_module()

        for type_ in MEMORY_TYPES:
            mod._check_behind_warn_only(type_)
        captured = capsys.readouterr()
        assert "behind" not in captured.err.lower() and "detr" not in captured.err.lower()

    def test_no_upstream_configured_is_silent(self, tmp_path, monkeypatch, capsys):
        repo = self._make_repo(tmp_path)  # no remote at all
        monkeypatch.chdir(repo)
        mod = _load_commit_module()

        mod._check_behind_warn_only("decision")
        captured = capsys.readouterr()
        assert "behind" not in captured.err.lower() and "detr" not in captured.err.lower()

    def test_not_a_git_repo_is_silent(self, tmp_path, monkeypatch, capsys):
        non_repo = str(tmp_path / "not_a_repo")
        os.makedirs(non_repo)
        monkeypatch.chdir(non_repo)
        mod = _load_commit_module()

        mod._check_behind_warn_only("decision")  # must not raise
        captured = capsys.readouterr()
        assert "behind" not in captured.err.lower() and "detr" not in captured.err.lower()

    def test_non_numeric_git_output_is_silent(self, tmp_path, monkeypatch, capsys):
        repo = self._make_repo(tmp_path)
        monkeypatch.chdir(repo)
        mod = _load_commit_module()
        mod.run_git = lambda *a, **kw: (0, "not-a-number")

        mod._check_behind_warn_only("decision")  # must not raise (ValueError caught)
        captured = capsys.readouterr()
        assert "behind" not in captured.err.lower() and "detr" not in captured.err.lower()

    def test_behind_positive_prints_visible_warning(self, tmp_path, monkeypatch, capsys):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, 2)
        _git(["fetch", "origin"], repo_a)
        monkeypatch.chdir(repo_a)
        mod = _load_commit_module()

        mod._check_behind_warn_only("decision")
        captured = capsys.readouterr()
        assert "2" in captured.err
        assert "detr" in captured.err.lower() or "behind" in captured.err.lower()


# ── §34 round-trip reinforcement: sanitization-touched Next value ────────


RAW_NEXT_SANITIZE_VARIANT = "NEXT-SANITIZE-VARIANT-café-\U0001F600-token  "  # trailing spaces + unicode


def _expected_sanitized_next(raw_value):
    """Derive the expected post-extraction value from the REAL producer
    pipeline (lib/parsing.py's scan_trailers_memory + sanitize_trailer_value
    — the exact two functions lib/boot_memory.py:extract_memory() calls on
    every Next: trailer), never by hand-simulating what "should" survive.
    """
    body = f"Next: {raw_value}"
    trailers = scan_trailers_memory(body)
    return sanitize_trailer_value(trailers["Next"])


class TestRoundTripSanitizationVariant:
    """Reinforces test_boot_freshness.py's TestIncidentBehindShowsRemoteNext
    (already a genuine §34 round-trip: B writes a unique Next marker, A's
    real boot fetches it via the real hook, and the assertion derives from
    the same marker variable — no fabricated ground truth). This variant
    specifically exercises characters sanitize_trailer_value() is documented
    to touch (trailing whitespace — stripped by scan_trailers_memory's own
    line.strip()/.strip() before sanitize_trailer_value even runs — and
    unicode, which nothing in the pipeline touches and must survive intact)
    end-to-end through a REAL bare-remote fetch and the REAL boot hook, not
    a direct function call — proving the full write→fetch→render seam
    preserves sanitization behavior, not just the extraction function in
    isolation.
    """

    def test_next_with_trailing_spaces_and_unicode_survives_sanitized_through_real_boot(self, tmp_path):
        expected = _expected_sanitized_next(RAW_NEXT_SANITIZE_VARIANT)
        assert expected == "NEXT-SANITIZE-VARIANT-café-\U0001F600-token", (
            "test setup sanity check: the real sanitizer pipeline's output "
            f"changed shape unexpectedly: {expected!r}"
        )

        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, 1, next_marker=RAW_NEXT_SANITIZE_VARIANT)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)
        assert rc == 0, f"stderr: {stderr}"

        line = _line_with(combined, expected)
        assert line is not None, (
            f"expected the sanitized Next value {expected!r} (derived from "
            f"the real sanitizer, trailing spaces stripped, unicode intact) "
            f"to appear verbatim in the boot output.\n{combined}"
        )
        assert "remot" in line.lower(), f"expected remote provenance label on line: {line!r}"
