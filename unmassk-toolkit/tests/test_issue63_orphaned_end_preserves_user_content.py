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

from conftest import SOURCE_ROOT, HOOKS_DIR, git_cmd, run_cmd, run_script

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import BLOCKS  # noqa: E402

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
