"""
Regression pass for the repair-round fixes to boot memory freshness
(multi-machine, issue #49) — Moriarty confirmed (T2) these fixes had NO
regression coverage protecting them in CI. This file pins each confirmed
break as an automated test that would FAIL if the corresponding fix were
ever reverted.

Findings protected (each class below references its finding explicitly):

  1. Clock-skew (Moriarty ROTO #1) — fetch_memory_ref()'s rate-limit gate
     `0 <= age < FETCH_RATE_LIMIT_SECONDS` in lib/boot_git_checks.py. A
     FETCH_HEAD mtime in the FUTURE (negative age) must never be treated
     as fresh/rate-limited.
  2. Decoupled stamp (Moriarty ROTO #2) — fetch_memory_ref() must fetch
     against the SAME ref resolved from `@{u}`, never a bare branch name.
     An incoherent branch.<name>.merge config must never let the stamp
     claim "remote (fetched)".
  3. Renamed remote (Moriarty, new break found in repair round 2) —
     `git remote rename origin upstream` (tracking preserved, coherent)
     must still fetch successfully, using the resolved remote NAME, never
     a hardcoded "origin" literal.
  4. English provenance label (Bex, language-unification decision) —
     REMOTE_PROVENANCE_LABEL must stay " [source: remote]", never regress
     back to the original Spanish wording.
  5. Windows process-tree kill (Argus SEC-MED-001) — logic-review only;
     no Windows machine available in this environment. What IS testable
     portably: on POSIX, run_git()'s os.killpg() on timeout kills the
     WHOLE process group, including a grandchild the hung "git" process
     spawned, not just the direct child. The Windows counterpart
     (_win32_kill_tree via taskkill /T) is NOT exercised here — see the
     class docstring below for why no trivial-pass substitute was written.
  6. `false`-by-PATH askpass (Argus, low portability) — on POSIX,
     _ASKPASS_FAILFAST must resolve via a plain PATH lookup to an
     executable that exits non-zero immediately, with no exec error.

Test surface for this pass: 6 confirmed findings, 10 test methods (11 test
cases counting one parametrization), all driven against the REAL,
already-fixed code in HEAD (lib/boot_git_checks.py, lib/boot_memory.py,
lib/git_helpers.py) — no mocking of the behavior under test, only real git
repos/remotes and (for findings 5/6) a real subprocess tree / real PATH
lookup. Excluded from this pass (not requested, out of scope for a
regression-only pass): the exhaustive branch/error-path re-sweep already
done in test_boot_freshness_hardening.py — this file only adds NEW
coverage for the specific fixes Moriarty flagged as unprotected.

Build mode: linear (regression pass on already-fixed code). No production
code is touched by this file — RED results here are reported, not fixed
(Absolute Prohibition #4).
"""

import os
import subprocess
import sys
import time

import pytest

from conftest import LIB_DIR

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import boot_git_checks
import boot_memory
import git_helpers

from test_boot_freshness import (
    WINDOWS,
    _clone_machine_b,
    _git,
    _line_with,
    _push_commits_from_b,
    _run_boot_combined,
    _setup_freshness_repo,
)
from test_boot_freshness_hardening import _add_bare_remote, _make_gated_repo


# ── Finding 1: clock skew — future FETCH_HEAD mtime must never rate-limit ──


