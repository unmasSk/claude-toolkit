"""
Boot briefing section renderers for session-start-boot.py (CRB T2-1 split;
second I/O extraction per Cerberus round 4, third per Cerberus round 5 —
see lib/boot_checks.py).

Owns the `render_*_section()` functions that remain PURE "given inputs,
produce these briefing lines" formatting for the non-memory parts of the
boot briefing: HEADER, STATUS, and the BOOT COMPLETE footer. All
subprocess/filesystem/network I/O lives in lib/boot_checks.py, alongside
skill-drift + version checks and the doctor/repair runners.

Memory v2 cleanup (docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3): the RESUME,
DECISIONS, MEMOS, REMEMBER, GC and TIMELINE section renderers, and their
crown-related helpers (_render_crowned_capped_section, _truncate_crown_value,
partition_by_relevance, score_branch_relevance, the BOOT_MAX_*/CROWN_*/
*_GC_THRESHOLD constants), were removed with the rest of the v1 memory
system — they only ever rendered memory (decisions/memos/remembers/next)
that no longer exists in this module's data flow.

Moved out of hooks/session-start-boot.py verbatim (Cerberus T2-1): the hook
file had grown to 1110 lines, well past the project's 500-line limit, and
these renderers are cohesive as a unit — pure "given inputs, produce these
briefing lines" functions — distinct from main()'s orchestration,
write_boot_log()'s file I/O, render_boot_banner_lines()'s short-banner
formatting, and run_preboot_migrations()'s one-shot migration concerns, which
all stay in the hook file.

Pure refactor otherwise: behavior is byte-for-byte identical to before the
splits, for the sections that survive.
"""

import os

from version import VERSION as PLUGIN_VERSION

import cache_sync_check
from boot_checks import (
    check_skill_drift,
    check_version_mismatch,
    run_doctor,
    run_repair,
)


def render_header_section(plugin_root: str) -> list[str]:
    """Render the HEADER section (plugin version + root path)."""
    return [f"[git-memory-boot] v{PLUGIN_VERSION} | {plugin_root}", ""]


def _render_plugin_sync_line(project_root: str | None) -> str:
    """Render the always-present PLUGIN: line — repo-vs-installed-cache file
    count.

    Deliberately louder than lib/cache_sync_check.py's own "stay silent
    when it doesn't apply" convention (see that module's docstring): the
    doctor only speaks when it has a warning to add, and a warn-level
    doctor finding does not even flip STATUS above "ok" in
    render_status_section() -- which is exactly how a stale plugin cache
    went unnoticed for 3 days (see this project's git-memory). This line
    always renders, with one of three outcomes: a real count of drifted
    files, an explicit zero, or an explicit "not verifiable" — never
    silence, and never "ok" when the answer is actually "unknown". Any
    exception from the comparator is swallowed (fail-open — boot must
    never break over this) but still named, never hidden.
    """
    if not project_root:
        return "PLUGIN: no verificable (project root no disponible)"
    try:
        summary = cache_sync_check.count_repo_cache_drift(project_root)
    except Exception as e:
        return f"PLUGIN: no verificable ({type(e).__name__})"
    if summary is None:
        return "PLUGIN: no verificable (sin repo fuente junto a la cache)"
    count, _descriptions = summary
    if count == 0:
        return "PLUGIN: sincronizado (0 ficheros)"
    return (
        f"PLUGIN: {count} ficheros desincronizados (repo vs cache) "
        "-> publica version y ejecuta 'claude plugin update'"
    )


def render_status_section(project_root: str | None = None) -> tuple[list[str], str, str]:
    """Run doctor/repair, check version + skill drift, render the STATUS section.

    Args:
        project_root: Git root of the current project, used only for the
            PLUGIN: line's repo-vs-cache file comparison. None renders that
            line as "not verifiable" rather than skipping it — see
            _render_plugin_sync_line().

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
    lines.append(_render_plugin_sync_line(project_root))
    lines.append("")
    return lines, status, status_detail


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
