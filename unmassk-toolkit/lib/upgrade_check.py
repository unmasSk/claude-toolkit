"""
Upgrade-need detection + auto-install trigger.

Moved here (issue #63, boot simplification, point 2) from
hooks/user-prompt-memory-check.py, where needs_upgrade() used to be
evaluated on EVERY UserPromptSubmit message -- 2 unconditional file reads
(CLAUDE.md + manifest.json) on every message, plus a subprocess of up to
15s once the installed manifest fell behind. That cost belongs at session
boundaries now: hooks/session-start-boot.py calls
trigger_auto_upgrade_if_needed() once per SessionStart, before
hooks/session-start-crew.py's manifest-version gate runs (hooks.json's
declared SessionStart order), so a synced manifest.json is already on disk
by the time that gate reads it.

Accepted loss (decision 0f5af98 + Bilbo's map, section 2, signed off by
Bex): a `/plugin update` mid-session is no longer detected until the NEXT
SessionStart -- previously UserPromptSubmit could catch it on the very next
message.

hooks/user-prompt-memory-check.py re-imports needs_upgrade/_parse_semver by
name (backward-compat only -- several existing tests load that hook file
directly via importlib and call hook.needs_upgrade()/hook._parse_semver():
tests/test_needs_upgrade_semver.py, tests/test_security_regression.py's
BUG M/T). The logic itself is unchanged, byte-for-byte, only its home
moved -- and hooks/user-prompt-memory-check.py's main() never calls either
name anymore, so zero evaluation happens per user message.
"""

import json
import os
import subprocess
import sys

try:
    # Imported defensively (project convention, see
    # lib/_symlink_safe_open.py's own docstring): tests/test_migrate_statusline.py
    # stubs out git_helpers with a minimal fake module that predates this
    # helper, and this module gets pulled in transitively via
    # hooks/session-start-boot.py during that stub window.
    from git_helpers import open_no_follow_symlink
except ImportError:
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink
from version import VERSION as PLUGIN_VERSION

# lib/upgrade_check.py -> one level up is the plugin root.
_PLUGIN_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _parse_semver(version_str) -> tuple[int, int, int] | None:
    """Parse a semver string into a (major, minor, patch) tuple of ints.

    Returns None if the input is not a string, is empty, or cannot be parsed
    as semver. Only strings with exactly three numeric components (X.Y.Z) are
    accepted; anything else returns None. Pre-release suffixes are not
    supported and will cause a parse failure (returns None).
    """
    if not isinstance(version_str, str) or not version_str:
        return None
    parts = version_str.split(".")
    if len(parts) != 3:
        return None
    try:
        return (int(parts[0]), int(parts[1]), int(parts[2]))
    except ValueError:
        return None


def needs_upgrade(root: str) -> bool:
    """Check if the CLAUDE.md managed block has outdated content OR the
    installed manifest version is older than PLUGIN_VERSION.

    Upgrade triggers (union — any one is enough):
      1. Old-style CLAUDE.md block markers (stale hardcoded bin/ paths or
         missing 'Context Checkpoint Commits').
      2. manifest.version < PLUGIN_VERSION (numeric semver comparison).

    Fail-safe: if the manifest is absent, corrupt, missing the 'version'
    key, or has an unparseable version string → False (not True).
    Returning True on a broken manifest would cause an infinite upgrade loop
    because the manifest is never written before the next hook fires.
    """
    claude_md = os.path.join(root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return False  # needs_install handles this
    try:
        # 7th audit round (BUG T): never follow a symlink planted at
        # CLAUDE.md for this read either — treat it exactly like the
        # fail-safe-to-False path used below for the manifest read.
        with open_no_follow_symlink(claude_md, "r") as f:
            content = f.read()
    except OSError:
        return False  # fail-safe: symlink or unreadable CLAUDE.md
    if "BEGIN unmassk-toolkit" not in content:
        return False  # needs_install handles this

    # ── Check 1: Old-style markers in the managed block ──────────────────
    begin = content.find("BEGIN unmassk-toolkit")
    end = content.find("END unmassk-toolkit")
    if begin == -1 or end == -1:
        return False
    block = content[begin:end]
    if "python3 bin/" in block or "Context Checkpoint Commits" not in block:
        return True

    # ── Check 2: Semver comparison — manifest.version < PLUGIN_VERSION ───
    try:
        manifest_path = os.path.join(root, ".claude", ".unmassk", "manifest.json")
        # SEC-T1-002 (Argus, issue #63): open_no_follow_symlink() below only
        # guards manifest.json's FINAL path component -- a .claude/.unmassk
        # parent that is ITSELF a symlink to a directory holding a real,
        # non-symlink manifest.json slips past it undetected. Deferred
        # import: this module is transitively loaded during
        # session-start-boot.py's git_helpers test-stub window (same reason
        # open_no_follow_symlink is imported defensively above). Caught by
        # the broad except below exactly like any other untrustworthy
        # manifest.
        from git_helpers import verify_path_within_project
        verify_path_within_project(manifest_path, root)
        # SEC-HIGH-NEW-11: never follow a symlink planted at manifest.json —
        # the surrounding except below already fails safe to False.
        with open_no_follow_symlink(manifest_path, "r") as f:
            manifest = json.load(f)
        # manifest.get("version", "") guards against a missing key, but JSON
        # null still arrives as None here. _parse_semver tolerates non-str input.
        manifest_version = manifest.get("version", "")
        manifest_tuple = _parse_semver(manifest_version)
        if manifest_tuple is None:
            return False  # fail-safe: unparseable or empty version
        code_tuple = _parse_semver(PLUGIN_VERSION)
        if code_tuple is None:
            return False  # fail-safe: PLUGIN_VERSION itself is broken
        return manifest_tuple < code_tuple
    except Exception:
        return False  # fail-safe: missing file, bad JSON, any I/O error


def trigger_auto_upgrade_if_needed(root: str) -> None:
    """If needs_upgrade(root), shell out to git-memory-install.py --auto.

    Fail-open, same discipline as every other boot-time helper: any
    exception (including subprocess.TimeoutExpired) is swallowed so
    SessionStart never fails because of this. Same subprocess shape
    (timeout=15) as the UserPromptSubmit-era call this replaces.
    """
    try:
        if needs_upgrade(root):
            install_script = os.path.join(_PLUGIN_ROOT, "bin", "git-memory-install.py")
            subprocess.run(
                [sys.executable, install_script, "--auto"],
                capture_output=True, text=True, encoding="utf-8", cwd=root, timeout=15,
            )
    except Exception as e:
        print(f"[git-memory] upgrade fail-open: {e!r}", file=sys.stderr)
        # fail-open: upgrade failure must never break session start
