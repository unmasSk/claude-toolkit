"""
Acceptance contract for boot memory freshness (multi-machine) — ATDD /
test-first pass, BEFORE Ultron implements.

Issue #49. Plan: docs/plan/feat-boot-freshness.md.
Decisions (git-memory, not up for debate here):
  - 3d2f377 decision(plugin/boot): council verdict — hardened, gated,
    rate-limited fetch; visible freshness stamp; explicit behind signal
    with a pull proposal; read memory from origin when strictly ahead;
    warn-only guard on writes while behind.
  - d958659 decision: pull is proposed at BOOT time, not at session close.

Code under test (does NOT exist yet in the shape this contract expects):
  - hooks/session-start-boot.py:246 — currently `run_git(["fetch",
    "--quiet"], timeout=BOOT_FETCH_TIMEOUT)`, ungated, unhardened,
    unthrottled, no env override.
  - lib/boot_memory.py:extract_memory() — currently HEAD-only, no ref
    parameter, never reads origin/<branch>.
  - lib/boot_git_checks.py:render_branch_section() — already computes
    ahead/behind and prints "PULL RECOMMENDED" (unchanged pre-existing
    behavior; this contract expects it escalated to a full directive).
  - bin/git-memory-commit.py — currently zero behind-check on any memory
    commit.

Build mode: test-first (ATDD contract pass, before Ultron). This is
ACCEPTANCE granularity — the 8 behaviors that define "done" per the plan
— not the exhaustive branch/line suite. The EXHAUSTION PROTOCOL hardening
pass runs AFTER Ultron implements (Flow Verify step), against the real
code.

Fixture model (Task 1 instructions, unmassk-standards §34 — no fabricated
ground truth): mirrors tests/test_release.py::_setup_release_repo (bare
remote + clone triangulation) and its TestPreflightBehindRemote (second
clone pushes -> first clone is behind). Machine B (a second clone) creates
REAL memory commits (emoji + type(scope): message + Next:/Decision:
trailers, the exact format lib/parsing.py's scan_trailers_memory() and
bin/git-memory-commit.py's build_commit_message() produce) with plain
`git commit -m` — the commit-validation hooks never run inside these
temp repos, so there is no wrapper to invoke. Every expected string this
file asserts on is either a marker THIS test itself wrote into B (and
therefore derives from the same variable/constant used to write it, never
a second hand-typed literal) or a behavior contract quoted directly from
the plan.

NO production code is touched by this file. Only tests.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

import pytest

from conftest import HOOKS_DIR, BIN_DIR, INSTALL, LIB_DIR, run_script, write_file

if LIB_DIR not in sys.path:
    sys.path.insert(0, LIB_DIR)

from boot_git_checks import FETCH_TIMEOUT_SECONDS  # decision b2a32b9: 3s -> 10s

BOOT_HOOK = os.path.join(HOOKS_DIR, "session-start-boot.py")
COMMIT_SCRIPT = os.path.join(BIN_DIR, "git-memory-commit.py")

WINDOWS = sys.platform == "win32"

# ── Constants shared by multiple tests ──────────────────────────────────

COMMITS_BEHIND_INCIDENT = 12          # Task 1 test 1 — the reported incident's exact scale
# Deliberately does NOT contain "remote"/"local"/etc. — those substrings are
# reserved for asserting on a provenance LABEL Ultron adds, never on the
# marker's own name (a marker like "...REMOTE-NEXT..." would make a
# `re.search(r"remot", line)` check pass vacuously on the marker's own text
# instead of on a genuine new label).
INCIDENT_NEXT_MARKER = "INCIDENT-NEXT-9f31a2"
PULL_DIRECTIVE_BEHIND_COUNT = 3
RATE_LIMIT_WINDOW_SECONDS = 300       # plan: FETCH_HEAD mtime < 300s -> skip

EMOJIS = {"context": "\U0001F4BE", "decision": "\U0001F9ED", "memo": "\U0001F4CC", "remember": "\U0001F9E0"}


# ── Git helpers (mirrors tests/test_release.py::_git) ───────────────────


def _git(args, cwd, check=True, env=None):
    """Run a git command in cwd. Returns CompletedProcess."""
    merged_env = {**os.environ, **(env or {})}
    return subprocess.run(
        ["git"] + args,
        cwd=cwd,
        capture_output=True,
        text=True, encoding='utf-8', errors='replace',
        env=merged_env,
        check=check,
    )


def _commit_real(repo, type_, scope, message, trailers=None):
    """Create a commit using the REAL emoji + type(scope): message format
    that lib/parsing.py's scan_trailers_memory() / lib/boot_memory.py's
    extract_memory() parse — matches bin/git-memory-commit.py's
    build_commit_message() output shape. Hooks are bypassed in test repos
    (established pattern, see tests/conftest.py::check_hook_msg's own
    docstring note and tests/test_crown.py::_commit), so a direct
    `git commit --allow-empty -m` is used instead of the wrapper script.
    """
    subject = f"{EMOJIS[type_]} {type_}({scope}): {message}"
    body_lines = [f"{k}: {v}" for k, v in (trailers or {}).items()]
    msg = subject if not body_lines else subject + "\n\n" + "\n".join(body_lines)
    _git(["commit", "--allow-empty", "-m", msg], repo)


def _push_commits_from_b(repo_b, count, next_marker=None, scope="freshness"):
    """Push `count` commits from machine B to the shared bare remote.

    If next_marker is given, the LAST of the `count` commits is a real
    context() commit carrying `Next: {next_marker}` — the newest resume
    item on the remote side (Task 1 tests 1 and 7).
    """
    for i in range(count):
        if next_marker is not None and i == count - 1:
            # Subject deliberately avoids "remote"/"local"/"behind"/"pull" —
            # those words are reserved for asserting on labels the FEATURE
            # adds, never for an accidental echo of an unrelated commit
            # subject that happens to land on a nearby rendered line.
            _commit_real(repo_b, "context", scope, f"sync update {i}", {"Next": next_marker})
        else:
            _git(["commit", "--allow-empty", "-m", f"chore: filler commit {i}"], repo_b)
    _git(["push", "origin", "main"], repo_b)


def _setup_freshness_repo(tmp_path):
    """Machine A: git repo + bare remote configured as `origin`, toolkit
    memory installed (CLAUDE.md marker + manifest.json) and committed so
    the fetch gate passes AND the tree starts clean — every test that
    isn't specifically about the gate itself (test 5 builds its own
    uninstalled repo) or about a dirty tree (test 3's dirty variant adds
    one on top) relies on this baseline.

    Returns (repo_a, bare).
    """
    repo_a = str(tmp_path / "repo_a")
    bare = str(tmp_path / "bare.git")
    os.makedirs(repo_a)

    _git(["init", "-b", "main"], repo_a)
    _git(["config", "user.email", "a@test.com"], repo_a)
    _git(["config", "user.name", "Machine A"], repo_a)
    _git(["commit", "--allow-empty", "-m", "init"], repo_a)

    subprocess.run(["git", "init", "--bare", "-b", "main", bare], capture_output=True, check=True)
    _git(["remote", "add", "origin", bare], repo_a)
    _git(["push", "-u", "origin", "main"], repo_a)

    install_rc, install_out, install_err = run_script(INSTALL, repo_a, ["--auto"])
    assert install_rc == 0, f"install --auto failed: {install_out}\n{install_err}"

    # Commit the install-generated tracked files (CLAUDE.md, .gitignore)
    # so the tree starts CLEAN — install does not auto-commit, and a
    # freshly-installed-but-uncommitted repo would make every "clean
    # tree" test below start dirty for the wrong reason.
    status = _git(["status", "--porcelain"], repo_a, check=False)
    if status.stdout.strip():
        _git(["add", "-A"], repo_a)
        _git(["commit", "-m", "chore: install unmassk-toolkit memory"], repo_a)
        _git(["push", "origin", "main"], repo_a)

    return repo_a, bare


def _clone_machine_b(bare, tmp_path, name="repo_b"):
    """Clone a second machine (B) from the CURRENT state of the shared
    bare remote. Call this AFTER any machine-A-only setup has already
    been pushed, so B starts in sync and its own pushes stay fast-forward.
    """
    repo_b = str(tmp_path / name)
    _git(["clone", bare, repo_b], str(tmp_path))
    _git(["config", "user.email", "b@test.com"], repo_b)
    _git(["config", "user.name", "Machine B"], repo_b)
    return repo_b


# ── Boot invocation + boot-log helpers (mirrors tests/test_boot_output.py) ──


def _boot_log_path(repo):
    return os.path.join(repo, ".claude", ".unmassk", "boot-log-latest.txt")


def _read_boot_log(repo):
    try:
        with open(_boot_log_path(repo), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


def _run_boot(repo, env=None, timeout=30):
    return run_script(BOOT_HOOK, repo, env=env, timeout=timeout)


def _run_boot_combined(repo, env=None, timeout=30):
    """Run the boot hook and return (rc, stdout, stderr, boot_log, combined).

    combined = stdout + boot_log, since the freshness stamp is specified
    to land in "stdout banner y/o boot-log" (plan Task 1 test 2) and the
    RESUME/Next content lives exclusively in the boot-log file per the
    already-shipped unconditional-banner contract.
    """
    rc, stdout, stderr = _run_boot(repo, env=env, timeout=timeout)
    log_content = _read_boot_log(repo)
    combined = stdout + "\n" + log_content
    return rc, stdout, stderr, log_content, combined


def _line_with(text, marker):
    for line in text.splitlines():
        if marker in line:
            return line
    return None


# ── Fake `git` executable (Task 1 tests 4 and 5) ────────────────────────
#
# Logs every invocation (argv + full env) to a JSONL file, then passes
# through to the REAL git for everything except `fetch`, so the rest of
# the boot pipeline (rev-parse, log, branch, status, doctor's own git
# calls) keeps working unmodified. `fetch` calls can additionally be made
# to hang for FAKE_GIT_FETCH_HANG_SECONDS, to exercise a timeout without
# depending on real network behavior (sandboxed test environments may not
# allow arbitrary outbound sockets, even to a dead port). POSIX only —
# Windows does not resolve a bare extensionless `git` file as executable
# via PATH lookup the way `subprocess.run(["git", ...])` needs here.

_FAKE_GIT_TEMPLATE = '''#!/usr/bin/env python3
import sys, os, json, subprocess, time

args = sys.argv[1:]
log_path = r"""__LOG_PATH__"""
try:
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"args": args, "env": dict(os.environ)}) + "\\n")
except OSError:
    pass

if args and args[0] == "fetch":
    hang = os.environ.get("FAKE_GIT_FETCH_HANG_SECONDS")
    if hang:
        time.sleep(float(hang))
        sys.exit(0)

real_git = r"""__REAL_GIT__"""
result = subprocess.run([real_git] + args)
sys.exit(result.returncode)
'''


def _make_fake_git(tmp_path, log_path):
    real_git = shutil.which("git")
    assert real_git, "real git binary not found on PATH — cannot build fake git wrapper"
    fake_dir = tmp_path / "fake_bin"
    fake_dir.mkdir(exist_ok=True)
    fake_git_path = fake_dir / "git"
    script = (
        _FAKE_GIT_TEMPLATE
        .replace("__LOG_PATH__", str(log_path))
        .replace("__REAL_GIT__", real_git)
    )
    fake_git_path.write_text(script, encoding="utf-8")
    os.chmod(fake_git_path, 0o755)
    return str(fake_dir)


def _read_fake_git_log(log_path):
    if not os.path.isfile(log_path):
        return []
    records = []
    with open(log_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                records.append(json.loads(line))
    return records


# ── Test 1: incident reproduction (the fix criterion) ───────────────────


class TestIncidentBehindShowsRemoteNext:
    """Plan Task 1 test 1 — incident reproduction / fix criterion.

    Clone A ends up 12 commits strictly behind the shared remote (machine
    B pushed 12, the last a real context() commit with a brand-new Next:
    trailer). The fix criterion: A's boot must (a) signal it is behind,
    AND (b) show B's newest Next as the RESUME/Next item, labeled with
    remote provenance — not A's own stale local Next.

    RED today: lib/boot_memory.py's extract_memory() has no ref
    parameter and only ever reads local HEAD, so it can never see B's
    commits at all (they only exist on origin/main, not on A's branch).
    """

    def test_behind_boot_shows_remote_next_labeled(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)

        local_next = "A-OWN-STALE-NEXT-MARKER"
        _commit_real(repo_a, "context", "freshness", "a's own last update", {"Next": local_next})
        _git(["push", "origin", "main"], repo_a)

        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, COMMITS_BEHIND_INCIDENT, next_marker=INCIDENT_NEXT_MARKER)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"boot must never fail the session. stderr: {stderr}"

        # (a) behind signal — the count is derived from the same constant
        # used to create the commits, not a second hand-typed literal.
        assert re.search(rf"\b{COMMITS_BEHIND_INCIDENT}\b", combined), (
            f"expected the behind count ({COMMITS_BEHIND_INCIDENT}) to appear "
            f"somewhere in the boot output.\n{combined}"
        )

        # (b) the fix criterion — B's newest Next, labeled remote.
        next_line = _line_with(combined, INCIDENT_NEXT_MARKER)
        assert next_line is not None, (
            "Expected the remote's newest Next (from B's context() commit) "
            f"to appear in the boot output. Got:\n{combined}"
        )
        assert re.search(r"remot", next_line, re.IGNORECASE), (
            "Expected the remote Next line to carry a remote-provenance "
            f"label (e.g. '[source: remote]'). Got line: {next_line!r}"
        )


# ── Test 2: freshness stamp in all three states ─────────────────────────


class TestFreshnessStampThreeStates:
    """Plan Task 1 test 2 — the MEMORY: freshness stamp must appear in the
    header (stdout banner and/or boot-log) in all three states: fresh
    fetch, rate-limited (still fresh — memory synced within the last 5min,
    fetch was simply skipped because it wasn't needed), and fetch-failed
    (falls back to "LOCAL ... unverified").

    Bex (issue #49 repair round): the stamp's wording was decided to be
    English (matching the rest of the boot banner) — was "MEMORIA:"/"sin
    verificar"/"omitido" (Spanish) when this file was first written,
    mechanically updated here to match the just-made language decision.

    Issue #60 (decision ceef426): the rate-limited variant was originally
    labeled "MEMORY: LOCAL — fetch skipped (rate-limit, ... ago)" — reading
    as a failure when it is actually the GOOD case (FETCH_HEAD < 300s old,
    memory confirmed fresh, a real fetch just wasn't needed). Relabeled to
    "MEMORY: remote (synced ... ago)" — "remote" (not "LOCAL"), no more
    "skipped". `test_rate_limited_state_shows_stamp` below asserts the new
    wording precisely, on the real MEMORY: line only (not a loose substring
    search over the whole combined output, which would also match text
    elsewhere in the banner).
    """

    def test_fresh_fetch_state_shows_stamp(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert "MEMORY:" in combined, f"expected a MEMORY: freshness stamp.\n{combined}"

    def test_rate_limited_state_shows_remote_synced_stamp_not_local(self, tmp_path):
        """Issue #60: rate-limited is the GOOD case (FETCH_HEAD < 300s old,
        memory already confirmed fresh this window) — the stamp must read
        "MEMORY: remote (synced {age} ago)" and must NOT contain "LOCAL" or
        "skipped" anywhere on that line. Real subprocess channel (§34): runs
        the actual hooks/session-start-boot.py hook twice over a real git
        repo, reading the real boot-log-latest.txt — no literal copied from
        today's output, the exact wording is quoted from the plan/decision
        (ceef426) as the target contract, not derived by running the
        unmodified code.
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)

        # First boot performs a real fetch, leaving .git/FETCH_HEAD with a
        # fresh mtime. The very next boot, still inside the rate-limit
        # window, must report the rate-limited (fresh, "remote") variant of
        # the stamp — not fall back to a "fetched" or "LOCAL" line.
        _run_boot(repo_a)
        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        memory_line = _line_with(combined, "MEMORY:")
        assert memory_line is not None, f"expected a MEMORY: freshness stamp.\n{combined}"
        assert memory_line.startswith("MEMORY: remote (synced "), (
            f"expected the rate-limited stamp to read 'MEMORY: remote (synced "
            f"... ago)', got: {memory_line!r}"
        )
        assert "LOCAL" not in memory_line, (
            f"rate-limited (fresh) memory must never be labeled LOCAL: {memory_line!r}"
        )
        assert "skipped" not in memory_line, (
            f"rate-limited (fresh) memory must never say 'skipped' (reads as "
            f"failure): {memory_line!r}"
        )

        # The original bug (issue #60): SessionStart can fire multiple boots
        # per session, and the LAST boot's output is what persists to disk in
        # boot-log-latest.txt — so the persisted FILE, not just this process's
        # stdout, is what a human or another tool actually reads afterward.
        # Assert directly against log_content (the file's contents), not just
        # the stdout+log "combined" blob, to pin that the second (rate-
        # limited) boot's persisted file itself carries the good label.
        log_memory_line = _line_with(log_content, "MEMORY:")
        assert log_memory_line is not None, (
            f"expected a MEMORY: freshness stamp in the persisted boot-log "
            f"file itself.\n{log_content}"
        )
        assert log_memory_line.startswith("MEMORY: remote (synced "), (
            f"expected the persisted boot-log-latest.txt to carry the "
            f"rate-limited 'MEMORY: remote (synced ... ago)' stamp after the "
            f"second boot, got: {log_memory_line!r}"
        )
        assert "LOCAL" not in log_memory_line and "skipped" not in log_memory_line, (
            f"persisted boot-log-latest.txt must never show the rate-limited "
            f"(fresh) state as LOCAL/skipped: {log_memory_line!r}"
        )

    def test_fetch_failed_state_shows_local_unverified(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)

        # Point origin at a path that does not exist — git fetch fails
        # outright, deterministically, with no network dependency at all.
        _git(["remote", "set-url", "origin", str(tmp_path / "does-not-exist.git")], repo_a)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a, timeout=20)

        assert rc == 0, f"boot must fail open even when fetch fails outright. stderr: {stderr}"
        assert "MEMORY:" in combined, f"expected a MEMORY: freshness stamp.\n{combined}"
        assert "LOCAL" in combined and re.search(r"unverified", combined, re.IGNORECASE), (
            f"expected 'LOCAL ... unverified' when fetch fails outright.\n{combined}"
        )


# ── Hardening (issue #60): rate-limit seam is robust to a remote that ────
#    breaks BETWEEN two real boots ───────────────────────────────────────


class TestRateLimitedStampSurvivesRemoteBreakage:
    """Hardening pass, issue #60 (docs/plan/fix-boot-memory-stamp.md, Task
    3). The relabel's whole design argument (decision ceef426's
    "refinamiento de diseño") is that "no pisar estado mas fresco" is
    satisfied FOR FREE by the rate-limit gate itself:
    `_fetch_gate_and_rate_limit` (lib/boot_git_checks.py) short-circuits on
    FETCH_HEAD's measured age alone, BEFORE ever resolving or touching the
    remote — so a rate-limited stamp can never be contaminated by the
    remote's CURRENT health. These two tests exercise that seam for real,
    through the actual boot subprocess (not fetch_memory_ref()'s dict in
    isolation — that's already covered directly in
    test_boot_freshness_hardening.py) — a real fetch succeeds, the remote
    THEN breaks, and a second real boot runs both inside and past the
    300s rate-limit window, reading the persisted boot-log-latest.txt FILE
    (not just stdout) each time — the same file whose staleness was the
    original issue #60 bug shape.
    """

    def _seed_good_fetch_then_break_remote(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)

        first_rc, _first_out, first_err = _run_boot(repo_a)
        assert first_rc == 0, f"first (real-fetch) boot must succeed. stderr: {first_err}"
        fetch_head = os.path.join(repo_a, ".git", "FETCH_HEAD")
        assert os.path.isfile(fetch_head), (
            "first boot must have performed a real, successful fetch — "
            "FETCH_HEAD is the seam the rate-limit gate reads"
        )

        _git(["remote", "set-url", "origin", str(tmp_path / "does-not-exist.git")], repo_a)
        return repo_a, fetch_head

    def test_within_window_broken_remote_still_shows_synced_not_fetched(self, tmp_path):
        """Fetch OK, remote breaks, second boot lands INSIDE the 300s
        window: the stamp must still read "remote (synced ... ago)"
        (truthful — a sync really did happen Ns ago) and must never say
        "fetched" (no new fetch is attempted at all — the gate
        short-circuits before the broken remote is ever resolved) nor fall
        back to "LOCAL".
        """
        repo_a, _fetch_head = self._seed_good_fetch_then_break_remote(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)
        assert rc == 0, f"boot must fail open. stderr: {stderr}"

        memory_line = _line_with(combined, "MEMORY:")
        assert memory_line is not None, f"expected a MEMORY: stamp.\n{combined}"
        assert memory_line.startswith("MEMORY: remote (synced "), (
            f"expected the still-fresh (rate-limited) stamp despite the "
            f"remote breaking after the sync. Got: {memory_line!r}"
        )
        assert "fetched" not in memory_line, (
            f"no new fetch should have been attempted at all (the gate "
            f"short-circuits on FETCH_HEAD age before touching the "
            f"remote) — 'fetched' must not appear. Got: {memory_line!r}"
        )
        assert "LOCAL" not in memory_line and "skipped" not in memory_line, (
            f"a rate-limited (still-fresh) sync must never be labeled "
            f"LOCAL/skipped, regardless of the remote's current health: "
            f"{memory_line!r}"
        )

        # Persisted-file channel (issue #60's original bug shape): the same
        # assertions against the FILE boot-log-latest.txt actually wrote,
        # not just this process's stdout.
        log_memory_line = _line_with(log_content, "MEMORY:")
        assert log_memory_line is not None, (
            f"expected a MEMORY: stamp in boot-log-latest.txt.\n{log_content}"
        )
        assert log_memory_line.startswith("MEMORY: remote (synced "), (
            f"expected the persisted boot-log to carry the same "
            f"rate-limited stamp. Got: {log_memory_line!r}"
        )
        assert "LOCAL" not in log_memory_line and "skipped" not in log_memory_line, (
            f"persisted boot-log-latest.txt must never show the "
            f"rate-limited (still-fresh) state as LOCAL/skipped: "
            f"{log_memory_line!r}"
        )

    def test_past_window_broken_remote_reverts_to_local_unverified_with_age(self, tmp_path):
        """Same setup, but the second boot lands PAST the 300s rate-limit
        window — a real refetch IS attempted this time, fails against the
        now-broken remote, and the stamp must honestly fall back to
        "LOCAL ... unverified", still carrying the age of the LAST
        successful sync (never "remote", and never the "never synced with
        origin" wording, which is reserved for a repo that has never once
        fetched successfully — this repo HAD a good fetch before the
        remote broke). Checked on both channels: stdout+log combined AND
        the persisted boot-log-latest.txt FILE alone.

        v1->v2 RE-BASE (issue #60 AMENDMENT v2, decision 90d096d): the
        "age evidence" aged past the window is now the boot's own success
        stamp (`.claude/.unmassk/boot-fetch-stamp.json`), not
        .git/FETCH_HEAD — only the seeding mechanic (which file os.utime()
        targets) changed; the remote (still named "origin", only its URL
        breaks) is unchanged between the seeding fetch and the second boot,
        so the stamp's remote/branch identity still matches and its age is
        genuinely preserved and reported, exactly as this test's semantic
        assertion (LOCAL/unverified with the LAST-known age, not "never
        synced") already required.
        """
        repo_a, _fetch_head = self._seed_good_fetch_then_break_remote(tmp_path)

        stamp_path = os.path.join(repo_a, ".claude", ".unmassk", "boot-fetch-stamp.json")
        assert os.path.isfile(stamp_path), (
            "setup sanity: the seeding boot's real successful fetch must "
            "have written the own-success stamp"
        )
        stale_time = time.time() - (RATE_LIMIT_WINDOW_SECONDS + 300)
        os.utime(stamp_path, (stale_time, stale_time))

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a, timeout=20)
        assert rc == 0, f"boot must fail open even when the refetch fails. stderr: {stderr}"

        memory_line = _line_with(combined, "MEMORY:")
        assert memory_line is not None, f"expected a MEMORY: stamp.\n{combined}"
        assert memory_line.startswith("MEMORY: LOCAL — last fetch "), (
            f"expected the post-window refetch failure to fall back to "
            f"the age-known LOCAL/unverified wording, not stay 'remote' "
            f"or claim 'never synced'. Got: {memory_line!r}"
        )
        assert memory_line.endswith("ago, unverified"), f"Got: {memory_line!r}"
        assert "remote (" not in memory_line, (
            f"a failed post-window refetch must never claim 'remote': {memory_line!r}"
        )

        log_memory_line = _line_with(log_content, "MEMORY:")
        assert log_memory_line is not None, (
            f"expected the persisted boot-log-latest.txt to carry a "
            f"MEMORY: stamp.\n{log_content}"
        )
        assert (
            log_memory_line.startswith("MEMORY: LOCAL — last fetch ")
            and log_memory_line.endswith("ago, unverified")
        ), (
            f"persisted boot-log-latest.txt must show the honest "
            f"LOCAL/unverified fallback after a real remote-broken "
            f"refetch attempt, not a stale 'remote (synced...)' stamp "
            f"from before the remote broke. Got: {log_memory_line!r}"
        )


