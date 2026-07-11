"""
Regression tests for wip f0313d8 ("Ultron endurece productor #63") —
issue #63, PRODUCER-side hardening deferred out of scope by
test_crew_content_gate_v2.py (see that file's own "Explicitly excluded
from this file's scope" note and
.claude/agent-memory/unmassk-toolkit-dante/issue-63-p1-v2-content-gate-contract-notes.md).

Two behaviors fixed by Ultron in f0313d8, both must stay fixed:

  A. lib/install_apply.py::apply_plan() — _create_manifest() only runs
     `if not errors`. Before this fix, apply_plan()'s per-action
     try/except appended to errors[] but never aborted the loop, so a
     failed update_claude_md write still let create_manifest stamp
     manifest.version == VERSION right after — Moriarty's PoC 1 exploited
     exactly this to make the P1 content gate trust a stale/poisoned
     CLAUDE.md forever.

  B. lib/upgrade_check.py::trigger_auto_upgrade_if_needed() — a non-zero
     installer returncode now leaves a breadcrumb in stderr instead of
     being silently discarded. Before this fix the returncode was never
     read at all, so a failed `--auto` re-install (manifest never
     re-stamped, per fix A above) looked identical to a successful one
     from this call site's perspective — nothing anywhere retried or even
     logged it.

Both mutation-checks below were run manually during this session (Edit ->
run the one affected test -> confirm RED for the right reason -> Edit
back -> `git diff --quiet` confirmed clean) per this project's documented
discipline (not committed as self-mutating test code) — see
unmassk-toolkit-python-test-conventions.md.

NO production code is touched by this file. Only tests.
"""

import json
import os
import sys

from conftest import SOURCE_ROOT, INSTALL, git_cmd, run_script, run_cmd

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from version import VERSION  # noqa: E402


# ── Repo helpers ──────────────────────────────────────────────────────────


def _make_repo(tmp_path, name="repo"):
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _manifest_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "manifest.json")


def _claude_md_path(repo):
    return os.path.join(repo, "CLAUDE.md")


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


# ── Behavior A: install_apply.apply_plan() manifest-stamp gating ─────────


def _run_apply_plan(repo, sabotage):
    """Run the REAL lib/install_apply.py::apply_plan() in its own
    subprocess, with a 2-action plan (update_claude_md, create_manifest —
    the two actions that always run regardless of repo state, per
    create_plan() in bin/git-memory-install.py). When `sabotage` is True,
    open_no_follow_symlink is monkeypatched to raise PermissionError ONLY
    for CLAUDE.md's write, mirroring test_crew_content_gate_v2.py's
    `_run_sabotaged_producer()` (same technique Ultron used to verify this
    fix manually, per the task brief) — no chmod, per this project's
    documented cross-platform write-failure-simulation rule.

    Returns (rc, stdout, stderr). stdout is a single JSON line:
    {"errors": [...]} — apply_plan()'s real return value.
    """
    sabotage_code = """
_real_open = install_apply.open_no_follow_symlink

def _sometimes_fail(path, mode="w", encoding="utf-8", **kwargs):
    if mode == "w" and os.path.basename(str(path)) == "CLAUDE.md":
        raise PermissionError(f"[simulated write failure] cannot open {path} for write")
    return _real_open(path, mode, encoding=encoding, **kwargs)

install_apply.open_no_follow_symlink = _sometimes_fail
""" if sabotage else ""

    code = f"""
import sys, os, json
sys.path.insert(0, {LIB_DIR!r})
os.chdir({repo!r})

import install_apply

{sabotage_code}

plan = {{
    "mode": "normal",
    "actions": [
        ("update_claude_md", "Update managed block in CLAUDE.md"),
        ("create_manifest", "Create/update .claude/.unmassk/manifest.json"),
    ],
    "skipped": [],
}}
errors = install_apply.apply_plan(plan, {SOURCE_ROOT!r}, {repo!r})
print(json.dumps({{"errors": errors}}))
"""
    return run_cmd([sys.executable, "-c", code], repo, timeout=30)


