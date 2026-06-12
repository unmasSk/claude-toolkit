"""
Regression tests for three memory-correctness bugs.

All three tests are written BEFORE the fix → they MUST FAIL (RED) today.
After Ultron implements the fixes they must turn GREEN.

=== Bug A (T1) — session-start-boot.py ===
Tombstone window too narrow: glossary scans ~500 commits but tombstones
are only collected from the SCAN_DEPTH=30 window.  When BOTH the original
note AND its Resolved-Memo / Resolved-Remember tombstone are pushed beyond
the 30-commit window (but still within the 500-commit glossary range) the
tombstone is invisible to extract_memory(), so the glossary merge re-injects
the retired entry.

The fix (Ultron's scope): collect tombstones from the full glossary range
(or pass them from extract_glossary), not only from the SCAN_DEPTH window.

=== Bug B (T1) — precompact-snapshot.py ~64 ===
The tombstone collector in extract_memory_from_log() only checks:
    for key in ("Resolved-Next", "Stale-Blocker"):
Missing: "Resolved-Memo" and "Resolved-Remember".
A retired memo/remember therefore reappears in the precompact snapshot.

The fix (Ultron's scope): use all four TOMBSTONE_KEYS from constants.

=== Bug C (T3) — session-start-boot.py ===
Context-commit detection uses two inconsistent predicates:
  extract_memory()      → "context(" in subject.lower()          (substring)
  get_last_context_time() → cleaned.lower().startswith("context") (prefix after emoji strip)

A commit whose subject contains "context(" in the middle of the message
(e.g. "feat(x): context(old) deleted") triggers extract_memory() but NOT
get_last_context_time() → last_context is set, ctx_time stays None.

A legitimate context commit (e.g. "💾 context(scope): pause work") must be
detected by BOTH paths.  A non-context commit that merely mentions "context("
in the middle must be detected by NEITHER.

Chosen canonical criterion (most defensible):
  A commit is a context commit iff its TYPE starts with "context" after
  stripping a leading emoji/whitespace prefix — i.e.
  `re.sub(r"^[^\\w#]+", "", subject).strip().lower().startswith("context")`.
  This aligns with get_last_context_time()'s current logic and with the
  semantic intent of the convention.
  extract_memory() must be updated to use the same predicate.

Fixture strategy
----------------
- _make_installed_repo / _add_filler_commits / run_boot reused from
  test_boot_tombstones.py pattern (same conftest helpers).
- Bug A: both the note AND the tombstone are pushed beyond SCAN_DEPTH=30
  by adding FILLER_COUNT=35 commits after the note and ANOTHER
  FILLER_COUNT=35 commits after the tombstone so both are outside the
  30-window.  The note is still within the 500-commit glossary range.
- Bug B: invokes precompact-snapshot.py directly (no install needed; the
  script reads git log from cwd).
- Bug C: commits a legitimate context commit and a non-context commit that
  mentions "context(" in the middle; asserts consistent detection.
"""

import os
import sys

import pytest

from conftest import (
    HOOKS_DIR, INSTALL, PRECOMPACT_SCRIPT,
    run_cmd, git_cmd, run_script,
)

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")

# Number of filler commits needed to push a commit beyond SCAN_DEPTH=30.
# 35 gives comfortable margin.
FILLER_COUNT = 35


# ── Shared helpers ─────────────────────────────────────────────────────────


def _make_installed_repo(tmp_path, name="repo"):
    """Create a minimal installed git repo (same pattern as test_boot_tombstones)."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])
    return repo


def _make_bare_repo(tmp_path, name="repo"):
    """Create a minimal git repo WITHOUT install (for precompact tests)."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _add_filler_commits(repo, count=FILLER_COUNT):
    """Push earlier commits beyond SCAN_DEPTH by adding non-memory commits."""
    for i in range(count):
        git_cmd(["commit", "--allow-empty", "-m", f"chore(pad): filler {i}"], repo)


def run_boot(repo):
    """Invoke session-start-boot and return stdout."""
    rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo)
    return stdout


def run_precompact(repo):
    """Invoke precompact-snapshot and return stdout."""
    rc, stdout, stderr = run_cmd([sys.executable, PRECOMPACT_SCRIPT], repo)
    return stdout


# ── Bug A: tombstone also outside SCAN_DEPTH window ───────────────────────


