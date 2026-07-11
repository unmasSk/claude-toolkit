"""
Acceptance contract (test-first, RED) for issue #63, decision 1d623da:
2 pre-existing T1 bugs found by Moriarty round 2 against the P1 v2 content
gate (decision 2d56444), that directly contradict that gate's own stated
goal ("veneno -> regenera") or #63's own stated goal (a boot-simplification
PR must not make boot MORE expensive). Both confirmed byte-identical on
main -- neither is new in this branch, but the decision explicitly phases
their fix into this batch instead of deferring.

  T1-A -- lib/managed_blocks.py:190 upsert_managed_blocks() checks only
  `begin in content`, never that `end` is ALSO present. Deleting a block's
  END marker (merge-conflict resolution, editor auto-fix, accidental line
  delete) leaves a dangling BEGIN with no matching END. The begin...end
  regex can't match, `pattern.sub` no-ops, and the code logs
  "up-to-date {begin}" -- a lie: the block is permanently corrupted and
  hooks/session-start-crew.py prints "[crew] All managed blocks up to
  date" forever, since the write only fires on a diff and there never is
  one. Defeats decision 2d56444's whole point for exactly the malformed
  case that gate was built to catch.

  T1-B -- lib/upgrade_check.py:102 needs_upgrade() Check 1 requires the
  literal string "Context Checkpoint Commits" inside the managed block to
  consider it current. That string has NEVER existed in real production
  content (`git log --all -S"Context Checkpoint Commits"` = 0 hits in
  managed_blocks.py / git-memory-install.py -- only test fixtures fake
  it, one commit message literally admitting "neutraliza Check 1... en
  vez de arreglarlo"). Effect: a from-scratch, 100% canonical install
  with manifest.version == VERSION still gets needs_upgrade()==True,
  forever -- trigger_auto_upgrade_if_needed() shells out to the full
  installer on every single SessionStart, which is exactly what #63
  (boot simplification) was supposed to eliminate.

NEW CONTRACT (decision 1d623da):
  T1-A: a block with BEGIN present but END absent/orphaned must be
  treated as outdated -> REGENERATED (full block, with its END, restored)
  -- never silently reported as up-to-date.
  T1-B: needs_upgrade() must return False when the install is genuinely
  current (manifest.version matches the plugin AND the managed block
  content is the real canonical content -- derived from
  lib/managed_blocks.py's own render, never a hand-typed literal); True
  only when it is genuinely behind (old manifest version, or a managed
  block that has actually drifted from canonical). The MECHANISM is left
  to Ultron (e.g. compare against the real canonical render, the same way
  the P1 v2 content gate already does, instead of a magic string) -- only
  the observable behavior is asserted here.

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity only -- the EXHAUSTION PROTOCOL does not apply to this pass
(see the post-Ultron hardening pass for that). NO production code is
touched by this file. Only tests.

See also: tests/test_crew_content_gate_v2.py (same P1 v2 gate, the round
this file's 2 bugs were found attacking), tests/test_needs_upgrade_semver.py
and tests/conftest.py::neutralize_needs_upgrade_check1() (existing tests
that assume the "Context Checkpoint Commits" magic string T1-B retires --
NOT touched here, see this session's report for the full list Ultron/Dante
must reconcile in the GREEN phase).
"""

import json
import os
import sys

from conftest import SOURCE_ROOT, HOOKS_DIR, INSTALL, git_cmd, run_script, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from managed_blocks import BLOCKS, any_block_outdated  # noqa: E402
from version import VERSION  # noqa: E402

CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")

DIVERGENT_MARKER = "TAMPERED: this managed block body has drifted from canonical content."


