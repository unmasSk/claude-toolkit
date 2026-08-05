"""
Boot git/repo-state checks for session-start-boot.py (split out of
lib/boot_checks.py, Cerberus round-6 LOC audit).

Owns the "read git/repo state for this boot" concern: branch/ahead-behind,
scopes.json, and remote branches — moved here together with their only
callers (parse_branch_keywords(), time_ago()) per the same rationale as the
original round-5 split: lib/boot_checks.py (and now this module) must never
import FROM lib/boot_render.py (confirmed unidirectional DAG:
boot_health/boot_git_checks <- boot_checks <- boot_render). lib/boot_checks.py
re-imports these functions by name so lib/boot_render.py and any direct
`boot_checks.<name>()` caller keep resolving unchanged.

Memory v2 cleanup: the "boot memory freshness" block (fetch_memory_ref() and
everything it depends on — the hardened-fetch env, the own-fetch-success
stamp integration, render_memoria_stamp()) and render_consolidation_section()
were removed with the rest of the v1 memory system (see
docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3) — this module now owns only
branch/upstream/scopes/remote-branches, none of which are memory-specific.

The module's two TIMELINE-only commit-scanning readers (DEUDA.md #7) were
removed separately, later: both were left behind after
render_timeline_section() itself was already gone from lib/boot_render.py,
with zero remaining callers anywhere in the codebase (confirmed by
grepping lib/hooks/bin, and by tracing every re-export in
lib/boot_checks.py's own import/`__all__` chain — nothing beyond that
shim ever referenced them by name).

check_upstream_shares_history() (and its _looks_like_git_option() helper)
went out with that same cut but was reinstated (DEUDA.md #6): it is not
memory-specific either — it also guards two outputs that never depended on
the memory system and still run on every boot: the PULL DIRECTIVE
(_build_pull_directive_lines(), via render_branch_section()) and the
BRANCHES listing (render_branches_section()). Without it, an `@{u}` pointing
at a remote with zero shared history produced a PULL DIRECTIVE git itself
would refuse ("refusing to merge unrelated histories") and listed that
remote's branches as if they belonged to this project.

Pure refactor otherwise: the surviving functions are byte-for-byte identical
to before the split.
"""

import json
import os
import re
from datetime import datetime, timezone
from typing import NamedTuple

from parsing import sanitize_trailer_value

try:
    # SEC-LOW-NEW-05: symlink-safe reader — a symlink planted at
    # git-memory-scopes.json must be rejected exactly like "file absent".
    # Imported defensively: tests/test_migrate_statusline.py stubs out
    # git_helpers with a minimal fake module that predates this helper.
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink


_SAFE_REMOTE_NAME_RE = re.compile(r"^[A-Za-z0-9._-]+$")


def _is_safe_remote_name(name: str) -> bool:
    """Narrow allowlist for a value embedded inside a git ref GLOB pattern
    (`--exclude=refs/remotes/<name>/*`), not passed as a bare argv token.

    Moved here from the now-deleted lib/boot_memory.py (memory v1 removal,
    docs/memoria-v2/PLAN-CONSTRUCCION.md §5.3) — this module is now its only
    caller (get_remote_branches()'s refs/remotes/ scope; the module's
    now-removed TIMELINE-only reader used to be a second caller for its own
    `--exclude` glob, but that reader was dropped as dead code — DEUDA.md
    #7). Intentionally NOT `_looks_like_git_option` below
    (which guards a different threat: a value passed as its OWN positional
    argv element that could be misread as a flag). Here `name` is always
    embedded inside a single `--exclude=...` string built by this module, so
    it can never be split into a separate flag by subprocess.Popen (no shell
    is involved) — the residual risk is `name` containing glob
    metacharacters (`*`, `?`, `[`) or path-like segments that widen the
    exclude pattern beyond the single intended remote. An allowlist (real
    git remote names are always `[A-Za-z0-9._-]+` in practice) is simpler
    and safer here than trying to enumerate every glob-widening character.
    """
    return bool(name) and bool(_SAFE_REMOTE_NAME_RE.match(name))


# BRANCHES section (plugin/boot decision, 2026-07-15 phase 2): cap on how
# many of the resolved remote's branches get listed — reasonable ceiling so
# an unusually active remote with hundreds of branches can't blow up the
# boot log; get_remote_branches() reports the true total separately so a
# cut-off is always stated, never silent (same "(N more ...)" contract as
# REMEMBER/DECISIONS/MEMOS in lib/boot_render.py's
# _render_crowned_capped_section()).
BOOT_MAX_REMOTE_BRANCHES = 20


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
            # (get_remote_branches(), extract_memory() in boot_memory.py).
            # Robust across git versions/locales, unlike %aI below.
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


