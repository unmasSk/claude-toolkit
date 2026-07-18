"""
Acceptance contract (test-first, BEFORE Ultron) for the pending-Next
cutoff bug in lib/boot_memory.py:extract_memory().

Bug (reported, real incident)
------------------------------
extract_memory()'s pending-item loop (lib/boot_memory.py:~259):

    if "Next" in trailers and len(pending) < MAX_PENDING:
        ...
        pending.append({...})

collects EVERY commit carrying a `Next:` trailer up to MAX_PENDING=30,
with zero filter against the most recent context() commit. Result: the
boot RESUME section shows a Next that was already superseded by a later
context() alongside the genuinely current one (observed live: d6187db,
an OLD context(), still surfaced its dead Next next to a1cd0e8's live
one).

Decision already on record (git-memory, plugin/boot scope):
  "boot checks gh issue state for Next with #number (closed=skip), Next
  without issue use latest context() as cutoff"

Contract fixed here (extract_memory()'s pending list only — issue-state
filtering for #issue-tagged Next items is a SEPARATE, already-existing
path in lib/boot_render.py's check_issue_status()/_issue_matches_next(),
untouched by this contract):

  T_ctx := the timestamp of the MOST RECENT commit (within the same
  SCAN_DEPTH window extract_memory() already reads) whose subject, after
  stripping a leading emoji/whitespace prefix, starts with "context(".

  - Next WITHOUT #issue, commit timestamp >= T_ctx  -> INCLUDED.
  - Next WITHOUT #issue, commit timestamp <  T_ctx  -> EXCLUDED.
  - Next WITH #issue -> the cutoff never applies (issue-state governs it
    elsewhere); extract_memory() must keep returning it unconditionally.
  - No context() commit anywhere in the scanned window -> no cutoff at
    all, fail-open (today's unfiltered behavior, unchanged).
  - Tombstoning (Resolved-Next) is unrelated to and unaffected by the
    cutoff either way.

Build mode: test-first (ATDD contract pass). This file writes ONLY
tests, at acceptance granularity — no production code is touched. Some
tests below are expected RED today (the bug is present); a few are
explicit [GUARD] anchors for behavior that must NOT change once the fix
lands (marked in each docstring).

Fixture model (unmassk-standards §34 / this project's calibration: no
external attacker threat model applies here, only "the system must not
break itself" — see CLAUDE.md). Every commit is a REAL commit made with
real `git commit --allow-empty` against a real temp git repo, then
reread through the REAL extract_memory() function — no hand-typed dict
ever stands in for its output. Timestamps are pinned via
GIT_AUTHOR_DATE/GIT_COMMITTER_DATE (git's own raw "<epoch> <tz>" format)
so ordering is deterministic and independent of wall-clock test runtime,
using the same in-process
`monkeypatch.chdir(repo); import boot_memory; boot_memory.extract_memory()`
call pattern used throughout this suite for stably-named modules (no
subprocess spawn needed — git_helpers.run_git's cwd=None already inherits
the process cwd, which monkeypatch.chdir sets for the duration of the
test).
"""

import os
import sys

from conftest import LIB_DIR, git_cmd

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)


# ── Fixed base timestamp so ordering is deterministic, independent of ────
#    wall-clock test runtime. An arbitrary real-looking epoch (2023-11-14).
_BASE_TS = 1_700_000_000

EMOJIS = {
    "context": "\U0001F4BE",  # 💾 — matches this repo's own real convention
    "feat": "✨",         # ✨
    "wip": "\U0001F6A7",      # 🚧
    "chore": "\U0001F527",    # 🔧
}


# ── Repo / commit helpers ───────────────────────────────────────────────


