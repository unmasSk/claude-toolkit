"""
Tests for the structured boot briefing v2 output.

Validates section ordering, branch-awareness, scaling limits,
and the BOOT COMPLETE terminator.
"""

import json
import os
import re
import shutil
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
# CORRECTION (Bex, 2026-07-04): the first version of this contract made the
# banner CONDITIONAL on a byte threshold (STDOUT_FULL_INLINE_BUDGET_BYTES =
# 6000): print everything inline if the full briefing measured under that,
# else switch to the banner. Yoda found this measured the wrong thing — a
# repo with 25 ordinary scopes (nothing extreme) totalled only 3193 bytes
# (under the threshold), yet its `Next:` line landed at byte 2491, already
# past the harness's real ~2KB truncation point. Measuring total size never
# guarantees where `Next:` falls. Bex's ruling: there is no conditional.
# The banner is UNCONDITIONAL — every boot, any repo size, gets the short
# banner on stdout and the full untruncated content in the boot-log file.
# With no threshold to cross, this whole class of bug is impossible by
# construction. Tests below that used to construct a "giant commit" JUST to
# force the banner branch no longer need to — an ordinary small repo now
# proves the same thing.
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

# Contract correction (Bex, 2026-07-04): the stdout banner is UNCONDITIONAL —
# every boot, any repo size, prints this short banner and writes full content
# to the boot-log file. There is no byte-threshold branch left to cross.
# Single source for the "<1000 bytes" budget asserted across this file.
STDOUT_SAFE_BYTES = 1000


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


