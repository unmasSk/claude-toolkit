"""
Regression tests for security/robustness findings.

BUG A — stdin not bounded in several hooks
------------------------------------------
hooks/pre-merge-gate.py, hooks/pre-task-recall.py,
hooks/pre-memory-dedup-gate.py, hooks/validate-memory-path.py
all call sys.stdin.read() without a size limit.  A very large payload is read
fully into RAM.

These tests are GUARDS: they pass NOW (the hooks do not crash or hang on large
input) and must continue to pass AFTER the fix (which adds a read limit).
The invariant being pinned: "stdin of >600 KB must not crash or hang the hook
and must produce a valid JSON response (or exit 0)".

Because there is currently no code-level limit the tests cannot assert "only N
bytes were processed" — that assertion is Ultron's to add.  What we CAN assert
now is the fail-open / fail-closed contract.  The tests are marked GUARD and
documented accordingly.

BUG B — GIT_MEMORY_CO_AUTHOR newline injection in bin/git-memory-commit.py
---------------------------------------------------------------------------
CO_AUTHOR is taken verbatim from the env var and appended to the commit
message without any sanitisation.  A value containing a newline + a fake
trailer injects that line into the commit message.

This test is RED now: the injected line appears in the commit.
After Ultron's fix it must be GREEN (injected line absent).

BUG C — unvalidated `count` argument in bin/git-memory-log.py
--------------------------------------------------------------
git-memory-log.py accepts `count` as a positional int.  Negative values are
passed as -n<negative> to `git log`, which dumps the full history.  Zero and
negative counts should be rejected with a clear error (exit != 0) before git
is called.

These tests are RED now: negative count exits 0 and dumps output.
After Ultron's fix they must be GREEN.

BUG D — manifest.json written through a pre-planted symlink (Argus SEC-HIGH-NEW-03)
-------------------------------------------------------------------------------------
bin/git-memory-install.py:_create_manifest() and bin/git-memory-upgrade.py's
inline "Update manifest" block in apply_upgrade() both write
.claude/.unmassk/manifest.json via plain `open(manifest_path, "w")` — unlike
lib/boot_memory.py's writers, which already use
git_helpers.open_no_follow_symlink() (SEC-CRIT-001, fixed earlier this
session). A malicious repo (or a leftover symlink from a prior compromise)
can have that path be a symlink (git blob mode 120000, or simply pre-existing
on disk) pointing outside the repo. Both `install --auto` and `upgrade --auto`
follow it silently and overwrite the file it points to with generated JSON —
confirmed live against the unmodified scripts (session 2026-07-05): the
victim file's original content is destroyed in both cases, no exception
raised.

These tests are RED now: the victim file is overwritten.
After Ultron's fix (using open_no_follow_symlink(), matching boot_memory.py's
existing pattern) they must be GREEN: the victim file is left untouched.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, BIN_DIR, INSTALL, UPGRADE, git_cmd, run_script, run_cmd

# ── Path constants ─────────────────────────────────────────────────────────────

HOOK_PRE_MERGE_GATE     = os.path.join(HOOKS_DIR, "pre-merge-gate.py")
HOOK_PRE_TASK_RECALL    = os.path.join(HOOKS_DIR, "pre-task-recall.py")
HOOK_PRE_DEDUP          = os.path.join(HOOKS_DIR, "pre-memory-dedup-gate.py")
HOOK_VALIDATE_MEM_PATH  = os.path.join(HOOKS_DIR, "validate-memory-path.py")

GIT_MEMORY_COMMIT = os.path.join(BIN_DIR, "git-memory-commit.py")
GIT_MEMORY_LOG    = os.path.join(BIN_DIR, "git-memory-log.py")

# 640 KB — clearly above any reasonable stdin limit
_LARGE_STDIN_SIZE = 640 * 1024


# ── Shared repo helpers ────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    """Minimal git repo with user identity configured."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


# ── BUG A helpers ─────────────────────────────────────────────────────────────

def _build_large_bash_payload(size_bytes=_LARGE_STDIN_SIZE):
    """
    Build a structurally valid JSON payload for a Bash tool call whose
    'command' field is padded to exceed size_bytes in total.

    The command is a simple 'echo x' followed by spaces to reach the target
    size.  It is valid JSON and would normally be handled quickly.
    """
    base_command = "echo x"
    # Pad with spaces so total serialised JSON exceeds target
    padding = " " * (size_bytes - len(base_command))
    payload = {
        "tool_name": "Bash",
        "tool_input": {"command": base_command + padding},
    }
    return json.dumps(payload)