class TestClockSkewFutureFetchHeadMtime:
    """Moriarty ROTO #1: `0 <= age < FETCH_RATE_LIMIT_SECONDS` in
    fetch_memory_ref() (lib/boot_git_checks.py) is the gate that must
    reject a FUTURE mtime (negative age) as "fresh" — a real cross-machine
    clock-skew scenario. Treating a negative age as fresh would permanently
    suppress every future fetch on that machine (a negative age never
    naturally enters the [0, window) range again).

    Verified via TWO independent channels per test, never trusting the
    status field alone: (1) the returned status, and (2) FETCH_HEAD's own
    mtime actually advancing — proof a real fetch attempt happened (a
    skipped/rate-limited call would leave it untouched).
    """

    def _seed_and_skew_future(self, tmp_path, offset_seconds):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        boot_git_checks.fetch_memory_ref(repo)  # seed a real FETCH_HEAD
        fetch_head = os.path.join(repo, ".git", "FETCH_HEAD")
        future_time = time.time() + offset_seconds
        os.utime(fetch_head, (future_time, future_time))
        return repo, fetch_head

    @pytest.mark.parametrize(
        "offset_seconds", [1, 10_000_000], ids=["future_by_1s", "future_massive"]
    )
    def test_future_mtime_never_rate_limits(self, tmp_path, offset_seconds):
        repo, fetch_head = self._seed_and_skew_future(tmp_path, offset_seconds)
        skewed_mtime = os.path.getmtime(fetch_head)

        result = boot_git_checks.fetch_memory_ref(repo)

        assert result["status"] != "rate_limited", (
            f"a FUTURE FETCH_HEAD mtime (offset +{offset_seconds}s) must "
            f"never be treated as fresh/rate-limited. Got: {result}"
        )
        # Independent channel: a real fetch attempt must have actually run —
        # proven by FETCH_HEAD's mtime moving away from the skewed value
        # (a skipped/rate-limited call would leave it untouched).
        assert os.path.getmtime(fetch_head) != skewed_mtime, (
            "FETCH_HEAD's mtime was never touched — no fetch was actually "
            "attempted despite the future-mtime clock-skew scenario"
        )
        assert result["status"] == "fetched", (
            f"expected a real fetch against the live bare remote to "
            f"succeed. Got: {result}"
        )

    def test_mtime_exactly_now_still_rate_limits(self, tmp_path):
        """Boundary: age == 0 (mtime freshly set to "now") is the one
        non-negative edge that MUST still rate-limit — only a genuinely
        NEGATIVE age (future) is exempted from the gate.
        """
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        boot_git_checks.fetch_memory_ref(repo)  # seed
        fetch_head = os.path.join(repo, ".git", "FETCH_HEAD")
        now = time.time()
        os.utime(fetch_head, (now, now))
        mtime_before = os.path.getmtime(fetch_head)

        result = boot_git_checks.fetch_memory_ref(repo)

        assert result["status"] == "rate_limited", (
            f"expected age≈0 to still be rate-limited. Got: {result}"
        )
        # Independent channel: a rate-limited call must never touch
        # FETCH_HEAD at all.
        assert os.path.getmtime(fetch_head) == mtime_before, (
            "a rate-limited call must never touch FETCH_HEAD's mtime"
        )


# ── Finding 2: decoupled stamp — fetch by resolved tracking ref ────────────


