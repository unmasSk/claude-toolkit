"""
Tests for the 4-block managed CLAUDE.md behavior.

Covers:
- All 4 blocks present after install
- Each block has the correct content
- upsert_managed_blocks() is idempotent
- Outdated block is updated in place
- Missing block is appended at end
- Block order is preserved
- Legacy blocks (including the retired caveman block) are removed
- session-start-crew.py writes all 4 blocks
- Uninstall removes all 4 blocks
- any_block_outdated / all_blocks_present helpers
"""

import json
import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, git_cmd, run_script, run_cmd

# Make lib/ importable
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import (  # noqa: E402
    BLOCKS,
    upsert_managed_blocks,
    all_blocks_present,
    any_block_outdated,
    _LEGACY_PATTERNS,
)

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")


# ── Helpers ───────────────────────────────────────────────────────────────

def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


# ── Unit tests: managed_blocks module ────────────────────────────────────

class TestBlocksDefinition:
    def test_exactly_four_blocks(self):
        assert len(BLOCKS) == 4

    def test_block_ids(self):
        """Each block has a distinct begin marker."""
        begins = [b["begin"] for b in BLOCKS]
        assert len(set(begins)) == 4, "Duplicate begin markers"

    def test_first_block_is_toolkit(self):
        assert "unmassk-toolkit" in BLOCKS[0]["begin"]

    def test_block_order(self):
        expected_ids = [
            "unmassk-toolkit",
            "unmassk-protocols",
            "unmassk-communication",
            "unmassk-build-mode",
        ]
        for i, expected in enumerate(expected_ids):
            assert expected in BLOCKS[i]["begin"], (
                f"Block[{i}] expected to contain '{expected}', got '{BLOCKS[i]['begin']}'"
            )

    def test_all_blocks_have_body(self):
        for b in BLOCKS:
            assert b["body"].strip(), f"Block '{b['begin']}' has empty body"

    def test_toolkit_block_content(self):
        """First block must contain the boot instructions.

        Aligned 2026-08-02 to the shorter, honest body reinstated this
        session: it no longer promises the unmassk-gitmemory skill or its
        CALIBRATION.md, both deliberately absent from this branch so the
        CLAUDE.md written into every installed project never carries an
        instruction the toolkit can't actually keep. This contract is
        touched again at plan step 7.12, once the new skill exists and the
        block is rewritten wholesale -- whoever reads this then should know
        it was already revisited once, and why.
        """
        body = BLOCKS[0]["body"]
        assert "unmassk-toolkit Active" in body
        assert "unmassk-core" in body

    def test_protocols_block_content(self):
        body = BLOCKS[1]["body"]
        assert "unmassk-project-lifecycle" in body
        assert "unmassk-grill" in body
        assert "unmassk-council" in body
        assert "unmassk-close-session" in body

    # ── Contract (TDD): the 3 real, shipped protocol skills that were
    # deliberately excluded from the Protocols menu under an old "only list
    # installed+referenced skills" policy. All 3 are fully built and tested
    # (not drafts), so the exclusion reason no longer applies — an 11-agent
    # council confirmed hiding them from the one menu Claude reads every
    # session actively hurts routing. These MUST fail against the current
    # generator (RED) until managed_blocks.py's protocols block body is
    # updated to include them (Ultron's job).

    def test_protocols_block_includes_flow_skill(self):
        """unmassk-flow (8-step creative build pipeline) must appear in the menu.

        Source of truth for trigger wording: skills/unmassk-flow/SKILL.md
        description — 'build a feature', 'create something new', 'implement',
        'add functionality', 'fix a non-trivial bug', 'refactor'.
        """
        body = BLOCKS[1]["body"]
        assert "`unmassk-flow`" in body, (
            "unmassk-flow is shipped and tested but missing from the Protocols "
            "menu — Claude can't route to a skill it can't see here"
        )
        trigger_phrases = ("build a feature", "implement", "non-trivial", "refactor")
        assert any(phrase in body.lower() for phrase in trigger_phrases), (
            "Protocols row for unmassk-flow must reflect its real trigger "
            f"situation from SKILL.md's description (expected one of {trigger_phrases})"
        )

    def test_protocols_block_includes_audit_skill(self):
        """unmassk-audit (14-step enterprise audit workflow) must appear in the menu.

        Source of truth for trigger wording: skills/unmassk-audit/SKILL.md
        description — 'audit a module', 'enterprise review', 'launch audit'.
        """
        body = BLOCKS[1]["body"]
        assert "`unmassk-audit`" in body, (
            "unmassk-audit is shipped and tested but missing from the Protocols "
            "menu — Claude can't route to a skill it can't see here"
        )
        trigger_phrases = ("audit", "enterprise review")
        assert any(phrase in body.lower() for phrase in trigger_phrases), (
            "Protocols row for unmassk-audit must reflect its real trigger "
            f"situation from SKILL.md's description (expected one of {trigger_phrases})"
        )

    def test_protocols_block_includes_scaffolding_skill(self):
        """unmassk-scaffolding (project scaffolding wizard) must appear in the menu.

        Source of truth for trigger wording: skills/unmassk-scaffolding/SKILL.md
        description — 'scaffold project', 'which stack', 'tech stack'.
        """
        body = BLOCKS[1]["body"]
        assert "`unmassk-scaffolding`" in body, (
            "unmassk-scaffolding is shipped and tested but missing from the "
            "Protocols menu — Claude can't route to a skill it can't see here"
        )
        trigger_phrases = ("scaffold", "new project", "tech stack", "boilerplate")
        assert any(phrase in body.lower() for phrase in trigger_phrases), (
            "Protocols row for unmassk-scaffolding must reflect its real trigger "
            f"situation from SKILL.md's description (expected one of {trigger_phrases})"
        )

    def test_protocols_block_still_has_original_four_skills(self):
        """Regression guard: adding the 3 new rows must not silently drop any
        of the 4 skills already in the menu (duplicates test_protocols_block_content's
        assertions explicitly, scoped to this contract change so a future
        edit to that test can't accidentally weaken this guarantee)."""
        body = BLOCKS[1]["body"]
        for existing_skill in (
            "unmassk-project-lifecycle",
            "unmassk-grill",
            "unmassk-council",
            "unmassk-close-session",
        ):
            assert existing_skill in body, (
                f"{existing_skill} was dropped from the Protocols menu"
            )

    def test_caveman_removed_from_active_blocks(self):
        """Caveman is no longer an active managed block — it was moved to
        _LEGACY_PATTERNS so upsert strips it from existing CLAUDE.md files
        instead of maintaining it going forward."""
        for b in BLOCKS:
            assert "caveman" not in b["begin"].lower()
            assert "caveman" not in b["body"].lower()
        legacy_names = [name for _, name in _LEGACY_PATTERNS]
        assert "unmassk-caveman" in legacy_names

    def test_communication_block_is_finalised(self):
        """Communication block must contain the finalised rules, not the
        placeholder, plus the two items added when caveman was retired."""
        body = BLOCKS[2]["body"]
        assert "PLACEHOLDER" not in body
        assert "Concise and plain" in body
        assert "Match the user's language" in body
        assert "Verify before claiming" in body
        assert "NOT YAPPING" in body
        assert "Don't assume" in body

    def test_build_mode_block_content(self):
        body = BLOCKS[3]["body"]
        assert "Test-first" in body
        assert "Linear" in body
        assert "Ultron" in body
        assert "Dante" in body


