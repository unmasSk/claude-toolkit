"""
Tests for pre-merge-gate.py — same-branch sync exemption (ACCEPTANCE CONTRACT).

Bug: today the hook blocks EVERY `git merge` / `git pull` (without --rebase)
unconditionally, demanding a Cerberus + Alexandria review before retrying.
That review is meant for integrating a DIFFERENT branch's new work (e.g.
`git merge feature/x`, or pulling a feature/fix branch) — not for a plain
catch-up sync where the local branch pulls/merges its OWN same-named remote
counterpart (e.g. `git pull origin main` while on `main`). That kind of sync
isn't "merging foreign work" and should be exempt from the review gate.

This is the test-first CONTRACT PASS, written before Ultron implements the
fix. Per Dante's EXHAUSTION PROTOCOL rules, the contract pass stays at
ACCEPTANCE granularity (these 10 scenarios) — it does not enumerate every
branch/edge case. That exhaustive hardening pass happens after Ultron
implements, against the real code.

Expected state against the CURRENT (unmodified) hook:
  [ROJO]  — new branch-awareness does not exist yet → MUST currently FAIL.
            Items 1, 2, 3 (the new exemptions).
  [GUARDA] — behavior that already works today by virtue of the existing
            (branch-blind) implementation → currently PASSES, and MUST keep
            passing after the fix so a naive rewrite doesn't regress it.
            Items 4, 5, 6, 7, 8, 9, 10.

Contract:
  EXEMPT (decision: approve), no review required:
    1. `git pull origin main` while on `main` (same branch name as target)
    2. Bare `git pull` while current branch's upstream tracks the same
       branch name (e.g. origin/main while on main)
    3. `git merge origin/main` while on `main` (own remote-tracking
       counterpart, same name after stripping the remote prefix)
    4. Existing exemptions still hold: --abort / --continue / --rebase
    5. `# merge-reviewed` bypass still works regardless of branch

  BLOCK (decision: block), review required:
    6. `git merge feature/some-branch` while on `main` (different branch —
       integrating foreign work)
    7. `git pull origin feature/some-branch` while on `main`
    8. `git pull origin dev` while on `main`
    9. Failure-closed: hook cannot determine current branch (not a git
       repo) → never silently exempt on error determining branch identity
   10. Innocuous non-git command (`echo hello`) is never blocked

Test surface: 10 acceptance scenarios, 13 test methods (some scenarios
expanded into multiple assertions for the sibling commands they cover).
Not tested (out of scope for the contract pass — hardening pass territory):
detached HEAD, upstream tracking a differently-named branch, malformed
`origin/<branch>` refs, multiple remotes. Those become the hardening-pass
EXHAUSTION PROTOCOL surface once Ultron's real branch-detection code exists.
"""

import json
import os
import sys

import pytest

from conftest import HOOKS_DIR, run_cmd, git_cmd

HOOK_PATH = os.path.join(HOOKS_DIR, "pre-merge-gate.py")


# ── Repo helpers ─────────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo", branch="main"):
    """Minimal git repo with user identity, checked out on `branch`.

    `git init`'s default branch name varies by git version/config
    (init.defaultBranch), so we always rename explicitly afterward rather
    than relying on `-b <branch>` support being present.
    """
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    git_cmd(["branch", "-m", branch], repo)
    return repo


def _make_repo_with_tracked_upstream(tmp_path, branch="main"):
    """Repo with a real `origin` remote whose `<branch>` is the configured
    upstream for local `branch` — exercises real git plumbing (`@{u}`,
    `refs/remotes/origin/<branch>`) rather than a stubbed value.
    """
    bare = str(tmp_path / "origin.git")
    os.makedirs(bare)
    git_cmd(["init", "--bare"], bare)
    repo = _make_repo(tmp_path, branch=branch)
    git_cmd(["remote", "add", "origin", bare], repo)
    rc, out, err = git_cmd(["push", "-u", "origin", branch], repo)
    assert rc == 0, f"fixture setup failed pushing/tracking upstream: {err}"
    return repo


# ── Hook invocation helper ───────────────────────────────────────────────────

def _run_hook(cwd, command):
    """Invoke pre-merge-gate.py as a subprocess with a Bash tool_input payload.

    Invocation convention: subprocess, JSON via stdin, cwd = the repo.

    Returns (rc, parsed_json_or_None, stdout, stderr).
    """
    payload = json.dumps({
        "tool_name": "Bash",
        "tool_input": {"command": command},
    })
    rc, stdout, stderr = run_cmd(
        [sys.executable, HOOK_PATH],
        cwd=cwd,
        input_text=payload,
        timeout=20,
    )
    try:
        parsed = json.loads(stdout) if stdout.strip() else None
    except (json.JSONDecodeError, ValueError):
        parsed = None
    return rc, parsed, stdout, stderr


# ══════════════════════════════════════════════════════════════════════════
# EXEMPT — same-branch sync, no review required  [ROJO: fails on current hook]
# ══════════════════════════════════════════════════════════════════════════

