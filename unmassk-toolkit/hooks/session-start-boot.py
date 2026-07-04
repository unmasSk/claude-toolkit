#!/usr/bin/env python3
"""
session-start-boot -- Auto-boot hook for SessionStart.

Runs automatically when Claude starts a new session. Executes doctor
silently, extracts memory from recent commits, and prints a compact
summary that Claude receives as context.

Exit codes:
  0: Always (never blocks session start)
"""

import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "lib"))

from git_helpers import run_git, commits_since_last_consolidation
try:
    # Reuse the canonical .claude/.unmassk/ creation helper instead of
    # reinventing it locally (Cerberus suggestion). Imported defensively:
    # some tests stub out git_helpers with a minimal fake module that
    # predates this helper, and the boot hook must still import cleanly
    # against that stub.
    from git_helpers import ensure_runtime_dir
except ImportError:
    ensure_runtime_dir = None
try:
    # SEC-CRIT-001: symlink-safe writer for boot-log/glossary-cache/.gitignore.
    # Imported defensively for the same reason as ensure_runtime_dir above —
    # tests/test_migrate_statusline.py stubs out git_helpers with a fake
    # module that predates this helper. Fallback reimplements the identical
    # O_NOFOLLOW logic locally so the safety property holds either way.
    from git_helpers import open_no_follow_symlink
except ImportError:
    def open_no_follow_symlink(path: str, mode: str = "w", encoding: str = "utf-8"):
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        flags |= os.O_APPEND if mode == "a" else os.O_TRUNC
        fd = os.open(path, flags, 0o600)
        return os.fdopen(fd, mode, encoding=encoding)
from parsing import normalize, parse_scope
from version import VERSION as PLUGIN_VERSION

# CRB-04: memory extraction (extract_memory/extract_glossary/crown logic/
# glossary cache) and one-shot migrations live in dedicated lib/ modules —
# see lib/boot_memory.py and lib/boot_migrations.py. Re-exported here by
# name so `python3 session-start-boot.py` behaves identically and so tests
# that load this module directly (e.g. tests/test_crown.py calling
# boot.extract_memory()) keep working unchanged.
from boot_memory import (
    MAX_DECISIONS,
    _crown_replace,
    _get_project_root,
    _sanitize_trailer_value,
    extract_glossary,
    extract_glossary_cached,
    extract_memory,
)
from boot_migrations import (
    _migrate_runtime_to_unmassk,
    _migrate_stale_context_writer_statusline,
    _migrate_untrack_generated_jsons,
)


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
    code, root = run_git(["rev-parse", "--show-toplevel"])
    if code != 0 or not root:
        return None
    manifest_path = os.path.join(root, ".claude", ".unmassk", "manifest.json")
    if not os.path.isfile(manifest_path):
        return None
    try:
        with open(manifest_path) as f:
            manifest = json.load(f)
        installed = manifest.get("version", "")
        if installed and installed != PLUGIN_VERSION:
            return f"Plugin v{PLUGIN_VERSION} available (installed: v{installed}). Suggest /plugin update"
        return None
    except (json.JSONDecodeError, OSError):
        return None


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


BANNER_FIELD_MAX_LEN = 60  # defensive cap on any single field embedded in the short banner