# ── Issue #60 AMENDMENT v2 (decision 90d096d): own success stamp, not ───
#    .git/FETCH_HEAD's mtime, must be the freshness signal ──────────────


class TestOwnSuccessStampNotFetchHeadMtime:
    """Plan Task 6 (docs/plan/fix-boot-memory-stamp.md, AMENDMENT v2).

    Moriarty broke the v1 relabel (which stays valid and untouched — see
    TestFreshnessStampThreeStates / TestRateLimitedStampSurvivesRemoteBreakage
    above): the SOURCE of the freshness signal was always
    `.git/FETCH_HEAD`'s mtime, and that file is touched by things that are
    NOT "this project's own memory was just confirmed fresh":

    (A) a FAILED fetch attempt also truncates FETCH_HEAD to 0 bytes and
        refreshes its mtime — real, confirmed git behavior (verified
        empirically against a live nonexistent-path remote before writing
        this test: `git fetch` against a bogus URL exits 128 but still
        creates/truncates FETCH_HEAD with a fresh mtime, even on a repo
        that has never had a single successful fetch before).
    (B) a successful fetch to a totally UNRELATED remote touches the same
        file — FETCH_HEAD is not per-remote.

    Decision v2: the boot now writes its OWN success stamp (location is
    Ultron's implementation choice, per the task instructions — these tests
    assert only OBSERVABLE BEHAVIOR through the real boot subprocess
    channel: what the MEMORY: line says, and whether a real `git fetch` was
    actually attempted, never the stamp file's own name/format/location).
    `_fetch_gate_and_rate_limit` and the rendered stamp must read THAT
    stamp; no stamp, or a stale one, must always fall through to a real
    fetch attempt (fail-open toward fetching, per the plan).

    Real subprocess channel throughout (§34) — every assertion runs the
    actual hooks/session-start-boot.py hook over a real git repo with a
    real bare remote, mirroring TestRateLimitedStampSurvivesRemoteBreakage's
    own fixture style. Expected strings are quoted from the plan's
    contract, never captured from today's (buggy) output.
    """

    def test_vector_a_failed_fetch_never_falsely_rate_limits_next_boot(self, tmp_path):
        """Vector A. Origin is broken BEFORE boot #1 ever runs — this repo
        has never once had a successful fetch. Boot #1: the fetch fails,
        correctly showing LOCAL/unverified (already passes today, sanity
        checked below). Boot #2, immediately after (well inside the 300s
        window): the FAILED fetch in boot #1 already refreshed
        `.git/FETCH_HEAD`'s mtime (see class docstring, point A). Today's
        mtime-sourced gate reads that as fresh and rate-limits — WITHOUT
        ever retrying the fetch — falsely rendering "MEMORY: remote (synced
        ...)" for a remote that has never once been reached. Fixed
        behavior: no own success stamp exists (boot #1's fetch failed, so
        nothing was stamped) -> the gate must not rate-limit -> boot #2
        must retry the fetch for real (it fails again, same broken remote)
        -> LOCAL/unverified again. The retry itself is verified via a fake
        `git` on PATH (installed only for boot #2, so boot #1 runs against
        real, unmodified git) that logs every invocation.
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)
        _git(["remote", "set-url", "origin", str(tmp_path / "does-not-exist.git")], repo_a)

        # Boot #1 — real, unmodified git, no fake wrapper. Already passes
        # today; this is a setup-sanity check, not the RED assertion.
        rc1, stdout1, stderr1, log1, combined1 = _run_boot_combined(repo_a, timeout=20)
        assert rc1 == 0, f"boot must fail open. stderr: {stderr1}"
        memory_line1 = _line_with(combined1, "MEMORY:")
        assert memory_line1 is not None, f"expected a MEMORY: stamp.\n{combined1}"
        assert memory_line1.startswith("MEMORY: LOCAL") and re.search(
            r"unverified", memory_line1, re.IGNORECASE
        ), (
            f"setup sanity: boot #1 (origin broken from the start, never "
            f"fetched) must show LOCAL/unverified. Got: {memory_line1!r}"
        )

        fetch_head = os.path.join(repo_a, ".git", "FETCH_HEAD")
        assert os.path.isfile(fetch_head), (
            "setup sanity: the failed fetch attempt must still have "
            "created FETCH_HEAD — this is the exact seam the bug lives in"
        )

        # Boot #2, immediately after (well inside the 300s window). Fake
        # git installed now only, to count fetch attempts without touching
        # boot #1's already-real behavior above.
        log_path = str(tmp_path / "fake_git_vector_a.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}

        rc2, stdout2, stderr2 = run_script(BOOT_HOOK, repo_a, env=env, timeout=20)
        log_content2 = _read_boot_log(repo_a)
        combined2 = stdout2 + "\n" + log_content2
        assert rc2 == 0, f"boot must fail open. stderr: {stderr2}"

        memory_line2 = _line_with(combined2, "MEMORY:")
        assert memory_line2 is not None, f"expected a MEMORY: stamp.\n{combined2}"
        assert "remote (synced" not in memory_line2, (
            f"a remote that has NEVER been successfully fetched must never "
            f"be rendered as 'synced', even immediately after a failed "
            f"fetch attempt refreshed .git/FETCH_HEAD's mtime. "
            f"Got: {memory_line2!r}"
        )
        assert memory_line2.startswith("MEMORY: LOCAL") and re.search(
            r"unverified", memory_line2, re.IGNORECASE
        ), f"expected LOCAL/unverified. Got: {memory_line2!r}"

        records = _read_fake_git_log(log_path)
        fetch_calls = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert fetch_calls, (
            "a failed fetch must never rate-limit the NEXT boot's retry — "
            "expected boot #2 to attempt its own fetch again, but no "
            "fetch call was observed at all"
        )

    def test_vector_b_unrelated_remote_fetch_never_falsely_rate_limits(self, tmp_path):
        """Vector B. Origin is alive but has never been fetched by the
        boot's own logic yet. A SEPARATE, unrelated remote ("secondary") is
        fetched directly with real git — bypassing the hook entirely —
        immediately before boot #1 runs. That fetch is real and
        successful, and it touches the SAME `.git/FETCH_HEAD` file
        origin's own fetch would use (FETCH_HEAD is not per-remote): the
        mtime-sourced gate reads that ambient touch as "this project's
        memory is fresh" without ever having reached origin at all. Fixed
        behavior: the own success stamp only exists after a fetch that
        targets THIS project's actual upstream (origin) succeeds — a
        foreign remote's fetch must never satisfy it, so boot #1 must still
        perform a real fetch of origin (verified via the fake-git call
        log), ending in status "fetched" (never the false "synced").
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)

        secondary_bare = str(tmp_path / "secondary.git")
        subprocess.run(["git", "init", "--bare", "-b", "main", secondary_bare], capture_output=True, check=True)
        secondary_seed = str(tmp_path / "secondary_seed")
        _git(["clone", secondary_bare, secondary_seed], str(tmp_path))
        _git(["config", "user.email", "sec@test.com"], secondary_seed)
        _git(["config", "user.name", "Secondary"], secondary_seed)
        _git(["commit", "--allow-empty", "-m", "unrelated secondary content"], secondary_seed)
        _git(["push", "origin", "main"], secondary_seed)

        _git(["remote", "add", "secondary", secondary_bare], repo_a)
        _git(["fetch", "secondary"], repo_a)  # real, successful, unrelated to origin

        fetch_head = os.path.join(repo_a, ".git", "FETCH_HEAD")
        assert os.path.isfile(fetch_head), "setup sanity: the secondary fetch must have touched FETCH_HEAD"

        log_path = str(tmp_path / "fake_git_vector_b.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}

        rc, stdout, stderr = run_script(BOOT_HOOK, repo_a, env=env, timeout=20)
        log_content = _read_boot_log(repo_a)
        combined = stdout + "\n" + log_content
        assert rc == 0, f"stderr: {stderr}"

        memory_line = _line_with(combined, "MEMORY:")
        assert memory_line is not None, f"expected a MEMORY: stamp.\n{combined}"
        assert "remote (synced" not in memory_line, (
            f"a foreign remote's own successful fetch must never be read "
            f"as THIS project's upstream being in sync — boot must "
            f"attempt its own fetch of origin. Got: {memory_line!r}"
        )
        assert memory_line.startswith("MEMORY: remote (fetched "), (
            f"expected boot to perform a genuine new fetch of its OWN "
            f"upstream (origin) and report 'fetched', not silently trust "
            f"the secondary remote's touch. Got: {memory_line!r}"
        )

        records = _read_fake_git_log(log_path)
        fetch_calls = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert fetch_calls, (
            "expected boot to attempt a real fetch of its own upstream "
            "despite FETCH_HEAD already being fresh from the unrelated "
            "secondary fetch"
        )
        origin_fetch_calls = [r for r in fetch_calls if len(r["args"]) > 1 and r["args"][1] == "origin"]
        assert origin_fetch_calls, (
            f"expected the fetch to target 'origin' (this project's real "
            f"upstream), not skip fetching entirely. All fetch calls: {fetch_calls}"
        )

    def test_vector_d_migration_external_origin_fetch_without_own_stamp_still_fetches(self, tmp_path):
        """Vector D (migration). Simulates upgrading a repo that pre-dates
        the v2 own-success-stamp mechanism: `.git/FETCH_HEAD` is fresh
        because of an EXTERNAL fetch against the SAME upstream (origin)
        that happened outside of — and before — the new hook's own
        stamp-writing logic ever ran (e.g. the old ungated v1 boot, an IDE
        auto-fetch, or a plain `git fetch` done by hand). No own stamp file
        exists yet anywhere. The fix must not treat "FETCH_HEAD happens to
        be fresh" as proof that its OWN gated/hardened fetch already ran —
        it must still perform a real fetch of its own before it can
        honestly claim "synced"/"fetched" (verified via the fetch call
        log, not inferred from wording alone).

        Distinguishing detail vs Vector B: here the SAME remote (origin) is
        the one externally touched, not an unrelated secondary — this
        proves the fix keys off "does the own-stamp file exist", not off
        "was a different remote name involved". If Ultron's real
        implementation makes this indistinguishable in practice from
        Vector B (e.g. both collapse to the exact same code path with no
        remote-name branching at all), that is expected and fine — the two
        tests together are what pin the invariant from both angles.
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)

        # External fetch against origin itself, done directly (not via the
        # hook) — simulates a pre-v2 install/upgrade or an IDE auto-fetch.
        _git(["fetch", "origin"], repo_a)
        fetch_head = os.path.join(repo_a, ".git", "FETCH_HEAD")
        assert os.path.isfile(fetch_head), "setup sanity: external fetch must have touched FETCH_HEAD"

        log_path = str(tmp_path / "fake_git_vector_d.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}

        rc, stdout, stderr = run_script(BOOT_HOOK, repo_a, env=env, timeout=20)
        log_content = _read_boot_log(repo_a)
        combined = stdout + "\n" + log_content
        assert rc == 0, f"stderr: {stderr}"

        memory_line = _line_with(combined, "MEMORY:")
        assert memory_line is not None, f"expected a MEMORY: stamp.\n{combined}"
        assert "remote (synced" not in memory_line, (
            f"a repo migrating from before the own-stamp mechanism existed "
            f"must never trust an externally-fresh FETCH_HEAD as proof of "
            f"its OWN successful fetch. Got: {memory_line!r}"
        )

        records = _read_fake_git_log(log_path)
        fetch_calls = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert fetch_calls, (
            "expected the first boot after migration to attempt its own "
            "real fetch, not skip it because FETCH_HEAD was already fresh "
            "from an external/legacy fetch"
        )

    def test_round_trip_own_stamp_survives_fetch_head_deletion(self, tmp_path):
        """Discriminant round-trip variant (combines with Vector A/B/D
        above to pin the full contract — the plain "boot OK, boot again
        inside the window -> synced" round trip already passes today via
        the WRONG mechanism, so it alone proves nothing new).

        Boot #1: origin alive, real successful fetch -> "fetched". Then
        `.git/FETCH_HEAD` is deleted entirely (not aged, not corrupted —
        gone). Boot #2, still inside the 300s window: if the freshness
        signal genuinely lives in the boot's OWN stamp (never in
        FETCH_HEAD), deleting FETCH_HEAD must have NO effect — boot #2 must
        still read the own stamp and render "remote (synced ... ago)"
        without needing a new fetch. Today the signal lives EXCLUSIVELY in
        FETCH_HEAD's mtime, so deleting it forces a genuine new fetch
        instead (status flips back to "fetched", never "synced").
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)

        rc1, stdout1, stderr1, log1, combined1 = _run_boot_combined(repo_a)
        assert rc1 == 0, f"stderr: {stderr1}"
        memory_line1 = _line_with(combined1, "MEMORY:")
        assert memory_line1 is not None and memory_line1.startswith("MEMORY: remote (fetched "), (
            f"setup sanity: boot #1 must perform a real successful fetch. "
            f"Got: {memory_line1!r}"
        )

        fetch_head = os.path.join(repo_a, ".git", "FETCH_HEAD")
        assert os.path.isfile(fetch_head), "setup sanity: boot #1's real fetch must have created FETCH_HEAD"
        os.remove(fetch_head)
        assert not os.path.exists(fetch_head)

        rc2, stdout2, stderr2, log2, combined2 = _run_boot_combined(repo_a)
        assert rc2 == 0, f"stderr: {stderr2}"

        memory_line2 = _line_with(combined2, "MEMORY:")
        assert memory_line2 is not None, f"expected a MEMORY: stamp.\n{combined2}"
        assert memory_line2.startswith("MEMORY: remote (synced "), (
            f"the freshness signal must survive FETCH_HEAD's deletion — it "
            f"must live in the boot's OWN success stamp, not in "
            f".git/FETCH_HEAD (which git itself may prune/rewrite/delete "
            f"for reasons entirely unrelated to this project's own fetch "
            f"tracking). Got: {memory_line2!r}"
        )