# ── Shared repo helpers (self-contained, mirrors test_crew_content_gate_v2.py) ──


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
    with version == VERSION. Never a hand-typed CLAUDE.md/manifest.json
    stand-in -- canonical content is always derived from the real installer,
    which itself is backed by lib/managed_blocks.py (unmassk-standards §34:
    no fabricated ground truth)."""
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"install --auto failed: {out}\n{err}"


def _claude_md_path(repo):
    return os.path.join(repo, "CLAUDE.md")


def _manifest_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "manifest.json")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def _write(path, content):
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


def _read_manifest(repo):
    with open(_manifest_path(repo), encoding="utf-8") as f:
        return json.load(f)


def _write_manifest_version(repo, version):
    data = _read_manifest(repo)
    data["version"] = version
    with open(_manifest_path(repo), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _replace_first_block_body(repo, marker):
    """Overwrite BLOCKS[0]'s body with `marker`, preserving its real
    begin/end fence lines -- same shape as test_crew_content_gate_v2.py's
    helper of the same name, duplicated locally to keep this file
    self-contained (existing convention across this suite's contract
    files, e.g. test_crew_manifest_version_gate.py vs
    test_crew_content_gate_v2.py)."""
    claude_md = _claude_md_path(repo)
    content = _read(claude_md)

    b0 = BLOCKS[0]
    begin = content.find(b0["begin"])
    end = content.find(b0["end"])
    assert begin != -1 and end != -1, "installed CLAUDE.md must contain the first managed block"
    end += len(b0["end"])

    patched = f"{b0['begin']}\n{marker}\n{b0['end']}"
    content = content[:begin] + patched + content[end:]
    _write(claude_md, content)
    return content


def _run_crew(repo):
    return run_cmd([sys.executable, CREW_HOOK], cwd=repo)


# ══════════════════════════════════════════════════════════════════════════
# T1-A -- orphaned END marker must regenerate the block, never claim
# "up to date". Real channel: subprocess of hooks/session-start-crew.py
# against a real installed repo.
# ══════════════════════════════════════════════════════════════════════════


class TestOrphanedEndMarkerRegeneratesBlock:
    def test_deleted_end_marker_is_regenerated_not_silently_declared_up_to_date(self, tmp_path):
        """Delete ONLY the END marker line for the first managed block from
        a real, freshly-installed CLAUDE.md (simulates a merge-conflict
        resolution or editor auto-fix that eats one line). The dangling
        BEGIN must be regenerated into a complete block (BEGIN and END both
        present again, canonical content) by a real run of
        session-start-crew.py -- and the hook must NOT print its
        "up to date" message while doing so, or while failing to do so.

        RED today: upsert_managed_blocks() only checks `begin in content`
        (lib/managed_blocks.py:190). The begin...end regex has nothing to
        match with END gone, `pattern.sub` no-ops, `new_content == content`
        stays True, and the log records "up-to-date {begin}" --
        hooks/session-start-crew.py prints "[crew] All managed blocks up
        to date" while the block is permanently missing its END marker.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        claude_md = _claude_md_path(repo)
        content_before = _read(claude_md)

        b0 = BLOCKS[0]
        # Sanity: a real install produces exactly one BEGIN and one END for
        # block 0 before any corruption.
        assert content_before.count(b0["begin"]) == 1
        assert content_before.count(b0["end"]) == 1

        # Corrupt: remove ONLY the END marker line, leave everything else
        # (including the BEGIN line and the body) untouched.
        lines = content_before.splitlines(keepends=True)
        corrupted_lines = [ln for ln in lines if ln.rstrip("\n") != b0["end"]]
        assert len(corrupted_lines) == len(lines) - 1, (
            "sanity check on the corruption itself: exactly one END line "
            "must be removed, or this test isn't corrupting what it claims to"
        )
        corrupted = "".join(corrupted_lines)
        _write(claude_md, corrupted)

        # Independent-channel confirmation the corruption is real -- plain
        # string counting, never through managed_blocks.py's own upsert
        # logic (that's the code under test, not the oracle).
        assert corrupted.count(b0["begin"]) == 1, "BEGIN must survive the corruption untouched"
        assert corrupted.count(b0["end"]) == 0, "END must be genuinely absent after corruption"

        # ── Run the REAL hook (code under test) via real subprocess ─────
        rc, stdout, stderr = _run_crew(repo)
        assert rc == 0, f"crew hook must exit 0 (fail-open). stderr={stderr!r}"

        content_after = _read(claude_md)

        # Independent-channel re-verification of the outcome -- plain
        # string counting again, not any_block_outdated()/upsert internals.
        begin_count_after = content_after.count(b0["begin"])
        end_count_after = content_after.count(b0["end"])

        combined = f"{stdout}\n{stderr}".lower()
        claimed_up_to_date = "up to date" in combined or "up-to-date" in combined

        # ── Anti-vacuity: distinguish "regenerated" from "lied about it" ──
        # A single assertion that only checks one side (content OR the
        # log line) could pass on an implementation that fixes one but not
        # the other. Both must hold together.
        assert end_count_after == 1, (
            "the block's END marker must be regenerated (exactly once), not "
            f"left permanently absent. stdout={stdout!r} content_after={content_after!r}"
        )
        assert begin_count_after == 1, (
            "regenerating the block must not leave a duplicate BEGIN behind "
            f"(e.g. appending a whole new block instead of replacing the "
            f"orphaned one). count={begin_count_after} content_after={content_after!r}"
        )
        assert not claimed_up_to_date, (
            "the hook must never claim managed blocks are up to date while "
            f"regenerating a block that was missing its END marker. "
            f"stdout={stdout!r} stderr={stderr!r}"
        )
        assert not any_block_outdated(content_after), (
            "after regeneration every block (not just the corrupted one) "
            f"must match canonical content exactly. content_after={content_after!r}"
        )

        # ── Idempotency: a second real run must be stable and genuinely
        # up-to-date this time (the correct case for that message).
        rc2, stdout2, stderr2 = _run_crew(repo)
        assert rc2 == 0, f"second crew run must exit 0. stderr={stderr2!r}"
        content_after_2 = _read(claude_md)
        assert content_after_2 == content_after, (
            "a second run against already-regenerated, canonical content "
            "must be a genuine no-op (idempotent)"
        )


