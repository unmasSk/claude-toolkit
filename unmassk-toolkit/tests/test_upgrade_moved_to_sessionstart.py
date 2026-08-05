"""
Acceptance contract (test-first, RED) for issue #63 point 2 — boot
simplification plan (docs/plan/refactor-boot-simplification.md), Bilbo's
map (.claude/agent-memory/unmassk-toolkit-bilbo/boot-simplification-63-map.md
section 2).

Code under test today: hooks/user-prompt-memory-check.py -- needs_upgrade()
(lines ~87-142) is evaluated on EVERY UserPromptSubmit, and when it
returns True the hook synchronously shells out to `git-memory-install.py
--auto` (lines ~203-213). Cost paid on every message: 2 unconditional file
reads (CLAUDE.md + manifest.json) plus, once behind, a real subprocess.

NEW CONTRACT (decision 0f5af98 + Bilbo's map, section 2 -- accepted loss
signed off by Bex: a mid-session `/plugin update` is no longer detected
until the NEXT SessionStart):
  - hooks/user-prompt-memory-check.py must no longer evaluate
    needs_upgrade() or trigger git-memory-install.py --auto at all -- this
    is a per-message hook and that cost belongs at session boundaries now.
  - The exact same EFFECT (a stale manifest gets synced back to the
    running plugin's VERSION) must happen instead during SessionStart --
    where in SessionStart is Ultron's wiring choice (session-start-boot.py
    or session-start-crew.py, per the plan). This file asserts the
    OBSERVABLE EFFECT of running the real SessionStart hooks in
    hooks.json's declared order, not which specific hook or function
    performs the sync -- that would over-specify an implementation detail
    that isn't this contract's concern.

Both new tests are genuinely RED against the unmodified code:
  - test_user_prompt_hook_no_longer_touches_manifest_or_claude_md: today's
    hook DOES rewrite both files when a version-gap is simulated.
  - test_sessionstart_hooks_perform_the_version_sync_effect: today NEITHER
    SessionStart hook touches manifest.json at all -- the sync only ever
    happens from UserPromptSubmit.

Build mode: test-first (contract pass, before Ultron). Acceptance
granularity only -- no exhaustive branch coverage here.

NO production code is touched by this file. Only tests.
"""

import json
import os
import sys

import pytest

from conftest import (
    SOURCE_ROOT,
    HOOKS_DIR,
    INSTALL,
    git_cmd,
    run_script,
    neutralize_needs_upgrade_check1,
)

LIB_DIR = os.path.join(SOURCE_ROOT, "lib")
if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from version import VERSION  # noqa: E402

USER_PROMPT_HOOK = os.path.join(HOOKS_DIR, "user-prompt-memory-check.py")
CREW_HOOK = os.path.join(HOOKS_DIR, "session-start-crew.py")

OLD_VERSION = "0.0.1"


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


def _read_manifest(repo):
    with open(_manifest_path(repo), encoding="utf-8") as f:
        return json.load(f)


def _set_manifest_version(repo, version):
    data = _read_manifest(repo)
    data["version"] = version
    with open(_manifest_path(repo), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _make_stale_installed_repo(tmp_path, name="repo"):
    """An installed repo whose ONLY reason to need an upgrade is the
    semver gap (manifest.version == OLD_VERSION < VERSION) -- Check 1
    (stale CLAUDE.md markers) is neutralized first via conftest's shared
    helper so this fixture exercises exactly the "plugin was updated,
    manifest hasn't synced yet" scenario the plan describes, not a
    coincidental second trigger.
    """
    repo = _make_repo(tmp_path, name)
    _install(repo)
    neutralize_needs_upgrade_check1(repo)
    _set_manifest_version(repo, OLD_VERSION)
    return repo


def _run_user_prompt_hook(repo, prompt="hola"):
    payload = {"prompt": prompt}
    return run_script(USER_PROMPT_HOOK, repo, input_text=json.dumps(payload))


# ── New behavior: UserPromptSubmit no longer evaluates/triggers upgrade ───


class TestUserPromptSubmitNoLongerUpgrades:
    def test_user_prompt_hook_no_longer_touches_manifest_or_claude_md(self, tmp_path):
        repo = _make_stale_installed_repo(tmp_path)

        with open(_manifest_path(repo), "rb") as f:
            manifest_bytes_before = f.read()
        with open(_claude_md_path(repo), "rb") as f:
            claude_md_bytes_before = f.read()

        rc, stdout, stderr = _run_user_prompt_hook(repo)
        assert rc == 0, f"UserPromptSubmit hook must always exit 0. stderr={stderr!r}"

        with open(_manifest_path(repo), "rb") as f:
            manifest_bytes_after = f.read()
        with open(_claude_md_path(repo), "rb") as f:
            claude_md_bytes_after = f.read()

        assert manifest_bytes_after == manifest_bytes_before, (
            "UserPromptSubmit must no longer auto-upgrade the manifest -- "
            f"manifest.json changed. stdout={stdout!r}"
        )
        assert claude_md_bytes_after == claude_md_bytes_before, (
            "UserPromptSubmit must no longer rewrite CLAUDE.md as a side "
            f"effect of the (removed) upgrade check. stdout={stdout!r}"
        )


# ── New behavior: SessionStart performs the same effect instead ───────────


class TestSessionStartPerformsTheUpgradeEffect:
    def test_sessionstart_hooks_perform_the_version_sync_effect(self, tmp_path):
        """Runs the real SessionStart hook(s) against a repo whose manifest
        is deliberately stale. Asserts only the observable EFFECT
        (manifest.version ends up synced to VERSION) -- not which hook, or
        which function, performs it.

        [corregido 2026-08-05: this originally ran session-start-boot.py
        THEN session-start-crew.py in hooks.json's declared order --
        session-start-boot.py was retired outright with the rest of the v1
        memory system (docs/memoria-v2/PLAN-CONSTRUCCION.md), so only
        session-start-crew.py remains registered in hooks.json. Confirmed
        live (grep) that the version-sync effect this test asserts already
        landed there: session-start-crew.py's _print_upgrade_check() calls
        upgrade_check.trigger_auto_upgrade_if_needed(), the same effect the
        docstring above describes. The contract itself (an observable
        effect, not a named hook) is unchanged -- only which hook(s) are
        actually invoked below.]
        """
        repo = _make_stale_installed_repo(tmp_path)
        assert _read_manifest(repo)["version"] == OLD_VERSION  # precondition

        rc, out, err = run_script(CREW_HOOK, repo)
        assert rc == 0, f"session-start-crew.py must exit 0. stderr={err!r}"

        assert _read_manifest(repo)["version"] == VERSION, (
            "the SessionStart hook must perform the version-sync upgrade "
            "that UserPromptSubmit no longer does -- manifest.version is "
            f"still {OLD_VERSION!r}. crew stdout={out!r}"
        )


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
