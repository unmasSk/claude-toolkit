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
  7. Repo-identity confusion (Moriarty T2, THIS pass, session 2026-07-06)
     — check_upstream_shares_history() (lib/boot_git_checks.py:449) +
     render_memoria_stamp(history_related=...) (:661) +
     session-start-boot.py main()'s upstream_ref-nulling (:300-333) +
     extract_glossary(exclude_remote=...)'s `--exclude=refs/remotes/
     <name>/*` guard (lib/boot_memory.py:340). A misconfigured `origin`
     that resolves cleanly, fetches successfully, and shares a branch
     NAME with local, but shares NO commit history at all, must never
     have its content rendered as this project's own memory — through
     EITHER the labeled resolve_boot_memory() path or the unlabeled
     extract_glossary() `--all` history scan.

Test surface for this pass: 7 confirmed findings, 17 test methods (18 test
cases counting one parametrization) — 10 methods / 11 cases for findings
1-6 (pre-existing, unchanged), 7 NEW methods for finding 7 (this session):
3 direct unit calls to check_upstream_shares_history() (shared/unrelated/
none-or-option-shaped), 1 end-to-end foreign-upstream boot scenario (stamp
+ content-suppression across both leak surfaces + an independent merge-base
verification channel), 2 direct extract_glossary(exclude_remote=...) calls
proving the leak is real without the guard and closed with it, 1 legit-
multi-machine control case proving the guard does not break the genuine
flow, and 1 NEW confirmed gap (PULL DIRECTIVE still recommends `git pull`
against a confirmed-unrelated upstream) pinned as xfail(strict=True) and
reported, not fixed (Absolute Prohibition #4). All driven against the REAL,
already-fixed code in HEAD (lib/boot_git_checks.py, lib/boot_memory.py,
lib/git_helpers.py) — no mocking of the behavior under test, only real git
repos/remotes/orphan-branches and (for findings 5/6) a real subprocess tree
/ real PATH lookup. Excluded from this pass (not requested, out of scope
for a regression-only pass): the exhaustive branch/line re-sweep already
done in test_boot_freshness_hardening.py — this file only adds NEW coverage
for the specific fixes Moriarty flagged as unprotected, plus the one new
gap found while writing finding 7's coverage.

Build mode: linear (regression pass on already-fixed code). No production
code is touched by this file — RED results here are reported, not fixed
(Absolute Prohibition #4).
"""

import os
import subprocess
import sys
import time

import pytest

from conftest import LIB_DIR, run_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import boot_git_checks
import boot_memory
import git_helpers

from test_boot_freshness import (
    WINDOWS,
    _clone_machine_b,
    _commit_real,
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


# ── Finding 7: repo-identity confusion (Moriarty T2, THIS pass) ───────────
#
# Fixture + shared markers for the foreign-upstream scenario. Marker text
# deliberately avoids "remote"/"local"/"behind"/"pull"/"memory" — those
# substrings are reserved for asserting on labels/wording the FEATURE adds,
# never for an accidental echo of the marker's own name (see
# feat-boot-freshness-contract-notes.md's "marker naming pitfall").

FOREIGN_DECISION_MARKER = "XENO-DECISION-7f3ab2c1"
FOREIGN_NEXT_MARKER = "XENO-NEXT-9d114ae2"
NORMAL_CASE_NEXT_MARKER = "T2-GUARD-CONTROL-NEXT-4b8e21"


def _build_foreign_bare_with_crowned_content(tmp_path, name="foreign_bare.git"):
    """A bare remote with a totally independent commit lineage (zero shared
    history with any machine-A repo in this file) carrying a real crowned
    Decision and a real Next resume marker — exactly the shape a
    legitimate upstream's memory takes, so a leak here would be
    indistinguishable from genuine remote memory if the T2 guard ever
    regressed.
    """
    foreign_bare = str(tmp_path / name)
    subprocess.run(["git", "init", "--bare", "-b", "main", foreign_bare], capture_output=True, check=True)
    foreign_work = str(tmp_path / f"{name}_work")
    _git(["clone", foreign_bare, foreign_work], str(tmp_path))
    _git(["config", "user.email", "foreign@test.com"], foreign_work)
    _git(["config", "user.name", "Foreign Machine"], foreign_work)
    _git(["commit", "--allow-empty", "-m", "init foreign lineage"], foreign_work)
    _commit_real(
        foreign_work, "decision", "xenoscope",
        f"{FOREIGN_DECISION_MARKER} adopt unrelated policy",
        {"Decision": FOREIGN_DECISION_MARKER, "Crown": "Decision"},
    )
    _commit_real(
        foreign_work, "context", "xenoscope",
        f"sync {FOREIGN_NEXT_MARKER}",
        {"Next": FOREIGN_NEXT_MARKER},
    )
    _git(["push", "origin", "main"], foreign_work)
    return foreign_bare


def _setup_foreign_upstream_scenario(tmp_path):
    """Machine A, toolkit-installed and clean (via _setup_freshness_repo's
    own baseline), with its `origin` remote repointed at a genuinely
    FOREIGN bare repo (zero shared history) — repointing the URL of the
    SAME remote NAME keeps branch.main.remote/.merge tracking config
    coherent (git never re-derives tracking from the URL), which is
    exactly the misconfiguration shape check_upstream_shares_history()
    exists to catch: `@{u}` resolves cleanly, a fetch against it succeeds,
    and yet the two sides share no commit history at all.
    """
    repo_a, _own_bare = _setup_freshness_repo(tmp_path)
    foreign_bare = _build_foreign_bare_with_crowned_content(tmp_path)
    _git(["remote", "set-url", "origin", foreign_bare], repo_a)
    return repo_a, foreign_bare


def _extract_glossary_direct(repo, exclude_remote=None):
    """Call boot_memory.extract_glossary(exclude_remote=...) with the test
    repo as GIT_DIR/GIT_WORK_TREE — same subprocess-isolation pattern as
    tests/test_boot_output.py's _extract_glossary(), extended with the
    exclude_remote passthrough that helper predates. Run out-of-process
    (not via a monkeypatched in-process import) because boot_memory is a
    stably-named module reused by every other test file in this suite —
    see unmassk-toolkit-python-test-conventions.md's sys.modules-
    contamination warning.
    """
    code = f"""
import sys, os, json, subprocess
sys.path.insert(0, {repr(LIB_DIR)})
os.chdir({repr(repo)})

import git_helpers as _gh

def _patched_run_git(args, cwd=None, timeout=None, env=None):
    merged_env = dict(os.environ)
    merged_env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    merged_env['GIT_WORK_TREE'] = {repr(repo)}
    result = subprocess.run(['git'] + args, capture_output=True, text=True, cwd={repr(repo)}, env=merged_env)
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import boot_memory
result = boot_memory.extract_glossary(exclude_remote={exclude_remote!r})

def _ser(lst):
    return [list(item) for item in lst]

print(json.dumps({{
    'decisions': _ser(result.get('decisions', [])),
    'memos': _ser(result.get('memos', [])),
    'remembers': _ser(result.get('remembers', [])),
}}))
"""
    import json as _json

    rc, stdout, stderr = run_cmd([sys.executable, "-c", code], repo, timeout=30)
    if rc != 0:
        raise RuntimeError(f"_extract_glossary_direct failed (rc={rc}): {stderr}")
    return _json.loads(stdout)


class TestCheckUpstreamSharesHistoryDirect:
    """Direct unit calls to check_upstream_shares_history() (lib/
    boot_git_checks.py:449) across its three documented return values —
    real repos/branches, no mocking of git itself. The function relies on
    ambient process cwd for its own `run_git(["merge-base", ...])` call (no
    cwd= param — see git_helpers.run_git's own docstring: "None = inherit
    caller cwd"), so the two repo-backed cases use monkeypatch.chdir()
    (pytest auto-restores it, no cross-test bleed).
    """

    def test_shared_history_returns_true(self, tmp_path, monkeypatch):
        repo = str(tmp_path / "shared_repo")
        os.makedirs(repo)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "a@test.com"], repo)
        _git(["config", "user.name", "A"], repo)
        _git(["commit", "--allow-empty", "-m", "shared ancestor"], repo)
        _git(["branch", "sibling"], repo)
        _git(["commit", "--allow-empty", "-m", "main-only commit"], repo)

        monkeypatch.chdir(repo)
        assert boot_git_checks.check_upstream_shares_history("sibling") is True

    def test_no_common_ancestor_returns_false(self, tmp_path, monkeypatch):
        repo = str(tmp_path / "orphan_repo")
        os.makedirs(repo)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "a@test.com"], repo)
        _git(["config", "user.name", "A"], repo)
        _git(["commit", "--allow-empty", "-m", "main history"], repo)
        _git(["checkout", "--orphan", "unrelated"], repo)
        _git(["commit", "--allow-empty", "-m", "unrelated history"], repo)
        _git(["checkout", "main"], repo)

        monkeypatch.chdir(repo)
        assert boot_git_checks.check_upstream_shares_history("unrelated") is False

    @pytest.mark.parametrize("ref", [None, "", "-x", "--evil"], ids=["none", "empty", "dash", "double-dash"])
    def test_missing_or_option_shaped_ref_returns_none(self, ref):
        # Short-circuits before any git call — no repo/chdir needed.
        assert boot_git_checks.check_upstream_shares_history(ref) is None


class TestForeignUpstreamBootSuppressesUnrelatedHistory:
    """Moriarty T2 PoC (issue #49 repair round, repo-identity confusion) —
    end-to-end regression pin for the FIXED code in HEAD.

    A misconfigured `origin` pointing at a repo with zero shared history
    must never have its crowned Decision/Next rendered as this project's
    own memory — through EITHER surface: resolve_boot_memory()'s labeled
    remote path, or extract_glossary()'s unlabeled `--all` history scan.
    """

    def test_stamp_exact_and_foreign_content_never_reaches_output(self, tmp_path):
        repo_a, foreign_bare = _setup_foreign_upstream_scenario(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)
        assert rc == 0, f"stderr: {stderr}"

        # (a) the MEMORY: stamp is EXACTLY the unrelated-history wording,
        # regardless of the fetch's own status (a fetch against the
        # foreign remote itself succeeds — the guard overrides the wording
        # unconditionally).
        stamp_line = _line_with(combined, "MEMORY:")
        assert stamp_line is not None, f"no MEMORY: line found in boot output.\n{combined}"
        assert stamp_line.strip() == (
            "MEMORY: LOCAL — upstream unrelated (no shared history), not shown"
        ), f"expected the exact unrelated-history stamp. Got: {stamp_line!r}"

        # (b) neither the crowned Decision nor the Next marker from the
        # foreign lineage reach stdout or the boot-log — via EITHER the
        # labeled resolve_boot_memory() path or the unlabeled
        # extract_glossary() `--all` scan.
        assert FOREIGN_DECISION_MARKER not in combined, (
            f"foreign upstream's crowned Decision leaked into boot output "
            f"despite zero shared history.\n{combined}"
        )
        assert FOREIGN_NEXT_MARKER not in combined, (
            f"foreign upstream's Next marker leaked into boot output "
            f"despite zero shared history.\n{combined}"
        )

        # (c) independent channel: prove via a SEPARATE, direct git
        # invocation (not the code under test) that the two sides
        # genuinely share no history — confirms the scenario itself, not
        # just the guard's rendered output.
        merge_base = _git(["merge-base", "HEAD", "origin/main"], repo_a, check=False)
        assert merge_base.returncode == 1, (
            f"test setup error: expected merge-base to confirm NO shared "
            f"history (exit 1). Got rc={merge_base.returncode}, "
            f"stdout={merge_base.stdout!r}"
        )


class TestExtractGlossaryExcludeRemoteGuardsForeignRefs:
    """Moriarty T2's second confirmed variant: extract_glossary()'s `--all`
    history scan (lib/boot_memory.py:340) walks EVERY ref under refs/,
    including refs/remotes/<name>/* — a foreign upstream's crowned Decision
    would leak into this project's OWN glossary with zero provenance
    label (strictly worse than resolve_boot_memory()'s labeled path).
    Proves the leak is real with exclude_remote=None (the pre-#49-repair
    default call shape, still the function's own default) AND that
    exclude_remote=<name> closes it — direct calls, isolating this ONE
    mechanism from the full-boot scenario above.
    """

    def _make_repo_with_fetched_foreign_remote(self, tmp_path):
        repo = str(tmp_path / "repo_glossary")
        os.makedirs(repo)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "a@test.com"], repo)
        _git(["config", "user.name", "A"], repo)
        _git(["commit", "--allow-empty", "-m", "init"], repo)

        foreign_bare = _build_foreign_bare_with_crowned_content(tmp_path, name="foreign_bare_glossary.git")
        _git(["remote", "add", "origin", foreign_bare], repo)
        _git(["fetch", "origin"], repo)
        return repo

    def test_without_exclude_remote_the_foreign_decision_leaks(self, tmp_path):
        repo = self._make_repo_with_fetched_foreign_remote(tmp_path)

        glossary = _extract_glossary_direct(repo, exclude_remote=None)

        found = any(FOREIGN_DECISION_MARKER in text for _label, text, _crown in glossary["decisions"])
        assert found, (
            "test setup error: expected extract_glossary(exclude_remote=None) "
            "to see the foreign remote's crowned Decision via its --all scan "
            f"(this proves the scenario is real). Got: {glossary['decisions']}"
        )

    def test_with_exclude_remote_the_foreign_decision_is_suppressed(self, tmp_path):
        repo = self._make_repo_with_fetched_foreign_remote(tmp_path)

        glossary = _extract_glossary_direct(repo, exclude_remote="origin")

        found = any(FOREIGN_DECISION_MARKER in text for _label, text, _crown in glossary["decisions"])
        assert not found, (
            f"extract_glossary(exclude_remote='origin') must exclude "
            f"refs/remotes/origin/* from its --all scan. Got: {glossary['decisions']}"
        )


class TestLegitMultiMachineFlowStillWorksAfterGuard:
    """The T2 guard (check_upstream_shares_history) must not break the
    legitimate multi-machine flow it sits alongside — a real second clone
    (genuinely shared history) pushing ahead must still produce the
    "remote (fetched...)" stamp and a labeled Next, exactly as before the
    repair round.
    """

    def test_legit_behind_machine_shows_remote_stamp_and_labeled_next(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, 2, next_marker=NORMAL_CASE_NEXT_MARKER)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)
        assert rc == 0, f"stderr: {stderr}"

        stamp_line = _line_with(combined, "MEMORY:")
        assert stamp_line is not None, f"no MEMORY: line found.\n{combined}"
        assert stamp_line.strip().startswith("MEMORY: remote ("), (
            f"expected a genuine shared-history upstream to still produce "
            f"the remote-confirmed stamp. Got: {stamp_line!r}"
        )

        next_line = _line_with(combined, NORMAL_CASE_NEXT_MARKER)
        assert next_line is not None, f"expected B's Next marker in boot output.\n{combined}"
        assert boot_memory.REMOTE_PROVENANCE_LABEL in next_line, (
            f"expected the remote-provenance label on B's Next line. Got: {next_line!r}"
        )

        # Independent channel: confirm this really IS the shared-history
        # case the guard must leave alone.
        merge_base = _git(["merge-base", "HEAD", "origin/main"], repo_a, check=False)
        assert merge_base.returncode == 0, (
            "test setup error: expected a real common ancestor for the "
            f"legit multi-machine case. Got rc={merge_base.returncode}"
        )


class TestPullDirectiveGapForUnrelatedUpstream:
    """NEW finding (Dante, this regression pass, session 2026-07-06) — NOT
    part of Ultron's T2 fix, not protected anywhere else. Confirmed
    empirically against the real, current HEAD code before writing this
    test: render_branch_section()'s PULL DIRECTIVE line (lib/
    boot_git_checks.py:_build_pull_directive_lines, built from raw
    ahead_n/behind_n) runs BEFORE check_upstream_shares_history() in
    hooks/session-start-boot.py's main() (:302-333), and main() never
    revisits pull_directive_lines after learning the upstream is unrelated
    — it only nulls upstream_ref for the memory-read/glossary paths. For a
    foreign, zero-shared-history upstream this actively tells the user to
    `git pull`, which would attempt to merge in a completely unrelated
    commit graph — the exact confusion this feature exists to prevent, one
    line up from the (correctly suppressed) MEMORY: stamp.

    Reported here, NOT fixed (Absolute Prohibition #4) — pinned as
    xfail(strict=True) so it flips to a hard failure (forcing a test
    update) the moment this gap is closed.
    """

    @pytest.mark.xfail(
        strict=True,
        reason="CONFIRMED GAP (session 2026-07-06): PULL DIRECTIVE still "
        "recommends `git pull` against an upstream already confirmed to "
        "share NO history with local HEAD — not covered by the T2 "
        "identity-confusion fix. Report to Ultron, do not silently fix here.",
    )
    def test_pull_directive_never_recommends_pull_for_unrelated_upstream(self, tmp_path):
        repo_a, foreign_bare = _setup_foreign_upstream_scenario(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)
        assert rc == 0, f"stderr: {stderr}"

        assert "git pull" not in combined, (
            "PULL DIRECTIVE recommended `git pull` against an upstream "
            "already confirmed to share NO history with local HEAD — "
            f"this would merge in an unrelated commit graph.\n{combined}"
        )