class TestUpsertManagedBlocks:
    def test_empty_content_gets_all_blocks(self):
        content, log = upsert_managed_blocks("")
        assert all_blocks_present(content)
        for b in BLOCKS:
            assert b["begin"] in content
            assert b["end"] in content

    def test_idempotent_on_fresh_content(self):
        content, _ = upsert_managed_blocks("")
        content2, log2 = upsert_managed_blocks(content)
        assert content == content2, "Second upsert changed content (not idempotent)"
        # All log entries should say "up-to-date"
        for entry in log2:
            assert "up-to-date" in entry or "removed" not in entry

    def test_preserves_user_content_above(self):
        user_content = "# My Project\n\nMy own instructions.\n"
        content, _ = upsert_managed_blocks(user_content)
        assert "My own instructions." in content
        assert all_blocks_present(content)

    def test_outdated_block_is_updated(self):
        """A block with stale body gets replaced with current body."""
        # Start with all blocks correct
        content, _ = upsert_managed_blocks("")
        # Corrupt the first block's body
        content = content.replace("unmassk-toolkit Active", "OLD TOOLKIT HEADER")
        assert "OLD TOOLKIT HEADER" in content

        content2, log = upsert_managed_blocks(content)
        assert "OLD TOOLKIT HEADER" not in content2
        assert "unmassk-toolkit Active" in content2
        # Log should mention the update
        assert any("updated" in entry for entry in log)

    def test_foreign_content_inside_block_is_not_silently_discarded(self):
        """DEUDA.md #15 -- hand-written content placed between an existing
        block's own BEGIN/END markers must not vanish without a trace when
        upsert regenerates that block.

        Real incident (2026-08-02): a state note was hand-written inside an
        existing managed block in this project's own CLAUDE.md. The next
        upsert matched BEGIN...END and replaced the whole span with the
        canonical body, discarding the note -- the only log line produced
        was the generic "updated {begin}", which carries no trace of what
        was destroyed. It was recovered by luck from conversation history,
        not from anything the function reported.

        This test writes a distinctive, non-canonical note into one block's
        interior -- text upsert_managed_blocks() never generated, so it
        compares two things written separately: this test's own note vs.
        the function's canonical BLOCKS body -- and asserts the note is
        recoverable from what the function reports afterwards.

        This does NOT assert whether the function should refuse to
        overwrite foreign content or warn-and-overwrite-anyway -- that is
        an open design question, not decided by any document (see report).
        It fixes only what's clear: foreign content must not be swallowed
        in total silence, leaving zero trace of what was lost.
        """
        content, _ = upsert_managed_blocks("")
        build_mode = BLOCKS[3]
        distinctive_note = (
            "STATE NOTE (hand-written, not generated): remember to check "
            "PR #491 with Bex before the next merge."
        )
        content = content.replace(build_mode["body"], distinctive_note)
        assert distinctive_note in content  # fixture sanity check

        _, log = upsert_managed_blocks(content)

        assert any(distinctive_note in entry for entry in log), (
            "Foreign content overwritten inside a managed block left no "
            "trace in the log -- it was destroyed in total silence. "
            f"log was: {log!r}"
        )

    def test_missing_single_block_is_appended(self):
        """If one block is missing, it gets appended (others untouched)."""
        content, _ = upsert_managed_blocks("")
        # Remove the protocols block
        begin = BLOCKS[1]["begin"]
        end = BLOCKS[1]["end"]
        start_idx = content.find(begin)
        end_idx = content.find(end) + len(end)
        content = content[:start_idx] + content[end_idx:]

        assert begin not in content

        content2, log = upsert_managed_blocks(content)
        assert begin in content2
        assert any("appended" in entry for entry in log)

    def test_block_order_preserved_after_upsert(self):
        """After upsert, blocks appear in BLOCKS definition order."""
        content, _ = upsert_managed_blocks("")
        positions = [content.find(b["begin"]) for b in BLOCKS]
        assert positions == sorted(positions), (
            f"Block order violated: positions={positions}"
        )

    def test_legacy_gitmemory_block_removed(self):
        old_content = (
            "<!-- BEGIN unmassk-gitmemory (managed block) -->\n"
            "old content\n"
            "<!-- END unmassk-gitmemory -->\n"
        )
        content, log = upsert_managed_blocks(old_content)
        assert "BEGIN unmassk-gitmemory" not in content
        assert any("removed" in entry and "gitmemory" in entry for entry in log)

    def test_legacy_crew_block_removed(self):
        old_content = (
            "<!-- BEGIN unmassk-crew (managed block) -->\n"
            "old crew stuff\n"
            "<!-- END unmassk-crew -->\n"
        )
        content, log = upsert_managed_blocks(old_content)
        assert "BEGIN unmassk-crew" not in content
        assert any("removed" in entry and "crew" in entry for entry in log)

    def test_caveman_is_legacy_removed(self):
        """A CLAUDE.md that already has a caveman block loses it entirely
        after upsert_managed_blocks — caveman moved from BLOCKS to
        _LEGACY_PATTERNS, so it's stripped like any other legacy block."""
        old_content = (
            "<!-- BEGIN unmassk-caveman (managed block) -->\n"
            "Ultra-compressed mode.\n"
            "<!-- END unmassk-caveman -->\n"
        )
        content, log = upsert_managed_blocks(old_content)
        assert content.count("<!-- BEGIN unmassk-caveman") == 0
        assert content.count("<!-- END unmassk-caveman -->") == 0
        assert any("removed" in entry and "caveman" in entry for entry in log)

    def test_missing_all_blocks_all_appended(self):
        """Content with no blocks gets all 4 appended."""
        user = "# Project\n\nSome docs.\n"
        content, log = upsert_managed_blocks(user)
        assert all_blocks_present(content)
        appended = [e for e in log if "appended" in e]
        assert len(appended) == len(BLOCKS)


