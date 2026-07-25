"""
Drift tests simulating 6 months of commit history.

Generates 200 commits across 6 scopes, then validates search, dedup,
snapshot budget, truncation, hook robustness, delimiter collision, nested
prefixes, and GC tombstones.
"""

import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

import pytest

from conftest import (
    PRECOMPACT_SCRIPT, PRE_HOOK,
    run_cmd, git_cmd, check_hook_msg, assert_repo_integrity,
)

# ── Config ──────────────────────────────────────────────────────────────

TOTAL_COMMITS = 200
DECISION_COUNT = 12
MEMO_COUNT = 8
SCOPES = ["auth", "forms", "api", "ui", "billing", "reports"]
EMOJIS = {"feat": "✨", "fix": "🐛", "refactor": "♻️", "chore": "🔧",
           "context": "💾", "decision": "🧭", "memo": "📌"}
CODE_TYPES = ["feat", "fix", "refactor", "chore"]
SNAPSHOT_MAX_LINES = 18


# ── Commit generators ──────────────────────────────────────────────────

def gen_code_commit(idx, scope, date_str, cwd):
    """Generate a random code commit (feat/fix/refactor/chore)."""
    ctype = random.choice(CODE_TYPES)
    emoji = EMOJIS[ctype]
    slug = f"change-{idx}"
    msg = (
        f"{emoji} {ctype}({scope}): {slug}\n\n"
        f"Issue: CU-042\n"
        f"Why: automated drift test commit #{idx}\n"
        f"Touched: app/{scope}/{slug}.php"
    )
    if random.random() < 0.10:
        msg += f"\nNext: continue {scope} work after commit {idx}"
    if random.random() < 0.05:
        msg += f"\nBlocker: waiting for {scope} API keys"
    env = {"GIT_AUTHOR_DATE": date_str, "GIT_COMMITTER_DATE": date_str}
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd, env)


def gen_decision(scope, idx, date_str, cwd):
    """Generate a decision commit with a random topic."""
    topics = [
        f"use library-{idx} for {scope}",
        f"adopt pattern-{idx} in {scope}",
        f"switch to approach-{idx} for {scope}",
    ]
    topic = random.choice(topics)
    msg = (
        f"🧭 decision({scope}): {topic}\n\n"
        f"Issue: CU-042\n"
        f"Why: evaluated alternatives for {scope} at decision point {idx}\n"
        f"Decision: {topic} — benchmarks show 3x improvement"
    )
    env = {"GIT_AUTHOR_DATE": date_str, "GIT_COMMITTER_DATE": date_str}
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd, env)


def gen_memo(scope, idx, date_str, cwd):
    """Generate a memo commit (preference, requirement, or antipattern)."""
    categories = ["preference", "requirement", "antipattern"]
    cat = random.choice(categories)
    descriptions = {
        "preference": f"always use strict types in {scope}",
        "requirement": f"client wants real-time updates in {scope}",
        "antipattern": f"never use raw SQL in {scope}",
    }
    desc = descriptions[cat]
    msg = (
        f"📌 memo({scope}): {desc}\n\n"
        f"Memo: {cat} - {desc}\n"
        f"Why: drift test memo #{idx}"
    )
    env = {"GIT_AUTHOR_DATE": date_str, "GIT_COMMITTER_DATE": date_str}
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd, env)


def gen_context(scope, idx, date_str, cwd):
    """Generate a context-save commit (pause work session)."""
    msg = (
        f"💾 context({scope}): pause {scope} work session {idx}\n\n"
        f"Issue: CU-042\n"
        f"Why: end of day\n"
        f"Next: resume {scope} implementation from commit {idx}\n"
        f"Blocker: waiting for {scope} deploy slot"
    )
    env = {"GIT_AUTHOR_DATE": date_str, "GIT_COMMITTER_DATE": date_str}
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd, env)


