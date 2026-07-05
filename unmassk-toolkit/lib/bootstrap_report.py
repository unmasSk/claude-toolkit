"""
bootstrap_report -- Finding classification, suggested actions, and
human-readable formatting for bin/git-memory-bootstrap.py.

Split out of git-memory-bootstrap.py (was 953 LOC). This module owns the
"turn raw scanner output into facts/hypotheses/suggestions, then format
them" concern. It never touches the filesystem or git directly — every
function here takes already-scanned data as arguments (from bootstrap_tree,
bootstrap_deps, bootstrap_commits) and returns/prints derived data.
"""

from typing import Any


# ── Classification ────────────────────────────────────────────────────────

def classify_findings(signals: list[dict[str, str]], pkg_info: dict[str, Any] | None, py_info: dict[str, Any] | None, commits: dict[str, Any] | None, monorepo: dict[str, Any], ci_signals: list[str], existing: dict[str, Any]) -> list[dict[str, Any]]:
    """Classify all scanner results into facts (directly detected) and hypotheses (inferred).

    Returns:
        List of finding dicts, each with "level", "category", "text", and "source".
    """
    findings: list[dict[str, Any]] = []

    # Facts: directly detected from files
    seen_signals = set()
    for sig in signals:
        label = sig["signal"]
        if label not in seen_signals:
            seen_signals.add(label)
            findings.append({
                "level": "fact",
                "category": "stack",
                "text": label,
                "source": sig["file"],
            })

    # Package.json details
    if pkg_info:
        for fw in pkg_info.get("frameworks", []):
            if fw not in seen_signals:
                findings.append({
                    "level": "fact",
                    "category": "stack",
                    "text": fw,
                    "source": "package.json",
                })
        if "typescript" in pkg_info:
            findings.append({
                "level": "fact",
                "category": "stack",
                "text": f"TypeScript {pkg_info['typescript']}",
                "source": "package.json",
            })
        if "package_manager" in pkg_info:
            findings.append({
                "level": "fact",
                "category": "stack",
                "text": f"Package manager: {pkg_info['package_manager']}",
                "source": "package.json",
            })
        if pkg_info.get("dependency_count", 0) > 0:
            findings.append({
                "level": "fact",
                "category": "size",
                "text": f"{pkg_info['dependency_count']} dependencies",
                "source": "package.json",
            })

    # Python details
    if py_info:
        for fw in py_info.get("frameworks", []):
            findings.append({
                "level": "fact",
                "category": "stack",
                "text": fw,
                "source": "pyproject.toml",
            })
        if "python_requires" in py_info:
            findings.append({
                "level": "fact",
                "category": "stack",
                "text": f"Python {py_info['python_requires']}",
                "source": "pyproject.toml",
            })
        if "build_backend" in py_info:
            findings.append({
                "level": "fact",
                "category": "stack",
                "text": f"Build: {py_info['build_backend']}",
                "source": "pyproject.toml",
            })

    # Hypotheses: inferred with medium signal
    mono_signals = monorepo.get("signals", [])
    mono_scope_map = monorepo.get("scope_map", {})
    if mono_signals:
        detail = list(mono_signals)
        if mono_scope_map:
            scopes = ", ".join(sorted(mono_scope_map.values())[:8])
            detail.append(f"Scopes: {scopes}")
        findings.append({
            "level": "hypothesis",
            "category": "structure",
            "text": "Monorepo detected",
            "detail": detail,
            "source": "directory structure",
        })

    if ci_signals:
        for ci_sig in ci_signals:
            if "commitlint" in ci_sig.lower():
                findings.append({
                    "level": "hypothesis",
                    "category": "compatibility",
                    "text": "commitlint may reject trailer-format commits",
                    "detail": [ci_sig],
                    "source": ci_sig.split(":")[0] if ":" in ci_sig else "ci config",
                })
                break
        else:
            # CI exists but no commitlint issue
            for ci_sig in ci_signals:
                findings.append({
                    "level": "fact",
                    "category": "ci",
                    "text": ci_sig,
                    "source": "project config",
                })

    # Commit history insights
    if commits:
        if commits["count"] > 0:
            findings.append({
                "level": "fact",
                "category": "history",
                "text": f"{commits['count']} recent commits analyzed",
                "source": "git log",
            })
            num_authors = len(commits["authors"])
            if num_authors > 1:
                authors_list = sorted(commits["authors"].items(), key=lambda x: -x[1])
                top = ", ".join(f"{a} ({n})" for a, n in authors_list[:3])
                findings.append({
                    "level": "fact",
                    "category": "team",
                    "text": f"{num_authors} contributors: {top}",
                    "source": "git log",
                })
            if commits["has_trailers"] > 0:
                findings.append({
                    "level": "fact",
                    "category": "memory",
                    "text": f"{commits['has_trailers']}/{commits['count']} commits already have trailers",
                    "source": "git log",
                })

    # Existing memory state
    if existing.get("already_installed"):
        findings.append({
            "level": "fact",
            "category": "memory",
            "text": f"git-memory already installed (v{existing.get('installed_version', '?')})",
            "source": "manifest",
        })

    return findings


