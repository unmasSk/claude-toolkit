"""
Tests for the managed CLAUDE.md blocks.

Covers:
- All blocks present after install (three since #89 retired build-mode)
- Each block has the correct content
- upsert_managed_blocks() is idempotent
- Outdated block is updated in place
- Missing block is appended at end
- Block order is preserved
- Legacy blocks (including the retired caveman block) are removed
- session-start-crew.py writes every block
- any_block_outdated / all_blocks_present helpers
"""

import json
import os
import re
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
    def test_exactly_three_blocks(self):
        """#89 3.1: build-mode left the active blocks (it lives in unmassk-flow)."""
        assert len(BLOCKS) == 3

    def test_block_ids(self):
        """Each block has a distinct begin marker."""
        begins = [b["begin"] for b in BLOCKS]
        assert len(set(begins)) == len(BLOCKS), "Duplicate begin markers"

    def test_first_block_is_toolkit(self):
        assert "unmassk-toolkit" in BLOCKS[0]["begin"]

    def test_block_order(self):
        expected_ids = [
            "unmassk-toolkit",
            "unmassk-protocols",
            "unmassk-communication",
        ]
        assert len(BLOCKS) == len(expected_ids)
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
        # #89 3.1: the "NOT YAPPING" label was folded into the short line;
        # its rule (answer the minimum) must survive.
        assert "the minimum" in body
        assert "Don't assume" in body


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
        target = BLOCKS[-1]
        distinctive_note = (
            "STATE NOTE (hand-written, not generated): remember to check "
            "PR #491 with Bex before the next merge."
        )
        content = content.replace(target["body"], distinctive_note)
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
        """Content with no blocks gets every block appended."""
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


# ── Integration tests: install writes every block ───────────────────────────

class TestInstallAllBlocks:
    def test_install_creates_all_blocks(self, tmp_path):
        """After install, CLAUDE.md contains every managed block."""
        repo = _make_repo(tmp_path)
        rc, _, _ = run_script(INSTALL, repo, ["--auto"])
        assert rc == 0

        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert all_blocks_present(content), (
            "Install must write every managed block to CLAUDE.md"
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
            "After install over partial CLAUDE.md, every block must be present"
        )


# ── Integration tests: session-start-crew hook ───────────────────────────

