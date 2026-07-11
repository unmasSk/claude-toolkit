"""
SUPERSEDED CONTRACT NOTICE (decision 2d56444, git show 2d56444):

This file originally carried the v1 acceptance contract for issue #63
point 1 (manifest.json's "version" field matching VERSION -> skip
rewriting CLAUDE.md entirely, even if a managed block was stale/altered).
Moriarty broke that contract with 3 live T1 PoCs (documented in
.claude/agent-memory/unmassk-toolkit-moriarty/MEMORY.md, "issue #63 Last
attack"): a version match is only proof "an install ran once", never
proof "CLAUDE.md's content is correct right now". Decision 2d56444
replaced it with the v2 content-based gate: the hook ALWAYS reads and
diffs CLAUDE.md's managed blocks against the canonical ones and skips
ONLY the write when content already matches -- manifest.json's version
field plays no role in that decision anymore.

`TestManifestVersionMatchSkipsRewrite` (asserted: version match + stale
block -> skip, content stays stale) has been RETIRED -- it asserted the
exact behavior 2d56444 reverses. `TestManifestVersionMismatchStillRegenerates`
has also been RETIRED as redundant: content-staleness now triggers
regeneration unconditionally, and the harder/adversarial case (matching
version + poisoned block still regenerates) is already covered by
test_crew_content_gate_v2.py::TestPoisonedBlockWithMatchingManifestStillRegenerates,
which strictly subsumes this file's former mismatched-version scenario.
See test_crew_content_gate_v2.py for the current v2 acceptance contract
(4 tests covering all 3 of Moriarty's PoCs plus the "don't lose the
optimization" control).

What remains in this file (`TestManifestAbsentOrCorruptStillRegenerates`)
is NOT part of the retired version-gate contract: it asserts that a
missing or corrupt manifest.json never blocks CLAUDE.md regeneration --
a robustness/regression guard that stays true (and is not otherwise
covered by test_crew_content_gate_v2.py, which never exercises a
missing/corrupt manifest fixture) regardless of whether the gate is
version-based or content-based.

NO production code is touched by this file. Only tests.
"""

import os
import sys

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, git_cmd, run_script, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import BLOCKS, all_blocks_present  # noqa: E402

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")

STALE_MARKER = "OLD VERSION OF INSTRUCTIONS."


# ── Repo helpers ──────────────────────────────────────────────────────────


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _install(repo):
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"install --auto failed: {out}\n{err}"


def _manifest_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "manifest.json")


def _claude_md_path(repo):
    return os.path.join(repo, "CLAUDE.md")


def _corrupt_manifest(repo):
    with open(_manifest_path(repo), "w", encoding="utf-8") as f:
        f.write("{ this is not valid json !!!")


def _stale_first_block(repo):
    """Force a real, observable diff opportunity: patch the first managed
    block's body so it no longer matches the canonical content
    upsert_managed_blocks() would write. Mirrors
    test_managed_blocks.py::TestCrewHookFiveBlocks::
    test_crew_hook_updates_outdated_block's fixture shape. Returns the
    full CLAUDE.md content after staling, for later exact-equality checks.
    """
    claude_md = _claude_md_path(repo)
    with open(claude_md, encoding="utf-8") as f:
        content = f.read()

    b0 = BLOCKS[0]
    begin = content.find(b0["begin"])
    end = content.find(b0["end"])
    assert begin != -1 and end != -1, "installed CLAUDE.md must contain the first managed block"
    end += len(b0["end"])

    staled = f"{b0['begin']}\n{STALE_MARKER}\n{b0['end']}"
    content = content[:begin] + staled + content[end:]
    with open(claude_md, "w", encoding="utf-8") as f:
        f.write(content)
    return content


def _run_crew(repo):
    return run_cmd([sys.executable, CREW_HOOK], cwd=repo)


# ── Retired (v1 contract, decision 2d56444 reverses it) ────────────────────
#
# TestManifestVersionMatchSkipsRewrite and TestManifestVersionMismatchStillRegenerates
# lived here. See the module docstring above for why both were removed
# instead of adapted: the first asserted the exact behavior 2d56444
# reverses; the second became a strictly weaker duplicate of
# test_crew_content_gate_v2.py::TestPoisonedBlockWithMatchingManifestStillRegenerates
# once the gate stopped caring about manifest.json's version at all.


# ── Existing (already-correct) behavior: missing/corrupt manifest -> regenerate (fail-open) ──


class TestManifestAbsentOrCorruptStillRegenerates:
    def test_missing_manifest_regenerates_stale_block(self, tmp_path):
        repo = _make_repo(tmp_path)
        _install(repo)
        _stale_first_block(repo)
        os.remove(_manifest_path(repo))

        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0. stderr={stderr!r}"

        with open(_claude_md_path(repo), encoding="utf-8") as f:
            content_after = f.read()

        assert STALE_MARKER not in content_after, (
            "a missing manifest must fail OPEN (regenerate), never freeze "
            "a stale CLAUDE.md silently"
        )
        assert all_blocks_present(content_after)

    def test_corrupt_manifest_regenerates_stale_block(self, tmp_path):
        repo = _make_repo(tmp_path)
        _install(repo)
        _stale_first_block(repo)
        _corrupt_manifest(repo)

        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0. stderr={stderr!r}"

        with open(_claude_md_path(repo), encoding="utf-8") as f:
            content_after = f.read()

        assert STALE_MARKER not in content_after, (
            "corrupt JSON in the manifest must fail OPEN (regenerate), "
            "never freeze a stale CLAUDE.md silently"
        )
        assert all_blocks_present(content_after)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
