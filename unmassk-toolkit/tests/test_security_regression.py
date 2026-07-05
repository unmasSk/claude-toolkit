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

BUG F — bin/git-memory-doctor.py reads AND writes manifest.json through a
symlink, unguarded (Argus SEC-CRIT-NEW-06)
--------------------------------------------------------------------------
check_manifest() (plain `open(manifest_path)`) and the end of run_doctor()
(reads, then writes back with an updated `last_healthcheck_at` timestamp,
both via plain `open()`) never guard against manifest_path being a symlink.
This runs on EVERY boot via lib/boot_checks.py:run_doctor(), which invokes
exactly `git-memory-doctor.py --json`. Confirmed live (session 2026-07-05):
a symlink at .claude/.unmassk/manifest.json pointing at an outside victim
JSON file causes (1) the victim's "version" field to leak into the JSON
report and (2) the victim file to be silently rewritten with an added
`last_healthcheck_at` key — a write-through-symlink, not just a read.

These tests are RED now: the victim file's content leaks into stdout AND
gets modified. After Ultron's fix (open_no_follow_symlink() on both the
check_manifest() read and the run_doctor() read+write-back, treating a
symlinked path exactly like "no manifest present") they must be GREEN.

BUG G — bin/git-memory-upgrade.py:create_backup() path traversal via the
unsanitized "version" field (Argus SEC-HIGH-NEW-07)
--------------------------------------------------------------------------
create_backup() builds `backup_name = f"manifest-v{version}-{timestamp}.json"`
straight from the installed manifest's "version" field, then
`os.path.join(backup_dir, backup_name)`. Because the value is embedded
mid-string (not passed as a standalone path component), the traversal only
resolves if the first path segment it produces ("manifest-v" + the version's
prefix up to its first "/") already exists as a real directory — which a
malicious repo can arrange by ALSO committing that placeholder directory
alongside a manifest.json with a matching "version" field (same "attacker
controls the whole repo" threat model as BUG D/E). Confirmed live (session
2026-07-05): with a pre-existing `.claude/backups/manifest-vX/` directory
and version `"X/../../../../PWNED-TRAVERSAL-MARKER"`, running
`git memory upgrade --auto` writes a fully attacker-controlled JSON backup
file OUTSIDE `.claude/backups/`, landing at the project's parent directory.

This test is RED now: the backup file lands outside `.claude/backups/`.
After Ultron's fix (sanitize/validate "version" before using it in a
filename — e.g. reject or strip path separators) it must be GREEN: the
backup always stays inside `.claude/backups/`, regardless of the version
field's content.

BUG H — manifest "version" field printed to terminal unsanitized in
non-JSON mode (Argus SEC-MED-NEW-08)
--------------------------------------------------------------------------
bin/git-memory-doctor.py (line 394, "Manifest" check message) and
bin/git-memory-upgrade.py (the "Version mismatch" reason built in
check_upgrade_needed(), and the "Installed:"/"Upgrade complete:" lines in
main()) all print the manifest's "version" field directly to the terminal
in non-JSON mode without passing it through any sanitizer — unlike
Decision/Memo/Remember/branch-name values elsewhere in this codebase, which
already go through `sanitize_trailer_value()`. A version field containing
raw ANSI escape bytes (ESC, \\x1b) is printed verbatim, allowing terminal
escape-sequence injection (e.g. clearing the screen, recoloring subsequent
output). Confirmed live (session 2026-07-05) for both scripts.

These tests are RED now: raw \\x1b bytes appear in stdout.
After Ultron's fix (sanitize "version" before any print, e.g. via
sanitize_trailer_value() or an explicit control-byte strip) they must be
GREEN: no raw ESC byte reaches stdout.

