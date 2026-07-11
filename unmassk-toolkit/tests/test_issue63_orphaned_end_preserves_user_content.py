"""
Acceptance contract (test-first, RED) for a DATA-LOSS regression in T1-A's
own fix, found by Moriarty round 3 (T1-1) against
lib/managed_blocks.py::upsert_managed_blocks() (~L212-242).

T1-A (see tests/test_issue63_t1_end_marker_and_magic_string.py) fixed the
lie where a block with an orphaned BEGIN (its END marker deleted, e.g. by a
merge-conflict resolution or editor auto-fix) was silently reported
"up to date" forever. The fix works: it correctly regenerates the block.
But its mechanism over-reaches. When it finds the orphaned BEGIN, it treats
EVERYTHING between that BEGIN and the NEXT managed block's BEGIN as
"orphaned body" and deletes it wholesale when splicing in the canonical
replacement:

    boundary = min(next_positions)
    content = content[:start] + rendered + "\n\n" + content[boundary:]

That gap is exactly where a normal user writes their own free-text notes
directly below a managed block (a completely ordinary, expected edit --
managed blocks are not the whole file). Deleting the block's END line
(the SAME corruption T1-A's own test simulates) therefore silently deletes
any user content sitting in that gap too, with no warning.

NEW CONTRACT: regenerating a block whose END marker is orphaned must NEVER
delete non-managed (user) content that was sitting around it. It must
restore the managed block (BEGIN+body+END) AND preserve whatever user text
was adjacent -- the same T1-A recovery, minus the collateral deletion.

Verified two real channels share the exact same upsert_managed_blocks()
call (lib/managed_blocks.py), so a single test per channel is
representative rather than redundant:
  1. hooks/session-start-crew.py (SessionStart hook) -- real subprocess.
  2. lib/install_apply.py::_update_claude_md() (installer's own producer,
     also reached indirectly via needs_upgrade() -> trigger_auto_upgrade_if_needed()
     -> bin/git-memory-install.py --auto) -- direct call in an isolated
     subprocess, same pattern as test_crew_content_gate_v2.py's
     _run_sabotaged_producer().

Build mode: test-first (contract pass, before Ultron). NO production code
is touched by this file. Only tests.

See also: tests/test_issue63_t1_end_marker_and_magic_string.py (the
original T1-A fix this file's regression sits inside),
tests/test_crew_content_gate_v2.py (the install_apply subprocess-call
pattern this file reuses for the installer channel).
"""

import os
import sys
import time

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd, run_script

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import BLOCKS, any_block_outdated, _render_block  # noqa: E402

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")
INSTALL = os.path.join(os.path.join(SOURCE_ROOT, "bin"), "git-memory-install.py")

# Recognizable, specific user content -- never a generic placeholder, so a
# fix that merely preserves "some" bytes near the gap (instead of genuinely
# preserving user content) cannot pass by accident.
USER_NOTE = "USER-NOTE: never touch payments"


# ── Shared repo helpers (self-contained, mirrors test_issue63_t1_end_marker_and_magic_string.py) ──


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _install(repo):
    """Real producer, happy path: writes canonical CLAUDE.md + manifest.json
    with version == VERSION. Never a hand-typed CLAUDE.md stand-in --
    canonical content is always derived from the real installer, which
    itself is backed by lib/managed_blocks.py (unmassk-standards §34: no
    fabricated ground truth)."""
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"install --auto failed: {out}\n{err}"