class TestHelpers:
    def test_all_blocks_present_true(self):
        content, _ = upsert_managed_blocks("")
        assert all_blocks_present(content) is True

    def test_all_blocks_present_false_when_missing(self):
        content, _ = upsert_managed_blocks("")
        # Remove the last block
        begin = BLOCKS[-1]["begin"]
        end = BLOCKS[-1]["end"]
        idx_b = content.find(begin)
        idx_e = content.find(end) + len(end)
        truncated = content[:idx_b] + content[idx_e:]
        assert all_blocks_present(truncated) is False

    def test_any_block_outdated_false_for_fresh(self):
        content, _ = upsert_managed_blocks("")
        assert any_block_outdated(content) is False

    def test_any_block_outdated_true_when_stale(self):
        content, _ = upsert_managed_blocks("")
        stale = content.replace("unmassk-toolkit Active", "OLD HEADER")
        assert any_block_outdated(stale) is True

    def test_any_block_outdated_true_when_missing(self):
        content, _ = upsert_managed_blocks("")
        begin = BLOCKS[2]["begin"]
        end = BLOCKS[2]["end"]
        idx_b = content.find(begin)
        idx_e = content.find(end) + len(end)
        trimmed = content[:idx_b] + content[idx_e:]
        assert any_block_outdated(trimmed) is True


