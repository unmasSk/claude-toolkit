"""
Subject-length guard for git-memory-commit.py's context() commits.

History: this file originally pinned a fail-closed contract for oversized
context() subjects (SUBJECT_MAX_LEN = 100 chars, reject + exit non-zero,
tell the caller to use --body). That gate was retired on purpose (Bex's
call, not an accident) -- an oversized subject now commits successfully
instead of being rejected. TestSubjectLengthFailClosed exercised exactly
that removed gate (asserted rc != 0 for an oversized subject, which is no
longer true) and has been removed along with it.

What survives is the half of the contract that never depended on the
gate's existence and is still true today: a subject built right at the
100-char boundary is accepted, and a short subject with an arbitrarily
long --body still succeeds. SUBJECT_MAX_LEN is kept as the boundary this
file measures against, not as a claim that a gate enforces it.

[GUARDA] (passes today, independent of whether a length gate exists):
    - test_subject_exactly_at_limit_is_accepted
    - test_short_message_with_long_body_still_succeeds
"""

import importlib.util
import os

from conftest import BIN_DIR, git_cmd, run_cmd, run_script

COMMIT_SCRIPT = os.path.join(BIN_DIR, "git-memory-commit.py")
SUBJECT_MAX_LEN = 100  # the contract this test file establishes

# Import the script directly (hyphenated filename — not importable via
# normal `import`) to read its real EMOJIS dict, so the boundary-case
# subject we construct here matches build_commit_message()'s own format
# string exactly, instead of duplicating "💾" as a string literal.
_spec = importlib.util.spec_from_file_location("git_memory_commit_under_test", COMMIT_SCRIPT)
_commit_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_commit_mod)
EMOJIS = _commit_mod.EMOJIS


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _commit_count(repo):
    rc, out, _ = run_cmd(["git", "rev-list", "--count", "HEAD"], repo)
    return int(out.strip())


def _subject_prefix_len(type_, scope):
    """Length of everything in the subject before the free-form message,
    exactly matching build_commit_message()'s f"{emoji} {type_}({scope}): "."""
    return len(f"{EMOJIS[type_]} {type_}({scope}): ")


class TestSubjectLengthBoundaryAndBodyPathUnaffected:
    """[GUARDA] Boundary acceptance and the --body path must keep working."""

    def test_subject_exactly_at_limit_is_accepted(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        prefix_len = _subject_prefix_len("context", "auth")
        message = "x" * (SUBJECT_MAX_LEN - prefix_len)
        rc, out, err = run_script(COMMIT_SCRIPT, repo, ["context", "auth", message])
        assert rc == 0, f"subject at exactly {SUBJECT_MAX_LEN} chars should be accepted: {err!r}"
        assert _commit_count(repo) == before + 1

    def test_short_message_with_long_body_still_succeeds(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        long_body = "y" * 2000
        rc, out, err = run_script(
            COMMIT_SCRIPT, repo,
            ["context", "auth", "short message", "--body", long_body],
        )
        assert rc == 0, f"short subject + long --body must still succeed: {err!r}"
        assert _commit_count(repo) == before + 1