# ══════════════════════════════════════════════════════════════════════════
# T1-B -- needs_upgrade() must derive "current" from real canonical content
# (lib/managed_blocks.py), never a magic string that was never part of
# production content. Real channel: direct call to the real, stably-named
# lib/upgrade_check.py::needs_upgrade() in an isolated subprocess (never
# via a hand-typed manifest/CLAUDE.md stand-in -- unmassk-standards §34).
# ══════════════════════════════════════════════════════════════════════════


def _call_needs_upgrade(repo):
    """Isolated subprocess, same pattern as
    test_issue63_manifest_read_hardening.py::_call_needs_upgrade -- avoids
    contaminating the main test process's sys.modules with a real,
    stably-named module (upgrade_check) that other test files also import."""
    code = f"""
import sys, json
sys.path.insert(0, {LIB_DIR!r})
import upgrade_check
result = upgrade_check.needs_upgrade({repo!r})
print(json.dumps({{"result": result}}))
"""
    import subprocess
    proc = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, encoding="utf-8", timeout=30,
    )
    assert proc.returncode == 0, (
        f"needs_upgrade() probe must not crash. rc={proc.returncode} "
        f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
    )
    last_line = proc.stdout.strip().splitlines()[-1]
    return json.loads(last_line)["result"]


class TestNeedsUpgradeCanonicalContentContract:
    def test_canonical_install_with_current_version_returns_false(self, tmp_path):
        """The core RED case: a from-scratch, 100% canonical install
        (real installer, manifest.version == VERSION, managed block content
        genuinely matching lib/managed_blocks.py's render) must be
        considered current -- needs_upgrade() must return False.

        RED today: Check 1 requires the literal string "Context Checkpoint
        Commits" inside the block (lib/upgrade_check.py:102). That string
        has never existed in real production content, so this precondition
        (genuinely canonical, version-matching install) still yields True
        -- trigger_auto_upgrade_if_needed() shells out to the full
        installer on every single SessionStart, forever.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        content = _read(_claude_md_path(repo))
        assert not any_block_outdated(content), (
            "precondition: a fresh install --auto must produce genuinely "
            "canonical CLAUDE.md content"
        )
        manifest = _read_manifest(repo)
        assert manifest["version"] == VERSION, (
            "precondition: a fresh install --auto must stamp manifest.version == VERSION"
        )

        result = _call_needs_upgrade(repo)
        assert result is False, (
            "needs_upgrade() must return False for a genuinely canonical, "
            "version-matching install -- it must never require a literal "
            "string that was never part of real production content. "
            f"result={result!r}"
        )

    def test_old_manifest_version_with_canonical_content_returns_true(self, tmp_path):
        """A genuinely stale manifest.version (older than the plugin's own
        VERSION) must still trigger needs_upgrade()==True even once Check 1
        stops keying off the magic string -- the "install is genuinely
        behind" case must keep working, not just the "install is current"
        case above.

        Not RED today for this exact assertion (today's magic-string Check
        1 already returns True for a different, wrong reason on every real
        install) -- kept as part of the same acceptance contract so the fix
        for the False case above cannot silently flip this one to False
        too. Locks in the CONDUCT (result==True), not the mechanism.
        """
        repo = _make_repo(tmp_path)
        _install(repo)
        _write_manifest_version(repo, "0.0.1")

        result = _call_needs_upgrade(repo)
        assert result is True, (
            "a manifest.version genuinely older than the plugin's VERSION "
            f"must still trigger needs_upgrade()==True. result={result!r}"
        )

    def test_divergent_managed_block_with_current_version_returns_true(self, tmp_path):
        """A managed block that has genuinely drifted from canonical
        content (tampered/poisoned/stale -- never the magic-string
        vector) must trigger needs_upgrade()==True even though
        manifest.version matches VERSION -- version alone must never be
        trusted as proof the content is current, symmetric with the P1 v2
        content gate's own contract (test_crew_content_gate_v2.py).

        Not RED today for this exact assertion (today's magic-string Check
        1 already returns True for a different, wrong reason -- the real
        install snippet never contains "Context Checkpoint Commits" in the
        first place, so this passes vacuously pre-fix). Kept as part of
        the same acceptance contract: once Check 1 stops keying off the
        magic string, genuine content drift must be what continues to
        drive True, not an accidental side effect.
        """
        repo = _make_repo(tmp_path)
        _install(repo)

        manifest = _read_manifest(repo)
        assert manifest["version"] == VERSION, (
            "precondition: manifest must genuinely claim the current VERSION "
            "-- the tampering below touches CLAUDE.md only"
        )

        _replace_first_block_body(repo, DIVERGENT_MARKER)
        content = _read(_claude_md_path(repo))
        assert DIVERGENT_MARKER in content, "sanity: the tamper must have actually landed"
        assert any_block_outdated(content), (
            "sanity check on the tamper itself: the replaced body must "
            "genuinely diverge from canonical content, or this test isn't "
            "exercising drift detection at all"
        )

        result = _call_needs_upgrade(repo)
        assert result is True, (
            "a managed block that has genuinely drifted from canonical "
            "content must trigger needs_upgrade()==True even though "
            f"manifest.version matches VERSION. result={result!r}"
        )