def _claude_md_path(repo):
    return os.path.join(repo, "CLAUDE.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _insert_user_note_after_end(repo, block, note):
    """Simulate a real user typing a free-text note directly below a real,
    freshly-installed managed block in CLAUDE.md (below its END marker,
    before the NEXT block's BEGIN) -- exactly the gap a normal user could
    occupy; managed blocks are not the whole file. Returns the new content
    string, and asserts the note actually landed there (sanity, not the
    regression under test)."""
    claude_md = _claude_md_path(repo)
    content = _read(claude_md)
    end_pos = content.find(block["end"])
    assert end_pos != -1, "installed CLAUDE.md must contain this block's END marker"
    insertion_point = end_pos + len(block["end"])
    new_content = content[:insertion_point] + "\n\n" + note + "\n" + content[insertion_point:]
    _write(claude_md, new_content)
    assert note in new_content, "sanity: the user note must have actually landed below the block"
    return new_content


def _insert_user_note_before_begin(repo, block, note):
    """Simulate a real user typing a free-text note directly ABOVE a real,
    freshly-installed managed block in CLAUDE.md (in the gap between the
    PREVIOUS block's END and this block's BEGIN) -- the mirror case of
    `_insert_user_note_after_end`: managed blocks are not the whole file,
    and a user is just as free to write notes above a block as below one.
    Returns the new content string, and asserts the note actually landed
    there (sanity, not the regression under test)."""
    claude_md = _claude_md_path(repo)
    content = _read(claude_md)
    begin_pos = content.find(block["begin"])
    assert begin_pos != -1, "installed CLAUDE.md must contain this block's BEGIN marker"
    new_content = content[:begin_pos] + note + "\n\n" + content[begin_pos:]
    _write(claude_md, new_content)
    assert note in new_content, "sanity: the user note must have actually landed above the block"
    return new_content


def _delete_only_end_line(repo, end_marker):
    """Corrupt CLAUDE.md by removing ONLY the given block's END marker line
    (merge-conflict resolution / editor auto-fix), leaving everything else
    -- including any user content already present -- untouched. Same
    corruption technique as test_issue63_t1_end_marker_and_magic_string.py's
    RED test, reused here so this file exercises the identical real-world
    trigger, not a different/easier one."""
    claude_md = _claude_md_path(repo)
    content = _read(claude_md)
    lines = content.splitlines(keepends=True)
    corrupted_lines = [ln for ln in lines if ln.rstrip("\n") != end_marker]
    assert len(corrupted_lines) == len(lines) - 1, (
        "sanity check on the corruption itself: exactly one END line must "
        "be removed, or this test isn't corrupting what it claims to"
    )
    corrupted = "".join(corrupted_lines)
    _write(claude_md, corrupted)
    return corrupted


def _run_crew(repo):
    return run_cmd([sys.executable, CREW_HOOK], cwd=repo)


def _run_installer_update_claude_md(repo):
    """Isolated subprocess call to the REAL lib/install_apply.py::
    _update_claude_md() -- the installer's own producer for the CLAUDE.md
    write, sharing the exact same managed_blocks.upsert_managed_blocks()
    call as the crew hook (lib/install_apply.py:220-243). Chosen as the
    representative test for the "camino instalador" per this contract's own
    explicit allowance to cover the shared upsert with one targeted call,
    instead of driving the full needs_upgrade() -> trigger_auto_upgrade_if_needed()
    -> bin/git-memory-install.py --auto chain (heavier, and that chain's own
    manifest-stamp gating is already covered elsewhere, e.g.
    test_issue63_producer_hardening.py) -- both channels bottom out in the
    identical upsert_managed_blocks() call, so a second, differently-shaped
    call into that same function proves the regression is not
    crew-hook-specific without duplicating the whole install pipeline.
    """
    code = f"""
import sys, os
sys.path.insert(0, {LIB_DIR!r})
import install_apply
install_apply._update_claude_md({repo!r})
print("OK")
"""
    return run_cmd([sys.executable, "-c", code], repo, timeout=30)


# ══════════════════════════════════════════════════════════════════════════
# Channel 1 -- hooks/session-start-crew.py, real subprocess against a real
# installed repo.
# ══════════════════════════════════════════════════════════════════════════


class TestCrewHookOrphanedEndPreservesUserContent:
    def test_crew_hook_preserves_user_note_below_regenerated_block(self, tmp_path):
        """A user note sitting directly below a managed block (a completely
        ordinary edit) must survive T1-A's orphaned-END regeneration.

        RED today: lib/managed_blocks.py's orphaned-BEGIN branch treats
        everything between the dangling BEGIN and the NEXT block's BEGIN as
        disposable "orphaned body" and deletes it wholesale when splicing in
        the canonical replacement -- including the user's note, which was
        never part of any managed block.

        Combined in the same test (not split into a separate case): the
        good part of T1-A's fix must still hold -- the block's END marker
        must genuinely come back (exactly once), not regress to the
        pre-T1-A "silently declared up to date, corruption stays forever"
        bug. A fix that solves the data-loss problem by reverting to that
        earlier bug would make this test fail for the END/BEGIN-count
        assertions instead, which is deliberately also checked here.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        b0 = BLOCKS[0]
        # Block 0 (unmassk-toolkit) is not the last block in BLOCKS -- the
        # next managed block's BEGIN (unmassk-protocols) is the real
        # boundary the buggy branch uses to decide what counts as
        # "orphaned body" and deletes. Using the last block would exercise
        # a different branch (no next_positions) that behaves differently.
        assert b0 is not BLOCKS[-1]

        _insert_user_note_after_end(repo, b0, USER_NOTE)

        corrupted = _delete_only_end_line(repo, b0["end"])
        # Independent-channel confirmation the corruption is real and the
        # note survived JUST the corruption step (not yet the hook run).
        assert USER_NOTE in corrupted, (
            "the user note must survive the END-line deletion itself -- "
            "only the END line was removed"
        )
        assert corrupted.count(b0["end"]) == 0, "END must be genuinely absent after corruption"
        assert corrupted.count(b0["begin"]) == 1, "BEGIN must survive the corruption untouched"

        # ── Run the REAL hook (code under test) via real subprocess ─────
        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0 (fail-open). stderr={stderr!r}"

        # Independent channel: raw bytes, never through managed_blocks.py's
        # own upsert logic (that's the code under test, not the oracle).
        with open(_claude_md_path(repo), "rb") as f:
            raw_after = f.read()
        content_after = raw_after.decode("utf-8")

        end_count_after = content_after.count(b0["end"])
        begin_count_after = content_after.count(b0["begin"])

        # ── T1-A's own contract must still hold ──────────────────────────
        assert end_count_after == 1, (
            "T1-A's fix must still hold: the block's END marker must be "
            f"regenerated (exactly once). stdout={stdout!r} content_after={content_after!r}"
        )
        assert begin_count_after == 1, (
            "regenerating the block must not leave a duplicate BEGIN behind. "
            f"count={begin_count_after} content_after={content_after!r}"
        )

        # ── The NEW contract this file adds ──────────────────────────────
        assert USER_NOTE.encode("utf-8") in raw_after, (
            "regenerating a block with an orphaned END marker must never "
            "silently delete unrelated user content that sat below it "
            f"(recognizable marker {USER_NOTE!r} missing). "
            f"content_after={content_after!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Channel 2 -- lib/install_apply.py::_update_claude_md(), the installer's
# own producer for the same write, called directly in an isolated
# subprocess. Also reachable via needs_upgrade() -> trigger_auto_upgrade_if_needed()
# -> bin/git-memory-install.py --auto, same underlying function.
# ══════════════════════════════════════════════════════════════════════════


class TestInstallerPathOrphanedEndPreservesUserContent:
    def test_update_claude_md_preserves_user_note_below_regenerated_block(self, tmp_path):
        """Same regression, installer channel: lib/install_apply.py::
        _update_claude_md() calls the identical managed_blocks.upsert_managed_blocks()
        that hooks/session-start-crew.py calls (see that module's docstring
        -- "Both session-start-crew.py ... and git-memory-install.py ...
        import this module so the 5 blocks never diverge"). If the crew
        channel above is fixed by patching upsert_managed_blocks() itself
        (the shared root), this channel must be fixed too, for free -- this
        test exists to make sure that's actually verified, not assumed.

        RED today: identical root cause as the crew-hook test above.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        b0 = BLOCKS[0]
        _insert_user_note_after_end(repo, b0, USER_NOTE)
        corrupted = _delete_only_end_line(repo, b0["end"])
        assert USER_NOTE in corrupted, (
            "the user note must survive the END-line deletion itself -- "
            "only the END line was removed"
        )
        assert corrupted.count(b0["end"]) == 0, "END must be genuinely absent after corruption"

        rc, stdout, stderr = _run_installer_update_claude_md(repo)
        assert rc == 0, (
            f"install_apply._update_claude_md() must not crash. "
            f"stdout={stdout!r} stderr={stderr!r}"
        )

        with open(_claude_md_path(repo), "rb") as f:
            raw_after = f.read()
        content_after = raw_after.decode("utf-8")

        assert content_after.count(b0["end"]) == 1, (
            "T1-A's fix must still hold on the installer channel too: the "
            f"block's END marker must be regenerated (exactly once). "
            f"content_after={content_after!r}"
        )
        assert content_after.count(b0["begin"]) == 1, (
            "regenerating the block must not leave a duplicate BEGIN behind. "
            f"content_after={content_after!r}"
        )
        assert USER_NOTE.encode("utf-8") in raw_after, (
            "the installer's own producer path (install_apply._update_claude_md, "
            "shares the same managed_blocks.upsert_managed_blocks() call as the "
            "crew hook) must also preserve user content sitting below an "
            "orphaned-END block, not just the crew hook. "
            f"content_after={content_after!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Hardening pass (post-Ultron, wip 7842668's conservative single-line-removal
# fix already GREEN for the 2 tests above). EXHAUSTION PROTOCOL scope for
# THIS file: close the specific gaps the task named, not re-litigate what
# the 2 tests above already prove.
#
# lib/managed_blocks.py's conservative fix (~L212-237) removes EXACTLY the
# orphaned BEGIN's own single line and reinserts the full canonical block at
# that same position -- unlike the OLD buggy mechanism it replaced (a
# `boundary = min(next_positions)` splice that behaved differently for the
# last block in BLOCKS vs. any other block, and only ever considered the
# gap BELOW a block, never above), the new mechanism never branches on
# block position and never touches anything before the BEGIN line at all.
# That makes it "safe by construction" for both gaps below AND above, and
# for the last block same as any other -- but that is exactly the kind of
# claim that must be pinned by a real test, not left as an inference from
# reading the diff, so a future change reintroducing position-dependent
# splicing would be caught. One channel (crew hook) is sufficient for each
# of these -- both existing tests above already proved BOTH channels (crew
# hook and the installer's _update_claude_md()) hit the identical shared
# upsert_managed_blocks() call, so re-doing that 2-channel proof again per
# edge case would be pure duplication, not new coverage.
# ══════════════════════════════════════════════════════════════════════════


class TestLastBlockOrphanedEndPreservesUserContent:
    def test_last_block_orphaned_end_preserves_note_below_and_recovers_end_once(self, tmp_path):
        """Item (a): the OLD buggy mechanism this fix replaced took a
        DIFFERENT branch for the last block in BLOCKS (no `next_positions`,
        so nothing to delete) than for any other block -- meaning the old
        bug's own regression tests (both above, using BLOCKS[0]) proved
        nothing about the last-block case. The NEW conservative mechanism
        doesn't branch on position at all, but that must be proven for the
        last block specifically, not assumed from the non-last-block tests
        passing. Also re-confirms item (c) (END recovered exactly once, not
        duplicated) for this position, since the same assertion must hold
        regardless of which block is corrupted.

        Mutation-checked against the OLD buggy mechanism (verified live by
        temporarily restoring `git show 7842668^:...managed_blocks.py`):
        the note-presence + begin/end-count-==1 assertions alone did NOT
        kill this mutant for the last-block case -- the old code's
        no-next-positions branch does `re.sub(begin + r"\n?", "", ...,
        count=1)` (strips ONLY the begin line, leaves the orphaned body in
        place) and separately queues the same block to be APPENDED at the
        very end. Net effect: begin count and end count both land on 1
        (from the fresh appended copy only) and the note survives (it was
        never in the deleted line), so those assertions alone false-passed
        against the known-buggy mechanism. What actually distinguishes the
        two mechanisms in scope here is POSITION: the old mechanism moves
        the regenerated block to the very end of the file (after the note),
        while the new one regenerates it in place (the block's END marker
        must appear BEFORE the note, not after it) -- confirmed live: False
        against the restored old code (end_pos=6781 > note_pos=5800), True
        against the current fix (end_pos=5849 < note_pos=6775). NOTE: both
        old and new code ALSO leave the orphaned block's original body text
        behind as unmarked dead text alongside the regenerated copy -- this
        is the SAME leftover-dead-text class Ultron already reported and
        the task explicitly deferred to issue #64, so it is deliberately
        NOT asserted against here (see this file's own docstring exclusion
        note added below, and the final task report).
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        last_block = BLOCKS[-1]
        assert last_block is BLOCKS[-1] and last_block is not BLOCKS[0], (
            "sanity: this test must target the LAST block, the one position "
            "the old buggy mechanism handled via a different code path"
        )

        note = "USER-NOTE-LAST-BLOCK: never touch payments"
        _insert_user_note_after_end(repo, last_block, note)
        corrupted = _delete_only_end_line(repo, last_block["end"])
        assert note in corrupted, "the note must survive the END-line deletion itself"
        assert corrupted.count(last_block["end"]) == 0, "END must be genuinely absent after corruption"
        assert corrupted.count(last_block["begin"]) == 1, "BEGIN must survive the corruption untouched"

        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0 (fail-open). stderr={stderr!r}"

        with open(_claude_md_path(repo), "rb") as f:
            raw_after = f.read()
        content_after = raw_after.decode("utf-8")

        assert content_after.count(last_block["end"]) == 1, (
            "the last block's END marker must be regenerated exactly once, same "
            f"as for any other block position. content_after={content_after!r}"
        )
        assert content_after.count(last_block["begin"]) == 1, (
            "regenerating the last block must not leave a duplicate BEGIN behind. "
            f"content_after={content_after!r}"
        )
        assert note.encode("utf-8") in raw_after, (
            "regenerating the LAST block's orphaned END must not silently delete "
            "user content sitting below it, the same guarantee already proven for "
            f"a non-last block. note={note!r} content_after={content_after!r}"
        )
        end_pos_after = content_after.index(last_block["end"])
        note_pos_after = content_after.index(note)
        assert end_pos_after < note_pos_after, (
            "the regenerated block must stay IN PLACE (near where the orphaned "
            "BEGIN originally sat), not be relocated to the very end of the "
            "file after the user's note -- position, not just presence, is "
            f"the in-scope claim here. end_pos={end_pos_after} note_pos="
            f"{note_pos_after} content_after={content_after!r}"
        )


class TestNoteBeforeOrphanedBlockPreserved:
    def test_orphaned_end_preserves_user_note_written_above_the_block(self, tmp_path):
        """Item (b): the 2 contract tests above only ever plant the user
        note BELOW the corrupted block (in the gap between its END and the
        next block's BEGIN). A user is just as free to write a note ABOVE a
        block -- in the gap between the PREVIOUS block's END and this
        block's BEGIN -- and that gap must survive the same regeneration
        just as reliably. Targets BLOCKS[1] (not BLOCKS[0], which has no
        real "previous block" gap of its own -- only the installer's fixed
        file header sits above it) so the gap being tested is a genuine
        inter-block gap, not the document header.

        Mutation-check note (verified live): unlike the below-the-block
        case, the OLD buggy mechanism's boundary deletion only ever
        searched FORWARD from the orphaned BEGIN for a boundary to delete
        up to -- it never touched anything before that BEGIN. So this
        specific test does not kill that OLD mutant (content before a
        block was never at risk under either mechanism) -- it is still
        kept as a permanent regression guard per the task's explicit ask,
        against a DIFFERENT future regression: any change that starts
        anchoring deletion on a "previous block's END" boundary (the
        mirror-image of the old bug) would be caught here.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        target = BLOCKS[1]
        assert target is not BLOCKS[0], (
            "sanity: must target a block with a real PREVIOUS block above it, "
            "so the note lands in a genuine inter-block gap"
        )

        note = "USER-NOTE-ABOVE: never touch payments"
        _insert_user_note_before_begin(repo, target, note)
        corrupted = _delete_only_end_line(repo, target["end"])
        assert note in corrupted, "the note must survive the END-line deletion itself"
        assert corrupted.count(target["end"]) == 0, "END must be genuinely absent after corruption"
        assert corrupted.count(target["begin"]) == 1, "BEGIN must survive the corruption untouched"

        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0 (fail-open). stderr={stderr!r}"

        with open(_claude_md_path(repo), "rb") as f:
            raw_after = f.read()
        content_after = raw_after.decode("utf-8")

        assert content_after.count(target["end"]) == 1, (
            f"the block's END marker must be regenerated exactly once. "
            f"content_after={content_after!r}"
        )
        assert content_after.count(target["begin"]) == 1, (
            f"regenerating the block must not leave a duplicate BEGIN behind. "
            f"content_after={content_after!r}"
        )
        assert note.encode("utf-8") in raw_after, (
            "regenerating a block whose END marker is orphaned must not silently "
            "delete unrelated user content sitting ABOVE it (not just below it, "
            f"the case the existing 2 tests already cover). note={note!r} "
            f"content_after={content_after!r}"
        )


class TestRegeneratedBlockRoundTripNoRewriteOnNextBoot:
    def test_next_boot_does_not_rewrite_after_regeneration(self, tmp_path):
        """unmassk-standards §34 round-trip closure for the full seam: a
        boot that regenerates CLAUDE.md (producer) must be followed by the
        NEXT boot reading that same file and genuinely NOT touching it again
        (consumer, real idempotence) -- not just "produces the same bytes if
        it did rewrite," which content-equality alone cannot distinguish
        from a real no-op write. Two existing tests each cover half of this
        claim without ever combining them end-to-end on the SAME
        regenerated file: test_crew_content_gate_v2.py's
        TestCanonicalContentWithMatchingManifestSkipsRewrite proves
        mtime-preserving no-rewrite, but only starting from a content that
        was ALREADY canonical straight out of a fresh install -- it never
        starts from a corrupted-then-regenerated file. test_issue63_t1_end_marker_and_magic_string.py's
        orphaned-END test proves a second run after regeneration produces
        byte-identical content -- but never checks mtime, so it cannot tell
        a genuine no-op from a rewrite that happens to reproduce the exact
        same bytes. This test closes that gap: real corruption -> real
        regeneration (boot 1) -> real second boot (boot 2) -> mtime AND
        content both provably untouched by boot 2, via the real crew-hook
        channel end to end (no fabricated fixture at any step).
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        b0 = BLOCKS[0]
        note = "USER-NOTE-ROUNDTRIP: never touch payments"
        _insert_user_note_after_end(repo, b0, note)
        corrupted = _delete_only_end_line(repo, b0["end"])
        assert note in corrupted, "the note must survive the END-line deletion itself"
        assert corrupted.count(b0["end"]) == 0, "END must be genuinely absent after corruption"

        # ── Boot 1 (producer): regenerates the corrupted block ───────────
        rc1, stdout1, stderr1 = _run_crew(repo)
        assert rc1 == 0, f"boot 1 (regeneration) must exit 0. stderr={stderr1!r}"

        claude_md = _claude_md_path(repo)
        content_after_boot1 = _read(claude_md)
        assert content_after_boot1.count(b0["end"]) == 1, (
            "sanity: boot 1 must have actually regenerated the block "
            f"(END present exactly once). content={content_after_boot1!r}"
        )
        assert note in content_after_boot1, (
            "sanity: boot 1's regeneration must not have deleted the user note "
            f"(already proven by the tests above; re-checked here as a precondition). "
            f"content={content_after_boot1!r}"
        )
        mtime_after_boot1 = os.path.getmtime(claude_md)

        # Filesystem mtime resolution can be as coarse as 1s on some hosts;
        # give a rewrite (if one incorrectly happens) room to be observable.
        # Same margin test_crew_content_gate_v2.py's mtime-based test uses.
        time.sleep(1.1)

        # ── Boot 2 (consumer): must be a genuine no-op ────────────────────
        rc2, stdout2, stderr2 = _run_crew(repo)
        assert rc2 == 0, f"boot 2 (next boot) must exit 0. stderr={stderr2!r}"

        content_after_boot2 = _read(claude_md)
        mtime_after_boot2 = os.path.getmtime(claude_md)

        assert content_after_boot2 == content_after_boot1, (
            "boot 2 must read back exactly what boot 1 wrote -- no further change. "
            f"boot1={content_after_boot1!r} boot2={content_after_boot2!r}"
        )
        assert mtime_after_boot2 == mtime_after_boot1, (
            "boot 2 must NOT rewrite CLAUDE.md at all (mtime must stay byte-for-byte "
            "identical to what boot 1 left) -- content equality alone cannot prove "
            "this, since a rewrite that happens to reproduce the same bytes would "
            "still pass a content-only check. mtime_boot1="
            f"{mtime_after_boot1!r} mtime_boot2={mtime_after_boot2!r} "
            f"stdout2={stdout2!r}"
        )
        combined2 = f"{stdout2}\n{stderr2}".lower()
        assert "up to date" in combined2 or "up-to-date" in combined2, (
            "boot 2 must genuinely report the blocks as up to date now that "
            f"regeneration already happened in boot 1. stdout2={stdout2!r}"
        )


class TestOrphanedBeginAtLiteralEOFNoTrailingNewline:
    """Cerberus suggestion (post-Ultron hardening): the `line_end == -1`
    sub-branch in lib/managed_blocks.py:233-236 has no dedicated test. Every
    "last block" test above (TestLastBlockOrphanedEndPreservesUserContent)
    always plants a user note directly below the corrupted block, so
    `content.find("\\n", start)` always finds that note's leading newline
    and takes the `line_end != -1` path. The ONLY way to force the other
    branch is a BEGIN marker that is the literal, physical last byte
    sequence of the file: no trailing newline, no END, nothing after it at
    all -- e.g. a write that was truncated mid-append, or a user who typed
    the BEGIN comment by hand and saved before typing anything else.

    NEW CONTRACT: this must regenerate the full block (BEGIN+body+END,
    exactly once each) in place, identically to every other orphaned-BEGIN
    case above -- not crash, not leave the dangling BEGIN untouched, and
    not corrupt any content that came before it in the file.

    Mutation-check note (verified live, not assumed): unlike the other
    classes in this file, this one does NOT distinguish current
    lib/managed_blocks.py from the OLD pre-7842668 mechanism (33de083) --
    both produce byte-identical output for this exact scenario, for every
    block position (checked all 5). That is expected, not a gap: the OLD
    mechanism's data-loss bug only manifests when real content sits
    BETWEEN the orphaned BEGIN and a later boundary; here nothing at all
    follows the BEGIN, so the OLD "no next_positions -> strip begin line,
    queue for end-of-file append" fallback happens to reconstruct the same
    bytes. This test exists for a DIFFERENT reason (Cerberus's ask): the
    `line_end == -1` branch itself (lib/managed_blocks.py:234-235) had zero
    dedicated coverage, and it IS capable of failing on its own -- verified
    live by reintroducing the specific naive regression this branch's
    ternary guards against (dropping the `if line_end == -1 else` guard and
    always doing `content.find("\\n", start) + 1`, which wraps to 0 and
    re-splices the ENTIRE document back onto itself): that mutant fails
    `content_after.count(target["begin"]) == 1` (produces 2). This test is
    a coverage-gap fill and a guard against that class of future
    regression, not a repeat of the OLD-mechanism data-loss regression
    guard the other classes in this file provide.
    """

    def test_begin_as_last_byte_of_file_regenerates_full_block(self, tmp_path):
        repo = _make_repo(tmp_path)
        _install(repo)

        # Last block in BLOCKS -- realistic choice: in a freshly installed
        # CLAUDE.md this block's BEGIN/body/END really is the physically
        # last content in the file, so truncating right after its BEGIN
        # marker (with no newline) does not require discarding any other
        # block to construct the scenario.
        target = BLOCKS[-1]
        assert target is BLOCKS[-1], "sanity: must be the physically last block"

        claude_md = _claude_md_path(repo)
        content_before = _read(claude_md)
        assert content_before.count(target["begin"]) == 1
        assert content_before.count(target["end"]) == 1

        begin_pos = content_before.find(target["begin"])
        assert begin_pos != -1, "installed CLAUDE.md must contain this block's BEGIN marker"
        prefix = content_before[:begin_pos]

        # Truncate the file to end EXACTLY at the last character of the
        # BEGIN marker itself: no newline after it, no END marker, no body,
        # nothing else -- the dangling BEGIN IS the last byte of the file.
        corrupted = content_before[: begin_pos + len(target["begin"])]
        assert corrupted.endswith(target["begin"]), (
            "sanity: the corrupted file must end with the bare BEGIN marker"
        )
        assert not corrupted.endswith("\n"), (
            "sanity: the corrupted file must have NO trailing newline after "
            "the dangling BEGIN -- otherwise content.find('\\n', start) would "
            "find one and this test would exercise the OTHER branch "
            "(line_end != -1), not the EOF one under test here"
        )
        assert corrupted.count(target["end"]) == 0, "END must be genuinely absent"
        assert corrupted.count(target["begin"]) == 1, "BEGIN must survive the corruption untouched"
        _write(claude_md, corrupted)

        # ── Run the REAL hook (code under test) via real subprocess ─────
        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0 (fail-open). stderr={stderr!r}"

        with open(claude_md, "rb") as f:
            raw_after = f.read()
        content_after = raw_after.decode("utf-8")

        # EOL-normalized view for STRING/semantic comparisons only. On
        # Windows the hook's text-mode write translates every "\n" it
        # emits to "\r\n" UNIFORMLY (not a mixed-EOL corruption -- a
        # genuine, correct Windows text file), while `expected_rendered`
        # below is built in-memory with bare "\n" and `prefix` was derived
        # from `content_before`, itself read via `_read()`'s universal-
        # newline text mode (always "\n"). Comparing those LF-built values
        # against the raw CRLF bytes would fail for a purely cosmetic EOL
        # reason having nothing to do with the behavior under test.
        # Byte-exact assertions (marker occurrence counts below) do NOT
        # depend on EOL -- the markers never embed a newline -- so those
        # stay on the raw-decoded `content_after`.
        content_after_text = content_after.replace("\r\n", "\n").replace("\r", "\n")

        assert content_after.count(target["begin"]) == 1, (
            "the block's BEGIN marker must be regenerated exactly once, not "
            f"duplicated. content_after={content_after!r}"
        )
        assert content_after.count(target["end"]) == 1, (
            "the block's END marker must come back exactly once -- the "
            f"pre-fix bug (line_end == -1 mishandled) must not leave it "
            f"permanently absent or duplicated. content_after={content_after!r}"
        )

        # Expected block bytes derived from the real render contract
        # (managed_blocks._render_block), never hand-typed -- unmassk-standards
        # §34: the expected value must come from the real producer seam.
        expected_rendered = _render_block(target)
        assert expected_rendered in content_after_text, (
            "the regenerated block must match the real canonical render "
            f"exactly (BEGIN+body+END). content_after={content_after!r}"
        )

        # Nothing before the dangling BEGIN (earlier blocks, file header)
        # may be touched -- the fix's own "safe by construction" claim for
        # this exact edge (no bytes after the BEGIN line to accidentally
        # eat, but also none before it that should ever move). `prefix`
        # is LF-normalized (derived from `content_before`), so it must be
        # compared against the LF-normalized view too.
        assert content_after_text.startswith(prefix), (
            "regenerating a BEGIN orphaned at EOF must not alter any byte "
            f"that came before it. prefix={prefix!r} content_after={content_after!r}"
        )

        assert not any_block_outdated(content_after_text), (
            "after regeneration every block (not just the corrupted one) "
            f"must match canonical content exactly. content_after={content_after!r}"
        )

        # ── Idempotency: a second real run must be a genuine no-op ──────
        rc2, stdout2, stderr2 = _run_crew(repo)
        assert rc2 == 0, f"second crew run must exit 0. stderr={stderr2!r}"
        # `_read()` uses text-mode universal newlines (always "\n"), so
        # compare against the LF-normalized view for the same EOL reason
        # as the assertions above -- not the raw CRLF-preserving one.
        content_after_2 = _read(claude_md)
        assert content_after_2 == content_after_text, (
            "a second run against already-regenerated, canonical content "
            "must be a genuine no-op (idempotent)"
        )