def _truncate_banner_field(text: str, max_len: int = BANNER_FIELD_MAX_LEN) -> str:
    """Bound a value embedded verbatim in the short banner.

    Git branch names (and, defensively, other embedded paths) have no
    practical length ceiling, so an unusually long one could alone push the
    banner past its <1000-byte stdout safety budget (Cerberus regression:
    TestBannerByteBudgetWithLongBranchName). Truncate with an ellipsis
    rather than fail — the banner only needs to be recognizable, the full
    untruncated value is always in the boot log file.
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


def score_branch_relevance(text: str, keywords: list[str]) -> int:
    """Score how relevant a text is to branch keywords. Higher = more relevant."""
    if not keywords:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


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


BOOT_CONSOLIDATION_THRESHOLD = 50  # commits since last context(consolidation) before warning

# Scaling limits (from design doc)
BOOT_MAX_BRANCH_DECISIONS = 10
BOOT_MAX_OTHER_DECISIONS = 10
BOOT_MAX_DECISIONS = 20
BOOT_MAX_BRANCH_MEMOS = 10
BOOT_MAX_OTHER_MEMOS = 10
BOOT_MAX_MEMOS = 20
BOOT_MAX_REMEMBERS = 30
BOOT_MAX_BRANCH_NEXT = 10
BOOT_MAX_OTHER_NEXT = 5
BOOT_MAX_NEXT = 10
BOOT_MAX_TIMELINE = 10

# CRB-06: named GC-warning thresholds (previously inline magic numbers).
MEMO_GC_THRESHOLD = 10
REMEMBER_GC_THRESHOLD = 8

# CRB-09: the background `git fetch` is best-effort and non-critical — it
# must not hold up session start for as long as a real git operation might
# (GIT_TIMEOUT default is 10s). A short, dedicated timeout bounds the worst
# case without touching the shared default used by everything else.
BOOT_FETCH_TIMEOUT = 5

# SEC-MED-005: crowned Decision/Memo/Remember entries intentionally bypass the
# normal MAX_DECISIONS/MAX_MEMOS/BOOT_MAX_REMEMBERS count-eviction budget (a
# crowned entry must never be evicted by a newer, non-crowned one). Contract
# decided by Dante: reuse MAX_DECISIONS (20) as the ceiling on TOTAL distinct
# crowned entries shown per section, and cap a single crowned trailer VALUE
# at 2000 chars (truncated, never discarded) so one oversized crowned commit
# can't blow up the boot log without limit.
CROWN_COUNT_CAP = MAX_DECISIONS  # 20 — same ceiling reused for crowned Decisions/Memos/Remembers
CROWN_VALUE_MAX_LEN = 2000


def _truncate_crown_value(text: str, max_len: int = CROWN_VALUE_MAX_LEN) -> str:
    """Bound a single crowned trailer value's length (SEC-MED-005).

    Crowned entries bypass the normal count-eviction budget, so nothing
    else bounds how large a single crowned trailer value can grow.
    Truncate (never discard) so an oversized crowned commit can't blow up
    the boot log file without limit.
    """
    if len(text) <= max_len:
        return text
    return text[:max_len] + "…"


# Stdout-truncation fix: the full briefing (everything, nothing shortened)
# is always written to this fixed-path file. stdout itself is UNCONDITIONALLY
# the short banner, regardless of repo size — see House's diagnosis and
# TestBootStdoutMinimalWithHeavyContent / TestBootLogFileFullContent. A prior
# byte-threshold approach (STDOUT_FULL_INLINE_BUDGET_BYTES) left the same bug
# class open: Yoda found a normal repo with 25 scopes (3193 bytes, under the
# old 6000-byte threshold) whose Next: still fell past the harness's real
# stdout truncation point. There is no safe threshold — the banner is always
# printed, and the only remaining full-text-on-stdout path is the write-
# failure fallback below (TestBootLogWriteFailureFallback).
BOOT_LOG_REL_PARTS = (".claude", ".unmassk", "boot-log-latest.txt")


def get_timeline(n: int = 10, suppress_scopes: set[str] | None = None) -> list[str]:
    """Get last N commits as timeline entries with time_ago.

    suppress_scopes: if provided, commits whose parsed scope is in this set are
    omitted. Used to hide non-crowned decision commits when a crowned entry
    exists for that scope.
    """
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
        entries.append(f"  {sha} {subject} | {time_ago(date_str)}")
    return entries


def get_last_context_time() -> str | None:
    """Get the timestamp of the last context() commit as time_ago string."""
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


def partition_by_relevance(items, keywords, text_fn):
    """Split items into (branch_scoped, other) based on keyword relevance.

    items: list of anything
    keywords: branch keywords
    text_fn: function to extract text from an item for scoring
    Returns (branch_scoped, other) where branch_scoped items are sorted by score descending.
    """
    if not keywords:
        return [], items
    scored = [(score_branch_relevance(text_fn(item), keywords), item) for item in items]
    # Sort branch-matching items by score descending
    branch_scoped = [item for _, item in sorted(
        [(s, i) for s, i in scored if s > 0], key=lambda x: -x[0]
    )]
    other = [item for score, item in scored if score == 0]
    return branch_scoped, other


def render_header_section(plugin_root: str) -> list[str]:
    """Render the HEADER section (plugin version + root path)."""
    return [f"[git-memory-boot] v{PLUGIN_VERSION} | {plugin_root}", ""]


def render_status_section() -> tuple[list[str], str, str]:
    """Run doctor/repair, check version + skill drift, render the STATUS section.

    Returns (lines, status, status_detail) — status/status_detail are also
    needed later, when the short banner is built at the end of boot.
    """
    lines: list[str] = []
    doctor_result = run_doctor()
    status = "ok"
    status_detail = ""
    if doctor_result.get("status") == "error":
        repaired = run_repair()
        if repaired:
            status = "warn"
            status_detail = " — auto-repaired issues"
        else:
            status = "error"
            status_detail = " — run doctor for details"

    version_warning = check_version_mismatch()
    skill_drift = check_skill_drift()

    lines.append(f"STATUS: {status}{status_detail}")
    if version_warning:
        lines.append(f"  {version_warning}")
    if skill_drift:
        for drift_warning in skill_drift:
            lines.append(f"  {drift_warning}")
    lines.append("")
    return lines, status, status_detail


def render_branch_section() -> tuple[list[str], str, list[str], str | None, str, int]:
    """Render the BRANCH section.

    Returns (lines, branch, branch_keywords, branch_issue, ahead_behind,
    behind_n) — all reused downstream (Next-item partitioning, the pull
    recommendation, the short banner).
    """
    lines: list[str] = []
    _, branch = run_git(["branch", "--show-current"])
    branch = branch or "(detached HEAD)"
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
    return lines, branch, branch_keywords, branch_issue, ahead_behind, behind_n


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
            with open(scopes_file) as f:
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


def render_resume_section(
    memory: dict, branch_issue: str | None, branch_keywords: list[str],
) -> list[str]:
    """Render the RESUME section (Last context / Issue / Next / Blockers)."""
    lines: list[str] = ["RESUME:"]

    # Last context with time_ago
    if memory.get("last_context"):
        ctx_time = get_last_context_time() or ""
        time_part = f" | {ctx_time}" if ctx_time else ""
        lines.append(f"  Last: {memory['last_context']}{time_part}")

    # Issue from branch
    if branch_issue:
        lines.append(f"  Issue (from branch): {branch_issue}")

    # Next items — filter closed issues + stale marker
    if memory.get("pending"):
        # Check issue status for items with refs
        issue_status = check_issue_status(memory["pending"])

        # Filter and annotate
        filtered_pending = []
        now = int(time.time())
        stale_threshold = 7 * 24 * 3600  # 7 days

        for item in memory["pending"]:
            issue_num = item.get("issue")

            # If has issue ref and we got status, check if closed
            if issue_num and issue_num in issue_status:
                status = issue_status[issue_num]
                if status["state"] == "CLOSED" and _issue_matches_next(item["text"], status["title"]):
                    continue  # Skip — issue closed and matches

            # Stale marker for items without issue
            display = item["display"]
            if not issue_num and item.get("timestamp") and item["timestamp"] > 0:
                age = now - item["timestamp"]
                if age > stale_threshold:
                    display = display.replace(": ", ": [stale] ", 1)

            filtered_pending.append({**item, "display": display})

        # Branch-scoped partitioning
        if filtered_pending:
            branch_next, other_next = partition_by_relevance(
                filtered_pending, branch_keywords, lambda x: x["display"])
            all_next = branch_next[:BOOT_MAX_BRANCH_NEXT] + other_next[:BOOT_MAX_OTHER_NEXT]
            all_next = all_next[:BOOT_MAX_NEXT]
            for item in all_next:
                lines.append(f"  Next: {item['display']}")
            remaining = len(filtered_pending) - len(all_next)
            if remaining > 0:
                lines.append(f"  ({remaining} more Next items in history. Use git-memory-log --type context)")

    # Blockers
    if memory.get("blockers"):
        for item in memory["blockers"]:
            lines.append(f"  Blocker: {item}")

    if not memory.get("last_context") and not memory.get("pending") and not memory.get("blockers"):
        lines.append("  (no prior session found)")

    lines.append("")
    return lines


def render_remember_section(
    memory: dict, glossary: dict, tombstones: set[str],
) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Render the REMEMBER section.

    Returns (lines, all_remembers) — all_remembers is reused by the GC
    WARNINGS section below.
    """
    lines: list[str] = []

    all_remembers: list[tuple[str, str, bool]] = list(memory.get("remembers", []))
    recent_remember_texts = {normalize(t) for _, t, _ in all_remembers}
    for gscope, gtext, gis_crown in glossary.get("remembers", []):
        norm = normalize(gtext)
        if norm not in recent_remember_texts and norm not in tombstones:
            all_remembers.append((gscope, gtext, gis_crown))
            recent_remember_texts.add(norm)

    if all_remembers:
        # SEC-MED-005: crowned entries intentionally bypass the normal
        # count-eviction budget — cap the TOTAL shown at CROWN_COUNT_CAP and
        # bound each value's length so a single crowned commit can't blow up
        # the boot log without limit.
        crowned_remembers = [(s, t, c) for s, t, c in all_remembers if c][:CROWN_COUNT_CAP]
        normal_remembers = [(s, t, c) for s, t, c in all_remembers if not c]

        lines.append("REMEMBER:")
        for scope, text, _ in crowned_remembers:
            lines.append(f"  👑 {scope} {_truncate_crown_value(text)}")
        for scope, text, _ in normal_remembers[:BOOT_MAX_REMEMBERS]:
            lines.append(f"  {scope} {text}")
        remaining = len(normal_remembers) - BOOT_MAX_REMEMBERS
        if remaining > 0:
            lines.append(f"  ({remaining} more. Use git-memory-log --type remember)")
        lines.append("")

    return lines, all_remembers


