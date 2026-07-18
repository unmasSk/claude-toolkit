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


# ── Direct extract_memory()/extract_glossary() helpers ─────────────────────
#
# Copied verbatim (same shape, not reinvented) from tests/test_crown.py's
# _extract_memory()/_extract_glossary() helpers: run a small inline Python
# snippet as a subprocess that monkeypatches git_helpers.run_git to point
# GIT_DIR/GIT_WORK_TREE at the temp repo, then calls the real function and
# prints its JSON-serialized return value. This gives a precise assertion on
# the actual (label, text, is_crown) tuples returned, instead of parsing
# rendered boot-log text.

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


def _extract_memory(repo):
    """Call extract_memory() from session-start-boot with the test repo as CWD."""
    code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import subprocess as _sp
import git_helpers as _gh

def _patched_run_git(args, cwd=None, **kwargs):
    env = dict(os.environ)
    env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    env['GIT_WORK_TREE'] = {repr(repo)}
    result = _sp.run(
        ['git'] + args,
        capture_output=True, text=True, encoding='utf-8', cwd={repr(repo)}, env=env,
    )
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import importlib, importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
boot.run_git = _patched_run_git  # type: ignore

import json
result = boot.extract_memory()

def _ser(lst):
    return [list(item) for item in lst]

print(json.dumps({{
    'pending':   result.get('pending', []),
    'decisions': _ser(result.get('decisions', [])),
    'memos':     _ser(result.get('memos', [])),
    'remembers': _ser(result.get('remembers', [])),
}}))
"""
    rc, stdout, stderr = run_cmd([sys.executable, "-c", code], repo, timeout=30)
    if rc != 0:
        raise RuntimeError(f"_extract_memory failed (rc={rc}): {stderr}")
    return json.loads(stdout)


def _extract_glossary(repo):
    """Call extract_glossary() from session-start-boot with the test repo as CWD."""
    code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import subprocess as _sp
import git_helpers as _gh

def _patched_run_git(args, cwd=None, **kwargs):
    env = dict(os.environ)
    env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    env['GIT_WORK_TREE'] = {repr(repo)}
    result = _sp.run(
        ['git'] + args,
        capture_output=True, text=True, encoding='utf-8', cwd={repr(repo)}, env=env,
    )
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import importlib, importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
boot.run_git = _patched_run_git  # type: ignore

import json
result = boot.extract_glossary()

def _ser(lst):
    return [list(item) for item in lst]

print(json.dumps({{
    'decisions': _ser(result.get('decisions', [])),
    'memos':     _ser(result.get('memos', [])),
    'remembers': _ser(result.get('remembers', [])),
}}))
"""
    rc, stdout, stderr = run_cmd([sys.executable, "-c", code], repo, timeout=30)
    if rc != 0:
        raise RuntimeError(f"_extract_glossary failed (rc={rc}): {stderr}")
    return json.loads(stdout)


def _make_repo_no_install(tmp_path, name="control-byte-repo"):
    """Minimal git repo, no installer run — extract_memory()/extract_glossary()
    only need a real git history, not the full installed layout.
    """
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


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
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        assert "head_sha" in cache
        assert "generated_at" in cache

    def test_cache_invalidated_on_head_change(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)  # creates cache
        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        with open(cache_path, encoding="utf-8") as f:
            cache_before = json.load(f)
        # Make a new commit to change HEAD
        git_cmd(["commit", "--allow-empty", "-m", "🧭 decision(db): use postgres\n\nDecision: postgres over mysql"], repo)
        run_boot(repo)  # should regenerate cache
        with open(cache_path, encoding="utf-8") as f:
            cache_after = json.load(f)
        assert cache_before["head_sha"] != cache_after["head_sha"]

    def test_cache_invalidated_on_ttl_expiry(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)  # creates cache
        cache_path = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        # Backdate the generated_at to simulate TTL expiry
        with open(cache_path, encoding="utf-8") as f:
            cache = json.load(f)
        from datetime import timedelta
        from datetime import datetime, timezone
        old_time = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
        cache["generated_at"] = old_time
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f)
        run_boot(repo)  # should regenerate
        with open(cache_path, encoding="utf-8") as f:
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
        with open(manifest_path, encoding="utf-8") as f:
            manifest = json.load(f)
        manifest["version"] = "1.0.0"
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        run_boot(repo)
        content = _read_boot_log(repo)
        assert "Plugin v" in content
        assert "installed: v1.0.0" in content


