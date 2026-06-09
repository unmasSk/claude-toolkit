"""
Acceptance contract for bin/release.py — ATDD / test-first pass.

These tests are intentionally RED until Ultron implements:
  - bin/release.py
  - bin/bump-version.py root-override (Task 2b)

Run: pytest unmassk-toolkit/tests/test_release.py
"""

import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date

import pytest

# ── Paths to real scripts ──────────────────────────────────────────────

# conftest.py defines SOURCE_ROOT as the plugin source root
# (unmassk-toolkit/). The real bin/ scripts live one level up.
_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_PLUGIN_ROOT = os.path.dirname(_THIS_DIR)          # unmassk-toolkit/
_REPO_ROOT = os.path.dirname(_PLUGIN_ROOT)          # git root

RELEASE_SCRIPT = os.path.join(_REPO_ROOT, "bin", "release.py")
BUMP_SCRIPT = os.path.join(_REPO_ROOT, "bin", "bump-version.py")


# ── Constants ──────────────────────────────────────────────────────────

PLUGIN_NAME = "unmassk-toolkit"
PLUGIN_VER_INITIAL = "1.3.0"

OTHER_PLUGIN_NAME = "unmassk-db"
OTHER_PLUGIN_VER_INITIAL = "2.0.0"

INITIAL_CHANGELOG = """\
# Changelog

## [Unreleased]

### Added
- New feature A that improves workflow.
- Improvement B for better performance.

## [1.3.0] - 2026-06-08

### Added
- Previous release note here.
"""

TODAY = date.today().isoformat()


# ── Fixture helpers ────────────────────────────────────────────────────

def _git(args, cwd, check=True, env=None):
    """Run a git command in cwd. Returns CompletedProcess."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True,
        env=merged_env,
        check=check,
    )


def _write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _make_plugin_json(version):
    return json.dumps({"name": PLUGIN_NAME, "version": version}, indent=2) + "\n"


def _make_other_plugin_json(version):
    return json.dumps({"name": OTHER_PLUGIN_NAME, "version": version}, indent=2) + "\n"


def _make_marketplace_json(plugin_ver=PLUGIN_VER_INITIAL, other_ver=OTHER_PLUGIN_VER_INITIAL):
    data = {
        "plugins": [
            {"name": PLUGIN_NAME, "version": plugin_ver},
            {"name": OTHER_PLUGIN_NAME, "version": other_ver},
        ]
    }
    return json.dumps(data, indent=2) + "\n"


def _setup_release_repo(tmp_path):
    """
    Build a complete fake marketplace repo in tmp_path with:
      - .claude-plugin/marketplace.json
      - <plugin>/.claude-plugin/plugin.json  (for both plugins)
      - CHANGELOG.md with non-empty [Unreleased]
      - git init, configured user, initial commit
      - bare remote in tmp_path/bare.git
      - upstream configured + pushed

    Returns (repo_path, bare_path).
    """
    repo = str(tmp_path / "repo")
    bare = str(tmp_path / "bare.git")

    os.makedirs(repo)

    # Marketplace JSON
    _write(
        os.path.join(repo, ".claude-plugin", "marketplace.json"),
        _make_marketplace_json(),
    )

    # Plugin JSON files
    _write(
        os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json"),
        _make_plugin_json(PLUGIN_VER_INITIAL),
    )
    _write(
        os.path.join(repo, OTHER_PLUGIN_NAME, ".claude-plugin", "plugin.json"),
        _make_other_plugin_json(OTHER_PLUGIN_VER_INITIAL),
    )

    # CHANGELOG
    _write(os.path.join(repo, "CHANGELOG.md"), INITIAL_CHANGELOG)

    # Git init
    _git(["init", "-b", "main"], repo)
    _git(["config", "user.email", "test@example.com"], repo)
    _git(["config", "user.name", "Test User"], repo)
    _git(["add", "-A"], repo)
    _git(["commit", "-m", "chore: initial commit"], repo)

    # Bare remote — use -b main so git clone from the bare repo has a valid HEAD
    subprocess.run(["git", "init", "--bare", "-b", "main", bare], capture_output=True, check=True)
    _git(["remote", "add", "origin", bare], repo)
    _git(["push", "-u", "origin", "main"], repo)

    return repo, bare


def _run_release(repo, args, env=None):
    """
    Invoke the real release.py via subprocess with cwd=repo.
    release.py resolves repo root via `git rev-parse --show-toplevel`
    over this cwd, so it operates on the temporary repo.

    NOTE (Ultron Task 2b): bump-version.py is called as a subprocess by
    release.py. bump-version.py currently resolves REPO_ROOT via __file__
    (file-relative), which would point to the real repo — not the temp repo.
    Task 2b must add a root-override mechanism (env var or CLI arg) so that
    release.py can pass the resolved root to bump-version.py. Until 2b is
    implemented, the happy-path and bump-related tests will fail for this
    reason even if release.py exists. Tests are red by design.
    """
    merged_env = {**os.environ, **(env or {})}
    result = subprocess.run(
        [sys.executable, RELEASE_SCRIPT] + args,
        cwd=repo,
        capture_output=True,
        text=True,
        env=merged_env,
        timeout=60,
    )
    return result.returncode, result.stdout, result.stderr


def _commit_count_on_remote(bare):
    """Return number of commits on main in the bare remote."""
    result = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=bare,
        capture_output=True,
        text=True,
    )
    return int(result.stdout.strip()) if result.returncode == 0 else 0


def _get_remote_head(bare):
    """Return the HEAD commit SHA of the bare remote."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=bare,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def _get_local_head(repo):
    result = _git(["rev-parse", "HEAD"], repo)
    return result.stdout.strip()