def _build_large_task_payload(size_bytes=_LARGE_STDIN_SIZE):
    """
    Valid JSON payload for a Task tool call (pre-task-recall hook).

    The 'prompt' field is padded to reach the target size.
    """
    base_prompt = "build the auth module"
    padding = " " * (size_bytes - len(base_prompt))
    payload = {
        "tool_name": "Task",
        "tool_input": {
            "subagent_type": "bilbo",  # non-whitelisted → passthrough, no recall
            "prompt": base_prompt + padding,
        },
    }
    return json.dumps(payload)


def _build_large_write_payload(git_root, size_bytes=_LARGE_STDIN_SIZE):
    """
    Valid JSON payload for a Write tool call (validate-memory-path hook).

    file_path points inside agent-memory so the hook evaluates the path.
    The padding is in a non-parsed field so it does not affect the decision.
    """
    file_path = os.path.join(git_root, ".claude", "agent-memory", "test-agent", "test.md")
    base = "x"
    padding = " " * (size_bytes - len(base))
    payload = {
        "tool_name": "Write",
        "tool_input": {
            "file_path": file_path,
            "content": base + padding,
        },
    }
    return json.dumps(payload)


def _run_hook_with_payload(hook_path, repo, payload_str, timeout=20):
    """
    Invoke a hook as a subprocess, passing payload_str via stdin.

    Returns (returncode, stdout, stderr).
    Timeout is generous (20 s) to detect hangs, not to be flaky.
    """
    rc, stdout, stderr = run_cmd(
        [sys.executable, hook_path],
        cwd=repo,
        input_text=payload_str,
        timeout=timeout,
    )
    return rc, stdout, stderr


# ══════════════════════════════════════════════════════════════════════════════
# BUG A — stdin size limit (GUARD tests — green now, must stay green after fix)
# ══════════════════════════════════════════════════════════════════════════════

