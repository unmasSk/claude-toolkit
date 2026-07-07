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

# `import bin.release_helpers` / `import bin.release` below rely on
# `_REPO_ROOT` (git root, parent of `bin/`) being on sys.path so `bin/`
# resolves as a namespace package (no __init__.py). This previously worked
# ONLY by accident: `python3 -m pytest ...` invoked from the git root
# inserts the current working directory into sys.path[0], which happened
# to BE the git root. Any other invocation shape (pytest run from inside
# tests/, a bare `pytest` entry point instead of `python -m pytest`, or a
# CI runner with a different cwd -- confirmed on Windows CI, issue #50)
# leaves `bin` unresolvable and fails every test below with
# `ModuleNotFoundError: No module named 'bin'`. Insert it explicitly so the
# import is correct by construction regardless of cwd or invocation method.
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

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

        # Break only the push URL, leaving the fetch URL (remote.origin.url) intact.
        # This way git fetch succeeds (pre-flight passes, local is up to date),
        # the script proceeds to create the local commit, then push fails.
        # Using a nonexistent pushurl while keeping origin.url valid for fetch.
        nonexistent_push = str(tmp_path / "gone-push.git")
        _git(["config", "remote.origin.pushurl", nonexistent_push], repo)

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


# ── Hardening: semver non-trivial numeric ordering ─────────────────────────


class TestSemverNumericOrdering:
    """
    Semver comparisons must be numeric, not lexicographic.
    '1.10.0' > '1.9.0' — string compare would wrongly say 1.9 > 1.10.
    These cases surface the bug if _semver_tuple ever uses string compare.
    """

    def _setup_repo_with_ver(self, tmp_path, current_ver):
        """
        Build a fake repo where the plugin starts at current_ver,
        then set it up cleanly for a release attempt.
        """
        repo = str(tmp_path / "repo")
        bare = str(tmp_path / "bare.git")
        os.makedirs(repo)

        plugin_json = json.dumps(
            {"name": PLUGIN_NAME, "version": current_ver}, indent=2
        ) + "\n"
        marketplace = json.dumps(
            {
                "plugins": [
                    {"name": PLUGIN_NAME, "version": current_ver},
                    {"name": OTHER_PLUGIN_NAME, "version": OTHER_PLUGIN_VER_INITIAL},
                ]
            },
            indent=2,
        ) + "\n"

        _write(os.path.join(repo, ".claude-plugin", "marketplace.json"), marketplace)
        _write(
            os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json"),
            plugin_json,
        )
        _write(
            os.path.join(repo, OTHER_PLUGIN_NAME, ".claude-plugin", "plugin.json"),
            _make_other_plugin_json(OTHER_PLUGIN_VER_INITIAL),
        )
        _write(os.path.join(repo, "CHANGELOG.md"), INITIAL_CHANGELOG)

        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "test@example.com"], repo)
        _git(["config", "user.name", "Test User"], repo)
        _git(["add", "-A"], repo)
        _git(["commit", "-m", "chore: initial commit"], repo)
        subprocess.run(
            ["git", "init", "--bare", "-b", "main", bare],
            capture_output=True,
            check=True,
        )
        _git(["remote", "add", "origin", bare], repo)
        _git(["push", "-u", "origin", "main"], repo)

        return repo, bare

    def test_1_10_0_accepted_over_1_9_0(self, tmp_path):
        """
        Current = 1.9.0, new = 1.10.0 must be ACCEPTED (numeric: 10 > 9).
        String compare would wrongly treat '1.10' < '1.9'.
        """
        repo, bare = self._setup_repo_with_ver(tmp_path, "1.9.0")
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.10.0"])
        assert rc == 0, (
            f"1.10.0 > 1.9.0 must be accepted (numeric ordering). "
            f"Got exit {rc}.\nstdout: {stdout}\nstderr: {stderr}"
        )
        marketplace = _read_json(
            os.path.join(repo, ".claude-plugin", "marketplace.json")
        )
        entry = next(p for p in marketplace["plugins"] if p["name"] == PLUGIN_NAME)
        assert entry["version"] == "1.10.0"

    def test_2_0_0_accepted_over_1_99_99(self, tmp_path):
        """
        Current = 1.99.99, new = 2.0.0 must be ACCEPTED (major bump).
        String compare of '2' > '1' happens to work, but the patch component
        99.99 is the dangerous part — a correct tuple comparison handles it.
        """
        repo, bare = self._setup_repo_with_ver(tmp_path, "1.99.99")
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "2.0.0"])
        assert rc == 0, (
            f"2.0.0 > 1.99.99 must be accepted. "
            f"Got exit {rc}.\nstdout: {stdout}\nstderr: {stderr}"
        )
        marketplace = _read_json(
            os.path.join(repo, ".claude-plugin", "marketplace.json")
        )
        entry = next(p for p in marketplace["plugins"] if p["name"] == PLUGIN_NAME)
        assert entry["version"] == "2.0.0"

    def test_1_9_0_rejected_as_lower_than_1_10_0(self, tmp_path):
        """
        Current = 1.10.0, new = 1.9.0 must be REJECTED.
        9 < 10 numerically — a string compare would wrongly accept it.
        """
        repo, bare = self._setup_repo_with_ver(tmp_path, "1.10.0")
        initial_marketplace = _read(
            os.path.join(repo, ".claude-plugin", "marketplace.json")
        )
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.9.0"])

        assert rc != 0, (
            "1.9.0 < 1.10.0: must be rejected. "
            f"Got exit {rc}.\nstdout: {stdout}\nstderr: {stderr}"
        )
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head

    def test_1_10_0_rejected_as_equal_to_1_10_0(self, tmp_path):
        """
        Current = 1.10.0, new = 1.10.0 must be REJECTED (equal, not strictly greater).
        """
        repo, bare = self._setup_repo_with_ver(tmp_path, "1.10.0")
        initial_marketplace = _read(
            os.path.join(repo, ".claude-plugin", "marketplace.json")
        )
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.10.0"])

        assert rc != 0, (
            "1.10.0 == 1.10.0: equal version must be rejected. "
            f"Got exit {rc}.\nstdout: {stdout}\nstderr: {stderr}"
        )
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head

    def test_1_99_99_rejected_as_lower_than_2_0_0(self, tmp_path):
        """
        Current = 2.0.0, new = 1.99.99 must be REJECTED.
        """
        repo, bare = self._setup_repo_with_ver(tmp_path, "2.0.0")
        initial_marketplace = _read(
            os.path.join(repo, ".claude-plugin", "marketplace.json")
        )
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.99.99"])
        assert rc != 0, (
            "1.99.99 < 2.0.0: must be rejected. "
            f"Got exit {rc}.\nstdout: {stdout}\nstderr: {stderr}"
        )
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace


# ── Hardening: CHANGELOG format precision ──────────────────────────────────


class TestChangelogPromotion:
    """
    CHANGELOG promotion format contract (precision beyond the acceptance tests):
    - Exactly ONE blank line between ## [Unreleased] and ## [<ver>] - <date>
    - Previous [Unreleased] content preserved verbatim under the new heading
    - Date in the heading = today in ISO format (YYYY-MM-DD)
    """

    def test_exactly_one_blank_line_between_unreleased_and_new_heading(self, tmp_path):
        """
        After promotion the gap between ## [Unreleased] and ## [<ver>] - <date>
        must be EXACTLY one blank line — no more, no less.
        Keep a Changelog canonical format.
        """
        repo, _ = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc == 0, f"exit {rc}\nstdout: {stdout}\nstderr: {stderr}"

        changelog = _read(os.path.join(repo, "CHANGELOG.md"))
        unreleased_header = "## [Unreleased]"
        new_header = f"## [{new_ver}] - {TODAY}"

        idx_unreleased = changelog.index(unreleased_header)
        idx_new_ver = changelog.index(new_header)

        # The text between end of "## [Unreleased]" and start of "## [<ver>]"
        between = changelog[idx_unreleased + len(unreleased_header):idx_new_ver]

        # Must be exactly "\n\n" — one newline ending the [Unreleased] line,
        # one blank line, then the new heading starts.
        assert between == "\n\n", (
            f"Expected exactly one blank line between headings. "
            f"Got {between!r}"
        )

    def test_unreleased_content_preserved_verbatim_under_new_heading(self, tmp_path):
        """
        The content that was under ## [Unreleased] must appear verbatim
        under the new ## [<ver>] - <date> heading.
        It must not be truncated, reordered, or HTML-escaped.
        """
        repo, _ = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # The INITIAL_CHANGELOG has two items under [Unreleased]:
        #   "New feature A that improves workflow."
        #   "Improvement B for better performance."
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])
        assert rc == 0, f"exit {rc}\nstdout: {stdout}\nstderr: {stderr}"

        changelog = _read(os.path.join(repo, "CHANGELOG.md"))
        new_header = f"## [{new_ver}] - {TODAY}"
        idx_new_ver = changelog.index(new_header)

        # Content after the new heading (up to next ## or end)
        after_new = changelog[idx_new_ver + len(new_header):]
        next_section = re.search(r"^## \[", after_new, re.MULTILINE)
        if next_section:
            section_body = after_new[: next_section.start()]
        else:
            section_body = after_new

        assert "New feature A that improves workflow." in section_body, (
            "Original [Unreleased] content must be preserved under the new version heading"
        )
        assert "Improvement B for better performance." in section_body, (
            "Original [Unreleased] content must be preserved under the new version heading"
        )

    def test_new_version_heading_uses_todays_date(self, tmp_path):
        """
        The date in the new heading must be today in ISO format (YYYY-MM-DD).
        Not hardcoded, not yesterday, not the date of the previous release.
        """
        repo, _ = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])
        assert rc == 0, f"exit {rc}\nstdout: {stdout}\nstderr: {stderr}"

        changelog = _read(os.path.join(repo, "CHANGELOG.md"))
        expected_heading = f"## [{new_ver}] - {TODAY}"
        assert expected_heading in changelog, (
            f"Expected heading '{expected_heading}' not found in CHANGELOG.\n{changelog}"
        )

    def test_new_unreleased_section_is_empty_after_promotion(self, tmp_path):
        """
        After promotion, ## [Unreleased] must have no content — the old content
        moved entirely to the new version heading.
        """
        repo, _ = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])
        assert rc == 0, f"exit {rc}\nstdout: {stdout}\nstderr: {stderr}"

        changelog = _read(os.path.join(repo, "CHANGELOG.md"))
        unreleased_idx = changelog.index("## [Unreleased]")
        new_ver_idx = changelog.index(f"## [{new_ver}]")
        between = changelog[unreleased_idx + len("## [Unreleased]"):new_ver_idx].strip()
        assert between == "", (
            f"[Unreleased] must be empty after promotion. Found: {between!r}"
        )

    def test_changelog_missing_aborts_cleanly(self, tmp_path):
        """
        If CHANGELOG.md is absent from the repo root, release.py must abort
        with exit != 0 and a clear error message — no traceback, no mutation.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Remove CHANGELOG.md and commit the deletion so the tree stays clean
        changelog_path = os.path.join(repo, "CHANGELOG.md")
        os.remove(changelog_path)
        _git(["add", "CHANGELOG.md"], repo)
        _git(["commit", "-m", "test: remove changelog"], repo)
        _git(["push", "origin", "main"], repo)

        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        combined = stdout + stderr
        assert rc != 0, f"Expected non-zero exit when CHANGELOG.md is absent. Got {rc}"
        # Error must mention the missing file — not dump a Python traceback
        assert "Traceback" not in combined, (
            f"Must not expose Python traceback. Output: {combined}"
        )
        assert _get_remote_head(bare) == initial_remote_head


# ── Hardening: malformed / missing input files ──────────────────────────────


class TestMalformedInputFiles:
    """
    Robustness when JSON files are corrupt or missing:
    - marketplace.json malformed → clear error, no traceback
    - plugin.json absent → clear error, no traceback
    """

    def test_marketplace_json_malformed_gives_clear_error(self, tmp_path):
        """
        If marketplace.json contains invalid JSON, release.py must exit != 0
        with a human-readable error message and NO Python traceback.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Corrupt marketplace.json and commit so tree is clean
        marketplace_path = os.path.join(repo, ".claude-plugin", "marketplace.json")
        _write(marketplace_path, "{ this is not valid json }")
        _git(["add", ".claude-plugin/marketplace.json"], repo)
        _git(["commit", "-m", "test: corrupt marketplace"], repo)
        _git(["push", "origin", "main"], repo)

        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        combined = stdout + stderr
        assert rc != 0, (
            f"Expected non-zero exit for malformed marketplace.json. Got {rc}"
        )
        assert "Traceback" not in combined, (
            f"Must not expose Python traceback on malformed JSON. Output: {combined}"
        )
        # Must produce a message (not silent failure)
        assert combined.strip() != "", "Error output must not be empty"
        assert _get_remote_head(bare) == initial_remote_head

    def test_plugin_json_absent_gives_clear_error(self, tmp_path):
        """
        If the plugin's plugin.json does not exist (plugin dir exists in marketplace
        but the file is missing), release.py must exit != 0 with a clear error,
        not a Python traceback. No files must be mutated.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Remove plugin.json and commit the deletion
        plugin_json_path = os.path.join(
            repo, PLUGIN_NAME, ".claude-plugin", "plugin.json"
        )
        os.remove(plugin_json_path)
        _git(["add", "-A"], repo)
        _git(["commit", "-m", "test: remove plugin.json"], repo)
        _git(["push", "origin", "main"], repo)

        initial_marketplace = _read(
            os.path.join(repo, ".claude-plugin", "marketplace.json")
        )
        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        combined = stdout + stderr
        assert rc != 0, (
            f"Expected non-zero exit when plugin.json is absent. Got {rc}"
        )
        assert "Traceback" not in combined, (
            f"Must not expose Python traceback. Output: {combined}"
        )
        assert combined.strip() != "", "Error output must not be empty"
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_remote_head(bare) == initial_remote_head


# ── Hardening: --dry-run zero-mutation guarantee ────────────────────────────


class TestDryRunZeroMutations:
    """
    --dry-run zero-mutation guarantee: even when all preconditions are correct,
    no file is modified and no commit is created. The existing TestDryRun covers
    the basic happy-path dry-run. This class covers cases where the dry-run
    encounters a pre-flight failure — ensuring it also exits != 0 cleanly there.
    """

    def test_dry_run_no_local_commit_created(self, tmp_path):
        """
        --dry-run must not create any git object (no new commit SHA on HEAD).
        Verifies local HEAD is identical before and after.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"
        initial_local_head = _get_local_head(repo)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--dry-run"])

        assert rc == 0, f"--dry-run must exit 0. Got {rc}\nstdout: {stdout}\nstderr: {stderr}"
        assert _get_local_head(repo) == initial_local_head, (
            "--dry-run must not create a local commit (HEAD changed)"
        )

    def test_dry_run_no_staged_changes(self, tmp_path):
        """
        --dry-run must leave the git index untouched — no files staged.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--dry-run"])

        assert rc == 0, f"--dry-run must exit 0. Got {rc}"

        # git diff --cached should show nothing staged
        staged_result = _git(["diff", "--cached", "--name-only"], repo)
        assert staged_result.stdout.strip() == "", (
            f"--dry-run must not stage any files. Staged: {staged_result.stdout.strip()}"
        )

    def test_dry_run_with_invalid_version_exits_nonzero(self, tmp_path):
        """
        --dry-run still runs pre-flight validation. Invalid semver must
        cause exit != 0 even with --dry-run.
        """
        repo, _ = _setup_release_repo(tmp_path)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "not-semver", "--dry-run"])

        assert rc != 0, (
            "--dry-run with invalid version must exit != 0 (pre-flight must still run)"
        )


# ── Hardening: bump-version.py retrocompatibility ──────────────────────────


class TestBumpVersionRetrocompat:
    """
    bump-version.py retrocompatibility: when UNMASSK_REPO_ROOT is NOT set,
    bump-version.py must behave exactly as before (uses __file__-relative root).
    The UNMASSK_REPO_ROOT override added for release.py must not break normal usage.
    """

    def test_bump_without_env_var_uses_file_relative_root(self, tmp_path, monkeypatch):
        """
        Invoke bump-version.py directly WITHOUT UNMASSK_REPO_ROOT in the environment.
        It must resolve REPO_ROOT from __file__ (the real repo), NOT from CWD.
        We verify this by:
          1. Running from a temp CWD that has no marketplace.json.
          2. Confirming the script finds the real marketplace.json (file-relative root).
          3. Using --list mode (read-only) so we don't mutate real files.
        """
        # Strip UNMASSK_REPO_ROOT from the environment for this subprocess call
        env_without_override = {
            k: v for k, v in os.environ.items() if k != "UNMASSK_REPO_ROOT"
        }

        result = subprocess.run(
            [sys.executable, BUMP_SCRIPT, "--list"],
            cwd=str(tmp_path),  # CWD has NO marketplace.json
            capture_output=True,
            text=True,
            env=env_without_override,
            timeout=30,
        )

        # Must succeed: the real marketplace.json is found via __file__, not CWD
        assert result.returncode == 0, (
            f"bump-version.py --list without UNMASSK_REPO_ROOT must succeed "
            f"(file-relative root). exit {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        # Output must contain the real plugin name (proves it read the real marketplace)
        assert PLUGIN_NAME in result.stdout, (
            f"Expected '{PLUGIN_NAME}' in --list output (real marketplace). "
            f"Got: {result.stdout}"
        )

    def test_bump_with_env_var_uses_override_root(self, tmp_path):
        """
        When UNMASSK_REPO_ROOT is set to a temp path, bump-version.py must use
        that root, not the __file__-relative one.
        We verify by pointing it at a temp repo that has its OWN marketplace.json
        with a DIFFERENT plugin name, then checking --list shows the temp plugin,
        not the real marketplace.
        """
        # Build a minimal marketplace in tmp_path
        fake_plugin = "fake-plugin-xyzzy"
        fake_marketplace = json.dumps(
            {"plugins": [{"name": fake_plugin, "version": "9.0.0"}]},
            indent=2,
        ) + "\n"
        marketplace_path = os.path.join(str(tmp_path), ".claude-plugin", "marketplace.json")
        _write(marketplace_path, fake_marketplace)

        env_with_override = {
            **os.environ,
            "UNMASSK_REPO_ROOT": str(tmp_path),
        }

        result = subprocess.run(
            [sys.executable, BUMP_SCRIPT, "--list"],
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
            env=env_with_override,
            timeout=30,
        )

        assert result.returncode == 0, (
            f"bump-version.py --list with UNMASSK_REPO_ROOT override must succeed. "
            f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert fake_plugin in result.stdout, (
            f"Expected override root's fake plugin '{fake_plugin}' in output. "
            f"Got: {result.stdout}"
        )
        # Must NOT show the real marketplace plugins (proving override took effect)
        assert PLUGIN_NAME not in result.stdout, (
            f"Real plugin '{PLUGIN_NAME}' must not appear when override root is active. "
            f"Output: {result.stdout}"
        )


# ── Regression tests (T1/T2 — added by Ultron fix pass) ───────────────────


class TestT11AllowDirtyNoStagedLeak:
    """
    T1.1 — --allow-dirty debe limpiar el índice antes de stagear los 3 ficheros.
    Un fichero ya staged ajeno al release NO debe entrar en el commit.
    """

    def test_pre_staged_untracked_file_not_in_commit(self, tmp_path):
        """
        Fichero ajeno añadido con 'git add' ANTES de llamar al script no debe
        aparecer en el commit de release (--allow-dirty + fichero staged no relacionado).
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Fichero ajeno: untracked -> staged
        foreign = os.path.join(repo, "foreign.py")
        _write(foreign, "# no debe entrar en el commit de release")
        _git(["add", "foreign.py"], repo)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--allow-dirty"])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        result = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [l.strip() for l in result.stdout.splitlines() if l.strip()]

        assert not any("foreign.py" in f for f in files_in_commit), (
            f"foreign.py (pre-staged) leaked into release commit! Files: {files_in_commit}"
        )
        # Los 3 ficheros del release sí deben estar
        assert any("marketplace.json" in f for f in files_in_commit)
        assert any("plugin.json" in f for f in files_in_commit)
        assert any("CHANGELOG.md" in f for f in files_in_commit)

    def test_pre_staged_modified_file_not_in_commit(self, tmp_path):
        """
        Fichero tracked ya modificado y staged antes de llamar no debe entrar en
        el commit de release con --allow-dirty.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Fichero tracked modificado -> staged
        extra = os.path.join(repo, "extra.txt")
        _write(extra, "version 1")
        _git(["add", "extra.txt"], repo)
        _git(["commit", "-m", "add extra"], repo)
        _git(["push", "origin", "main"], repo)

        # Ahora modificar y stagear
        _write(extra, "version 2 — no debe ir en el release")
        _git(["add", "extra.txt"], repo)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--allow-dirty"])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        result = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [l.strip() for l in result.stdout.splitlines() if l.strip()]

        assert not any("extra.txt" in f for f in files_in_commit), (
            f"extra.txt (pre-staged modified) leaked into release commit! Files: {files_in_commit}"
        )


class TestT12PreReleaseSemver:
    """
    T1.2 — Precedencia semver pre-release.
    1.4.0-rc1 < 1.4.0 según semver 2.0.0.
    """

    def _setup_with_version(self, tmp_path, current_ver):
        repo = str(tmp_path / "repo")
        bare = str(tmp_path / "bare.git")
        os.makedirs(repo)
        plugin_json = json.dumps({"name": PLUGIN_NAME, "version": current_ver}, indent=2) + "\n"
        marketplace = json.dumps({
            "plugins": [
                {"name": PLUGIN_NAME, "version": current_ver},
                {"name": OTHER_PLUGIN_NAME, "version": OTHER_PLUGIN_VER_INITIAL},
            ]
        }, indent=2) + "\n"
        _write(os.path.join(repo, ".claude-plugin", "marketplace.json"), marketplace)
        _write(os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json"), plugin_json)
        _write(os.path.join(repo, OTHER_PLUGIN_NAME, ".claude-plugin", "plugin.json"),
               _make_other_plugin_json(OTHER_PLUGIN_VER_INITIAL))
        _write(os.path.join(repo, "CHANGELOG.md"), INITIAL_CHANGELOG)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "test@example.com"], repo)
        _git(["config", "user.name", "Test User"], repo)
        _git(["add", "-A"], repo)
        _git(["commit", "-m", "chore: initial commit"], repo)
        subprocess.run(["git", "init", "--bare", "-b", "main", bare],
                       capture_output=True, check=True)
        _git(["remote", "add", "origin", bare], repo)
        _git(["push", "-u", "origin", "main"], repo)
        return repo, bare

    def test_final_accepted_over_rc(self, tmp_path):
        """1.4.0-rc1 (current) → 1.4.0 (new) debe ser ACEPTADO."""
        repo, bare = self._setup_with_version(tmp_path, "1.4.0-rc1")
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.0"])
        assert rc == 0, (
            f"1.4.0 > 1.4.0-rc1 debe aceptarse. exit {rc}\n{stdout}\n{stderr}"
        )

    def test_rc2_accepted_over_rc1(self, tmp_path):
        """1.4.0-rc1 (current) → 1.4.0-rc2 (new) debe ser ACEPTADO."""
        repo, bare = self._setup_with_version(tmp_path, "1.4.0-rc1")
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.0-rc2"])
        assert rc == 0, (
            f"1.4.0-rc2 > 1.4.0-rc1 debe aceptarse. exit {rc}\n{stdout}\n{stderr}"
        )

    def test_rc_rejected_as_lower_than_final(self, tmp_path):
        """1.4.0 (current) → 1.4.0-rc1 (new) debe ser RECHAZADO (rc < final)."""
        repo, bare = self._setup_with_version(tmp_path, "1.4.0")
        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.0-rc1"])
        assert rc != 0, (
            f"1.4.0-rc1 < 1.4.0 debe rechazarse. exit {rc}\n{stdout}\n{stderr}"
        )
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace

    def test_same_rc_rejected(self, tmp_path):
        """1.4.0-rc1 (current) → 1.4.0-rc1 (new) igual → RECHAZADO."""
        repo, bare = self._setup_with_version(tmp_path, "1.4.0-rc1")
        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.0-rc1"])
        assert rc != 0, (
            f"Misma versión rc debe rechazarse. exit {rc}\n{stdout}\n{stderr}"
        )
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace

    def test_patch_still_accepted(self, tmp_path):
        """1.4.0 (current) → 1.4.1 (new) sigue funcionando."""
        repo, bare = self._setup_with_version(tmp_path, "1.4.0")
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.1"])
        assert rc == 0, (
            f"1.4.1 > 1.4.0 debe aceptarse. exit {rc}\n{stdout}\n{stderr}"
        )


class TestT21FetchFailClosed:
    """
    T2.1 — git fetch que falla debe abortar el release (fail-closed).
    """

    def test_fetch_failure_aborts_release(self, tmp_path):
        """
        Si git fetch falla (remoto inaccesible), release.py debe abortar con
        exit != 0 y no mutar ningún fichero.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Romper el remoto apuntando a una ruta inexistente
        _git(["remote", "set-url", "origin", str(tmp_path / "gone.git")], repo)

        initial_marketplace = _read(os.path.join(repo, ".claude-plugin", "marketplace.json"))
        initial_local_head = _get_local_head(repo)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, (
            f"fetch fallido debe abortar (fail-closed). exit {rc}\n{stdout}\n{stderr}"
        )
        assert _read(os.path.join(repo, ".claude-plugin", "marketplace.json")) == initial_marketplace
        assert _get_local_head(repo) == initial_local_head, "No debe crearse ningún commit local"


