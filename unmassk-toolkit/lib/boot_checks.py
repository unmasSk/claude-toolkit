"""
Boot I/O checks for session-start-boot.py — thin re-export shim (Cerberus
round-6 LOC audit: this module had grown to 563 lines, past the project's
500-line limit).

Split further into two topic modules, both re-exported here by name:

- lib/boot_health.py — "is the plugin/repo installed correctly?": skill-drift
  + installed-version comparison, doctor/repair runners, GitHub issue-status
  lookups (_md5_file, _latest_version_dir, _build_repo_skill_index,
  check_skill_drift, check_version_mismatch, run_doctor, run_repair,
  check_issue_status, _issue_matches_next).
- lib/boot_git_checks.py — "read git/repo state for this boot": branch,
  scopes.json, consolidation threshold, commit timeline, remote branches
  (parse_branch_keywords, time_ago, get_timeline, get_last_context_time,
  render_branch_section, render_branches_section, render_scopes_section,
  render_consolidation_section).

Kept as a shim (rather than deleted) because three things resolve names
through THIS exact module:

1. lib/boot_render.py's `from boot_checks import (...)`.
2. tests/test_security_regression.py loads this exact file path via
   `importlib.util.spec_from_file_location(..., BOOT_CHECKS_PATH)` and calls
   `mod.render_scopes_section(...)` directly on the loaded module.
3. Docstrings/comments elsewhere (tests/test_boot_output.py,
   tests/test_security_regression.py) reference "lib/boot_checks.py:<fn>()"
   by name.

Confirmed unidirectional DAG: boot_memory <- boot_health/boot_git_checks <-
boot_checks <- boot_render — this module must never be imported FROM either
of the two modules it re-exports from.

Pure refactor: behavior is byte-for-byte identical to before the split.
"""

from boot_health import (
    _md5_file,
    _latest_version_dir,
    _build_repo_skill_index,
    check_skill_drift,
    check_version_mismatch,
    run_doctor,
    run_repair,
    check_issue_status,
    _issue_matches_next,
)
from boot_git_checks import (
    parse_branch_keywords,
    time_ago,
    get_timeline,
    get_last_context_time,
    render_branch_section,
    render_branches_section,
    render_scopes_section,
    render_consolidation_section,
)

__all__ = [
    "_md5_file",
    "_latest_version_dir",
    "_build_repo_skill_index",
    "check_skill_drift",
    "check_version_mismatch",
    "run_doctor",
    "run_repair",
    "check_issue_status",
    "_issue_matches_next",
    "parse_branch_keywords",
    "time_ago",
    "get_timeline",
    "get_last_context_time",
    "render_branch_section",
    "render_branches_section",
    "render_scopes_section",
    "render_consolidation_section",
]
