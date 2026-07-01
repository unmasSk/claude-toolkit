"""
Regression tests for session-start-crew.py — Bug B.

BUG B (~line 41): `claude_md.read_text(encoding='utf-8')` is called without
try/except. When CLAUDE.md contains non-UTF-8 bytes this raises
UnicodeDecodeError and propagates out of main(), crashing the hook.

Because this is a SessionStart hook it MUST be fail-open: exit 0 always,
even when CLAUDE.md is unreadable. Crashing the hook breaks every session
start in repos with binary or mixed-encoding files.

Expected behaviour after fix:
    CLAUDE.md with non-UTF-8 bytes  → read with errors='replace' or try/except
                                       → hook continues / exits 0, no crash
    CLAUDE.md missing               → existing behaviour (creates it) unchanged

RED contract (these tests MUST fail before the fix):
    - test_non_utf8_claude_md_does_not_crash  → currently raises UnicodeDecodeError
                                                 → hook exits non-zero / crashes
"""

import os
import sys

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_script

HOOK_PATH = os.path.join(HOOKS_DIR, "session-start-crew.py")


# ── Repo helpers ──────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Minimal git repo with user identity configured."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _run_hook(repo):
    """Invoke session-start-crew.py with cwd=repo. Returns (rc, stdout, stderr)."""
    return run_script(HOOK_PATH, repo)


# ── Bug B regression tests ────────────────────────────────────────────────

class TestNonUtf8ClaudeMd:
    """SessionStart hook must not crash when CLAUDE.md contains non-UTF-8 bytes.

    Before the fix: read_text(encoding='utf-8') raises UnicodeDecodeError.
    After the fix: tolerant reading (errors='replace' or try/except) → exit 0.
    """

    def test_non_utf8_claude_md_does_not_crash(self, tmp_path):
        """CLAUDE.md with 0xFF 0xFE BOM + Latin-1 payload must not crash the hook.

        BUG: read_text(encoding='utf-8') raises UnicodeDecodeError for these bytes.
        EXPECTED after fix: hook exits 0 without propagating the exception.
        """
        repo = _make_repo(tmp_path)
        claude_md_path = os.path.join(repo, "CLAUDE.md")

        # Write bytes that are invalid UTF-8 (UTF-16 LE BOM + Latin-1 content)
        bad_bytes = b"\xff\xfe contenido con bytes inv\xe1lidos"
        with open(claude_md_path, "wb") as f:
            f.write(bad_bytes)

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0, (
            f"SessionStart hook must exit 0 (fail-open) when CLAUDE.md has "
            f"non-UTF-8 bytes. Got rc={rc}. stderr={stderr!r}"
        )

    def test_non_utf8_claude_md_no_exception_in_output(self, tmp_path):
        """The hook must not print a Python traceback when CLAUDE.md is non-UTF-8.

        If UnicodeDecodeError propagates, Python prints the traceback to stderr
        and exits non-zero. We assert no traceback is present.
        """
        repo = _make_repo(tmp_path)
        claude_md_path = os.path.join(repo, "CLAUDE.md")

        bad_bytes = b"\xff\xfe" + bytes(range(0x80, 0x100))
        with open(claude_md_path, "wb") as f:
            f.write(bad_bytes)

        rc, stdout, stderr = _run_hook(repo)

        assert "UnicodeDecodeError" not in stderr, (
            f"UnicodeDecodeError must not reach stderr. stderr={stderr!r}"
        )
        assert "Traceback" not in stderr, (
            f"No Python traceback expected. stderr={stderr!r}"
        )

    def test_valid_utf8_claude_md_still_works(self, tmp_path):
        """CONTROL: normal UTF-8 CLAUDE.md must still be processed correctly."""
        repo = _make_repo(tmp_path)
        claude_md_path = os.path.join(repo, "CLAUDE.md")
        with open(claude_md_path, "w", encoding="utf-8") as f:
            f.write("# Project\n\nSome content.\n")

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0, (
            f"Hook must work normally with valid UTF-8 CLAUDE.md. "
            f"Got rc={rc}. stderr={stderr!r}"
        )

    def test_missing_claude_md_still_works(self, tmp_path):
        """CONTROL: absent CLAUDE.md (existing behaviour) must not be broken."""
        repo = _make_repo(tmp_path)
        # No CLAUDE.md created

        rc, stdout, stderr = _run_hook(repo)

        assert rc == 0, (
            f"Hook must exit 0 when CLAUDE.md is absent. "
            f"Got rc={rc}. stderr={stderr!r}"
        )