# ── Integration tests: install writes 4 blocks ───────────────────────────

class TestInstallFourBlocks:
    def test_install_creates_all_four_blocks(self, tmp_path):
        """After install, CLAUDE.md contains all 4 managed blocks."""
        repo = _make_repo(tmp_path)
        rc, _, _ = run_script(INSTALL, repo, ["--auto"])
        assert rc == 0

        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert all_blocks_present(content), (
            "Install must write all 4 managed blocks to CLAUDE.md"
        )

    def test_install_block_content_is_correct(self, tmp_path):
        """Each block's body matches the canonical definition."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, ["--auto"])

        with open(os.path.join(repo, "CLAUDE.md"), encoding="utf-8") as f:
            content = f.read()

        assert not any_block_outdated(content), (
            "Installed blocks should not be flagged as outdated immediately after install"
        )

    def test_install_is_idempotent(self, tmp_path):
        """Running install twice produces the same CLAUDE.md."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, ["--auto"])

        with open(os.path.join(repo, "CLAUDE.md"), encoding="utf-8") as f:
            content_after_first = f.read()

        run_script(INSTALL, repo, ["--auto"])

        with open(os.path.join(repo, "CLAUDE.md"), encoding="utf-8") as f:
            content_after_second = f.read()

        assert content_after_first == content_after_second, (
            "Second install changed CLAUDE.md — not idempotent"
        )

    def test_install_preserves_user_content(self, tmp_path):
        """Install does not wipe existing non-managed content in CLAUDE.md."""
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write("# My Project\n\nCustom instructions here.\n")

        run_script(INSTALL, repo, ["--auto"])

        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert "Custom instructions here." in content
        assert all_blocks_present(content)

    def test_install_over_one_existing_block_appends_rest(self, tmp_path):
        """If only the first block is present, install appends the other 3."""
        repo = _make_repo(tmp_path)
        # Write only the first block
        claude_md = os.path.join(repo, "CLAUDE.md")
        b0 = BLOCKS[0]
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(f"{b0['begin']}\n{b0['body']}\n{b0['end']}\n")

        run_script(INSTALL, repo, ["--auto"])

        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert all_blocks_present(content), (
            "After install over partial CLAUDE.md, all 4 blocks must be present"
        )