def render_decisions_section(
    memory: dict, glossary: dict, branch_keywords: list[str],
) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Render the DECISIONS section.

    Returns (lines, all_decisions) — all_decisions is reused by the TIMELINE
    section's crowned-scope suppression.
    """
    lines: list[str] = []

    all_decisions: list[tuple[str, str, bool]] = list(memory.get("decisions", []))
    recent_decision_scopes = {s for s, _, _ in all_decisions}

    # Glossary merge: crowned glossary entry beats non-crowned recent at same scope
    for gscope, gtext, gis_crown in glossary.get("decisions", []):
        if gscope not in recent_decision_scopes:
            all_decisions.append((gscope, gtext, gis_crown))
            recent_decision_scopes.add(gscope)
        elif gis_crown:
            # Replace non-crowned recent entry with crowned glossary entry
            _crown_replace(all_decisions, gscope, gtext)

    if all_decisions:
        # SEC-MED-005: cap total crowned count + per-value length (see REMEMBER above)
        crowned_decs = [(s, t, c) for s, t, c in all_decisions if c][:CROWN_COUNT_CAP]
        normal_decs = [(s, t, c) for s, t, c in all_decisions if not c]

        branch_decs, other_decs = partition_by_relevance(
            normal_decs, branch_keywords, lambda x: f"{x[0]} {x[1]}")
        shown_normal = branch_decs[:BOOT_MAX_BRANCH_DECISIONS] + other_decs[:BOOT_MAX_OTHER_DECISIONS]
        shown_normal = shown_normal[:BOOT_MAX_DECISIONS]

        lines.append("DECISIONS:")
        # Crowned first, outside budget
        for scope, text, _ in crowned_decs:
            lines.append(f"  👑 {scope} {_truncate_crown_value(text)}")
        # Then normal entries with their budget
        for scope, text, _ in shown_normal:
            lines.append(f"  {scope} {text}")
        remaining = len(normal_decs) - len(shown_normal)
        if remaining > 0:
            lines.append(f"  ({remaining} more decisions in history. Use git-memory-log --type decision)")
        lines.append("")

    return lines, all_decisions


def render_memos_section(
    memory: dict, glossary: dict, tombstones: set[str], branch_keywords: list[str],
) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Render the MEMOS section.

    Returns (lines, all_memos) — all_memos is reused by the GC WARNINGS section.
    """
    lines: list[str] = []

    all_memos: list[tuple[str, str, bool]] = list(memory.get("memos", []))
    recent_memo_scopes = {s for s, _, _ in all_memos}
    for gscope, gtext, gis_crown in glossary.get("memos", []):
        if gscope not in recent_memo_scopes and normalize(gtext) not in tombstones:
            all_memos.append((gscope, gtext, gis_crown))
            recent_memo_scopes.add(gscope)
        elif gis_crown:
            # CRB-01: a retired crowned Memo must not resurrect and evict a
            # newer, active, never-retired entry for the same scope.
            _crown_replace(all_memos, gscope, gtext, tombstones)

    if all_memos:
        # SEC-MED-005: cap total crowned count + per-value length (see REMEMBER above)
        crowned_memos = [(s, t, c) for s, t, c in all_memos if c][:CROWN_COUNT_CAP]
        normal_memos = [(s, t, c) for s, t, c in all_memos if not c]

        branch_memos, other_memos = partition_by_relevance(
            normal_memos, branch_keywords, lambda x: f"{x[0]} {x[1]}")
        shown_normal = branch_memos[:BOOT_MAX_BRANCH_MEMOS] + other_memos[:BOOT_MAX_OTHER_MEMOS]
        shown_normal = shown_normal[:BOOT_MAX_MEMOS]

        lines.append("MEMOS:")
        for scope, text, _ in crowned_memos:
            lines.append(f"  👑 {scope} {_truncate_crown_value(text)}")
        for scope, text, _ in shown_normal:
            lines.append(f"  {scope} {text}")
        remaining = len(normal_memos) - len(shown_normal)
        if remaining > 0:
            lines.append(f"  ({remaining} more memos in history. Use git-memory-log --type memo)")
        lines.append("")

    return lines, all_memos


