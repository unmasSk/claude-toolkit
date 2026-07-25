"""
Boot briefing section renderers for session-start-boot.py (CRB T2-1 split;
second I/O extraction per Cerberus round 4, third per Cerberus round 5 —
see lib/boot_checks.py).

Owns the `render_*_section()` functions that remain PURE "given inputs,
produce these briefing lines" formatting — plus their pure helpers
(relevance scoring/partitioning, crowned-value truncation). All
subprocess/filesystem/network I/O — including get_timeline(),
get_last_context_time(), render_branch_section(), render_scopes_section(),
and render_consolidation_section(), which round 5 moved out because they
call run_git()/open()/os.listdir() directly — now lives in
lib/boot_checks.py, alongside skill-drift + version checks and the
doctor/repair runners moved there in round 4. This module re-imports all of
it by name so render_status_section()/render_resume_section()/
render_timeline_section() call it unchanged, so hooks/session-start-boot.py's
`from boot_render import (render_branch_section, render_consolidation_section,
render_scopes_section, ...)` keeps resolving without any change there, and so
a direct `import boot_render; boot_render.check_version_mismatch()` /
`boot_render.get_timeline()` call (the latter used by
tests/test_migrate_statusline.py) keeps resolving.

Moved out of hooks/session-start-boot.py verbatim (Cerberus T2-1): the hook
file had grown to 1110 lines, well past the project's 500-line limit, and
these renderers are cohesive as a unit — pure "given inputs, produce these
briefing lines" functions — distinct from main()'s orchestration,
write_boot_log()'s file I/O, render_boot_banner_lines()'s short-banner
formatting, and run_preboot_migrations()'s one-shot migration concerns, which
all stay in the hook file. lib/boot_checks.py then took over the I/O-heavy
functions that had crept back in here (Cerberus round-4: 875 lines, past the
500-line limit again, mixing pure rendering with real subprocess/filesystem
work) — and, this round, the remaining ones Cerberus found still doing real
I/O (round-5: back to 661 lines). parse_branch_keywords() and time_ago(),
though pure, moved to lib/boot_checks.py together with their only callers
(render_branch_section(), get_timeline(), get_last_context_time()) rather
than staying here — boot_checks.py must never import FROM boot_render.py
(confirmed unidirectional DAG: boot_memory <- boot_checks <- boot_render),
so leaving them behind would have forced exactly that reverse import.

Pure refactor: behavior is byte-for-byte identical to before any of the
three splits. See lib/boot_memory.py's own module docstring and
tests/test_migrate_statusline.py for why `parsing` AND `git_helpers` imports
below are deferred into function bodies rather than hoisted to module level
— this module is a real, stably-named module (first `import boot_render`
anywhere in a process caches it for that process), and a module-level `from
git_helpers import X` (or `from parsing import X`) could freeze X to a
test's temporary stub forever if this module's first-ever import happened to
land inside that stub's window.
"""

import os
import time

from version import VERSION as PLUGIN_VERSION

from boot_memory import MAX_DECISIONS, _crown_replace
from boot_checks import (
    check_issue_status,
    check_skill_drift,
    check_version_mismatch,
    get_last_context_time,
    get_timeline,
    render_branch_section,
    render_branches_section,
    render_consolidation_section,
    render_scopes_section,
    run_doctor,
    run_repair,
    _issue_matches_next,
)


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
BOOT_MAX_TIMELINE = 20

# CRB-06: named GC-warning thresholds (previously inline magic numbers).
MEMO_GC_THRESHOLD = 10
REMEMBER_GC_THRESHOLD = 16

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


def score_branch_relevance(text: str, keywords: list[str]) -> int:
    """Score how relevant a text is to branch keywords. Higher = more relevant."""
    if not keywords:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw in text_lower)


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