class TestManifestNotStampedWhenActionFailsNoPriorManifest:
    def test_manifest_absent_after_failed_write_when_never_installed(self, tmp_path):
        """Fresh target, never installed before (no manifest.json on disk
        at all). A sabotaged update_claude_md write fails -> apply_plan()
        must NOT stamp manifest.json afterward -- it must stay exactly as
        it was: absent.

        Pre-fix behavior (RED without the `if not errors` guard):
        manifest.json would exist with version == VERSION despite the
        write failure, because create_manifest ran unconditionally right
        after update_claude_md's exception was appended to errors[].
        """
        repo = _make_repo(tmp_path)
        claude_md = _claude_md_path(repo)
        manifest = _manifest_path(repo)
        assert not os.path.exists(claude_md), "sanity: no pre-existing CLAUDE.md"
        assert not os.path.exists(manifest), "sanity: no pre-existing manifest.json"

        rc, out, err = _run_apply_plan(repo, sabotage=True)
        assert rc == 0, f"sabotage subprocess itself must not crash. stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])

        assert payload["errors"], (
            "sanity check on the sabotage setup: apply_plan() must report a real "
            f"failure, or this test isn't sabotaging anything. out={out!r}"
        )
        assert any("update_claude_md" in e for e in payload["errors"]), (
            f"the failure must be attributed to update_claude_md specifically. errors={payload['errors']!r}"
        )

        assert not os.path.exists(claude_md), (
            "anti-vacuity: CLAUDE.md must genuinely never have been created -- "
            "the sabotaged write must have failed before any bytes landed on disk"
        )
        assert not os.path.exists(manifest), (
            "manifest.json must NOT be stamped when an earlier action in the same "
            f"apply_plan() run failed. errors={payload['errors']!r}"
        )


class TestManifestPreservedUnchangedWhenActionFailsAfterPriorInstall:
    def test_manifest_byte_identical_after_failed_write_when_prior_install_exists(self, tmp_path):
        """Target with a REAL prior successful install (manifest.json
        genuinely on disk, stamped by a real earlier apply_plan() run),
        whose version is then downgraded on disk to simulate "installed by
        an older release" (same technique as test_hardening_recall.py's
        `_make_repo_needing_upgrade_via_semver`). A second, sabotaged
        apply_plan() run fails update_claude_md -> the manifest must be
        left EXACTLY as it was before this second run (byte-identical),
        never re-stamped with the current VERSION and never deleted.

        Expected value is the real content read from disk right before
        the sabotaged run -- never hand-typed (§34) -- so this proves
        "preserved" against this run's own genuine prior state, not an
        assumed shape.
        """
        repo = _make_repo(tmp_path)
        rc, out, err = run_script(INSTALL, repo, ["--auto"])
        assert rc == 0, f"real prior install --auto must succeed. out={out}\n{err}"

        manifest = _manifest_path(repo)
        with open(manifest, encoding="utf-8") as f:
            manifest_data = json.load(f)
        assert manifest_data["version"] == VERSION, (
            "precondition: a fresh install --auto must stamp the current VERSION"
        )
        manifest_data["version"] = "0.0.1"
        with open(manifest, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2)

        content_before = _read(manifest)

        rc, out, err = _run_apply_plan(repo, sabotage=True)
        assert rc == 0, f"sabotage subprocess itself must not crash. stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])
        assert payload["errors"], (
            f"sanity check on the sabotage setup: apply_plan() must report a real failure. out={out!r}"
        )
        assert any("update_claude_md" in e for e in payload["errors"]), (
            f"the failure must be attributed to update_claude_md specifically. errors={payload['errors']!r}"
        )

        content_after = _read(manifest)
        assert content_after == content_before, (
            "manifest.json must stay byte-identical (still the stale/prior version) "
            "when a later action in the same apply_plan() run fails -- it must never "
            "be re-stamped with the current VERSION on a failed run"
        )


