"""
Regression contract (test-first) for the tombstone-in-glossary-merge bug.

Bug description
---------------
extract_memory() (scans last SCAN_DEPTH=30 commits) correctly filters
Remember and Memo entries against tombstones collected in the same scan.
BUT extract_glossary() (full history) returns entries WITHOUT filtering
tombstones — it has no knowledge of them.

In main(), the glossary merge for REMEMBER (lines ~976-981) and MEMOS
(lines ~1016-1019) only deduplicates against recent_remember_texts /
recent_memo_scopes; it does NOT check tombstones.  Result: a note that
was retired via Resolved-Remember / Resolved-Memo re-appears in the boot
output when the original commit is beyond SCAN_DEPTH.

The fix (Ultron's scope)
------------------------
extract_memory() will return tombstones in its dict.
main() will skip glossary entries whose normalize(text) is in tombstones.

These tests are written BEFORE the fix so they FAIL today (RED) for the
right reason: the retired note IS present in the output.  After Ultron
implements the fix they must turn GREEN.

Fixture strategy
----------------
Same pattern as test_boot_output.py:
  - make_repo_with_memory / run_boot helpers from that module
  - git_cmd, run_script, run_cmd from conftest
  - Repo is a full git repo with install (required for boot to run)
  - To force a note into the glossary path we add >SCAN_DEPTH (30) filler
    commits after the note so extract_memory() does not see it, but
    extract_glossary() does.
  - The Resolved-* tombstone commit is then added AFTER the filler,
    so it is inside the SCAN_DEPTH window and lands in the tombstones set.
  - The note text in the tombstone trailer is EXACTLY the same as in the
    original note (including the "Remember: " / "Memo: " prefix stripped
    by scan_trailers) so normalize() produces the same hash on both sides.
"""

import os
import sys

import pytest

from conftest import (
    HOOKS_DIR, INSTALL,
    run_cmd, git_cmd, run_script,
)

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")

# How many filler commits we need to push the original note out of the
# SCAN_DEPTH=30 window.  35 is enough margin.
FILLER_COUNT = 35


# ── Helpers ────────────────────────────────────────────────────────────