def _render_crowned_capped_section(
    header: str,
    all_items: list[tuple[str, str, bool]],
    log_type: str,
    *,
    branch_keywords: list[str] | None = None,
    branch_cap: int = 0,
    other_cap: int = 0,
    total_cap: int = 0,
    more_label: str = "",
) -> list[str]:
    """Shared REMEMBER/DECISIONS/MEMOS render body (Cerberus round 5: the
    three callers had near-identical partition + cap + format logic,
    duplicated 3x).

    Callers own their own glossary-merge step first (that part differs
    meaningfully per section — Remembers dedup by normalized TEXT with no
    scope-uniqueness or crown-replace; Decisions/Memos dedup by SCOPE with
    crown-replace semantics, and Memos additionally checks tombstones — see
    SEC-MED-005/CRB-01), then pass the merged list here for the identical
    part: crowned/normal split (SEC-MED-005's count-eviction-bypass cap),
    optional branch-relevance partitioning, and the "(N more ...)" trailer.

    branch_keywords=None means "no branch partitioning" (REMEMBER's case —
    just a flat total_cap slice); otherwise normal entries are partitioned
    branch-scoped/other first, each capped, then re-capped to total_cap
    (DECISIONS/MEMOS's case).
    """
    lines: list[str] = []
    if not all_items:
        return lines

    # SEC-MED-005: crowned entries intentionally bypass the normal
    # count-eviction budget — cap the TOTAL shown at CROWN_COUNT_CAP and
    # bound each value's length so a single crowned commit can't blow up
    # the boot log without limit.
    crowned = [(s, t, c) for s, t, c in all_items if c][:CROWN_COUNT_CAP]
    normal = [(s, t, c) for s, t, c in all_items if not c]

    if branch_keywords is not None:
        branch_items, other_items = partition_by_relevance(
            normal, branch_keywords, lambda x: f"{x[0]} {x[1]}")
        shown_normal = branch_items[:branch_cap] + other_items[:other_cap]
        shown_normal = shown_normal[:total_cap]
    else:
        shown_normal = normal[:total_cap]

    lines.append(header)
    for scope, text, _ in crowned:
        lines.append(f"  👑 {scope} {_truncate_crown_value(text)}")
    for scope, text, _ in shown_normal:
        lines.append(f"  {scope} {text}")
    remaining = len(normal) - len(shown_normal)
    if remaining > 0:
        label = f" {more_label}" if more_label else ""
        lines.append(f"  ({remaining} more{label}. Use git-memory-log --type {log_type})")
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

    all_remembers: list[tuple[str, str, bool]] = list(memory.get("remembers", []))
    recent_remember_texts = {normalize(t) for _, t, _ in all_remembers}
    for gscope, gtext, gis_crown in glossary.get("remembers", []):
        norm = normalize(gtext)
        if norm not in recent_remember_texts and norm not in tombstones:
            all_remembers.append((gscope, gtext, gis_crown))
            recent_remember_texts.add(norm)

    lines = _render_crowned_capped_section(
        "REMEMBER:", all_remembers, "remember", total_cap=BOOT_MAX_REMEMBERS)

    return lines, all_remembers


def render_decisions_section(
    memory: dict, glossary: dict, branch_keywords: list[str],
) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Render the DECISIONS section.

    Returns (lines, all_decisions) — all_decisions is reused by the TIMELINE
    section's crowned-scope suppression.
    """
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

    lines = _render_crowned_capped_section(
        "DECISIONS:", all_decisions, "decision",
        branch_keywords=branch_keywords,
        branch_cap=BOOT_MAX_BRANCH_DECISIONS, other_cap=BOOT_MAX_OTHER_DECISIONS,
        total_cap=BOOT_MAX_DECISIONS, more_label="decisions in history")

    return lines, all_decisions


def render_memos_section(
    memory: dict, glossary: dict, tombstones: set[str], branch_keywords: list[str],
) -> tuple[list[str], list[tuple[str, str, bool]]]:
    """Render the MEMOS section.

    Returns (lines, all_memos) — all_memos is reused by the GC WARNINGS section.
    """
    from parsing import normalize

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

    lines = _render_crowned_capped_section(
        "MEMOS:", all_memos, "memo",
        branch_keywords=branch_keywords,
        branch_cap=BOOT_MAX_BRANCH_MEMOS, other_cap=BOOT_MAX_OTHER_MEMOS,
        total_cap=BOOT_MAX_MEMOS, more_label="memos in history")

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


def render_timeline_section(
    all_decisions: list[tuple[str, str, bool]],
    exclude_remote: str | None = None,
) -> list[str]:
    """Render the TIMELINE section (suppressing commits whose scope has a crowned decision).

    exclude_remote: forwarded to get_timeline() unchanged — see its own
    docstring (lib/boot_git_checks.py). The caller passes the same
    `unrelated_remote_name` already computed once for
    extract_glossary_cached(), so a confirmed-unrelated upstream's refs
    never leak into the (now `--all`-scanning) TIMELINE either.
    """
    lines: list[str] = []

    # Suppress commits whose scope has a crowned decision — the crowned entry
    # is the canonical record; the non-crowned commit is historical noise.
    crowned_scopes: set[str] = {
        label[1:-1] for label, _, is_c in all_decisions if is_c and label != "(global)"
    }
    timeline = get_timeline(
        BOOT_MAX_TIMELINE, suppress_scopes=crowned_scopes or None, exclude_remote=exclude_remote,
    )
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