# ── Fixtures ──────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def require_release_script():
    """
    Every test in this module requires bin/release.py to exist.
    When the file is absent (before Ultron implements Task 2), this fixture
    fails with a clear, intentional RED — not a tautological pass from a
    missing-file exit code.
    """
    assert os.path.exists(RELEASE_SCRIPT), (
        f"bin/release.py does not exist yet ({RELEASE_SCRIPT}). "
        "This is the expected RED state. Ultron must implement Task 2."
    )


# ── Tests ──────────────────────────────────────────────────────────────


class TestHappyPath:
    """Happy path: full release with bump, changelog promotion, commit, push, verify."""

    def test_happy_path_bumps_versions_and_promotes_changelog(self, tmp_path):
        """
        release.py <plugin> <new-version> executes the full pipeline:
        - marketplace.json and plugin.json reflect the new version
        - CHANGELOG.md has ## [<new-version>] - <today> with prior [Unreleased] content
        - A fresh empty ## [Unreleased] is above it
        - The commit is present on the bare remote
        - Exit code is 0
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        # --- Version assertions ---
        marketplace = _read_json(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        plugin_entry = next(p for p in marketplace["plugins"] if p["name"] == PLUGIN_NAME)
        assert plugin_entry["version"] == new_ver, (
            f"marketplace.json still has old version: {plugin_entry['version']}"
        )

        plugin_json = _read_json(
            os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json")
        )
        assert plugin_json["version"] == new_ver, (
            f"plugin.json still has old version: {plugin_json['version']}"
        )

        # Both JSON files must agree (post-push verify contract)
        assert plugin_entry["version"] == plugin_json["version"]

        # --- CHANGELOG assertions ---
        changelog = _read(os.path.join(repo, "CHANGELOG.md"))

        # New version header present with today's date
        expected_header = f"## [{new_ver}] - {TODAY}"
        assert expected_header in changelog, (
            f"Expected '{expected_header}' in CHANGELOG.md.\n{changelog}"
        )

        # [Unreleased] content promoted: "New feature A" was under [Unreleased]
        assert "New feature A" in changelog
        assert "Improvement B" in changelog

        # A fresh empty [Unreleased] section is at the top
        # IMPLEMENTATION NOTE for Ultron: the pattern must be:
        #   ## [Unreleased]\n\n## [<new_ver>]
        # i.e. [Unreleased] with NO content between it and the new version header.
        unreleased_idx = changelog.index("## [Unreleased]")
        new_ver_idx = changelog.index(f"## [{new_ver}]")
        assert unreleased_idx < new_ver_idx, "[Unreleased] must appear before the new version"
        between = changelog[unreleased_idx + len("## [Unreleased]"):new_ver_idx].strip()
        assert between == "", (
            f"[Unreleased] section must be empty after promotion, found: {between!r}"
        )

        # --- Git / remote assertions ---
        remote_commits_before = 1  # only initial commit
        remote_commits_after = _commit_count_on_remote(bare)
        assert remote_commits_after > remote_commits_before, (
            "No new commit found on the bare remote"
        )

        local_head = _get_local_head(repo)
        remote_head = _get_remote_head(bare)
        assert local_head == remote_head, (
            f"Local HEAD {local_head} != remote HEAD {remote_head}: push did not propagate"
        )

    def test_other_plugin_not_mutated_by_release(self, tmp_path):
        """
        Only the released plugin's versions change.
        The other plugin in marketplace.json must be untouched.
        """
        repo, _ = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        marketplace = _read_json(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        other_entry = next(p for p in marketplace["plugins"] if p["name"] == OTHER_PLUGIN_NAME)
        assert other_entry["version"] == OTHER_PLUGIN_VER_INITIAL, (
            f"Other plugin version mutated: {other_entry['version']}"
        )


class TestDryRun:
    """--dry-run: prints the plan, makes zero changes, exits 0."""

    def test_dry_run_makes_no_changes(self, tmp_path):
        """
        --dry-run must not mutate any file, create any commit, or push anything.
        Exit code must be 0.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        initial_remote_head = _get_remote_head(bare)

        # Read initial file contents to diff later
        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_plugin_json = _read(
            os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json")
        )
        initial_changelog = _read(os.path.join(repo, "CHANGELOG.md"))

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--dry-run"])

        assert rc == 0, f"Expected exit 0 for --dry-run, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        # No file mutations
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _read(os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json")) == initial_plugin_json
        assert _read(os.path.join(repo, "CHANGELOG.md")) == initial_changelog

        # No new commits on remote
        assert _get_remote_head(bare) == initial_remote_head, (
            "--dry-run must not push any commit"
        )

        # No new local commits either
        assert _get_local_head(repo) == initial_remote_head, (
            "--dry-run must not create a local commit"
        )

    def test_dry_run_prints_plan(self, tmp_path):
        """
        --dry-run output must describe what would happen.
        IMPLEMENTATION NOTE for Ultron: stdout must mention the plugin name
        and new version so the user can verify the plan before running for real.
        """
        repo, _ = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--dry-run"])

        combined = stdout + stderr
        assert PLUGIN_NAME in combined, "--dry-run output must mention the plugin name"
        assert new_ver in combined, "--dry-run output must mention the new version"


class TestPreflightDirtyTree:
    """Pre-flight: abort if working tree is dirty (without --allow-dirty)."""

    def test_aborts_on_dirty_tree(self, tmp_path):
        """
        If working tree has unstaged changes and --allow-dirty is not set,
        release.py must exit != 0 without mutating any file.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Dirty the tree
        _write(os.path.join(repo, "dirty.txt"), "uncommitted change")

        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, "Expected non-zero exit for dirty tree without --allow-dirty"

        # No mutations
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head


class TestPreflightVersionNotGreater:
    """Pre-flight: abort if new-version is not strictly greater than current."""

    def test_aborts_on_equal_version(self, tmp_path):
        """Same version as current must be rejected (fail-closed)."""
        repo, bare = _setup_release_repo(tmp_path)
        same_ver = PLUGIN_VER_INITIAL  # 1.3.0

        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, same_ver])

        assert rc != 0, f"Expected non-zero exit for same version, got {rc}"
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head

    def test_aborts_on_lower_version(self, tmp_path):
        """Lower version than current must be rejected (fail-closed)."""
        repo, bare = _setup_release_repo(tmp_path)
        lower_ver = "1.2.0"

        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, lower_ver])

        assert rc != 0, f"Expected non-zero exit for lower version, got {rc}"
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head


class TestPreflightEmptyUnreleased:
    """Pre-flight: abort if [Unreleased] section has no content."""

    def test_aborts_on_empty_unreleased(self, tmp_path):
        """
        If CHANGELOG.md has ## [Unreleased] with no content (blank lines only
        until the next ## header), release.py must exit != 0 without mutating.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Overwrite with empty [Unreleased]
        empty_changelog = """\
# Changelog

## [Unreleased]

## [1.3.0] - 2026-06-08

### Added
- Previous release.
"""
        _write(os.path.join(repo, "CHANGELOG.md"), empty_changelog)
        # Stage and commit so tree is clean
        _git(["add", "CHANGELOG.md"], repo)
        _git(["commit", "-m", "test: empty unreleased"], repo)
        _git(["push", "origin", "main"], repo)

        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, f"Expected non-zero exit for empty [Unreleased], got {rc}"
        # CHANGELOG must not be mutated
        assert _read(os.path.join(repo, "CHANGELOG.md")) == empty_changelog
        assert _get_remote_head(bare) == initial_remote_head


class TestPreflightPluginNotFound:
    """Pre-flight: abort if plugin does not exist in marketplace.json."""

    def test_aborts_on_unknown_plugin(self, tmp_path):
        """Plugin not in marketplace.json must be rejected before any mutation."""
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"
        unknown_plugin = "nonexistent-plugin"

        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [unknown_plugin, new_ver])

        assert rc != 0, f"Expected non-zero exit for unknown plugin, got {rc}"
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head


