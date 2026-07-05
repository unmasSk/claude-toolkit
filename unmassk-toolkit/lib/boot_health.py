"""
Boot health checks for session-start-boot.py (split out of lib/boot_checks.py,
Cerberus round-6 LOC audit).

Owns the "is the plugin/repo installed correctly?" checks: skill-drift +
installed-version comparison, doctor/repair runners, and GitHub issue-status
lookups. lib/boot_checks.py re-imports these functions by name so
lib/boot_render.py and any direct `boot_checks.<name>()` caller (including
tests/test_security_regression.py's importlib load of boot_checks.py) keep
resolving unchanged.

Pure refactor: behavior is byte-for-byte identical to before the split.

See lib/boot_memory.py's own module docstring and
tests/test_migrate_statusline.py for why the `git_helpers` import below is
deferred into check_version_mismatch()'s function body rather than hoisted
to module level — this module is a real, stably-named module (first `import
boot_health` anywhere in a process caches it for that process, transitively
triggered by `from boot_health import ...` in lib/boot_checks.py), and a
module-level `from git_helpers import run_git` could freeze `run_git` to a
test's temporary stub forever if this module's first-ever import happened
to land inside that stub's window.
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time

from version import VERSION as PLUGIN_VERSION

from boot_memory import _sanitize_trailer_value

try:
    # SEC-LOW-NEW-05: symlink-safe reader for manifest.json, symmetric with
    # boot_memory.py's _read_glossary_cache() guard (SEC-MED-NEW-02) — a
    # symlink planted at the manifest path (pointing outside the repo) must
    # be rejected exactly like "no manifest present", never followed.
    # Imported defensively: tests/test_migrate_statusline.py stubs out
    # git_helpers with a minimal fake module that predates this helper.
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink


CACHE_BASE_DIR = os.path.join(os.path.expanduser("~"), ".claude", "plugins", "cache", "unmassk-claude-toolkit")
REPO_BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _md5_file(path: str) -> str:
    """Return MD5 hex digest of a file's content."""
    h = hashlib.md5()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def _latest_version_dir(plugin_cache_dir: str) -> str | None:
    """Return the path to the latest semver version directory under plugin_cache_dir."""
    try:
        versions = [
            d for d in os.listdir(plugin_cache_dir)
            if os.path.isdir(os.path.join(plugin_cache_dir, d))
        ]
    except OSError:
        return None
    if not versions:
        return None
    # Sort by semver (tuple of ints), fall back to string sort
    def _semver_key(v: str):
        try:
            return tuple(int(x) for x in v.split("."))
        except ValueError:
            return (0, 0, 0)
    latest = max(versions, key=_semver_key)
    return os.path.join(plugin_cache_dir, latest)


def _build_repo_skill_index() -> dict[str, str]:
    """Build a mapping of skill_name -> SKILL.md path from the repo source.

    Scans all <repo>/<plugin-dir>/skills/<skill-name>/SKILL.md paths.
    Returns dict: skill_name -> absolute path.
    """
    index: dict[str, str] = {}
    try:
        repo_entries = os.listdir(REPO_BASE_DIR)
    except OSError:
        return index
    for entry in repo_entries:
        skills_dir = os.path.join(REPO_BASE_DIR, entry, "skills")
        if not os.path.isdir(skills_dir):
            continue
        try:
            skill_names = os.listdir(skills_dir)
        except OSError:
            continue
        for skill_name in skill_names:
            skill_md = os.path.join(skills_dir, skill_name, "SKILL.md")
            if os.path.isfile(skill_md):
                index[skill_name] = skill_md
    return index


def check_skill_drift() -> list[str] | None:
    """Compare cached SKILL.md files against repo source using MD5.

    Scans every installed plugin's latest cached version, finds all SKILL.md
    files, and compares them to the matching file in the repo source tree.

    Returns a list of warning strings for drifted skills, or None if all OK
    or if the check cannot run (cache or repo not found).

    Designed to complete well under 200ms on typical installations.
    """
    if not os.path.isdir(CACHE_BASE_DIR) or not os.path.isdir(REPO_BASE_DIR):
        return None

    repo_index = _build_repo_skill_index()
    if not repo_index:
        return None

    drifted: list[str] = []

    try:
        plugins = os.listdir(CACHE_BASE_DIR)
    except OSError:
        return None

    for plugin_name in plugins:
        plugin_cache_dir = os.path.join(CACHE_BASE_DIR, plugin_name)
        if not os.path.isdir(plugin_cache_dir):
            continue
        latest_dir = _latest_version_dir(plugin_cache_dir)
        if not latest_dir:
            continue
        skills_dir = os.path.join(latest_dir, "skills")
        if not os.path.isdir(skills_dir):
            continue
        try:
            skill_names = os.listdir(skills_dir)
        except OSError:
            continue
        for skill_name in skill_names:
            cached_skill = os.path.join(skills_dir, skill_name, "SKILL.md")
            if not os.path.isfile(cached_skill):
                continue
            repo_skill = repo_index.get(skill_name)
            if not repo_skill:
                continue  # Skill not in repo — skip (may be published-only)
            try:
                if _md5_file(cached_skill) != _md5_file(repo_skill):
                    drifted.append(f"⚠️ drift: {plugin_name}/{skill_name} cache differs from repo source")
            except OSError:
                continue

    return drifted if drifted else None