class TestT22LeadingZerosSemver:
    """
    T2.2 — Semver estricto: ceros a la izquierda deben rechazarse.
    """

    def test_leading_zero_minor_rejected(self, tmp_path):
        """1.04.0 debe rechazarse por leading zero en minor."""
        repo, bare = _setup_release_repo(tmp_path)
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.04.0"])
        assert rc != 0, f"1.04.0 con leading zero debe rechazarse. exit {rc}"

    def test_leading_zero_patch_rejected(self, tmp_path):
        """1.4.00 debe rechazarse por leading zero en patch."""
        repo, bare = _setup_release_repo(tmp_path)
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.00"])
        assert rc != 0, f"1.4.00 con leading zero debe rechazarse. exit {rc}"

    def test_leading_zero_major_rejected(self, tmp_path):
        """01.4.0 debe rechazarse por leading zero en major."""
        repo, bare = _setup_release_repo(tmp_path)
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "01.4.0"])
        assert rc != 0, f"01.4.0 con leading zero debe rechazarse. exit {rc}"

    def test_valid_semver_still_accepted(self, tmp_path):
        """1.4.0 sin ceros a la izquierda sigue siendo aceptado."""
        repo, bare = _setup_release_repo(tmp_path)
        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, "1.4.0"])
        assert rc == 0, f"1.4.0 válido debe aceptarse. exit {rc}\n{stdout}\n{stderr}"


