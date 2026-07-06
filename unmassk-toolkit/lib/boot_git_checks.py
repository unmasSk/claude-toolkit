"""
Boot git/repo-state checks for session-start-boot.py (split out of
lib/boot_checks.py, Cerberus round-6 LOC audit).

Owns the "read git/repo state for this boot" concern: branch/ahead-behind,
scopes.json, consolidation threshold, and commit timeline — moved here
together with their only callers (parse_branch_keywords(), time_ago()) per
the same rationale as the original round-5 split: lib/boot_checks.py (and
now this module) must never import FROM lib/boot_render.py (confirmed
unidirectional DAG: boot_memory <- boot_health/boot_git_checks <- boot_checks
<- boot_render). lib/boot_checks.py re-imports these functions by name so
lib/boot_render.py and any direct `boot_checks.<name>()` caller (including
tests/test_security_regression.py's importlib load of boot_checks.py) keep
resolving unchanged.

Pure refactor: behavior is byte-for-byte identical to before the split.
"""

import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from typing import NamedTuple

from boot_memory import _sanitize_trailer_value

try:
    # SEC-LOW-NEW-05: symlink-safe reader, symmetric with boot_memory.py's
    # _read_glossary_cache() guard (SEC-MED-NEW-02) — a symlink planted at
    # git-memory-scopes.json must be rejected exactly like "file absent".
    # Imported defensively: tests/test_migrate_statusline.py stubs out
    # git_helpers with a minimal fake module that predates this helper.
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink


# Commits since last context(consolidation) before warning.
BOOT_CONSOLIDATION_THRESHOLD = 50


def parse_branch_keywords(branch: str) -> tuple[list[str], str | None]:
    """Extract keywords and issue number from branch name.

    'feat/issue-42-auth-refactor' -> (['auth', 'refactor', '42'], '#42')
    'main' -> ([], None)
    """
    # Strip prefix (feat/, fix/, chore/, etc.)
    stripped = re.sub(r"^(feat|fix|chore|refactor|docs|test|ci|perf)/", "", branch)
    # Extract issue number
    issue_match = re.search(r"(?:issue[- ]?|#)(\d+)", stripped, re.IGNORECASE)
    issue_ref = f"#{issue_match.group(1)}" if issue_match else None
    # Extract keywords (split on -, _, /, filter short/noise)
    tokens = re.split(r"[-_/]", stripped)
    noise = {"feat", "fix", "chore", "issue", "refactor", "dev", "main", "master", "staging"}
    keywords = [t.lower() for t in tokens if len(t) > 2 and t.lower() not in noise]
    return keywords, issue_ref


def time_ago(iso_or_unix: str) -> str:
    """Convert ISO timestamp or unix timestamp to human-readable 'N ago' string.

    '2026-03-13T08:00:00+00:00' -> '2h ago'
    """
    try:
        if iso_or_unix.isdigit():
            dt = datetime.fromtimestamp(int(iso_or_unix), tz=timezone.utc)
        else:
            # git log %aI format
            dt = datetime.fromisoformat(iso_or_unix)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        delta = now - dt
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return "just now"
        elif seconds < 3600:
            return f"{seconds // 60}m ago"
        elif seconds < 86400:
            return f"{seconds // 3600}h ago"
        elif seconds < 604800:
            return f"{seconds // 86400}d ago"
        else:
            return f"{seconds // 604800}w ago"
    except (ValueError, TypeError, OSError):
        return "unknown"


def get_timeline(n: int = 10, suppress_scopes: set[str] | None = None) -> list[str]:
    """Get last N commits as timeline entries with time_ago.

    suppress_scopes: if provided, commits whose parsed scope is in this set are
    omitted. Used to hide non-crowned decision commits when a crowned entry
    exists for that scope.
    """
    from parsing import parse_scope
    from git_helpers import run_git

    code, output = run_git([
        "log", f"-n{n}",
        "--pretty=format:%h\x1f%s\x1f%aI"
    ])
    if code != 0 or not output:
        return []
    entries = []
    for line in output.split("\n"):
        parts = line.strip().split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, subject, date_str = parts
        if suppress_scopes:
            commit_scope = parse_scope(subject) or ""
            if commit_scope in suppress_scopes:
                continue
        entries.append(f"  {sha} {_sanitize_trailer_value(subject)} | {time_ago(date_str)}")
    return entries


