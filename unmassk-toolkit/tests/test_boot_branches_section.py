"""
Regression coverage for the BRANCHES boot section (lib/boot_git_checks.py)
-- get_remote_branches() and render_branches_section() -- added by Ultron
(plugin/boot decision, 2026-07-15 phase 2) without a dedicated test file.
Linear mode: the code already exists and is green; this file only fills
the missing coverage. No production code is touched here.

Contract fixed here:
  1. Lists the resolved remote's branches (refs/remotes/<remote>/*),
     ordered by last-commit author date DESCENDING (newest first).
  2. Marks the current branch " (current)"; no other branch gets it.
  3. Each line carries short sha + last-commit subject + relative time.
  4. Excludes the remote's symbolic HEAD alias
     (refs/remotes/<remote>/HEAD).
  5. Caps at BOOT_MAX_REMOTE_BRANCHES (20), with an explicit
     "(N more...)" line stating the true total -- never a silent cut.
  6. remote_name=None (unrelated/absent upstream, already nulled
     upstream) renders nothing.
  7. Fail-open: a git read failure collapses to [] / [], never an
     exception.
  8. Scoped to ONE remote's own refs -- never mixes another configured
     remote's branches (never `git branch -a` / `--all`).

Fixture model (unmassk-standards §34 -- no fabricated ground truth): real
bare "origin" remote(s) + a real working clone. Branches are created with
GIT_AUTHOR_DATE/GIT_COMMITTER_DATE pinned to explicit, distinct epoch
values (same raw-format technique as test_boot_pending_next_cutoff.py),
never a hand-typed dict standing in for a branch. refs/remotes/<remote>/*
is refreshed with the SAME refspec fetch_memory_ref() uses in production
(`+refs/heads/*:refs/remotes/<remote>/*`), so tests read exactly the ref
shape the real hardened fetch populates -- not a hand-built ref layout.

Call pattern: IN-PROCESS via monkeypatch.chdir() + a direct import of
boot_git_checks (git_helpers.run_git's cwd=None inherits the process cwd,
which monkeypatch.chdir() changes for real -- no subprocess/fake-git
needed for these two pure data/render functions; see
pending-next-cutoff-contract-notes.md for the same pattern applied to
extract_memory()).

Out of scope (explicitly, per this project's CLAUDE.md threat model --
"security against a malicious attacker DOES NOT APPLY" / "a test that
simulates a malicious attacker is surplus -- cut it"): the
`_is_safe_remote_name()` allowlist guard inside get_remote_branches() is
NOT independently exercised here with a crafted glob/shell-metacharacter
remote name. That guard is defensive coding against a hostile config, not
against this system breaking itself, and this project has a single owner.

Build mode: linear (code already implemented and green).
"""

import os
import re
import sys

from conftest import LIB_DIR, git_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

import boot_git_checks  # noqa: E402

BOOT_MAX_REMOTE_BRANCHES = boot_git_checks.BOOT_MAX_REMOTE_BRANCHES

_BASE_TS = 1_700_000_000  # arbitrary fixed epoch -- deterministic ordering, independent of wall clock


# ── Repo / remote fixtures ──────────────────────────────────────────────


def _seed_bare(tmp_path, name="origin-bare"):
    """A bare remote that already HAS a branch (main) BEFORE anything
    clones it. Verified live (see conversation record): git only
    auto-creates the symbolic refs/remotes/<remote>/HEAD alias when
    cloning an ALREADY-POPULATED remote -- an empty-bare-then-push-after-
    clone sequence never creates it. test_excludes_symbolic_head_alias
    below depends on this alias genuinely existing, so every fixture in
    this file seeds the bare remote before cloning it.
    """
    seed = str(tmp_path / f"{name}-seed")
    os.makedirs(seed)
    git_cmd(["init", "-b", "main"], seed)
    git_cmd(["config", "user.email", "seed@test.com"], seed)
    git_cmd(["config", "user.name", "Seed"], seed)
    date_env = {
        "GIT_AUTHOR_DATE": f"{_BASE_TS - 1000} +0000",
        "GIT_COMMITTER_DATE": f"{_BASE_TS - 1000} +0000",
    }
    git_cmd(["commit", "--allow-empty", "-m", "init"], seed, env=date_env)

    bare = str(tmp_path / f"{name}.git")
    git_cmd(["clone", "--bare", seed, bare], str(tmp_path))
    return bare


def _clone_repo(bare, tmp_path, name="repo"):
    repo = str(tmp_path / name)
    git_cmd(["clone", bare, repo], str(tmp_path))
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    return repo


