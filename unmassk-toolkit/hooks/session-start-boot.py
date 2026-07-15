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
from encoding_guard import force_utf8_streams
force_utf8_streams()

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

# CRB-04: memory extraction (extract_memory/extract_glossary/crown logic)
# and one-shot migrations live in dedicated lib/ modules — see
# lib/boot_memory.py and lib/boot_migrations.py. Re-exported here by name so
# `python3 session-start-boot.py` behaves identically and so tests that load
# this module directly (e.g. tests/test_crown.py calling boot.extract_memory())
# keep working unchanged.
from boot_memory import (
    _sanitize_trailer_value,
    extract_glossary,
    extract_memory,
    resolve_boot_memory,
)
# Glossary cache I/O (further split of boot_memory.py, see
# lib/boot_glossary_cache.py) — _get_project_root/extract_glossary_cached
# now live there.
from boot_glossary_cache import (
    _get_project_root,
    extract_glossary_cached,
)
from boot_migrations import _migrate_stale_context_writer_statusline
# Issue #63 (boot simplification, point 2): the per-message auto-upgrade
# check that used to live in hooks/user-prompt-memory-check.py now runs
# once per SessionStart instead — see lib/upgrade_check.py's module
# docstring for the full rationale and the accepted mid-session-update loss.
from upgrade_check import trigger_auto_upgrade_if_needed

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
    render_branches_section,
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
# Boot memory freshness (multi-machine, issue #49, plan Task 2/3) — hardened,
# gated, rate-limited fetch + the MEMORY: freshness stamp. boot_git_checks
# is already transitively loaded via boot_render <- boot_checks <-
# boot_git_checks, so a plain module-level import here is safe (not on
# tests/test_migrate_statusline.py's stub list, unlike git_helpers/parsing/
# version).
from boot_git_checks import check_upstream_shares_history, fetch_memory_ref, render_memoria_stamp


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


# CRB-09 / issue #49: the background `git fetch` is best-effort and
# non-critical — it must not hold up session start for as long as a real
# git operation might. Its own bounded timeout (FETCH_TIMEOUT_SECONDS) now
# lives in lib/boot_git_checks.py alongside fetch_memory_ref(), which also
# owns the gate + rate-limit that replaced the old unconditional fetch.

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
        # reject_hardlinks=True (issue #53, decision 51a3c44): this path is
        # a toolkit-generated-only file (never a legitimate user file, so a
        # hard link planted here can only be an attack, not a worktree-
        # sharing setup) — safe to close the F6 residual for this call site.
        # errors="backslashreplace" (issue #54, T3): full_text assembles
        # git-derived memory content (commit trailers, subjects, bodies —
        # see run_git()'s docstring for how a malformed source could yield
        # a lone surrogate). A clean, always-strict-UTF-8-re-readable escape
        # keeps this write-path's "only OSError escapes" contract even in
        # that case, matching the existing sanitize-for-display discipline
        # this codebase already applies to trailer text (parsing.py's
        # sanitize_trailer_value()) rather than preserving raw bytes.
        with open_no_follow_symlink(
            candidate_log_path, "w", reject_hardlinks=True, errors="backslashreplace"
        ) as f:
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
    memoria_stamp: str, pull_directive_lines: list[str] | None = None,
) -> list[str]:
    """Build the short banner lines printed to stdout when the boot log write succeeded.

    Unconditional: stdout is always this short banner, for any repo size —
    see House's diagnosis and TestBootStdoutMinimalWithHeavyContent /
    TestBootLogFileFullContent for why there is no byte-threshold here.

    `memoria_stamp` and `pull_directive_lines` (issue #49, plan Task 3) are
    the two exceptions to "banner is short, boot-log has everything" — both
    are short enough by design to fit the banner AND the full boot-log
    content, and provenance/behind-signal is important enough to surface
    even when Claude never opens the boot-log file.
    """
    banner_log_path = boot_log_path.replace(os.sep, "/")
    banner_branch = _truncate_banner_field(branch)
    lines = [
        f"[git-memory-boot] v{PLUGIN_VERSION} | {plugin_root}",
        "",
    ]
    # Cerberus (nitpick): an empty memoria_stamp means main() already
    # applied the "skipped_gate" gate (no toolkit memory installed) — omit
    # the line entirely instead of printing a blank one in its place.
    if memoria_stamp:
        lines.append(memoria_stamp)
    lines.extend([
        f"STATUS: {status}{status_detail}",
        f"BRANCH: {banner_branch}{ahead_behind}",
    ])
    if pull_directive_lines:
        lines.extend(pull_directive_lines)
    lines.extend([
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
    ])
    return lines