def get_last_context_time() -> str | None:
    """Get the timestamp of the last context() commit as time_ago string."""
    from git_helpers import run_git

    code, output = run_git([
        "log", "-n30",
        "--pretty=format:%h\x1f%s\x1f%aI"
    ])
    if code != 0 or not output:
        return None
    for line in output.split("\n"):
        parts = line.strip().split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, subject, date_str = parts
        cleaned = re.sub(r"^[^\w#]+", "", subject).strip()
        if cleaned.lower().startswith("context("):
            return time_ago(date_str)
    return None


def get_ahead_behind(branch: str) -> tuple[int, int, str | None]:
    """Return (ahead, behind, upstream_ref) for `branch` vs its upstream.

    upstream_ref is the resolved tracking-ref name (e.g. "origin/main"), or
    None when there is no upstream / not on a real branch. Single
    `rev-list --left-right --count` call — reused by BOTH
    render_branch_section() (display) and hooks/session-start-boot.py's
    main() (issue #49, plan Task 4 — deciding whether to read memory from
    origin/<branch>). Deliberately one calculation, never two divergent
    ones (plan's own instruction).
    """
    from git_helpers import run_git

    if not branch or branch == "(detached HEAD)":
        return 0, 0, None

    code_ref, upstream_ref = run_git(["rev-parse", "--abbrev-ref", "@{u}"])
    upstream_ref = upstream_ref.strip() if code_ref == 0 else ""
    if not upstream_ref:
        return 0, 0, None

    code_ab, ab_out = run_git(["rev-list", "--left-right", "--count", f"HEAD...{upstream_ref}"])
    if code_ab == 0 and ab_out.strip():
        parts = ab_out.strip().split()
        if len(parts) == 2:
            try:
                return int(parts[0]), int(parts[1]), upstream_ref
            except ValueError:
                # Dante (BUG, fail-open violation): `rev-list --left-right
                # --count` returning two whitespace-separated tokens that
                # aren't valid integers must fall through to the SAME safe
                # fallback used for the wrong-token-count case below, not
                # raise an uncaught ValueError that crashes the boot.
                pass
    return 0, 0, upstream_ref


def _build_pull_directive_lines(behind_n: int, is_dirty: bool) -> list[str]:
    """Escalated PULL directive (issue #49, plan Task 3) — replaces the old
    bare "PULL RECOMMENDED" line. Clean tree: propose `git pull` to the user
    as the FIRST action of the session (decision d958659 — proposed at boot,
    not at close). Dirty tree: warn about the uncommitted work and say
    explicitly NOT to pull, so nothing is silently clobbered.
    """
    if is_dirty:
        return [
            f"  PULL DIRECTIVE: local is {behind_n} commit(s) behind, but the "
            "working tree is DIRTY (uncommitted changes) — do NOT pull. "
            "Inform the user and leave it untouched."
        ]
    return [
        f"  PULL DIRECTIVE: local is {behind_n} commit(s) behind — propose "
        "`git pull` to the user as the FIRST action of this session."
    ]


def _resolve_sanitized_branch() -> tuple[str, list[str], str | None]:
    """Current branch name (sanitized) plus its parsed keywords/issue ref.

    SEC-CRIT-NEW-04: git's ref-name rules don't block injection markers in a
    branch name, and this value reaches the UNCONDITIONAL stdout banner
    (render_boot_banner_lines() in hooks/session-start-boot.py) on every
    boot — the most severe of the 5 unsanitized sites found. Sanitize once,
    here, so every downstream consumer gets the safe value.
    """
    from git_helpers import run_git

    _, branch = run_git(["branch", "--show-current"])
    branch = branch or "(detached HEAD)"
    branch = _sanitize_trailer_value(branch)
    branch_keywords, branch_issue = parse_branch_keywords(branch)
    return branch, branch_keywords, branch_issue


