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
import re
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


# ══════════════════════════════════════════════════════════════════════════
# D-119 / D-120 — the gate moves from "any foreign merge" to "into dev: no
# gate; above dev: the heavy staging gate". (Issue #101, owner 2026-10-18.)
#
# Expected values below come from the owner's decisions D-119 and D-120,
# never from the hook's code:
#   D-119: a merge/pull whose TARGET is `dev` -> no gate at all (flow already
#          ran Cerberus, Argus and Alexandria on that work).
#   D-120: a merge/pull whose target is above dev (staging, main, master,
#          production) -> blocked; the gate asks for Cerberus + Argus on the
#          whole incoming diff, Alexandria checking CHANGELOG + version
#          against it, and Bex's (the owner's) yes; the full suite is left
#          to CI on push.
#
# The TARGET is the branch that receives the merge: HEAD when the command
# runs, or the branch the command switches to first (`git switch dev &&
# git merge ...`, `git checkout dev && git merge ...`).
#
# Two groups:
#   GOLDEN  — today's behaviour that must survive the change. Green now.
#   CONTRACT — new behaviour. RED now where behaviour changes.
# ══════════════════════════════════════════════════════════════════════════

ABOVE_DEV_BRANCHES = ["staging", "main", "master", "production"]


def _make_repo_on(tmp_path, current, also=()):
    """Temporary repo checked out on `current`, with the extra local
    branches in `also` created at the same commit (so a `git switch <b>`
    inside the command refers to a branch that really exists)."""
    repo = _make_repo(tmp_path, branch=current)
    for name in also:
        rc, out, err = git_cmd(["branch", name], repo)
        assert rc == 0, f"fixture setup failed creating branch {name}: {err}"
    return repo


def _assert_decision(parsed, stdout, rc, stderr, expected, context):
    assert rc == 0, f"hook process failed: rc={rc}, stderr={stderr}"
    assert parsed is not None, f"stdout not valid JSON: {stdout!r}"
    assert parsed.get("decision") == expected, (
        f"{context}: expected decision {expected!r}; got {parsed!r}"
    )


def _assert_heavy_gate_message(parsed, context):
    """D-120's four asks, pinned by key items, not by wording."""
    reason = parsed.get("reason", "")
    lower = reason.lower()
    missing = []
    if "cerberus" not in lower:
        missing.append("Cerberus")
    if "argus" not in lower:
        missing.append("Argus")
    if "diff" not in lower:
        missing.append("the incoming diff")
    if "alexandria" not in lower:
        missing.append("Alexandria")
    if "changelog" not in lower:
        missing.append("CHANGELOG")
    if "version" not in lower:
        missing.append("version")
    if "bex" not in lower and "owner" not in lower:
        missing.append("Bex's / the owner's yes")
    if "suite" not in lower:
        missing.append("the full suite")
    if re.search(r"\bCI\b", reason) is None:
        missing.append("CI (suite left to CI on push)")
    assert not missing, (
        f"{context}: the staging gate message must name {missing}; "
        f"got reason={reason!r}"
    )


# ── GOLDEN: today's behaviour that must survive ─────────────────────────────

class TestGoldenExemptionsAboveDev:
    """GOLDEN (point 3): --abort / --continue / --rebase / # merge-reviewed
    keep passing even when the target is a branch above dev, where the
    heavy gate would otherwise apply."""

    @pytest.mark.parametrize("command", [
        "git merge --abort",
        "git merge --continue",
        "git pull --rebase origin dev",
        "git merge dev # merge-reviewed",
        "git pull origin dev # merge-reviewed",
    ])
    def test_should_approve_when_exempt_command_on_staging(self, tmp_path, command):
        repo = _make_repo_on(tmp_path, "staging", also=["dev"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"`{command}` on `staging`")


class TestGoldenIndirectionStaysBlocked:
    """GOLDEN (point 3): eval / bash -c / sh -c wrapping git keeps being
    blocked with the indirection message — also on `dev`, where a direct
    merge will become free. The hook cannot see the real target through
    the wrapper, so D-119's exemption must not leak into it."""

    @pytest.mark.parametrize("command", [
        'eval "git merge feat/x"',
        'bash -c "git merge feat/x"',
        'sh -c "git pull origin feat/x"',
    ])
    @pytest.mark.parametrize("current", ["dev", "staging"])
    def test_should_block_indirection_when_wrapping_git(self, tmp_path, current, command):
        repo = _make_repo_on(tmp_path, current)

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "block",
                         f"`{command}` on `{current}`")
        assert "indirection" in parsed.get("reason", "").lower(), (
            f"indirection must keep its own message; got {parsed!r}"
        )