# ── Test 3: pull directive (clean vs dirty tree) ────────────────────────


class TestPullDirective:
    """Plan Task 1 test 3 — behind + clean tree must emit a directive
    proposing `git pull` as the session's FIRST action; behind + dirty
    tree must instead warn that there is uncommitted work and NOT to
    touch it.

    RED today: render_branch_section() only ever prints
    "PULL RECOMMENDED: remote is N ahead" — no "first action" framing,
    no dirty-tree-specific "do not pull" warning exists at all.
    """

    def _setup_behind(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, PULL_DIRECTIVE_BEHIND_COUNT)
        return repo_a

    def test_behind_clean_tree_proposes_pull_as_first_action(self, tmp_path):
        repo_a = self._setup_behind(tmp_path)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert re.search(r"pull", combined, re.IGNORECASE), (
            f"expected a pull directive for a behind + clean tree.\n{combined}"
        )
        assert re.search(r"first|primer", combined, re.IGNORECASE), (
            f"expected the pull to be framed as the session's first action.\n{combined}"
        )

    def test_behind_dirty_tree_warns_do_not_pull(self, tmp_path):
        repo_a = self._setup_behind(tmp_path)
        write_file(repo_a, "wip_notes.txt", "scratch content, not committed")

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"stderr: {stderr}"
        assert re.search(r"dirty|sucio|uncommitted|sin commitear", combined, re.IGNORECASE), (
            f"expected the dirty-tree state to be mentioned.\n{combined}"
        )
        assert re.search(r"(don'?t|do not|\bno\b).{0,25}pull", combined, re.IGNORECASE), (
            f"expected an explicit 'do not pull' warning for a dirty tree.\n{combined}"
        )