class BranchSectionResult(NamedTuple):
    """Cerberus (round of issue #49 repairs): render_branch_section() grew a
    9-element positional tuple that main() unpacks by position — a silent
    field swap (e.g. moving ahead_n before behind_n) would type-check fine
    and fail only at runtime, far from this definition. A NamedTuple keeps
    positional unpacking working unchanged (it IS a tuple) for the one real
    caller (hooks/session-start-boot.py's main()) while making every field
    self-documenting and swap-resistant via attribute access.
    """
    lines: list[str]
    branch: str
    branch_keywords: list[str]
    branch_issue: str | None
    ahead_behind: str
    ahead_n: int
    behind_n: int
    upstream_ref: str | None
    pull_directive_lines: list[str]


def render_branch_section() -> BranchSectionResult:
    """Render the BRANCH section.

    Returns a BranchSectionResult(lines, branch, branch_keywords,
    branch_issue, ahead_behind, ahead_n, behind_n, upstream_ref,
    pull_directive_lines). ahead_n/behind_n/upstream_ref (issue #49, Task 4)
    are get_ahead_behind()'s own numbers, reused (not recomputed) by
    main()'s origin-read decision. pull_directive_lines is also returned
    standalone (beyond already being folded into `lines`) so main() can
    fold the same short text into the minimal stdout banner too — both it
    and the MEMORY: stamp are short enough to belong in the banner AND the
    full boot-log content.
    """
    from git_helpers import run_git

    lines: list[str] = []
    branch, branch_keywords, branch_issue = _resolve_sanitized_branch()

    ahead_n, behind_n, upstream_ref = get_ahead_behind(branch)
    ahead_behind = f" [{ahead_n}/{behind_n} vs upstream]" if upstream_ref else ""

    lines.append(f"BRANCH: {branch}{ahead_behind}")

    # Dirty state
    _, status_porcelain = run_git(["status", "--porcelain"])
    is_dirty = bool(status_porcelain)
    if status_porcelain:
        dirty_count = len([l for l in status_porcelain.splitlines() if l.strip()])
        lines.append(f"  DIRTY: {dirty_count} files")

    # Pull directive (reuses behind_n/is_dirty computed above — no second check)
    pull_directive_lines: list[str] = []
    if behind_n > 0:
        pull_directive_lines = _build_pull_directive_lines(behind_n, is_dirty)
        lines.extend(pull_directive_lines)

    lines.append("")
    return BranchSectionResult(
        lines, branch, branch_keywords, branch_issue, ahead_behind,
        ahead_n, behind_n, upstream_ref, pull_directive_lines,
    )


def render_scopes_section(project_root: str | None) -> list[str]:
    """Render the SCOPES section."""
    lines: list[str] = []
    scopes_file = os.path.join(project_root, ".claude", "git-memory-scopes.json") if project_root else None
    # Fallback: search in agent-memory directories
    if scopes_file and not os.path.isfile(scopes_file) and project_root:
        agent_mem = os.path.join(project_root, ".claude", "agent-memory")
        if os.path.isdir(agent_mem):
            for agent_dir in os.listdir(agent_mem):
                candidate = os.path.join(agent_mem, agent_dir, "scopes.json")
                if os.path.isfile(candidate):
                    scopes_file = candidate
                    break
    scopes_exist = scopes_file and os.path.isfile(scopes_file)
    if scopes_exist:
        try:
            # SEC-MED-NEW-12: never follow a symlink planted at
            # git-memory-scopes.json.
            with open_no_follow_symlink(scopes_file, "r") as f:
                scopes_data = json.load(f)
            scope_map = scopes_data.get("scopes", {})
            if scope_map:
                lines.append("SCOPES:")
                for scope_name, scope_info in scope_map.items():
                    # SEC-CRIT-002: scopes.json is not exclusively agent-authored
                    # (compromised collaborator commit, corrupted Bilbo run) — sanitize
                    # every embedded field the same way Decision/Memo/Remember already are.
                    safe_name = _sanitize_trailer_value(str(scope_name))
                    desc = scope_info.get("description", "") if isinstance(scope_info, dict) else str(scope_info)
                    safe_desc = _sanitize_trailer_value(str(desc))
                    children = scope_info.get("children", {}) if isinstance(scope_info, dict) else {}
                    if children:
                        safe_children = [_sanitize_trailer_value(str(k)) for k in children]
                        child_list = ", ".join(f"{safe_name}/{k}" for k in safe_children)
                        lines.append(f"  {safe_name}: {safe_desc} [{child_list}]")
                    else:
                        lines.append(f"  {safe_name}: {safe_desc}")
                lines.append("")
        except (json.JSONDecodeError, OSError):
            pass  # Silently skip if file is corrupt
    elif project_root:
        lines.append("SCOPES: not generated yet")
        lines.append(
            "  ACTION: Launch Bilbo (subagent_type=unmassk-toolkit:bilbo) to analyze the project "
            "structure and generate .claude/agent-memory/unmassk-crew-bilbo/scopes.json. "
            "The agent should: scan directories, detect frameworks, extract existing scopes "
            "from git log, and write a JSON with version, project_type, scopes (2 levels max), "
            "existing_scopes, and notes. Run it in background."
        )
        lines.append("")
    return lines