class TestCrewHookAllBlocks:
    def test_crew_hook_creates_all_blocks(self, tmp_path):
        """session-start-crew.py writes every block when CLAUDE.md is absent."""
        repo = _make_repo(tmp_path)
        rc, stdout, stderr = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0, f"crew hook failed: {stderr}"

        claude_md = os.path.join(repo, "CLAUDE.md")
        assert os.path.isfile(claude_md), "crew hook must create CLAUDE.md"

        with open(claude_md, encoding="utf-8") as f:
            content = f.read()

        assert all_blocks_present(content), (
            "crew hook must write every managed block"
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


# ── Integration tests: uninstall removes every block ────────────────────
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


# ── Contract #89 3.1: the shorter managed block ──────────────────────────
#
# Owner-approved (#89 point 3, rebased 2026-10-19): rules import and the
# file-based boot step stay; the protocols menu is one line per situation;
# the progress-line rule leaves communication (it lives in core, rule 1);
# build-mode is retired as a legacy block (unmassk-flow carries it).

_SKILL_RE = re.compile(r"`(unmassk-[a-z-]+)`")

# The eight protocol skills the menu routes to (owner's short menu, #89).
_MENU_SKILLS = (
    "unmassk-project-lifecycle",
    "unmassk-scaffolding",
    "unmassk-grill",
    "unmassk-council",
    "unmassk-flow",
    "unmassk-audit",
    "unmassk-groundhog",
    "unmassk-close-session",
)

# Hand-written copy of the block every project carries today; markers are
# the exact strings the generator shipped.
_OLD_BUILD_MODE_BLOCK = (
    "<!-- BEGIN unmassk-build-mode (managed block) -->\n"
    "## Build mode (you decide, before delegating)\n"
    "\n"
    "- **Test-first** → Dante writes failing tests → Ultron implements.\n"
    "- **Linear** → Ultron implements → Dante tests.\n"
    "<!-- END unmassk-build-mode -->"
)


def _block(name):
    return next(b for b in BLOCKS if name in b["begin"])


def _bullets(body):
    return [ln for ln in body.splitlines() if ln.lstrip().startswith("- ")]


def _line_naming(body, skill):
    lines = [ln for ln in body.splitlines() if f"`{skill}`" in ln]
    assert len(lines) == 1, f"{skill} expected on exactly one line, got {lines!r}"
    return lines[0]


def _rendered(block):
    return f"{block['begin']}\n{block['body']}\n{block['end']}"


class TestShortToolkitBlock:
    """Green on purpose: what #89 must not lose from the first block."""

    def test_should_keep_rules_import_on_its_own_line(self):
        lines = [ln.strip() for ln in _block("unmassk-toolkit")["body"].splitlines()]
        assert "@.claude/project-memory/rules.md" in lines

    def test_should_keep_file_based_boot_report_step_with_boot_failed_clause(self):
        body = " ".join(_block("unmassk-toolkit")["body"].split())
        assert "`[memory]`" in body
        assert "the boot failed" in body
        assert "already in your context" not in body

    def test_should_keep_the_four_rules(self):
        body = _block("unmassk-toolkit")["body"]
        tail = body.split("Four rules", 1)[1]
        assert len(_bullets(tail)) == 4
        for anchor in (
            "Memory is a commit",
            "zone list are written by the commands",
            "restriction is retired by asking the user",
            "Never ask the user to run a command",
        ):
            assert anchor in tail, anchor


class TestShortProtocolsMenu:
    def test_should_name_each_protocol_skill_exactly_once(self):
        named = _SKILL_RE.findall(_block("unmassk-protocols")["body"])
        assert sorted(named) == sorted(_MENU_SKILLS), named

    def test_should_be_one_bullet_per_situation(self):
        body = _block("unmassk-protocols")["body"]
        bullets = _bullets(body)
        assert len(bullets) == len(_MENU_SKILLS), bullets
        for ln in bullets:
            assert len(_SKILL_RE.findall(ln)) == 1, ln

    def test_should_fit_heading_bullets_and_footer_only(self):
        body = _block("unmassk-protocols")["body"]
        non_empty = [ln for ln in body.splitlines() if ln.strip()]
        assert len(non_empty) <= len(_MENU_SKILLS) + 2, non_empty

    def test_flow_line_should_point_to_the_build_mode_decision(self):
        line = _line_naming(_block("unmassk-protocols")["body"], "unmassk-flow")
        assert "build mode" in line.lower(), line

    def test_lifecycle_line_should_keep_state_the_situation_in_one_line(self):
        line = _line_naming(
            _block("unmassk-protocols")["body"], "unmassk-project-lifecycle")
        assert "situation" in line.lower() and "one line" in line.lower(), line

    def test_groundhog_line_should_keep_owner_approval(self):
        line = _line_naming(_block("unmassk-protocols")["body"], "unmassk-groundhog")
        assert "approv" in line.lower(), line

    def test_should_keep_output_to_memory_never_md_files(self):
        body = _block("unmassk-protocols")["body"]
        assert "**memory**" in body and "`.md`" in body


class TestShortCommunicationBlock:
    def test_should_drop_the_progress_line_rule(self):
        body = _block("unmassk-communication")["body"].lower()
        assert "numbered line" not in body
        assert "agent or step" not in body

    def test_should_keep_rules_core_does_not_say(self):
        body = _block("unmassk-communication")["body"].lower()
        for anchor in (
            "structural changes",
            "irreversible",
            "one thing at a time",
            "contradictions",
        ):
            assert anchor in body, anchor


class TestBuildModeRetired:
    def test_should_not_be_an_active_block(self):
        for b in BLOCKS:
            assert "build-mode" not in b["begin"]
            assert "## Build mode" not in b["body"]

    def test_should_be_a_legacy_pattern(self):
        assert "unmassk-build-mode" in [name for _, name in _LEGACY_PATTERNS]

    def test_upsert_should_strip_old_block_keep_user_text_and_log_it(self):
        old = (
            "# My Project\n\nUser line above.\n\n"
            + _OLD_BUILD_MODE_BLOCK
            + "\n\nUser line below.\n"
        )
        content, log = upsert_managed_blocks(old)
        assert "unmassk-build-mode" not in content
        assert "## Build mode" not in content
        assert "User line above." in content and "User line below." in content
        assert any("removed" in e and "build-mode" in e for e in log), log
        assert all_blocks_present(content) and not any_block_outdated(content)

    def test_crew_hook_should_retire_it_from_a_project_claude_md(self, tmp_path):
        """User's door: the every-start hook over a CLAUDE.md shaped like today's."""
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")
        today = "\n\n".join(
            ["# My Project\n\nOwn rules here."]
            + [_rendered(b) for b in BLOCKS if "build-mode" not in b["begin"]]
            + [_OLD_BUILD_MODE_BLOCK, "Trailing user note."]
        ) + "\n"
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(today)

        rc, _, stderr = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0, stderr
        with open(claude_md, encoding="utf-8") as f:
            first = f.read()

        assert "unmassk-build-mode" not in first
        assert "## Build mode" not in first
        assert "Own rules here." in first and "Trailing user note." in first
        assert all_blocks_present(first) and not any_block_outdated(first)

        run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        with open(claude_md, encoding="utf-8") as f:
            assert f.read() == first


# ── #89 fix pass (Argus SEC-LOW-001): retiring a block is local and lossless ──
#
# Retiring build-mode fires once in every project. The cut must touch only
# the block: the owner's own blank-line runs elsewhere stay byte for byte,
# and text the owner hand-wrote inside the retired block is logged verbatim,
# like the update path does for an active block (DEUDA #15).

# Owner text with runs of 3+ newlines outside any block (a fenced snippet
# and a spaced paragraph), written here by hand.
_OWNER_SPACED_TEXT = (
    "# Mine\n\n\n\nSpaced paragraph.\n\n\n\n"
    "```\nline a\n\n\n\nline b\n```\n"
)

_OWNER_EDIT_LINE = "Owner note: in this repo, Moriarty always runs on payments."

_EDITED_BUILD_MODE_BLOCK = _OLD_BUILD_MODE_BLOCK.replace(
    "<!-- END unmassk-build-mode -->",
    _OWNER_EDIT_LINE + "\n<!-- END unmassk-build-mode -->",
)


def _current_blocks_text():
    return "\n\n".join(_rendered(b) for b in BLOCKS)


class TestBuildModeRetirementIsLocalAndLossless:
    def test_should_keep_owner_blank_line_runs_elsewhere_when_retiring(self):
        # Bug caught: the post-removal collapse runs over the whole file and
        # squeezes the owner's own 3+ newline runs (inside a code fence too).
        old = (
            _OWNER_SPACED_TEXT + "\n" + _current_blocks_text()
            + "\n\n" + _OLD_BUILD_MODE_BLOCK + "\n"
        )
        content, _ = upsert_managed_blocks(old)
        assert "unmassk-build-mode" not in content
        assert _OWNER_SPACED_TEXT in content, repr(content)

    def test_should_keep_owner_blank_line_runs_below_the_retired_block(self):
        # Bug caught: same collapse, on owner text that sits after the cut.
        old = (
            _current_blocks_text() + "\n\n" + _OLD_BUILD_MODE_BLOCK
            + "\n\n" + _OWNER_SPACED_TEXT
        )
        content, _ = upsert_managed_blocks(old)
        assert "unmassk-build-mode" not in content
        assert _OWNER_SPACED_TEXT in content, repr(content)

    def test_should_log_owner_text_inside_retired_block_verbatim(self):
        # Bug caught: hand-written text between the retired markers is
        # deleted and the log only says "removed", so it is unrecoverable.
        old = (
            "# My Project\n\n" + _current_blocks_text()
            + "\n\n" + _EDITED_BUILD_MODE_BLOCK + "\n"
        )
        content, log = upsert_managed_blocks(old)
        assert _OWNER_EDIT_LINE not in content
        removal = [e for e in log if "build-mode" in e]
        assert any(_OWNER_EDIT_LINE in e for e in removal), log

    def _run_crew_over_edited_spaced_file(self, tmp_path):
        repo = _make_repo(tmp_path)
        claude_md = os.path.join(repo, "CLAUDE.md")
        with open(claude_md, "w", encoding="utf-8") as f:
            f.write(
                _OWNER_SPACED_TEXT + "\n" + _current_blocks_text()
                + "\n\n" + _EDITED_BUILD_MODE_BLOCK + "\n"
            )
        rc, stdout, stderr = run_cmd([sys.executable, CREW_HOOK], cwd=repo)
        assert rc == 0, stderr
        with open(claude_md, encoding="utf-8") as f:
            return f.read(), stdout

    def test_crew_hook_should_keep_owner_spacing_when_retiring(self, tmp_path):
        """User's door: the every-start hook over a spaced CLAUDE.md."""
        after, _ = self._run_crew_over_edited_spaced_file(tmp_path)
        assert "unmassk-build-mode" not in after
        assert _OWNER_SPACED_TEXT in after, repr(after)

    def test_crew_hook_should_print_owner_edit_from_retired_block(self, tmp_path):
        """User's door: the owner's hand edit is in the hook's output."""
        after, stdout = self._run_crew_over_edited_spaced_file(tmp_path)
        assert _OWNER_EDIT_LINE not in after
        assert _OWNER_EDIT_LINE in stdout, stdout
