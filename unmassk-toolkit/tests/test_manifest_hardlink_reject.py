"""
Test-first contract (Dante, before Ultron) -- SEC-HIGH-001, an Argus-confirmed
extension of the F6 hard-link bypass closed by issue #53 (decision 51a3c44,
see tests/test_hardlink_reject_guard.py for the base contract on the two
open_no_follow_symlink() twins themselves).

Background: F6 is "a hard link planted at a guarded path is indistinguishable
from an ordinary file to os.path.islink() and to POSIX O_NOFOLLOW" -- closed
at the FUNCTION level by an opt-in `reject_hardlinks: bool = False` parameter
on both twins (lib/git_helpers.py:open_no_follow_symlink() and
lib/_symlink_safe_open.py:open_no_follow_symlink_fallback()). That base
contract is fully implemented and GREEN: 3 call sites already pass
reject_hardlinks=True (grepped live) -- lib/boot_glossary_cache.py (read +
write), hooks/user-prompt-memory-check.py (.session-booted flag write), and
hooks/session-start-boot.py (boot-log write).

Argus found the fix was applied inconsistently: 3 MORE call sites write
.claude/.unmassk/manifest.json -- a fixed path generated only by this
toolkit, never a legitimate user file, so there is no false-positive risk
(unlike CLAUDE.md/settings.json/package.json/.gitignore/scopes, which
deliberately keep reject_hardlinks=False by default) -- via plain
open_no_follow_symlink(manifest_path, "w") with NO reject_hardlinks argument
at all, leaving them exposed to the exact same bypass:

  - lib/install_apply.py:276               _create_manifest()
    (reachable automatically via the user-prompt-memory-check.py hook's
    auto-upgrade path, not just an explicit manual install)
  - bin/git-memory-doctor.py:517            run_doctor() healthcheck write-back
  - bin/git-memory-upgrade.py:362           apply_upgrade()

Threat model (same "attacker controls the whole repo" model already
documented throughout test_security_regression.py's BUG D/E/F/... series for
the symlink variant of this same manifest path): the attacker plants a real
hard link at .claude/.unmassk/manifest.json pointing at the same inode as
some OTHER file the toolkit later writes over -- os.link() needs no special
privilege on POSIX or Windows (confirmed live on this Windows dev box,
see conftest.py::real_hardlink_capable), unlike os.symlink(). Because a hard
link has no "content of its own" -- the guarded path and the victim path are
two names for the SAME inode -- any unguarded write through the guarded path
also silently overwrites the victim's real content.

Build mode: test-first (CONTRACT pass, before Ultron). Acceptance
granularity only -- one behavior-level test per unprotected call site,
exercised through the real CLI end-to-end (mirrors the existing BUG D
"symlink write" / BUG F "symlink read+write" tests in
test_security_regression.py, swapping os.symlink() for a real os.link()).
The EXHAUSTION PROTOCOL hardening pass runs AFTER Ultron implements (Flow
Verify step) and is deliberately NOT applied in this file.

§34 (Producer-Consumer / anti-fixture-fabrication): every hard link here is
created for real via os.link() inside the test itself (_plant_hardlink()
below). st_nlink is read back live via os.stat() immediately before each
assertion that depends on it -- never hardcoded. The "expected" victim
content after running the CLI is exactly the content THIS test itself wrote
to the victim file moments earlier (the test is both producer and, via a
plain unguarded victim.read_text() call -- an independent channel from
whatever the CLI under test reports on stdout -- the consumer that proves
the shared inode was, or was not, actually touched).

RED-now expectation: all 3 tests below currently FAIL -- the victim's real
content is silently overwritten by the CLI's manifest write, because none of
these 3 call sites pass reject_hardlinks=True yet. Expected GREEN once
Ultron adds `reject_hardlinks=True` to the 3 call sites listed above (the
parameter and its st_nlink>1 check already exist and are fully tested in
test_hardlink_reject_guard.py -- nothing new to implement in git_helpers.py/
_symlink_safe_open.py themselves, only 3 call-site kwargs).

NO production code is touched by this file. Only tests.
"""

import json
import os

import pytest

from conftest import INSTALL, UPGRADE, DOCTOR, git_cmd, run_script


