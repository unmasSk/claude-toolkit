"""
Tests for the 5-block managed CLAUDE.md behavior.

Covers:
- All 5 blocks present after install
- Each block has the correct content
- upsert_managed_blocks() is idempotent
- Outdated block is updated in place
- Missing block is appended at end
- Block order is preserved
- Legacy blocks are removed
- session-start-crew.py writes all 5 blocks
- Uninstall removes all 5 blocks
- any_block_outdated / all_blocks_present helpers
"""

import json
import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, UNINSTALL, git_cmd, run_script, run_cmd

# Make lib/ importable
LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import (  # noqa: E402
    BLOCKS,
    upsert_managed_blocks,
    all_blocks_present,
    any_block_outdated,
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
    def test_exactly_five_blocks(self):
        assert len(BLOCKS) == 5

    def test_block_ids(self):
        """Each block has a distinct begin marker."""
        begins = [b["begin"] for b in BLOCKS]
        assert len(set(begins)) == 5, "Duplicate begin markers"

    def test_first_block_is_toolkit(self):
        assert "unmassk-toolkit" in BLOCKS[0]["begin"]

    def test_block_order(self):
        expected_ids = [
            "unmassk-toolkit",
            "unmassk-protocols",
            "unmassk-caveman",
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
        """First block must contain the boot instructions."""
        body = BLOCKS[0]["body"]
        assert "unmassk-toolkit Active" in body
        assert "unmassk-core" in body
        assert "unmassk-gitmemory" in body
        assert "CALIBRATION.md" in body

    def test_protocols_block_content(self):
        body = BLOCKS[1]["body"]
        assert "unmassk-project-lifecycle" in body
        assert "unmassk-grill" in body
        assert "unmassk-council" in body
        assert "unmassk-close-session" in body

    def test_caveman_block_content(self):
        body = BLOCKS[2]["body"]
        assert "caveman" in body
        assert "/caveman" in body

    def test_communication_block_is_placeholder(self):
        """PLACEHOLDER block must be included as-is."""
        body = BLOCKS[3]["body"]
        assert "PLACEHOLDER" in body

    def test_build_mode_block_content(self):
        body = BLOCKS[4]["body"]
        assert "Test-first" in body
        assert "Linear" in body
        assert "Ultron" in body
        assert "Dante" in body


class TestUpsertManagedBlocks:
    def test_empty_content_gets_all_blocks(self):
        content, log = upsert_managed_blocks("")
        assert all_blocks_present(content)
        assert len(BLOCKS) == 5
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

    def test_missing_all_blocks_all_appended(self):
        """Content with no blocks gets all 5 appended."""
        user = "# Project\n\nSome docs.\n"
        content, log = upsert_managed_blocks(user)
        assert all_blocks_present(content)
        appended = [e for e in log if "appended" in e]
        assert len(appended) == 5


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


# ── Integration tests: install writes 5 blocks ───────────────────────────

class TestInstallFiveBlocks:
    def test_install_creates_all_five_blocks(self, tmp_path):
        """After install, CLAUDE.md contains all 5 managed blocks."""
        repo = _make_repo(tmp_path)
        rc, _, _ = run_script(INSTALL, repo, ["--auto"])
        assert rc == 0

        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md) as f:
            content = f.read()

        assert all_blocks_present(content), (
            "Install must write all 5 managed blocks to CLAUDE.md"
        )

    def test_install_block_content_is_correct(self, tmp_path):
        """Each block's body matches the canonical definition."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, ["--auto"])

        with open(os.path.join(repo, "CLAUDE.md")) as f:
            content = f.read()

        assert not any_block_outdated(content), (
            "Installed blocks should not be flagged as outdated immediately after install"
        )

    def test_install_is_idempotent(self, tmp_path):
        """Running install twice produces the same CLAUDE.md."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, ["--auto"])

        with open(os.path.join(repo, "CLAUDE.md")) as f:
            content_after_first = f.read()

        run_script(INSTALL, repo, ["--auto"])

        with open(os.path.join(repo, "CLAUDE.md")) as f:
            content_after_second = f.read()

        assert content_after_first == content_after_second, (
            "Second install changed CLAUDE.md — not idempotent"
        )

    def test_install_preserves_user_content(self, tmp_path):
        """Install does not wipe existing non-managed content in CLAUDE.md."""
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md, "w") as f:
            f.write("# My Project\n\nCustom instructions here.\n")

        run_script(INSTALL, repo, ["--auto"])

        with open(claude_md) as f:
            content = f.read()

        assert "Custom instructions here." in content
        assert all_blocks_present(content)

    def test_install_over_one_existing_block_appends_rest(self, tmp_path):
        """If only the first block is present, install appends the other 4."""
        repo = _make_repo(tmp_path)
        # Write only the first block
        claude_md = os.path.join(repo, "CLAUDE.md")
        b0 = BLOCKS[0]
        with open(claude_md, "w") as f:
            f.write(f"{b0['begin']}\n{b0['body']}\n{b0['end']}\n")

        run_script(INSTALL, repo, ["--auto"])

        with open(claude_md) as f:
            content = f.read()

        assert all_blocks_present(content), (
            "After install over partial CLAUDE.md, all 5 blocks must be present"
        )


