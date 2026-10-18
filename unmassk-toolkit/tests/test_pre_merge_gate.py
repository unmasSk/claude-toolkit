"""
Tests for pre-merge-gate.py — the merge/pull gate, decided by the branch that
RECEIVES the merge (the target).

Contract (owner's decisions D-119 / D-120, issue #101; the expected values in
this file come from those decisions and from Cerberus's review of
2026-10-18, never from the hook's code):

  APPROVE, no gate:
    - target is `dev` (D-119) — HEAD on dev, or a leading
      `git switch dev &&` / `git checkout dev &&`; several merges in one
      command are free only if EVERY one of them lands on dev.
    - a branch syncing its own remote copy (`git pull origin main` on main,
      bare `git pull` with a same-named upstream, `git merge origin/main`
      where `origin` is a real remote). A local branch whose name merely ends
      in the target (`feat/main`) is NOT a sync.
    - --abort / --continue / --rebase, and the `# merge-reviewed` token.
    - any non-git command.

  BLOCK with the heavy staging gate (D-120: Cerberus + Argus on the whole
  diff, Alexandria on CHANGELOG + version, the owner's yes, suite left to CI):
    - any merge/pull in the command whose target is above dev (staging, main,
      master, production) — including the second or later merge of a chained
      command (`&&`, `;`, newline).
    - target unknown: no repo, detached HEAD, a switch that cannot be read
      (`;`, `--track`), a `cd`/`pushd` before the merge, `git -C <path>`.
      Unknown never means "into dev", and never gets the lighter message.

  BLOCK with the light gate (Cerberus + Alexandria): any other target
  (a feature branch receiving another branch).

  BLOCK with the indirection message: eval / bash -c / sh -c wrapping git.

Every test runs the real hook as a subprocess (JSON on stdin, cwd = a
temporary git repo), the way Claude Code calls it.
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
# EXEMPT — same-branch sync, no review required
# ══════════════════════════════════════════════════════════════════════════

class TestSameBranchPullIsExempt:
    """Contract item 1: `git pull origin main` while on `main` is a
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
    """Contract item 2: bare `git pull` when the current branch's
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
    """Contract item 3: `git merge origin/main` while on `main` merges
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
# EXEMPT — --abort / --continue / --rebase / # merge-reviewed
# ══════════════════════════════════════════════════════════════════════════

class TestExistingExemptionsStillHold:
    """Contract item 4: regression coverage — a branch-aware fix
    must not break the long-standing exemptions (--abort,
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
    """Contract item 5: `# merge-reviewed` must keep bypassing the
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
# BLOCK — foreign-branch integration, review required
# ══════════════════════════════════════════════════════════════════════════

class TestForeignBranchMergeIsBlocked:
    """Contract item 6: merging a differently-named branch is
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
    """Contract items 7-8: pulling a differently-named branch is
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
# FAIL-CLOSED — branch identity cannot be determined
# ══════════════════════════════════════════════════════════════════════════

class TestFailsClosedWhenBranchUndetermined:
    """Contract item 9: if the hook cannot determine the current
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
# REGRESSION — innocuous commands are never blocked
# ══════════════════════════════════════════════════════════════════════════

class TestInnocuousCommandNeverBlocked:
    """Contract item 10: a plain non-git command must never be
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
#   GOLDEN  — behaviour from before D-119/D-120 that had to survive it.
#   CONTRACT — the D-119/D-120 behaviour itself.
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


# ── GOLDEN: behaviour that had to survive D-119/D-120 ─────────────────────────────

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
    """CONTRACT (point 1, D-119): the target is `dev` -> approve, no gate."""

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
        # for the wrong reason.
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"`{command}` from `feat/other` (target is dev, D-119)")

    def test_should_approve_when_dev_syncs_its_own_remote(self, tmp_path):
        """Same-branch sync on dev: approved."""
        repo = _make_repo_on(tmp_path, "dev")

        rc, parsed, stdout, stderr = _run_hook(repo, "git pull origin dev")

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         "`git pull origin dev` on `dev`")


# ── CONTRACT: D-120 — merges above dev hit the heavy gate ───────────────────

