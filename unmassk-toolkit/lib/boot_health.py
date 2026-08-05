"""
Boot health checks for session-start-boot.py (split out of lib/boot_checks.py,
Cerberus round-6 LOC audit).

Owns the "is the plugin/repo installed correctly?" checks: skill-drift +
installed-version comparison, and doctor/repair runners. lib/boot_checks.py
re-imports these functions by name so lib/boot_render.py and any direct
`boot_checks.<name>()` caller keep resolving unchanged.

Memory v2 cleanup: the GitHub issue-status lookups (check_issue_status(),
_issue_matches_next()) were removed with the rest of the v1 memory system —
they only ever fed the RESUME section's Next: filtering in the now-deleted
lib/boot_memory.py/lib/boot_render.py (see
docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3).

Pure refactor otherwise: the surviving functions are byte-for-byte identical
to before the split.

See tests/test_migrate_statusline.py for why the `git_helpers` import below
is deferred into check_version_mismatch()'s function body rather than
hoisted to module level — this module is a real, stably-named module (first
`import boot_health` anywhere in a process caches it for that process,
transitively triggered by `from boot_health import ...` in
lib/boot_checks.py), and a module-level `from git_helpers import run_git`
could freeze `run_git` to a test's temporary stub forever if this module's
first-ever import happened to land inside that stub's window.
"""

import hashlib
import json
import os
import subprocess
import sys

from version import VERSION as PLUGIN_VERSION

from parsing import sanitize_trailer_value

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


def _is_real_repo_source(repo_base_dir: str, cache_base_dir: str) -> bool:
    """True only if REPO_BASE_DIR looks like a genuine dev-repo checkout of
    the toolkit source -- never a plugin cache directory mistaken for one.

    Issue #63 point 3 (confirmed bug, not designed behavior -- Bilbo's map,
    boot-simplification-63-map.md section 3): REPO_BASE_DIR is computed as
    dirname^3(__file__), arithmetic that is only correct when this module
    runs from a real <GIT_ROOT>/<plugin-dir>/lib/boot_health.py checkout.
    In production (module running from
    ~/.claude/plugins/cache/.../unmassk-toolkit/<version>/lib/), the same
    arithmetic lands on the plugin's OWN cache directory -- whose children
    are VERSION dirs, not plugin dirs -- a path that always exists, so the
    old `if not os.path.isdir(REPO_BASE_DIR)` guard never caught it.

    Two independent signals, both required:
      1. REPO_BASE_DIR is not CACHE_BASE_DIR itself, nor nested inside it
         (in either direction) -- a real dev-repo checkout is never
         physically located inside the plugin cache tree.
      2. REPO_BASE_DIR has a top-level ".git" entry (a directory for a
         normal clone, a file for a worktree) -- the one marker every real
         repo checkout has and a cache install never ships (copytree-style
         cache installs exclude .git; confirmed by
         test_skill_drift_repo_source_detection.py's own fixture, which
         explicitly excludes ".git" to simulate this).
    """
    repo_base_dir = os.path.abspath(repo_base_dir)
    cache_base_dir = os.path.abspath(cache_base_dir)
    try:
        common = os.path.commonpath([repo_base_dir, cache_base_dir])
    except ValueError:
        # Different drives on Windows -- definitely not nested either way.
        common = None
    if common in (repo_base_dir, cache_base_dir):
        return False
    return os.path.exists(os.path.join(repo_base_dir, ".git"))


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