# ── Test 4: fetch hardening (env + bounded timeout, fail-open) ──────────


class TestFetchHardening:
    """Plan Task 1 test 4 — the fetch must run under a hardened
    environment (GIT_TERMINAL_PROMPT=0, GIT_ASKPASS/SSH_ASKPASS
    neutralized, GIT_SSH_COMMAND with BatchMode=yes) and a short bounded
    timeout, so a hung or interactively-prompting remote can never block
    the boot. Verified with a fake `git` in PATH that records the exact
    env the fetch call received and hangs on `fetch` to exercise the
    timeout without depending on real network behavior.

    RED today: hooks/session-start-boot.py's fetch call
    (`run_git(["fetch", "--quiet"], timeout=BOOT_FETCH_TIMEOUT)`) passes
    no custom env at all — it inherits the ambient environment unmodified.
    """

    AMBIENT_GIT_TERMINAL_PROMPT = "1"
    AMBIENT_GIT_ASKPASS = "/nonexistent/ambient-askpass.sh"
    AMBIENT_SSH_ASKPASS = "/nonexistent/ambient-ssh-askpass.sh"
    AMBIENT_GIT_SSH_COMMAND = "ssh"  # no BatchMode

    @pytest.mark.skipif(WINDOWS, reason="fake-git PATH-shadowing needs a POSIX-executable named exactly 'git'")
    def test_fetch_uses_hardened_env_and_bounded_timeout(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        local_marker = "FAILOPEN-LOCAL-CONTENT-MARKER"
        _commit_real(repo_a, "context", "freshness", "local content before hang", {"Next": local_marker})

        log_path = str(tmp_path / "fake_git_fetch_calls.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        # The fake git's hang must safely OUTLAST FETCH_TIMEOUT_SECONDS, or
        # the fake fetch just finishes on its own (fake git exits 0 after
        # its sleep) before run_git's own timeout ever fires — which would
        # prove nothing about the timeout actually bounding the hang.
        hang_seconds = FETCH_TIMEOUT_SECONDS + 20
        env = {
            "PATH": fake_bin + os.pathsep + os.environ.get("PATH", ""),
            "FAKE_GIT_FETCH_HANG_SECONDS": str(hang_seconds),
            "GIT_TERMINAL_PROMPT": self.AMBIENT_GIT_TERMINAL_PROMPT,
            "GIT_ASKPASS": self.AMBIENT_GIT_ASKPASS,
            "SSH_ASKPASS": self.AMBIENT_SSH_ASKPASS,
            "GIT_SSH_COMMAND": self.AMBIENT_GIT_SSH_COMMAND,
        }

        start = time.monotonic()
        rc, stdout, stderr = run_script(BOOT_HOOK, repo_a, env=env, timeout=FETCH_TIMEOUT_SECONDS + 20)
        elapsed = time.monotonic() - start

        assert rc == 0, f"boot must fail open even if the fetch hangs. stderr: {stderr}"
        assert elapsed < FETCH_TIMEOUT_SECONDS + 5, (
            f"boot took {elapsed:.1f}s — a hung fetch must be bounded by the "
            f"{FETCH_TIMEOUT_SECONDS}s fetch timeout, not the harness's own subprocess timeout"
        )

        records = _read_fake_git_log(log_path)
        fetch_records = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert fetch_records, "fetch was never attempted — cannot verify hardening"
        fetch_env = fetch_records[-1]["env"]

        assert fetch_env.get("GIT_TERMINAL_PROMPT") == "0", (
            "expected GIT_TERMINAL_PROMPT=0 to override the ambient "
            f"{self.AMBIENT_GIT_TERMINAL_PROMPT!r}. Got: {fetch_env.get('GIT_TERMINAL_PROMPT')!r}"
        )
        assert fetch_env.get("GIT_ASKPASS") != self.AMBIENT_GIT_ASKPASS, (
            "expected GIT_ASKPASS to be neutralized, not the ambient poisoned value"
        )
        assert fetch_env.get("SSH_ASKPASS") != self.AMBIENT_SSH_ASKPASS, (
            "expected SSH_ASKPASS to be neutralized, not the ambient poisoned value"
        )
        ssh_cmd = fetch_env.get("GIT_SSH_COMMAND", "")
        assert "BatchMode=yes" in ssh_cmd, (
            f"expected GIT_SSH_COMMAND to force BatchMode=yes. Got: {ssh_cmd!r}"
        )

        # Fail-open: local content is still served despite the hung fetch.
        combined = stdout + "\n" + _read_boot_log(repo_a)
        assert local_marker in combined, (
            f"local memory must still be shown when the fetch hangs/fails.\n{combined}"
        )


# ── Test 5: gate — no toolkit memory means no fetch at all ──────────────


class TestFetchGateSkipsWithoutToolkitMemory:
    """Plan Task 1 test 5 — a repo with NO toolkit memory installed (no
    "BEGIN unmassk-toolkit" marker in CLAUDE.md, no
    .claude/.unmassk/manifest.json) must never attempt a fetch at all.
    Verified via a fake `git` executable placed first on PATH that logs
    every invocation — if a `fetch` subcommand is ever recorded, the gate
    is missing or broken.

    RED today: session-start-boot.py's fetch call is completely ungated —
    it runs on every repo regardless of toolkit-memory presence.
    """

    @pytest.mark.skipif(WINDOWS, reason="fake-git PATH-shadowing needs a POSIX-executable named exactly 'git'")
    def test_no_toolkit_memory_never_attempts_fetch(self, tmp_path):
        repo = str(tmp_path / "ungated_repo")
        os.makedirs(repo)
        _git(["init", "-b", "main"], repo)
        _git(["config", "user.email", "x@test.com"], repo)
        _git(["config", "user.name", "X"], repo)
        _git(["commit", "--allow-empty", "-m", "init"], repo)

        # A real remote IS configured — so if a fetch attempt happened, it
        # would actually reach the fake git wrapper instead of failing
        # earlier for lack of a remote.
        bare = str(tmp_path / "bare_ungated.git")
        subprocess.run(["git", "init", "--bare", "-b", "main", bare], capture_output=True, check=True)
        _git(["remote", "add", "origin", bare], repo)
        _git(["push", "-u", "origin", "main"], repo)

        # Deliberately no INSTALL run — no CLAUDE.md marker, no manifest.json.
        assert not os.path.isfile(os.path.join(repo, "CLAUDE.md"))
        assert not os.path.isfile(os.path.join(repo, ".claude", ".unmassk", "manifest.json"))

        log_path = str(tmp_path / "fake_git_calls.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}

        rc, stdout, stderr = run_script(BOOT_HOOK, repo, env=env, timeout=20)
        assert rc == 0, f"stderr: {stderr}"

        records = _read_fake_git_log(log_path)
        assert records, "fake git was never invoked at all — cannot verify the gate"
        fetch_calls = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert not fetch_calls, (
            "expected NO git fetch attempt for a repo without toolkit memory, "
            f"got: {fetch_calls}"
        )


# ── Test 6: rate-limit via FETCH_HEAD mtime ──────────────────────────────


class TestFetchRateLimit:
    """Plan Task 1 test 6 — the rate-limit gate skips the boot's fetch when
    there is fresh evidence of a prior own successful sync, and runs it
    when that evidence is stale or absent.

    v1->v2 RE-BASE (issue #60 AMENDMENT v2, decision 90d096d, session
    2026-07-10): the evidence source moved from .git/FETCH_HEAD's mtime
    (touched by ANY git fetch, including a raw one bypassing the hook) to
    the boot's own success stamp (written ONLY by a real boot's own
    successful fetch — see lib/boot_git_checks.py's
    TestOwnSuccessStampNotFetchHeadMtime class in this file). The seeding
    mechanic in both tests below changed accordingly (a raw `git fetch
    origin`, bypassing the hook, no longer counts as evidence at all —
    that exact shape is Vector D's own contract now) and the "skipped"
    assertion is verified via the fake-git call log instead of FETCH_HEAD's
    mtime (v2 does not read or care about that file at all anymore). The
    SEMANTIC each test pins is unchanged: fresh evidence -> skip re-fetch;
    stale evidence -> re-fetch for real.
    """

    def test_fresh_fetch_head_skips_fetch(self, tmp_path):
        """Re-based seeding: a full real boot (through the hook) is the
        only thing that can write a valid own-success stamp under v2, so
        seed via one real boot cycle first (its real successful fetch
        writes the stamp), then assert the immediately-following boot
        (well inside the 300s window) skips re-fetching entirely — checked
        via the fake-git invocation log, since FETCH_HEAD's mtime is no
        longer the observable signal.
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)

        first_rc, _first_out, first_err = _run_boot(repo_a)
        assert first_rc == 0, f"seeding boot must succeed. stderr: {first_err}"

        log_path = str(tmp_path / "fake_git_fresh_skip.jsonl")
        fake_bin = _make_fake_git(tmp_path, log_path)
        env = {"PATH": fake_bin + os.pathsep + os.environ.get("PATH", "")}

        rc, stdout, stderr = run_script(BOOT_HOOK, repo_a, env=env, timeout=20)
        assert rc == 0, f"boot must fail open. stderr: {stderr}"

        records = _read_fake_git_log(log_path)
        fetch_calls = [r for r in records if r["args"] and r["args"][0] == "fetch"]
        assert not fetch_calls, (
            "a boot within the rate-limit window, with a valid own-success "
            "stamp from the previous boot, must skip re-fetching entirely"
        )

    def test_stale_fetch_head_runs_fetch(self, tmp_path):
        """Re-based seeding: seed via one real boot cycle (writes the own
        stamp), then age the STAMP FILE itself past the 300s window
        (instead of FETCH_HEAD) — the stale evidence must force a real
        refetch, provably refreshing the stamp file's own mtime, and the
        MEMORY: freshness stamp must still appear.
        """
        repo_a, bare = _setup_freshness_repo(tmp_path)

        first_rc, _first_out, first_err = _run_boot(repo_a)
        assert first_rc == 0, f"seeding boot must succeed. stderr: {first_err}"

        stamp_path = os.path.join(repo_a, ".claude", ".unmassk", "boot-fetch-stamp.json")
        assert os.path.isfile(stamp_path), (
            "setup sanity: the seeding boot's real successful fetch must "
            "have written the own-success stamp"
        )
        stale_time = time.time() - (RATE_LIMIT_WINDOW_SECONDS + 300)
        os.utime(stamp_path, (stale_time, stale_time))

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)
        assert rc == 0, f"stderr: {stderr}"

        assert os.path.getmtime(stamp_path) > stale_time + 60, (
            "a stamp older than the rate-limit window must be refreshed by "
            "the boot's real refetch"
        )
        assert "MEMORY:" in combined, (
            f"a fresh fetch (stale-stamp case) must show the MEMORY: "
            f"freshness stamp.\n{combined}"
        )


# ── Test 7: divergence — both sides labeled, never merged ───────────────


class TestDivergenceShowsBothSidesLabeled:
    """Plan Task 1 test 7 — A has 1 unpushed local commit AND B pushed 2
    commits: A is simultaneously ahead by 1 and behind by 2. Boot must
    not crash, and must show BOTH sides' memory, each correctly labeled —
    never silently merged or dropped.

    RED today: extract_memory() only ever reads local HEAD, so A's own
    (ahead) Next already shows today, but B's (behind) Next can never
    appear — it only exists on origin/main, which nothing reads yet.
    """

    def test_divergence_shows_both_sides_labeled_no_merge(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)

        a_local_marker = "A-LOCAL-UNPUSHED-NEXT-MARKER"
        _commit_real(repo_a, "context", "freshness", "a's own unpushed update", {"Next": a_local_marker})
        # Deliberately NOT pushed — A is ahead by 1.

        # Deliberately no "remote" substring in the marker itself — see the
        # comment on INCIDENT_NEXT_MARKER for why.
        b_remote_marker = "B-NEXT-MARKER-77c2"
        _push_commits_from_b(repo_b, 2, next_marker=b_remote_marker)

        rc, stdout, stderr, log_content, combined = _run_boot_combined(repo_a)

        assert rc == 0, f"boot must not crash on divergence. stderr: {stderr}"
        assert "[1/2 vs upstream]" in combined, (
            f"expected the existing ahead/behind indicator to show 1 ahead, "
            f"2 behind.\n{combined}"
        )

        assert a_local_marker in combined, (
            f"A's own (ahead, unpushed) Next must still be shown.\n{combined}"
        )
        remote_line = _line_with(combined, b_remote_marker)
        assert remote_line is not None, (
            f"B's remote-only Next (behind) must also be shown, not merged "
            f"away or dropped.\n{combined}"
        )
        assert re.search(r"remot", remote_line, re.IGNORECASE), (
            f"the remote-side Next must carry a remote-provenance label. "
            f"Got line: {remote_line!r}"
        )


# ── Test 8: write path — warn-only when behind ───────────────────────────


class TestWritePathWarnOnlyWhenBehind:
    """Plan Task 1 test 8 — a memory commit made via
    bin/git-memory-commit.py while the local branch is strictly behind
    its upstream must print a VISIBLE warning, but the commit must still
    be created (warn-only, never blocking, exit 0).

    RED today: bin/git-memory-commit.py has zero behind-check — no
    warning is ever printed regardless of how far behind local is.
    """

    def test_commit_behind_warns_but_still_commits(self, tmp_path):
        repo_a, bare = _setup_freshness_repo(tmp_path)
        repo_b = _clone_machine_b(bare, tmp_path)
        _push_commits_from_b(repo_b, 2)

        # Per the plan, the write-path check makes NO network call of its
        # own — it trusts the existing remote-tracking refs, which a
        # prior boot's own fetch would already have kept fresh. Simulate
        # that here with a direct fetch.
        _git(["fetch", "origin"], repo_a)

        # The commit message deliberately does NOT contain "behind"/"detrás"
        # anywhere — git-memory-commit.py echoes the message back in its
        # own confirmation line, so a message containing that word would
        # make the warning assertion below pass vacuously on the echoed
        # input instead of on a genuine new warning line.
        commit_message = "proceed with commit regardless"
        rc, stdout, stderr = run_script(
            COMMIT_SCRIPT, repo_a,
            ["decision", "freshness", commit_message,
             "--trailer", "Decision=proceed anyway"],
        )

        combined = stdout + "\n" + stderr
        assert rc == 0, (
            f"a memory commit must still succeed while behind (warn-only). "
            f"Got exit {rc}.\nstdout: {stdout}\nstderr: {stderr}"
        )
        assert re.search(r"behind|detr[aá]s", combined, re.IGNORECASE), (
            f"expected a visible 'behind' warning.\n{combined}"
        )

        log_result = _git(["log", "-1", "--pretty=%s"], repo_a)
        assert commit_message in log_result.stdout, (
            f"expected the commit to be created despite the warning. "
            f"HEAD subject: {log_result.stdout!r}"
        )
