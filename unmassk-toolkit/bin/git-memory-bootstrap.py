#!/usr/bin/env python3
"""
git-memory-bootstrap -- Conservative analyzer for first contact with a repo.

Analyzes structure, dependencies, tech stack, and recent commits.
Classifies findings by confidence level (fact/hypothesis).
Produces structured output for Claude to present to the user and confirm.

Does NOT create commits. Only analyzes and reports.
Claude uses the output to present findings, get confirmation,
and create the bootstrap commit with the appropriate trailers.

Usage:
  git memory bootstrap              # Human-readable report
  git memory bootstrap --json       # Machine-readable JSON
  git memory bootstrap --silent     # Exit code only (0=findings, 1=empty)

Exit codes:
  0: Findings produced
  1: Nothing to report (empty project or error)

Implementation note: the scanning/classification logic used to live
entirely in this file (953 LOC, never split across 10 rounds). It is now
split by theme into lib/ modules — this file is the thin CLI entrypoint
(argument parsing + orchestration) only:
  - lib/bootstrap_tree.py     — directory walk + signal-file matching
  - lib/bootstrap_deps.py     — package.json/pyproject/monorepo/CI/existing-install detection
  - lib/bootstrap_commits.py  — recent git history analysis
  - lib/bootstrap_report.py   — finding classification + suggestions + human-readable formatting

Every function is re-exported by name below (not `import *`) so
`python3 git-memory-bootstrap.py` behaves identically, and so tests that
load this module directly via importlib and reach into its namespace
(e.g. mod.check_existing_memory, mod.scan_tree, mod.detect_monorepo,
mod.detect_ci_commitlint) keep working unchanged.
"""

import argparse
import json
import os
import sys

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import run_git
from version import VERSION

from bootstrap_tree import SKIP_DIRS, SIGNAL_FILES, MAX_TREE_DEPTH, scan_tree, scan_signal_files
from bootstrap_deps import (
    scan_package_json, scan_pyproject, detect_monorepo,
    detect_ci_commitlint, check_existing_memory,
)
from bootstrap_commits import SCAN_COMMITS, scan_recent_commits
from bootstrap_report import classify_findings, suggest_actions, format_human


# ── Helpers ───────────────────────────────────────────────────────────────

def find_project_root() -> str:
    """Find the project root using git rev-parse, falling back to cwd."""
    code, root = run_git(["rev-parse", "--show-toplevel"])
    if code == 0 and root:
        return root
    return os.getcwd()


# ── Main ──────────────────────────────────────────────────────────────────

def run_bootstrap(silent: bool = False, as_json: bool = False) -> int:
    """Run all scanners, classify findings, and produce the report.

    Returns:
        0 if meaningful findings were found, 1 otherwise.
    """
    root = find_project_root()

    # Repo info
    _, branch = run_git(["rev-parse", "--abbrev-ref", "HEAD"])
    _, remote = run_git(["remote", "get-url", "origin"])
    repo_name = os.path.basename(root)
    repo_info = {
        "name": repo_name,
        "branch": branch or "unknown",
        "remote": remote or "none",
        "root": root,
    }

    # Run all scans
    tree = scan_tree(root)
    signals = scan_signal_files(root, tree["files"])
    pkg_info = scan_package_json(root)
    py_info = scan_pyproject(root)
    commits = scan_recent_commits()
    monorepo = detect_monorepo(root, tree)
    ci_signals = detect_ci_commitlint(root)
    existing = check_existing_memory(root)

    # Classify
    findings = classify_findings(signals, pkg_info, py_info, commits, monorepo, ci_signals, existing)
    suggestions = suggest_actions(findings, existing, monorepo, ci_signals)

    # Output
    if as_json:
        output = {
            "version": VERSION,
            "repo": repo_info,
            "findings": findings,
            "suggestions": suggestions,
            "monorepo_signals": monorepo.get("signals", []),
            "monorepo_scope_map": monorepo.get("scope_map", {}),
            "ci_signals": ci_signals,
            "existing_memory": existing,
        }
        if pkg_info:
            output["package_json"] = pkg_info
        if py_info:
            output["pyproject"] = py_info
        if commits:
            output["commits"] = commits
        print(json.dumps(output, indent=2, default=str))
    elif not silent:
        print(format_human(findings, suggestions, repo_info))

    # Exit 0 if meaningful findings (stack/structure), 1 if empty/trivial
    meaningful = [f for f in findings if f["category"] in ("stack", "structure", "compatibility")]
    return 0 if meaningful else 1


def main() -> None:
    """CLI entry point. Parses args and runs the bootstrap analyzer."""
    parser = argparse.ArgumentParser(description="Analyze repo for first contact.")
    parser.add_argument("--silent", action="store_true", help="Exit code only")
    parser.add_argument("--json", dest="json", action="store_true", help="Machine-readable JSON output")
    args = parser.parse_args()
    silent = args.silent
    as_json = args.json

    exit_code = run_bootstrap(silent=silent, as_json=as_json)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