def _make_repo(tmp_path, name="repo"):
    """Minimal git repo, no installer needed — extract_memory() only reads
    real git history via `git log`."""
    repo = str(tmp_path / name)
    os.makedirs(repo)
    git_cmd(["init"], repo)
    # Deliberately OLDER than every scenario commit below (_BASE_TS - 100)
    # so the init commit never accidentally becomes the "newest" commit in
    # a DAG where every other commit is pinned to an explicit, later ts.
    init_env = {
        "GIT_AUTHOR_DATE": f"{_BASE_TS - 100} +0000",
        "GIT_COMMITTER_DATE": f"{_BASE_TS - 100} +0000",
    }
    git_cmd(["commit", "--allow-empty", "-m", "init"], repo, env=init_env)
    return repo


def _commit_at(repo, kind, scope, message, ts, trailers=None):
    """Create a real commit with an explicit, controlled author timestamp.

    `ts` is a raw Unix epoch second, passed to GIT_AUTHOR_DATE/
    GIT_COMMITTER_DATE using git's own internal raw format ("<seconds>
    <tz>") — the exact value boot_memory.py's `git log
    --pretty=format:...%at...` reads back via %at, with no ISO-parsing
    ambiguity in either direction.
    """
    emoji = EMOJIS.get(kind, "\U0001F527")
    subject = f"{emoji} {kind}({scope}): {message}"
    body_lines = [f"{k}: {v}" for k, v in (trailers or {}).items()]
    msg = subject if not body_lines else subject + "\n\n" + "\n".join(body_lines)
    date_env = {"GIT_AUTHOR_DATE": f"{ts} +0000", "GIT_COMMITTER_DATE": f"{ts} +0000"}
    git_cmd(["commit", "--allow-empty", "-m", msg], repo, env=date_env)


def _extract(repo, monkeypatch):
    """Call the REAL extract_memory() in-process, cwd pointed at the test
    repo. Uses the same in-process monkeypatch.chdir() call pattern used
    throughout this suite for stably-named modules."""
    monkeypatch.chdir(repo)
    import boot_memory
    return boot_memory.extract_memory()


def _pending_texts(result):
    return {item["text"] for item in result["pending"]}


# ══════════════════════════════════════════════════════════════════════════
# Contract points 1-3 + 6 — single context() establishes T_ctx
# ══════════════════════════════════════════════════════════════════════════