BUG I — bin/git-memory-repair.py's diagnose() silently trusts a symlinked
manifest.json as valid (barrido finding, same class as BUG E)
--------------------------------------------------------------------------
diagnose() checks the manifest with plain `os.path.isfile()` (follows
symlinks) + plain `open()`+`json.load()` (also follows symlinks and trusts
the parsed content). If a symlink at .claude/.unmassk/manifest.json points
to a syntactically valid external JSON file, diagnose() reports ZERO
manifest-related issues — it never even recognizes anything is wrong, so
`git memory repair` never repairs it and the symlink stays in place,
silently trusting attacker-controlled content indefinitely. Confirmed live
(session 2026-07-05): only the unrelated "CLAUDE.md not found" issue is
reported; no manifest issue appears.

This test is RED now: diagnose() reports no manifest issue for a symlinked
manifest. After Ultron's fix (open_no_follow_symlink() on the read, treating
a symlink like "no manifest present" → flagged as missing/corrupt so repair
recreates a real file) it must be GREEN.

BUG J — bin/git-memory-bootstrap.py's check_existing_memory(): same
symlink-read gap as BUG E/I, PLUS the same unsanitized-version-print gap as
BUG H (barrido finding, new site not named by Argus)
--------------------------------------------------------------------------
check_existing_memory() reads .claude/.unmassk/manifest.json via plain
`open()` (follows a symlink, trusts the target's "version" field as
`installed_version`), and that value is later embedded verbatim into a
finding's "text" field, printed to the terminal by format_human() in
non-JSON mode — with no sanitization anywhere in the chain. Confirmed live
(session 2026-07-05): (1) a symlinked manifest's victim version string
("0.0.1-VICTIM-BOOTSTRAP") appears directly in bootstrap's stdout, and (2) a
real (non-symlinked) manifest with raw ESC bytes in "version" also reaches
stdout unsanitized.

These tests are RED now. After Ultron's fix (open_no_follow_symlink() on the
read + sanitizing "version" before embedding it in any finding text) they
must be GREEN.
"""

import json
import os
import subprocess
import sys

import pytest

from conftest import (
    SOURCE_ROOT, HOOKS_DIR, BIN_DIR, INSTALL, UPGRADE, DOCTOR, REPAIR, BOOTSTRAP,
    git_cmd, run_script, run_cmd,
)

# ── Path constants ─────────────────────────────────────────────────────────────

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")

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


# ══════════════════════════════════════════════════════════════════════════════
# BUG E — manifest.json READ paths follow a pre-planted symlink (SEC-LOW-NEW-05)
# ══════════════════════════════════════════════════════════════════════════════
#
# lib/boot_render.py:check_version_mismatch() (plain `os.path.isfile()` +
# `open(manifest_path)`) and bin/git-memory-upgrade.py:read_installed_manifest()
# (plain `open(manifest_path)`) both read .claude/.unmassk/manifest.json without
# the symlink guard already applied to boot_memory.py's readers
# (_read_glossary_cache(), SEC-MED-NEW-02, fixed earlier this session) and to
# every writer of that same directory (SEC-CRIT-001 / SEC-HIGH-NEW-03). A
# symlink planted at the manifest path, pointing outside the repo, is silently
# followed and its content trusted as a real, valid manifest.
#
# These tests are RED now: the victim file's content is read and acted upon.
# After Ultron's fix (open_no_follow_symlink() in read mode / an explicit
# symlink check, mirroring _read_glossary_cache()'s existing pattern) they
# must be GREEN: a symlinked manifest path is treated exactly like "no
# manifest present" — never followed, never read.

def _check_version_mismatch(repo):
    """Call boot_render.check_version_mismatch() with `repo` as CWD.

    Plain isolated subprocess call (no sys.modules stubbing involved) —
    same direct-import-and-call pattern documented in
    unmassk-toolkit-python-test-conventions.md, adapted for a lib/ module
    that isn't hyphenated.
    """
    code = f"""