# ── Suggested Actions ─────────────────────────────────────────────────────

def suggest_actions(findings: list[dict[str, Any]], existing: dict[str, Any], monorepo: dict[str, Any], ci_signals: list[str]) -> list[dict[str, Any]]:
    """Build a list of suggested next steps based on findings.

    Returns:
        List of action dicts with "action", "reason", and "detail" keys.
    """
    suggestions = []

    # Already installed?
    if existing.get("already_installed"):
        suggestions.append({
            "action": "skip_bootstrap",
            "reason": "git-memory already installed",
            "detail": "Run `git memory doctor` to check health instead",
        })
        return suggestions

    # Monorepo?
    mono_signals = monorepo.get("signals", [])
    mono_scope_map = monorepo.get("scope_map", {})
    if mono_signals:
        scope_detail = "Ask user: global memory or per-subproject?"
        if mono_scope_map:
            scopes = ", ".join(sorted(mono_scope_map.values())[:8])
            scope_detail += f" Available scopes: {scopes}"
        suggestions.append({
            "action": "ask_scope",
            "reason": "Monorepo detected",
            "detail": scope_detail,
        })

    # commitlint risk?
    has_commitlint = any("commitlint" in str(f.get("text", "")).lower() for f in findings)
    if has_commitlint:
        suggestions.append({
            "action": "consider_compatible_mode",
            "reason": "commitlint detected — trailers may be rejected",
            "detail": "Consider installing in compatible mode",
        })

    # Empty project?
    code_findings = [f for f in findings if f["category"] == "stack"]
    if not code_findings:
        suggestions.append({
            "action": "minimal_bootstrap",
            "reason": "No stack detected (empty or non-code project)",
            "detail": "Create memory as work progresses, no upfront bootstrap needed",
        })
    else:
        # Normal bootstrap: collect facts for memo commit
        facts = [f for f in findings if f["level"] == "fact" and f["category"] == "stack"]
        if facts:
            stack_text = ", ".join(f["text"] for f in facts[:8])
            suggestions.append({
                "action": "bootstrap_commit",
                "reason": f"Stack detected: {stack_text}",
                "detail": "Create bootstrap memo(stack) commit after user confirmation",
                "proposed_trailer": f"Memo: stack - {stack_text}",
            })

    return suggestions


# ── Output ────────────────────────────────────────────────────────────────

def format_human(findings: list[dict[str, Any]], suggestions: list[dict[str, Any]], repo_info: dict[str, str]) -> str:
    """Format findings and suggestions as a human-readable text report."""
    lines = []
    lines.append("=== git memory bootstrap — Project Scout ===")
    lines.append(f"Repo: {repo_info.get('name', '?')} ({repo_info.get('branch', '?')})")
    lines.append("")

    # Group by level
    facts = [f for f in findings if f["level"] == "fact"]
    hypotheses = [f for f in findings if f["level"] == "hypothesis"]

    if facts:
        lines.append("── Facts (detected directly) ──")
        for f in facts:
            lines.append(f"  ✅ [{f['category']}] {f['text']}")
        lines.append("")

    if hypotheses:
        lines.append("── Hypotheses (need confirmation) ──")
        for f in hypotheses:
            lines.append(f"  ❓ [{f['category']}] {f['text']}")
            if "detail" in f:
                if isinstance(f["detail"], list):
                    for d in f["detail"]:
                        lines.append(f"      → {d}")
                else:
                    lines.append(f"      → {f['detail']}")
        lines.append("")

    if suggestions:
        lines.append("── Suggested Actions ──")
        for s in suggestions:
            lines.append(f"  → {s['action']}: {s['reason']}")
            if "proposed_trailer" in s:
                lines.append(f"    Trailer: {s['proposed_trailer']}")
        lines.append("")

    if not findings:
        lines.append("No findings. Empty project or nothing to detect.")

    return "\n".join(lines)