def render_gc_section(
    all_memos: list[tuple[str, str, bool]], all_remembers: list[tuple[str, str, bool]],
) -> list[str]:
    """Render the GC WARNINGS section (memo/remember accumulation thresholds)."""
    lines: list[str] = []
    gc_warnings: list[str] = []

    memo_count = len(all_memos)
    if memo_count > MEMO_GC_THRESHOLD:
        gc_warnings.append(
            f"  ⚠️ Memory accumulation: {memo_count} memos detected (threshold: {MEMO_GC_THRESHOLD}). "
            "Consider invoking Gitto's Mode C (Consolidator) to clean this up."
        )

    remember_user_count = sum(1 for label, _, _ in all_remembers if "(user)" in label)
    if remember_user_count > REMEMBER_GC_THRESHOLD:
        gc_warnings.append(
            f"  ⚠️ Memory accumulation: {remember_user_count} remember(user) detected "
            f"(threshold: {REMEMBER_GC_THRESHOLD}). "
            "Consider invoking Gitto's Mode C (Consolidator) to clean this up."
        )

    remember_claude_count = sum(1 for label, _, _ in all_remembers if "(claude)" in label)
    if remember_claude_count > REMEMBER_GC_THRESHOLD:
        gc_warnings.append(
            f"  ⚠️ Memory accumulation: {remember_claude_count} remember(claude) detected "
            f"(threshold: {REMEMBER_GC_THRESHOLD}). "
            "Consider invoking Gitto's Mode C (Consolidator) to clean this up."
        )

    if gc_warnings:
        lines.append("GC:")
        lines.extend(gc_warnings)
        lines.append("")

    return lines