def _build_repo_skill_index() -> dict[str, dict[str, str]]:
    """Build a mapping of plugin_dir_name -> {skill_name -> SKILL.md path}
    from the repo source.

    Scans all <repo>/<plugin-dir>/skills/<skill-name>/SKILL.md paths.
    Returns a dict scoped by plugin directory name (issue #63 point 3,
    Dante's contract note): a flat skill_name -> path index is not a safe
    lookup key across a monorepo with several plugin directories -- two
    different plugins could ship a same-named skill with different content,
    and comparing cached content against the WRONG plugin's source would
    produce a meaningless drift verdict even when REPO_BASE_DIR correctly
    resolves to real source. check_skill_drift() looks up by the same
    plugin_name it already has from the cache-side listing.
    """
    index: dict[str, dict[str, str]] = {}
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
        plugin_index: dict[str, str] = {}
        for skill_name in skill_names:
            skill_md = os.path.join(skills_dir, skill_name, "SKILL.md")
            if os.path.isfile(skill_md):
                plugin_index[skill_name] = skill_md
        if plugin_index:
            index[entry] = plugin_index
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

    # Issue #63 point 3: no real toolkit source repo present -> skip the
    # entire check silently (not just "no warnings found" -- never even
    # build an index or compare anything). See _is_real_repo_source()'s
    # docstring for why the old isdir() guard above never caught this.
    if not _is_real_repo_source(REPO_BASE_DIR, CACHE_BASE_DIR):
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
        # Scoped by plugin_name (issue #63 point 3, Dante's contract note):
        # never fall back to an unscoped, cross-plugin skill_name lookup --
        # a skill not shipped by THIS plugin in the repo source must be
        # treated exactly like "skill not in repo" (skip), never matched
        # against a same-named skill belonging to a different plugin.
        plugin_repo_index = repo_index.get(plugin_name, {})
        for skill_name in skill_names:
            cached_skill = os.path.join(skills_dir, skill_name, "SKILL.md")
            if not os.path.isfile(cached_skill):
                continue
            repo_skill = plugin_repo_index.get(skill_name)
            if not repo_skill:
                continue  # Skill not in repo (or wrong plugin) — skip
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
    from git_helpers import run_git, verify_path_within_project
    # Issue #64: deferred for the same reason git_helpers is above (see this
    # module's docstring) -- upgrade_check.py is a real, stably-named module
    # whose own module-level `from version import VERSION as PLUGIN_VERSION`
    # must not risk running during a test's temporary stub window.
    from upgrade_check import _parse_semver

    code, root = run_git(["rev-parse", "--show-toplevel"])
    if code != 0 or not root:
        return None
    manifest_path = os.path.join(root, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        # SEC-T1-002 (Argus, issue #63): open_no_follow_symlink() below only
        # guards manifest.json's FINAL path component -- a .claude/.unmassk
        # parent that is ITSELF a symlink to a directory holding a real,
        # non-symlink manifest.json slips past it undetected. This gate has
        # the biggest blast radius of the 3 read sites: it's called
        # unguarded from render_status_section() in the main boot hook, so a
        # poisoned manifest here would have silently suppressed the
        # upgrade-suggestion warning forever. verify_path_within_project()
        # resolves every intermediate component via realpath() and rejects
        # anything escaping root; caught by the broad except below like any
        # other untrustworthy manifest.
        verify_path_within_project(manifest_path, root)
        # SEC-LOW-NEW-05: never follow a symlink planted at the manifest
        # path — treat it exactly like "no manifest present" (see
        # open_no_follow_symlink's docstring for the O_NOFOLLOW guarantee).
        with open_no_follow_symlink(manifest_path, "r") as f:
            manifest = json.load(f)
        installed = manifest.get("version", "")
        # Issue #64: raw string inequality (`installed != PLUGIN_VERSION`)
        # suggested an update even when the installed version was actually
        # NEWER than the code (confirmed PoC: manifest "9.9.9" vs code
        # "1.19.4" still produced an upgrade suggestion, backwards). Reuse
        # the same numeric semver comparator upgrade_check.needs_upgrade()
        # already trusts for its own Check 2 (`manifest_tuple < code_tuple`)
        # instead of writing a second hand-rolled parser -- one source of
        # truth for "is the code genuinely newer than what's installed".
        # Fail-safe: an unparseable version on either side suppresses the
        # warning, same discipline as the rest of this function.
        if installed:
            installed_tuple = _parse_semver(installed)
            code_tuple = _parse_semver(PLUGIN_VERSION)
            if installed_tuple is not None and code_tuple is not None and installed_tuple < code_tuple:
                # SEC-CRIT-NEW-04: the manifest's "version" field is not
                # trusted content — sanitize it the same way Decision/Memo/
                # Remember values already are before embedding it in the
                # STATUS section's upgrade-suggestion line.
                safe_installed = sanitize_trailer_value(str(installed))
                return f"Plugin v{PLUGIN_VERSION} available (installed: v{safe_installed}). Suggest /plugin update"
        return None
    except Exception:
        # SEC-T1-001 (Argus, issue #63): a maliciously deep-nested manifest
        # raises RecursionError from json.load, which escaped the previous
        # narrow (json.JSONDecodeError, OSError) tuple and crashed the whole
        # boot hook (called unguarded from render_status_section). Broadened
        # to Exception so a poisoned manifest fails safe like any other
        # unreadable manifest, matching the pattern already used in
        # lib/upgrade_check.py's needs_upgrade().
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
            capture_output=True, text=True, encoding="utf-8", timeout=15,
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
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
        return result.returncode == 0
    except Exception as e:
        # CRB-05: boot must never fail here — the design is intentional —
        # but leave a one-line breadcrumb instead of swallowing silently.
        print(f"[session-start-boot] BOOT-WARNING: {type(e).__name__} in run_repair", file=sys.stderr)
        return False
