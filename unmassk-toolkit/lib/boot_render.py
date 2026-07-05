"""
Boot briefing section renderers for session-start-boot.py (CRB T2-1 split;
second split per Cerberus round 4 — see lib/boot_checks.py).

Owns every `render_*_section()` function plus their PURE formatting helpers
(branch keyword parsing, time-ago formatting, relevance scoring/partitioning,
timeline/last-context extraction). All subprocess/filesystem/network I/O
that used to live here (skill-drift + version checks, doctor/repair runners,
GitHub issue-status checks) has been extracted to lib/boot_checks.py — this
module re-imports those by name so render_status_section() and
render_resume_section() call them unchanged, and so a direct `import
boot_render; boot_render.check_version_mismatch()` (used by
tests/test_security_regression.py) keeps resolving.

Moved out of hooks/session-start-boot.py verbatim (Cerberus T2-1): the hook
file had grown to 1110 lines, well past the project's 500-line limit, and
these renderers are cohesive as a unit — pure "given inputs, produce these
briefing lines" functions — distinct from main()'s orchestration,
write_boot_log()'s file I/O, render_boot_banner_lines()'s short-banner
formatting, and run_preboot_migrations()'s one-shot migration concerns, which
all stay in the hook file. lib/boot_checks.py later took over the I/O-heavy
functions that had crept back in here (Cerberus round-4: 875 lines, past the
500-line limit again, mixing pure rendering with real subprocess/filesystem
work).

Pure refactor: behavior is byte-for-byte identical to before either split.
See lib/boot_memory.py's own module docstring and
tests/test_migrate_statusline.py for why `parsing` AND `git_helpers` imports
below are deferred into function bodies rather than hoisted to module level
— this module is a real, stably-named module (first `import boot_render`
anywhere in a process caches it for that process), and a module-level `from
git_helpers import X` (or `from parsing import X`) could freeze X to a
test's temporary stub forever if this module's first-ever import happened to
land inside that stub's window.
"""

import json
import os
import re
import time
from datetime import datetime, timezone

from version import VERSION as PLUGIN_VERSION

from boot_memory import MAX_DECISIONS, _crown_replace, _sanitize_trailer_value
from boot_checks import (
    check_issue_status,
    check_skill_drift,
    check_version_mismatch,
    run_doctor,
    run_repair,
    _issue_matches_next,
)


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


def score_branch_relevance(text: str, keywords: list[str]) -> int:
    """Score how relevant a text is to branch keywords. Higher = more relevant."""
    if not keywords:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


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
    from parsing import normalize

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
    from parsing import normalize

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