def make_repo_with_giant_commit_no_install(tmp_path, name="giant-repo-no-install"):
    """Same giant commit as make_repo_with_giant_commit(), but deliberately
    WITHOUT running the installer, so `.claude/.unmassk` does not exist yet.

    Used by the write-failure regression test below: we need the *creation*
    of `.claude/.unmassk` (i.e. the os.makedirs() call inside the hook) to be
    the thing that fails when `.claude` is made read-only — matching
    Cerberus's live repro exactly (chmod 0o500 on a fresh `.claude` before
    `.unmassk` exists).
    """
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)

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
    """Boot output always splits in two: a short stdout banner (STATUS,
    BRANCH, the pointer message, BOOT COMPLETE terminator) and a full
    boot-log file with every section, untruncated. RESUME/REMEMBER/
    DECISIONS/TIMELINE never print inline anymore — for ANY repo, not just
    large ones — so those are asserted against the file, not stdout.

    [ROJO]: the file-based assertions below fail against the current hook,
    which still prints the full briefing inline for small/normal repos
    (STDOUT_FULL_INLINE_BUDGET_BYTES conditional) instead of writing it to
    the boot-log file unconditionally.
    """

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
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "RESUME:" in content

    def test_has_remember_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "REMEMBER:" in content

    def test_has_decisions_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "DECISIONS:" in content

    def test_has_timeline_section(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "TIMELINE" in content

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

    def test_section_order_in_stdout_banner(self, tmp_path):
        """The stdout banner keeps STATUS, BRANCH, BOOT COMPLETE in order."""
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        positions = []
        for marker in ["STATUS:", "BRANCH:", "BOOT COMPLETE"]:
            pos = output.find(marker)
            assert pos != -1, f"Missing banner section: {marker}"
            positions.append(pos)
        assert positions == sorted(positions), f"Banner sections out of order: {positions}"

    def test_section_order_in_log_file(self, tmp_path):
        """The full boot-log file keeps the designed section order: STATUS,
        BRANCH, RESUME, REMEMBER, DECISIONS, TIMELINE, BOOT COMPLETE."""
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        positions = []
        for marker in ["STATUS:", "BRANCH:", "RESUME:", "REMEMBER:", "DECISIONS:", "TIMELINE", "BOOT COMPLETE"]:
            pos = content.find(marker)
            assert pos != -1, f"Missing section in log file: {marker}"
            positions.append(pos)
        assert positions == sorted(positions), f"Sections out of order in log file: {positions}"

    def test_header_has_version(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert "[git-memory-boot]" in output
        # Version should be in the first line
        first_line = output.split("\n")[0]
        assert re.search(r"v\d+\.\d+\.\d+", first_line)

    def test_resume_shows_next(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "finish JWT refresh token flow" in content

    def test_resume_shows_last_context(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "pause JWT implementation" in content


class TestBootTimeAgo:
    """Boot shows time since last session — the time-ago string lives in the
    RESUME section, which is no longer printed inline (any repo size), so it
    is asserted against the full boot-log file."""

    def test_last_commit_has_time_ago(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        # The RESUME section should show a time-ago like "Xm ago" or "just now"
        assert re.search(r"\d+[mhdw] ago|just now", content)


class TestBootBranchAwareness:
    """Branch-scoped items appear first in their sections — verified in the
    full boot-log file, since RESUME/Next items are no longer printed inline
    (any repo size)."""

    def test_branch_scoped_next_first(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        # Create a branch with auth keyword
        git_cmd(["checkout", "-b", "feat/issue-42-auth-refactor"], repo)
        git_cmd(["commit", "--allow-empty", "-m",
                 "💾 context(api): pause API work\n\nWhy: context switch\nNext: add rate limiting to API"], repo)
        run_boot(repo)
        content = _read_boot_log(repo)
        # The auth-related Next should appear BEFORE the API Next
        # because branch name contains "auth"
        auth_pos = content.find("JWT refresh token")
        api_pos = content.find("rate limiting")
        # Both should exist
        assert auth_pos != -1, "Branch-matching 'JWT refresh token' item missing from log file"
        assert api_pos != -1, "Non-matching 'rate limiting' item missing from log file"
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
    """Version mismatch detection works correctly. The version warning is a
    STATUS sub-line, which — like the rest of STATUS detail beyond the bare
    `STATUS: ok` line — is not guaranteed to fit in the minimal stdout
    banner, so it is asserted against the full boot-log file, which always
    carries the complete STATUS section untruncated."""

    def test_no_warning_when_versions_match(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        content = _read_boot_log(repo)
        # STATUS should be ok with no version warning
        assert "Plugin v" not in content or "available" not in content

    def test_warning_when_versions_mismatch(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        # Tamper the manifest to have an old version
        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        with open(manifest_path) as f:
            manifest = json.load(f)
        manifest["version"] = "1.0.0"
        with open(manifest_path, "w") as f:
            json.dump(manifest, f)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "Plugin v" in content
        assert "installed: v1.0.0" in content


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


class TestBootStdoutAlwaysMinimal:
    """Acceptance contract (corrected, Bex 2026-07-04): the stdout banner is
    UNCONDITIONAL. Every boot — normal small repo or one with a giant
    subject/trailers — must survive the harness's ~2KB preview window, print
    only the short banner, and write the full untruncated briefing to the
    boot-log file. There is no byte threshold left to cross, so each check
    below is proven twice: once on an ordinary small repo (the case that a
    conditional-threshold design would have gotten wrong, per Yoda's
    25-scopes/3193-bytes finding) and once on the original giant-commit
    reproduction (making sure removing the threshold didn't regress the
    extreme case).

    [ROJO]: every test in this class fails against the current hook, which
    still gates the banner behind STDOUT_FULL_INLINE_BUDGET_BYTES and prints
    STATUS/BRANCH/SCOPES/RESUME/REMEMBER/DECISIONS/MEMOS/TIMELINE inline for
    anything under that threshold — including a normal small repo.
    """

    def test_stdout_stays_under_safe_byte_budget_for_normal_repo(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        size = len(output.encode("utf-8"))
        assert size < STDOUT_SAFE_BYTES, (
            f"stdout is {size} bytes for a normal repo (no giant commit), "
            f"expected < {STDOUT_SAFE_BYTES} — the banner must be "
            "unconditional, not gated behind a byte threshold"
        )

    def test_stdout_excludes_heavy_sections_for_normal_repo(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        for heavy_marker in ["SCOPES:", "RESUME:", "REMEMBER:", "DECISIONS:", "MEMOS:", "TIMELINE"]:
            assert heavy_marker not in output, (
                f"stdout should never contain heavy section {heavy_marker!r}, "
                "regardless of repo size — it belongs only in the full boot-log file"
            )

    def test_stdout_points_to_full_log_file_for_normal_repo(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert BOOT_LOG_REL_PATH in output.replace(os.sep, "/"), (
            "stdout banner must reference the fixed-path full boot log file "
            f"({BOOT_LOG_REL_PATH}) even for a small, everyday repo"
        )

    def test_stdout_instructs_to_read_the_file_for_normal_repo(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        output = run_boot(repo)
        assert re.search(r"(?i)\bread\b", output), (
            "stdout banner must clearly instruct Claude to read the full file"
        )

    def test_stdout_stays_under_safe_byte_budget_with_giant_commit(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        size = len(output.encode("utf-8"))
        assert size < STDOUT_SAFE_BYTES, (
            f"stdout is {size} bytes, expected < {STDOUT_SAFE_BYTES} "
            "to survive the harness's preview-window truncation"
        )

    def test_stdout_excludes_heavy_sections_with_giant_commit(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        for heavy_marker in ["SCOPES:", "RESUME:", "REMEMBER:", "DECISIONS:", "MEMOS:", "TIMELINE"]:
            assert heavy_marker not in output, (
                f"stdout should not contain heavy section {heavy_marker!r} — "
                "it belongs only in the full boot-log file"
            )

    def test_stdout_points_to_full_log_file_with_giant_commit(self, tmp_path):
        repo = make_repo_with_giant_commit(tmp_path)
        output = run_boot(repo)
        assert BOOT_LOG_REL_PATH in output.replace(os.sep, "/"), (
            "stdout banner must reference the fixed-path full boot log file "
            f"({BOOT_LOG_REL_PATH})"
        )

    def test_stdout_instructs_to_read_the_file_with_giant_commit(self, tmp_path):
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


class TestBootLogWriteFailureFallback:
    """Regression test for a Cerberus-confirmed gap (BLOQUEANTE): the hook
    assigns `boot_log_path` to a real path string BEFORE the try/except that
    attempts the actual write. If the write fails (permissions, disk full —
    Cerberus reproduced with `chmod 500` on `.claude` before `.unmassk`
    exists, so the `os.makedirs()` call itself raises PermissionError), the
    variable is still truthy, so the hook falls into the "heavy case" branch
    and prints the short banner pointing at a file that was NEVER written.

    This reproduces the exact original bug (losing the Next:/content on the
    failure path) that the stdout-truncation fix exists to prevent.

    Correct behavior (what this test enforces): when the log write fails,
    the hook must fall back to printing the full inline `full_text` —
    regardless of repo size — never a banner that references a file that
    doesn't exist. This is unchanged by the removal of
    STDOUT_FULL_INLINE_BUDGET_BYTES: the write-failure fallback was never
    about a byte threshold, it is about the write itself succeeding or not.
    The giant commit here is still used only so the Z-marker run-length
    gives an unambiguous, hard-to-fake proof that the FULL content survived
    (not because it's needed to force any particular stdout mode).
    """

    def test_full_text_printed_when_boot_log_write_fails(self, tmp_path):
        repo = make_repo_with_giant_commit_no_install(tmp_path)
        claude_dir = os.path.join(repo, ".claude")
        os.makedirs(claude_dir, exist_ok=True)
        os.chmod(claude_dir, 0o500)  # simulate write failure (permissions/disk full)
        try:
            output = run_boot(repo)
        finally:
            # Restore write permission before tmp_path's teardown tries to
            # remove the directory tree, or the test leaves garbage on disk.
            os.chmod(claude_dir, 0o700)

        # Sanity check: prove the log file genuinely was never created —
        # otherwise this test wouldn't be testing the failure path at all.
        assert not os.path.isdir(os.path.join(claude_dir, ".unmassk")), (
            "sanity check failed: .unmassk should not exist — the write "
            "must genuinely have failed for this test to mean anything"
        )

        # Today's bug: stdout is the short banner, and it references a boot
        # log file path that was never written.
        assert BOOT_LOG_REL_PATH not in output.replace(os.sep, "/"), (
            "stdout must not point Claude at a boot log file that was never "
            "successfully written — when the write fails, fall back to "
            "printing the full text inline instead of the short banner"
        )

        # Correct behavior: the full inline text (same as the "fits under
        # budget" branch) must be printed, so the Next: content survives.
        run = _longest_char_run(output, "Z")
        assert run == len(LONG_NEXT_MARKER), (
            "when the boot log file write fails, stdout must contain the "
            f"full inline briefing (expected {len(LONG_NEXT_MARKER)} 'Z' "
            f"chars from the Next: trailer, found a run of only {run}) — "
            "printing the short banner here silently loses this content, "
            "exactly the bug this fix exists to prevent"
        )


class TestBannerByteBudgetWithLongBranchName:
    """Non-blocking gap (Cerberus): the banner's <1000-byte budget assumes
    branch names are "usually short", but nothing in the code caps the
    branch name length before it's embedded verbatim in the `BRANCH:` line.
    Git allows path-segment branch names well beyond what a "short" name
    implies, and a long branch name alone can push the banner past its
    1000-byte budget.

    Simplification (contract correction, Bex 2026-07-04): the banner is now
    unconditional, so an ordinary small repo (make_repo_with_memory) already
    reaches the banner path — a giant commit is no longer needed just to
    force banner mode before testing the branch-name edge case.

    Uses a two-segment branch name (each segment under the filesystem's
    per-component name-length ceiling, so `git checkout -b` itself succeeds)
    for a total length of ~491 characters — comfortably over "~200+".
    """

    LONG_BRANCH_NAME = ("a" * 245) + "/" + ("b" * 245)

    def test_banner_stays_under_byte_budget_with_long_branch_name(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        rc, _, err = git_cmd(["checkout", "-b", self.LONG_BRANCH_NAME], repo)
        assert rc == 0, f"test setup failed: could not create long branch name: {err}"

        output = run_boot(repo)
        size = len(output.encode("utf-8"))
        assert size < STDOUT_SAFE_BYTES, (
            f"banner is {size} bytes with a {len(self.LONG_BRANCH_NAME)}-char "
            f"branch name, expected < {STDOUT_SAFE_BYTES} to stay within the "
            "contract's stdout safety budget — the branch name must be "
            "bounded before being embedded in the banner"
        )


class TestNoByteThresholdRegression:
    """Regression (Yoda): the FIRST version of this fix used a conditional
    (STDOUT_FULL_INLINE_BUDGET_BYTES = 6000, measuring TOTAL briefing size)
    to decide between printing everything inline vs. switching to the
    banner. Yoda found a repo with 25 ordinary scopes — nothing extreme,
    just a normal amount of accumulated decisions — whose full briefing
    totalled only 3193 bytes (comfortably under the 6000-byte threshold, so
    it still printed everything inline), yet its `Next:` line landed at
    byte 2491 — already past the harness's real ~2KB stdout truncation
    point. Measuring total size never guarantees where `Next:` falls, so
    that threshold left the exact same bug reachable with unremarkable
    input.

    Bex's ruling: remove the conditional entirely. There is no threshold to
    measure against, so this class of bug cannot recur by construction —
    this test is the direct proof, reproducing the same shape (many
    ordinary scopes, nothing extreme) rather than the giant-single-commit
    reproduction used elsewhere in this file.

    [ROJO]: fails against the current hook, which still has
    STDOUT_FULL_INLINE_BUDGET_BYTES and would print this repo's briefing
    fully inline (it measures under 6000 bytes).
    """

    def test_normal_repo_with_25_scopes_still_gets_banner(self, tmp_path):
        repo = str(tmp_path / "twentyfive-scopes-repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        run_script(INSTALL, repo, ["--auto"])

        # 25 ordinary decision commits across distinct scopes — realistic
        # content, nothing extreme, reproducing Yoda's exact finding shape.
        for i in range(25):
            git_cmd(["commit", "--allow-empty", "-m",
                     f"🧭 decision(scope{i}): pick option {i}\n\n"
                     f"Decision: use approach {i} for this scope"], repo)
        # The actual Next: instruction this session cares about.
        git_cmd(["commit", "--allow-empty", "-m",
                 "💾 context(final): pause work\n\nWhy: context switch\n"
                 "Next: ship the release notes"], repo)

        output = run_boot(repo)
        size = len(output.encode("utf-8"))
        assert size < STDOUT_SAFE_BYTES, (
            f"stdout is {size} bytes for a repo with 25 ordinary scopes — "
            "expected the short banner regardless, since there is no byte "
            "threshold left to cross"
        )
        assert "Next:" not in output, (
            "Next: must never appear inline — it belongs only in the full "
            "boot-log file, regardless of the total briefing size"
        )
        content = _read_boot_log(repo)
        assert "ship the release notes" in content, (
            "the Next: instruction must survive in full in the boot-log file"
        )
