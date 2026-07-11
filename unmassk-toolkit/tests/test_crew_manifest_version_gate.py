"""
Acceptance contract (test-first, RED) for issue #63 point 1 — boot
simplification plan (docs/plan/refactor-boot-simplification.md), Bilbo's
map (.claude/agent-memory/unmassk-toolkit-bilbo/boot-simplification-63-map.md
section 1).

Code under test: hooks/session-start-crew.py — today calls
upsert_managed_blocks(content) UNCONDITIONALLY on every SessionStart
(line ~61), diffing the whole CLAUDE.md against the 5 canonical blocks
every single boot regardless of whether anything actually changed since
the last successful install/upgrade.

NEW CONTRACT (decision 0f5af98 + Bilbo's map, section 1):
  - manifest.json's "version" field == the running plugin's VERSION
    (lib/version.py) -> session-start-crew.py must NOT rewrite CLAUDE.md
    at all. Content AND mtime stay exactly as they were before the hook
    ran (fail-open still means "trust the version marker", not "diff
    anyway just in case").
  - manifest.json's version differs from VERSION, OR the manifest is
    absent/corrupt/unreadable -> the hook MUST still regenerate (fail-open:
    an untrustworthy version signal must never silently freeze a stale
    CLAUDE.md forever).

Only the "skip" case is genuinely new behavior — today's hook has no
manifest-awareness at all (confirmed by Bilbo: `grep -n "manifest"
hooks/session-start-crew.py` returns nothing), so it is the only test in
this file expected to fail (RED) against the unmodified hook. The two
"regenerate" tests encode existing, already-correct behavior (today's
hook always rewrites unconditionally) — they exist here as part of the
same acceptance contract and as a regression guard: the new gate must not
accidentally suppress regeneration for the cases where it's still
required.

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity only — no exhaustive branch coverage here (see EXHAUSTION
PROTOCOL note in Dante's operating rules; the hardening pass runs after
Ultron implements).

NO production code is touched by this file. Only tests.
"""

import json
import os
import sys
import time

import pytest

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, git_cmd, run_script, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import BLOCKS, all_blocks_present  # noqa: E402
from version import VERSION  # noqa: E402

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


def _set_manifest_version(repo, version):
    """Read-modify-write manifest.json's "version" key, preserving every
    other field install --auto already wrote (matches the shape a real
    manifest has — never a hand-typed minimal stand-in, unmassk-standards
    §34's spirit applied to fixture realism even outside a producer/
    consumer round-trip)."""
    path = _manifest_path(repo)
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    data["version"] = version
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


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


# ── New behavior: manifest.version == VERSION -> skip entirely (RED) ──────


class TestManifestVersionMatchSkipsRewrite:
    def test_matching_manifest_version_skips_rewrite_even_with_stale_block(self, tmp_path):
        """Genuinely new contract: when the manifest already claims the
        current plugin version, the crew hook must trust that signal and
        skip regeneration ENTIRELY -- not just "skip when content happens
        to already be correct". Staling the block first proves the skip is
        driven by the version check, not by there being nothing to change.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        with open(_manifest_path(repo), encoding="utf-8") as f:
            installed_version = json.load(f)["version"]
        assert installed_version == VERSION, (
            "precondition: a fresh install --auto must write manifest.version == VERSION"
        )

        stale_content = _stale_first_block(repo)
        claude_md = _claude_md_path(repo)
        mtime_before = os.path.getmtime(claude_md)
        # Filesystem mtime resolution can be as coarse as 1s on some hosts;
        # give a rewrite (if one incorrectly happens) room to be observable.
        time.sleep(1.1)

        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0. stderr={stderr!r}"

        with open(claude_md, encoding="utf-8") as f:
            content_after = f.read()
        mtime_after = os.path.getmtime(claude_md)

        assert content_after == stale_content, (
            "manifest.version == VERSION must skip regeneration entirely -- "
            f"CLAUDE.md content changed anyway. stdout={stdout!r}"
        )
        assert mtime_after == mtime_before, (
            "CLAUDE.md must not be rewritten (mtime must stay intact) when "
            "manifest.version already matches the running plugin version"
        )


# ── Existing (already-correct) behavior: version mismatch -> regenerate ───


class TestManifestVersionMismatchStillRegenerates:
    def test_older_manifest_version_regenerates_stale_block(self, tmp_path):
        repo = _make_repo(tmp_path)
        _install(repo)
        _stale_first_block(repo)
        _set_manifest_version(repo, "0.0.1")

        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0. stderr={stderr!r}"

        with open(_claude_md_path(repo), encoding="utf-8") as f:
            content_after = f.read()

        assert STALE_MARKER not in content_after, (
            "manifest.version != VERSION must still regenerate the stale "
            "block (fail-open on an untrustworthy version signal)"
        )
        assert all_blocks_present(content_after)


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