def _build_pull_directive_lines(behind_n: int, is_dirty: bool) -> list[str]:
    """Escalated PULL directive (issue #49, plan Task 3) — replaces the old
    bare "PULL RECOMMENDED" line. Clean tree: propose `git pull` to the user
    as the FIRST action of the session (decision d958659 — proposed at boot,
    not at close). Dirty tree: warn about the uncommitted work and say
    explicitly NOT to pull, so nothing is silently clobbered.

    DEUDA.md #17: `behind_n` comes from refs/remotes/<remote>/* exactly as
    they sat after whatever `git fetch` last touched them (the boot itself
    no longer fetches) — it can be days old. Both branches below say so
    inline, so the directive never reads as more certain than it is.
    """
    if is_dirty:
        return [
            f"  PULL DIRECTIVE: local is {behind_n} commit(s) behind (not "
            "confirmed against a fresh remote check), but the working tree "
            "is DIRTY (uncommitted changes) — do NOT pull. Inform the user "
            "and leave it untouched."
        ]
    return [
        f"  PULL DIRECTIVE: local is {behind_n} commit(s) behind (not "
        "confirmed against a fresh remote check) — propose `git pull` to "
        "the user as the FIRST action of this session."
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
    branch = sanitize_trailer_value(branch)
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


def get_remote_branches(remote_name: str | None) -> list[tuple[str, str, str, str]]:
    """Every branch of `remote_name` known via `refs/remotes/<remote_name>/*`
    — whatever this repo's most recent `git fetch` of that remote last
    updated. Sorted by author date descending (newest first).

    Returns a list of (branch_name, short_sha, unix_date_str, subject)
    tuples — raw and unformatted, so the caller decides capping/marking/
    sanitizing (mirrors REMEMBER/DECISIONS/MEMOS's own data/render split in
    lib/boot_render.py, not a simpler single-shot format, because this
    section must report a true total for its "(N more)" line — see
    render_branches_section()). Never capped here: the number of branches on
    one remote is bounded by reality (not repo history depth), so reading
    all of them via one `for-each-ref` call is cheap.

    `git for-each-ref` scoped to `refs/remotes/<remote_name>/` ONLY — never
    `git branch -a` (mixes in local branches and every other configured
    remote) and never `--all` (same repo-identity-confusion class
    extract_glossary() guards against, see its own docstring) — this
    function only ever reads the ONE already-resolved remote's own refs.
    Excludes that remote's symbolic HEAD pointer
    (`refs/remotes/<remote_name>/HEAD`, e.g. "origin/HEAD -> origin/main")
    — it is an alias for a branch already listed under its own name, not a
    distinct branch.

    `remote_name=None` (no upstream configured, or a confirmed-unrelated
    upstream — see render_branches_section()'s docstring for how a caller
    keeps an unrelated remote out) means "nothing to list": returns [],
    never raises. `_is_safe_remote_name()` (same allowlist extract_glossary()
    uses for its own `--exclude=` glob) guards `remote_name` before it's
    embedded in the `refs/remotes/.../` ref-pattern argument below — real
    git remote names are always `[A-Za-z0-9._-]+` in practice.

    Never raises (fail-open) — any git/parsing failure collapses to [],
    same fail-open contract as every other reader in this module.
    """
    from git_helpers import run_git

    if not remote_name or not _is_safe_remote_name(remote_name):
        return []

    code, output = run_git([
        "for-each-ref",
        "--sort=-authordate",
        "--format=%(refname:short)\x1f%(objectname:short)\x1f%(authordate:unix)\x1f%(subject)",
        "--",
        f"refs/remotes/{remote_name}/",
    ], log_stderr_on_failure=True)
    if code != 0 or not output:
        return []

    entries: list[tuple[str, str, str, str]] = []
    prefix = f"{remote_name}/"
    for line in output.split("\n"):
        parts = line.strip().split("\x1f", 3)
        if len(parts) < 4:
            continue
        ref_short, sha, date_str, subject = parts
        if not ref_short.startswith(prefix):
            # Also excludes the remote's symbolic HEAD alias: git's
            # `%(refname:short)` renders refs/remotes/<remote_name>/HEAD as
            # the BARE remote name (e.g. "origin", verified empirically —
            # never "origin/HEAD"), which already fails this startswith(prefix)
            # check on its own -- no separate `== f"{remote_name}/HEAD"`
            # comparison is reachable here.
            continue  # not this remote's own ref
        entries.append((ref_short[len(prefix):], sha, date_str, subject))
    return entries


def render_branches_section(remote_name: str | None, current_branch: str | None) -> list[str]:
    """Render the BRANCHES section: every branch known locally for
    `remote_name` (via `refs/remotes/<remote_name>/*`), newest commit first,
    current branch marked — Bex (2026-07-15 phase 2): "just so they're known
    to be there", deliberately no elaborate per-branch state beyond name +
    last commit.

    `remote_name=None` renders nothing (fail-open, same as every other
    render_*_section() in this module returning [] when there's nothing to
    show).

    DEUDA.md #17: these branches come from refs/remotes/<remote>/* exactly
    as they sat after whatever `git fetch` last touched them (the boot
    itself no longer fetches, per get_remote_branches()'s own docstring) —
    the section says so with its own line, so the list never reads as a
    live remote state it isn't.
    """
    lines: list[str] = []
    if not remote_name:
        return lines

    branches = get_remote_branches(remote_name)
    if not branches:
        return lines

    shown = branches[:BOOT_MAX_REMOTE_BRANCHES]
    lines.append(f"BRANCHES ({remote_name}):")
    lines.append("  (not confirmed against a fresh remote check — reflects the last fetch)")
    for branch_name, sha, date_str, subject in shown:
        safe_name = sanitize_trailer_value(branch_name)
        marker = " (current)" if current_branch and branch_name == current_branch else ""
        lines.append(f"  {safe_name}{marker}: {sha} {sanitize_trailer_value(subject)} | {time_ago(date_str)}")
    remaining = len(branches) - len(shown)
    if remaining > 0:
        lines.append(f"  ({remaining} more branch(es) not shown, {len(branches)} total)")
    lines.append("")
    return lines


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
        safe_name = sanitize_trailer_value(str(scope_name))
        desc = scope_info.get("description", "") if isinstance(scope_info, dict) else str(scope_info)
        safe_desc = sanitize_trailer_value(str(desc))
        children = scope_info.get("children", {}) if isinstance(scope_info, dict) else {}
        if children:
            safe_children = [sanitize_trailer_value(str(k)) for k in children]
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
