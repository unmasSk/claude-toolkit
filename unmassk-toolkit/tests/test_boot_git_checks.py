"""
Surviving coverage for lib/boot_git_checks.py + lib/git_helpers.py, salvaged
from the retired multi-machine "boot memory freshness" test family (issue
#49/#60, formerly test_boot_freshness.py / test_boot_freshness_hardening.py /
test_boot_freshness_regression.py — 3 files, ~4300 lines, chained imports).

Memory v2 (docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3) removed the entire
boot-memory-freshness subsystem: multi-machine memory sync was declared out
of scope ("el propietario trabaja en una máquina a la vez"), so
fetch_memory_ref(), the own-fetch-success stamp (lib/boot_fetch_stamp.py, now
orphaned/unimported), render_memoria_stamp(), check_upstream_shares_history(),
_has_toolkit_memory(), _ASKPASS_FAILFAST, and all of lib/boot_memory.py /
lib/boot_glossary_cache.py were deleted. Every test that drove those symbols
died with them and was retired (3 files, 96 test methods) — see git history
for the deleted files.

This file keeps only what still exercises LIVE code, confirmed against HEAD
(2026-08-02): boot_git_checks.get_ahead_behind(), boot_git_checks.
_build_pull_directive_lines() (both still called from render_branch_section(),
which session-start-boot.py's non-memory BRANCHES section renders on every
boot), boot_git_checks.time_ago() (still used by get_timeline()/
get_remote_branches()), and git_helpers.run_git()'s env= kwarg,
log_stderr_on_failure= kwarg, and POSIX/Windows process-group kill-on-timeout
(none of which are freshness-specific — run_git() is the general-purpose git
subprocess wrapper used everywhere in the codebase).

Build mode: n/a (retirement + salvage pass, linear). No production code is
touched by this file.
"""

import os
import shutil
import subprocess
import sys
import time

import pytest

from conftest import HOOKS_DIR, INSTALL, LIB_DIR, run_script, write_file

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import boot_git_checks
import git_helpers

WINDOWS = sys.platform == "win32"

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")

EMOJIS = {"context": "\U0001F4BE", "decision": "\U0001F9ED", "memo": "\U0001F4CC", "remember": "\U0001F9E0"}

PULL_DIRECTIVE_BEHIND_COUNT = 3


# ── Git / repo helpers (subset salvaged from the old test_boot_freshness.py) ─