def _make_installed_repo(tmp_path, name="repo"):
    """Create a minimal git repo with git-memory installed."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    run_script(INSTALL, repo, ["--auto"])
    return repo


def _add_filler_commits(repo, count=FILLER_COUNT):
    """Add non-memory commits to push earlier commits beyond SCAN_DEPTH."""
    for i in range(count):
        git_cmd(["commit", "--allow-empty", "-m", f"chore(pad): filler commit {i}"], repo)


def run_boot(repo):
    """Run session-start-boot and return stdout.

    NOTE (contract correction, Bex 2026-07-04): stdout is now always a short
    banner (STATUS/BRANCH/pointer/BOOT COMPLETE). The REMEMBER/MEMOS content
    these tests actually assert on lives only in the boot-log file — use
    _read_boot_log(repo) after calling this to get the full content.
    """
    rc, stdout, stderr = run_cmd([sys.executable, BOOT_HOOK], repo)
    return stdout


# ── Boot-log file helpers (same pattern as test_boot_output.py) ───────────

BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")


def _boot_log_path(repo):
    return os.path.join(repo, *BOOT_LOG_REL_PARTS)


def _read_boot_log(repo):
    with open(_boot_log_path(repo), encoding="utf-8") as f:
        return f.read()


# ── Tests ──────────────────────────────────────────────────────────────


class TestTombstonedRememberDoesNotReappearViaGlossary:
    """A retired remember() note must NOT reappear in the REMEMBER section.

    The note is pushed beyond SCAN_DEPTH so it only enters boot via the
    glossary merge.  The tombstone (Resolved-Remember) is within SCAN_DEPTH.
    Today (pre-fix) the note reappears — these tests must FAIL (RED).
    After Ultron's fix they must PASS (GREEN).
    """

    def test_retired_remember_absent_from_boot_output(self, tmp_path):
        """Resolved-Remember tombstone suppresses a glossary-sourced remember note."""
        repo = _make_installed_repo(tmp_path)

        # 1. The note — text matches exactly what scan_trailers extracts for "Remember" key.
        #    Trailer format: "Remember: <value>"  ->  scan_trailers returns value = "user - prefiere español siempre"
        note_text = "user - prefiere respuestas en español siempre xyzretired"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"🧠 remember(user): language pref\n\nRemember: {note_text}"], repo)

        # 2. Push the note beyond SCAN_DEPTH so it is invisible to extract_memory()
        #    but still present in the full git history read by extract_glossary().
        _add_filler_commits(repo)

        # 3. Tombstone commit — within SCAN_DEPTH, picked up by extract_memory().
        #    The Resolved-Remember value is IDENTICAL to note_text so normalize()
        #    produces the same key on both sides.
        git_cmd(["commit", "--allow-empty", "-m",
                 f"♻️ chore(gc): retire remember\n\nResolved-Remember: {note_text}"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)

        # The distinctive token is unique — if it appears, the bug is present.
        # REMEMBER content now lives only in the boot-log file (stdout is a
        # short banner), so we assert against the file, not stdout.
        assert "xyzretired" not in content, (
            "Retired remember note (xyzretired) must NOT appear in the boot log after "
            "Resolved-Remember tombstone.  If this assertion fails today that is "
            "EXPECTED (pre-fix RED state)."
        )

    def test_non_retired_remember_still_appears(self, tmp_path):
        """Control: a note WITHOUT a tombstone continues to appear (no regression)."""
        repo = _make_installed_repo(tmp_path)

        # Active note — no matching tombstone, must survive the merge.
        active_text = "user - debug output kept brief always xyzkept"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"🧠 remember(user): debug pref\n\nRemember: {active_text}"], repo)

        # Push beyond SCAN_DEPTH so it enters via glossary path.
        _add_filler_commits(repo)

        # Unrelated tombstone — different text, must not suppress the active note.
        git_cmd(["commit", "--allow-empty", "-m",
                 "♻️ chore(gc): retire unrelated\n\nResolved-Remember: unrelated text xyz000"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)

        assert "xyzkept" in content, (
            "Active (non-retired) remember note (xyzkept) must appear in REMEMBER section "
            "of the boot log file. If this fails, the fix introduced a false-positive suppression."
        )


class TestTombstonedMemoDoesNotReappearViaGlossary:
    """A retired memo() note must NOT reappear in the MEMOS section.

    Same scenario as the Remember tests but for Memo / Resolved-Memo.
    Today (pre-fix) the memo reappears — these tests must FAIL (RED).
    After Ultron's fix they must PASS (GREEN).
    """

    def test_retired_memo_absent_from_boot_output(self, tmp_path):
        """Resolved-Memo tombstone suppresses a glossary-sourced memo note."""
        repo = _make_installed_repo(tmp_path)

        # The memo — unique text to detect reappearance unambiguously.
        memo_text = "preference - usar tabs never spaces xyzretiredmemo"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"📌 memo(style): indent pref\n\nMemo: {memo_text}"], repo)

        # Push beyond SCAN_DEPTH.
        _add_filler_commits(repo)

        # Tombstone — identical text so normalize() matches.
        git_cmd(["commit", "--allow-empty", "-m",
                 f"♻️ chore(gc): retire memo\n\nResolved-Memo: {memo_text}"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)

        assert "xyzretiredmemo" not in content, (
            "Retired memo note (xyzretiredmemo) must NOT appear in the boot log after "
            "Resolved-Memo tombstone.  If this assertion fails today that is "
            "EXPECTED (pre-fix RED state)."
        )

    def test_non_retired_memo_still_appears(self, tmp_path):
        """Control: a memo WITHOUT a tombstone continues to appear (no regression)."""
        repo = _make_installed_repo(tmp_path)

        active_memo = "preference - async/await everywhere xyzactivememo"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"📌 memo(style): async pref\n\nMemo: {active_memo}"], repo)

        # Push beyond SCAN_DEPTH.
        _add_filler_commits(repo)

        # Unrelated tombstone.
        git_cmd(["commit", "--allow-empty", "-m",
                 "♻️ chore(gc): retire unrelated\n\nResolved-Memo: unrelated memo xyz000"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)

        assert "xyzactivememo" in content, (
            "Active (non-retired) memo note (xyzactivememo) must appear in MEMOS section "
            "of the boot log file. If this fails, the fix introduced a false-positive suppression."
        )


class TestCrownOverrideResurrectsTombstonedMemo:
    """CRB-01 (Cerberus correctness finding, real bug — not security):
    the crown-OVERRIDE branches never re-check the tombstone set — only the
    INITIAL insertion branch does, in both extract_glossary()'s own Memo
    dedup loop and main()'s glossary-merge loop for MEMOS.

    Sequence that resurrects a retired entry:
      1. An OLD Memo commit carries `Crown: Memo` for scope X.
      2. It is later retired via a `Resolved-Memo:` trailer (exact same
         normalized text).
      3. Both (1) and (2) are pushed beyond SCAN_DEPTH (30) — so
         extract_memory() never sees either; only extract_glossary()
         (full-history scan) does.
      4. A NEWER, non-crowned Memo commit for the SAME scope X lands inside
         the recent window (extract_memory() sees this one fine).

    extract_glossary() walks its full history newest-first: it inserts the
    newer non-crowned entry for scope X first (still un-tombstoned at that
    point — the insertion branch does check tombstones, but this specific
    entry was never retired), then later reaches the OLDER crowned commit.
    Because scope X is already present and non-crowned, it takes the
    "crown beats a non-crowned entry" override branch — which does NOT
    check whether the value being restored is tombstoned. The retired
    OLD crowned text overwrites the newer active entry inside
    extract_glossary()'s own output. main()'s glossary-merge repeats the
    same unchecked-override mistake on top of that.

    Net effect: the explicitly-retired old crowned text resurrects and
    replaces the newer, active, never-retired entry in the final MEMOS
    output — silently reviving content a human/agent deliberately retired.

    Correct behavior: a crown-override must be a no-op if the crowned
    commit's own text is in the combined tombstone set — the scope must
    keep showing the newer active (non-crowned) entry instead.

    [ROJO]: expected to fail against the current hook.
    """

    def test_retired_crowned_memo_does_not_resurrect_over_newer_noncrowned_memo(self, tmp_path):
        repo = _make_installed_repo(tmp_path)
        scope = "crownresurrect"

        old_crowned_text = "old crowned canonical answer xyzoldcrown"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"📌 memo({scope}): old canonical\n\n"
                 f"Memo: {old_crowned_text}\nCrown: Memo"], repo)

        git_cmd(["commit", "--allow-empty", "-m",
                 f"♻️ chore(gc): retire old crowned memo\n\n"
                 f"Resolved-Memo: {old_crowned_text}"], repo)

        # Push both commits above beyond SCAN_DEPTH=30 — only extract_glossary()
        # (full history) will see them; extract_memory() (recent window) won't.
        _add_filler_commits(repo)

        new_active_text = "newer active answer xyznewactive"
        git_cmd(["commit", "--allow-empty", "-m",
                 f"📌 memo({scope}): newer answer\n\nMemo: {new_active_text}"], repo)

        run_boot(repo)
        content = _read_boot_log(repo)
        start = content.find("MEMOS:")
        memos_block = content[start:start + 2000] if start != -1 else ""

        assert "xyzoldcrown" not in memos_block, (
            f"the retired (Resolved-Memo) crowned text must NOT resurrect via "
            f"the glossary crown-override path, which skips the tombstone "
            f"check. Block:\n{memos_block}"
        )
        assert "xyznewactive" in memos_block, (
            f"the newer, non-crowned, non-tombstoned memo must be the entry "
            f"shown for this scope. Block:\n{memos_block}"
        )
        assert "👑" not in memos_block, (
            f"the scope must render as plain (uncrowned) after its only "
            f"crown was retired — it must not silently regain a crown. "
            f"Block:\n{memos_block}"
        )