class TestSameBranchPullIsExempt:
    """Contract item 1 [ROJO]: `git pull origin main` while on `main` is a
    plain catch-up sync with your own branch, not foreign work — approve."""

    def test_pull_origin_same_branch_name_is_approved(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin main")

        assert rc == 0, f"hook process failed: rc={rc}, stderr={stderr}"
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"same-branch `git pull origin main` on `main` should be exempt "
            f"from review; got {parsed!r}"
        )


class TestBarePullWithMatchingUpstreamIsExempt:
    """Contract item 2 [ROJO]: bare `git pull` when the current branch's
    upstream tracks a branch of the same name (origin/main <- main) — approve."""

    def test_bare_pull_matching_tracked_upstream_is_approved(self, tmp_path):
        repo = _make_repo_with_tracked_upstream(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull")

        assert rc == 0, f"hook process failed: rc={rc}, stderr={stderr}"
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"bare `git pull` tracking a same-named upstream should be "
            f"exempt; got {parsed!r}"
        )


class TestMergeOwnRemoteCounterpartIsExempt:
    """Contract item 3 [ROJO]: `git merge origin/main` while on `main` merges
    your own remote-tracking counterpart (same name after stripping the
    remote prefix) — not foreign work — approve."""

    def test_merge_remote_tracking_same_branch_is_approved(self, tmp_path):
        repo = _make_repo_with_tracked_upstream(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge origin/main")

        assert rc == 0, f"hook process failed: rc={rc}, stderr={stderr}"
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git merge origin/main` on `main` should be exempt; "
            f"got {parsed!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# EXEMPT — pre-existing behavior, must not regress  [GUARDA: passes today]
# ══════════════════════════════════════════════════════════════════════════

class TestExistingExemptionsStillHold:
    """Contract item 4 [GUARDA]: regression coverage — a branch-aware fix
    must not break the exemptions that already work today (--abort,
    --continue, --rebase)."""

    def test_merge_abort_is_approved(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge --abort")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git merge --abort` must stay exempt; got {parsed!r}"
        )

    def test_merge_continue_is_approved(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge --continue")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git merge --continue` must stay exempt; got {parsed!r}"
        )

    def test_pull_rebase_is_approved(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull --rebase origin main")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`git pull --rebase` must stay exempt; got {parsed!r}"
        )


class TestMergeReviewedBypassStillWorks:
    """Contract item 5 [GUARDA]: `# merge-reviewed` must keep bypassing the
    gate regardless of branch, even for what would otherwise be a blocked
    foreign-branch merge."""

    def test_merge_reviewed_bypasses_foreign_branch_block(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(
            repo, "git merge feature/some-branch # merge-reviewed"
        )

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"`# merge-reviewed` bypass must work regardless of branch; "
            f"got {parsed!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# BLOCK — foreign-branch integration, review required  [GUARDA: passes today]
# ══════════════════════════════════════════════════════════════════════════

class TestForeignBranchMergeIsBlocked:
    """Contract item 6 [GUARDA]: merging a differently-named branch is
    integrating foreign work — still requires review."""

    def test_merge_different_branch_is_blocked(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge feature/some-branch")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"merging a different branch into `main` must still require "
            f"review; got {parsed!r}"
        )


class TestForeignBranchPullIsBlocked:
    """Contract items 7-8 [GUARDA]: pulling a differently-named branch is
    integrating foreign work — still requires review."""

    def test_pull_different_named_branch_is_blocked(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(
            repo, "git pull origin feature/some-branch"
        )

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"pulling a different branch into `main` must still require "
            f"review; got {parsed!r}"
        )

    def test_pull_dev_branch_while_on_main_is_blocked(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin dev")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"`git pull origin dev` while on `main` must still require "
            f"review; got {parsed!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# FAIL-CLOSED — branch identity cannot be determined  [GUARDA: passes today]
# ══════════════════════════════════════════════════════════════════════════

class TestFailsClosedWhenBranchUndetermined:
    """Contract item 9 [GUARDA]: if the hook cannot determine the current
    branch, it must never silently exempt the command — fail closed
    (block), preserving the hook's existing fail-closed-on-exception
    behavior."""

    def test_non_git_directory_blocks_pull(self, tmp_path):
        """Running outside any git repo — branch detection has nothing to
        resolve. Even a command that WOULD be exempt in a real repo
        (`git pull origin main`) must block when identity can't be verified."""
        non_git_dir = str(tmp_path / "not-a-repo")
        os.makedirs(non_git_dir)

        rc, parsed, stdout, stderr = _run_hook(non_git_dir, "git pull origin main")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "block", (
            f"undeterminable branch identity must fail closed (block), "
            f"never silently approve; got {parsed!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# REGRESSION — innocuous commands are never blocked  [GUARDA: passes today]
# ══════════════════════════════════════════════════════════════════════════

class TestInnocuousCommandNeverBlocked:
    """Contract item 10 [GUARDA]: a plain non-git command must never be
    blocked by this hook, branch-aware or not."""

    def test_echo_command_is_approved(self, tmp_path):
        repo = _make_repo(tmp_path, branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, "echo hello")

        assert rc == 0
        assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
        assert parsed.get("decision") == "approve", (
            f"innocuous command must never be blocked; got {parsed!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