class TestGoldenOtherTargets:
    """GOLDEN (point 4): targets that are neither dev nor above dev — e.g. a
    feature branch receiving another feature branch. EXECUTED against the
    hook of 2026-10-18: blocked, with a message naming Cerberus and
    Alexandria. Pinned as is."""

    def test_should_block_when_feature_merges_another_feature(self, tmp_path):
        repo = _make_repo_on(tmp_path, "feat/a", also=["feat/b"])

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge feat/b")

        _assert_decision(parsed, stdout, rc, stderr, "block",
                         "`git merge feat/b` on `feat/a`")
        reason = parsed.get("reason", "").lower()
        assert "cerberus" in reason and "alexandria" in reason, (
            f"feature-into-feature block must still ask for review; got {parsed!r}"
        )

    def test_should_block_when_feature_pulls_another_feature(self, tmp_path):
        repo = _make_repo_on(tmp_path, "feat/a")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin feat/b")

        _assert_decision(parsed, stdout, rc, stderr, "block",
                         "`git pull origin feat/b` on `feat/a`")

    def test_should_approve_when_feature_syncs_its_own_remote(self, tmp_path):
        repo = _make_repo_on(tmp_path, "feat/a")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin feat/a")

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         "same-branch sync `git pull origin feat/a` on `feat/a`")


class TestGoldenUnknownTargetFailsClosed:
    """GOLDEN: when the receiving branch cannot be known (detached HEAD),
    the merge is never treated as "into dev" — it stays blocked. Without
    this, a target-detection bug would silently open the gate."""

    def test_should_block_merge_when_head_is_detached(self, tmp_path):
        repo = _make_repo_on(tmp_path, "dev")
        rc, out, err = git_cmd(["checkout", "--detach"], repo)
        assert rc == 0, f"fixture setup failed detaching HEAD: {err}"

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge feat/x")

        _assert_decision(parsed, stdout, rc, stderr, "block",
                         "`git merge feat/x` on a detached HEAD")


# ── CONTRACT: D-119 — merges INTO dev pass with no gate ─────────────────────

class TestMergeIntoDevIsFree:
    """CONTRACT (point 1, D-119): the target is `dev` -> approve, no gate.
    RED today: the hook blocks every merge of a different branch."""

    @pytest.mark.parametrize("command", [
        "git merge feat/x",
        "git merge --no-ff feat/x",
        "git merge --no-ff -m 'merge feat/x' feat/x",
        "git pull origin feat/x",
    ])
    def test_should_approve_when_head_is_dev(self, tmp_path, command):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"`{command}` with HEAD on `dev` (D-119: no gate into dev)")

    @pytest.mark.parametrize("command", [
        "git switch dev && git merge --no-ff feat/x",
        "git checkout dev && git merge --no-ff feat/x",
        "git switch dev && git pull origin feat/x",
    ])
    def test_should_approve_when_command_switches_to_dev_first(self, tmp_path, command):
        # Start on a THIRD branch: starting on feat/x would make
        # `git pull origin feat/x` look like a same-branch sync and pass
        # today for the wrong reason.
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"`{command}` from `feat/other` (target is dev, D-119)")

    def test_should_approve_when_dev_syncs_its_own_remote(self, tmp_path):
        """Already approved today (same-branch sync) and still approved."""
        repo = _make_repo_on(tmp_path, "dev")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin dev")

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         "`git pull origin dev` on `dev`")


# ── CONTRACT: D-120 — merges above dev hit the heavy gate ───────────────────

class TestMergeAboveDevHitsHeavyGate:
    """CONTRACT (point 2, D-120): target above dev -> block, and the message
    names the four asks. Decision already `block` today; the message is RED
    (today it names neither Argus, CHANGELOG/version, Bex nor CI)."""

    @pytest.mark.parametrize("target", ABOVE_DEV_BRANCHES)
    def test_should_block_with_heavy_gate_when_head_merges_dev(self, tmp_path, target):
        repo = _make_repo_on(tmp_path, target, also=["dev"])

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge --no-ff dev")

        context = f"`git merge --no-ff dev` on `{target}`"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    @pytest.mark.parametrize("target", ABOVE_DEV_BRANCHES)
    def test_should_block_with_heavy_gate_when_head_pulls_dev(self, tmp_path, target):
        repo = _make_repo_on(tmp_path, target)

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin dev")

        context = f"`git pull origin dev` on `{target}`"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    @pytest.mark.parametrize("switch", ["switch", "checkout"])
    def test_should_block_when_on_dev_but_command_switches_to_staging(self, tmp_path, switch):
        """HEAD is dev, but the merge lands on staging. Reading only HEAD
        would wrongly open the gate — the target is what counts."""
        repo = _make_repo_on(tmp_path, "dev", also=["staging"])
        command = f"git {switch} staging && git merge --no-ff dev"

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "block",
                         f"`{command}` from `dev` (target is staging)")
        _assert_heavy_gate_message(parsed, f"`{command}` from `dev`")


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