def run_preboot_migrations(project_root: str | None) -> dict:
    """Run all one-shot pre-boot migrations plus the best-effort background fetch.

    Order matters: session-booted flag cleanup, then the global statusLine
    migration (runs even without a project root — it's a user-level config,
    not project-level), then the non-critical remote fetch.

    Issue #63 (boot simplification, point 4): the two pre-v1.0.0 project-root
    migrations that used to run here (_migrate_runtime_to_unmassk,
    _migrate_untrack_generated_jsons — both from 037e0cb, 2026-03-17, ~4
    months of boots since) are retired from this path. Both scenarios are
    long past due: no active installation can still be on the pre-.unmassk/
    layout or have generated JSONs tracked from an old install. The
    _migrate_runtime_to_unmassk copy in bin/git-memory-upgrade.py is now the
    single home for that migration (upgrade-path only, for very old
    installs running an explicit `git memory upgrade`); the copy that used
    to live in lib/boot_migrations.py is deleted, not just unwired, per
    "una regla, un sitio". _migrate_untrack_generated_jsons has no other
    caller and had no upgrade-path duplicate, so it is deleted outright.
    _migrate_stale_context_writer_statusline (introduced 2026-06-05, only
    ~5 weeks old at the time of this change) is kept unchanged for one more
    cycle — conservative criterion, per the plan.

    Returns the fetch_memory_ref() result dict ({"status": ..., "age_seconds":
    ...}) — consumed by Task 3's freshness-stamp rendering, not by this
    function itself.
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

    # 0b-global. Migrate: fix stale context-writer statusLine in global settings.json
    _migrate_stale_context_writer_statusline()

    # 0c. Hardened, gated, rate-limited fetch (issue #49, plan Task 2) —
    # replaces the previous ungated, unhardened, unthrottled
    # `run_git(["fetch", "--quiet"])`. Fail-open on every branch.
    return fetch_memory_ref(project_root)


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

    # fetch_state ({"status": ..., "age_seconds": ...}) — issue #49, plan
    # Task 2's return value, consumed here by Task 3's MEMORY: stamp.
    fetch_state = run_preboot_migrations(project_root)

    status_lines, status, status_detail = render_status_section()

    # Issue #63 (boot simplification, point 2): sync a stale manifest AFTER
    # render_status_section() has already read it -- so this boot's own
    # STATUS line still truthfully reports the mismatch it found the
    # manifest in (TestVersionCheck's contract: "Plugin vX available
    # (installed: vY)"), instead of silently erasing the signal before it's
    # ever shown. The write still lands on disk before this process exits,
    # which is what matters for hooks/session-start-crew.py (the next
    # SessionStart hook in hooks.json's declared order) -- its own gate
    # reads manifest.version fresh, in a separate process, after this one.
    if project_root:
        trigger_auto_upgrade_if_needed(project_root)

    (branch_lines, branch, branch_keywords, branch_issue, ahead_behind,
     ahead_n, behind_n, upstream_ref, pull_directive_lines) = render_branch_section()

    # T2 fix (Moriarty, issue #49 repair round — Round-Trip Sabotage §34,
    # repo-identity confusion): an `@{u}` that resolves to a coherent,
    # fetchable ref is NOT proof that ref is a continuation of THIS
    # project's history — a misconfigured branch.<x>.remote/.merge can
    # point at a totally unrelated repo that happens to share a branch
    # name. Run the ancestry check ONCE here (only meaningful when an
    # upstream_ref actually exists) and let its result drive BOTH the
    # MEMORY: stamp wording below AND which ref resolve_boot_memory()/
    # extract_glossary_cached() are allowed to treat as this project's own
    # — never two independent decisions that could disagree.
    history_related: bool | None = None
    unrelated_remote_name: str | None = None
    if upstream_ref:
        history_related = check_upstream_shares_history(upstream_ref)
        if history_related is False:
            # Fail closed on TRUST (not on availability): never read,
            # cache-key, or label an unrelated/unverifiable upstream's
            # memory as "remote" for this project. Nulling upstream_ref
            # here reuses resolve_boot_memory()'s and
            # extract_glossary_cached()'s existing "no upstream" path
            # unchanged, rather than adding a new branch to either.
            # remote_name is captured separately (from the ORIGINAL,
            # not-yet-nulled ref) because extract_glossary()'s `--all`
            # scan reads refs/remotes/<name>/* directly — independent of
            # ahead/behind or of upstream_ref being nulled below — so it
            # needs its own explicit exclusion signal.
            unrelated_remote_name, _, _ = upstream_ref.partition("/")
            upstream_ref = None
            # Dante T2/T3 gap (session 2026-07-06,
            # TestPullDirectiveGapForUnrelatedUpstream): render_branch_section()
            # builds pull_directive_lines from raw behind_n BEFORE this check
            # ever runs, so "N commits behind" against an upstream confirmed
            # to share NO history is not a meaningful pull signal — git
            # itself would refuse the merge ("refusing to merge unrelated
            # histories"). Reuse the SAME history_related result computed
            # once above (no second merge-base call) to strip the
            # already-built directive from BOTH output surfaces: the full
            # boot-log content (branch_lines, extended into `lines` below)
            # and the short-banner copy (pull_directive_lines, passed to
            # render_boot_banner_lines()). Simplest correct fix: suppress
            # the directive entirely rather than reword it — there is no
            # truthful "behind N" figure to report when the two histories
            # don't share a common ancestor.
            if pull_directive_lines:
                branch_lines = [line for line in branch_lines if line not in pull_directive_lines]
                pull_directive_lines = []

    # Cerberus (nitpick, issue #49 repair round): "skipped_gate" ONLY ever
    # means "this repo has no unmassk-toolkit memory installed at all" (see
    # fetch_memory_ref's own gate check) — rendering a "LOCAL — never
    # synced with origin" line for a repo that was never SUPPOSED to sync
    # in the first place is misleading noise, not a freshness signal. The
    # gate already skips the fetch itself; the stamp must respect the same
    # gate and simply not appear. render_memoria_stamp() itself is left
    # returning its documented string for every status (its own direct unit
    # tests call it with "skipped_gate" and expect that string back) — the
    # gate is applied here, at the one real rendering call site, instead.
    memoria_stamp = (
        render_memoria_stamp(fetch_state, history_related)
        if fetch_state.get("status") != "skipped_gate"
        else ""
    )

    lines: list[str] = []
    lines.extend(render_header_section(plugin_root))
    # MEMORY: stamp lands near the top of the full boot-log content too —
    # see render_boot_banner_lines() for the stdout-banner copy of the same
    # line (issue #49, plan Task 3: both, not just one).
    if memoria_stamp:
        lines.append(memoria_stamp)
        lines.append("")

    lines.extend(status_lines)
    lines.extend(branch_lines)

    # BRANCHES section (plugin/boot decision, 2026-07-15 phase 2 — Bex: "so
    # it's known what's there", no elaborate per-branch state): remote_name
    # is derived from `upstream_ref` HERE, AFTER the `history_related is
    # False` nulling above — the exact same mechanism resolve_boot_memory()'s
    # own `upstream_ref` argument already relies on. A confirmed-unrelated
    # upstream already nulled upstream_ref to None by this point, so
    # remote_name is None too and render_branches_section() renders nothing
    # — see that function's own docstring for why no second, independent
    # exclude_remote parameter is needed here the way render_timeline_section()/
    # extract_glossary_cached() need one (those scan `--all`; this only ever
    # reads the one resolved remote's own refs).
    remote_name = upstream_ref.partition("/")[0] if upstream_ref else None
    lines.extend(render_branches_section(remote_name, branch))

    lines.extend(render_scopes_section(project_root))

    # issue #49, plan Task 4: read from origin/<branch> when strictly behind,
    # both sides (labeled) when diverged, local HEAD otherwise — ahead_n/
    # behind_n/upstream_ref are the exact numbers render_branch_section()
    # already computed for the `[N/M vs upstream]` display, reused here.
    memory = resolve_boot_memory(ahead_n, behind_n, upstream_ref)
    lines.extend(render_resume_section(memory, branch_issue, branch_keywords))

    # Merge recent + glossary remembers. exclude_remote (T2 fix) drops
    # refs/remotes/<unrelated_remote_name>/* from extract_glossary()'s own
    # `--all` scan — see the comment above where unrelated_remote_name is
    # set for why this can't just ride on the (already-nulled) upstream_ref.
    glossary = extract_glossary_cached(upstream_ref, exclude_remote=unrelated_remote_name)
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
    lines.extend(render_timeline_section(all_decisions, exclude_remote=unrelated_remote_name))

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
            memoria_stamp, pull_directive_lines,
        )
        print("\n".join(banner))

    sys.exit(0)


if __name__ == "__main__":
    main()