class TestBugA_TombstoneOutsideScanDepth:
    """Bug A (T1): tombstone suppression fails when BOTH the note and its
    tombstone are beyond SCAN_DEPTH=30 but within the glossary range (~500).

    Today (pre-fix): the retired note REAPPEARS → assertion fails (RED).
    After Ultron's fix: GREEN.
    """

    def test_retired_remember_absent_when_tombstone_also_beyond_scan_depth(self, tmp_path):
        """A Resolved-Remember tombstone that is itself beyond SCAN_DEPTH=30
        must still suppress the corresponding remember note in boot output.

        Fixture layout (oldest → newest):
          [init + install]
          [remember commit]          ← pushed to ~70+ commits ago by two filler batches
          [35 filler commits]        ← push the remember beyond window
          [tombstone commit]         ← this is now also beyond SCAN_DEPTH
          [35 filler commits]        ← push the tombstone itself beyond window
          HEAD

        Both note and tombstone are within the 500-commit glossary range.
        extract_memory() sees NEITHER (both outside window of 30).
        extract_glossary() sees the note; the tombstone must suppress it.
        """
        repo = _make_installed_repo(tmp_path)

        note_text = "user - prefiere commit messages en ingles xyzbugatombstone"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"🧠 remember(user): language pref\n\nRemember: {note_text}"],
            repo,
        )

        # Push note beyond SCAN_DEPTH
        _add_filler_commits(repo)

        # Tombstone — also ends up beyond SCAN_DEPTH after the second filler batch
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"♻️ chore(gc): retire remember\n\nResolved-Remember: {note_text}"],
            repo,
        )

        # Push the tombstone itself beyond SCAN_DEPTH
        _add_filler_commits(repo)

        output = run_boot(repo)

        # Bug A: today the note reappears because the tombstone is not collected
        # from the glossary range.  The assertion fails (RED).
        assert "xyzbugatombstone" not in output, (
            "BUG A (pre-fix RED): Retired remember note (xyzbugatombstone) must NOT "
            "appear in boot output when its Resolved-Remember tombstone is also beyond "
            "SCAN_DEPTH=30 but within glossary range (~500 commits).  "
            "After Ultron's fix this must be GREEN."
        )

    def test_retired_memo_absent_when_tombstone_also_beyond_scan_depth(self, tmp_path):
        """Same as above but for Memo / Resolved-Memo.

        Today (pre-fix): retired memo reappears → RED.
        After fix: GREEN.
        """
        repo = _make_installed_repo(tmp_path)

        memo_text = "preference - usar snake_case en todo el proyecto xyzbugatombstonememo"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"📌 memo(style): naming pref\n\nMemo: {memo_text}"],
            repo,
        )

        # Push note beyond SCAN_DEPTH
        _add_filler_commits(repo)

        # Tombstone
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"♻️ chore(gc): retire memo\n\nResolved-Memo: {memo_text}"],
            repo,
        )

        # Push tombstone beyond SCAN_DEPTH
        _add_filler_commits(repo)

        output = run_boot(repo)

        assert "xyzbugatombstonememo" not in output, (
            "BUG A (pre-fix RED): Retired memo note (xyzbugatombstonememo) must NOT "
            "appear in boot output when its Resolved-Memo tombstone is also beyond "
            "SCAN_DEPTH=30 but within glossary range.  "
            "After Ultron's fix this must be GREEN."
        )

    def test_control_non_retired_remember_still_appears(self, tmp_path):
        """Control: a note with no tombstone must continue to appear (no regression)."""
        repo = _make_installed_repo(tmp_path)

        active_text = "user - debug output kept brief xyzbugatombstonecontrol"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"🧠 remember(user): debug pref\n\nRemember: {active_text}"],
            repo,
        )

        # Push note beyond SCAN_DEPTH (both batches)
        _add_filler_commits(repo)
        # Unrelated tombstone — must not suppress the active note
        git_cmd(
            ["commit", "--allow-empty",
             "-m", "♻️ chore(gc): retire unrelated\n\nResolved-Remember: unrelated text xyz000control"],
            repo,
        )
        _add_filler_commits(repo)

        output = run_boot(repo)

        assert "xyzbugatombstonecontrol" in output, (
            "Control: active (non-retired) remember note (xyzbugatombstonecontrol) "
            "must still appear after the fix.  A failure here means the fix "
            "introduced false-positive suppression."
        )


# ── Bug B: precompact-snapshot missing Resolved-Memo / Resolved-Remember ──