import sys, os, json, importlib.util
sys.path.insert(0, {repr(LIB_DIR)})
os.chdir({repr(repo)})
spec = importlib.util.spec_from_file_location(
    "boot_render_probe", os.path.join({repr(LIB_DIR)}, "boot_render.py"))
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
result = mod.check_version_mismatch()
print(json.dumps({{"result": result}}))
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(f"_check_version_mismatch failed (rc={proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])["result"]


class TestBugECheckVersionMismatchManifestSymlinkRead:
    """check_version_mismatch() must not follow a symlink planted at
    .claude/.unmassk/manifest.json."""

    def test_check_version_mismatch_does_not_follow_symlink(self, tmp_path):
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-checkversion.json"
        victim.write_text(json.dumps({"version": "0.0.1-SYMLINK-VICTIM"}))

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        result = _check_version_mismatch(repo)

        assert result is None or "0.0.1-SYMLINK-VICTIM" not in result, (
            "BUG SEC-LOW-NEW-05: check_version_mismatch() followed a symlink "
            "planted at the manifest.json path and read the victim file's "
            f"content as if it were a real manifest. result={result!r}"
        )


class TestBugEUpgradeReadInstalledManifestSymlinkRead:
    """bin/git-memory-upgrade.py's read_installed_manifest() must not follow
    a symlink planted at .claude/.unmassk/manifest.json — the upgrade CLI
    must behave exactly as if no installation exists."""

    def test_upgrade_check_does_not_follow_symlink_at_manifest_path(self, tmp_path):
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-upgrade-check.json"
        victim.write_text(json.dumps({
            "version": "0.0.1-SYMLINK-VICTIM",
            "installed_at": "2020-01-01T00:00:00",
            "runtime_mode": "normal",
        }))

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--auto", "--check", "--json"])

        assert "0.0.1-SYMLINK-VICTIM" not in stdout, (
            "BUG SEC-LOW-NEW-05: git-memory-upgrade.py --check followed a "
            "symlink planted at the manifest.json path and reported the "
            f"victim file's version as the installed version. stdout={stdout!r}"
        )
        assert rc == 1, (
            "read_installed_manifest() must treat a symlinked manifest path "
            "exactly like a missing manifest — 'no installation to upgrade' "
            f"(exit 1) — but got rc={rc}, stdout={stdout!r}, stderr={stderr!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG F — doctor.py reads AND writes manifest.json through a symlink (RED now)
# ══════════════════════════════════════════════════════════════════════════════

class TestBugFDoctorManifestSymlinkReadWrite:
    """bin/git-memory-doctor.py's check_manifest() + the healthcheck-timestamp
    write-back at the end of run_doctor() must not follow a symlink planted
    at .claude/.unmassk/manifest.json — treat it exactly like "no manifest
    present", and never write through it."""

    def test_doctor_json_does_not_modify_victim_through_symlinked_manifest(self, tmp_path):
        """
        RED: `git-memory-doctor.py --json` (the exact command lib/boot_checks.py
        runs on every boot) must leave a symlinked manifest's target file
        byte-for-byte untouched.

        Currently: check_manifest() follows the symlink to read it, and the
        end of run_doctor() re-reads + rewrites it with an added
        'last_healthcheck_at' key — silently modifying the victim file.
        """
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-doctor.json"
        original_content = json.dumps({"version": "0.0.1-VICTIM-ORIGINAL", "secret": "do-not-touch"})
        victim.write_text(original_content)

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        rc, stdout, stderr = run_script(DOCTOR, repo, extra_args=["--json"])

        assert victim.read_text() == original_content, (
            "BUG SEC-CRIT-NEW-06: git-memory-doctor.py --json followed a "
            "symlink planted at the manifest.json path and modified the "
            f"victim file it points to. doctor rc={rc}\n"
            f"stdout (first 500): {stdout[:500]}\nstderr (first 500): {stderr[:500]}\n"
            f"victim content is now: {victim.read_text()!r}"
        )

    def test_doctor_json_does_not_leak_victim_version_through_symlinked_manifest(self, tmp_path):
        """
        RED companion: the victim's "version" field must not appear in
        doctor's JSON report — a symlinked manifest must be treated as if
        no manifest were present, never as a valid one to report on.
        """
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-doctor-leak.json"
        victim.write_text(json.dumps({"version": "0.0.1-VICTIM-LEAK-MARKER"}))

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        rc, stdout, stderr = run_script(DOCTOR, repo, extra_args=["--json"])

        assert "0.0.1-VICTIM-LEAK-MARKER" not in stdout, (
            "BUG SEC-CRIT-NEW-06: git-memory-doctor.py --json followed a "
            "symlink planted at the manifest.json path and reported the "
            f"victim file's version in its output. stdout={stdout!r}"
        )

    def test_doctor_json_still_updates_real_manifest_healthcheck_timestamp(self, tmp_path):
        """
        GREEN control: for a REAL (non-symlinked) manifest, doctor must still
        perform its normal healthcheck-timestamp update. This must pass
        BEFORE and AFTER the fix — proving the fix doesn't regress the
        legitimate write path, only the symlink case.
        """
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")

        rc, stdout, stderr = run_script(DOCTOR, repo, extra_args=["--json"])

        after = json.load(open(manifest_path))
        assert "last_healthcheck_at" in after, (
            f"Real (non-symlinked) manifest was not updated with a healthcheck "
            f"timestamp. doctor rc={rc}, stdout={stdout[:300]}, manifest={after!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG G — upgrade.py create_backup() path traversal via "version" (RED now)
# ══════════════════════════════════════════════════════════════════════════════

class TestBugGUpgradeBackupPathTraversal:
    """bin/git-memory-upgrade.py's create_backup() must never write outside
    .claude/backups/, regardless of the installed manifest's "version"
    field content."""

    def test_create_backup_rejects_path_traversal_in_version(self, tmp_path):
        """
        RED: a manifest whose "version" field is crafted to escape
        .claude/backups/ (in combination with a pre-existing placeholder
        directory an attacker-controlled repo would also commit — same
        "attacker controls the whole repo" model as BUG D/E) must not
        result in a backup file being written outside .claude/backups/.

        Confirmed live (session 2026-07-05): the unmodified script writes a
        fully attacker-controlled JSON file at the project's PARENT
        directory (outside the repo entirely).
        """
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])

        backup_dir = os.path.join(repo, ".claude", "backups")
        # The attacker-committed placeholder directory that makes the first
        # path segment of the traversal resolve to something real.
        os.makedirs(os.path.join(backup_dir, "manifest-vX"), exist_ok=True)

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        manifest = json.load(open(manifest_path))
        manifest["version"] = "X/../../../../PWNED-TRAVERSAL-MARKER"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--auto"])

        escaped_files = [
            p for p in os.listdir(str(tmp_path))
            if "PWNED-TRAVERSAL-MARKER" in p
        ]
        assert not escaped_files, (
            "BUG SEC-HIGH-NEW-07: git-memory-upgrade.py --auto wrote a backup "
            f"file outside .claude/backups/, at {tmp_path}/{escaped_files}. "
            f"upgrade rc={rc}\nstdout (first 800): {stdout[:800]}\n"
            f"stderr (first 500): {stderr[:500]}"
        )

    def test_create_backup_with_clean_version_stays_in_backup_dir(self, tmp_path):
        """
        GREEN control: a normal version string ("1.0.0", no path separators)
        must always produce a backup file inside .claude/backups/. Must pass
        BEFORE and AFTER the fix.
        """
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        manifest = json.load(open(manifest_path))
        manifest["version"] = "1.0.0"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--auto"])

        backup_dir = os.path.join(repo, ".claude", "backups")
        backups = [f for f in os.listdir(backup_dir) if f.startswith("manifest-v1.0.0-")]
        assert backups, (
            f"Expected a backup file inside {backup_dir} for a clean version "
            f"string. rc={rc}\nstdout: {stdout[:500]}\nfound: {os.listdir(backup_dir)}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG H — unsanitized "version" printed to terminal, non-JSON mode (RED now)
# ══════════════════════════════════════════════════════════════════════════════

_ESC = "\x1b"
_MALICIOUS_VERSION = f"{_ESC}[2J{_ESC}[31mPWNED-ESC-MARKER{_ESC}[0m"


def _write_manifest_version(manifest_path, version):
    """Overwrite an installed manifest.json's "version" field in place."""
    manifest = json.load(open(manifest_path))
    manifest["version"] = version
    with open(manifest_path, "w") as f:
        json.dump(manifest, f)


class TestBugHVersionFieldTerminalInjection:
    """bin/git-memory-doctor.py and bin/git-memory-upgrade.py must sanitize
    the manifest's "version" field before printing it to the terminal in
    non-JSON mode. A version containing raw ANSI escape bytes must never
    reach stdout verbatim."""

    def test_doctor_non_json_does_not_leak_raw_escape_bytes(self, tmp_path):
        """RED: doctor's "Manifest: vX" line embeds the raw ESC bytes."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _write_manifest_version(manifest_path, _MALICIOUS_VERSION)

        rc, stdout, stderr = run_script(DOCTOR, repo)

        assert _ESC not in stdout, (
            "BUG SEC-MED-NEW-08: git-memory-doctor.py printed the manifest's "
            "raw ANSI escape bytes to stdout unsanitized.\n"
            f"stdout (repr, first 500): {stdout[:500]!r}"
        )

    def test_upgrade_check_non_json_does_not_leak_raw_escape_bytes(self, tmp_path):
        """RED: upgrade's `--check` "Upgrade available: vX -> vY" line embeds
        the raw ESC bytes (installed_version comes straight from the
        manifest, via check_upgrade_needed()'s "Version mismatch" reason)."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _write_manifest_version(manifest_path, _MALICIOUS_VERSION)

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--check"])

        assert _ESC not in stdout, (
            "BUG SEC-MED-NEW-08: git-memory-upgrade.py --check printed the "
            "manifest's raw ANSI escape bytes to stdout unsanitized.\n"
            f"stdout (repr, first 500): {stdout[:500]!r}"
        )

    def test_upgrade_full_auto_run_does_not_leak_raw_escape_bytes(self, tmp_path):
        """RED: a full non-check, non-dry-run `--auto` upgrade prints the
        version at least 3 times ("Installed:", the "Changes needed:" reason
        line, and "Upgrade complete:") — all must be sanitized."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _write_manifest_version(manifest_path, _MALICIOUS_VERSION)

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--auto"])

        assert _ESC not in stdout, (
            "BUG SEC-MED-NEW-08: git-memory-upgrade.py --auto printed the "
            "manifest's raw ANSI escape bytes to stdout unsanitized at least "
            f"once in the full upgrade flow. rc={rc}\n"
            f"stdout (repr, first 1000): {stdout[:1000]!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG I — repair.py diagnose() trusts a symlinked manifest as valid (RED now)
# ══════════════════════════════════════════════════════════════════════════════

def _repair_diagnose(target):
    """Call bin/git-memory-repair.py's diagnose(target) directly via importlib,
    matching the direct-import-and-call pattern used elsewhere in this suite
    (see _check_version_mismatch above)."""
    code = f"""
import sys, os, json, importlib.util
sys.path.insert(0, {repr(LIB_DIR)})
spec = importlib.util.spec_from_file_location("repair_probe", {repr(REPAIR)})
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
issues = mod.diagnose({repr(target)})
print(json.dumps({{"issues": issues}}))
"""
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=15)
    if proc.returncode != 0:
        raise RuntimeError(f"_repair_diagnose failed (rc={proc.returncode}): {proc.stderr}")
    return json.loads(proc.stdout.strip().splitlines()[-1])["issues"]


class TestBugIRepairDiagnoseTrustsSymlinkedManifest:
    """diagnose() must not silently treat a symlinked manifest.json as a
    healthy, valid manifest — it must be flagged as an issue (missing or
    corrupt), same as SEC-LOW-NEW-05/BUG E's read-guard requirement."""

    def test_diagnose_flags_symlinked_manifest_as_an_issue(self, tmp_path):
        """
        RED: with a symlink at .claude/.unmassk/manifest.json pointing to a
        syntactically valid external JSON file, diagnose() currently reports
        ZERO manifest-related issues (silently trusts the victim content) —
        confirmed live (session 2026-07-05), only an unrelated "CLAUDE.md
        not found" issue appears. After the fix, a symlinked manifest must
        be flagged as an issue so `git memory repair` recreates a real file.
        """
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-repair.json"
        victim.write_text(json.dumps({"version": "0.0.1-VICTIM-REPAIR"}))

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        issues = _repair_diagnose(repo)
        manifest_issue_types = {i[0] for i in issues if i[1] == "manifest"}

        assert manifest_issue_types, (
            "BUG (barrido, same class as SEC-LOW-NEW-05): diagnose() did not "
            "flag a symlinked manifest.json as any kind of issue — it silently "
            f"trusted the victim file's content as a valid manifest. issues={issues!r}"
        )

    def test_diagnose_reports_no_manifest_issue_for_a_real_manifest(self, tmp_path):
        """
        GREEN control: a REAL (non-symlinked, valid) manifest must not be
        flagged as an issue. Must pass BEFORE and AFTER the fix.
        """
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])

        issues = _repair_diagnose(repo)
        manifest_issue_types = {i[0] for i in issues if i[1] == "manifest"}

        assert not manifest_issue_types, (
            f"diagnose() incorrectly flagged a real, valid manifest as an "
            f"issue. issues={issues!r}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# BUG J — bootstrap.py check_existing_memory(): symlink read + version leak
# ══════════════════════════════════════════════════════════════════════════════

class TestBugJBootstrapManifestSymlinkAndVersionLeak:
    """bin/git-memory-bootstrap.py's check_existing_memory() must not follow
    a symlink planted at .claude/.unmassk/manifest.json, and must sanitize
    the "version" field before it reaches any printed finding text."""

    def test_bootstrap_does_not_leak_victim_version_through_symlinked_manifest(self, tmp_path):
        """
        RED: a symlinked manifest's victim "version" string must not appear
        in bootstrap's stdout. Confirmed live (session 2026-07-05): the
        victim's version string appears verbatim in the "already installed"
        finding text.
        """
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-bootstrap.json"
        victim.write_text(json.dumps({"version": "0.0.1-VICTIM-BOOTSTRAP"}))

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_symlink(manifest_path, str(victim))

        rc, stdout, stderr = run_script(BOOTSTRAP, repo)

        assert "0.0.1-VICTIM-BOOTSTRAP" not in stdout, (
            "BUG (barrido, same class as SEC-LOW-NEW-05): "
            "git-memory-bootstrap.py followed a symlink planted at the "
            "manifest.json path and reported the victim file's version in "
            f"its output. stdout={stdout[:500]!r}"
        )

    def test_bootstrap_non_json_does_not_leak_raw_escape_bytes(self, tmp_path):
        """
        RED: a REAL (non-symlinked) manifest with raw ESC bytes in its
        "version" field must not have those bytes reach bootstrap's stdout
        verbatim. Confirmed live (session 2026-07-05).
        """
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _write_manifest_version(manifest_path, _MALICIOUS_VERSION)

        rc, stdout, stderr = run_script(BOOTSTRAP, repo)

        assert _ESC not in stdout, (
            "BUG SEC-MED-NEW-08 (barrido, new site): git-memory-bootstrap.py "
            "printed the manifest's raw ANSI escape bytes to stdout "
            f"unsanitized.\nstdout (repr, first 500): {stdout[:500]!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