def render_consolidation_section() -> list[str]:
    """Render the CONSOLIDATE trigger section."""
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


def render_timeline_section(all_decisions: list[tuple[str, str, bool]]) -> list[str]:
    """Render the TIMELINE section (suppressing commits whose scope has a crowned decision)."""
    lines: list[str] = []

    # Suppress commits whose scope has a crowned decision — the crowned entry
    # is the canonical record; the non-crowned commit is historical noise.
    crowned_scopes: set[str] = {
        label[1:-1] for label, _, is_c in all_decisions if is_c and label != "(global)"
    }
    timeline = get_timeline(BOOT_MAX_TIMELINE, suppress_scopes=crowned_scopes or None)
    if timeline:
        lines.append(f"TIMELINE (last {len(timeline)}):")
        lines.extend(timeline)
        lines.append("")

    return lines


def render_boot_complete_section(plugin_root: str) -> tuple[list[str], str, str]:
    """Render the BOOT COMPLETE footer.

    Returns (lines, commit_script, log_script) — the two script paths are
    also needed later for the short banner.
    """
    commit_script = os.path.join(plugin_root, "bin", "git-memory-commit.py").replace(os.sep, "/")
    log_script = os.path.join(plugin_root, "bin", "git-memory-log.py").replace(os.sep, "/")
    lines = [
        "---",
        "BOOT COMPLETE. Do NOT run doctor or git-memory-log. All context is above.",
        f'Commit: python3 "{commit_script}"',
        f'Log: python3 "{log_script}"',
    ]
    return lines, commit_script, log_script


