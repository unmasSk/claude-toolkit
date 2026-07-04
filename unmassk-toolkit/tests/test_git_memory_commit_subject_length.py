"""
Acceptance contract (test-first, RED pass): git-memory-commit.py must fail
closed on an oversized context() subject.

Root cause (House diagnosis, see test_boot_output.py's
TestBootStdoutMinimalWithHeavyContent / TestBootLogFileFullContent for the
other half of the fix): a real context() commit had a 1297-byte subject.
Combined with the SCOPES section, that alone blew the harness's ~2KB stdout
preview window and dropped the Next: instruction. The boot-hook fix (moving
full content to a file) treats the symptom; this is the root-cause fix at
the source — a commit should never be allowed to create a subject that
large in the first place.

Design decision taken here (git-memory-commit.py has no prior subject-length
validation to extend, so this is a new contract, not a change to an existing
one):

  - SUBJECT_MAX_LEN = 100 characters, measured on the FULL constructed
    subject line: EMOJIS[type] + " " + f"{type}({scope}): " + message. This
    is exactly the string build_commit_message() currently assembles as
    `parts[0]`, and exactly what ends up on git log %s / the boot hook's
    RESUME "Last:" line.
  - If the constructed subject exceeds SUBJECT_MAX_LEN: git-memory-commit.py
    must fail closed — exit non-zero, create NO commit — and the stderr
    message must name the limit and tell the caller to shorten `message` and
    move the remaining detail into `--body`.
  - `--body` itself stays completely unrestricted (it already exists for
    long-form content — see build_commit_message()); a short subject with a
    long --body must keep succeeding exactly as it does today. This is the
    "forcing the excess into --body" half of Bex's design decision — the
    script does not auto-split long messages, it rejects them and tells the
    caller to use the existing --body mechanism.
  - This gate applies to type "context" specifically, per Bex's design
    decision item 4 ("un commit context() que exceda ~100 caracteres").
    Other commit types are out of scope for this contract.

[ROJO] (must fail against the current script — no subject-length check
exists today, so oversized subjects commit successfully):
    - test_long_message_without_body_is_rejected
    - test_long_message_rejection_mentions_body_and_limit
    - test_subject_over_limit_by_one_char_is_rejected

[GUARDA] (must already pass today, and must keep passing after the fix):
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


class TestSubjectLengthFailClosed:
    """[ROJO] Oversized context() subjects must be rejected, not committed."""

    def test_long_message_without_body_is_rejected(self, tmp_path):
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        long_message = "x" * 150  # prefix + this comfortably exceeds SUBJECT_MAX_LEN
        rc, out, err = run_script(COMMIT_SCRIPT, repo, ["context", "auth", long_message])
        assert rc != 0, "commit with oversized subject and no --body must fail closed"
        assert _commit_count(repo) == before, (
            "no commit should have been created for a rejected oversized subject"
        )

    def test_long_message_rejection_mentions_body_and_limit(self, tmp_path):
        repo = _make_repo(tmp_path)
        long_message = "x" * 150
        rc, out, err = run_script(COMMIT_SCRIPT, repo, ["context", "auth", long_message])
        assert str(SUBJECT_MAX_LEN) in err, f"error should name the {SUBJECT_MAX_LEN}-char limit: {err!r}"
        assert "--body" in err, f"error should tell the caller to use --body for the rest: {err!r}"

    def test_subject_over_limit_by_one_char_is_rejected(self, tmp_path):
        """Boundary: exactly SUBJECT_MAX_LEN + 1 chars must already be rejected."""
        repo = _make_repo(tmp_path)
        before = _commit_count(repo)
        prefix_len = _subject_prefix_len("context", "auth")
        message = "x" * (SUBJECT_MAX_LEN - prefix_len + 1)
        rc, out, err = run_script(COMMIT_SCRIPT, repo, ["context", "auth", message])
        assert rc != 0, "subject one character over the limit must be rejected"
        assert _commit_count(repo) == before


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