def build_history(cwd):
    """Generate 200 commits spread over 6 months."""
    start_date = datetime(2025, 9, 1, 9, 0, 0)
    end_date = datetime(2026, 3, 1, 18, 0, 0)
    total_seconds = int((end_date - start_date).total_seconds())

    decision_positions = sorted(random.sample(range(10, TOTAL_COMMITS - 5), DECISION_COUNT))
    memo_positions = sorted(random.sample(
        [i for i in range(10, TOTAL_COMMITS - 5) if i not in decision_positions],
        MEMO_COUNT,
    ))
    context_positions = [TOTAL_COMMITS // 3, 2 * TOTAL_COMMITS // 3, TOTAL_COMMITS - 2]

    d_idx = m_idx = c_idx = 0

    for i in range(TOTAL_COMMITS):
        offset = int(total_seconds * (i / TOTAL_COMMITS))
        commit_date = start_date + timedelta(seconds=offset)
        date_str = commit_date.strftime("%Y-%m-%dT%H:%M:%S")
        scope = SCOPES[i % len(SCOPES)]

        if i in decision_positions:
            gen_decision(scope, d_idx, date_str, cwd)
            d_idx += 1
        elif i in memo_positions:
            gen_memo(scope, m_idx, date_str, cwd)
            m_idx += 1
        elif i in context_positions:
            gen_context(scope, c_idx, date_str, cwd)
            c_idx += 1
        else:
            gen_code_commit(i, scope, date_str, cwd)


def run_snapshot(cwd):
    """Run precompact-snapshot and return the snapshot portion of stdout.

    Filters out any post-snapshot instructions (e.g. context checkpoint
    reminder) by extracting only lines between the snapshot markers.

    Issue #52 (House, round 2): stderr used to be silently discarded here
    (`rc, out, _ = ...`). Every one of this helper's callers asserts on the
    RETURNED SNAPSHOT STRING (e.g. "Snapshot returned empty"), which gives
    zero diagnostic trail if precompact-snapshot.py actually crashed --
    exactly the situation for the 7 ubuntu-only CI failures under issue #52
    that don't reproduce locally. Fail loudly here with rc/stdout/stderr
    embedded the moment the script doesn't exit 0, so the NEXT CI run
    surfaces the real cause in the pytest failure message instead of a
    downstream assert with no clue why the snapshot was empty/malformed.
    """
    rc, out, err = run_cmd([sys.executable, PRECOMPACT_SCRIPT], cwd, timeout=15)
    assert rc == 0, (
        f"precompact-snapshot.py exited {rc} (expected 0).\n"
        f"--- stdout ---\n{out}\n"
        f"--- stderr ---\n{err}"
    )
    # Extract only the snapshot block (between markers)
    lines = out.split("\n")
    snapshot_lines = []
    in_snapshot = False
    for line in lines:
        if "GIT MEMORY SNAPSHOT" in line:
            in_snapshot = True
        if in_snapshot:
            snapshot_lines.append(line)
        if "END SNAPSHOT" in line:
            break
    return "\n".join(snapshot_lines) if snapshot_lines else out


# ── Module-scoped fixture ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def drift_repo():
    """Create a drift test repo with 200 commits. Shared across all tests."""
    path = tempfile.mkdtemp(prefix="drift-test-")
    git_cmd(["init"], path)
    git_cmd(["checkout", "-b", "dev"], path)
    git_cmd(["commit", "--allow-empty", "-m",
             "🔧 chore: init repo\n\nWhy: initial setup\nTouched: none"], path)
    git_cmd(["checkout", "-b", "feat/CU-042-big-feature"], path)
    build_history(path)
    # Issue #61 (reabierto): probe fail-loud ANTES de que cualquier test use
    # este fixture compartido (module-scoped) — si el object-store quedó
    # corrupto (gc race) mientras se generaban los 200 commits, esto falla
    # con un mensaje explícito de "fixture corrupto" en vez de un opaco
    # fallo de conteo/búsqueda en cualquiera de los tests que lo consumen
    # (test_deep_search y el resto de este archivo).
    assert_repo_integrity(path, "drift_repo fixture tras build_history (200 commits)")
    yield path
    shutil.rmtree(path, ignore_errors=True)


# ── Tests ──────────────────────────────────────────────────────────────


def _git_log_or_fail(args, cwd):
    """Run a `git log` query and assert success, embedding rc/stderr on failure.

    Issue #61 (House root cause): this function's callers used to discard
    rc entirely (`_, out, _ = git_cmd(...)`), so a transient git subprocess
    failure under CI resource pressure (thousands of forked git processes
    on a 2-core/7GB ubuntu-latest runner) surfaced as an opaque downstream
    count assertion (e.g. "assert 4 >= 12") with zero trail back to the
    real cause. Same rationale/pattern already applied to run_snapshot()
    above (issue #52, House round 2).
    """
    rc, out, err = git_cmd(args, cwd)
    assert rc == 0, (
        f"git {' '.join(args)} exited {rc} (expected 0).\n"
        f"--- stdout ---\n{out}\n"
        f"--- stderr ---\n{err}"
    )
    return out


def test_deep_search(drift_repo):
    """Verify deep search returns results by Issue/scope/recency."""
    cwd = drift_repo

    # All decisions findable
    out = _git_log_or_fail(["log", "--all", "--grep=Decision:", "--pretty=format:%h %s %b"], cwd)
    decision_lines = [l for l in out.split("\n") if "Decision:" in l]
    assert len(decision_lines) >= DECISION_COUNT

    # All memos findable
    out = _git_log_or_fail(["log", "--all", "--grep=Memo:", "--pretty=format:%h %s %b"], cwd)
    memo_lines = [l for l in out.split("\n") if "Memo:" in l]
    assert len(memo_lines) >= MEMO_COUNT

    # Deep search finds decisions across multiple scopes
    out = _git_log_or_fail(["log", "--all", "--grep=Decision:", "--pretty=format:%h %s"], cwd)
    all_d_scopes = set()
    for line in out.strip().split("\n"):
        sm = re.search(r"decision\((\w+)\)", line, re.IGNORECASE)
        if sm:
            all_d_scopes.add(sm.group(1))
    assert len(all_d_scopes) >= 2

    # Issue filter
    out = _git_log_or_fail(["log", "--all", "--grep=Issue: CU-042", "--oneline"], cwd)
    issue_count = len([l for l in out.strip().split("\n") if l.strip()])
    assert issue_count >= 50


def test_dedup_integrity(drift_repo):
    """Verify snapshot preserves entries from different scopes."""
    cwd = drift_repo
    snapshot = run_snapshot(cwd)
    assert snapshot, "Snapshot returned empty"

    # Verify blocker dedup
    blocker_texts = []
    in_blockers = False
    for line in snapshot.split("\n"):
        if "Blockers:" in line:
            in_blockers = True
            continue
        elif line and not line.startswith("  "):
            in_blockers = False
        if in_blockers and line.strip().startswith("- ["):
            m = re.match(r"\s*-\s*\[\w+\]\s*(.+)", line)
            if m:
                blocker_texts.append(m.group(1).lower())

    assert len(blocker_texts) == len(set(blocker_texts)), f"Duplicate blockers: {blocker_texts}"


def test_snapshot_budget(drift_repo):
    """Verify budget in normal and stress scenarios."""
    cwd = drift_repo

    # Normal snapshot
    snapshot = run_snapshot(cwd)
    lines = snapshot.split("\n")
    assert len(lines) <= SNAPSHOT_MAX_LINES, f"Normal: {len(lines)} > {SNAPSHOT_MAX_LINES}"
    assert any("GIT MEMORY SNAPSHOT" in l for l in lines)
    assert any("END SNAPSHOT" in l for l in lines)
    assert any(l.startswith("Branch:") for l in lines)

    # Stress: max out every section
    for i, scope in enumerate(["alpha", "beta", "gamma", "delta", "epsilon"]):
        msg = f"🧭 decision({scope}): stress decision {i}\n\nWhy: stress test\nDecision: stress pick {scope}"
        git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    for i, scope in enumerate(["alpha", "beta", "gamma", "delta"]):
        msg = f"📌 memo({scope}): stress memo {i}\n\nMemo: preference - stress pref for {scope}"
        git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    for i in range(5):
        scope = SCOPES[i % len(SCOPES)]
        msg = f"✨ feat({scope}): stress feature {i}\n\nWhy: stress test\nTouched: app/{scope}/stress-{i}.php\nNext: stress pending item {i}"
        git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    for i in range(3):
        scope = SCOPES[i % len(SCOPES)]
        msg = f"💾 context({scope}): stress context {i}\n\nWhy: stress test\nNext: stress next from context {i}\nBlocker: unique blocker {i} for {scope}"
        git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    stress_snapshot = run_snapshot(cwd)
    stress_lines = stress_snapshot.split("\n")
    assert len(stress_lines) <= SNAPSHOT_MAX_LINES, f"Stress: {len(stress_lines)} > {SNAPSHOT_MAX_LINES}"


def test_truncation(drift_repo):
    """Verify long trailer values get truncated in snapshot."""
    cwd = drift_repo
    long_text = "X" * 300
    msg = f"🧭 decision(trunc): long test\n\nWhy: test\nDecision: {long_text}"
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    snapshot = run_snapshot(cwd)
    assert "..." in snapshot and "X" * 50 in snapshot, "Truncation not detected"
    assert "X" * 250 not in snapshot, "Value not truncated — full 300 chars present"


def test_hook_robustness(drift_repo):
    """Verify hooks handle fixup!, merge, revert messages correctly."""
    cwd = drift_repo

    # fixup!, squash!, amend! should pass with trailers
    assert check_hook_msg("fixup! ✨ feat(auth): fix typo",
                          cwd, "Why: typo\nTouched: auth.py\nIssue: #1") == 0
    assert check_hook_msg("squash! 🐛 fix(api): cleanup",
                          cwd, "Why: cleanup\nTouched: api.py\nIssue: CU-042") == 0
    assert check_hook_msg("amend! ♻️ refactor(ui): rename",
                          cwd, "Why: clarity\nTouched: ui.py\nIssue: CU-042") == 0

    # Merge and Revert whitelisted
    assert check_hook_msg("Merge branch 'main' into dev", cwd) == 0
    assert check_hook_msg("Merge remote-tracking branch 'origin/main'", cwd) == 0
    assert check_hook_msg("Revert feat(auth): add login", cwd) == 0

    # Claude without trailers → blocked
    assert check_hook_msg("✨ feat(auth): no trailers here", cwd, as_claude=True) != 0

    # Human without trailers → warn only (exit 0)
    assert check_hook_msg("✨ feat(auth): no trailers here", cwd, as_claude=False) == 0


# NOTE (2026-07-25): test_post_hook_exit_code was removed here — it invoked
# post-validate-commit-trailers.py, which was deleted outright (dead code in
# the wrapper's path; see test_memo_category_deadend_contract.py's
# retirement note for the full history). pre-validate-commit-trailers.py
# (the surviving hook, still exercised elsewhere in this file via
# check_hook_msg/PRE_HOOK) never inspected tool_output/exit_code at all — it
# only blocks the tool invocation BEFORE execution based on the command
# string — so there is no live pre-hook behavior to adapt this test toward.


def test_delimiter_collision(drift_repo):
    """Verify commit messages with pipe characters don't break the snapshot."""
    cwd = drift_repo

    msg = "✨ feat(parser): fix collision with |---END---| tokens\n\nIssue: CU-042\nWhy: pipes in messages | should not | break parsing\nTouched: parser.py"
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    msg2 = "🧭 decision(parser): choose approach A | not B | not C\n\nWhy: A handles edge cases\nDecision: approach A over B|C — cleaner API"
    git_cmd(["commit", "--allow-empty", "-m", msg2], cwd)

    snapshot = run_snapshot(cwd)
    assert snapshot, "Snapshot empty after pipe-containing commits"
    assert "GIT MEMORY SNAPSHOT" in snapshot, "Snapshot corrupted by pipes"
    assert "END SNAPSHOT" in snapshot, "Snapshot missing footer"
    assert len(snapshot.split("\n")) <= SNAPSHOT_MAX_LINES


def test_nested_prefixes(drift_repo):
    """Verify hooks handle nested Git prefixes like squash! fixup! feat:"""
    cwd = drift_repo

    assert check_hook_msg(
        "squash! fixup! ✨ feat(auth): double nested",
        cwd, "Why: test\nTouched: auth.py\nIssue: CU-042") == 0

    assert check_hook_msg(
        "fixup! fixup! 🐛 fix(api): triple fixup",
        cwd, "Why: test\nTouched: api.py\nIssue: CU-042") == 0

    assert check_hook_msg(
        "amend! squash! fixup! ♻️ refactor(ui): triple nested",
        cwd, "Why: test\nTouched: ui.py\nIssue: CU-042") == 0


def test_gc_tombstones(drift_repo):
    """Verify GC tombstone trailers suppress items from the snapshot."""
    cwd = drift_repo

    # Create Next + Blocker
    msg = "💾 context(api): pause api work\n\nWhy: end of day\nNext: implement rate limiting for api\nBlocker: waiting for api credentials"
    git_cmd(["commit", "--allow-empty", "-m", msg], cwd)

    snapshot_before = run_snapshot(cwd)
    assert "rate limiting" in snapshot_before, "Next not found before GC"
    assert "api credentials" in snapshot_before, "Blocker not found before GC"

    # GC tombstones
    gc_msg = "🔧 chore(memory): gc — 2 items cleaned\n\nWhy: automated memory garbage collection\nResolved-Next: implement rate limiting for api\nStale-Blocker: waiting for api credentials"
    git_cmd(["commit", "--allow-empty", "-m", gc_msg], cwd)

    snapshot_after = run_snapshot(cwd)
    assert "rate limiting" not in snapshot_after, "Next still present after GC"
    assert "api credentials" not in snapshot_after, "Blocker still present after GC"
    assert "GIT MEMORY SNAPSHOT" in snapshot_after
    assert "END SNAPSHOT" in snapshot_after


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