def _git(args, cwd, check=True, env=None):
    """Run a git command in cwd. Returns CompletedProcess."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True, encoding='utf-8', errors='replace',
        env=merged_env,
        check=check,
    )


def _commit_real(repo, type_, scope, message, trailers=None):
    """Create a commit using the real emoji + type(scope): message format —
    hooks are bypassed in test repos (established convention), so a direct
    `git commit --allow-empty` is used instead of the wrapper script.
    """
    subject = f"{EMOJIS[type_]} {type_}({scope}): {message}"
    body_lines = [f"{k}: {v}" for k, v in (trailers or {}).items()]
    msg = subject if not body_lines else subject + "\n\n" + "\n".join(body_lines)
    _git(["commit", "--allow-empty", "-m", msg], repo)


def _push_commits_from_b(repo_b, count, next_marker=None, scope="freshness"):
    """Push `count` commits from a second clone (machine B) to the shared
    bare remote. Kept generic even though the freshness-specific Next-marker
    parameter is unused by every surviving caller in this file.
    """
    for i in range(count):
        if next_marker is not None and i == count - 1:
            _commit_real(repo_b, "context", scope, f"sync update {i}", {"Next": next_marker})
        else:
            _git(["commit", "--allow-empty", "-m", f"chore: filler commit {i}"], repo_b)
    _git(["push", "origin", "main"], repo_b)


def _setup_freshness_repo(tmp_path):
    """Machine A: git repo + bare remote configured as `origin`, toolkit
    memory installed (CLAUDE.md marker + manifest.json) and committed so the
    tree starts CLEAN. Returns (repo_a, bare).
    """
    repo_a = str(tmp_path / "repo_a")
    bare = str(tmp_path / "bare.git")
    os.makedirs(repo_a)

    _git(["init", "-b", "main"], repo_a)
    _git(["config", "user.email", "a@test.com"], repo_a)
    _git(["config", "user.name", "Machine A"], repo_a)
    _git(["commit", "--allow-empty", "-m", "init"], repo_a)

    subprocess.run(["git", "init", "--bare", "-b", "main", bare], capture_output=True, check=True)
    _git(["remote", "add", "origin", bare], repo_a)
    _git(["push", "-u", "origin", "main"], repo_a)

    install_rc, install_out, install_err = run_script(INSTALL, repo_a, ["--auto"])
    assert install_rc == 0, f"install --auto failed: {install_out}\n{install_err}"

    status = _git(["status", "--porcelain"], repo_a, check=False)
    if status.stdout.strip():
        _git(["add", "-A"], repo_a)
        _git(["commit", "-m", "chore: install unmassk-toolkit memory"], repo_a)
        _git(["push", "origin", "main"], repo_a)

    return repo_a, bare


def _clone_machine_b(bare, tmp_path, name="repo_b"):
    """Clone a second machine (B) from the CURRENT state of the shared bare
    remote — call AFTER any machine-A-only setup has already been pushed.
    """
    repo_b = str(tmp_path / name)
    _git(["clone", bare, repo_b], str(tmp_path))
    _git(["config", "user.email", "b@test.com"], repo_b)
    _git(["config", "user.name", "Machine B"], repo_b)
    return repo_b


def _boot_log_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "boot-log-latest.txt")


def _read_boot_log(repo):
    try:
        with open(_boot_log_path(repo), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _run_boot(repo, env=None, timeout=30):
    return run_script(BOOT_HOOK, repo, env=env, timeout=timeout)


def _run_boot_combined(repo, env=None, timeout=30):
    """Run the boot hook, return (rc, stdout, stderr, boot_log, combined)."""
    rc, stdout, stderr = _run_boot(repo, env=env, timeout=timeout)
    log_content = _read_boot_log(repo)
    combined = stdout + "\n" + log_content
    return rc, stdout, stderr, log_content, combined


def _make_gated_repo(tmp_path, name="gated_repo"):
    """Minimal real repo, no bare remote — enough for get_ahead_behind()'s
    no-upstream branch and for direct-call unit tests that need no server.
    """
    repo = str(tmp_path / name)
    os.makedirs(repo)
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "a@test.com"], repo)
    _git(["config", "user.name", "A"], repo)
    _git(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _add_bare_remote(repo, tmp_path, name="bare.git"):
    bare = str(tmp_path / name)
    subprocess.run(["git", "init", "--bare", "-b", "main", bare], capture_output=True, check=True)
    _git(["remote", "add", "origin", bare], repo)
    _git(["push", "-u", "origin", "main"], repo)
    return bare


# ── PULL DIRECTIVE: clean vs dirty tree (render_branch_section, real boot) ──


class TestPullDirective:
    """render_branch_section() escalates a behind-count into a PULL
    DIRECTIVE: clean tree -> propose `git pull` as the session's FIRST
    action; dirty tree -> warn about uncommitted work and say explicitly NOT
    to pull. Driven through the real boot hook end-to-end — this is
    render_branch_section()'s own directive-building path
    (_build_pull_directive_lines()), unrelated to the retired memory-fetch
    subsystem.
    """

    def _setup_behind(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, PULL_DIRECTIVE_BEHIND_COUNT)
        # Memory v2 removed the boot's own `git fetch` entirely (it was
        # part of the retired freshness subsystem) — get_ahead_behind()
        # only ever reads the LOCAL refs/remotes/origin/main tracking ref,
        # which a real prior fetch would already have kept current. Fetch
        # explicitly here, same as TestGetAheadBehind's own direct-call
        # tests, to reproduce that precondition.
        _git(["fetch", "origin"], repo_a)
        return repo_a

    def test_behind_clean_tree_proposes_pull_as_first_action(self, tmp_path):
        repo_a = self._setup_behind(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert "pull" in combined.lower(), (
            f"expected a pull directive for a behind + clean tree.\n{combined}"
        )
        assert "first" in combined.lower(), (
            f"expected the pull to be framed as the session's first action.\n{combined}"
        )

    def test_behind_dirty_tree_warns_do_not_pull(self, tmp_path):
        repo_a = self._setup_behind(tmp_path)
        write_file(repo_a, "wip_notes.txt", "scratch content, not committed")

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert "dirty" in combined.lower() or "uncommitted" in combined.lower(), (
            f"expected the dirty-tree state to be mentioned.\n{combined}"
        )
        assert "not pull" in combined.lower() or "do not pull" in combined.lower(), (
            f"expected an explicit 'do not pull' warning for a dirty tree.\n{combined}"
        )


# ── check_upstream_shares_history(): direct + real-boot regression ────────
# ── (DEUDA.md #6/#18 — restored after being retired with the memory ───────
# ── subsystem, which also protected these two SURVIVING live outputs) ─────


def _build_foreign_bare(tmp_path, name="foreign_bare.git", commit_count=2):
    """A bare remote with its own independent commit lineage. A fresh `git
    init --bare` + one clone + N fresh commits naturally shares ZERO
    history with any other repo in this file (different root commit) --
    no orphan-branch trick needed, this IS what "another project's repo"
    looks like from the outside.
    """
    foreign_bare = str(tmp_path / name)
    subprocess.run(["git", "init", "--bare", "-b", "main", foreign_bare], capture_output=True, check=True)
    foreign_work = str(tmp_path / f"{name}_work")
    _git(["clone", foreign_bare, foreign_work], str(tmp_path))
    _git(["config", "user.email", "foreign@test.com"], foreign_work)
    _git(["config", "user.name", "Foreign Machine"], foreign_work)
    for i in range(commit_count):
        _git(["commit", "--allow-empty", "-m", f"chore: foreign lineage commit {i}"], foreign_work)
    _git(["push", "origin", "main"], foreign_work)
    return foreign_bare


def _setup_foreign_upstream_scenario(tmp_path):
    """Machine A (toolkit-installed, clean tree, via _setup_freshness_repo)
    with its `origin` remote repointed at a genuinely FOREIGN bare repo
    (zero shared history) -- repointing the URL of the SAME remote NAME
    keeps branch.main.remote/.merge tracking config coherent (git never
    re-derives tracking from a remote's URL), which is exactly the
    misconfiguration shape check_upstream_shares_history() exists to
    catch: `@{u}` resolves cleanly to "origin/main", a fetch against it
    succeeds, and yet the two sides share no commit history at all.

    Fetches explicitly -- memory v2 removed the boot's own `git fetch`
    entirely (DEUDA.md #17, run_preboot_migrations()'s own docstring: "no
    longer performs any network I/O"), same convention already used by
    TestPullDirective._setup_behind above -- so refs/remotes/origin/main
    genuinely reflects the foreign lineage before the boot hook ever runs;
    get_ahead_behind()'s own `rev-list` call only ever reads that local
    tracking ref, never the network.
    """
    repo_a, _own_bare = _setup_freshness_repo(tmp_path)
    foreign_bare = _build_foreign_bare(tmp_path)
    _git(["remote", "set-url", "origin", foreign_bare], repo_a)
    _git(["fetch", "origin"], repo_a)
    return repo_a, foreign_bare


class TestCheckUpstreamSharesHistoryDirect:
    """Direct unit calls to check_upstream_shares_history() (lib/
    boot_git_checks.py:361) across its three documented return values --
    real repos/branches, no mocking of git itself. The function relies on
    ambient process cwd for its own `run_git(["merge-base", ...])` call
    (no cwd= param -- see git_helpers.run_git's own docstring: "None =
    inherit caller cwd"), so the two repo-backed cases use
    monkeypatch.chdir() (pytest auto-restores it, no cross-test bleed).
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
        # Short-circuits before any git call -- no repo/chdir needed.
        assert boot_git_checks.check_upstream_shares_history(ref) is None


class TestBootSuppressesPullAndBranchesForUnrelatedUpstream:
    """DEUDA.md #6/#18 regression. check_upstream_shares_history() was
    retired along with the multi-machine memory subsystem, but it ALSO
    protected two surviving live outputs: the PULL DIRECTIVE
    (_build_pull_directive_lines(), via render_branch_section()) and the
    BRANCHES section (render_branches_section()). Reproduced live before
    the fix (DEUDA.md #6): a real boot against a misconfigured `origin`
    (an `@{u}` that resolves and fetches cleanly, but shares zero commit
    history with local HEAD) recommended `git pull` -- which real git
    itself would refuse with "refusing to merge unrelated histories" --
    and listed the foreign repo's own branches as if they belonged to this
    project, without saying where they came from.

    Fix restored the guard in hooks/session-start-boot.py's main(): when
    check_upstream_shares_history(upstream_ref) is False, upstream_ref is
    nulled, which empties BOTH downstream sections at once (remote_name
    for BRANCHES derives from upstream_ref; pull_directive_lines is
    filtered out of branch_lines and re-emptied for the banner).
    """

    def test_unrelated_upstream_shows_neither_pull_nor_branches(self, tmp_path):
        repo_a, foreign_bare = _setup_foreign_upstream_scenario(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert "git pull" not in combined, (
            "PULL DIRECTIVE recommended `git pull` against an upstream "
            "already confirmed to share NO history with local HEAD -- "
            f"real git would refuse this merge.\n{combined}"
        )
        assert "BRANCHES (" not in combined, (
            "BRANCHES section listed a foreign remote's branches as if "
            f"they belonged to this project.\n{combined}"
        )

        # Independent channel (not the code under test): confirm the
        # scenario genuinely has zero shared history, not just that the
        # guard says so.
        merge_base = _git(["merge-base", "HEAD", "origin/main"], repo_a, check=False)
        assert merge_base.returncode == 1, (
            "test setup error: expected merge-base to confirm NO shared "
            f"history (exit 1). Got rc={merge_base.returncode}, "
            f"stdout={merge_base.stdout!r}"
        )

    def test_legit_upstream_still_shows_both_pull_and_branches(self, tmp_path):
        """Negative control -- the guard must not suppress these two
        outputs for a real, shared-history upstream. Same fixture shape as
        TestPullDirective's own behind-repo setup, extended to also assert
        the BRANCHES section (not covered there).
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, PULL_DIRECTIVE_BEHIND_COUNT)
        _git(["fetch", "origin"], repo_a)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert "git pull" in combined, f"expected a pull directive for a legit behind upstream.\n{combined}"
        assert "BRANCHES (" in combined, f"expected a BRANCHES section for a legit upstream.\n{combined}"

        # Independent channel: confirm this really IS the shared-history
        # case the guard must leave alone.
        merge_base = _git(["merge-base", "HEAD", "origin/main"], repo_a, check=False)
        assert merge_base.returncode == 0, (
            "test setup error: expected a real common ancestor for the "
            f"legit case. Got rc={merge_base.returncode}"
        )


# ── get_ahead_behind: every branch, real repos where git state matters ─────


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
        """Deleting the remote-tracking ref file while branch.<n>.remote/
        .merge stays intact makes `git rev-parse --abbrev-ref @{u}` itself
        fail (exit 128) — get_ahead_behind() can't distinguish this from
        "no upstream at all", and that collapse is the correct, safe one
        (never crashes, never reports fake ahead/behind numbers).
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

    def test_real_ahead_and_behind_counts_simultaneously(self, tmp_path, monkeypatch):
        """Divergence case (local has 1 unpushed commit AND the remote has 2
        commits this repo never saw) — salvaged from the retired
        TestDivergenceShowsBothSidesLabeled, whose OTHER assertions (a
        remote-provenance-labeled memory "Next" item) tested the deleted
        multi-machine memory subsystem and were not portable. The numeric
        ahead+behind claim itself is live, real render_branch_section()
        output (`f" [{ahead_n}/{behind_n} vs upstream]"`), and had zero
        direct unit coverage for the "both nonzero at once" case anywhere
        else in the suite.
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _git(["commit", "--allow-empty", "-m", "chore: a's own unpushed commit"], repo_a)
        _push_commits_from_b(repo_b, 2)
        _git(["fetch", "origin"], repo_a)
        monkeypatch.chdir(repo_a)

        assert boot_git_checks.get_ahead_behind("main") == (1, 2, "origin/main")

    def test_non_numeric_rev_list_output_should_fail_open_but_raises(self, tmp_path, monkeypatch):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        monkeypatch.chdir(repo_a)

        real_run_git = git_helpers.run_git

        def _fake_run_git(args, timeout=10, cwd=None, env=None, **kwargs):
            if args and args[0] == "rev-list" and "--left-right" in args:
                return 0, "abc def"
            return real_run_git(args, timeout=timeout, cwd=cwd, env=env)

        monkeypatch.setattr(git_helpers, "run_git", _fake_run_git)

        result = boot_git_checks.get_ahead_behind("main")
        assert result == (0, 0, "origin/main")


# ── _build_pull_directive_lines: dirty vs clean, pure ────────────────────


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


# ── DEUDA.md #17: PULL DIRECTIVE / BRANCHES don't disclose that the local ──
# ── remote-tracking data may be stale (memory v2 removed the boot's own ────
# ── `git fetch` entirely -- both sections still compute off whatever the ───
# ── LAST fetch left in refs/remotes/<remote>/*, which can be days old) ─────


# Any of these, case-insensitive, counts as "discloses the local remote data
# may not reflect the real remote" -- the exact wording is Ultron's call
# (test-first contract; DEUDA.md #17 itself asks for the effect, not a
# literal phrase that would go red the day someone rewords the sentence).
FRESHNESS_DISCLOSURE_KEYWORDS = (
    "confirm", "stale", "fresh", "verify", "verified", "outdated",
    "up to date", "up-to-date",
)


def _discloses_unconfirmed_freshness(text):
    lowered = text.lower()
    return any(keyword in lowered for keyword in FRESHNESS_DISCLOSURE_KEYWORDS)


class TestPullDirectiveDisclosesUnconfirmedFreshness:
    """DEUDA.md #17: `run_preboot_migrations()` no longer performs any
    network I/O (its own docstring) -- get_ahead_behind()'s `behind_n` is
    computed purely from refs/remotes/<remote>/* exactly as they sat after
    whatever fetch last touched them, which can be days old.
    _build_pull_directive_lines() escalates that possibly-stale number into
    a directive telling the user to `git pull` as the FIRST action of the
    session with the SAME confidence the text always had -- nothing in it
    says the number might not reflect the real remote. Contract: the text
    must disclose that, wording left to Ultron (FRESHNESS_DISCLOSURE_KEYWORDS
    above) -- pure calls, no repo/git needed, mirrors TestBuildPullDirectiveLines
    right above.
    """

    def test_clean_tree_directive_discloses_unconfirmed_freshness(self):
        lines = boot_git_checks._build_pull_directive_lines(3, is_dirty=False)
        joined = "\n".join(lines)
        assert _discloses_unconfirmed_freshness(joined), (
            "PULL DIRECTIVE (clean-tree case) must disclose that the "
            f"behind-count is not confirmed against a fresh remote fetch. Got: {lines!r}"
        )

    def test_dirty_tree_directive_discloses_unconfirmed_freshness(self):
        lines = boot_git_checks._build_pull_directive_lines(3, is_dirty=True)
        joined = "\n".join(lines)
        assert _discloses_unconfirmed_freshness(joined), (
            "PULL DIRECTIVE (dirty-tree case) must disclose that the "
            f"behind-count is not confirmed against a fresh remote fetch. Got: {lines!r}"
        )


class TestBranchesSectionDisclosesUnconfirmedFreshness:
    """DEUDA.md #17, same gap for the other surviving text producer:
    render_branches_section() lists refs/remotes/<remote>/* exactly as they
    sat after the last fetch (get_remote_branches()'s own docstring:
    "whatever this repo's most recent `git fetch` of that remote last
    updated") with no fetch running in this boot to refresh them -- nothing
    in its output says so. Real repo + real remote via the file's own
    _make_gated_repo()/_add_bare_remote() helpers (no mocking of git); a
    direct unit call, decoupled from the PULL DIRECTIVE path above so this
    assertion can't pass merely because the OTHER function's text leaked in.
    """

    def test_branches_section_discloses_unconfirmed_freshness(self, tmp_path, monkeypatch):
        repo = _make_gated_repo(tmp_path)
        _add_bare_remote(repo, tmp_path)
        monkeypatch.chdir(repo)

        lines = boot_git_checks.render_branches_section("origin", "main")

        assert any("BRANCHES (" in line for line in lines), (
            f"test setup error: expected a real BRANCHES section. Got: {lines!r}"
        )
        joined = "\n".join(lines)
        assert _discloses_unconfirmed_freshness(joined), (
            "BRANCHES section must disclose that the listed branches reflect "
            "whatever the last fetch left behind, not a confirmed live "
            f"remote state. Got: {lines!r}"
        )


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
    """lib/git_helpers.py:run_git()'s log_stderr_on_failure kwarg —
    subprocess.Popen is monkeypatched at the module level to force a
    controlled (returncode, stdout, stderr) triple without depending on a
    real git failure.
    """

    class _FakeProc:
        def __init__(self, returncode, stdout="", stderr=""):
            self.returncode = returncode
            self.pid = 424242
            self._stdout = stdout
            self._stderr = stderr

        def communicate(self, timeout=None):
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


# ── run_git() timeout: POSIX process-group kill (Argus SEC-MED-001) ──────

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
    """Argus SEC-MED-001: run_git()'s TimeoutExpired branch must kill the
    WHOLE process group (os.killpg on POSIX via start_new_session=True at
    spawn time), not just the direct "git" child — otherwise a hung
    ssh/askpass/credential-helper grandchild survives as an orphan.
    """

    @pytest.mark.skipif(
        WINDOWS,
        reason="POSIX process-group kill (os.killpg) has no meaning on Windows; "
        "the Windows path (_win32_kill_tree/taskkill) is exercised by "
        "TestWin32ProcessTreeKillOnTimeout below",
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

        grandchild_pid = int(pid_file.read_text(encoding='utf-8').strip())

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _pid_is_alive(grandchild_pid):
            time.sleep(0.1)

        assert not _pid_is_alive(grandchild_pid), (
            f"grandchild pid {grandchild_pid} is still alive after run_git's "
            f"timeout — expected the WHOLE process group to be killed via "
            f"os.killpg(), not just the direct 'git' child"
        )


# ── run_git() timeout: Windows process-tree kill (Argus SEC-MED-001) ─────

_WIN32_SITECUSTOMIZE_SPAWN_GRANDCHILD_TEMPLATE = '''import subprocess, sys, os, time

pid_file = r"""__PID_FILE__"""
grandchild = subprocess.Popen([sys.executable, "-S", "-c", "import time; time.sleep(60)"])
with open(pid_file, "w") as f:
    f.write(str(grandchild.pid))
    f.flush()
    os.fsync(f.fileno())

time.sleep(60)
'''


def _resolve_real_python_exe():
    """Return a real, standalone python.exe suitable for copying to a new
    path and running there as a fake "git.exe" — sys.base_exec_prefix
    always points at the base (non-venv) install, unlike sys.executable
    which may be a small venv launcher stub that can't run relocated.
    """
    candidate = os.path.join(sys.base_exec_prefix, "python.exe")
    if os.path.isfile(candidate):
        return candidate
    return sys.executable


def _make_fake_win32_git_spawning_grandchild(tmp_path, pid_file):
    """Windows counterpart to _make_fake_git_spawning_grandchild() — a fake
    "git.exe" that spawns a real, independent grandchild, writes its pid to
    `pid_file`, then hangs. The fake "git.exe" is a literal copy of a real
    Python interpreter binary; a PYTHONPATH-injected sitecustomize.py does
    the actual work (imported automatically during interpreter startup,
    before argv[1] is ever opened as a script file).

    Returns (fake_bin_dir, sitepkg_dir) — caller puts fake_bin_dir on the
    real process's PATH and passes sitepkg_dir via run_git's own
    env={"PYTHONPATH": ...} kwarg.
    """
    fake_dir = tmp_path / "fake_bin_grandchild_win32"
    fake_dir.mkdir(exist_ok=True)
    fake_git_path = fake_dir / "git.exe"
    shutil.copy(_resolve_real_python_exe(), str(fake_git_path))

    sitepkg_dir = tmp_path / "sitepkg_grandchild_win32"
    sitepkg_dir.mkdir(exist_ok=True)
    script = _WIN32_SITECUSTOMIZE_SPAWN_GRANDCHILD_TEMPLATE.replace("__PID_FILE__", str(pid_file))
    (sitepkg_dir / "sitecustomize.py").write_text(script, encoding="utf-8")

    return str(fake_dir), str(sitepkg_dir)


def _win32_pid_is_alive(pid):
    """tasklist-based liveness check. encoding="oem" (not UTF-8) because
    tasklist's console output uses the OEM/ANSI codepage.
    """
    result = subprocess.run(
        ["tasklist", "/FI", f"PID eq {pid}"],
        capture_output=True,
        text=True,
        encoding="oem",
        errors="replace",
        timeout=5,
    )
    return str(pid) in result.stdout


class TestWin32ProcessTreeKillOnTimeout:
    """Argus SEC-MED-001, Windows counterpart to
    TestPosixProcessTreeKillOnTimeout above — proves run_git()'s
    TimeoutExpired branch on win32 (_win32_kill_tree(), `taskkill /F /T
    /PID`) kills the whole process tree rooted at the "git" process it
    launched, not just the direct child. No mocking of subprocess.run,
    taskkill, or _win32_kill_tree — a real fake "git.exe" spawns a real,
    independent grandchild and this test proves via a real tasklist query
    that it is dead after run_git's timeout fires.

    Windows' CreateProcess (invoked when Popen() is given a bare command
    name like "git" with shell=False) resolves the executable via the
    CALLING process's own live PATH block, NOT the env= kwarg passed to
    run_git — so this test monkeypatches the TEST PROCESS's own
    os.environ["PATH"] before calling run_git, and passes the fake's
    sitepkg dir through run_git's own env={"PYTHONPATH": ...} kwarg.
    """

    @pytest.mark.skipif(
        not WINDOWS,
        reason="Windows-only: exercises _win32_kill_tree()/taskkill, the "
        "win32 counterpart to POSIX os.killpg() tested in "
        "TestPosixProcessTreeKillOnTimeout",
    )
    def test_timeout_kills_grandchild_process_not_just_direct_child_win32(self, tmp_path, monkeypatch):
        repo = tmp_path / "killtree_repo_win32"
        repo.mkdir()

        pid_file = tmp_path / "grandchild_win32.pid"
        fake_bin, sitepkg = _make_fake_win32_git_spawning_grandchild(tmp_path, pid_file)
        monkeypatch.setenv("PATH", fake_bin + os.pathsep + os.environ.get("PATH", ""))

        start = time.monotonic()
        code, _out = git_helpers.run_git(
            ["fetch"],
            timeout=1,
            cwd=str(repo),
            env={"PYTHONPATH": sitepkg},
        )
        elapsed = time.monotonic() - start

        assert code == 1, "a timed-out run_git call must return exit code 1"
        assert elapsed < 6, f"run_git took {elapsed:.1f}s — timeout not bounding the hang"
        assert _wait_for_file(str(pid_file)), "grandchild never wrote its own pid — test setup broken"

        grandchild_pid = int(pid_file.read_text(encoding='utf-8').strip())

        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and _win32_pid_is_alive(grandchild_pid):
            time.sleep(0.1)

        assert not _win32_pid_is_alive(grandchild_pid), (
            f"grandchild pid {grandchild_pid} is still alive after run_git's "
            f"timeout — expected the WHOLE process tree to be killed via "
            f"taskkill /F /T /PID, not just the direct 'git.exe' child"
        )


# ── time_ago(): error-path robustness (still live, used by get_timeline()/ ──
# ── get_remote_branches()) ────────────────────────────────────────────────


class TestTimeAgoOverflowFallsBackSafely:
    """time_ago()'s `iso_or_unix.isdigit()` branch feeds the raw int
    straight into datetime.fromtimestamp(), which raises OverflowError for
    a digit string whose value is out of range for the platform's time_t.
    Fix (commit 6fc6386): widened the except tuple to (ValueError,
    TypeError, OSError, OverflowError). get_timeline()/get_last_context_time()
    emit `%at` (unix epoch), so the isdigit() branch is a real production
    path, not dead code.
    """

    @pytest.mark.parametrize(
        "iso_or_unix",
        [
            "9" * 30,  # digit string -> int() never overflows, but
                       # datetime.fromtimestamp() does (OverflowError)
            "9" * 12,  # smaller but still-out-of-range digit string
        ],
        ids=["30-digit-timestamp", "12-digit-timestamp"],
    )
    def test_out_of_range_digit_timestamp_returns_unknown(self, iso_or_unix):
        assert boot_git_checks.time_ago(iso_or_unix) == "unknown"

    @pytest.mark.parametrize(
        "iso_or_unix",
        [
            "not-a-date",  # ValueError from datetime.fromisoformat()
            "",  # ValueError from datetime.fromisoformat()
            "2026-13-99T99:99:99",  # ValueError, out-of-range calendar fields
        ],
        ids=["not_a_date", "empty_string", "invalid_calendar_fields"],
    )
    def test_pre_existing_invalid_iso_input_still_returns_unknown(self, iso_or_unix):
        assert boot_git_checks.time_ago(iso_or_unix) == "unknown"


class TestTimeAgoNonStringInputContract:
    """time_ago() calls `iso_or_unix.isdigit()` unconditionally inside the
    try block — AttributeError is not in the except tuple, so a non-string
    input crashes instead of degrading to "unknown" like every other
    malformed-input case. Mirrors lib/date_parsing.py::parse_date()'s
    identical guard (BUG-1, Argus SEC-LOW-001).
    """

    @pytest.mark.parametrize(
        "bad_input",
        [None, 123456, ["a"]],
        ids=["none", "int", "list"],
    )
    def test_returns_unknown_instead_of_raising(self, bad_input):
        result = boot_git_checks.time_ago(bad_input)
        assert result == "unknown", (
            f"time_ago({bad_input!r}) should return \"unknown\" -- the same "
            "fallback every other parse failure in this function already "
            f"gets -- not raise. Got {result!r}."
        )


class TestTimeAgoNonAsciiDigitsContract:
    """str.isdigit() returns True for non-ASCII Unicode digit characters
    (fullwidth, arabic-indic, devanagari, ...) that int() also happily
    parses — a real `git log %at` call never emits these, so any such
    string reaching time_ago() must resolve to "unknown", not a
    plausible-but-wrong "N ago" string derived via int().
    """

    @pytest.mark.parametrize(
        "non_ascii_digits",
        ["１２３", "٢٠٢٤", "१२३"],
        ids=["fullwidth", "arabic_indic", "devanagari"],
    )
    def test_non_ascii_digit_string_returns_unknown(self, non_ascii_digits):
        assert non_ascii_digits.isdigit(), (
            "test setup error: fixture string is not a str.isdigit() == "
            "True case -- this test targets the exact isdigit()-but-not-"
            "ASCII gap"
        )
        assert not non_ascii_digits.isascii(), (
            "test setup error: fixture string is ASCII digits -- must be "
            "non-ASCII to target this gap"
        )

        result = boot_git_checks.time_ago(non_ascii_digits)

        assert result == "unknown", (
            f"time_ago({non_ascii_digits!r}) returned {result!r} -- a "
            "plausible-but-wrong date derived from a non-ASCII digit "
            "string that str.isdigit() accepts but no real `git log %at` "
            "call ever emits. Must be rejected as unparseable (\"unknown\"), "
            "not silently converted via int()."
        )