def write_boot_log(full_text: str, project_root: str | None) -> str | None:
    """Write the full, untruncated boot briefing to .claude/.unmassk/boot-log-latest.txt.

    Returns the path only after a successful write — boot_log_path must
    never be treated as "available" just because a path was computed for it.
    Otherwise, on write failure (permissions, disk full), the caller would
    still take the short-banner branch and point Claude at a file that was
    never written, silently losing the Next: content — exactly the bug this
    fix exists to prevent (Cerberus regression: TestBootLogWriteFailureFallback).
    """
    if not project_root:
        return None
    try:
        if ensure_runtime_dir is not None:
            runtime_dir = ensure_runtime_dir(project_root)
        else:
            runtime_dir = os.path.join(project_root, *BOOT_LOG_REL_PARTS[:-1])
            os.makedirs(runtime_dir, exist_ok=True)
        candidate_log_path = os.path.join(runtime_dir, BOOT_LOG_REL_PARTS[-1])
        with open_no_follow_symlink(candidate_log_path, "w") as f:
            f.write(full_text + "\n")
        try:
            os.chmod(candidate_log_path, 0o600)
        except OSError:
            pass
        return candidate_log_path  # only mark available after a successful write
    except OSError:
        return None  # Boot must never fail because the log file couldn't be written


def render_boot_banner_lines(
    plugin_root: str, status: str, status_detail: str, branch: str, ahead_behind: str,
    boot_log_path: str, commit_script: str, log_script: str,
) -> list[str]:
    """Build the short banner lines printed to stdout when the boot log write succeeded.

    Unconditional: stdout is always this short banner, for any repo size —
    see House's diagnosis and TestBootStdoutMinimalWithHeavyContent /
    TestBootLogFileFullContent for why there is no byte-threshold here.
    """
    banner_log_path = boot_log_path.replace(os.sep, "/")
    banner_branch = _truncate_banner_field(branch)
    return [
        f"[git-memory-boot] v{PLUGIN_VERSION} | {plugin_root}",
        "",
        f"STATUS: {status}{status_detail}",
        f"BRANCH: {banner_branch}{ahead_behind}",
        "",
        "The full briefing (nothing shortened) was written to:",
        f"  {banner_log_path}",
        "Read that file now before doing anything else — it has everything "
        "the inline briefing normally has.",
        "",
        "---",
        "BOOT COMPLETE. Do NOT run doctor or git-memory-log.",
        f'Commit: python3 "{commit_script}"',
        f'Log: python3 "{log_script}"',
    ]