class TestMergeAboveDevHitsHeavyGate:
    """CONTRACT (point 2, D-120): target above dev -> block, and the message
    names the four asks."""

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


# ── CONTRACT: every merge in a chained command is judged (Cerberus #1) ──────

class TestChainedMergesAreAllJudged:
    """One Bash call can close a task into dev and then promote dev above it.
    The second merge lands on staging/main and must hit the heavy gate even
    though the first one, into dev, is free. Judging only the first merge
    lets work reach staging/main with no review at all."""

    @pytest.mark.parametrize("command", [
        "git switch dev && git merge --no-ff feat/x && git switch staging && git merge --no-ff dev",
        "git merge --no-ff feat/x && git switch main && git merge --no-ff dev",
        "git merge --no-ff feat/x && git switch main && git merge dev",
        "git merge feat/x && git checkout main && git pull origin dev",
        "git merge --no-ff feat/x\ngit switch staging\ngit merge --no-ff dev",
        "git merge --no-ff feat/x\ngit checkout main\ngit pull origin dev",
    ])
    def test_should_block_with_heavy_gate_when_a_later_merge_lands_above_dev(
            self, tmp_path, command):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x", "staging", "main"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} from `dev` (second merge lands above dev)"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    @pytest.mark.parametrize("command", [
        "git merge --no-ff feat/x && git merge --no-ff feat/y",
        "git merge --no-ff feat/x\ngit pull origin feat/y",
    ])
    def test_should_approve_when_every_chained_merge_lands_on_dev(self, tmp_path, command):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x", "feat/y"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} on `dev` (both merges into dev, D-119)")

    def test_should_approve_when_switching_to_dev_then_merging_twice(self, tmp_path):
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x", "feat/y"])
        command = "git switch dev && git merge --no-ff feat/x && git merge --no-ff feat/y"

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} from `feat/other` (both merges into dev)")


# ── CONTRACT: the merge runs somewhere else (Cerberus #2, pre-existing -C) ──

class TestMergeInAnotherDirectoryIsUnknown:
    """The session repo sits on dev, but the merge runs in another repo or
    worktree that may be on main. Reading the session repo's branch would
    open the gate for a merge into main. The target is unknown -> block,
    with the heavy gate."""

    @pytest.mark.parametrize("command", [
        "cd ../other && git merge dev",
        "cd ../other && git merge --no-ff feat/x",
        "pushd ../other && git merge dev",
        "cd ../other\ngit merge dev",
        "git -C ../other merge dev",
        "git -C ../other merge --no-ff feat/x",
        "git -C ../other pull origin dev",
    ])
    def test_should_block_when_merge_runs_in_another_directory(self, tmp_path, command):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x"])
        _make_repo(tmp_path, name="other", branch="main")

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} with the session repo on `dev`, ../other on `main`"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)


# ── CONTRACT: unknown target gets the HEAVY gate (Cerberus #3) ──────────────

class TestUnknownTargetGetsHeavyGate:
    """When the receiving branch cannot be read, it may well be staging or
    main. The block must ask for the stricter review (Argus and the owner's
    yes), never the light Cerberus + Alexandria one — following the light
    message and adding the token would merge into staging under-reviewed."""

    @pytest.mark.parametrize("command", [
        "git checkout staging; git merge dev",
        "git switch staging; git merge --no-ff dev",
        "git switch --track origin/staging && git merge dev",
    ])
    def test_should_block_with_heavy_gate_when_switch_is_unreadable(self, tmp_path, command):
        repo = _make_repo_on(tmp_path, "dev", also=["staging"])

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} from `dev` (switch cannot be read)"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    def test_should_block_with_heavy_gate_when_head_is_detached(self, tmp_path):
        repo = _make_repo_on(tmp_path, "dev")
        rc, out, err = git_cmd(["checkout", "--detach"], repo)
        assert rc == 0, f"fixture setup failed detaching HEAD: {err}"

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge feat/x")

        context = "`git merge feat/x` on a detached HEAD"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    def test_should_block_with_heavy_gate_when_not_a_repo(self, tmp_path):
        non_git_dir = str(tmp_path / "not-a-repo")
        os.makedirs(non_git_dir)

        rc, parsed, stdout, stderr = _run_hook(non_git_dir, "git merge dev")

        context = "`git merge dev` outside any git repo"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)