def render_consolidation_section() -> list[str]:
    """Render the CONSOLIDATE trigger section."""
    from git_helpers import commits_since_last_consolidation

    lines: list[str] = []

    _consolidation_threshold = BOOT_CONSOLIDATION_THRESHOLD
    _env_threshold = os.environ.get("GIT_MEMORY_CONSOLIDATION_THRESHOLD", "")
    if _env_threshold:
        try:
            _consolidation_threshold = int(_env_threshold)
        except (ValueError, TypeError):
            pass  # invalid override → fall back to default; never crash boot

    _commits_since = commits_since_last_consolidation()
    if _commits_since >= _consolidation_threshold:
        lines.append("CONSOLIDATE:")
        lines.append(
            f"  ⚠️ {_commits_since} commits since last consolidation. "
            "Time to consolidate: invoke Gitto (consolidator mode, additive — deletes nothing)."
        )
        lines.append("")

    return lines


# ── Boot memory freshness (multi-machine, issue #49, plan Task 2) ───────
#
# Hardened, gated, rate-limited replacement for the previous unconditional
# `run_git(["fetch", "--quiet"], timeout=BOOT_FETCH_TIMEOUT)` call in
# hooks/session-start-boot.py. Fail-open on every branch: this module must
# never let a hung, prompting, or absent remote delay or break the boot.

FETCH_RATE_LIMIT_SECONDS = 300  # skip the fetch if .git/FETCH_HEAD is younger than this
FETCH_TIMEOUT_SECONDS = 3  # short bounded timeout — replaces the old BOOT_FETCH_TIMEOUT=5

# Known residual (Argus SEC-LOW-001, accepted deliberately, not a bug):
# .git/FETCH_HEAD's mtime is plain local filesystem state, writable by
# anything with repo access (touch, a crafted checkout, clock changes).
# The rate limit above and _fetch_head_age_seconds() below trust it as-is.
# This is intentional — the gate exists purely to avoid redundant network
# fetches on every boot, not to prove or enforce when a fetch last really
# happened. A tampered/backdated mtime can only ever cause an extra (or
# skipped) fetch attempt; every actual freshness claim in the rendered
# stamp still comes from the fetch's own real exit code, never from this
# timestamp. Treat it as a best-effort optimization, not a security
# control.

# GIT_TERMINAL_PROMPT=0 + neutralized askpass + BatchMode=yes: guarantees the
# boot-time fetch can never hang on an interactive credential prompt.
#
# Windows has no `/bin/false` — Cerberus (T3, this round): the askpass
# override must fail fast on every platform, not just POSIX, or the
# "hardened" env silently degrades to "no override at all" on Windows
# whenever a real GIT_ASKPASS/SSH_ASKPASS happened to be missing/broken
# already. `cmd /c exit 1` is the Windows equivalent: it exists on every
# Windows install and returns non-zero immediately with no prompt.
#
# Argus (low portability, repair round 2): git invokes GIT_ASKPASS/
# SSH_ASKPASS as a single literal argv[0] (prompt.c's do_askpass() never
# shell-splits the value — only prepare_shell_cmd(), used for a different
# knob like GIT_SSH_COMMAND, does that). A hardcoded absolute path like
# `/bin/false` is not portable: it doesn't exist on macOS (only
# `/usr/bin/false` does; `/bin/false` is Linux-only). Using the BARE word
# `false` (no path separator) instead lets git's own has-dir-sep check
# fall through to a normal PATH lookup — `false` resolves correctly via
# PATH on both macOS (`/usr/bin/false`) and Linux (`/bin/false` or
# `/usr/bin/false`, whichever coreutils installs). Verified on this
# machine: execing "false" with an extra arg (the prompt argv the askpass
# protocol appends) exits 1 immediately, no exec error.
_ASKPASS_FAILFAST = "cmd /c exit 1" if sys.platform == "win32" else "false"