def _commit_at(repo, message, ts):
    """One empty commit on the CURRENT branch, author/committer date
    pinned to `ts` (git's own raw "<epoch> +0000" format -- same technique
    as test_boot_pending_next_cutoff.py, exact value get_remote_branches()
    reads back via `%(authordate:unix)`).
    """
    date_env = {"GIT_AUTHOR_DATE": f"{ts} +0000", "GIT_COMMITTER_DATE": f"{ts} +0000"}
    git_cmd(["commit", "--allow-empty", "-m", message], repo, env=date_env)


def _push_new_branch(repo, remote, branch_name, message, ts, from_ref="main"):
    """New branch off `from_ref`, one commit with a pinned author date,
    pushed to `remote`. Returns to `from_ref` afterward so repeated calls
    always branch off the same known point.
    """
    git_cmd(["checkout", "-b", branch_name, from_ref], repo)
    _commit_at(repo, message, ts)
    git_cmd(["push", "-u", remote, branch_name], repo)
    git_cmd(["checkout", from_ref], repo)


def _sync_remote_tracking(repo, remote="origin"):
    """Refresh refs/remotes/<remote>/* from the bare remote's CURRENT
    branches -- the SAME refspec fetch_memory_ref() uses in production
    (+refs/heads/*:refs/remotes/<remote>/*, see
    boot_git_checks.py::_run_hardened_fetch), so tests read exactly the
    ref shape the real hardened fetch populates.
    """
    git_cmd(["fetch", remote, "--no-tags", "--", f"+refs/heads/*:refs/remotes/{remote}/*"], repo)


def _get_remote_branches(repo, remote_name, monkeypatch):
    monkeypatch.chdir(repo)
    return boot_git_checks.get_remote_branches(remote_name)


def _render_branches_section(repo, remote_name, current_branch, monkeypatch):
    monkeypatch.chdir(repo)
    return boot_git_checks.render_branches_section(remote_name, current_branch)


# ── get_remote_branches() ────────────────────────────────────────────────


class TestGetRemoteBranchesOrdering:
    """Contract item 1: newest-last-commit-date first."""

    def test_orders_by_author_date_descending(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)

        _push_new_branch(repo, "origin", "oldest-branch", "oldest work", _BASE_TS + 100)
        _push_new_branch(repo, "origin", "middle-branch", "middle work", _BASE_TS + 200)
        _push_new_branch(repo, "origin", "newest-branch", "newest work", _BASE_TS + 300)
        _sync_remote_tracking(repo)

        branches = _get_remote_branches(repo, "origin", monkeypatch)
        names = [b[0] for b in branches]

        assert names.index("newest-branch") < names.index("middle-branch") < names.index("oldest-branch"), (
            f"expected newest-first order by last-commit author date, got: {names}"
        )


