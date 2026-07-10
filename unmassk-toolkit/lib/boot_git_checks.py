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
import subprocess
import sys
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

# Issue #60 AMENDMENT v2/v3 (decisions 90d096d, 787b698): the boot's own
# fetch-success stamp is written under .claude/.unmassk/ — path resolution,
# read (identity + schema validated), atomic write, and the rate-limit
# decision built on it now live in lib/boot_fetch_stamp.py (Cerberus S2,
# round 3 — split out once this file crossed 1000 LOC). Re-imported here by
# ORIGINAL NAME (not `import boot_fetch_stamp` + qualified access) so every
# existing caller/test in this file, including tests that reach into this
# module's own namespace directly (e.g.
# tests/test_boot_freshness_hardening.py::TestReadOwnStampAgeDirectCalls
# calling `boot_git_checks._read_own_stamp_age(...)`), keeps resolving
# unchanged — pure extraction, no public-API/contract change. See that
# module's own docstring for the two-strictness-level identity design.
from boot_fetch_stamp import (
    FETCH_RATE_LIMIT_SECONDS,
    _OWN_STAMP_FILENAME,
    _OWN_STAMP_SCHEMA_VERSION,
    _own_stamp_path,
    _read_own_stamp_age,
    _read_stamp_age_by_alias_only,
    _write_own_stamp,
    _check_own_stamp_rate_limit,
)


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

    Returns "unknown" whenever parsing fails -- including non-str input and
    non-ASCII digit strings. Mirrors lib/date_parsing.py's parse_date(),
    this function's sibling in the same "git log date parsing" lineage.
    """
    # iso_or_unix.isdigit() below has no .isdigit attribute on non-str
    # input (None, int, list, ...) -- AttributeError is not in the except
    # tuple, so it would crash instead of degrading to the "unknown"
    # fallback every other malformed-input case in this function already
    # gets. Explicit type guard up front, mirroring parse_date()'s own
    # guard for the identical shape.
    if not isinstance(iso_or_unix, str):
        return "unknown"
    try:
        # isascii() gate: str.isdigit() also accepts non-ASCII Unicode
        # digits (fullwidth, arabic-indic, devanagari, ...) that int()
        # would happily convert -- but no real `git log %at` call ever
        # emits those, so a non-ASCII digit string here is malformed input,
        # not a valid epoch, and must fall through to the ISO-8601 branch
        # (which will also fail to parse it) rather than be silently
        # accepted.
        if iso_or_unix.isascii() and iso_or_unix.isdigit():
            # %at (unix epoch) — the format every in-repo caller now uses
            # (get_timeline(), get_last_context_time(), extract_memory() in
            # boot_memory.py). Robust across git versions/locales, unlike
            # %aI below.
            dt = datetime.fromtimestamp(int(iso_or_unix), tz=timezone.utc)
        else:
            # ISO-8601 (git log %aI) fallback — kept for any external/legacy
            # caller still passing this shape; no in-repo git log call in
            # this module produces it anymore.
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
    except (ValueError, TypeError, OSError, OverflowError):
        return "unknown"


def get_timeline(n: int = 10, suppress_scopes: set[str] | None = None) -> list[str]:
    """Get last N commits as timeline entries with time_ago.

    suppress_scopes: if provided, commits whose parsed scope is in this set are
    omitted. Used to hide non-crowned decision commits when a crowned entry
    exists for that scope.
    """
    from parsing import parse_scope
    from git_helpers import run_git

    # %at (author date, unix epoch) — NOT %aI (ISO-8601). Same date token
    # (%at), HEAD ref, and trailing "--" terminator as extract_memory()'s
    # git log call (boot_memory.py) — not an identical invocation (that
    # call also uses `-z` for NUL-separated records) — so both code paths
    # that render a commit's age agree by construction, instead of relying
    # on two different git date formatters staying in sync
    # (House root-cause, CI issue: an older git runner's %aI/locale
    # interaction produced a date string time_ago()'s ISO branch could not
    # parse, silently dropping the " | <time_ago>" suffix). %at is plain
    # digits regardless of git version or locale, and time_ago() already has
    # a dedicated `.isdigit()` branch for it. Explicit "HEAD" + trailing "--"
    # mirror extract_memory()'s own SEC-CRIT-001 defense-in-depth shape used
    # throughout this module — no external `ref` reaches this call today,
    # but the same positional-argument hygiene applies uniformly on principle.
    code, output = run_git([
        "log", "HEAD", f"-n{n}",
        "--pretty=format:%h\x1f%s\x1f%at",
        "--",
    ], log_stderr_on_failure=True)
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
    """Get the timestamp of the last context() commit as time_ago string.

    Uses %at (unix epoch), same rationale/token as get_timeline() above.
    Shares the %at date token, HEAD ref, and trailing "--" terminator with
    extract_memory()'s git log call (boot_memory.py) — not an identical
    invocation (that call also uses `-z`) — one robust date format shared
    by every "how long ago" reader, so this and get_timeline() can never
    disagree just because a different git version renders %aI differently.
    """
    from git_helpers import run_git

    code, output = run_git([
        "log", "HEAD", "-n30",
        "--pretty=format:%h\x1f%s\x1f%at",
        "--",
    ], log_stderr_on_failure=True)
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


def _resolve_scopes_file(project_root: str | None) -> str | None:
    """Locate git-memory-scopes.json: canonical `.claude/` path first, then
    fall back to searching each `agent-memory/*/scopes.json`.

    Returns None only when `project_root` itself is falsy. Otherwise always
    returns a path string — the canonical (possibly non-existent) path when
    no fallback candidate is found, so the caller's own `os.path.isfile()`
    check still correctly reports "not generated yet".
    """
    if not project_root:
        return None
    scopes_file = os.path.join(project_root, ".claude", "git-memory-scopes.json")
    if os.path.isfile(scopes_file):
        return scopes_file
    agent_mem = os.path.join(project_root, ".claude", "agent-memory")
    if os.path.isdir(agent_mem):
        for agent_dir in os.listdir(agent_mem):
            candidate = os.path.join(agent_mem, agent_dir, "scopes.json")
            if os.path.isfile(candidate):
                return candidate
    return scopes_file


def _render_scope_entries(scope_map: dict) -> list[str]:
    """Render one sanitized line per scope.

    SEC-CRIT-002: scopes.json is not exclusively agent-authored (compromised
    collaborator commit, corrupted Bilbo run) — sanitize every embedded
    field the same way Decision/Memo/Remember already are.
    """
    lines: list[str] = []
    for scope_name, scope_info in scope_map.items():
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
    return lines


def render_scopes_section(project_root: str | None) -> list[str]:
    """Render the SCOPES section."""
    lines: list[str] = []
    scopes_file = _resolve_scopes_file(project_root)
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
                lines.extend(_render_scope_entries(scope_map))
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

FETCH_TIMEOUT_SECONDS = 10  # bounded timeout, raised from 3s (decision b2a32b9): 3s let the
# fetch time out under normal network conditions, leaving boot to read a stale local
# briefing instead of origin's fresh one (resolve_boot_memory() only picks up origin
# when the fetch actually completes). 10s gives the fetch enough margin to complete on
# ordinary network — still a bounded timeout, boot never hangs indefinitely; fail-open
# on every branch is unchanged.

# Historical residual (Argus SEC-LOW-001, issue #49) + restored invariant
# (issue #60 AMENDMENT v2, decision 90d096d): .git/FETCH_HEAD's mtime is
# plain local filesystem state, writable by anything with repo access
# (touch, a crafted checkout, clock changes, ANY git fetch to ANY remote —
# not just this project's own memory upstream), and even a FAILED fetch
# truncates+refreshes it. Issue #60's v1 relabel briefly let this mtime
# feed a real freshness CLAIM (`MEMORY: remote (synced ... ago)`) — Cerberus
# flagged that this directly contradicted the invariant this comment used
# to state ("every actual freshness claim ... never from this timestamp"),
# and Moriarty confirmed it live (T1): a failed fetch, or a successful
# fetch of an unrelated remote, both produced a false "synced" claim.
#
# v2 restored the invariant for real, by changing the SOURCE instead of
# layering a comparison on top of the same untrustworthy file: FETCH_HEAD is
# no longer read AT ALL by the gate or the rendered stamp —
# `_fetch_head_age_seconds()`, the old reader, has been removed entirely
# (not just stopped-being-called; see "no dead code"). The rate limit and
# the "synced Ns ago" wording read ONLY the boot's own success stamp
# (`.claude/.unmassk/boot-fetch-stamp.json`, gitignored, per-machine),
# written EXCLUSIVELY after THIS project's own `git fetch` against the
# resolved memory upstream exits 0.
#
# v3 (decision 787b698) closed a SECOND identity gap Moriarty found in v2:
# matching that stamp by remote ALIAS + branch alone ("origin"/"main") lets
# a stamp file copied verbatim between two entirely unrelated repos that
# merely share that common alias/branch convention (template scaffolding,
# backup, dotfiles-sync — no adversary or git operation required) pass as
# "this project's own confirmed sync". The identity now compared also
# includes the remote's REAL URL (`git remote get-url`) and the stamp's
# schema_version — see lib/boot_fetch_stamp.py (the own-stamp I/O module
# this file delegates to, Cerberus S2 split, round 3) for the read/write/
# rate-limit implementation, the exact comparison, and what this identity
# model does and does NOT cover (short version: it closes cross-repo stamp
# reuse via a shared alias/branch convention; it does not, and cannot,
# defend against an attacker who already has local write access to THIS
# repo's own .claude/.unmassk/ directory — the same threat class every
# other gitignored, locally-writable cache file in this codebase already
# sits outside the trust boundary for). A tampered/backdated-but-otherwise-
# matching stamp can still only ever cause an extra (harmless) or a skipped
# fetch attempt — the same fail-open philosophy as before.

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


# check_upstream_shares_history() background (Moriarty T2, issue #49 repair
# round, Round-Trip Sabotage §34): fetch_memory_ref()/resolve_boot_memory()
# only ever checked that `@{u}` resolves to a coherent, FETCHABLE ref — never
# that the resolved ref is actually a continuation of THIS project's history.
# A misconfigured branch.<x>.remote/.merge pointing at a totally unrelated
# repo (zero shared history) satisfies every existing check (fetch succeeds,
# `@{u}` resolves cleanly) while that repo's crowned decisions get rendered
# as "[source: remote]" memory for a project that has never seen them.
#
# `git merge-base HEAD <upstream_ref>` (deliberately NOT --is-ancestor — the
# two sides can be mutually diverged, neither an ancestor of the other; we
# only care whether ANY common ancestor exists at all) resolves this: exit 0
# means a common ancestor exists (confirmed continuation); exit 1 (or any
# other run_git-level failure, which collapses to the same (1, "") per its
# documented contract) means "not confirmed shared".
#
# Deliberate fail-CLOSED-on-TRUST design (the opposite of this module's usual
# fail-open-on-availability rule elsewhere): a shallow clone can make
# `merge-base` return a FALSE NEGATIVE even when history really IS shared,
# because the true common ancestor sits past the shallow boundary. There is
# no reliable local signal that tells "genuinely unrelated" apart from
# "shallow clone truncated the graph" — both present identically — so this
# function deliberately does not try to distinguish them. The cost is that a
# shallow clone with a legitimate upstream may occasionally get its remote
# memory suppressed for one boot; the alternative (assuming "shared" on any
# ambiguity) is exactly the T2 hole this function exists to close — per
# Moriarty's own framing, better to under-show than to show another
# project's memory as if it were this one's.
def check_upstream_shares_history(upstream_ref: str | None) -> bool | None:
    """Does `upstream_ref` share real commit history with local HEAD?

    Returns True (confirmed shared ancestor), False (not confirmed shared —
    covers both "genuinely unrelated" and "shallow clone, can't tell"), or
    None when `upstream_ref` itself is missing or option-shaped ("not
    evaluated" — callers must treat this as "no signal, behave as before
    this check existed", never as "confirmed unrelated"). See the comment
    block above this function for the full design rationale.
    """
    from git_helpers import run_git

    if not upstream_ref or _looks_like_git_option(upstream_ref):
        return None
    # `--` separates options from the two positional refs — defense in
    # depth, same rationale as every other positional-ref git call in this
    # module (SEC-CRIT-001).
    code, _ = run_git(["merge-base", "--", "HEAD", upstream_ref])
    return code == 0


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


def _resolve_current_branch(project_root: str) -> tuple[dict | None, str | None]:
    """Current branch name, validated. Returns (early_result, branch);
    `early_result` is not None for detached HEAD or an option-shaped name.
    No own-stamp identity is known yet at this point in the resolution
    flow, so every early-exit here reports age_seconds=None.
    """
    from git_helpers import run_git

    _, branch = run_git(["branch", "--show-current"], cwd=project_root)
    branch = branch.strip()
    if not branch or _looks_like_git_option(branch):
        # Detached HEAD, or a branch name that could be misread as a git
        # option (SEC-CRIT-001, Argus) — fail closed, no fetch attempted.
        return {"status": "failed", "age_seconds": None}, None
    return None, branch


def _check_remote_is_live(project_root: str, remote_name: str, remote_branch: str) -> tuple[dict | None, str | None]:
    """Moriarty #2 (repair round 2, T2): confirm the REAL upstream remote
    name (never a hardcoded "origin" literal) actually resolves — a `git
    remote rename origin upstream` repo (tracking preserved) would
    otherwise always hit "no_remote", permanently dead on non-default
    remotes.

    Returns (early_result, remote_url). `early_result` is not None when the
    caller must return it immediately: the remote entry doesn't resolve at
    all (`git remote get-url` fails — e.g. `git remote remove origin` ran
    since the last successful sync), or its URL is option-shaped/empty
    (SEC-CRIT-001 defense-in-depth, same pattern already used for
    remote/branch — a value that could be misread as a git flag is never
    trusted as identity evidence). On success, `early_result` is None and
    `remote_url` carries the resolved URL (never None on that branch) — the
    own-stamp identity check (lib/boot_fetch_stamp.py, v3) needs it
    alongside remote_name/remote_branch.

    Cerberus S1 (round 3, decision 787b698 — fixes a false docstring: this
    used to claim "no own-stamp identity is known yet at this point" and
    hardcoded every early exit to age_seconds=None, which stopped being
    true the moment a real prior sync could exist under the SAME
    remote/branch alias). When the remote is dead, a prior stamp may still
    exist from before it broke; its age is informative (a genuine sync
    really did happen) even though there's no live URL left to compare
    against for strict identity. Deliberately compares alias/branch ONLY
    here (`_read_stamp_age_by_alias_only()`, never the strict
    `_read_own_stamp_age()`) — safe because the status returned on this
    branch is ALWAYS "no_remote", never "rate_limited"/"fetched", so this
    age can only ever reach the "LOCAL — last fetch Xs ago, unverified"
    wording, never a "remote (synced ...)" claim — it does not reopen the
    v3 cross-repo vector (see lib/boot_fetch_stamp.py's docstring for that
    helper's own safety argument).
    """
    from git_helpers import run_git

    code_remote, url = run_git(["remote", "get-url", "--", remote_name], cwd=project_root)
    url = url.strip() if code_remote == 0 else ""
    if code_remote != 0 or _looks_like_git_option(url):
        age = _read_stamp_age_by_alias_only(project_root, remote_name, remote_branch)
        return {"status": "no_remote", "age_seconds": age}, None
    return None, url


def _resolve_fetch_target(project_root: str) -> tuple[dict | None, str | None, str | None, str | None]:
    """Resolve (remote_name, remote_branch, remote_url) to fetch, aligned
    with the SAME upstream `@{u}` ref get_ahead_behind()/resolve_boot_memory()
    read (Moriarty #2 — a bare-branch-name fetch can silently target the
    wrong remote-tracking ref after a rename). Returns (early_result,
    remote_name, remote_branch, remote_url); `early_result` is not None
    when the caller must return it immediately. Runs BEFORE any own-stamp
    check (issue #60 v2): the stamp's age is only meaningful once we know
    which remote/branch/URL it must match (v3, decision 787b698 — the URL
    is resolved here too, via `_check_remote_is_live()`, and threaded down
    to the own-stamp identity check).
    """
    from git_helpers import run_git

    early, _branch = _resolve_current_branch(project_root)
    if early is not None:
        return early, None, None, None

    code_ref, upstream_ref = run_git(["rev-parse", "--abbrev-ref", "@{u}"], cwd=project_root)
    upstream_ref = upstream_ref.strip() if code_ref == 0 else ""
    if not upstream_ref or "/" not in upstream_ref:
        # No coherent upstream to align the fetch with — the stamp must
        # tell the truth (LOCAL / unverified), never "remote".
        return {"status": "no_remote", "age_seconds": None}, None, None, None

    remote_name, _, remote_branch = upstream_ref.partition("/")
    if _looks_like_git_option(remote_name) or _looks_like_git_option(remote_branch):
        return {"status": "failed", "age_seconds": None}, None, None, None

    early, remote_url = _check_remote_is_live(project_root, remote_name, remote_branch)
    if early is not None:
        return early, None, None, None

    return None, remote_name, remote_branch, remote_url


def _run_hardened_fetch(
    project_root: str, remote_name: str, remote_branch: str, remote_url: str | None, age: float | None
) -> dict:
    """Run the hardened fetch itself and build the final result dict."""
    from git_helpers import run_git

    code_fetch, _ = run_git(
        # SEC-CRIT-001 (Argus): `--` separates options from the positional
        # ref argument — even with the leading-dash guard upstream, this
        # must not depend on that invariant holding forever.
        ["fetch", remote_name, "--no-tags", "--", remote_branch],
        timeout=FETCH_TIMEOUT_SECONDS,
        cwd=project_root,
        env=_FETCH_HARDENED_ENV,
    )
    if code_fetch != 0:
        return {"status": "failed", "age_seconds": age}

    # Issue #60 AMENDMENT v2/v3: record OUR OWN success, keyed to the exact
    # remote/branch/URL just fetched — this write (not FETCH_HEAD's mtime)
    # is what the rate-limit gate and the rendered stamp read from now on.
    # age_seconds is hardcoded 0.0 (not re-measured): this process controls
    # exactly when the stamp is written, synchronously right here, unlike
    # FETCH_HEAD, which git itself could touch for unrelated reasons — no
    # separate measurement can be more accurate than "right now".
    _write_own_stamp(project_root, remote_name, remote_branch, remote_url)
    return {"status": "fetched", "age_seconds": 0.0}


def fetch_memory_ref(project_root: str | None) -> dict:
    """Hardened, gated, rate-limited background fetch for multi-machine
    memory freshness. Never raises (fail-open) — any expected failure
    (network down, missing remote, IO error, timeout) falls back to
    "failed" so the boot always continues.

    Returns:
        {"status": "fetched" | "rate_limited" | "skipped_gate" |
                    "no_remote" | "failed",
         "age_seconds": seconds since this project's own last confirmed
                         successful fetch (issue #60 v2/v3's own-success
                         stamp — see lib/boot_fetch_stamp.py), or None if
                         never fetched (or no evidence for the CURRENT
                         resolved remote/branch/URL)}
        Consumed by Task 3's freshness-stamp rendering, not by this
        function. "no_remote" also covers "a remote is configured but the
        current branch has no coherent upstream tracking ref to align the
        fetch with" (Moriarty #2) — the stamp must never claim "remote" for
        a fetch target that isn't the same ref get_ahead_behind()/
        resolve_boot_memory() will actually read.
    """
    try:
        if not project_root:
            return {"status": "skipped_gate", "age_seconds": None}

        if not _has_toolkit_memory(project_root):
            return {"status": "skipped_gate", "age_seconds": None}

        # Resolve the target BEFORE checking the own stamp (issue #60 v2):
        # the stamp's age is only meaningful once we know which
        # remote/branch/URL it must match against.
        early, remote_name, remote_branch, remote_url = _resolve_fetch_target(project_root)
        if early is not None:
            return early

        early, age = _check_own_stamp_rate_limit(project_root, remote_name, remote_branch, remote_url)
        if early is not None:
            return early

        return _run_hardened_fetch(project_root, remote_name, remote_branch, remote_url, age)
    except (subprocess.SubprocessError, OSError, ValueError, TypeError) as e:
        # Expected failure modes for a network/IO-bound operation: a
        # subprocess-level error, filesystem error, or malformed numeric
        # data. Every helper above already collapses git-level failures to
        # (1, "")/None internally — this is defense-in-depth for the glue
        # code in this function itself. Still fail-open (the boot must
        # never crash), but logged so it's diagnosable.
        print(f"[boot_git_checks] fetch_memory_ref: {type(e).__name__}: {e}", file=sys.stderr)
        return {"status": "failed", "age_seconds": None}
    except Exception as e:
        # UNEXPECTED: a real programming bug in this function or one of its
        # helpers (AttributeError, KeyError, TypeError from a shape the code
        # above doesn't already guard against, etc). Still fail-open — the
        # boot must never crash on this non-critical, best-effort feature —
        # but tagged distinctly so it reads as "investigate this", never as
        # a routine network/IO hiccup.
        print(f"[boot_git_checks] fetch_memory_ref: UNEXPECTED (likely a bug, not a routine failure) {type(e).__name__}: {e}", file=sys.stderr)
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


# render_memoria_stamp() background: Bex (issue #49 repair round, language-
# unification decision) — the whole boot banner (STATUS/BRANCH/RESUME/
# REMEMBER/DECISIONS/PULL DIRECTIVE) is English; this stamp used to be the
# one Spanish outlier. Wording is English now. Issue #60 (relabel decision
# ceef426) later corrected the `rate_limited` branch below: a confirmed-
# recent own success stamp (issue #60 AMENDMENT v2, decision 90d096d — see
# `_check_own_stamp_rate_limit()`) means memory is confirmed fresh, so it
# renders as "remote", not "LOCAL" — labeling a good state as a local-only
# fallback read as a failure that wasn't one.
# `history_related` (Moriarty T2, repo-identity confusion): None
# (default) preserves the three fetch-status branches below exactly,
# unchanged for every caller that never passes this argument. False means
# check_upstream_shares_history() found (or could not rule out) that the
# resolved upstream is NOT a continuation of this project's history — in
# that case NONE of the fetch-status wording may be used, since "fetched" or
# "rate_limited" only describes whether bytes moved, not whose history they
# belong to, and claiming "remote" for an unrelated repo's content is
# exactly the incident this fix closes. That check runs first and
# short-circuits everything else.
def _render_confirmed_fetch_stamp(status: str | None, age: float | None) -> str | None:
    """The two "memory is confirmed fresh against origin this boot" states.
    Both `fetched` and `rate_limited` mean this project's OWN success stamp
    is known-recent (issue #60 AMENDMENT v2 — the latter only fires when
    `_check_own_stamp_rate_limit()` measured age < 300s against the CURRENT
    resolved remote/branch), so both render as "remote" — never "LOCAL".
    Returns None when neither applies, so the caller falls through to the
    "unverified" wording (age known-but-stale, or never fetched at all).
    """
    if status == "fetched":
        age_txt = _format_age_seconds(age if age is not None else 0.0)
        return f"MEMORY: remote (fetched {age_txt} ago)"
    if status == "rate_limited":
        age_txt = _format_age_seconds(age) if age is not None else "?"
        return f"MEMORY: remote (synced {age_txt} ago)"
    return None


def render_memoria_stamp(fetch_state: dict, history_related: bool | None = None) -> str:
    """Render the MEMORY: provenance/freshness stamp for the boot header
    (issue #49, plan Task 3). One short line — printed in BOTH the minimal
    stdout banner and the full boot-log content, near the top of each. See
    the comment block above this function for the full design rationale.
    """
    if history_related is False:
        return "MEMORY: LOCAL — upstream unrelated (no shared history), not shown"

    status = fetch_state.get("status")
    age = fetch_state.get("age_seconds")

    confirmed = _render_confirmed_fetch_stamp(status, age)
    if confirmed is not None:
        return confirmed

    # "failed" / "no_remote" / "skipped_gate" (or any future fail-open
    # status): never confirmed fresh against origin this boot.
    if age is not None:
        age_txt = _format_age_seconds(age)
        return f"MEMORY: LOCAL — last fetch {age_txt} ago, unverified"
    return "MEMORY: LOCAL — unverified (never synced with origin)"
