"""
Tests for the structured boot briefing v2 output.

Validates section ordering, branch-awareness, scaling limits,
and the BOOT COMPLETE terminator.
"""

import json
import os
import re
import subprocess
import sys

import pytest

from conftest import (
    SOURCE_ROOT, HOOKS_DIR, INSTALL,
    run_cmd, git_cmd, write_file, run_script,
)

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")

# ── Stdout-truncation-fix contract (test-first, RED pass) ─────────────────
#
# Bug (House diagnosis): a context() commit subject of 1297 bytes, printed in
# full on the RESUME "Last:" line, plus the SCOPES section printed before it,
# exhausted the Claude Code harness's ~2KB stdout preview window before the
# "Next:" line (the most important instruction) was reached. Fix (Bex's
# design decision, not up for debate): stdout becomes a short banner; ALL
# real content (STATUS, BRANCH, SCOPES, RESUME with untruncated Last:/Next:,
# REMEMBER, DECISIONS, MEMOS, GC, CONSOLIDATE, TIMELINE) is written in full,
# with nothing capped, to a fixed-path file the hook controls:
# .claude/.unmassk/boot-log-latest.txt (this path follows the existing
# convention of .claude/.unmassk/ for all generated runtime files — see
# glossary-cache.json / manifest.json in git_helpers._GENERATED_JSONS, which
# already gitignores the whole directory, so no new .gitignore entry is
# needed).
#
# These markers are unique repeated-character runs (not real words) so a
# "longest contiguous run" check proves the payload was copied in full,
# rather than cut short — natural boot-log text never repeats one character
# thousands of times in a row.
LONG_SUBJECT_PAYLOAD = "Q" * 2200   # embedded directly in the commit subject
LONG_NEXT_MARKER = "Z" * 2100       # Next: trailer value
LONG_DECISION_MARKER = "D" * 2050   # Decision: trailer value
LONG_MEMO_MARKER = "M" * 2080       # Memo: trailer value
LONG_REMEMBER_MARKER = "R" * 2030   # Remember: trailer value

BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")
BOOT_LOG_REL_PATH = "/".join(BOOT_LOG_REL_PARTS)


def make_repo_with_giant_commit(tmp_path, name="giant-repo"):
    """Repo whose most recent commit is a context() commit with a 2000+ char
    subject and 2000+ char Next/Decision/Memo/Remember trailers — reproduces
    the real-world 1297-byte-subject truncation bug at a larger scale.
    """
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])

    subject = f"💾 context(giant): {LONG_SUBJECT_PAYLOAD}"
    body = (
        "Why: reproduces the stdout-truncation bug at a larger scale\n"
        f"Next: {LONG_NEXT_MARKER}\n"
        f"Decision: {LONG_DECISION_MARKER}\n"
        f"Memo: {LONG_MEMO_MARKER}\n"
        f"Remember: {LONG_REMEMBER_MARKER}\n"
    )
    git_cmd(["commit", "--allow-empty", "-m", subject + "\n\n" + body], repo)
    return repo


def _boot_log_path(repo):
    return os.path.join(repo, *BOOT_LOG_REL_PARTS)


def _read_boot_log(repo):
    with open(_boot_log_path(repo), encoding="utf-8") as f:
        return f.read()


def _longest_char_run(text, char):
    """Length of the longest contiguous run of `char` in `text`."""
    longest = 0
    current = 0
    for c in text:
        if c == char:
            current += 1
            longest = max(longest, current)
        else:
            current = 0
    return longest


