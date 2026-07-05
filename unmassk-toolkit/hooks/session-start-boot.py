#!/usr/bin/env python3
"""
session-start-boot -- Auto-boot hook for SessionStart.

Runs automatically when Claude starts a new session. Executes doctor
silently, extracts memory from recent commits, and prints a compact
summary that Claude receives as context.

Exit codes:
  0: Always (never blocks session start)
"""

import os
import sys

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
    # module that predates this helper.
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback (was a byte-identical local copy of
    # the same O_NOFOLLOW logic as lib/boot_memory.py's fallback) — see
    # lib/_symlink_safe_open.py for the single implementation both share.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink
from version import VERSION as PLUGIN_VERSION

# CRB-04: memory extraction (extract_memory/extract_glossary/crown logic/
# glossary cache) and one-shot migrations live in dedicated lib/ modules —
# see lib/boot_memory.py and lib/boot_migrations.py. Re-exported here by
# name so `python3 session-start-boot.py` behaves identically and so tests
# that load this module directly (e.g. tests/test_crown.py calling
# boot.extract_memory()) keep working unchanged.
from boot_memory import (
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

# CRB T2-1: every render_*_section() function (plus its small helpers —
# skill drift/version checks, branch keyword parsing, time formatting,
# GitHub issue matching, timeline extraction, relevance partitioning) lives
# in lib/boot_render.py now. This file had grown to 1110 lines, well past
# the project's 500-line limit; the renderers are pure "inputs → briefing
# lines" functions, cohesive as their own unit and separable from this
# file's orchestration (main()), file I/O (write_boot_log()), short-banner
# formatting (render_boot_banner_lines()), and one-shot migrations
# (run_preboot_migrations()). Re-exported here by name — `python3
# session-start-boot.py` behaves identically, and main() calls these
# exactly as it did before the split.
from boot_render import (
    render_boot_complete_section,
    render_branch_section,
    render_consolidation_section,
    render_decisions_section,
    render_gc_section,
    render_header_section,
    render_memos_section,
    render_remember_section,
    render_resume_section,
    render_scopes_section,
    render_status_section,
    render_timeline_section,
)


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


# CRB-09: the background `git fetch` is best-effort and non-critical — it
# must not hold up session start for as long as a real git operation might
# (GIT_TIMEOUT default is 10s). A short, dedicated timeout bounds the worst
# case without touching the shared default used by everything else.
BOOT_FETCH_TIMEOUT = 5

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
            # Fallback path when ensure_runtime_dir couldn't be imported
            # (stub or stale git_helpers.py without it). ensure_runtime_dir
            # itself calls verify_path_within_project() internally, so this
            # fallback needs the same guard explicitly, or it silently loses
            # the "parent-directory symlink" protection the normal path gets.
            # Deferred import (not module-level) for the same reason as the
            # other verify_path_within_project import in this file — a test
            # stubs git_helpers without this name during its import window.
            from git_helpers import verify_path_within_project
            runtime_dir = os.path.join(project_root, *BOOT_LOG_REL_PARTS[:-1])
            verify_path_within_project(runtime_dir, project_root)
            os.makedirs(runtime_dir, exist_ok=True)
        candidate_log_path = os.path.join(runtime_dir, BOOT_LOG_REL_PARTS[-1])
        with open_no_follow_symlink(candidate_log_path, "w") as f:
            f.write(full_text + "\n")
        try:
            os.chmod(candidate_log_path, 0o600)
        except OSError:
            pass
        return candidate_log_path  # only mark available after a successful write
    except OSError as e:
        # CRB T2-2: this is the single most important failure path in the
        # file (it's what triggers the inline-fallback branch in main()) —
        # leave a one-line breadcrumb instead of failing completely silently.
        print(f"[session-start-boot] BOOT-WARNING: {type(e).__name__} writing boot log", file=sys.stderr)
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
        # SEC-HIGH-007: .claude may be a symlink to an external directory
        # containing a real .session-booted file — os.remove() resolves
        # symlinked PARENT components (unlike a symlinked final component,
        # which os.remove()'s own unlink-not-follow-target semantics would
        # already refuse to traverse). Deferred import (not module top
        # level): tests/test_migrate_statusline.py stubs git_helpers only
        # during THIS module's own load, never while run_preboot_migrations()
        # is actually called, so importing here avoids ImportError against
        # that stub. This function runs with no wrapping try/except on every
        # SessionStart, so UnsafePathError is caught right here — fail
        # closed (skip the cleanup) without ever crashing the boot.
        from git_helpers import verify_path_within_project, UnsafePathError
        try:
            verify_path_within_project(booted_flag, project_root)
        except UnsafePathError:
            pass  # escapes project_root — never touch it
        else:
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

    branch_lines, branch, branch_keywords, branch_issue, ahead_behind = render_branch_section()
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