# ── Integration tests: session-start-crew hook ───────────────────────────

class TestCrewHookFiveBlocks:
    def test_crew_hook_creates_all_five_blocks(self, tmp_path):
        """session-start-crew.py writes all 5 blocks when CLAUDE.md is absent."""
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0, f"crew hook failed: {stderr}"

        claude_md = os.path.join(repo, "CLAUDE.md")
        assert os.path.isfile(claude_md), "crew hook must create CLAUDE.md"

        with open(claude_md) as f:
            content = f.read()

        assert all_blocks_present(content), (
            "crew hook must write all 5 managed blocks"
        )

    def test_crew_hook_updates_outdated_block(self, tmp_path):
        """crew hook replaces stale block body with canonical version."""
        repo = _make_repo(tmp_path)
        # Write a stale first block
        claude_md = os.path.join(repo, "CLAUDE.md")
        b0 = BLOCKS[0]
        stale_body = "## unmassk-toolkit Active\n\nOLD VERSION OF INSTRUCTIONS."
        with open(claude_md, "w") as f:
            f.write(f"{b0['begin']}\n{stale_body}\n{b0['end']}\n")

        rc, stdout, _ = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0

        with open(claude_md) as f:
            content = f.read()

        assert "OLD VERSION OF INSTRUCTIONS" not in content
        assert "unmassk-core" in content
        assert all_blocks_present(content)

    def test_crew_hook_is_idempotent(self, tmp_path):
        """Running crew hook twice produces identical CLAUDE.md."""
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")

        run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        with open(claude_md) as f:
            content_first = f.read()

        run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        with open(claude_md) as f:
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


# ── Integration tests: uninstall removes all 5 blocks ────────────────────

class TestUninstallFiveBlocks:
    def test_uninstall_removes_all_five_blocks(self, tmp_path):
        """After uninstall, CLAUDE.md has no managed block markers."""
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, ["--auto"])
        run_script(UNINSTALL, repo, ["--auto"])

        claude_md = os.path.join(repo, "CLAUDE.md")
        if os.path.isfile(claude_md):
            with open(claude_md) as f:
                content = f.read()
            for b in BLOCKS:
                assert b["begin"] not in content, (
                    f"Uninstall left block '{b['begin']}' in CLAUDE.md"
                )
                assert b["end"] not in content, (
                    f"Uninstall left end marker '{b['end']}' in CLAUDE.md"
                )

    def test_uninstall_preserves_user_content(self, tmp_path):
        """Uninstall removes blocks but preserves user content in CLAUDE.md."""
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md, "w") as f:
            f.write("# My Project\n\nUser notes here.\n")

        run_script(INSTALL, repo, ["--auto"])
        run_script(UNINSTALL, repo, ["--auto"])

        if os.path.isfile(claude_md):
            with open(claude_md) as f:
                content = f.read()
            assert "User notes here." in content