def _make_repo(tmp_path, name="repo"):
    """Minimal git repo with user identity configured -- mirrors
    test_security_regression.py's _make_repo() (kept local rather than
    imported cross-file, since it is 5 lines and this file's only repo
    dependency)."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    git_cmd(["config", "user.email", "test@test.com"], repo)
    git_cmd(["config", "user.name", "Test"], repo)
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo)
    return repo


def _plant_hardlink(target_path, victim_path):
    """Make target_path a REAL second hard link to victim_path (os.link()),
    replacing whatever currently sits at target_path.

    Mirrors test_security_regression.py's _plant_symlink() but for a hard
    link: unlike a symlink, a hard link has no content of its own -- after
    this call, target_path and victim_path are two directory entries for the
    SAME inode, so any write through target_path is a write through
    victim_path too, unless the write refuses to open a multi-link file.
    """
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    if os.path.lexists(target_path):
        os.remove(target_path)
    os.link(victim_path, target_path)


# ══════════════════════════════════════════════════════════════════════════
# SEC-HIGH-001 site 1 — lib/install_apply.py:276 _create_manifest() (RED now)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestSecHigh001InstallManifestHardlinkWrite:
    """git-memory-install.py --auto must not write through a hard link
    planted at .claude/.unmassk/manifest.json before install ever runs --
    same repro shape as test_security_regression.py's BUG D install test,
    with os.link() instead of os.symlink()."""

    def test_install_does_not_write_through_hardlinked_manifest_path(self, tmp_path):
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-install-hardlink.json"
        victim.write_text("SENSITIVE ORIGINAL CONTENT - HARDLINK INSTALL", encoding="utf-8")

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_hardlink(manifest_path, str(victim))
        nlink_before = os.stat(str(victim)).st_nlink
        assert nlink_before > 1, (
            f"fixture setup invariant broken: expected st_nlink>1 after a "
            f"real os.link(), got {nlink_before}"
        )

        rc, stdout, stderr = run_script(INSTALL, repo, extra_args=["--auto"])

        assert victim.read_text(encoding="utf-8") == "SENSITIVE ORIGINAL CONTENT - HARDLINK INSTALL", (
            "SEC-HIGH-001: git-memory-install.py --auto "
            "(lib/install_apply.py:276, _create_manifest()) wrote through a "
            "hard link planted at the manifest.json path and clobbered the "
            "shared inode's content -- the same bypass class F6/issue #53 "
            "already closed for boot-log/glossary-cache/booted_flag via "
            "reject_hardlinks=True, left unprotected at this call site. "
            f"install rc={rc}\nstdout (first 500): {stdout[:500]}\n"
            f"stderr (first 500): {stderr[:500]}\n"
            f"victim content is now: {victim.read_text(encoding='utf-8')!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# SEC-HIGH-001 site 2 — bin/git-memory-upgrade.py:362 apply_upgrade() (RED now)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestSecHigh001UpgradeManifestHardlinkWrite:
    """git-memory-upgrade.py --auto must not write through a hard link
    planted at .claude/.unmassk/manifest.json when it rewrites the manifest
    as part of applying an upgrade -- same repro shape as
    test_security_regression.py's BUG D upgrade test, with os.link() instead
    of os.symlink().

    The victim must contain valid manifest-shaped JSON with an old version
    marker ("1.0.0") so read_installed_manifest()'s READ (a separate,
    already-unguarded-by-design call site, out of scope here) succeeds and
    check_upgrade_needed() finds a genuine version mismatch -- otherwise
    upgrade exits early without ever reaching the WRITE this test targets,
    and would prove nothing about the write-side guard.
    """

    def test_upgrade_does_not_write_through_hardlinked_manifest_path(self, tmp_path):
        repo = _make_repo(tmp_path)
        run_script(INSTALL, repo, extra_args=["--auto"])

        victim = tmp_path / "victim-manifest-upgrade-hardlink.json"
        victim.write_text(json.dumps({
            "version": "1.0.0",
            "installed_at": "2020-01-01T00:00:00",
            "runtime_mode": "normal",
        }), encoding="utf-8")

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_hardlink(manifest_path, str(victim))
        nlink_before = os.stat(str(victim)).st_nlink
        assert nlink_before > 1, (
            f"fixture setup invariant broken: expected st_nlink>1 after a "
            f"real os.link(), got {nlink_before}"
        )

        rc, stdout, stderr = run_script(UPGRADE, repo, extra_args=["--auto"])

        assert "1.0.0" in victim.read_text(encoding="utf-8"), (
            "SEC-HIGH-001: git-memory-upgrade.py --auto "
            "(bin/git-memory-upgrade.py:362, apply_upgrade()) wrote through "
            "a hard link planted at the manifest.json path and clobbered "
            "the shared inode's content with the new manifest -- the "
            "pre-upgrade version marker is gone. "
            f"upgrade rc={rc}\nstdout (first 500): {stdout[:500]}\n"
            f"stderr (first 500): {stderr[:500]}\n"
            f"victim content is now: {victim.read_text(encoding='utf-8')!r}"
        )


# ══════════════════════════════════════════════════════════════════════════
# SEC-HIGH-001 site 3 — bin/git-memory-doctor.py:517 run_doctor() (RED now)
# ══════════════════════════════════════════════════════════════════════════


@pytest.mark.usefixtures("real_hardlink_capable")
class TestSecHigh001DoctorManifestHardlinkWrite:
    """git-memory-doctor.py --json's healthcheck-timestamp write-back must
    not write through a hard link planted at .claude/.unmassk/manifest.json
    -- same repro shape as test_security_regression.py's BUG F doctor test,
    with os.link() instead of os.symlink(). The READ at doctor.py's
    check_manifest() (a separate, already-unguarded-by-design call site, out
    of scope here) is expected to succeed either way; only the WRITE-BACK
    this test targets must refuse to touch a multi-link file.
    """

    def test_doctor_json_does_not_write_through_hardlinked_manifest(self, tmp_path):
        repo = _make_repo(tmp_path)
        victim = tmp_path / "victim-manifest-doctor-hardlink.json"
        original_content = json.dumps({"version": "0.0.1-HARDLINK-ORIGINAL", "secret": "do-not-touch"})
        victim.write_text(original_content, encoding="utf-8")

        manifest_path = os.path.join(repo, ".claude", ".unmassk", "manifest.json")
        _plant_hardlink(manifest_path, str(victim))
        nlink_before = os.stat(str(victim)).st_nlink
        assert nlink_before > 1, (
            f"fixture setup invariant broken: expected st_nlink>1 after a "
            f"real os.link(), got {nlink_before}"
        )

        rc, stdout, stderr = run_script(DOCTOR, repo, extra_args=["--json"])

        assert victim.read_text(encoding="utf-8") == original_content, (
            "SEC-HIGH-001: git-memory-doctor.py --json "
            "(bin/git-memory-doctor.py:517, run_doctor() healthcheck "
            "write-back) wrote through a hard link planted at the "
            "manifest.json path and added last_healthcheck_at to the "
            "shared inode's content. "
            f"doctor rc={rc}\nstdout (first 500): {stdout[:500]}\n"
            f"stderr (first 500): {stderr[:500]}\n"
            f"victim content is now: {victim.read_text(encoding='utf-8')!r}"
        )