class TestPreflightNoUpstream:
    """Pre-flight: abort if current branch has no upstream configured."""

    def test_aborts_when_no_upstream(self, tmp_path):
        """
        If git branch has no upstream (no tracking remote), release.py must
        exit != 0 and make no mutations.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Remove upstream tracking info
        _git(["branch", "--unset-upstream"], repo)

        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, f"Expected non-zero exit when no upstream, got {rc}"
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head


class TestPreflightBehindRemote:
    """Pre-flight: abort if local branch is behind the remote."""

    def test_aborts_when_local_behind_remote(self, tmp_path):
        """
        If the remote has commits not in local HEAD (local is behind),
        release.py must abort and tell the user to pull first.
        Exit != 0, no mutations.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Clone a second copy, commit to it, push to bare — now 'repo' is behind
        repo2 = str(tmp_path / "repo2")
        _git(["clone", bare, repo2], str(tmp_path))
        _git(["config", "user.email", "test@example.com"], repo2)
        _git(["config", "user.name", "Test User"], repo2)
        _write(os.path.join(repo2, "extra.txt"), "extra commit from another clone")
        _git(["add", "extra.txt"], repo2)
        _git(["commit", "-m", "chore: extra commit from repo2"], repo2)
        _git(["push", "origin", "main"], repo2)

        # repo is now behind bare by 1 commit
        initial_local_head = _get_local_head(repo)
        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, f"Expected non-zero exit when local is behind remote, got {rc}"
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        # Local HEAD must not have changed (no stray commits created)
        assert _get_local_head(repo) == initial_local_head