# SEC-CRIT-001 (Argus): also disable EVERY configured credential helper
# (system/global/local config files, including OS-native ones — osxkeychain,
# libsecret, Windows/macOS SSO helpers) for this one fetch. GIT_TERMINAL_PROMPT
# and the askpass overrides above only stop git's OWN interactive prompt; a
# configured helper can still pop its own out-of-band dialog. Setting
# credential.helper to the empty string resets the accumulated helper list
# (documented git behavior). GIT_CONFIG_COUNT/GIT_CONFIG_KEY_<n>/
# GIT_CONFIG_VALUE_<n> (stable since git 2.31) apply at the same "command"
# precedence scope as `-c credential.helper=` WITHOUT changing argv — some
# tests key a fake-git wrapper's behavior off argv[0] == "fetch", which a
# leading `-c ...` global option would have broken.
_FETCH_HARDENED_ENV = {
    "GIT_TERMINAL_PROMPT": "0",
    "GIT_ASKPASS": _ASKPASS_FAILFAST,
    "SSH_ASKPASS": _ASKPASS_FAILFAST,
    "GIT_SSH_COMMAND": "ssh -oBatchMode=yes",
    "GIT_CONFIG_COUNT": "1",
    "GIT_CONFIG_KEY_0": "credential.helper",
    "GIT_CONFIG_VALUE_0": "",
}


def _looks_like_git_option(value: str) -> bool:
    """Defense-in-depth (Argus SEC-CRIT-001): reject a string that could be
    misread as a git option/flag if it were ever passed as a positional git
    argument.

    Normal branch/remote creation already forbids a leading '-'
    (`git check-ref-format --branch` is documented to be stricter than the
    general refname rules specifically on this point) — but that gate only
    runs at CREATION time. A crafted `.git/HEAD` symref or a hand-edited
    `packed-refs`/`config` entry in a malicious clone can plant a ref or
    remote name that violates it, and `git branch --show-current` /
    `git rev-parse --abbrev-ref @{u}` do not re-validate before printing.
    Every value this module reads back from git config/refs and later
    passes as a positional argument to another git invocation must be
    checked with this before use — fail closed (True) on anything empty or
    leading with '-', never assume the value was pre-validated upstream.
    """
    return not value or value.startswith("-")


def _has_toolkit_memory(project_root: str) -> bool:
    """Gate check: does this repo have unmassk-toolkit memory installed?

    Either signal is sufficient: `.claude/.unmassk/manifest.json` present,
    OR the "BEGIN unmassk-toolkit" marker in CLAUDE.md — mirrors
    hooks/user-prompt-memory-check.py's needs_install() check (:51-62).
    This is a DIFFERENT axis than git-memory-config.json's `repo_type`
    (deploy-risk) — never use that field for this gate.
    """
    manifest_path = os.path.join(project_root, ".claude", ".unmassk", "manifest.json")
    if os.path.isfile(manifest_path):
        return True
    claude_md = os.path.join(project_root, "CLAUDE.md")
    if not os.path.isfile(claude_md):
        return False
    try:
        # SEC: never follow a symlink planted at CLAUDE.md — treat it
        # exactly like "no CLAUDE.md present" (same guard as
        # needs_install() and render_scopes_section() above).
        with open_no_follow_symlink(claude_md, "r") as f:
            return "BEGIN unmassk-toolkit" in f.read()
    except OSError:
        return False