def run_preboot_migrations(project_root: str | None) -> None:
    """Run all one-shot pre-boot migrations plus the best-effort background fetch.

    Order matters: session-booted flag cleanup, then the two project-root
    migrations, then the global statusLine migration (runs even without a
    project root — it's a user-level config, not project-level), then the
    non-critical remote fetch.
    """
    # 0. Clean session-booted flag (new session = fresh boot)
    if project_root:
        booted_flag = os.path.join(project_root, ".claude", ".unmassk", ".session-booted")
        try:
            os.remove(booted_flag)
        except FileNotFoundError:
            pass

    # 0a. Migrate: move runtime files from .claude/ root to .claude/.unmassk/ (v3.7→v3.8)
    if project_root:
        _migrate_runtime_to_unmassk(project_root)
        _migrate_untrack_generated_jsons(project_root)

    # 0b-global. Migrate: fix stale context-writer statusLine in global settings.json
    _migrate_stale_context_writer_statusline()

    # 0c. Fetch remote refs silently (CRB-09: short dedicated timeout — this
    # is a non-critical background refresh, it must not hold up session start).
    run_git(["fetch", "--quiet"], timeout=BOOT_FETCH_TIMEOUT)


def main() -> None:
    """Auto-boot: structured briefing with all context pre-extracted.

    Pure orchestrator (CRB-02): each `── X ──` section of the briefing is
    rendered by its own render_*_section() function; main() just runs the
    pre-boot migrations, calls each renderer in order, concatenates the
    lines, and decides banner vs full-text-on-stdout for the write.
    """
    # Check if we're in a git repo
    code, _ = run_git(["rev-parse", "--is-inside-work-tree"])
    if code != 0:
        sys.exit(0)

    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__))).replace(os.sep, "/")
    project_root = _get_project_root()
    run_preboot_migrations(project_root)

    lines: list[str] = []
    lines.extend(render_header_section(plugin_root))

    status_lines, status, status_detail = render_status_section()
    lines.extend(status_lines)

    branch_lines, branch, branch_keywords, branch_issue, ahead_behind, behind_n = render_branch_section()
    lines.extend(branch_lines)

    lines.extend(render_scopes_section(project_root))

    memory = extract_memory()
    lines.extend(render_resume_section(memory, branch_issue, branch_keywords))

    # Merge recent + glossary remembers
    glossary = extract_glossary_cached()
    # Union: tombstones from recent window + tombstones from the full glossary range
    tombstones = memory.get("tombstones", set()) | glossary.get("tombstones", set())

    remember_lines, all_remembers = render_remember_section(memory, glossary, tombstones)
    lines.extend(remember_lines)

    decisions_lines, all_decisions = render_decisions_section(memory, glossary, branch_keywords)
    lines.extend(decisions_lines)

    memos_lines, all_memos = render_memos_section(memory, glossary, tombstones, branch_keywords)
    lines.extend(memos_lines)

    lines.extend(render_gc_section(all_memos, all_remembers))
    lines.extend(render_consolidation_section())
    lines.extend(render_timeline_section(all_decisions))

    boot_complete_lines, commit_script, log_script = render_boot_complete_section(plugin_root)
    lines.extend(boot_complete_lines)

    # DO NOT create .session-booted flag here — let the UserPromptSubmit hook
    # detect the first message and force skill loading. The flag is created
    # by user-prompt-memory-check.py AFTER it tells Claude to load skills.

    full_text = "\n".join(lines)

    # Always refresh the full, untruncated boot log file (nothing capped —
    # this is the file Claude is told to read when stdout switches to the
    # minimal banner below).
    boot_log_path = write_boot_log(full_text, project_root)

    if not boot_log_path:
        # Safety fallback: the boot log file could not be written (permissions,
        # disk full, etc). Printing the short banner would point Claude at a
        # file that was never written, silently losing the Next: content —
        # exactly the bug this fix exists to prevent. Print everything inline
        # instead, even though it risks the harness's stdout preview truncation.
        print(full_text)
    else:
        banner = render_boot_banner_lines(
            plugin_root, status, status_detail, branch, ahead_behind,
            boot_log_path, commit_script, log_script,
        )
        print("\n".join(banner))

    sys.exit(0)


if __name__ == "__main__":
    main()