class TestGetRemoteBranchesExcludesHeadAlias:
    """Contract item 4: the remote's symbolic HEAD alias is not a distinct
    branch and must never be listed."""

    def test_excludes_symbolic_head_alias(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        _push_new_branch(repo, "origin", "feature-x", "feature work", _BASE_TS + 100)
        _sync_remote_tracking(repo)

        # Setup sanity: the real clone must have created the alias this
        # test guards against, or the assertion below would pass vacuously.
        rc, _out, _err = git_cmd(["symbolic-ref", "refs/remotes/origin/HEAD"], repo)
        assert rc == 0, "setup sanity: origin/HEAD alias must exist for this test to mean anything"

        branches = _get_remote_branches(repo, "origin", monkeypatch)
        names = [b[0] for b in branches]

        assert "HEAD" not in names
        assert set(names) == {"main", "feature-x"}


class TestGetRemoteBranchesEntryContent:
    """Contract item 3: each entry carries a short sha, the last commit's
    subject, and a raw date the caller can format as relative time."""

    def test_entry_has_sha_subject_and_date(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        marker = "UNIQUE-COMMIT-SUBJECT-7f3a"
        _push_new_branch(repo, "origin", "feature-y", marker, _BASE_TS + 50)
        _sync_remote_tracking(repo)

        branches = _get_remote_branches(repo, "origin", monkeypatch)
        entry = next(b for b in branches if b[0] == "feature-y")
        _branch_name, sha, date_str, subject = entry

        assert re.fullmatch(r"[0-9a-f]{4,40}", sha), f"expected a short hex sha, got {sha!r}"
        assert subject == marker
        assert date_str.isdigit() and int(date_str) == _BASE_TS + 50, (
            f"expected the pinned author-date epoch ({_BASE_TS + 50}), got {date_str!r}"
        )


class TestGetRemoteBranchesNoneGuard:
    """Contract item 6: remote_name=None (confirmed-unrelated or absent
    upstream, already nulled by the caller) means nothing is listed."""

    def test_none_remote_returns_empty_list(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        monkeypatch.chdir(repo)

        assert boot_git_checks.get_remote_branches(None) == []

    def test_empty_string_remote_returns_empty_list(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        monkeypatch.chdir(repo)

        assert boot_git_checks.get_remote_branches("") == []


class TestGetRemoteBranchesFailOpen:
    """Contract item 7: a git read failure collapses to [], never raises,
    so a bad ref read can never crash the boot."""

    def test_git_failure_returns_empty_never_raises(self, tmp_path, monkeypatch):
        not_a_repo = str(tmp_path / "not-a-repo")
        os.makedirs(not_a_repo)
        monkeypatch.chdir(not_a_repo)

        result = boot_git_checks.get_remote_branches("origin")

        assert result == []

    def test_remote_configured_but_never_fetched_returns_empty(self, tmp_path, monkeypatch):
        """rc==0 but empty output (a real, distinct git success shape from
        the outright-failure case above): a remote can be `git remote add`-
        ed without ever being fetched, leaving zero refs/remotes/<name>/*
        on disk even though the repo and the remote entry are both valid.
        """
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        ghost_bare = _seed_bare(tmp_path, name="ghost-bare")
        git_cmd(["remote", "add", "ghost", ghost_bare], repo)
        # Deliberately never fetched.

        result = _get_remote_branches(repo, "ghost", monkeypatch)

        assert result == []


class TestGetRemoteBranchesSingleRemoteScope:
    """Contract item 8: scoped to the ONE resolved remote's own refs --
    never mixes another configured remote's branches."""

    def test_never_mixes_another_configured_remote(self, tmp_path, monkeypatch):
        origin_bare = _seed_bare(tmp_path, name="origin-bare")
        other_bare = _seed_bare(tmp_path, name="other-bare")

        repo = _clone_repo(origin_bare, tmp_path, name="repo")
        git_cmd(["remote", "add", "other", other_bare], repo)

        _push_new_branch(repo, "origin", "origin-only-branch", "origin work", _BASE_TS + 10)
        _push_new_branch(repo, "other", "other-only-branch", "other work", _BASE_TS + 20)

        _sync_remote_tracking(repo, remote="origin")
        _sync_remote_tracking(repo, remote="other")

        origin_names = {b[0] for b in _get_remote_branches(repo, "origin", monkeypatch)}
        other_names = {b[0] for b in _get_remote_branches(repo, "other", monkeypatch)}

        assert "other-only-branch" not in origin_names
        assert "origin-only-branch" not in other_names
        assert "other-only-branch" in other_names
        assert "origin-only-branch" in origin_names


# ── render_branches_section() ────────────────────────────────────────────


class TestRenderBranchesSectionCurrentMarker:
    """Contract item 2: the current branch is marked " (current)"; no
    other branch gets it."""

    def test_marks_only_the_current_branch(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        _push_new_branch(repo, "origin", "feature-z", "feature work", _BASE_TS + 10)
        _sync_remote_tracking(repo)

        lines = _render_branches_section(repo, "origin", "main", monkeypatch)

        main_line = next(l for l in lines if l.strip().startswith("main:") or l.strip().startswith("main "))
        feature_line = next(l for l in lines if l.strip().startswith("feature-z:"))

        assert "(current)" in main_line
        assert "(current)" not in feature_line


class TestRenderBranchesSectionLineContent:
    """Contract item 3, at the rendered-line level: sha + subject + a
    relative-time suffix are all present."""

    def test_line_has_sha_subject_and_relative_time(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        marker = "RENDER-CONTENT-MARKER-a91c"
        _push_new_branch(repo, "origin", "feature-w", marker, _BASE_TS + 5)
        _sync_remote_tracking(repo)

        raw = _get_remote_branches(repo, "origin", monkeypatch)
        entry = next(b for b in raw if b[0] == "feature-w")
        _branch_name, expected_sha, _date_str, _subject = entry

        lines = _render_branches_section(repo, "origin", "main", monkeypatch)
        line = next(l for l in lines if marker in l)

        assert expected_sha in line, f"expected sha {expected_sha!r} in rendered line: {line!r}"
        assert marker in line
        assert re.search(r"\d+[mhdw] ago|just now|unknown", line), (
            f"expected a relative-time suffix in the rendered line: {line!r}"
        )


class TestRenderBranchesSectionOrdering:
    """Contract item 1, at the rendered-line level: order is preserved
    from get_remote_branches() -- newest last-commit first."""

    def test_render_preserves_newest_first_order(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        _push_new_branch(repo, "origin", "oldest-r", "oldest render", _BASE_TS + 100)
        _push_new_branch(repo, "origin", "middle-r", "middle render", _BASE_TS + 200)
        _push_new_branch(repo, "origin", "newest-r", "newest render", _BASE_TS + 300)
        _sync_remote_tracking(repo)

        lines = _render_branches_section(repo, "origin", "main", monkeypatch)
        text = "\n".join(lines)
        positions = {name: text.find(name) for name in ("newest-r", "middle-r", "oldest-r")}

        assert all(p != -1 for p in positions.values()), positions
        assert positions["newest-r"] < positions["middle-r"] < positions["oldest-r"], positions


class TestRenderBranchesSectionCap:
    """Contract item 5: caps at BOOT_MAX_REMOTE_BRANCHES, with an explicit
    '(N more...)' line stating the true total -- never a silent cut."""

    def test_caps_at_boot_max_with_explicit_more_line(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)

        # BOOT_MAX_REMOTE_BRANCHES new branches + the pre-existing "main"
        # branch guarantees the true total exceeds the cap by exactly 1 --
        # the minimum needed to prove capping without paying for a much
        # larger fixture.
        for i in range(BOOT_MAX_REMOTE_BRANCHES):
            _push_new_branch(repo, "origin", f"branch-{i:02d}", f"work {i}", _BASE_TS + i)
        _sync_remote_tracking(repo)

        raw = _get_remote_branches(repo, "origin", monkeypatch)
        total = len(raw)  # the TRUE total this run actually produced -- never hand-computed
        assert total > BOOT_MAX_REMOTE_BRANCHES, (
            f"setup sanity: need more branches than the cap to test capping, got {total}"
        )

        lines = _render_branches_section(repo, "origin", "main", monkeypatch)
        shown_branch_lines = [
            l for l in lines if l.startswith("  ") and ":" in l and "more branch" not in l
        ]
        assert len(shown_branch_lines) == BOOT_MAX_REMOTE_BRANCHES, (
            f"expected exactly {BOOT_MAX_REMOTE_BRANCHES} branch lines, got "
            f"{len(shown_branch_lines)}: {shown_branch_lines}"
        )

        remaining = total - BOOT_MAX_REMOTE_BRANCHES
        more_line = next((l for l in lines if "more branch" in l), None)
        assert more_line is not None, (
            "expected an explicit '(N more...)' line -- a cap must never truncate silently"
        )
        assert f"({remaining} more branch(es) not shown, {total} total)" in more_line, (
            f"expected the true remaining count ({remaining}) and total ({total}) "
            f"in the more-line, got: {more_line!r}"
        )


class TestRenderBranchesSectionNoneGuard:
    """Contract item 6, at the render level."""

    def test_none_remote_renders_nothing(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)

        lines = _render_branches_section(repo, None, "main", monkeypatch)

        assert lines == []


class TestRenderBranchesSectionFailOpen:
    """Contract item 7, at the render level: a read failure renders
    nothing, never raises."""

    def test_git_failure_renders_nothing_never_raises(self, tmp_path, monkeypatch):
        not_a_repo = str(tmp_path / "not-a-repo")
        os.makedirs(not_a_repo)
        monkeypatch.chdir(not_a_repo)

        lines = boot_git_checks.render_branches_section("origin", "main")

        assert lines == []

    def test_remote_configured_but_never_fetched_renders_nothing(self, tmp_path, monkeypatch):
        bare = _seed_bare(tmp_path)
        repo = _clone_repo(bare, tmp_path)
        ghost_bare = _seed_bare(tmp_path, name="ghost-bare-render")
        git_cmd(["remote", "add", "ghost", ghost_bare], repo)

        lines = _render_branches_section(repo, "ghost", "main", monkeypatch)

        assert lines == []


class TestRenderBranchesSectionSingleRemoteScope:
    """Contract item 8, at the render level."""

    def test_never_lists_another_configured_remotes_branch(self, tmp_path, monkeypatch):
        origin_bare = _seed_bare(tmp_path, name="origin-bare2")
        other_bare = _seed_bare(tmp_path, name="other-bare2")
        repo = _clone_repo(origin_bare, tmp_path, name="repo2")
        git_cmd(["remote", "add", "other", other_bare], repo)

        _push_new_branch(repo, "other", "other-secret-branch", "other secret", _BASE_TS + 10)
        _sync_remote_tracking(repo, remote="other")

        lines = _render_branches_section(repo, "origin", "main", monkeypatch)
        text = "\n".join(lines)

        assert "other-secret-branch" not in text