class TestT23UnreleasedOnlySubheaders:
    """
    T2.3 — [Unreleased] con solo cabeceras ### y whitespace cuenta como VACÍO.
    """

    def test_unreleased_with_only_subheaders_aborts(self, tmp_path):
        """
        ## [Unreleased] seguido solo de cabeceras ### sin entradas debe abortar.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        changelog_only_headers = """\
# Changelog

## [Unreleased]

### Added

### Changed

## [1.3.0] - 2026-06-08

### Added
- Previous release.
"""
        _write(os.path.join(repo, "CHANGELOG.md"), changelog_only_headers)
        _git(["add", "CHANGELOG.md"], repo)
        _git(["commit", "-m", "test: unreleased with only subheaders"], repo)
        _git(["push", "origin", "main"], repo)

        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, (
            f"[Unreleased] con solo cabeceras ### debe abortar. exit {rc}\n{stdout}\n{stderr}"
        )
        assert _read(os.path.join(repo, "CHANGELOG.md")) == changelog_only_headers
        assert _get_remote_head(bare) == initial_remote_head


class TestT24ChangelogMalformed:
    """
    T2.4 — CHANGELOG malformado: múltiples [Unreleased] o [Unreleased] no primero.
    """

    def test_multiple_unreleased_aborts(self, tmp_path):
        """
        Dos ## [Unreleased] en el CHANGELOG debe abortar con mensaje claro.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        bad_changelog = """\