# ── CONTRACT: pre-existing holes Cerberus found (EXECUTED approve before) ───

class TestAbortFallbackDoesNotExemptTheMerge:
    """`git merge X || git merge --abort` is the common "try, abort on
    conflict" form. The --abort is only the fallback; the merge itself still
    lands on main and must be gated."""

    def test_should_block_when_merge_has_abort_fallback_on_main(self, tmp_path):
        repo = _make_repo_on(tmp_path, "main", also=["dev"])
        command = "git merge dev || git merge --abort"

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} on `main`"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)


class TestOnlyARealRemoteCountsAsOwnCopy:
    """`git merge origin/main` on main syncs main's own remote copy (origin
    is a configured remote). `git merge feat/main` on main merges a local
    feature branch that merely ends in `main` — foreign work into main."""

    def test_should_block_when_local_branch_name_ends_in_target(self, tmp_path):
        repo = _make_repo_on(tmp_path, "main", also=["feat/main"])

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge feat/main")

        context = "`git merge feat/main` on `main` (feat is not a remote)"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    def test_should_approve_when_merging_real_remote_copy(self, tmp_path):
        repo = _make_repo_with_tracked_upstream(tmp_path, branch="main")
        rc, out, err = git_cmd(["branch", "feat/main"], repo)
        assert rc == 0, f"fixture setup failed creating feat/main: {err}"

        rc, parsed, stdout, stderr = _run_hook(repo, "git merge origin/main")

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         "`git merge origin/main` on `main` with a real `origin` remote")


# ── CONTRACT: D-129 — -C / cd pointing at the SESSION repo is not "elsewhere" ──
#
# D-129 (council, 2026-10-18, owner: «Arréglalos todos»): the fail-closed on
# cd / -C protected other worktrees but sent every everyday merge into dev
# written as `git -C <session repo> ...` or `cd <session repo> && ...` to the
# staging gate. Fix: when the path resolves to the SAME top-level directory
# the session is in (absolute or relative, trailing slash or not, or a
# subdirectory of it), the target is read exactly as with no -C / cd. A
# different repo, or a different worktree of the same repo (its own
# top-level), stays unknown -> heavy gate.

def _same_repo_spellings(tmp_path, repo):
    """Ways of writing the session repo's own path from cwd = repo.
    `tmp_path/repo` is where `_make_repo` puts it, so the relative form
    `../repo` is derived from the fixture, not from the hook."""
    assert os.path.basename(repo) == "repo"
    return {
        "absolute": repo,
        "absolute-trailing-slash": repo + "/",
        "dot": ".",
        "relative-via-parent": "../repo",
        "relative-via-parent-trailing-slash": "../repo/",
    }


_SAME_REPO_FORMS = [
    "absolute",
    "absolute-trailing-slash",
    "dot",
    "relative-via-parent",
    "relative-via-parent-trailing-slash",
]