class TestBugAStdinLimitGuards:
    """
    GUARD tests — these pass now AND must pass after the fix.

    The invariant: each hook MUST handle a >600 KB stdin payload without
    crashing (non-zero exit from an unhandled exception), without hanging
    (> 20 s timeout), and must produce a valid JSON response on stdout.

    After the fix the hooks will truncate the input at a defined limit.
    The response contract (approve / block / allow) must not change for
    structurally valid payloads that fit within the limit — and for payloads
    that exceed the limit the hook must still exit 0 and emit valid JSON
    (fail-open for task hooks, fail-closed for security hooks that were already
    fail-closed).

    These tests do NOT assert how many bytes were consumed — that assertion
    is Ultron's to add when the read limit is introduced.  They assert only
    that the hook terminates successfully and emits parseable JSON.
    """

    # GUARD: pre-merge-gate with >600 KB Bash payload
    def test_pre_merge_gate_large_stdin_does_not_crash_or_hang(self, tmp_path):
        """
        GUARD: pre-merge-gate handles a >600 KB Bash payload without crashing.

        The command is 'echo x' padded with spaces — no git merge/pull present.
        Expected: hook exits 0, stdout is parseable JSON with decision=approve.
        """
        repo = _make_repo(tmp_path)
        payload = _build_large_bash_payload()
        rc, stdout, stderr = _run_hook_with_payload(HOOK_PRE_MERGE_GATE, repo, payload)

        assert rc == 0, f"pre-merge-gate exited {rc} on large stdin. stderr: {stderr[:500]}"
        parsed = json.loads(stdout)
        assert "decision" in parsed, f"pre-merge-gate stdout not valid decision JSON: {stdout[:200]}"
        # A plain echo command must not be blocked
        assert parsed["decision"] == "approve", (
            f"pre-merge-gate blocked an innocuous echo command. response: {parsed}"
        )

    # GUARD: pre-task-recall with >600 KB Task payload
    def test_pre_task_recall_large_stdin_does_not_crash_or_hang(self, tmp_path):
        """
        GUARD: pre-task-recall handles a >600 KB Task payload without crashing.

        Subagent is 'bilbo' (non-whitelisted) → passthrough.
        Expected: hook exits 0, stdout is parseable JSON with permissionDecision=allow.
        """
        repo = _make_repo(tmp_path)
        payload = _build_large_task_payload()
        rc, stdout, stderr = _run_hook_with_payload(HOOK_PRE_TASK_RECALL, repo, payload)

        assert rc == 0, f"pre-task-recall exited {rc} on large stdin. stderr: {stderr[:500]}"
        parsed = json.loads(stdout)
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow", (
            f"pre-task-recall did not allow on large stdin. response: {parsed}"
        )

    # GUARD: pre-memory-dedup-gate with >600 KB Bash payload
    def test_pre_memory_dedup_gate_large_stdin_does_not_crash_or_hang(self, tmp_path):
        """
        GUARD: pre-memory-dedup-gate handles a >600 KB Bash payload.

        Command is 'echo x' padded — does not match the commit pattern.
        Expected: hook exits 0, stdout is parseable JSON with permissionDecision=allow,
        no permissionDecisionReason.
        """
        repo = _make_repo(tmp_path)
        payload = _build_large_bash_payload()
        rc, stdout, stderr = _run_hook_with_payload(HOOK_PRE_DEDUP, repo, payload)

        assert rc == 0, f"pre-memory-dedup-gate exited {rc} on large stdin. stderr: {stderr[:500]}"
        parsed = json.loads(stdout)
        hso = parsed.get("hookSpecificOutput", {})
        assert hso.get("permissionDecision") == "allow", (
            f"pre-memory-dedup-gate did not allow on large stdin. response: {parsed}"
        )
        # No dedup warning on a plain echo command
        assert "permissionDecisionReason" not in hso, (
            f"pre-memory-dedup-gate emitted unexpected warning on echo command: {hso}"
        )

    # GUARD: validate-memory-path with >600 KB Write payload
    def test_validate_memory_path_large_stdin_does_not_crash_or_hang(self, tmp_path):
        """
        GUARD: validate-memory-path handles a >600 KB Write payload.

        file_path points inside the repo's agent-memory → should approve.
        Expected: hook exits 0, stdout is parseable JSON with decision=approve.
        """
        repo = _make_repo(tmp_path)
        payload = _build_large_write_payload(repo)
        rc, stdout, stderr = _run_hook_with_payload(HOOK_VALIDATE_MEM_PATH, repo, payload)

        assert rc == 0, f"validate-memory-path exited {rc} on large stdin. stderr: {stderr[:500]}"
        parsed = json.loads(stdout)
        assert "decision" in parsed, f"validate-memory-path stdout not valid JSON: {stdout[:200]}"
        # Path is inside the repo's agent-memory: the hook should approve
        assert parsed["decision"] == "approve", (
            f"validate-memory-path blocked an in-bounds write with large stdin. response: {parsed}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG B — GIT_MEMORY_CO_AUTHOR newline injection (RED now)
# ══════════════════════════════════════════════════════════════════════════════

class TestBugBCoAuthorInjection:
    """
    BUG B: GIT_MEMORY_CO_AUTHOR containing a newline injects a fake trailer
    into the commit message.

    Expected state NOW (before fix): RED — the injected trailer appears.
    Expected state AFTER fix: GREEN — the injected trailer is absent.

    The fix must sanitise or reject newlines in CO_AUTHOR before appending
    it to the commit message.
    """

    def test_co_author_newline_does_not_inject_fake_trailer(self, tmp_path):
        """
        RED: CO_AUTHOR with embedded newline + fake trailer must NOT appear
        in the resulting commit message.

        Steps:
        1. Create a temp git repo with user identity.
        2. Set GIT_MEMORY_CO_AUTHOR to a value containing a newline followed
           by a fake 'Resolved-Next: fake' trailer.
        3. Run git-memory-commit.py decision test "msg" in that repo.
        4. Read the commit message of the resulting commit.
        5. Assert that 'Resolved-Next: fake' is NOT in the message.

        Currently FAILS because the value is appended verbatim.
        """
        repo = _make_repo(tmp_path)

        injected_line = "Resolved-Next: fake"
        malicious_co_author = f"Co-Authored-By: legit <legit@example.com>\n{injected_line}"

        env_override = {
            "GIT_MEMORY_CO_AUTHOR": malicious_co_author,
            # Disable gh CLI to avoid network calls
            "PATH": os.environ.get("PATH", ""),
        }

        rc, stdout, stderr = run_script(
            GIT_MEMORY_COMMIT,
            repo,
            extra_args=["decision", "test", "injection test"],
            env=env_override,
        )

        # The commit must succeed (or fail only because git rejects it — both OK
        # as long as the injected trailer did not land in the history).
        # We check the actual commit message via git log.
        _, log_out, _ = git_cmd(
            ["log", "-1", "--pretty=format:%B"],
            repo,
        )

        assert injected_line not in log_out, (
            f"BUG B: injected trailer found in commit message.\n"
            f"Commit body:\n{log_out}\n"
            f"GIT_MEMORY_CO_AUTHOR was: {malicious_co_author!r}"
        )

    def test_co_author_without_newline_is_accepted(self, tmp_path):
        """
        Control: a clean CO_AUTHOR value (no newline) must work normally.

        This test must be GREEN before AND after the fix.
        """
        repo = _make_repo(tmp_path)

        clean_co_author = "Co-Authored-By: legit <legit@example.com>"
        env_override = {
            "GIT_MEMORY_CO_AUTHOR": clean_co_author,
            "PATH": os.environ.get("PATH", ""),
        }

        rc, stdout, stderr = run_script(
            GIT_MEMORY_COMMIT,
            repo,
            extra_args=["decision", "test", "clean co-author test"],
            env=env_override,
        )

        assert rc == 0, (
            f"git-memory-commit.py failed with clean CO_AUTHOR. rc={rc}\n"
            f"stderr: {stderr[:500]}"
        )

        _, log_out, _ = git_cmd(
            ["log", "-1", "--pretty=format:%B"],
            repo,
        )
        # The clean line must appear in the commit
        assert "Co-Authored-By: legit" in log_out, (
            f"Clean Co-Authored-By line absent from commit message.\nBody: {log_out}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG C — unvalidated `count` in git-memory-log.py (RED for negative, GREEN for valid)
# ══════════════════════════════════════════════════════════════════════════════

class TestBugCLogCountValidation:
    """
    BUG C: git-memory-log.py passes the `count` argument directly to
    `git log -n<count>` without validation.

    - count = -1  → git log -n-1  → dumps the full history (RED now).
    - count = 0   → git log -n0   → no output, but should also be rejected.
    - count = 5   → works fine (GREEN now, stays GREEN after fix).

    Expected state after fix:
    - Negative and zero counts exit != 0 with a clear error message,
      WITHOUT calling git log.
    """

    def _populate_repo(self, repo, commit_count=15):
        """Add N empty commits so the repo has enough history to detect 'full dump'."""
        for i in range(commit_count):
            git_cmd(["commit", "--allow-empty", "-m", f"chore: filler {i}"], repo)

    def test_negative_count_is_rejected(self, tmp_path):
        """
        RED: git-memory-log.py -1 must exit != 0 and NOT dump the full history.

        Currently: exits 0 and passes -n-1 to git log, which outputs everything.
        After fix: exits != 0 with a validation error before calling git.
        """
        repo = _make_repo(tmp_path)
        self._populate_repo(repo, commit_count=15)

        rc, stdout, stderr = run_script(GIT_MEMORY_LOG, repo, extra_args=["-1"])

        assert rc != 0, (
            f"BUG C: git-memory-log.py -1 exited 0 (should be rejected).\n"
            f"stdout (first 500): {stdout[:500]}"
        )

    def test_negative_count_does_not_dump_full_history(self, tmp_path):
        """
        RED companion: when count=-1, all commits must NOT appear in stdout.

        Even if the exit code is 0 (current behaviour), the output must not
        contain the full history.  After the fix this test is redundant but
        harmless (exit != 0 means stdout will be empty anyway).

        We commit a sentinel string unique enough to detect full-history output.
        """
        sentinel = "zz-sentinel-full-dump-xyzabc"
        repo = _make_repo(tmp_path)
        git_cmd(["commit", "--allow-empty", "-m", f"chore: {sentinel}"], repo)
        self._populate_repo(repo, commit_count=15)

        _, stdout, _ = run_script(GIT_MEMORY_LOG, repo, extra_args=["-1"])

        assert sentinel not in stdout, (
            f"BUG C: git-memory-log.py -1 printed full history (sentinel found).\n"
            f"stdout (first 500): {stdout[:500]}"
        )

    def test_zero_count_is_rejected(self, tmp_path):
        """
        RED: git-memory-log.py 0 must exit != 0.

        A count of 0 means "show zero commits" which is not useful and
        should be rejected as an invalid argument.
        """
        repo = _make_repo(tmp_path)

        rc, stdout, stderr = run_script(GIT_MEMORY_LOG, repo, extra_args=["0"])

        assert rc != 0, (
            f"BUG C: git-memory-log.py 0 exited 0 (should be rejected).\n"
            f"stdout: {stdout[:500]}"
        )

    def test_valid_positive_count_works(self, tmp_path):
        """
        GREEN control: a valid positive count (5) must always work.

        This test must be GREEN before AND after the fix.
        """
        repo = _make_repo(tmp_path)
        self._populate_repo(repo, commit_count=10)

        rc, stdout, stderr = run_script(GIT_MEMORY_LOG, repo, extra_args=["5"])

        assert rc == 0, (
            f"git-memory-log.py 5 failed unexpectedly. rc={rc}\n"
            f"stderr: {stderr[:500]}"
        )

    def test_very_large_count_does_not_error(self, tmp_path):
        """
        GUARD: a very large count (e.g. 99999) passed to git log may produce
        a git error on some platforms.

        After the fix, Ultron may choose to cap large counts to a sane maximum
        or let git handle them.  This test asserts only that the tool does not
        crash with an unhandled exception (exit != 1 from Python exception, not
        from git error which is acceptable).

        Marked GREEN if the tool exits 0 (git handles it fine) or exits 1 with
        a clean error message.  Any non-zero exit from an unhandled Python
        traceback is a failure.
        """
        repo = _make_repo(tmp_path)
        self._populate_repo(repo, commit_count=3)

        rc, stdout, stderr = run_script(GIT_MEMORY_LOG, repo, extra_args=["99999"])

        # Acceptable: exit 0 (git printed what it had) or exit 1 with clean error.
        # Not acceptable: Python traceback in stderr.
        assert "Traceback" not in stderr, (
            f"git-memory-log.py 99999 raised an unhandled Python exception.\n"
            f"stderr: {stderr[:500]}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG D — manifest.json write follows a pre-planted symlink (RED now)
# ══════════════════════════════════════════════════════════════════════════════

def _plant_symlink(target_path, victim_path):
    """Point target_path at victim_path, replacing whatever is currently there.

    Uses lexists (not exists) so a broken symlink at target_path is still
    detected and removed — exists() follows the link and would wrongly report
    False for a dangling link, skipping the cleanup.
    """
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if os.path.lexists(target_path):
        os.remove(target_path)
    os.symlink(victim_path, target_path)


class TestBugDManifestSymlinkWrite:
    """
    BUG D: both git-memory-install.py and git-memory-upgrade.py write
    .claude/.unmassk/manifest.json via plain open(path, "w"), silently
    following a pre-existing symlink at that path and overwriting whatever
    it points to.

    Expected state NOW (before fix): RED — the victim file's content is
    destroyed.
    Expected state AFTER fix: GREEN — the victim file is untouched (the
    write must refuse to follow the symlink, mirroring
    git_helpers.open_no_follow_symlink() already used for boot-log-latest.txt
    and glossary-cache.json).
    """

    def test_install_does_not_follow_symlink_at_manifest_path(self, tmp_path):
        """
        RED: `git-memory-install.py --auto` must not follow a symlink planted
        at .claude/.unmassk/manifest.json before install ever runs.

        Setup mirrors the confirmed repro (session 2026-07-05): create a bare
        repo (no install yet), pre-create .claude/.unmassk/ with the manifest
        path already a symlink to an outside victim file, then run install.
        """
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-install.json"
        victim.write_text("SENSITIVE ORIGINAL CONTENT")

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        rc, stdout, stderr = run_script(INSTALL, repo, extra_args=["--auto"])

        assert victim.read_text() == "SENSITIVE ORIGINAL CONTENT", (
            "BUG D: git-memory-install.py --auto followed a symlink planted at "
            "the manifest.json path and overwrote the file it points to. "
            f"install rc={rc}\nstdout (first 500): {stdout[:500]}\n"
            f"stderr (first 500): {stderr[:500]}"
        )

    def test_upgrade_does_not_follow_symlink_at_manifest_path(self, tmp_path):
        """
        RED: `git-memory-upgrade.py --auto` must not follow a symlink planted
        at .claude/.unmassk/manifest.json when it rewrites the manifest as
        part of applying an upgrade.

        Setup: install normally first, then replace the real manifest with a
        symlink to an outside victim file. The victim file must itself be
        valid manifest-shaped JSON with an old version, so
        read_installed_manifest() succeeds and check_upgrade_needed() finds
        a genuine version-mismatch reason — otherwise upgrade would exit
        early ("no installation to upgrade") without ever reaching the
        write, and the test would prove nothing about the symlink guard.
        """
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])

        victim = tmp_path / "victim-manifest-upgrade.json"
        victim.write_text(json.dumps({
            "version": "1.0.0",
            "installed_at": "2020-01-01T00:00:00",
            "runtime_mode": "normal",
        }))

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--auto"])

        assert "1.0.0" in victim.read_text(), (
            "BUG D: git-memory-upgrade.py --auto followed a symlink planted at "
            "the manifest.json path and overwrote the file it points to. "
            f"upgrade rc={rc}\nstdout (first 500): {stdout[:500]}\n"
            f"stderr (first 500): {stderr[:500]}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