# Changelog

## [Unreleased]

### Added
- Entry A.

## [Unreleased]

### Added
- Entry B.

## [1.3.0] - 2026-06-08
- Old entry.
"""
        _write(os.path.join(repo, "CHANGELOG.md"), bad_changelog)
        _git(["add", "CHANGELOG.md"], repo)
        _git(["commit", "-m", "test: multiple unreleased"], repo)
        _git(["push", "origin", "main"], repo)

        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, (
            f"Múltiples [Unreleased] debe abortar. exit {rc}\n{stdout}\n{stderr}"
        )
        combined = stdout + stderr
        assert "Unreleased" in combined, (
            f"Mensaje de error debe mencionar 'Unreleased'. Output: {combined}"
        )
        assert _get_remote_head(bare) == initial_remote_head

    def test_unreleased_not_first_version_aborts(self, tmp_path):
        """
        Si hay un ## [x.y.z] antes de ## [Unreleased], debe abortar.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        bad_changelog = """\
# Changelog

## [1.3.0] - 2026-06-08

### Added
- Released entry.

## [Unreleased]

### Added
- Unreleased entry.
"""
        _write(os.path.join(repo, "CHANGELOG.md"), bad_changelog)
        _git(["add", "CHANGELOG.md"], repo)
        _git(["commit", "-m", "test: unreleased not first"], repo)
        _git(["push", "origin", "main"], repo)

        initial_remote_head = _get_remote_head(bare)

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver])

        assert rc != 0, (
            f"[Unreleased] no-primero debe abortar. exit {rc}\n{stdout}\n{stderr}"
        )
        combined = stdout + stderr
        assert "Unreleased" in combined, (
            f"Mensaje de error debe mencionar 'Unreleased'. Output: {combined}"
        )
        assert _get_remote_head(bare) == initial_remote_head


class TestT25TimeoutExpired:
    """
    T2.5 — subprocess.TimeoutExpired debe capturarse con mensaje limpio, sin traceback.
    Probamos directamente sobre _run() en release_helpers (donde vive tras el refactor T2.8).
    """

    def test_timeout_in_run_gives_clean_error(self, tmp_path, monkeypatch):
        """
        Si _run() recibe un TimeoutExpired de subprocess.run, debe llamar a _die
        con mensaje legible — sin propagar el TimeoutExpired ni dejar traceback.

        Tras el refactor T2.8, _run vive en release_helpers.py; el monkeypatch
        apunta a release_helpers.subprocess para no interferir con subprocess global.
        """
        import bin.release_helpers as helpers
        import subprocess as sp

        def always_timeout(args, **kwargs):
            raise sp.TimeoutExpired(args, kwargs.get("timeout", 60))

        monkeypatch.setattr(helpers.subprocess, "run", always_timeout)

        with pytest.raises(SystemExit) as exc_info:
            helpers._run(["git", "status"], cwd=str(tmp_path))

        assert exc_info.value.code != 0, "TimeoutExpired en _run debe causar exit != 0"


class TestT26NoDuplicateStderr:
    """
    T2.6 — El stderr del fallo de commit no debe imprimirse dos veces.
    """

    def test_commit_failure_no_duplicate_stderr(self, tmp_path, monkeypatch, capsys):
        """
        Cuando git-memory-commit.py falla, el mensaje de error NO debe aparecer
        duplicado en stderr.
        """
        import bin.release as rel

        repo, bare = _setup_release_repo(tmp_path)
        monkeypatch.chdir(repo)

        # Hacer que _execute_commit_push llame a _run pero forzar fallo del commit
        original_run = rel._run

        def patched_run(args, **kwargs):
            if "git-memory-commit" in str(args):
                result = type("R", (), {
                    "returncode": 1,
                    "stdout": "commit stdout msg\n",
                    "stderr": "commit stderr msg\n",
                })()
                return result
            return original_run(args, **kwargs)

        monkeypatch.setattr(rel, "_run", patched_run)

        # Ejecutar hasta la fase de commit
        plugin_json_path = os.path.join(repo, PLUGIN_NAME, ".claude-plugin", "plugin.json")
        marketplace_path = os.path.join(repo, ".claude-plugin", "marketplace.json")
        changelog_path = os.path.join(repo, "CHANGELOG.md")

        with pytest.raises(SystemExit):
            rel._execute_commit_push(
                PLUGIN_NAME, "1.4.0", repo,
                plugin_json_path, marketplace_path, changelog_path,
            )

        captured = capsys.readouterr()
        # El mensaje de stderr del commit NO debe aparecer dos veces
        stderr_output = captured.err
        count = stderr_output.count("commit stderr msg")
        assert count <= 1, (
            f"stderr del commit aparece {count} veces (duplicado). Output:\n{stderr_output}"
        )


class TestT27DieNoReturn:
    """
    T2.7 — _die debe estar anotada como -> NoReturn.
    """

    def test_die_annotated_as_no_return(self):
        """_die debe tener anotación de retorno NoReturn."""
        import bin.release as rel
        import typing
        hints = typing.get_type_hints(rel._die)
        assert hints.get("return") is typing.NoReturn, (
            f"_die debe tener -> NoReturn. Hints actuales: {hints}"
        )


# ── Contrato nuevo (decisión c28753a): pathspec explícito, sin git reset ──────
#
# Los tests de este bloque validan el nuevo contrato de seguridad:
#   - El commit usa `git commit -- <3 ficheros>` (pathspec explícito).
#   - Se elimina el `git reset` que había en `_execute_stage`.
#   - Lo que el usuario tuviera staged ANTES sigue staged DESPUÉS.
#
# Tests RED: TestBystanderRemainsStaged y TestGitMemoryCommitPathFlag
#   (el código actual hace git reset -q, lo que des-stagea el bystander).
# Tests GREEN: TestPromoteChangelogUnit (función pura, no afectada por el cambio).


class TestBystanderRemainsStaged:
    """
    Contrato de no-reset: un fichero ajeno staged ANTES del release debe
    seguir staged DESPUÉS. Con el código actual (git reset -q en _execute_stage)
    estos tests van en ROJO — ese es el estado correcto hasta que Ultron
    elimine el git reset y use pathspec explícito en el commit.
    """

    def test_staged_untracked_bystander_remains_staged_after_release(self, tmp_path):
        """
        Setup: bystander.py (fichero nuevo, nunca commitado) se añade con
        'git add bystander.py' ANTES del release.

        Asserts:
          (a) bystander.py NO está en el commit del release.   [ya pasaba antes]
          (b) bystander.py SÍ aparece en 'git diff --cached'  [NUEVO — RED con reset]
              después del release.

        RED hasta que _execute_stage deje de hacer git reset.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Crear y stagear el bystander (untracked → staged)
        bystander = os.path.join(repo, "bystander.py")
        _write(bystander, "# bystander — debe quedar staged tras el release\n")
        _git(["add", "bystander.py"], repo)

        # Verificar que está staged antes de llamar al release
        pre_staged = _git(["diff", "--cached", "--name-only"], repo)
        assert "bystander.py" in pre_staged.stdout, (
            "Precondición fallida: bystander.py debería estar staged antes del release"
        )

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--allow-dirty"])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        # (a) bystander NO en el commit
        result = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        assert not any("bystander.py" in f for f in files_in_commit), (
            f"bystander.py leaked into release commit! Files: {files_in_commit}"
        )

        # (b) bystander SIGUE staged — NUEVO CONTRATO (RED con git reset)
        post_staged = _git(["diff", "--cached", "--name-only"], repo)
        staged_files = [line.strip() for line in post_staged.stdout.splitlines() if line.strip()]
        assert any("bystander.py" in f for f in staged_files), (
            f"CONTRATO NUEVO: bystander.py debe seguir staged después del release. "
            f"Staged tras el release: {staged_files!r}. "
            "El código actual hace 'git reset -q' que lo des-stagea. "
            "Ultron debe eliminar el reset y usar pathspec explícito en el commit."
        )

    def test_staged_modified_tracked_bystander_remains_staged_after_release(self, tmp_path):
        """
        Setup: extra.txt (fichero tracked) modificado y staged ANTES del release.

        Asserts:
          (a) extra.txt NO en el commit del release.
          (b) extra.txt SÍ sigue staged después.

        RED hasta que _execute_stage deje de hacer git reset.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        # Crear, commitear y pushear extra.txt para que sea tracked
        extra = os.path.join(repo, "extra.txt")
        _write(extra, "version 1\n")
        _git(["add", "extra.txt"], repo)
        _git(["commit", "-m", "add extra.txt"], repo)
        _git(["push", "origin", "main"], repo)

        # Modificar y stagear (tracked → modified + staged)
        _write(extra, "version 2 — debe quedar staged tras el release\n")
        _git(["add", "extra.txt"], repo)

        pre_staged = _git(["diff", "--cached", "--name-only"], repo)
        assert "extra.txt" in pre_staged.stdout, (
            "Precondición: extra.txt debería estar staged antes del release"
        )

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--allow-dirty"])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        # (a) extra.txt NO en el commit
        result = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        assert not any("extra.txt" in f for f in files_in_commit), (
            f"extra.txt leaked into release commit! Files: {files_in_commit}"
        )

        # (b) extra.txt SIGUE staged — NUEVO CONTRATO (RED con git reset)
        post_staged = _git(["diff", "--cached", "--name-only"], repo)
        staged_files = [line.strip() for line in post_staged.stdout.splitlines() if line.strip()]
        assert any("extra.txt" in f for f in staged_files), (
            f"CONTRATO NUEVO: extra.txt debe seguir staged después del release. "
            f"Staged tras el release: {staged_files!r}. "
            "El código actual hace 'git reset -q' que lo des-stagea."
        )

    def test_staged_untracked_newly_added_file_remains_staged_after_release(self, tmp_path):
        """
        Variante explícita: fichero nuevo (nunca en el repo) añadido con
        'git add nuevo.txt' antes del release. Tras el release sigue staged
        como fichero nuevo (aparece en diff --cached como "new file").

        RED hasta que se elimine el git reset.
        """
        repo, bare = _setup_release_repo(tmp_path)
        new_ver = "1.4.0"

        nuevo = os.path.join(repo, "nuevo.txt")
        _write(nuevo, "fichero nuevo que debe permanecer staged\n")
        _git(["add", "nuevo.txt"], repo)

        pre_staged = _git(["diff", "--cached", "--name-only"], repo)
        assert "nuevo.txt" in pre_staged.stdout, (
            "Precondición: nuevo.txt debería estar staged antes del release"
        )

        rc, stdout, stderr = _run_release(repo, [PLUGIN_NAME, new_ver, "--allow-dirty"])

        assert rc == 0, f"Expected exit 0, got {rc}.\nstdout: {stdout}\nstderr: {stderr}"

        # nuevo.txt NO en el commit del release
        result = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        assert not any("nuevo.txt" in f for f in files_in_commit), (
            f"nuevo.txt leaked into release commit! Files: {files_in_commit}"
        )

        # nuevo.txt SIGUE staged — NUEVO CONTRATO (RED con git reset)
        post_staged = _git(["diff", "--cached", "--name-only"], repo)
        staged_files = [line.strip() for line in post_staged.stdout.splitlines() if line.strip()]
        assert any("nuevo.txt" in f for f in staged_files), (
            f"CONTRATO NUEVO: nuevo.txt debe seguir staged después del release. "
            f"Staged tras el release: {staged_files!r}. "
            "Ultron debe eliminar el git reset de _execute_stage."
        )


class TestGitMemoryCommitPathFlag:
    """
    Contrato del flag --path en git-memory-commit.py.

    El wrapper debe aceptar uno o más --path <fichero> y, cuando se pasan,
    hacer `git commit -- <paths>` en lugar de `git commit` a secas
    (que commitea el índice completo).

    Esto permite que release.py elimine el `git reset` y en su lugar
    pase los 3 ficheros explícitamente al wrapper.

    Tests RED: el wrapper actual no tiene --path; git commit usa el índice
    completo sin pathspec → los ficheros extra entran en el commit.
    """

    GIT_MEMORY_COMMIT = os.path.join(_REPO_ROOT, "unmassk-toolkit", "bin", "git-memory-commit.py")

    def _setup_bare_repo(self, tmp_path):
        """
        Repo git mínimo con upstream bare. Devuelve (repo_path, bare_path).
        Configura user.email y user.name para que git commit funcione.
        """
        repo = str(tmp_path / "repo")
        bare = str(tmp_path / "bare.git")
        os.makedirs(repo)

        subprocess.run(["git", "init", "-b", "main", repo], capture_output=True, check=True)
        _git(["config", "user.email", "test@example.com"], repo)
        _git(["config", "user.name", "Test User"], repo)

        # Commit inicial
        _write(os.path.join(repo, "README.md"), "# test\n")
        _git(["add", "README.md"], repo)
        _git(["commit", "-m", "initial"], repo)

        subprocess.run(["git", "init", "--bare", "-b", "main", bare],
                       capture_output=True, check=True)
        _git(["remote", "add", "origin", bare], repo)
        _git(["push", "-u", "origin", "main"], repo)

        return repo, bare

    def _run_wrapper(self, repo, extra_args, env=None):
        """Invoca git-memory-commit.py con args base + extra_args desde repo."""
        merged_env = {**os.environ, **(env or {})}
        result = subprocess.run(
            [sys.executable, self.GIT_MEMORY_COMMIT,
             "chore", "test-scope", "test commit message"] + extra_args,
            cwd=repo,
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=30,
        )
        return result

    def test_path_flag_commits_only_specified_files(self, tmp_path):
        """
        Con --path A --path B staged: A y B en el commit, C staged pero
        NO en el commit (C sigue staged después).

        RED: el wrapper actual no tiene --path; commitea el índice completo,
        incluyendo C.
        """
        repo, bare = self._setup_bare_repo(tmp_path)

        # Crear y stagear A, B, C
        file_a = os.path.join(repo, "a.txt")
        file_b = os.path.join(repo, "b.txt")
        file_c = os.path.join(repo, "c.txt")
        _write(file_a, "content A\n")
        _write(file_b, "content B\n")
        _write(file_c, "content C — must stay staged, not go into the commit\n")

        _git(["add", "a.txt", "b.txt", "c.txt"], repo)

        result = self._run_wrapper(repo, ["--path", "a.txt", "--path", "b.txt"])

        assert result.returncode == 0, (
            f"git-memory-commit.py con --path debe tener exit 0. "
            f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # A y B en el commit
        show = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in show.stdout.splitlines() if line.strip()]
        assert "a.txt" in files_in_commit, (
            f"a.txt debe estar en el commit. Files: {files_in_commit}"
        )
        assert "b.txt" in files_in_commit, (
            f"b.txt debe estar en el commit. Files: {files_in_commit}"
        )

        # C NO en el commit — NUEVO CONTRATO (RED: sin --path, C entraría)
        assert "c.txt" not in files_in_commit, (
            f"CONTRATO NUEVO: c.txt NO debe estar en el commit cuando se usa --path. "
            f"Files en commit: {files_in_commit!r}. "
            "El wrapper actual no tiene --path y commitea el índice completo."
        )

        # C sigue staged después del commit — NUEVO CONTRATO
        post_staged = _git(["diff", "--cached", "--name-only"], repo)
        staged_after = [line.strip() for line in post_staged.stdout.splitlines() if line.strip()]
        assert "c.txt" in staged_after, (
            f"CONTRATO NUEVO: c.txt debe seguir staged tras el commit con pathspec. "
            f"Staged después: {staged_after!r}"
        )

    def test_path_flag_multiple_accumulates(self, tmp_path):
        """
        Múltiples --path son acumulables (no se descarta el anterior).
        Tres ficheros A, B, C staged; --path A --path B --path C → los tres
        en el commit.

        Esto valida que el wrapper parsea action="append" correctamente.
        RED si el wrapper no tiene --path.
        """
        repo, bare = self._setup_bare_repo(tmp_path)

        for name in ["x.txt", "y.txt", "z.txt"]:
            _write(os.path.join(repo, name), f"content {name}\n")
        _git(["add", "x.txt", "y.txt", "z.txt"], repo)

        result = self._run_wrapper(
            repo, ["--path", "x.txt", "--path", "y.txt", "--path", "z.txt"]
        )

        assert result.returncode == 0, (
            f"Múltiples --path deben funcionar. "
            f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        show = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in show.stdout.splitlines() if line.strip()]
        for name in ["x.txt", "y.txt", "z.txt"]:
            assert name in files_in_commit, (
                f"{name} debe estar en el commit con --path acumulado. Files: {files_in_commit}"
            )

    def test_without_path_flag_commits_full_index(self, tmp_path):
        """
        Sin --path el wrapper hace commit del índice completo (retrocompat).
        Dos ficheros A y B staged → ambos en el commit.

        Este test debe quedar VERDE (comportamiento actual ya correcto).
        """
        repo, bare = self._setup_bare_repo(tmp_path)

        _write(os.path.join(repo, "p.txt"), "content P\n")
        _write(os.path.join(repo, "q.txt"), "content Q\n")
        _git(["add", "p.txt", "q.txt"], repo)

        result = self._run_wrapper(repo, [])  # sin --path

        assert result.returncode == 0, (
            f"Sin --path debe commitear el índice y tener exit 0. "
            f"exit {result.returncode}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        show = _git(["show", "--name-only", "--format=", "HEAD"], repo)
        files_in_commit = [line.strip() for line in show.stdout.splitlines() if line.strip()]
        assert "p.txt" in files_in_commit, f"p.txt debe estar en el commit. Files: {files_in_commit}"
        assert "q.txt" in files_in_commit, f"q.txt debe estar en el commit. Files: {files_in_commit}"


# ── Unit tests de _promote_changelog (función pura, sin subprocess) ──────────


class TestPromoteChangelogUnit:
    """
    Tests unitarios directos de release_helpers._promote_changelog.

    Se importa la función y se le pasan strings — sin subprocesos, sin
    repos temporales. Cobertura unitaria marcada ausente por Yoda.
    """

    def _promote(self, text, ver="2.0.0", today="2026-06-09"):
        import bin.release_helpers as helpers
        return helpers._promote_changelog(text, ver, today)

    def test_basic_promotion_inserts_version_header(self):
        """
        [Unreleased] con contenido → aparece ## [2.0.0] - 2026-06-09 en el resultado.
        """
        text = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- Feature X.\n\n"
            "## [1.0.0] - 2026-01-01\n\n"
            "- Old.\n"
        )
        result = self._promote(text)

        assert "## [2.0.0] - 2026-06-09" in result, (
            f"Encabezado de nueva versión no encontrado en:\n{result}"
        )

    def test_unreleased_section_empty_after_promotion(self):
        """
        Tras la promoción, ## [Unreleased] tiene cero contenido entre él
        y ## [2.0.0].
        """
        text = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- Feature X.\n\n"
            "## [1.0.0] - 2026-01-01\n\n"
            "- Old.\n"
        )
        result = self._promote(text)

        idx_unreleased = result.index("## [Unreleased]")
        idx_new_ver = result.index("## [2.0.0]")
        between = result[idx_unreleased + len("## [Unreleased]"):idx_new_ver]

        assert between == "\n\n", (
            f"Debe haber exactamente una línea en blanco entre [Unreleased] y la nueva versión. "
            f"Got {between!r}"
        )

    def test_exactly_one_blank_line_between_headers(self):
        """
        El gap entre ## [Unreleased] y ## [ver] - fecha es exactamente '\\n\\n'.
        Keep a Changelog canónico: ni más líneas en blanco ni menos.
        """
        text = (
            "## [Unreleased]\n\n"
            "- Entry.\n\n"
            "## [1.5.0] - 2025-01-01\n"
            "- Past.\n"
        )
        result = self._promote(text, ver="1.6.0", today="2026-06-09")

        idx_u = result.index("## [Unreleased]")
        idx_v = result.index("## [1.6.0]")
        between = result[idx_u + len("## [Unreleased]"):idx_v]
        assert between == "\n\n", (
            f"Gap esperado '\\n\\n', encontrado: {between!r}"
        )

    def test_content_preserved_verbatim_under_new_version(self):
        """
        El contenido que estaba bajo [Unreleased] aparece bajo el nuevo heading
        sin modificaciones (sin truncar, reordenar, ni escapar HTML).
        """
        text = (
            "## [Unreleased]\n\n"
            "### Added\n"
            "- Feature Alpha: soporte para <angle brackets> & ampersands.\n"
            "- Feature Beta: múltiples líneas\n"
            "  con indentación.\n\n"
            "## [1.0.0] - 2025-01-01\n"
            "- Past.\n"
        )
        result = self._promote(text, ver="1.1.0", today="2026-06-09")

        new_header = "## [1.1.0] - 2026-06-09"
        assert new_header in result

        idx_new = result.index(new_header)
        after_new = result[idx_new + len(new_header):]
        # Buscar el siguiente ## o fin de string
        import re as _re
        next_section = _re.search(r"^## \[", after_new, _re.MULTILINE)
        body = after_new[:next_section.start()] if next_section else after_new

        assert "Feature Alpha: soporte para <angle brackets> & ampersands." in body, (
            f"Contenido con caracteres especiales no preservado. Cuerpo:\n{body}"
        )
        assert "Feature Beta: múltiples líneas" in body, (
            f"Contenido con múltiples líneas no preservado. Cuerpo:\n{body}"
        )

    def test_no_existing_versions_below_unreleased(self):
        """
        [Unreleased] con contenido y SIN ninguna ## [x.y.z] debajo.
        Debe promocionar correctamente dejando [Unreleased] vacío
        y la nueva versión con el contenido. Sin corrupción.
        """
        text = (
            "# Changelog\n\n"
            "## [Unreleased]\n\n"
            "### Added\n"
            "- First ever release content.\n"
        )
        result = self._promote(text, ver="1.0.0", today="2026-06-09")

        assert "## [1.0.0] - 2026-06-09" in result, (
            f"Encabezado de versión no encontrado. Resultado:\n{result}"
        )
        assert "First ever release content." in result, (
            "El contenido de [Unreleased] debe aparecer bajo la nueva versión."
        )

        # [Unreleased] debe quedar vacío (exactamente \n\n antes del nuevo header)
        idx_u = result.index("## [Unreleased]")
        idx_v = result.index("## [1.0.0]")
        between = result[idx_u + len("## [Unreleased]"):idx_v]
        assert between == "\n\n", (
            f"[Unreleased] debe quedar vacío (gap '\\n\\n'). Got: {between!r}"
        )

    def test_crlf_line_endings_preserved(self):
        """
        Si el fichero CHANGELOG tiene CRLF, el resultado debe conservar CRLF.
        No se puede normalizar silenciosamente a LF porque rompería el fichero
        en editores Windows y produciría un diff en git.
        """
        # Construir el texto con CRLF explícito
        text = (
            "# Changelog\r\n"
            "\r\n"
            "## [Unreleased]\r\n"
            "\r\n"
            "### Added\r\n"
            "- CRLF feature.\r\n"
            "\r\n"
            "## [1.0.0] - 2025-01-01\r\n"
            "- Past.\r\n"
        )
        result = self._promote(text, ver="1.1.0", today="2026-06-09")

        # El CRLF del contenido original debe mantenerse en el resultado
        assert "\r\n" in result, (
            "CRLF debe preservarse en el resultado de _promote_changelog. "
            f"El resultado contiene solo LF o no tiene saltos de línea CRLF."
        )
        # La entrada que estaba en [Unreleased] con CRLF debe aparecer bajo la nueva versión
        assert "CRLF feature.\r\n" in result, (
            "El contenido con CRLF no fue preservado verbatim bajo la nueva versión."
        )
