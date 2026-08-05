"""
Drift tests simulating 6 months of commit history.

Generates 200 commits across 6 scopes, then validates deep search, hook
robustness (fixup!/squash!/amend!/merge/revert), and nested Git prefixes.

Retirement note (memoria-v2 cleanup, docs/memoria-v2/PLAN-CONSTRUCCION.md
§9.3): test_gc_tombstones, test_dedup_integrity, test_snapshot_budget,
test_truncation and test_delimiter_collision were all removed — every one
of them depended on hooks/precompact-snapshot.py (via the run_snapshot()
helper), which no longer exists on disk.
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
    git_cmd, assert_repo_integrity,
)

# ── Config ──────────────────────────────────────────────────────────────

TOTAL_COMMITS = 200
DECISION_COUNT = 12
MEMO_COUNT = 8
SCOPES = ["auth", "forms", "api", "ui", "billing", "reports"]
EMOJIS = {"feat": "✨", "fix": "🐛", "refactor": "♻️", "chore": "🔧",
           "context": "💾", "decision": "🧭", "memo": "📌"}
CODE_TYPES = ["feat", "fix", "refactor", "chore"]


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


# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): run_snapshot() invocaba
# hooks/precompact-snapshot.py, que ya no existe en disco (confirmado por
# FileNotFoundError en ejecucion real) — eliminado junto con el resto del
# sistema de memoria v1. Sus unicos cuatro llamadores (test_dedup_integrity,
# test_snapshot_budget, test_truncation, test_delimiter_collision, mas
# abajo) se retiraron con el.


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


# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): test_dedup_integrity,
# test_snapshot_budget y test_truncation llamaban a run_snapshot() (ver
# nota de retiro mas arriba) — 100% de su contenido probaba
# hooks/precompact-snapshot.py, eliminado.


# RETIRADO (memoria v2, 2026-08-05): test_hook_robustness y
# test_nested_prefixes llamaban a check_hook_msg() -> PRE_HOOK
# (hooks/pre-validate-commit-trailers.py), borrado entero junto con el
# resto del sistema de memoria v1 (confirmado: check_hook_msg() devuelve
# rc=2/"can't open file" para todo, no el resultado real que estos tests
# esperaban). Su sucesor, hooks/customs.py, no tiene el concepto de
# fixup!/squash!/amend!/Merge/Revert -- esos eran prefijos que el v1
# TOLERABA para no bloquear un rewrite de historia local legitimo;
# customs.py resuelve la misma familia de casos de otra forma (rebase con
# --continue/--skip/--abort pasa siempre, ver TestRebasePassthroughOnlyForInFlightOperations
# en tests/memory/test_customs_hook.py) -- no hay un equivalente 1:1 al
# que redirigir estos dos tests sin inventar cobertura no pedida.

# NOTE (2026-07-25): test_post_hook_exit_code was removed here — it invoked
# post-validate-commit-trailers.py, which was deleted outright (dead code in
# the wrapper's path; see test_memo_category_deadend_contract.py's
# retirement note for the full history). pre-validate-commit-trailers.py
# never inspected tool_output/exit_code at all — it only blocks the tool
# invocation BEFORE execution based on the command string — so there was no
# live pre-hook behavior to adapt this test toward, and now the hook itself
# is gone too.


# RETIRADO (PLAN-CONSTRUCCION.md paso 9.3): test_delimiter_collision
# llamaba a run_snapshot() (ver nota de retiro mas arriba) — probaba que
# los pipes no rompian el snapshot de hooks/precompact-snapshot.py,
# eliminado.


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