class TestDecoupledStampUsesResolvedTrackingRef:
    """Moriarty ROTO #2: fetch_memory_ref() must fetch against the SAME ref
    get_ahead_behind()/resolve_boot_memory() actually read via `@{u}` — not
    just the local branch's own name. A repo whose branch.<name>.merge
    config is incoherent (points at a ref that doesn't exist on the real
    remote) must never let the stamp claim "remote (fetched)" for content
    that was never actually confirmed.
    """

    def test_incoherent_merge_ref_never_claims_remote_fetched(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        _git(["config", "branch.main.merge", "refs/heads/does-not-exist-xyz"], repo_a)

        result = boot_git_checks.fetch_memory_ref(repo_a)

        assert result["status"] != "fetched", (
            f"a nonexistent remote-side ref must fail, never claim "
            f"success. Got: {result}"
        )
        stamp = boot_git_checks.render_memoria_stamp(result)
        assert "remote (fetched" not in stamp, (
            f"the stamp must never claim remote-fetched for an incoherent "
            f"tracking ref. Got: {stamp!r}"
        )
        assert "LOCAL" in stamp, f"expected the LOCAL/unverified fallback. Got: {stamp!r}"

    def test_missing_upstream_merge_config_returns_no_remote(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        _git(["config", "--unset", "branch.main.merge"], repo_a)

        result = boot_git_checks.fetch_memory_ref(repo_a)

        assert result["status"] == "no_remote", (
            f"a branch with a remote configured but no coherent merge/"
            f"upstream ref must report no_remote, not attempt a "
            f"branch-name fetch. Got: {result}"
        )
        stamp = boot_git_checks.render_memoria_stamp(result)
        assert "remote (fetched" not in stamp


# ── Finding 3: renamed remote must still resolve and fetch ─────────────────


class TestRenamedRemoteStillFetches:
    """Moriarty (new break found in repair round 2): `git remote rename
    origin upstream` (tracking preserved, coherent — git updates
    branch.<name>.remote automatically) must still fetch successfully.
    Regression guard against a hardcoded "origin" literal creeping back
    into the liveness check instead of the real `remote_name` resolved
    from `@{u}`.
    """

    def test_renamed_remote_still_fetches_successfully(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        _git(["remote", "rename", "origin", "upstream"], repo_a)
        # Sanity: git's own rename keeps tracking coherent.
        upstream_check = _git(["rev-parse", "--abbrev-ref", "@{u}"], repo_a)
        assert upstream_check.stdout.strip() == "upstream/main", (
            "test setup error: git remote rename did not preserve tracking"
        )

        result = boot_git_checks.fetch_memory_ref(repo_a)

        assert result["status"] == "fetched", (
            f"expected a renamed-but-coherent remote to fetch "
            f"successfully, not fall back to no_remote. Got: {result}"
        )


# ── Finding 4: English provenance label, never Spanish again ───────────────


class TestRemoteProvenanceLabelIsEnglish:
    """Bex (issue #49 repair round, language-unification decision):
    REMOTE_PROVENANCE_LABEL must stay the English " [source: remote]"
    literal. Regression guard against the original Spanish wording
    ("[fuente: remoto]" or similar) reappearing.
    """

    def test_literal_label_value(self):
        assert boot_memory.REMOTE_PROVENANCE_LABEL == " [source: remote]"

    def test_labeled_content_never_contains_spanish_wording(self):
        memory = {
            "last_context": "abc123 msg",
            "pending": [],
            "blockers": [],
            "decisions": [],
            "memos": [],
            "remembers": [],
            "tombstones": set(),
        }
        labeled = boot_memory._label_remote_provenance(memory)
        assert labeled["last_context"].endswith(" [source: remote]")
        assert "fuente" not in labeled["last_context"].lower()
        assert "remoto" not in labeled["last_context"].lower()

    def test_behind_boot_output_uses_english_literal(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        marker = "PROVENANCE-ENGLISH-LITERAL-MARKER"
        _push_commits_from_b(repo_b, 1, next_marker=marker)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        line = _line_with(combined, marker)
        assert line is not None, f"expected the remote Next marker in boot output.\n{combined}"
        assert "[source: remote]" in line, f"expected the English literal. Got line: {line!r}"
        assert "fuente" not in line.lower()
        assert "remoto]" not in line.lower()


# ── Finding 5: POSIX process-tree kill on timeout ───────────────────────────

_FAKE_GIT_SPAWN_GRANDCHILD_TEMPLATE = '''#!/usr/bin/env python3
import sys, os, subprocess, time

pid_file = r"""__PID_FILE__"""
grandchild = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
with open(pid_file, "w") as f:
    f.write(str(grandchild.pid))
    f.flush()
    os.fsync(f.fileno())

time.sleep(60)
'''


def _make_fake_git_spawning_grandchild(tmp_path, pid_file):
    fake_dir = tmp_path / "fake_bin_grandchild"
    fake_dir.mkdir(exist_ok=True)
    fake_git_path = fake_dir / "git"
    script = _FAKE_GIT_SPAWN_GRANDCHILD_TEMPLATE.replace("__PID_FILE__", str(pid_file))
    fake_git_path.write_text(script, encoding="utf-8")
    os.chmod(fake_git_path, 0o755)
    return str(fake_dir)


def _wait_for_file(path, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if os.path.isfile(path) and os.path.getsize(path) > 0:
            return True
        time.sleep(0.05)
    return False


def _pid_is_alive(pid):
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True  # exists but not ours — still alive
    return True


class TestPosixProcessTreeKillOnTimeout:
    """Argus SEC-MED-001 (repair round 2): run_git()'s TimeoutExpired
    branch must kill the WHOLE process group (os.killpg on POSIX via
    start_new_session=True at spawn time), not just the direct "git"
    child — otherwise a hung ssh/askpass/credential-helper grandchild
    survives as an orphan that can still pop an interactive dialog
    completely out of context.

    Windows note (item 5's "logic-review only" scope): the Windows
    counterpart (_win32_kill_tree, using `taskkill /F /T /PID`) is NOT
    exercised anywhere in this suite — there is no Windows machine
    available in this environment, and `taskkill` has no POSIX
    equivalent to fake it against. Writing a test that merely calls
    _win32_kill_tree() with a mocked subprocess.run would only prove the
    mock was configured correctly, not that a real Windows process tree
    actually dies — exactly the kind of vacuous test this project's own
    "Coverage Boundaries" rule forbids. Left as an explicit, documented
    gap rather than a trivial-pass substitute.
    """

    @pytest.mark.skipif(
        WINDOWS,
        reason="POSIX process-group kill (os.killpg) has no meaning on Windows; "
        "the Windows path (_win32_kill_tree/taskkill) is untestable without a "
        "real Windows machine — see class docstring",
    )
    def test_timeout_kills_grandchild_process_not_just_direct_child(self, tmp_path):
        repo = tmp_path / "killtree_repo"
        repo.mkdir()

        pid_file = tmp_path / "grandchild.pid"
        fake_bin = _make_fake_git_spawning_grandchild(tmp_path, pid_file)

        start = time.monotonic()
        code, _out = git_helpers.run_git(
            ["fetch"],
            timeout=1,
            cwd=str(repo),
            env={"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")},
        )
        elapsed = time.monotonic() - start

        assert code == 1, "a timed-out run_git call must return exit code 1"
        assert elapsed < 6, f"run_git took {elapsed:.1f}s — timeout not bounding the hang"
        assert _wait_for_file(str(pid_file)), "grandchild never wrote its own pid — test setup broken"

        grandchild_pid = int(pid_file.read_text().strip())

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _pid_is_alive(grandchild_pid):
            time.sleep(0.1)

        assert not _pid_is_alive(grandchild_pid), (
            f"grandchild pid {grandchild_pid} is still alive after run_git's "
            f"timeout — expected the WHOLE process group to be killed via "
            f"os.killpg(), not just the direct 'git' child"
        )


# ── Finding 6: `false`-by-PATH askpass resolves and fails fast ─────────────


class TestAskpassFailfastResolvesViaPath:
    """Argus (low portability, repair round 2): `_ASKPASS_FAILFAST` on
    POSIX is the bare word "false" (no path separator), deliberately
    relying on git's own PATH lookup (has-dir-sep check falls through to a
    normal PATH search) rather than a hardcoded absolute path like
    "/bin/false" (Linux-only) or "/usr/bin/false" (missing on some
    minimal Linux images) — portable across macOS and Linux. This test
    proves that literal resolves via a plain PATH lookup to a real
    executable that exits non-zero immediately, with no exec error, the
    exact contract GIT_ASKPASS/SSH_ASKPASS need.

    Windows note: on Windows, `_ASKPASS_FAILFAST` is `"cmd /c exit 1"` — a
    full command-line string, not a bare executable name (Windows'
    CreateProcess parses the whole string natively, unlike POSIX argv
    splitting). That value cannot be executed on this POSIX host at all
    (no `cmd.exe`) — logic-review only, no trivial-pass substitute
    written here.
    """

    @pytest.mark.skipif(
        WINDOWS,
        reason="_ASKPASS_FAILFAST is a Windows command-line string ('cmd /c exit 1') "
        "on win32, not a POSIX-executable name — untestable without a real Windows "
        "machine, see class docstring",
    )
    def test_posix_askpass_failfast_resolves_and_exits_nonzero(self):
        assert boot_git_checks._ASKPASS_FAILFAST == "false", (
            "test assumes the documented POSIX value — if this changed, "
            "re-derive the assertion from the real constant"
        )

        try:
            result = subprocess.run(
                [boot_git_checks._ASKPASS_FAILFAST, "some-prompt-argv-appended-by-git"],
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, OSError) as e:
            pytest.fail(
                f"'{boot_git_checks._ASKPASS_FAILFAST}' failed to exec via a "
                f"plain PATH lookup: {e!r}"
            )

        assert result.returncode != 0, (
            "the askpass fail-fast executable must exit non-zero so git "
            "treats any credential prompt as declined, never hangs"
        )
