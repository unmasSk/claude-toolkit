"""
Boot I/O checks for session-start-boot.py (CRB round-4 second split of
lib/boot_render.py).

Owns every subprocess/filesystem/network check the boot briefing needs:
skill-drift + installed-version comparison, doctor/repair runners, and
GitHub issue-status lookups. Moved out of lib/boot_render.py (Cerberus
round-4): that module had grown back to 875 lines, past the project's
500-line limit, mixing pure "given inputs, produce these briefing lines"
renderers with real I/O (subprocess.run/Popen, filesystem scans, manifest
reads) — two genuinely different concerns that happened to share a file.
lib/boot_render.py re-imports these functions by name so
render_status_section()/render_resume_section() call them unchanged.

Pure refactor: behavior is byte-for-byte identical to before the split.

See lib/boot_memory.py's own module docstring and
tests/test_migrate_statusline.py for why the `git_helpers` import below is
deferred into check_version_mismatch()'s function body rather than hoisted
to module level — this module is a real, stably-named module (first `import
boot_checks` anywhere in a process caches it for that process, transitively
triggered by `from boot_checks import ...` in lib/boot_render.py), and a
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
from datetime import datetime, timezone

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

# Moved here with render_consolidation_section() — commits since last
# context(consolidation) before warning.
BOOT_CONSOLIDATION_THRESHOLD = 50


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


# ── Moved from lib/boot_render.py (Cerberus round 5, second CRB T2-1 pass) ──
#
# render_branch_section(), render_scopes_section(), render_consolidation_section(),
# get_timeline(), and get_last_context_time() all do real I/O (subprocess via
# run_git, filesystem reads via open()/os.listdir()) — the same class of
# concern this module already owns (see module docstring). boot_render.py had
# grown back past the 500-line limit; this is the second extraction pass.
#
# parse_branch_keywords() and time_ago() are pure (no I/O) but are moved
# alongside render_branch_section()/get_timeline()/get_last_context_time()
# — their only callers — rather than left behind in boot_render.py, because
# boot_checks.py must never import FROM boot_render.py (confirmed
# unidirectional DAG: boot_memory <- boot_checks <- boot_render; boot_render
# re-imports from boot_checks, never the other way around). Leaving them in
# boot_render.py would have forced exactly that reverse import.
#
# lib/boot_render.py re-imports all of these by name (mirroring
# check_version_mismatch/run_doctor/run_repair above) so render_timeline_section()
# and render_resume_section() (which stay in boot_render.py) keep calling
# get_timeline()/get_last_context_time() unchanged, and so hooks/session-start-boot.py's
# `from boot_render import (render_branch_section, render_consolidation_section,
# render_scopes_section, ...)` keeps resolving without any change there.

def parse_branch_keywords(branch: str) -> tuple[list[str], str | None]:
    """Extract keywords and issue number from branch name.

    'feat/issue-42-auth-refactor' -> (['auth', 'refactor', '42'], '#42')
    'main' -> ([], None)
    """
    # Strip prefix (feat/, fix/, chore/, etc.)
    stripped = re.sub(r"^(feat|fix|chore|refactor|docs|test|ci|perf)/", "", branch)
    # Extract issue number
    issue_match = re.search(r"(?:issue[- ]?|#)(\d+)", stripped, re.IGNORECASE)
    issue_ref = f"#{issue_match.group(1)}" if issue_match else None
    # Extract keywords (split on -, _, /, filter short/noise)
    tokens = re.split(r"[-_/]", stripped)
    noise = {"feat", "fix", "chore", "issue", "refactor", "dev", "main", "master", "staging"}
    keywords = [t.lower() for t in tokens if len(t) > 2 and t.lower() not in noise]
    return keywords, issue_ref


def time_ago(iso_or_unix: str) -> str:
    """Convert ISO timestamp or unix timestamp to human-readable 'N ago' string.

    '2026-03-13T08:00:00+00:00' -> '2h ago'
    """
    try:
        if iso_or_unix.isdigit():
            dt = datetime.fromtimestamp(int(iso_or_unix), tz=timezone.utc)
        else:
            # git log %aI format
            dt = datetime.fromisoformat(iso_or_unix)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        elif seconds < 604800:
            return f"{seconds // 86400}d ago"
        else:
            return f"{seconds // 604800}w ago"
    except (ValueError, TypeError, OSError):
        return "unknown"


def get_timeline(n: int = 10, suppress_scopes: set[str] | None = None) -> list[str]:
    """Get last N commits as timeline entries with time_ago.

    suppress_scopes: if provided, commits whose parsed scope is in this set are
    omitted. Used to hide non-crowned decision commits when a crowned entry
    exists for that scope.
    """
    from parsing import parse_scope
    from git_helpers import run_git

    code, output = run_git([
        "log", f"-n{n}",
        "--pretty=format:%h\x1f%s\x1f%aI"
    ])
    if code != 0 or not output:
        return []
    entries = []
    for line in output.split("\n"):
        parts = line.strip().split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, subject, date_str = parts
        if suppress_scopes:
            commit_scope = parse_scope(subject) or ""
            if commit_scope in suppress_scopes:
                continue
        entries.append(f"  {sha} {_sanitize_trailer_value(subject)} | {time_ago(date_str)}")
    return entries


def get_last_context_time() -> str | None:
    """Get the timestamp of the last context() commit as time_ago string."""
    from git_helpers import run_git

    code, output = run_git([
        "log", "-n30",
        "--pretty=format:%h\x1f%s\x1f%aI"
    ])
    if code != 0 or not output:
        return None
    for line in output.split("\n"):
        parts = line.strip().split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, subject, date_str = parts
        cleaned = re.sub(r"^[^\w#]+", "", subject).strip()
        if cleaned.lower().startswith("context("):
            return time_ago(date_str)
    return None


def render_branch_section() -> tuple[list[str], str, list[str], str | None, str]:
    """Render the BRANCH section.

    Returns (lines, branch, branch_keywords, branch_issue, ahead_behind) —
    reused downstream for Next-item partitioning and the short banner.
    `behind_n` (the pull recommendation) is only needed inside this
    function and is not part of the return value (T3-2: it used to be
    returned but was never actually consumed by any caller).
    """
    from git_helpers import run_git

    lines: list[str] = []
    _, branch = run_git(["branch", "--show-current"])
    branch = branch or "(detached HEAD)"
    # SEC-CRIT-NEW-04: git's ref-name rules don't block injection markers in
    # a branch name, and the RETURNED `branch` value (not just the `lines`
    # rendered here) reaches the UNCONDITIONAL stdout banner
    # (render_boot_banner_lines() in hooks/session-start-boot.py) on every
    # boot — the most severe of the 5 unsanitized sites. Sanitize once, here,
    # so every downstream consumer of the return value gets the safe value.
    branch = _sanitize_trailer_value(branch)
    branch_keywords, branch_issue = parse_branch_keywords(branch)

    # Ahead/behind (single rev-list call with --left-right --count)
    ahead_behind = ""
    ahead_n = 0
    behind_n = 0
    if branch and branch != "(detached HEAD)":
        code_ab, ab_out = run_git(["rev-list", "--left-right", "--count", f"HEAD...@{{u}}"])
        if code_ab == 0 and ab_out.strip():
            parts = ab_out.strip().split()
            if len(parts) == 2:
                ahead_n, behind_n = int(parts[0]), int(parts[1])
                ahead_behind = f" [{ahead_n}/{behind_n} vs upstream]"

    lines.append(f"BRANCH: {branch}{ahead_behind}")

    # Dirty state
    _, status_porcelain = run_git(["status", "--porcelain"])
    if status_porcelain:
        dirty_count = len([l for l in status_porcelain.splitlines() if l.strip()])
        lines.append(f"  DIRTY: {dirty_count} files")

    # Pull recommendation (reuses behind_n from the single rev-list call above)
    if behind_n > 0:
        lines.append(f"  PULL RECOMMENDED: remote is {behind_n} ahead")

    lines.append("")
    return lines, branch, branch_keywords, branch_issue, ahead_behind


def render_scopes_section(project_root: str | None) -> list[str]:
    """Render the SCOPES section."""
    lines: list[str] = []
    scopes_file = os.path.join(project_root, ".claude", "git-memory-scopes.json") if project_root else None
    # Fallback: search in agent-memory directories
    if scopes_file and not os.path.isfile(scopes_file) and project_root:
        agent_mem = os.path.join(project_root, ".claude", "agent-memory")
        if os.path.isdir(agent_mem):
            for agent_dir in os.listdir(agent_mem):
                candidate = os.path.join(agent_mem, agent_dir, "scopes.json")
                if os.path.isfile(candidate):
                    scopes_file = candidate
                    break
    scopes_exist = scopes_file and os.path.isfile(scopes_file)
    if scopes_exist:
        try:
            # SEC-MED-NEW-12: never follow a symlink planted at
            # git-memory-scopes.json.
            with open_no_follow_symlink(scopes_file, "r") as f:
                scopes_data = json.load(f)
            scope_map = scopes_data.get("scopes", {})
            if scope_map:
                lines.append("SCOPES:")
                for scope_name, scope_info in scope_map.items():
                    # SEC-CRIT-002: scopes.json is not exclusively agent-authored
                    # (compromised collaborator commit, corrupted Bilbo run) — sanitize
                    # every embedded field the same way Decision/Memo/Remember already are.
                    safe_name = _sanitize_trailer_value(str(scope_name))
                    desc = scope_info.get("description", "") if isinstance(scope_info, dict) else str(scope_info)
                    safe_desc = _sanitize_trailer_value(str(desc))
                    children = scope_info.get("children", {}) if isinstance(scope_info, dict) else {}
                    if children:
                        safe_children = [_sanitize_trailer_value(str(k)) for k in children]
                        child_list = ", ".join(f"{safe_name}/{k}" for k in safe_children)
                        lines.append(f"  {safe_name}: {safe_desc} [{child_list}]")
                    else:
                        lines.append(f"  {safe_name}: {safe_desc}")
                lines.append("")
        except (json.JSONDecodeError, OSError):
            pass  # Silently skip if file is corrupt
    elif project_root:
        lines.append("SCOPES: not generated yet")
        lines.append(
            "  ACTION: Launch Bilbo (subagent_type=unmassk-toolkit:bilbo) to analyze the project "
            "structure and generate .claude/agent-memory/unmassk-crew-bilbo/scopes.json. "
            "The agent should: scan directories, detect frameworks, extract existing scopes "
            "from git log, and write a JSON with version, project_type, scopes (2 levels max), "
            "existing_scopes, and notes. Run it in background."
        )
        lines.append("")
    return lines


def render_consolidation_section() -> list[str]:
    """Render the CONSOLIDATE trigger section."""
    from git_helpers import commits_since_last_consolidation

    lines: list[str] = []

    _consolidation_threshold = BOOT_CONSOLIDATION_THRESHOLD
    _env_threshold = os.environ.get("GIT_MEMORY_CONSOLIDATION_THRESHOLD", "")
    if _env_threshold:
        try:
            _consolidation_threshold = int(_env_threshold)
        except (ValueError, TypeError):
            pass  # invalid override → fall back to default; never crash boot

    _commits_since = commits_since_last_consolidation()
    if _commits_since >= _consolidation_threshold:
        lines.append("CONSOLIDATE:")
        lines.append(
            f"  ⚠️ {_commits_since} commits since last consolidation. "
            "Time to consolidate: invoke Gitto (consolidator mode, additive — deletes nothing)."
        )
        lines.append("")

    return lines


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