class TestManifestStampedOnHappyPath:
    def test_manifest_stamped_with_current_version_when_no_action_fails(self, tmp_path):
        """Control: the optimization/contract this fix must NOT break --
        when nothing fails, create_manifest must still run and stamp
        manifest.version == VERSION exactly as before."""
        repo = _make_repo(tmp_path)
        manifest = _manifest_path(repo)
        assert not os.path.exists(manifest), "sanity: no pre-existing manifest.json"

        rc, out, err = _run_apply_plan(repo, sabotage=False)
        assert rc == 0, f"apply_plan subprocess itself must not crash. stderr={err!r}"
        payload = json.loads(out.strip().splitlines()[-1])

        assert payload["errors"] == [], (
            f"happy path must report zero errors. errors={payload['errors']!r}"
        )
        assert os.path.isfile(manifest), (
            "manifest.json must be created when apply_plan() had no failures"
        )
        with open(manifest, encoding="utf-8") as f:
            manifest_data = json.load(f)
        assert manifest_data["version"] == VERSION, (
            f"manifest must be stamped with the current VERSION on the happy path. "
            f"got={manifest_data.get('version')!r}"
        )
        assert manifest_data["runtime_mode"] == "normal"


# ── Behavior B: upgrade_check.trigger_auto_upgrade_if_needed() breadcrumb ─


def _make_repo_needing_upgrade(tmp_path):
    """Real, fully installed repo whose manifest.json is downgraded below
    the current VERSION -- the only condition that makes needs_upgrade()
    return True without relying on old-style CLAUDE.md markers. Mirrors
    test_hardening_recall.py's `_make_repo_needing_upgrade_via_semver`."""
    repo = _make_repo(tmp_path)
    rc, out, err = run_script(INSTALL, repo, ["--auto"])
    assert rc == 0, f"real prior install --auto must succeed. out={out}\n{err}"

    manifest = _manifest_path(repo)
    with open(manifest, encoding="utf-8") as f:
        manifest_data = json.load(f)
    manifest_data["version"] = "0.0.1"
    with open(manifest, "w", encoding="utf-8") as f:
        json.dump(manifest_data, f)
    return repo


def _run_trigger_upgrade(repo, fake_installer_body, extra_sabotage=""):
    """Run lib/upgrade_check.py::trigger_auto_upgrade_if_needed() directly
    in its own subprocess (real, stably-named module -- isolated per this
    project's convention so a monkeypatch here can't leak into other test
    files' sys.modules). `_PLUGIN_ROOT` is pointed at a throwaway fake
    plugin root whose bin/git-memory-install.py is `fake_installer_body`,
    a real subprocess Python script -- no subprocess.run mocking needed
    for the returncode-path tests. Prints "TRIGGER_DONE" on success so a
    caller can confirm the function returned normally (never raised)
    without relying on rc alone (rc==0 could also mean the subprocess
    crashed before reaching that print, masked by an unrelated early exit
    -- this makes the "did it actually complete" check explicit).
    """
    fake_root = os.path.join(repo, "_fake_plugin_root")
    os.makedirs(os.path.join(fake_root, "bin"), exist_ok=True)
    if fake_installer_body is not None:
        with open(os.path.join(fake_root, "bin", "git-memory-install.py"), "w", encoding="utf-8") as f:
            f.write(fake_installer_body)

    code = f"""
import sys, os
sys.path.insert(0, {LIB_DIR!r})
os.chdir({repo!r})

import upgrade_check
assert upgrade_check.needs_upgrade({repo!r}) is True, "sanity: needs_upgrade must be True before sabotaging"

upgrade_check._PLUGIN_ROOT = {fake_root!r}

{extra_sabotage}

upgrade_check.trigger_auto_upgrade_if_needed({repo!r})
print("TRIGGER_DONE")
"""
    return run_cmd([sys.executable, "-c", code], repo, timeout=30)