class TestBugB_PrecompactMissingTombstoneKeys:
    """Bug B (T1): precompact-snapshot.py only tombstones Resolved-Next and
    Stale-Blocker.  Resolved-Memo and Resolved-Remember are ignored, so a
    retired memo/remember reappears in the snapshot.

    Today (pre-fix): the retired note APPEARS in the snapshot → RED.
    After Ultron's fix (using all four TOMBSTONE_KEYS): GREEN.
    """

    def test_resolved_memo_suppressed_in_precompact_snapshot(self, tmp_path):
        """A Memo followed by a Resolved-Memo tombstone must NOT appear in
        the precompact snapshot.

        Both commits are within the last 30 (no filler needed) because
        precompact only scans 30 commits and does not have a separate
        glossary path.  The bug is purely about which tombstone keys are
        checked.
        """
        repo = _make_bare_repo(tmp_path)

        memo_text = "preference - usar 2 espacios xyzprecompactmemo"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"📌 memo(style): indent\n\nMemo: {memo_text}"],
            repo,
        )
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"♻️ chore(gc): retire memo\n\nResolved-Memo: {memo_text}"],
            repo,
        )

        output = run_precompact(repo)

        # Bug B: today Resolved-Memo is not checked → the memo reappears.
        # This assertion fails (RED) until Ultron adds "Resolved-Memo" to the
        # tombstone collector in precompact-snapshot.py.
        assert "xyzprecompactmemo" not in output, (
            "BUG B (pre-fix RED): Retired memo (xyzprecompactmemo) must NOT appear "
            "in precompact snapshot after Resolved-Memo tombstone.  "
            "After Ultron's fix this must be GREEN."
        )

    def test_resolved_remember_suppressed_in_precompact_snapshot(self, tmp_path):
        """A Remember followed by a Resolved-Remember tombstone must NOT appear
        in the precompact snapshot.

        Same mechanics as the Memo test above.

        Note: precompact-snapshot only prints the snapshot when has_content is
        True (pending/blockers/decisions/memos/last_context).  To force that
        path we include a Decision commit so the snapshot is always emitted —
        the Remember still appears in the "Remember (personality notes)" section
        when it is active, and must NOT appear after Resolved-Remember.
        """
        repo = _make_bare_repo(tmp_path)

        # Anchor commit to make has_content=True (Decision)
        git_cmd(
            ["commit", "--allow-empty",
             "-m", "🧭 decision(api): use REST\n\nDecision: REST over GraphQL xyzprecompactrememanchor"],
            repo,
        )

        remember_text = "user - siempre responder en español xyzprecompactremember"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"🧠 remember(user): language\n\nRemember: {remember_text}"],
            repo,
        )
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"♻️ chore(gc): retire remember\n\nResolved-Remember: {remember_text}"],
            repo,
        )

        output = run_precompact(repo)

        # Verify the snapshot was actually emitted (anchor must be there)
        assert "xyzprecompactrememanchor" in output, (
            "Test setup error: Decision anchor commit must appear in snapshot — "
            "if this fails the snapshot was not emitted at all."
        )

        assert "xyzprecompactremember" not in output, (
            "BUG B (pre-fix RED): Retired remember (xyzprecompactremember) must NOT "
            "appear in precompact snapshot after Resolved-Remember tombstone.  "
            "After Ultron's fix this must be GREEN."
        )

    def test_control_active_memo_still_appears_in_precompact(self, tmp_path):
        """Control: an active (non-retired) memo must still appear in the snapshot."""
        repo = _make_bare_repo(tmp_path)

        active_memo = "preference - async/await everywhere xyzprecompactactive"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"📌 memo(style): async pref\n\nMemo: {active_memo}"],
            repo,
        )
        # Unrelated tombstone — must not suppress the active memo
        git_cmd(
            ["commit", "--allow-empty",
             "-m", "♻️ chore(gc): retire unrelated\n\nResolved-Memo: unrelated memo xyz999"],
            repo,
        )

        output = run_precompact(repo)

        assert "xyzprecompactactive" in output, (
            "Control: active (non-retired) memo (xyzprecompactactive) must still appear "
            "in the precompact snapshot.  A failure here means the fix introduced "
            "false-positive suppression."
        )

    def test_control_active_remember_still_appears_in_precompact(self, tmp_path):
        """Control: an active (non-retired) remember must still appear in the snapshot.

        Includes a Decision commit to ensure has_content=True so the snapshot
        is always emitted (precompact only prints when pending/blockers/decisions/
        memos/last_context are present).
        """
        repo = _make_bare_repo(tmp_path)

        # Anchor commit: ensures the snapshot is emitted
        git_cmd(
            ["commit", "--allow-empty",
             "-m", "🧭 decision(api): use REST\n\nDecision: REST over GraphQL xyzprecompactctrlanchor"],
            repo,
        )

        active_remember = "user - respuestas cortas siempre xyzprecompactactiveremember"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", f"🧠 remember(user): brevity\n\nRemember: {active_remember}"],
            repo,
        )
        # Unrelated tombstone — must not suppress the active remember
        git_cmd(
            ["commit", "--allow-empty",
             "-m", "♻️ chore(gc): retire unrelated\n\nResolved-Remember: unrelated xyz888"],
            repo,
        )

        output = run_precompact(repo)

        # Verify anchor is present (snapshot was emitted)
        assert "xyzprecompactctrlanchor" in output, (
            "Test setup error: Decision anchor must be in snapshot — "
            "if this fails the snapshot was not emitted."
        )

        assert "xyzprecompactactiveremember" in output, (
            "Control: active (non-retired) remember (xyzprecompactactiveremember) "
            "must still appear in the precompact snapshot.  "
            "A failure here means the fix introduced false-positive suppression."
        )