def check_version_mismatch() -> str | None:
    """Compare installed manifest version vs plugin VERSION constant.

    Returns warning string if mismatch, None if OK or can't check.
    """
    from git_helpers import run_git

    code, root = run_git(["rev-parse", "--show-toplevel"])
    if code != 0 or not root:
        return None
    manifest_path = os.path.join(root, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        # SEC-LOW-NEW-05: never follow a symlink planted at the manifest
        # path — treat it exactly like "no manifest present" (see
        # open_no_follow_symlink's docstring for the O_NOFOLLOW guarantee).
        with open_no_follow_symlink(manifest_path, "r") as f:
            manifest = json.load(f)
        installed = manifest.get("version", "")
        if installed and installed != PLUGIN_VERSION:
            # SEC-CRIT-NEW-04: the manifest's "version" field is not
            # trusted content — sanitize it the same way Decision/Memo/
            # Remember values already are before embedding it in the
            # STATUS section's upgrade-suggestion line.
            safe_installed = _sanitize_trailer_value(str(installed))
            return f"Plugin v{PLUGIN_VERSION} available (installed: v{safe_installed}). Suggest /plugin update"
        return None
    except (json.JSONDecodeError, OSError):
        return None


def run_doctor() -> dict:
    """Run doctor silently and return parsed JSON."""
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    doctor = os.path.join(plugin_root, "bin", "git-memory-doctor.py")
    if not os.path.isfile(doctor):
        return {"status": "skip", "checks": []}
    try:
        result = subprocess.run(
            [sys.executable, doctor, "--json"],
            capture_output=True, text=True, timeout=15,
        )
        if result.returncode == 0:
            return json.loads(result.stdout)
    except Exception as e:
        # CRB-05: boot must never fail here — the design is intentional —
        # but leave a one-line breadcrumb instead of swallowing silently.
        print(f"[session-start-boot] BOOT-WARNING: {type(e).__name__} in run_doctor", file=sys.stderr)
    return {"status": "error", "checks": []}


def run_repair() -> bool:
    """Run repair silently. Returns True if successful."""
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repair = os.path.join(plugin_root, "bin", "git-memory-repair.py")
    if not os.path.isfile(repair):
        return False
    try:
        result = subprocess.run(
            [sys.executable, repair, "--auto"],
            capture_output=True, text=True, timeout=15,
        )
        return result.returncode == 0
    except Exception as e:
        # CRB-05: boot must never fail here — the design is intentional —
        # but leave a one-line breadcrumb instead of swallowing silently.
        print(f"[session-start-boot] BOOT-WARNING: {type(e).__name__} in run_repair", file=sys.stderr)
        return False


def check_issue_status(pending_items: list[dict], timeout: float = 5.0) -> dict[int, dict]:
    """Check GitHub issue status for pending items with issue refs.

    Launches parallel gh calls and collects results within timeout.
    Returns dict mapping issue number to {"state": "OPEN"|"CLOSED", "title": "..."}.
    Missing entries mean gh failed or timed out.
    """
    issues = {item["issue"] for item in pending_items if item.get("issue")}
    if not issues:
        return {}

    # Check gh availability (single probe)
    try:
        probe = subprocess.run(
            ["gh", "auth", "status"],
            capture_output=True, timeout=3,
        )
        if probe.returncode != 0:
            return {}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {}

    # Launch parallel gh calls
    procs: dict[int, subprocess.Popen] = {}
    for issue_num in issues:
        try:
            procs[issue_num] = subprocess.Popen(
                ["gh", "issue", "view", str(issue_num), "--json", "state,title"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
            )
        except OSError:
            continue

    # Collect results with global timeout
    deadline = time.time() + timeout
    results: dict[int, dict] = {}
    for issue_num, proc in procs.items():
        remaining = max(0.1, deadline - time.time())
        try:
            stdout, _ = proc.communicate(timeout=remaining)
            if proc.returncode == 0 and stdout.strip():
                data = json.loads(stdout)
                results[issue_num] = {
                    "state": data.get("state", "OPEN"),
                    "title": data.get("title", ""),
                }
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            proc.kill()
            proc.wait()

    return results


def _issue_matches_next(next_text: str, issue_title: str) -> bool:
    """Check if a GitHub issue title plausibly matches a Next trailer text.

    Prevents false positives from issue #N belonging to a different context.
    Returns True if >= 2 keywords (3+ chars) overlap.
    """
    stop = {"the", "and", "for", "from", "with", "that", "this", "not", "are", "was"}

    def keywords(text: str) -> set[str]:
        return {
            w.lower() for w in re.findall(r"[a-zA-Z]{3,}", text)
            if w.lower() not in stop
        }

    return len(keywords(next_text) & keywords(issue_title)) >= 2