def make_repo_with_memory(tmp_path, name="repo"):
    """Create a repo with install + some memory commits."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])

    # Add memory commits
    git_cmd(["commit", "--allow-empty", "-m",
             "🧭 decision(auth): use JWT\n\nDecision: JWT over sessions\nWhy: stateless API"], repo)
    git_cmd(["commit", "--allow-empty", "-m",
             "📌 memo(api): preference - async/await\n\nMemo: preference - async/await everywhere"], repo)
    git_cmd(["commit", "--allow-empty", "-m",
             "🧠 remember(user): prefers Spanish\n\nRemember: user - prefiere respuestas en español"], repo)
    git_cmd(["commit", "--allow-empty", "-m",
             "💾 context(auth): pause JWT implementation\n\nWhy: switching to urgent bugfix\nNext: finish JWT refresh token flow"], repo)
    return repo


def run_boot(repo):
    """Run the session-start-boot hook and return stdout."""
    rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo)
    return stdout


class TestBootSections:
    """Boot output has all required sections in correct order."""

    def test_has_status_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "STATUS:" in output

    def test_has_branch_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "BRANCH:" in output

    def test_has_resume_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "RESUME:" in output

    def test_has_remember_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "REMEMBER:" in output

    def test_has_decisions_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "DECISIONS:" in output

    def test_has_timeline_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "TIMELINE" in output

    def test_has_boot_complete_terminator(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "BOOT COMPLETE" in output
        assert "Do NOT run doctor or git-memory-log" in output

    def test_has_script_paths_in_terminator(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "git-memory-commit.py" in output
        assert "git-memory-log.py" in output

    def test_section_order(self, tmp_path):
        """Sections appear in the designed order: STATUS, BRANCH, RESUME, REMEMBER, DECISIONS, TIMELINE, BOOT COMPLETE."""
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        positions = []
        for marker in ["STATUS:", "BRANCH:", "RESUME:", "REMEMBER:", "DECISIONS:", "TIMELINE", "BOOT COMPLETE"]:
            pos = output.find(marker)
            assert pos != -1, f"Missing section: {marker}"
            positions.append(pos)
        assert positions == sorted(positions), f"Sections out of order: {positions}"

    def test_header_has_version(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "[git-memory-boot]" in output
        # Version should be in the first line
        first_line = output.split("\n")[0]
        assert re.search(r"v\d+\.\d+\.\d+", first_line)

    def test_resume_shows_next(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "finish JWT refresh token flow" in output

    def test_resume_shows_last_context(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "pause JWT implementation" in output


class TestBootTimeAgo:
    """Boot shows time since last session."""

    def test_last_commit_has_time_ago(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        # The RESUME section should show a time-ago like "Xm ago" or "just now"
        assert re.search(r"\d+[mhdw] ago|just now", output)


class TestBootBranchAwareness:
    """Branch-scoped items appear first in their sections."""

    def test_branch_scoped_next_first(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        # Create a branch with auth keyword
        git_cmd(["checkout", "-b", "feat/issue-42-auth-refactor"], repo)
        git_cmd(["commit", "--allow-empty", "-m",
                 "💾 context(api): pause API work\n\nWhy: context switch\nNext: add rate limiting to API"], repo)
        output = run_boot(repo)
        # The auth-related Next should appear BEFORE the API Next
        # because branch name contains "auth"
        auth_pos = output.find("JWT refresh token")
        api_pos = output.find("rate limiting")
        # Both should exist
        assert auth_pos != -1, "Branch-matching 'JWT refresh token' item missing from output"
        assert api_pos != -1, "Non-matching 'rate limiting' item missing from output"
        # Branch-matching items must appear before non-matching items
        assert auth_pos < api_pos, (
            f"Branch-matching item should appear before non-matching item: "
            f"auth_pos={auth_pos}, api_pos={api_pos}"
        )


class TestBootEmpty:
    """Boot handles empty repos gracefully."""

    def test_empty_repo(self, tmp_path):
        repo = str(tmp_path / "empty")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        output = run_boot(repo)
        assert "BOOT COMPLETE" in output
        assert "STATUS:" in output


class TestGlossaryCache:
    """Glossary caching creates, reads, and invalidates correctly."""

    def test_cache_created_on_first_boot(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        assert os.path.isfile(cache_path), "Glossary cache file should be created on first boot"
        with open(cache_path) as f:
            cache = json.load(f)
        assert "head_sha" in cache
        assert "generated_at" in cache

    def test_cache_invalidated_on_head_change(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)  # creates cache
        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        with open(cache_path) as f:
            cache_before = json.load(f)
        # Make a new commit to change HEAD
        git_cmd(["commit", "--allow-empty", "-m", "🧭 decision(db): use postgres\n\nDecision: postgres over mysql"], repo)
        run_boot(repo)  # should regenerate cache
        with open(cache_path) as f:
            cache_after = json.load(f)
        assert cache_before["head_sha"] != cache_after["head_sha"]

    def test_cache_invalidated_on_ttl_expiry(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)  # creates cache
        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        # Backdate the generated_at to simulate TTL expiry
        with open(cache_path) as f:
            cache = json.load(f)
        from datetime import timedelta
        from datetime import datetime, timezone
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        cache["generated_at"] = old_time
        with open(cache_path, "w") as f:
            json.dump(cache, f)
        run_boot(repo)  # should regenerate
        with open(cache_path) as f:
            refreshed = json.load(f)
        # generated_at should be recent, not the backdated time
        assert refreshed["generated_at"] != old_time


class TestVersionCheck:
    """Version mismatch detection works correctly."""

    def test_no_warning_when_versions_match(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        # STATUS should be ok with no version warning
        assert "Plugin v" not in output or "available" not in output

    def test_warning_when_versions_mismatch(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        # Tamper the manifest to have an old version
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["version"] = "1.0.0"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        output = run_boot(repo)
        assert "Plugin v" in output
        assert "installed: v1.0.0" in output


class TestMigrateUntrackedGeneratedJsons:
    """Boot should untrack generated JSONs left by older installs."""

    def test_untrack_previously_committed_jsons(self, tmp_path):
        """If generated JSONs are tracked, boot should git rm --cached them."""
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        run_script(INSTALL, repo, ["--auto"])

        # Simulate old install: force-add the generated JSONs to the index
        # .unmassk is a directory, so files go inside it
        unmassk_dir = os.path.join(repo, ".claude", ".unmassk")
        os.makedirs(unmassk_dir, exist_ok=True)
        generated_files = [
            os.path.join(".unmassk", "glossary-cache.json"),
            os.path.join(".unmassk", "manifest.json"),
        ]
        claude_dir = os.path.join(repo, ".claude")
        for rel_name in generated_files:
            fpath = os.path.join(claude_dir, rel_name)
            with open(fpath, "w") as f:
                f.write("{}")
            git_cmd(["add", "-f", fpath], repo)
        git_cmd(["commit", "-m", "old install committed jsons"], repo)

        # Verify they are tracked
        rc, out, _ = run_cmd(["git", "ls-files", ".claude/.unmassk/glossary-cache.json"], repo)
        assert "glossary-cache.json" in out

        # Run boot — should untrack them
        run_boot(repo)

        # Verify they are no longer tracked
        for rel_name in generated_files:
            rc, out, _ = run_cmd(["git", "ls-files", f".claude/{rel_name}"], repo)
            basename = os.path.basename(rel_name)
            assert basename not in out, f"{basename} should be untracked after boot"

    def test_gitignore_entries_added(self, tmp_path):
        """Boot migration should also ensure .gitignore has the entries."""
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        run_script(INSTALL, repo, ["--auto"])

        # Remove gitignore entries to simulate old install
        gitignore_path = os.path.join(repo, ".gitignore")
        with open(gitignore_path) as f:
            content = f.read()
        # Strip out the generated JSON lines
        lines = [l for l in content.splitlines()
                 if not any(j in l for j in [".glossary-cache", "git-memory-manifest"])]
        with open(gitignore_path, "w") as f:
            f.write("\n".join(lines) + "\n")

        # Force-add a JSON so migration triggers
        fpath = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        with open(fpath, "w") as f:
            f.write("{}")
        git_cmd(["add", "-f", fpath], repo)
        git_cmd(["commit", "-m", "old tracked json"], repo)

        run_boot(repo)

        with open(gitignore_path) as f:
            gitignore = f.read()
        assert ".claude/.unmassk/" in gitignore

    def test_no_error_when_already_clean(self, tmp_path):
        """Boot should not fail if JSONs are already untracked."""
        repo = make_repo_with_memory(tmp_path)
        # Just run boot — nothing to migrate, should not error
        output = run_boot(repo)
        assert "STATUS:" in output


class TestBootStdoutMinimalWithHeavyContent:
    """Acceptance contract: stdout must survive the harness's ~2KB preview
    window even when the underlying memory has a giant subject/trailers.

    [ROJO]: every test in this class fails against the current hook, which
    still prints STATUS/BRANCH/SCOPES/RESUME/REMEMBER/DECISIONS/MEMOS/TIMELINE
    inline and writes no file at all.
    """

    STDOUT_SAFE_BYTES = 1000  # comfortably under the harness's ~2KB preview window

    def test_stdout_stays_under_safe_byte_budget(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        size = len(output.encode("utf-8"))
        assert size < self.STDOUT_SAFE_BYTES, (
            f"stdout is {size} bytes, expected < {self.STDOUT_SAFE_BYTES} "
            "to survive the harness's preview-window truncation"
        )

    def test_stdout_excludes_heavy_sections(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        for heavy_marker in ["SCOPES:", "RESUME:", "REMEMBER:", "DECISIONS:", "MEMOS:", "TIMELINE"]:
            assert heavy_marker not in output, (
                f"stdout should not contain heavy section {heavy_marker!r} — "
                "it belongs only in the full boot-log file"
            )

    def test_stdout_points_to_full_log_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        assert BOOT_LOG_REL_PATH in output.replace(os.sep, "/"), (
            "stdout banner must reference the fixed-path full boot log file "
            f"({BOOT_LOG_REL_PATH})"
        )

    def test_stdout_instructs_to_read_the_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        assert re.search(r"(?i)\bread\b", output), (
            "stdout banner must clearly instruct Claude to read the full file"
        )


class TestBootLogFileFullContent:
    """The fixed-path boot-log file must contain everything, untruncated."""

    def test_log_file_created_on_boot(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        assert os.path.isfile(_boot_log_path(repo)), (
            f"expected boot log file at {_boot_log_path(repo)}"
        )

    def test_log_file_reflects_new_commits_on_each_boot(self, tmp_path):
        """File is regenerated (not written once and left stale)."""
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content_before = _read_boot_log(repo)
        assert "brand-new-marker-xyz" not in content_before

        git_cmd(["commit", "--allow-empty", "-m",
                 "🧭 decision(freshscope): brand-new-marker-xyz"], repo)
        run_boot(repo)
        content_after = _read_boot_log(repo)
        assert "brand-new-marker-xyz" in content_after, (
            "boot log file must be rewritten with the latest commit's memory on every boot"
        )

    def test_log_file_has_all_sections(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        for marker in ["STATUS:", "BRANCH:", "SCOPES:", "RESUME:",
                       "REMEMBER:", "DECISIONS:", "MEMOS:", "TIMELINE"]:
            assert marker in content, f"boot log file missing section {marker!r}"

    def test_log_file_has_last_and_next(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "Last:" in content
        assert "Next:" in content

    def test_long_subject_not_truncated_in_log_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        run = _longest_char_run(content, "Q")
        assert run == len(LONG_SUBJECT_PAYLOAD), (
            f"expected the full {len(LONG_SUBJECT_PAYLOAD)}-char subject payload "
            f"untruncated, found a run of only {run} 'Q' characters"
        )

    def test_long_next_not_truncated_in_log_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        run = _longest_char_run(content, "Z")
        assert run == len(LONG_NEXT_MARKER), (
            f"Next: trailer truncated — expected {len(LONG_NEXT_MARKER)} 'Z' chars, found {run}"
        )

    def test_long_decision_not_truncated_in_log_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        run = _longest_char_run(content, "D")
        assert run == len(LONG_DECISION_MARKER), (
            f"Decision: trailer truncated — expected {len(LONG_DECISION_MARKER)} 'D' chars, found {run}"
        )

    def test_long_memo_not_truncated_in_log_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        run = _longest_char_run(content, "M")
        assert run == len(LONG_MEMO_MARKER), (
            f"Memo: trailer truncated — expected {len(LONG_MEMO_MARKER)} 'M' chars, found {run}"
        )

    def test_long_remember_not_truncated_in_log_file(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        run = _longest_char_run(content, "R")
        assert run == len(LONG_REMEMBER_MARKER), (
            f"Remember: trailer truncated — expected {len(LONG_REMEMBER_MARKER)} 'R' chars, found {run}"
        )

    def test_long_subject_appears_untruncated_in_timeline(self, tmp_path):
        """TIMELINE lists the same giant commit — its subject must not be
        truncated there either (contract item 4)."""
        repo = make_repo_with_giant_commit(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        timeline_section = content[content.find("TIMELINE"):]
        run = _longest_char_run(timeline_section, "Q")
        assert run == len(LONG_SUBJECT_PAYLOAD), (
            "TIMELINE entry for the giant commit must show the full subject, not a cut version"
        )

    # NOTE: GC is intentionally not asserted here for "untruncated-ness" —
    # GC only ever prints aggregate counts (e.g. "12 memos detected"), never
    # raw commit text, so there is no payload for it to truncate. The
    # TIMELINE/REMEMBER/DECISIONS/MEMOS assertions above already cover every
    # section that carries raw long-form text from this commit.