def _fetch_head_age_seconds(project_root: str) -> float | None:
    """Seconds since .git/FETCH_HEAD's mtime, or None if it doesn't exist."""
    fetch_head = os.path.join(project_root, ".git", "FETCH_HEAD")
    try:
        return time.time() - os.path.getmtime(fetch_head)
    except OSError:
        return None


def fetch_memory_ref(project_root: str | None) -> dict:
    """Hardened, gated, rate-limited background fetch for multi-machine
    memory freshness. Never raises (fail-open) — any exception, timeout,
    or missing remote falls back to "failed" so the boot always continues.

    Returns:
        {"status": "fetched" | "rate_limited" | "skipped_gate" |
                    "no_remote" | "failed",
         "age_seconds": seconds since the last known successful fetch
                         (FETCH_HEAD mtime), or None if never fetched}
        Consumed by Task 3's freshness-stamp rendering, not by this
        function. "no_remote" now also covers "a remote is configured but
        the current branch has no coherent upstream tracking ref to align
        the fetch with" (Moriarty #2) — the stamp must never claim "remote"
        for a fetch target that isn't the same ref get_ahead_behind()/
        resolve_boot_memory() will actually read.
    """
    from git_helpers import run_git

    try:
        if not project_root or not _has_toolkit_memory(project_root):
            return {"status": "skipped_gate", "age_seconds": None}

        age = _fetch_head_age_seconds(project_root)
        # Moriarty #1 (clock skew): a NEGATIVE age means FETCH_HEAD's mtime
        # is in the FUTURE relative to this machine's clock (a real scenario
        # across multiple machines with unsynced clocks) — that is NOT
        # freshness, it's a broken measurement. Treating it as "fresh" would
        # permanently suppress every future fetch on this machine (age stays
        # negative forever, always < the rate-limit window). Only a genuine
        # non-negative age inside the window counts as rate-limited; a
        # negative age falls through and forces a real fetch attempt instead.
        if age is not None and 0 <= age < FETCH_RATE_LIMIT_SECONDS:
            return {"status": "rate_limited", "age_seconds": age}

        _, branch = run_git(["branch", "--show-current"], cwd=project_root)
        branch = branch.strip()
        if not branch:
            # Detached HEAD — nothing to fetch a matching branch for.
            return {"status": "failed", "age_seconds": age}
        if _looks_like_git_option(branch):
            # SEC-CRIT-001 (Argus): a branch name that could be misread as a
            # git option (e.g. planted via a crafted .git/HEAD symref or
            # packed-refs entry in a malicious clone/fork) must never reach
            # a git invocation as a positional argument. Fail closed — no
            # fetch attempted — rather than risk option injection.
            return {"status": "failed", "age_seconds": age}

        # Moriarty #2: align the fetch target with the SAME ref
        # get_ahead_behind()/resolve_boot_memory() actually read via `@{u}`
        # — not just the local branch's own name. If tracking is
        # misconfigured (e.g. after a branch rename, a common real case),
        # fetching by bare branch name can silently update the wrong
        # remote-tracking ref (or fail outright) while the MEMORY stamp
        # still claims "remote" for content that was never really
        # confirmed — reproducing issue #49 by a different path. Reusing
        # this exact resolution (not a second, potentially divergent one)
        # is the same principle get_ahead_behind() itself documents.
        code_ref, upstream_ref = run_git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=project_root)
        upstream_ref = upstream_ref.strip() if code_ref == 0 else ""
        if not upstream_ref or "/" not in upstream_ref:
            # No coherent upstream to align the fetch with — the stamp must
            # tell the truth (LOCAL / unverified), never "remote", for
            # content that was never actually confirmed against a real
            # tracking ref.
            return {"status": "no_remote", "age_seconds": age}

        remote_name, _, remote_branch = upstream_ref.partition("/")
        if _looks_like_git_option(remote_name) or _looks_like_git_option(remote_branch):
            return {"status": "failed", "age_seconds": age}

        # Moriarty #2 (repair round 2, T2): the liveness check must use the
        # REAL upstream remote name just derived from `@{u}` above, never a
        # hardcoded "origin" literal. A repo that ran
        # `git remote rename origin upstream` (tracking preserved,
        # coherent) previously always hit this check with the literal
        # "origin", which no longer resolves, so the check always failed
        # with "no_remote" and the whole freshness feature was permanently
        # dead on any repo not using the default remote name. `remote_name`
        # is already fail-closed validated by _looks_like_git_option above.
        code_remote, _ = run_git(["remote", "get-url", "--", remote_name], cwd=project_root)
        if code_remote != 0:
            return {"status": "no_remote", "age_seconds": age}

        code_fetch, _ = run_git(
            # SEC-CRIT-001 (Argus): `--` separates options from the
            # positional ref argument — even with the leading-dash guard
            # above, this must not depend on that invariant holding forever.
            ["fetch", remote_name, "--no-tags", "--", remote_branch],
            timeout=FETCH_TIMEOUT_SECONDS,
            cwd=project_root,
            env=_FETCH_HARDENED_ENV,
        )
        if code_fetch != 0:
            return {"status": "failed", "age_seconds": age}

        # Cerberus (nitpick): reflect FETCH_HEAD's real mtime-derived age
        # instead of a hardcoded 0.0 — a successful fetch stamps FETCH_HEAD
        # at completion time, so this is genuinely ~0 in the overwhelming
        # common case, but it's now MEASURED rather than assumed.
        fresh_age = _fetch_head_age_seconds(project_root)
        fresh_age_seconds = float(max(0, int(fresh_age))) if fresh_age is not None else 0.0
        return {"status": "fetched", "age_seconds": fresh_age_seconds}
    except Exception as e:
        # Fail-open: this function must never raise regardless of cause.
        # Cerberus: leave a breadcrumb (same pattern as git_helpers.py's
        # UnicodeDecodeError branch) instead of failing completely silently.
        print(f"[boot_git_checks] fetch_memory_ref: unexpected {type(e).__name__}: {e}", file=sys.stderr)
        return {"status": "failed", "age_seconds": None}