class TestMigrateUntrackedGeneratedJsons:
    """Boot should ensure .gitignore has the generated-JSON entries.

    Issue #63 (boot simplification, point 4):
    _migrate_untrack_generated_jsons() -- the "git rm --cached previously
    tracked generated JSONs" one-shot migration this class used to also
    cover -- is retired from the boot path outright (pre-v1.0.0, present
    since 037e0cb 2026-03-17, ~4 months of boots since; no other caller, no
    upgrade-path duplicate to fall back to, unlike _migrate_runtime_to_unmassk).
    Its own regression test (test_untrack_previously_committed_jsons) is
    removed for the same reason: the behavior it asserted no longer exists
    by design, not by accident. The gitignore-ensuring behavior below is
    unaffected -- it comes from lib/boot_glossary_cache.py and
    lib/boot_fetch_stamp.py's own independent ensure_gitignore() calls in
    the normal boot flow, never from the retired migration.
    """

    def test_gitignore_entries_added(self, tmp_path):
        """Boot's normal glossary/fetch flow ensures .gitignore has the entries."""
        repo = str(tmp_path / "repo")
        os.makedirs(repo)
        git_cmd(["init"], repo)
        git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
        run_script(INSTALL, repo, ["--auto"])

        # Remove gitignore entries to simulate old install
        gitignore_path = os.path.join(repo, ".gitignore")
        with open(gitignore_path, encoding="utf-8") as f:
            content = f.read()
        # Strip out the generated JSON lines
        lines = [l for l in content.splitlines()
                 if not any(j in l for j in [".glossary-cache", "git-memory-manifest"])]
        with open(gitignore_path, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        # Force-add a JSON so migration triggers
        fpath = os.path.join(repo, ".claude", ".unmassk", "glossary-cache.json")
        with open(fpath, "w", encoding="utf-8") as f:
            f.write("{}")
        git_cmd(["add", "-f", fpath], repo)
        git_cmd(["commit", "-m", "old tracked json"], repo)

        run_boot(repo)

        with open(gitignore_path, encoding="utf-8") as f:
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


def _run_boot_with_failing_log_write(repo):
    """Run the REAL hooks/session-start-boot.py main() with the real IO
    boundary write_boot_log() uses forced to raise OSError, WITHOUT relying
    on chmod-based permission simulation.

    Why not chmod: the original technique (`os.chmod(claude_dir, 0o500)`)
    only blocks the OWNER's own writes on POSIX; on Windows this does not
    restrict the owning process at all, so the write silently SUCCEEDS and
    the "prove the write genuinely failed" sanity check fails — the test
    never reaches the code path it claims to cover on that platform.

    Real seam forced instead: write_boot_log() (defined directly in
    session-start-boot.py) calls the module-level name
    `open_no_follow_symlink(candidate_log_path, "w")` — imported at module
    level (try/except ImportError fallback, see the file's own top) rather
    than looked up fresh from git_helpers at call time. So the fix here
    mirrors this project's own documented gotcha (see
    unmassk-toolkit-python-test-conventions.md, "patch the module that OWNS
    the function's __globals__"): after loading session-start-boot.py via
    spec_from_file_location (module name 'boot'), `boot.open_no_follow_symlink`
    IS the exact name write_boot_log() reads at call time (both are defined
    in/bound directly onto the same `boot` module object), so overwriting
    it there reaches the real function's real global lookup — no other
    dependency (git_helpers.run_git, ensure_runtime_dir, etc.) is touched,
    so every other part of main()'s real flow (branch/status/scopes/
    memory extraction) still runs unchanged.

    boot.main() itself calls sys.exit(0) at its end exactly like running
    the file directly would — this subprocess's rc/stdout/stderr are
    therefore identical in shape to run_boot()'s, just with the write
    seam forced to fail instead of chmod'd out from under it.

    Isolated in its own subprocess (same convention as _extract_memory()/
    _extract_glossary() above) so loading the hook under a throwaway module
    name never leaks into sys.modules for other tests in the same session.

    Returns (rc, stdout, stderr).
    """
    code = f"""
import sys, os
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)

def _raise_permission_error(path, mode="w", encoding="utf-8", **kwargs):
    raise PermissionError(f"[simulated write failure] cannot open {{path}} for {{mode!r}}")
boot.open_no_follow_symlink = _raise_permission_error

boot.main()
"""
    return run_cmd([sys.executable, "-c", code], repo, timeout=30)


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

    Cross-platform rewrite (Bex, enterprise-complete directive): replaced
    `os.chmod(claude_dir, 0o500)` (POSIX-only — does not block the owner's
    own writes on Windows) with _run_boot_with_failing_log_write(), which
    forces the real write_boot_log() -> open_no_follow_symlink() call to
    raise OSError directly. Same production code path, same assertions,
    now honest on every platform.
    """

    def test_full_text_printed_when_boot_log_write_fails(self, tmp_path):
        repo = make_repo_with_giant_commit_no_install(tmp_path)
        claude_dir = os.path.join(repo, ".claude")

        rc, output, stderr = _run_boot_with_failing_log_write(repo)

        # Sanity check: prove the log file genuinely was never created —
        # otherwise this test wouldn't be testing the failure path at all.
        assert not os.path.isfile(os.path.join(claude_dir, ".unmassk", "boot-log-latest.txt")), (
            "sanity check failed: boot-log-latest.txt should not exist — the "
            "write must genuinely have failed for this test to mean anything"
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


def _write_boot_log_with_surrogate(repo):
    """Call the REAL write_boot_log() (session-start-boot.py) directly with
    a `full_text` payload containing a lone surrogate (issue #54, T3) — the
    exact shape write_boot_log()'s own docstring says can arise from
    malformed git-log source data. write_boot_log() passes
    errors="backslashreplace" to open_no_follow_symlink() at its one real
    call site (hooks/session-start-boot.py:182); before that fix, the
    surrogate raised UnicodeEncodeError from inside the write, which is NOT
    caught by write_boot_log()'s `except OSError` — it would escape
    write_boot_log() entirely and crash main()/this subprocess with a
    non-zero exit and a UnicodeEncodeError traceback in stderr, instead of
    returning a path string.

    Isolated in its own subprocess (same convention as
    _render_banner_with_branch()/_run_boot_with_failing_log_write() above)
    so loading session-start-boot.py under a throwaway module name never
    leaks into sys.modules for other tests in the same pytest session.

    Returns (rc, stdout, stderr) — on success, stdout's last line is a JSON
    object {"boot_log_path": <str or null>}.
    """
    code = f"""
import sys, os, json
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)

full_text = "bad-\\udc80-surrogate in full_text"
boot_log_path = boot.write_boot_log(full_text, {repr(repo)})
print(json.dumps({{"boot_log_path": boot_log_path}}))
"""
    return run_cmd([sys.executable, "-c", code], repo, timeout=30)


class TestWriteBootLogSurrogateEscape:
    """Regression test for issue #54, T3: write_boot_log()'s one real call
    site passes errors="backslashreplace" (hooks/session-start-boot.py:182)
    specifically so a lone surrogate anywhere in the assembled `full_text`
    (git-derived memory content — commit trailers/subjects/bodies) cannot
    raise UnicodeEncodeError and escape the function uncaught. Before this
    fix, write_boot_log() returned None only for OSError (permissions, disk
    full) — a UnicodeEncodeError from the same write call was NOT an
    OSError, so it propagated straight out of write_boot_log() instead of
    being handled by its `except OSError: return None` fallback, crashing
    the whole boot hook.
    """

    def test_surrogate_in_full_text_returns_path_not_none(self, tmp_path):
        repo = _make_repo_no_install(tmp_path, name="surrogate-boot-log-repo")

        rc, stdout, stderr = _write_boot_log_with_surrogate(repo)

        assert rc == 0, (
            f"write_boot_log() must not let UnicodeEncodeError escape for a "
            f"lone-surrogate full_text — subprocess crashed instead "
            f"(rc={rc}):\nstdout={stdout}\nstderr={stderr}"
        )
        data = json.loads(stdout.strip().splitlines()[-1])
        assert data["boot_log_path"] is not None, (
            "write_boot_log() returned None (the OSError/failure branch) "
            "for a surrogate in full_text — it must succeed via "
            "errors='backslashreplace' and return the real log path"
        )
        assert os.path.isfile(data["boot_log_path"]), (
            "write_boot_log() returned a path but no file exists there — "
            "the write must have actually happened, not just been claimed"
        )


def _render_banner_with_branch(repo, fake_branch):
    """Drive the REAL production banner path — boot_git_checks.render_branch_section()
    (via its boot_render/session-start-boot.py re-export) and
    hooks/session-start-boot.py's own render_boot_banner_lines() — with an
    arbitrary branch-name STRING, without ever creating a real git ref for
    it.

    Why not `git checkout -b <name>`: some payloads worth testing here
    (very long names, names containing `<`/`>`) cannot exist as real git
    refs on Windows (MAX_PATH / NTFS-reserved-character rules reject them
    outright at ref-creation time), which would make the test fail at SETUP
    for a reason that has nothing to do with the banner code under test —
    the exact trap this rewrite avoids.

    The ONLY thing faked is the single `git branch --show-current` call
    inside boot_git_checks._resolve_sanitized_branch() — every other
    git_helpers.run_git() call this flow makes (status --porcelain,
    rev-parse @{u}, rev-list --left-right, doctor/repair subprocesses) still
    goes to the real git binary against the real repo, so ahead/behind,
    dirty-state, and the REAL sanitizer (parsing.sanitize_trailer_value,
    reached through _resolve_sanitized_branch()) all run completely
    unchanged from production. write_boot_log() is also called for real
    (against a throwaway string) so boot_log_path is a genuine return value,
    never a hand-computed path.

    Isolated in its own subprocess (same convention as _extract_memory()/
    _extract_glossary() above in this file) so loading session-start-boot.py
    under a throwaway module name never leaks into sys.modules for other
    tests in the same pytest session.

    Returns the joined banner text exactly as main() would print it to stdout.
    """
    code = f"""
import sys, os, json
sys.path.insert(0, {repr(LIB_DIR)})
sys.path.insert(0, {repr(HOOKS_DIR)})
os.chdir({repr(repo)})

import subprocess as _sp
import git_helpers as _gh

_FAKE_BRANCH = {fake_branch!r}

def _patched_run_git(args, cwd=None, **kwargs):
    if args[:2] == ["branch", "--show-current"]:
        return 0, _FAKE_BRANCH
    env = dict(os.environ)
    env['GIT_DIR'] = os.path.join({repr(repo)}, '.git')
    env['GIT_WORK_TREE'] = {repr(repo)}
    result = _sp.run(
        ['git'] + args,
        capture_output=True, text=True, encoding='utf-8', cwd={repr(repo)}, env=env,
    )
    return result.returncode, result.stdout.strip()
_gh.run_git = _patched_run_git

import importlib.util
spec = importlib.util.spec_from_file_location('boot', {repr(BOOT_HOOK)})
boot = importlib.util.module_from_spec(spec)
spec.loader.exec_module(boot)
# No `boot.run_git = _patched_run_git` here (unlike the sibling
# _extract_memory()/_extract_glossary() helpers above): this helper never
# calls boot.main(), only render_status_section()/render_branch_section()/
# render_boot_complete_section()/write_boot_log() directly, all of which
# resolve run_git via `from git_helpers import run_git` inside
# boot_git_checks.py at call time — so patching _gh.run_git above is the
# only patch that's load-bearing on this call path.

plugin_root = os.path.dirname(os.path.dirname(os.path.abspath({repr(BOOT_HOOK)}))).replace(os.sep, "/")

status_lines, status, status_detail = boot.render_status_section()
branch_result = boot.render_branch_section()
boot_complete_lines, commit_script, log_script = boot.render_boot_complete_section(plugin_root)
boot_log_path = boot.write_boot_log("probe content for banner test", {repr(repo)})

banner = boot.render_boot_banner_lines(
    plugin_root, status, status_detail, branch_result.branch, branch_result.ahead_behind,
    boot_log_path, commit_script, log_script,
    "", branch_result.pull_directive_lines,
)
print(json.dumps({{"banner": "\\n".join(banner)}}))
"""
    rc, stdout, stderr = run_cmd([sys.executable, "-c", code], repo, timeout=30)
    if rc != 0:
        raise RuntimeError(f"_render_banner_with_branch failed (rc={rc}): {stderr}")
    return json.loads(stdout.strip().splitlines()[-1])["banner"]


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

    Cross-platform rewrite (Bex, enterprise-complete directive): the
    original version created this name as a REAL git ref via `git checkout
    -b`, which fails on Windows (MAX_PATH) before the banner code is ever
    reached. Rewritten to drive render_boot_banner_lines() directly via
    _render_banner_with_branch() — same 491-char two-segment payload, same
    real sanitizer + banner code, no real ref ever created.
    """

    LONG_BRANCH_NAME = ("a" * 245) + "/" + ("b" * 245)

    def test_banner_stays_under_byte_budget_with_long_branch_name(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)

        output = _render_banner_with_branch(repo, self.LONG_BRANCH_NAME)
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


# ══════════════════════════════════════════════════════════════════════════
# Audit findings (Argus + Cerberus) — test-first contract, acceptance pass
# ══════════════════════════════════════════════════════════════════════════
#
# Integrity-only survivors of the original 6-finding audit batch. The four
# external-attacker-framed findings (SEC-CRIT-001 symlink write, SEC-CRIT-002
# scopes injection, SEC-HIGH-003 glossary injection, SEC-MED-004 Next/Blocker
# injection) were retired in #72 (adelgazamiento) — no external adversary in
# this project's threat model. The two that remain are self-inflicted-growth
# / robustness concerns, not attacker defenses:
#   - SEC-MED-005: crowned-entry count/length caps (unbounded boot-log growth
#     over a project's lifetime).
#   - SEC-LOW-006: boot-log file permissions (umask default).
#
# TestScopesRenderStaysSingleLine below restores, with pure integrity framing
# (#72 fix pass, Cerberus finding), coverage for the render_scopes_section()
# wiring the old SEC-CRIT-002 class exercised — direct byte-level coverage of
# sanitize_trailer_value() itself now lives in
# test_parsing_consolidation.py::TestSanitizeTrailerValueControlByteContract.


class TestScopesRenderStaysSingleLine:
    """render_scopes_section() (lib/boot_git_checks.py:527-546,
    _render_scope_entries()) sanitizes scope_name/description/children the
    same way Decision/Memo/Remember already are in extract_memory() — the
    wiring under test here, not the sanitizer's own byte contract (that
    lives in test_parsing_consolidation.py).

    Integrity concern, not attacker defense: git-memory-scopes.json is
    generated by Bilbo (an autonomous exploration agent). If a Bilbo run
    is interrupted mid-write or a scan produces malformed output, a
    description field can end up with an embedded raw newline plus stray
    leftover text. Left unsanitized, that raw newline breaks the "one line
    per scope" render contract and, in the worst case, produces a stray
    line that happens to collide with a real section terminator like
    "BOOT COMPLETE" purely by coincidence of corrupted content — nothing
    engineered, just a malformed write reaching the render step unfiltered.

    Correct behavior: scope_name/description/children are always
    sanitized, so a scope entry always renders as exactly one line, and
    corrupted content never produces a stray line colliding with a real
    section terminator.
    """

    def test_scope_description_with_embedded_newline_renders_as_single_line(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        scopes_path = os.path.join(repo, ".claude", "git-memory-scopes.json")
        corrupted_desc = (
            "normal desc\n\nBOOT COMPLETE\nstray leftover text from an interrupted scan"
        )
        scopes_data = {"scopes": {"auth": {"description": corrupted_desc, "children": {}}}}
        os.makedirs(os.path.dirname(scopes_path), exist_ok=True)
        with open(scopes_path, "w", encoding="utf-8") as f:
            json.dump(scopes_data, f)

        run_boot(repo)
        content = _read_boot_log(repo)

        stray_terminator_lines = [l for l in content.splitlines() if l.strip() == "BOOT COMPLETE"]
        assert stray_terminator_lines == [], (
            f"a raw newline inside a corrupted scope description produced a "
            f"standalone 'BOOT COMPLETE' line colliding with the real "
            f"terminator: {stray_terminator_lines}"
        )

        scope_lines = [l for l in content.splitlines() if l.startswith("  auth:")]
        assert len(scope_lines) == 1, (
            f"the scope entry must render as a single line (no embedded raw "
            f"newlines) even when the source description is corrupted — got "
            f"{len(scope_lines)} lines: {scope_lines}"
        )
        assert "normal desc" in scope_lines[0], (
            "sanitization must strip the newline/control content, not the "
            "legitimate description text alongside it"
        )


class TestCrownedEntriesHaveSensibleCaps:
    """SEC-MED-005: crowned Decision/Memo/Remember entries intentionally
    bypass MAX_DECISIONS/MAX_MEMOS/BOOT_MAX_REMEMBERS (see the "crowned
    entries bypass MAX_DECISIONS cap" comment in extract_memory()) — a
    crowned entry must never be evicted by a newer, non-crowned one within
    the normal budget. But nothing bounds the TOTAL number of DISTINCT
    crowned entries that can accumulate over a project's lifetime (one
    always-shown line per crowned scope, forever), and nothing bounds the
    length of a single crowned trailer value.

    Contract decided here (Dante, acceptance pass — exact numbers are a
    documented design choice for Ultron to implement against, not a
    pre-existing constant):
      - crowned entries still respect a sensible ceiling on TOTAL COUNT
        shown per section — this contract reuses the existing MAX_DECISIONS
        value (20) itself as that ceiling, rather than an unbounded separate
        lane alongside the normal budget.
      - a single crowned trailer VALUE is capped at 2000 characters — generous
        enough for a real crowned summary, small enough to bound a
        single-entry blowup growing the boot log without limit.

    [ROJO]: expected to fail against the current hook, which shows every
    crowned entry with no count cap and no per-value length cap.
    """

    CROWN_VALUE_MAX_LEN = 2000
    CROWN_COUNT_CAP = 20  # same ceiling as MAX_DECISIONS

    def test_crowned_decisions_count_is_capped(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        # MAX_DECISIONS is 20 — crown 5 more distinct scopes than that.
        for i in range(25):
            git_cmd(["commit", "--allow-empty", "-m",
                     f"🧭 decision(crownscope{i}): pick option {i}\n\n"
                     f"Decision: crowned canonical choice {i}\nCrown: Decision"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)

        start = content.find("DECISIONS:")
        end = content.find("\n\n", start)
        section_text = content[start:end] if end != -1 else content[start:]
        crowned_lines = [l for l in section_text.splitlines() if "👑" in l]

        assert len(crowned_lines) <= self.CROWN_COUNT_CAP, (
            f"crowned decisions must respect a sensible ceiling "
            f"({self.CROWN_COUNT_CAP}, same as MAX_DECISIONS) — got "
            f"{len(crowned_lines)} crowned lines with no cap applied"
        )

    def test_crowned_decision_value_length_is_capped(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        huge_value = "X" * 5000
        git_cmd(["commit", "--allow-empty", "-m",
                 f"🧭 decision(hugecrown): huge crowned value\n\n"
                 f"Decision: {huge_value}\nCrown: Decision"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)
        run = _longest_char_run(content, "X")

        assert run <= self.CROWN_VALUE_MAX_LEN, (
            f"a single crowned Decision trailer value must be capped at a "
            f"sensible max length ({self.CROWN_VALUE_MAX_LEN} chars) — got an "
            f"uncapped run of {run} 'X' characters in the boot log"
        )


class TestBootLogFilePermissions:
    """SEC-LOW-006: boot-log-latest.txt is written with plain
    open(path, "w"), inheriting the process umask (typically 0o644 on this
    system — world/group-readable). It can contain sensitive project
    memory (decisions, blockers, personal Remember notes). On a
    shared/multi-user machine this leaks that content to other local
    users. Correct behavior: the file must be created with restrictive
    permissions (no group/other access), not left to the umask default.

    [ROJO]: expected to fail against the current hook on any system with a
    default umask like 0o022.

    Windows (Bex, enterprise-complete directive): genuinely OS-specific,
    kept as an explicit skip, not rewritten. lib/git_helpers.py's
    open_no_follow_symlink() docstring (~line 135) already documents this
    as an accepted, deliberate decision: "0o600 on Windows does NOT deny
    group/other access the way it does on POSIX — a file created here
    inherits the ACL of its containing directory instead. That is a
    Windows filesystem semantic, not a bug in this function." Asserting
    POSIX mode bits against an NTFS file would either be dishonest (fake a
    result the filesystem cannot produce) or would test the wrong thing
    entirely (ACL inheritance, a different mechanism this test was never
    written to check). Skip is the honest outcome here, not laziness.
    """

    @pytest.mark.skipif(
        sys.platform == "win32",
        reason="0o600 POSIX mode bits are documented as POSIX-only in "
        "lib/git_helpers.py's open_no_follow_symlink() docstring — on "
        "Windows/NTFS a file inherits its containing directory's ACL "
        "instead, so asserting mode bits here would either fake a result "
        "NTFS cannot produce or test an unrelated mechanism (ACLs)",
    )
    def test_boot_log_file_has_restrictive_permissions(self, tmp_path):
        repo = make_repo_with_memory(tmp_path)
        run_boot(repo)
        mode = os.stat(_boot_log_path(repo)).st_mode & 0o777

        assert mode & 0o077 == 0, (
            f"boot-log-latest.txt must not be group/other-accessible — got "
            f"permissions {oct(mode)}. It can contain sensitive project "
            f"memory and must not rely on the process umask default"
        )


class TestBootLogWriteFailureLogsWarning:
    """CRB T2-2 (Cerberus): write_boot_log()'s `except OSError: return None`
    (hooks/session-start-boot.py, ~line 966) is the single most important
    failure path in the file — it's what triggers the inline-fallback branch
    already covered by TestBootLogWriteFailureFallback above — yet today it
    leaves zero trace. Confirmed live (session 2026-07-05): reproducing the
    write failure (chmod 0o500 on a fresh .claude before .unmassk exists,
    same technique as TestBootLogWriteFailureFallback) produces completely
    empty stderr.

    Correct behavior: when the boot-log write fails, a warning line
    identifying the failure (and the exception type) must reach stderr — not
    just silently falling back to inline printing (already covered by
    TestBootLogWriteFailureFallback; this test is about the missing trace,
    not the fallback behavior itself).

    [ROJO]: expected to fail against the current hook (stderr is empty).

    Cross-platform rewrite (Bex, enterprise-complete directive): replaced
    `os.chmod(claude_dir, 0o500)` (POSIX-only) with
    _run_boot_with_failing_log_write(), which forces the real
    write_boot_log() -> open_no_follow_symlink() call to raise OSError
    directly — see that helper's docstring (defined above, next to
    TestBootLogWriteFailureFallback) for why chmod cannot honestly
    reproduce this failure on Windows. Same production code path
    (write_boot_log()'s real `except OSError` branch), same assertions.
    """

    def test_boot_log_write_failure_logs_warning_to_stderr(self, tmp_path):
        repo = make_repo_with_giant_commit_no_install(tmp_path)
        claude_dir = os.path.join(repo, ".claude")

        rc, stdout, stderr = _run_boot_with_failing_log_write(repo)

        assert not os.path.isfile(os.path.join(claude_dir, ".unmassk", "boot-log-latest.txt")), (
            "sanity check failed: boot-log-latest.txt should not exist — the "
            "write must genuinely have failed for this test to mean anything"
        )
        assert "BOOT-WARNING" in stderr, (
            f"write_boot_log()'s except OSError branch must emit a trace to "
            f"stderr identifying the failure, so it is debuggable instead of "
            f"silent. stderr was: {stderr!r}"
        )
        assert "PermissionError" in stderr or "OSError" in stderr, (
            f"the stderr trace must include the exception type, not just a "
            f"generic message. stderr was: {stderr!r}"
        )