class TestAllowDirty:
    """--allow-dirty: proceed despite dirty tree, but only stage the 3 release files."""

    def test_allow_dirty_succeeds_and_stages_only_release_files(self, tmp_path):
        """
        --allow-dirty overrides the dirty-tree preflight check.
        The commit must contain ONLY the 3 release files:
          - <plugin>/.claude-plugin/plugin.json
          - .claude-plugin/marketplace.json
          - CHANGELOG.md

        The untracked/modified bystander file must NOT appear in the commit.
        This is a hard contract: a dirty release staging other files would
        corrupt the repo's cleanliness guarantees.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Create a bystander untracked file (not related to this release)
        bystander = os.path.join(repo, "bystander.txt")
        _write(bystander, "this should NOT be in the release commit")

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--allow-dirty"])

        assert rc == 0, f"Expected exit 0 with --allow-dirty, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        # Verify versions were bumped
        marketplace = _read_json(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        plugin_entry = next(p for p in marketplace["plugins"] if p["name"] == PLUGIN_NAME)
        assert plugin_entry["version"] == new_ver

        # Check what files were in the release commit
        # IMPLEMENTATION NOTE for Ultron: use `git show --name-only HEAD` to get files in commit
        result = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in result.stdout.splitlines() if line.strip()]

        # The 3 release files must be in the commit
        assert any("marketplace.json" in f for f in files_in_commit), (
            f"marketplace.json not in commit. Files: {files_in_commit}"
        )
        assert any("plugin.json" in f for f in files_in_commit), (
            f"plugin.json not in commit. Files: {files_in_commit}"
        )
        assert any("CHANGELOG.md" in f for f in files_in_commit), (
            f"CHANGELOG.md not in commit. Files: {files_in_commit}"
        )

        # The bystander must NOT be in the commit
        assert not any("bystander.txt" in f for f in files_in_commit), (
            f"Bystander file leaked into the release commit! Files: {files_in_commit}"
        )

        # Bystander must still be present and untracked (not deleted, not staged)
        assert os.path.exists(bystander), "Bystander file must still exist after release"


class TestPushFailure:
    """Push failure: local commit exists, exit != 0, clear error message."""

    def test_push_failure_leaves_local_commit_and_exits_nonzero(self, tmp_path):
        """
        If push fails (e.g. remote becomes unreachable after pre-flight),
        release.py must:
          - exit != 0
          - leave the local commit in place (do not roll back silently)
          - print a message making it clear what happened

        IMPLEMENTATION NOTE for Ultron: the script must not swallow push errors
        and exit 0. The post-push verify must catch origin/<branch>..HEAD != 0
        and fail with a non-zero exit. The local commit is recoverable; silent
        success is not.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        initial_remote_head = _get_remote_head(bare)

        # Break the remote by removing the bare dir after pre-flight would pass
        # We simulate this by making the remote URL point to a nonexistent path
        nonexistent = str(tmp_path / "gone.git")
        _git(["remote", "set-url", "origin", nonexistent], repo)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, f"Expected non-zero exit on push failure, got {rc}"

        # Local commit with bumped versions must exist (do not roll back)
        local_plugin_json = _read_json(
            os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json")
        )
        # IMPLEMENTATION NOTE for Ultron: the local commit is intentional —
        # it lets the user `git push` manually to recover without losing work.
        # The test asserts the local HEAD advanced (commit was created locally).
        local_head = _get_local_head(repo)
        # Remote HEAD on the original bare dir is unchanged (we broke the URL)
        # so we just verify local advanced past the original state:
        assert local_head != initial_remote_head, (
            "Expected a local commit to exist even after push failure"
        )

        # Output must mention the failure clearly
        combined = stdout + stderr
        assert combined.strip() != "", "Push failure must produce diagnostic output"


class TestInvalidInputs:
    """Edge cases: invalid semver, invalid plugin name."""

    def test_aborts_on_invalid_semver(self, tmp_path):
        """Passing a non-semver version string must abort with exit != 0."""
        repo, bare = _setup_release_repo(tmp_path)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "not-a-version"])

        assert rc != 0, "Expected non-zero exit for invalid semver"

    def test_aborts_on_invalid_plugin_name(self, tmp_path):
        """Passing a plugin name with invalid characters must abort with exit != 0."""
        repo, bare = _setup_release_repo(tmp_path)

        # Plugin name with path traversal / invalid chars
        rc, stdout, stderr = _run_release(repo, ["../evil", "1.4.0"])

        assert rc != 0, "Expected non-zero exit for invalid plugin name"