class TestPendingNextCutoffSingleContext:
    """A single context() commit establishes T_ctx. A Next-without-issue
    commit strictly OLDER than T_ctx must be excluded; the Next carried by
    T_ctx's own commit (timestamp == T_ctx), and any Next strictly NEWER
    than T_ctx, must both be included.

    [ROJO] today: extract_memory() applies no cutoff at all — every Next
    up to MAX_PENDING is collected regardless of position relative to the
    last context(). The BEFORE_MARKER assertion below is the one that
    fails today (it currently DOES appear in pending — that is the bug).
    The other two assertions already pass today (nothing is filtered at
    all yet); they're asserted here as part of the same contract because
    they're the two cases that must NOT regress once the cutoff is added.
    """

    BEFORE_MARKER = "dead-next-before-context-c9a1"
    CTX_OWN_MARKER = "context-own-next-b7f2"
    AFTER_MARKER = "next-after-context-e4d8"

    def test_before_excluded_own_and_after_included(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        _commit_at(repo, "feat", "alpha", "old work item", _BASE_TS + 1000,
                   {"Next": self.BEFORE_MARKER})
        _commit_at(repo, "context", "root", "checkpoint", _BASE_TS + 2000,
                   {"Next": self.CTX_OWN_MARKER})
        _commit_at(repo, "wip", "beta", "continued after checkpoint", _BASE_TS + 3000,
                   {"Next": self.AFTER_MARKER})

        result = _extract(repo, monkeypatch)
        texts = _pending_texts(result)

        assert self.BEFORE_MARKER not in texts, (
            f"a Next without #issue OLDER than the last context() commit "
            f"must be excluded (dead, superseded). pending={result['pending']}"
        )
        assert self.CTX_OWN_MARKER in texts, (
            f"the Next carried by the last context() commit ITSELF must "
            f"appear (it IS the cutoff, not before it). pending={result['pending']}"
        )
        assert self.AFTER_MARKER in texts, (
            f"a Next without #issue NEWER than the last context() must "
            f"appear. pending={result['pending']}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Contract point 4 — the EXACT reported incident: two context() commits
# ══════════════════════════════════════════════════════════════════════════


class TestPendingNextCutoffTwoContexts:
    """Two context() commits in the scanned history. Only the NEWER one
    sets T_ctx; the OLDER context's own Next must be treated as dead
    (its timestamp is < T_ctx), the NEWER context's Next must survive.

    This is the exact incident shape (d6187db old context vs a1cd0e8
    new context).

    [ROJO] today: both Next markers appear side by side in pending — the
    old, dead one included alongside the current one is precisely the
    incident this contract fixes.
    """

    OLD_CTX_MARKER = "old-context-dead-next-a1f3"
    NEW_CTX_MARKER = "new-context-live-next-d6c8"

    def test_only_newest_context_next_survives(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        _commit_at(repo, "context", "roadmap", "old checkpoint", _BASE_TS + 1000,
                   {"Next": self.OLD_CTX_MARKER})
        _commit_at(repo, "chore", "docs", "unrelated filler", _BASE_TS + 2000)
        _commit_at(repo, "context", "roadmap", "new checkpoint", _BASE_TS + 3000,
                   {"Next": self.NEW_CTX_MARKER})

        result = _extract(repo, monkeypatch)
        texts = _pending_texts(result)

        assert self.OLD_CTX_MARKER not in texts, (
            f"the SUPERSEDED context's own Next must not resurface once a "
            f"newer context() exists. pending={result['pending']}"
        )
        assert self.NEW_CTX_MARKER in texts, (
            f"the current (newest) context's Next must be shown. "
            f"pending={result['pending']}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Contract point 5 — fail-open when no context() exists at all
# ══════════════════════════════════════════════════════════════════════════


class TestPendingNextCutoffNoContextFailOpen:
    """When there is no context() commit anywhere in the scanned window,
    the cutoff must never activate: every Next up to MAX_PENDING is
    collected, exactly as before this fix (fail-open, never fail-closed).

    [GUARD]: already passes today (nothing to filter yet) and MUST keep
    passing after Ultron's fix — pins the fail-open default so the new
    cutoff logic can never accidentally start rejecting Next items when
    no context() commit was ever found.
    """

    def test_all_next_included_when_no_context_commit_exists(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        markers = [f"no-context-next-{i}-f3a9" for i in range(3)]
        for i, marker in enumerate(markers):
            _commit_at(repo, "feat", f"scope{i}", f"work item {i}",
                       _BASE_TS + 1000 * (i + 1), {"Next": marker})

        result = _extract(repo, monkeypatch)
        texts = _pending_texts(result)

        assert result["last_context"] == "", (
            "setup sanity: this scenario must contain zero context() "
            f"commits. Got last_context={result['last_context']!r}"
        )
        for marker in markers:
            assert marker in texts, (
                f"with no context() commit anywhere in the scan window, "
                f"every Next must still be collected (fail-open, unchanged "
                f"behavior). Missing: {marker}. pending={result['pending']}"
            )


# ══════════════════════════════════════════════════════════════════════════
# Contract point 3 (bis) — #issue-tagged Next bypasses the cutoff entirely
# ══════════════════════════════════════════════════════════════════════════


class TestPendingNextCutoffIssueBypassesCutoff:
    """A Next WITH a #issue reference is governed by issue state
    (closed=skip), handled downstream in lib/boot_render.py's
    check_issue_status()/_issue_matches_next() — never by this cutoff.
    extract_memory() itself has no gh/issue-state awareness at all; it
    must keep returning an issue-tagged Next unconditionally, regardless
    of its position relative to the last context().

    [GUARD]: already passes today (no cutoff exists yet) and MUST keep
    passing after Ultron's fix — pins that the new cutoff only ever
    excludes Next items WITHOUT a #issue reference.
    """

    def test_issue_tagged_next_before_context_still_returned(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        _commit_at(repo, "feat", "gamma", "tracked work", _BASE_TS + 1000,
                   {"Next": "finish tracked work #79"})
        _commit_at(repo, "context", "root", "checkpoint", _BASE_TS + 2000)

        result = _extract(repo, monkeypatch)
        texts = _pending_texts(result)
        issue_item = next((i for i in result["pending"] if i.get("issue") == 79), None)

        assert issue_item is not None, (
            f"a Next carrying #79, OLDER than the last context(), must "
            f"still be returned by extract_memory() — the cutoff must "
            f"never apply to issue-tagged Next items. pending={result['pending']}"
        )
        assert "finish tracked work #79" in texts


# ══════════════════════════════════════════════════════════════════════════
# Contract point 5 (original list) — tombstoning is orthogonal to cutoff
# ══════════════════════════════════════════════════════════════════════════


class TestPendingNextCutoffTombstoneStillWins:
    """Tombstoning (Resolved-Next) is unrelated to, and unaffected by, the
    cutoff: a matching tombstone must still suppress a Next even when that
    Next's own timestamp is >= T_ctx (i.e. would otherwise survive the new
    cutoff).

    [GUARD]: pins that Ultron's cutoff implementation does not disturb the
    existing (already correct) tombstone check.
    """

    def test_tombstoned_next_after_context_still_excluded(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        marker = "tombstoned-next-after-ctx-77bd"
        _commit_at(repo, "context", "root", "checkpoint", _BASE_TS + 1000)
        _commit_at(repo, "feat", "delta", "work item", _BASE_TS + 2000,
                   {"Next": marker})
        _commit_at(repo, "chore", "gc", "retire it", _BASE_TS + 3000,
                   {"Resolved-Next": marker})

        result = _extract(repo, monkeypatch)
        texts = _pending_texts(result)

        assert marker not in texts, (
            f"a tombstoned Next must stay excluded even though it is "
            f"NEWER than the last context() — tombstoning is independent "
            f"of the cutoff. pending={result['pending']}"
        )


# ══════════════════════════════════════════════════════════════════════════
# Edge case — timestamp tie between a Next commit and the context() commit
# ══════════════════════════════════════════════════════════════════════════


class TestPendingNextCutoffTimestampTie:
    """Edge case: the contract is 'timestamp >= T_ctx' (a NUMERIC
    comparison), not 'chronologically/graph-position after the context
    commit'. A Next-without-issue commit sharing the EXACT SAME author
    timestamp as the context() commit, but positioned as its ANCESTOR
    (created first, older in the DAG — same wall-clock second, earlier in
    history), must still be INCLUDED under the letter of the '>=' rule.

    Not RED today for an interesting reason: extract_memory() applies no
    cutoff at all yet, so this "passes" today vacuously (nothing is
    excluded). Recorded here as an explicit boundary so the eventual fix
    doesn't get the comparison backwards (a naive strict '>' instead of
    '>=', or a graph-order check instead of a plain timestamp comparison,
    would wrongly exclude this commit even though it satisfies the
    documented rule).
    """

    def test_next_at_same_timestamp_as_context_ancestor_is_included(self, tmp_path, monkeypatch):
        repo = _make_repo(tmp_path)
        tie_ts = _BASE_TS + 5000
        marker = "tied-timestamp-next-91ae"
        _commit_at(repo, "feat", "epsilon", "ancestor at tie timestamp", tie_ts,
                   {"Next": marker})
        _commit_at(repo, "context", "root", "checkpoint at same instant", tie_ts)

        result = _extract(repo, monkeypatch)
        texts = _pending_texts(result)

        assert marker in texts, (
            f"a Next commit sharing the exact same author timestamp as "
            f"the last context() must be included under the '>= T_ctx' "
            f"rule, even though it is the context's ancestor. "
            f"pending={result['pending']}"
        )