class TestSessionRepoPathIsReadLikeNoPath:
    """CONTRACT (D-129): `git -C <session repo>` and `cd <session repo> &&`
    read the session repo's branch, as if no path had been given."""

    @pytest.mark.parametrize("form", _SAME_REPO_FORMS)
    def test_should_approve_when_git_C_session_repo_switches_to_dev(self, tmp_path, form):
        # Third branch, so the pull/merge cannot pass as a same-branch sync.
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x"])
        path = _same_repo_spellings(tmp_path, repo)[form]
        command = f"git -C {path} switch dev && git -C {path} merge --no-ff feat/x"

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} — -C is the session repo ({form}), target dev (D-129)")

    @pytest.mark.parametrize("form", _SAME_REPO_FORMS)
    def test_should_approve_when_cd_session_repo_then_switches_to_dev(self, tmp_path, form):
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x"])
        path = _same_repo_spellings(tmp_path, repo)[form]
        command = f"cd {path} && git switch dev && git merge --no-ff feat/x"

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} — cd into the session repo ({form}), target dev (D-129)")

    @pytest.mark.parametrize("command_tpl", [
        "git -C {path} merge --no-ff feat/x",
        "git -C {path} pull origin feat/x",
        "cd {path} && git merge --no-ff feat/x",
    ])
    def test_should_approve_when_head_is_dev_and_path_is_session_repo(self, tmp_path, command_tpl):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x"])
        command = command_tpl.format(path=repo)

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} with HEAD on dev (D-129: same as no path)")

    def test_should_approve_when_path_is_a_subdirectory_of_session_repo(self, tmp_path):
        """Same top-level once resolved: a subfolder of the session repo is
        the session repo."""
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "feat/x"])
        sub = os.path.join(repo, "sub")
        os.makedirs(sub)
        command = f"git -C {sub} switch dev && git -C {sub} merge --no-ff feat/x"

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        _assert_decision(parsed, stdout, rc, stderr, "approve",
                         f"{command!r} — subfolder of the session repo, target dev")

    @pytest.mark.parametrize("target", ["staging", "main"])
    @pytest.mark.parametrize("command_tpl", [
        "git -C {path} switch {target} && git -C {path} merge --no-ff dev",
        "cd {path} && git switch {target} && git merge --no-ff dev",
    ])
    def test_should_block_with_heavy_gate_when_session_repo_path_switches_above_dev(
            self, tmp_path, command_tpl, target):
        repo = _make_repo_on(tmp_path, "feat/other", also=["dev", "staging", "main"])
        command = command_tpl.format(path=repo, target=target)

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} — session repo, target {target} (D-120)"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)
        # Read like no path: the message names the real target, not "unknown".
        assert f"'{target}'" in parsed.get("reason", ""), (
            f"{context}: target is readable, the message should name '{target}'; "
            f"got {parsed.get('reason')!r}"
        )

    @pytest.mark.parametrize("command_tpl", [
        "git -C {path} merge --no-ff dev",
        "cd {path} && git merge --no-ff dev",
    ])
    def test_should_block_with_heavy_gate_when_head_is_main_and_path_is_session_repo(
            self, tmp_path, command_tpl):
        repo = _make_repo_on(tmp_path, "main", also=["dev"])
        command = command_tpl.format(path=repo)

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} with HEAD on main"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)


class TestOtherRepoOrWorktreeStaysUnknown:
    """CONTRACT (D-129, the part that must NOT change): a path that resolves
    to another top-level — another repo, or another worktree of the session
    repo — keeps the target unknown -> heavy gate, even when the session
    repo sits on dev."""

    @pytest.mark.parametrize("command_tpl", [
        "git -C {path} merge --no-ff dev",
        "git -C {path} switch dev && git -C {path} merge --no-ff feat/x",
        "cd {path} && git merge --no-ff dev",
        "cd {path} && git switch dev && git merge --no-ff feat/x",
    ])
    def test_should_block_when_path_is_another_worktree_of_session_repo(
            self, tmp_path, command_tpl):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x", "main"])
        wt = str(tmp_path / "wt")
        rc, out, err = git_cmd(["worktree", "add", wt, "main"], repo)
        assert rc == 0, f"fixture setup failed adding worktree: {err}"
        command = command_tpl.format(path=wt)

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        context = f"{command!r} — second worktree on main, session repo on dev"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)

    @pytest.mark.parametrize("command_tpl", [
        "git -C {path} merge --no-ff dev",
        "cd {path} && git merge --no-ff dev",
    ])
    def test_should_block_when_absolute_path_is_another_repo(self, tmp_path, command_tpl):
        repo = _make_repo_on(tmp_path, "dev", also=["feat/x"])
        other = _make_repo(tmp_path, name="other", branch="dev")
        command = command_tpl.format(path=other)

        rc, parsed, stdout, stderr = _run_hook(repo, command)

        # Even with ../other on dev: another repo is not the session repo,
        # and D-129 only opens the session repo.
        context = f"{command!r} — another repo by absolute path"
        _assert_decision(parsed, stdout, rc, stderr, "block", context)
        _assert_heavy_gate_message(parsed, context)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
