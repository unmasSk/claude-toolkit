"""
Boot git/repo-state checks for session-start-boot.py (split out of
lib/boot_checks.py, Cerberus round-6 LOC audit).

Owns the "read git/repo state for this boot" concern: branch/ahead-behind,
scopes.json, consolidation threshold, and commit timeline — moved here
together with their only callers (parse_branch_keywords(), time_ago()) per
the same rationale as the original round-5 split: lib/boot_checks.py (and
now this module) must never import FROM lib/boot_render.py (confirmed
unidirectional DAG: boot_memory <- boot_health/boot_git_checks <- boot_checks
<- boot_render). lib/boot_checks.py re-imports these functions by name so
lib/boot_render.py and any direct `boot_checks.<name>()` caller (including
tests/test_security_regression.py's importlib load of boot_checks.py) keep
resolving unchanged.

Pure refactor: behavior is byte-for-byte identical to before the split.
"""

import json
import os
import re
from datetime import datetime, timezone

from boot_memory import _sanitize_trailer_value

try:
    # SEC-LOW-NEW-05: symlink-safe reader, symmetric with boot_memory.py's
    # _read_glossary_cache() guard (SEC-MED-NEW-02) — a symlink planted at
    # git-memory-scopes.json must be rejected exactly like "file absent".
    # Imported defensively: tests/test_migrate_statusline.py stubs out
    # git_helpers with a minimal fake module that predates this helper.
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink


# Commits since last context(consolidation) before warning.
BOOT_CONSOLIDATION_THRESHOLD = 50


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