def _format_age_seconds(seconds: float) -> str:
    """Human-readable age for the MEMORY: stamp, e.g. '0s' / '5min' / '2h'."""
    total = max(0, int(seconds))
    if total < 60:
        return f"{total}s"
    minutes = total // 60
    if minutes < 60:
        return f"{minutes}min"
    hours = minutes // 60
    return f"{hours}h"


def render_memoria_stamp(fetch_state: dict) -> str:
    """Render the MEMORY: provenance/freshness stamp for the boot header
    (issue #49, plan Task 3). One short line — printed in BOTH the minimal
    stdout banner and the full boot-log content, near the top of each.

    Bex (issue #49 repair round, language-unification decision): the whole
    boot banner (STATUS/BRANCH/RESUME/REMEMBER/DECISIONS/PULL DIRECTIVE) is
    English — this stamp used to be the one Spanish outlier. Wording is
    English now; the field/state semantics documented below are unchanged.

    Three states, matching fetch_memory_ref()'s `status` field:
      - "fetched": a fetch against origin completed this boot — content is
        remote-confirmed fresh.
      - "rate_limited": the fetch was skipped this boot (still inside the
        rate-limit window) — local content, not reconfirmed this boot.
      - anything else ("failed", "no_remote", "skipped_gate"): freshness
        against origin could not be confirmed this boot — falls back to
        the "LOCAL ... unverified" wording.
    """
    status = fetch_state.get("status")
    age = fetch_state.get("age_seconds")

    if status == "fetched":
        age_txt = _format_age_seconds(age if age is not None else 0.0)
        return f"MEMORY: remote (fetched {age_txt} ago)"

    if status == "rate_limited":
        age_txt = _format_age_seconds(age) if age is not None else "?"
        return f"MEMORY: LOCAL — fetch skipped (rate-limit, {age_txt} ago)"

    # "failed" / "no_remote" / "skipped_gate" (or any future fail-open
    # status): never confirmed fresh against origin this boot.
    if age is not None:
        age_txt = _format_age_seconds(age)
        return f"MEMORY: LOCAL — last fetch {age_txt} ago, unverified"
    return "MEMORY: LOCAL — unverified (never synced with origin)"