class TestNonZeroReturncodeLeavesBreadcrumbAndDoesNotSwallowFailure:
    def test_nonzero_returncode_prints_breadcrumb_to_stderr(self, tmp_path):
        """A real installer subprocess exiting non-zero must leave a
        breadcrumb in stderr identifying the returncode and must not raise
        -- the caller (trigger_auto_upgrade_if_needed) must complete
        normally (fail-open), never silently treat this as success.

        Pre-fix behavior (RED without the `if result.returncode != 0`
        block): the returncode was discarded entirely, no breadcrumb of
        any kind was ever printed for this case.
        """
        repo = _make_repo_needing_upgrade(tmp_path)
        fake_installer = (
            "import sys\n"
            "sys.stderr.write('simulated installer failure: could not write CLAUDE.md\\n')\n"
            "sys.exit(1)\n"
        )

        rc, out, err = _run_trigger_upgrade(repo, fake_installer)

        assert rc == 0, f"the wrapper subprocess itself must not crash. stdout={out!r} stderr={err!r}"
        assert "TRIGGER_DONE" in out, (
            f"trigger_auto_upgrade_if_needed() must return normally (not raise) on a "
            f"non-zero installer exit. stdout={out!r} stderr={err!r}"
        )
        assert "upgrade fail-open" in err, (
            f"a breadcrumb must be printed to stderr for a non-zero returncode. stderr={err!r}"
        )
        assert "exited 1" in err, (
            f"the breadcrumb must name the actual returncode. stderr={err!r}"
        )
        assert "simulated installer failure" in err, (
            "the breadcrumb must surface the installer's own stderr, not just the "
            f"bare returncode -- otherwise the failure is unactionable. stderr={err!r}"
        )
        assert "success" not in err.lower(), (
            f"the breadcrumb must never claim success for a non-zero exit. stderr={err!r}"
        )


class TestZeroReturncodePrintsNoBreadcrumb:
    def test_zero_returncode_is_silent(self, tmp_path):
        """Control: the happy path must NOT be affected by this fix -- a
        successful `--auto` install (returncode 0) must print no upgrade
        fail-open breadcrumb at all."""
        repo = _make_repo_needing_upgrade(tmp_path)
        fake_installer = "import sys\nsys.exit(0)\n"

        rc, out, err = _run_trigger_upgrade(repo, fake_installer)

        assert rc == 0, f"the wrapper subprocess itself must not crash. stdout={out!r} stderr={err!r}"
        assert "TRIGGER_DONE" in out, (
            f"trigger_auto_upgrade_if_needed() must return normally on a zero exit. "
            f"stdout={out!r} stderr={err!r}"
        )
        assert "upgrade fail-open" not in err, (
            f"no breadcrumb must be printed for a successful (returncode 0) install. stderr={err!r}"
        )


class TestSubprocessExceptionStillFailsOpen:
    def test_subprocess_run_exception_does_not_propagate(self, tmp_path):
        """Regression guard for the pre-existing except-branch (unchanged
        by this fix, but exercised here via a direct unit call rather than
        the full-boot channel test_hardening_recall.py already covers):
        a genuine exception raised by subprocess.run() itself (not just a
        non-zero returncode) must still be swallowed -- trigger_auto_upgrade_if_needed()
        must return normally, never propagate."""
        repo = _make_repo_needing_upgrade(tmp_path)
        sabotage = """
import subprocess as _subprocess
_real_run = _subprocess.run
def _fake_run(cmd, *a, **kw):
    if isinstance(cmd, list) and any('git-memory-install.py' in str(c) for c in cmd):
        raise OSError('simulated: installer not found')
    return _real_run(cmd, *a, **kw)
_subprocess.run = _fake_run
"""
        rc, out, err = _run_trigger_upgrade(repo, fake_installer_body=None, extra_sabotage=sabotage)

        assert rc == 0, f"the wrapper subprocess itself must not crash. stdout={out!r} stderr={err!r}"
        assert "TRIGGER_DONE" in out, (
            f"trigger_auto_upgrade_if_needed() must return normally on a genuine "
            f"subprocess exception (fail-open). stdout={out!r} stderr={err!r}"
        )
        assert "upgrade fail-open" in err, (
            f"the except-branch breadcrumb must still fire. stderr={err!r}"
        )
