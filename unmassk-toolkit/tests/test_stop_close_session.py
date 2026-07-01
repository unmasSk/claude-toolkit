"""
Tests for stop-close-session.py — the close-session reminder hook.

Covers:
- Substantive commits since last context() → reminder injected to stderr.
- No commits since last context() → silent (no output).
- Only non-substantive commits (init only) → silent.
- Empty / non-git repo → silent, exit 0.
- Hook never blocks (always exit 0).
- PreCompact path: hook is NOT registered on PreCompact (precompact-snapshot handles it).
- Script imports without error (syntax/import check).
"""

import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd, run_script

HOOK_PATH = os.path.join(HOOKS_DIR, "stop-close-session.py")


# ── Repo helpers ─────────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Create a minimal git repo with identity configured."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit(repo, subject, body=""):
    """Add an empty commit with the given subject and optional body."""
    msg = subject if not body else f"{subject}\n\n{body}"
    git_cmd(["commit", "--allow-empty", "-m", msg], repo)


def _run_hook(repo):
    """Invoke stop-close-session.py in `repo`. Returns (rc, stdout, stderr)."""
    return run_script(HOOK_PATH, repo)


# ── Tests: suppression (no output) ───────────────────────────────────────────

class TestSuppressed:
    def test_no_commits_after_context_is_silent(self, tmp_path):
        """A context() commit with nothing after it → no reminder output."""
        repo = _make_repo(tmp_path)
        _commit(repo, "feat(auth): add login endpoint", "Why: new feature")
        _commit(repo, "context(auth): checkpoint", "Why: pause\nNext: add refresh token")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" not in stderr, (
            "No reminder expected when nothing followed the context() commit"
        )

    def test_empty_repo_init_only_is_silent(self, tmp_path):
        """Repo with only the init commit has no substantive work → silent."""
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" not in stderr

    def test_non_substantive_commit_only_is_silent(self, tmp_path):
        """A docs: commit after context() does not trigger the reminder.

        'docs' is not in _SUBSTANTIVE_TYPES — the session has no code/decision
        work that needs a close-session checklist.
        """
        repo = _make_repo(tmp_path)
        _commit(repo, "context(docs): checkpoint", "Next: write README")
        _commit(repo, "docs(readme): fix typo")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" not in stderr


# ── Tests: reminder fires ─────────────────────────────────────────────────────

class TestReminderFires:
    def test_feat_commit_after_context_triggers_reminder(self, tmp_path):
        """feat() commit since last context() → reminder to stderr."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(auth): prior checkpoint", "Next: add refresh token")
        _commit(repo, "feat(auth): implement refresh token endpoint")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr

    def test_fix_commit_triggers_reminder(self, tmp_path):
        """fix() commit since last context() → reminder fires."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(api): checkpoint", "Next: fix rate limit bug")
        _commit(repo, "fix(api): correct rate limit header handling")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr

    def test_decision_commit_triggers_reminder(self, tmp_path):
        """decision() commit since last context() → reminder fires."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(plugin): checkpoint", "Next: decide on recall strategy")
        _commit(repo, "decision(plugin): use BM25 for recall", "Decision: BM25 chosen")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr

    def test_wip_commit_triggers_reminder(self, tmp_path):
        """wip: commit since last context() → reminder fires."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(hooks): checkpoint", "Next: finish close-session hook")
        _commit(repo, "wip: partial close-session hook")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr

    def test_no_context_commit_ever_and_substantive_work_triggers(self, tmp_path):
        """Repo never had a context() commit but has feat() work → reminder fires."""
        repo = _make_repo(tmp_path)
        _commit(repo, "feat(api): add user endpoint")
        _commit(repo, "fix(api): handle null user")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr

    def test_reminder_contains_three_step_checklist(self, tmp_path):
        """Reminder output contains all three close-session steps."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(auth): checkpoint", "Next: implement logout")
        _commit(repo, "feat(auth): implement logout")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        # Step 1: flush decisions
        assert "decision" in stderr.lower() or "memo" in stderr.lower(), (
            "Step 1 (flush decisions) must be mentioned"
        )
        # Step 2: housekeeping
        assert "housekeeping" in stderr.lower() or "version" in stderr.lower(), (
            "Step 2 (housekeeping) must be mentioned"
        )
        # Step 3: resume point / context commit
        assert "resume" in stderr.lower() or "context()" in stderr.lower(), (
            "Step 3 (resume point) must be mentioned"
        )


# ── Tests: hook never blocks ──────────────────────────────────────────────────

class TestNeverBlocks:
    def test_always_exits_zero_with_commits(self, tmp_path):
        """Hook exits 0 even when reminder fires."""
        repo = _make_repo(tmp_path)
        _commit(repo, "feat(x): some work")

        rc, _, _ = _run_hook(repo)

        assert rc == 0

    def test_always_exits_zero_empty_repo(self, tmp_path):
        """Hook exits 0 on repo with only init commit."""
        repo = _make_repo(tmp_path)

        rc, _, _ = _run_hook(repo)

        assert rc == 0

    def test_always_exits_zero_after_context(self, tmp_path):
        """Hook exits 0 when suppressed (nothing after context())."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(x): checkpoint", "Next: nothing")

        rc, _, _ = _run_hook(repo)

        assert rc == 0

    def test_stdout_is_always_empty(self, tmp_path):
        """Hook never writes to stdout — all output is stderr."""
        repo = _make_repo(tmp_path)
        _commit(repo, "feat(x): work done")

        rc, stdout, _ = _run_hook(repo)

        assert rc == 0
        assert stdout == "", f"Hook must not write to stdout; got: {stdout!r}"


# ── Tests: import sanity ──────────────────────────────────────────────────────

class TestImportSanity:
    def test_hook_imports_without_error(self, tmp_path):
        """The hook module compiles without syntax or import errors.

        Uses py_compile instead of -c exec to avoid Windows path escaping.
        """
        rc, stdout, stderr = run_cmd(
            [sys.executable, "-m", "py_compile", HOOK_PATH],
            cwd=str(tmp_path),
        )
        assert rc == 0, f"Syntax/compile error in hook: stderr={stderr!r}"

    def test_hook_runs_in_non_git_dir(self, tmp_path):
        """Hook exits 0 silently when cwd is not a git repo."""
        non_git = str(tmp_path / "not-a-repo")
        os.makedirs(non_git)

        rc, stdout, stderr = run_cmd([sys.executable, HOOK_PATH], cwd=non_git)

        assert rc == 0
        assert "close-session" not in stderr
        assert stdout == ""


# ── Tests: emoji-prefixed conventional commits ───────────────────────────────

class TestEmojiPrefixedCommits:
    def test_emoji_prefixed_feat_triggers_reminder(self, tmp_path):
        """'feat()' with an emoji prefix is detected as substantive work."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(auth): checkpoint", "Next: add OAuth")
        # Emoji prefix mirrors toolkit commit style (e.g. "✨ feat(auth): ...")
        _commit(repo, "✨ feat(auth): add OAuth provider")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr, (
            "Emoji-prefixed feat() must be detected as substantive"
        )

    def test_emoji_prefixed_decision_triggers_reminder(self, tmp_path):
        """'\U0001f9ed decision()' commit is detected as substantive."""
        repo = _make_repo(tmp_path)
        _commit(repo, "context(plugin): checkpoint", "Next: decide algo")
        _commit(repo, "\U0001f9ed decision(plugin): chose BM25", "Decision: BM25")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0
        assert "close-session" in stderr