# ── Integration tests: session-start-crew hook ───────────────────────────

class TestCrewHookFourBlocks:
    def test_crew_hook_creates_all_four_blocks(self, tmp_path):
        """session-start-crew.py writes all 4 blocks when CLAUDE.md is absent."""
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0, f"crew hook failed: {stderr}"

        claude_md = os.path.join(repo, "CLAUDE.md")
        assert os.path.isfile(claude_md), "crew hook must create CLAUDE.md"

        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert all_blocks_present(content), (
            "crew hook must write all 4 managed blocks"
        )

    def test_crew_hook_updates_outdated_block(self, tmp_path):
        """crew hook replaces stale block body with canonical version."""
        repo = _make_repo(tmp_path)
        # Write a stale first block
        claude_md = os.path.join(repo, "CLAUDE.md")
        b0 = BLOCKS[0]
        stale_body = "## unmassk-toolkit Active\n\nOLD VERSION OF INSTRUCTIONS."
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(f"{b0['begin']}\n{stale_body}\n{b0['end']}\n")

        rc, stdout, _ = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0

        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert "OLD VERSION OF INSTRUCTIONS" not in content
        assert "unmassk-core" in content
        assert all_blocks_present(content)

    def test_crew_hook_is_idempotent(self, tmp_path):
        """Running crew hook twice produces identical CLAUDE.md."""
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")

        run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        with open(claude_md, encoding="utf-8") as f:
            content_first = f.read()

        run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        with open(claude_md, encoding="utf-8") as f:
            content_second = f.read()

        assert content_first == content_second, (
            "Running crew hook twice must produce identical output"
        )

    def test_crew_hook_non_git_repo_exits_cleanly(self, tmp_path):
        """crew hook in a non-git directory exits 0 without error."""
        non_git = str(tmp_path / "not_a_repo")
        os.makedirs(non_git)
        rc, stdout, stderr = run_cmd([sys.executable, CREW_HOOK], cwd=non_git)
        assert rc == 0
        assert "Not a git repo" in stdout


# ── Integration tests: uninstall removes all 4 blocks ────────────────────
#
# Retirement note (2026-08-02): both tests that lived in this section are
# gone now. test_uninstall_removes_all_four_blocks was removed first
# (invoked bin/git-memory-uninstall.py, which no longer exists on disk --
# §5.4, "ya estaban muertos" -- retired per §9.3). test_uninstall_preserves
# _user_content followed on the same grounds, per Yoda's call: it invoked
# the same dead script and never asserted on its return code, so
# run_script(UNINSTALL, ...) being a permanent no-op (dead script,
# FileNotFoundError before any code runs) made its one assertion ("User
# notes here." still present) trivially true regardless of whether
# uninstall ever ran. PIEZAS.md §3.1's rule -- a test survives only if the
# code it exercises still runs -- settles it: the code is gone, so does
# the test, even though it happened to stay green. §9.3 applies the same
# way it did to its sibling above.