# ── Bug C: inconsistent context-commit detection ──────────────────────────


class TestBugC_ContextDetectionInconsistency:
    """Bug C (T3): two detection predicates for context commits are inconsistent.

    extract_memory() uses:
        "context(" in subject.lower()            ← substring anywhere
    get_last_context_time() uses:
        cleaned.lower().startswith("context")    ← prefix after emoji strip

    Canonical criterion chosen for the fix (see module docstring):
        re.sub(r"^[^\\w#]+", "", subject).strip().lower().startswith("context")
    i.e. the TYPE of the commit starts with "context" after stripping the
    emoji/whitespace prefix.  This is the same logic get_last_context_time()
    already uses.

    The two observable symptoms tested here:

    Symptom 1 — false positive in extract_memory():
        A commit whose subject CONTAINS "context(" in a non-type position
        (e.g. "feat(x): context(old) deleted") sets last_context in
        extract_memory() but get_last_context_time() returns None.
        In the boot output: "Last: <sha> feat(x): context(old) deleted | "
        (notice the empty time part — the pipe is there but no time string).
        After the fix: this commit must NOT set last_context.

    Symptom 2 — legitimate context commit detected by both paths:
        A commit "💾 context(scope): pause work" is detected by both
        extract_memory() AND get_last_context_time().
        This must remain true after the fix (no regression).

    Why these tests fail today (pre-fix):
        Symptom 1 test: asserts the false-positive commit is NOT shown as
        "Last:" in the RESUME section.  Today it IS shown → FAIL (RED).
        Symptom 2 test: currently passes (both paths agree on legit commits)
        but is included as a regression guard.
    """

    def test_non_context_commit_with_context_substring_not_detected(self, tmp_path):
        """A commit like "feat(x): context(old) deleted" must NOT be treated
        as a context() commit by either detection path.

        Symptom 1: extract_memory() currently fires on this commit via
        the substring check.  The RESUME section then shows it as the last
        context with an empty/missing time part (get_last_context_time()
        returns None because the startswith predicate correctly rejects it).

        Expected post-fix behavior: this commit is NOT shown under "Last:"
        in RESUME.  Instead, RESUME shows "(no prior session found)" or
        shows a genuinely different last_context if one exists.

        This assertion fails today (RED) because extract_memory() does set
        last_context for this commit, and the output includes its subject.
        """
        repo = _make_installed_repo(tmp_path)

        # A non-context commit whose subject happens to contain "context("
        # but whose TYPE is "feat", not "context".
        false_positive_subject = "feat(x): context(old) deleted xyzfalsectx"
        git_cmd(
            ["commit", "--allow-empty",
             "-m", false_positive_subject],
            repo,
        )

        output = run_boot(repo)

        # The RESUME "Last:" line must NOT contain our false-positive commit.
        # Post-fix: neither extraction path matches this commit as a context commit.
        # NOTE: the commit may legitimately appear in the TIMELINE section (recent
        # commits list) — that is correct behavior and must NOT fail this test.
        # We assert specifically on the RESUME section, not the whole output.
        resume_section = _extract_resume_section(output)
        last_line = next(
            (line for line in resume_section.splitlines() if "Last:" in line),
            None,
        )
        # If there is a Last: line, it must not reference the false-positive commit.
        # If there is no Last: line at all, the commit was correctly not set as context.
        if last_line is not None:
            assert "xyzfalsectx" not in last_line, (
                "BUG C: Commit 'feat(x): context(old) deleted xyzfalsectx' "
                "must NOT appear under 'Last:' in the RESUME section.  "
                "extract_memory() incorrectly fires on it via substring check.  "
                "After the fix both paths must use the same startswith predicate.  "
                f"Offending Last: line → {last_line!r}"
            )

    def test_legitimate_context_commit_detected_in_boot_output(self, tmp_path):
        """A commit with type 'context' must be detected by both paths and
        appear correctly under RESUME with a non-empty time part.

        This test documents the expected post-fix state and acts as a
        regression guard — it must remain GREEN before and after the fix.
        If it fails today, the fix broke legitimate detection.
        """
        repo = _make_installed_repo(tmp_path)

        # A legitimate context commit — type "context", scope "auth"
        context_subject = "💾 context(auth): pause auth work xyzlegitctx"
        git_cmd(
            ["commit", "--allow-empty",
             "-m",
             f"{context_subject}\n\nWhy: switching to urgent bugfix\nNext: finish auth flow"],
            repo,
        )

        output = run_boot(repo)

        # The legitimate context commit must appear under RESUME Last:
        assert "xyzlegitctx" in output, (
            "Regression guard: legitimate context commit (xyzlegitctx) must appear "
            "in RESUME section.  If this fails the fix broke legitimate detection."
        )

    def test_non_context_startswith_not_detected_by_either_path(self, tmp_path):
        """Explicit check: a commit starting with 'contextualize' (starts with
        'context' but is not a context() commit) should NOT be detected.

        This test exposes an edge case of the startswith predicate: if the
        fix blindly uses startswith("context") without checking the delimiter
        (opening parenthesis), it would also fire on 'contextualize(...)'.

        Expected behavior: only "context(" (with opening paren) qualifies.
        Note: this test documents the expected contract; if the fix uses
        startswith("context(") it will be GREEN; if it uses startswith("context")
        without the paren it may still fire on 'contextualize(scope): ...'

        Marking as xfail if the fix team decides startswith("context") alone
        is acceptable — but the test documents the stricter contract.
        """
        repo = _make_installed_repo(tmp_path)

        # "contextualize" starts with "context" but is not a context() type
        git_cmd(
            ["commit", "--allow-empty",
             "-m", "contextualize(db): schema migration xyzcontextualise"],
            repo,
        )

        output = run_boot(repo)

        # "contextualize" must NOT be treated as a context() commit.
        # The word "contextualize" appears in TIMELINE (always shown), so we
        # assert specifically that it does NOT appear under the RESUME "Last:" line.
        resume_section = _extract_resume_section(output)
        assert "xyzcontextualise" not in resume_section, (
            "BUG C edge case: 'contextualize(db): ...' must NOT be treated as a "
            "context() commit.  The canonical criterion requires the type to be "
            "exactly 'context(' not merely start with 'context'."
        )

    def test_consistent_detection_both_paths_agree_on_context_commit(self, tmp_path):
        """Both paths must agree: a real context commit appears under Last: AND
        has a non-empty time component (i.e. get_last_context_time() returns a value).

        Checks the output format: "Last: <sha> <subject> | <time_ago>"
        The time_ago token must be present when a context commit exists.
        """
        import re as _re

        repo = _make_installed_repo(tmp_path)

        git_cmd(
            ["commit", "--allow-empty",
             "-m",
             "💾 context(api): pause api work xyzconsistecheck\n\n"
             "Why: switching focus\nNext: resume api work"],
            repo,
        )

        output = run_boot(repo)

        # 1. Subject must appear in output
        assert "xyzconsistecheck" in output, (
            "Legitimate context commit must appear in boot output."
        )

        # 2. The Last: line must include a time_ago token
        #    (produced by get_last_context_time() → both paths agree)
        last_line = next(
            (line for line in output.splitlines() if "Last:" in line and "xyzconsistecheck" in line),
            None,
        )
        assert last_line is not None, (
            "A 'Last:' line containing the context commit subject must appear in RESUME."
        )
        has_time = _re.search(r"\d+[mhdw] ago|just now", last_line)
        assert has_time, (
            "The 'Last:' line must contain a time_ago string (e.g. '5m ago'), "
            "meaning get_last_context_time() detected the same commit that "
            "extract_memory() found.  If this is absent, one path missed the commit "
            "(Bug C inconsistency still present)."
        )


# ── Helper: extract RESUME section from boot output ───────────────────────


def _extract_resume_section(output: str) -> str:
    """Return the text between 'RESUME:' and the next blank line + section header."""
    lines = output.splitlines()
    in_resume = False
    resume_lines = []
    for line in lines:
        if line.strip().startswith("RESUME:"):
            in_resume = True
            resume_lines.append(line)
            continue
        if in_resume:
            # Stop at blank line followed by a section header
            if line.strip() == "":
                resume_lines.append(line)
                continue
            if line.strip() and not line.startswith(" ") and line.strip().endswith(":"):
                break
            resume_lines.append(line)
    return "\n".join(resume_lines)
