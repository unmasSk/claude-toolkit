"""
Memory extraction for session-start-boot.py (CRB-04 split).

Owns everything that turns raw git commit history into the boot briefing's
memory data structures: pending Next items, blockers, decisions, memos,
remembers, tombstones, and the crown (canonical entry) override rule. Also
owns the on-disk glossary cache (.claude/.unmassk/glossary-cache.json) that
lets extract_glossary()'s full-history scan be skipped on most boots.

Moved out of hooks/session-start-boot.py verbatim (Cerberus CRB-04): these
functions all read/derive the same commit-history-backed memory model and
are cohesive as a unit, distinct from main()'s rendering/orchestration
concerns which stay in the hook file.
"""

import json
import os
import re
from datetime import datetime, timezone

from constants import TOMBSTONE_KEYS
try:
    # SEC-CRIT-001 / SEC-MED-NEW-02: symlink-safe reader/writer for
    # glossary-cache.json. Imported defensively: tests/test_migrate_statusline.py
    # stubs out git_helpers with a minimal fake module that predates this
    # helper, and this module must still import cleanly against that stub
    # (it is imported transitively by session-start-boot.py even when only
    # _migrate_stale_context_writer_statusline() is under test).
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink
# NOTE: the `parsing` helpers below (scan_trailers_memory, normalize,
# parse_scope, sanitize_trailer_value) AND the `git_helpers` helpers
# (run_git, ensure_gitignore) are deliberately imported INSIDE each function
# that uses them, not once here at module level. lib/boot_memory.py is a
# real, stably-named module — the first `import boot_memory` anywhere in a
# process caches it for the rest of that process. If that first import
# happens to run while some other test has temporarily replaced
# sys.modules["parsing"] or sys.modules["git_helpers"] with a stub
# (tests/test_migrate_statusline.py does exactly this, restoring it again in
# a `finally` block), a module-level `from parsing import X` or `from
# git_helpers import Y` here would freeze X/Y to the STUB's version forever,
# even after the stub is restored — because the binding lives in
# boot_memory's own namespace, set once, never re-evaluated. A deferred
# (function-body) import re-reads sys.modules[...] on every call, so it
# always sees whatever is really installed by the time this code runs.
# hooks/session-start-boot.py itself doesn't need this: tests load it via
# spec_from_file_location + exec_module without caching it under a stable
# name, so it always re-executes fresh and never carries stale bindings.


SCAN_DEPTH = 30
MAX_PENDING = 30
MAX_BLOCKERS = 20
MAX_DECISIONS = 20
MAX_MEMOS = 10

# Glossary: deeper scan for full memory picture
GLOSSARY_MAX_DECISIONS = 10
GLOSSARY_MAX_MEMOS = 10

GLOSSARY_CACHE_TTL = 86400  # 24 hours


def _sanitize_trailer_value(text: str) -> str:
    """Strip injection characters from trailer values. Delegates to canonical sanitizer in lib/parsing."""
    from parsing import sanitize_trailer_value as _sanitize_canonical
    return _sanitize_canonical(text)


def _crown_replace(
    entries: list[tuple[str, str, bool]],
    key: str,
    text: str,
    tombstones: set[str] | None = None,
) -> None:
    """Replace the existing non-crowned entry for `key` with a crowned one, in place.

    Single implementation of the "crown beats a non-crowned entry for the
    same scope" override, reused by extract_memory(), extract_glossary(),
    and main()'s glossary-merge for Decisions/Memos/Remembers (Cerberus
    found this exact loop shape repeated 6 times).

    CRB-01 fix: when `tombstones` is provided, the replace is a no-op if
    `text` (the crowned commit's own value) has been explicitly retired —
    a retired crowned entry must never resurrect and overwrite a newer,
    active, never-retired entry for the same scope. Decisions have no
    tombstone concept, so their call sites simply omit `tombstones`.
    """
    from parsing import normalize
    if tombstones is not None and normalize(text) in tombstones:
        return
    for i, (rscope, _rtext, ris_crown) in enumerate(entries):
        if rscope == key and not ris_crown:
            entries[i] = (key, text, True)
            return


def extract_memory() -> dict:
    """Extract memory from recent commits."""
    from parsing import scan_trailers_memory as scan_trailers, normalize, parse_scope
    from git_helpers import run_git

    # SEC-CRIT-NEW-01 (Argus): record boundaries use `-z` (NUL, \x00) instead
    # of an embedded \x1e in the --pretty=format string. A commit body CAN
    # contain a literal \x1e byte (it's an ordinary control character as far
    # as git is concerned) — str.split()-ing on it let a single real commit
    # forge an entire fake record (sha/scope/Decision text chosen by an
    # attacker). A commit message can never contain a raw NUL byte (git
    # truncates/rejects it at the object level), so splitting on \x00 has no
    # forgeable equivalent. \x1f remains as the FIELD separator within a
    # single record — already confirmed inert on its own (fixed maxsplit
    # below caps the field count, and \x1f can't start a new line for
    # scan_trailers_memory's line-based trailer regex either).
    code, log_output = run_git([
        "log", "-z", f"-n{SCAN_DEPTH}",
        "--pretty=format:%h\x1f%s\x1f%b\x1f%at"
    ])
    if code != 0 or not log_output:
        return {}

    tombstones: set[str] = set()
    commits = log_output.split("\x00")
    pending: list[dict] = []
    blockers: list[str] = []
    decisions: list[tuple[str, str, bool]] = []  # (scope, text, is_crown)
    memos: list[tuple[str, str, bool]] = []      # (scope, text, is_crown)
    remembers: list[tuple[str, str, bool]] = []  # (scope, text, is_crown)
    last_context: str = ""
    decision_scopes: set[str] = set()
    memo_scopes: set[str] = set()
    remember_seen: set[str] = set()  # dedup by normalized text

    # Retracted crown hashes — collected up front over the same commit range.
    # A retraction only ever targets a commit that is chronologically older
    # than itself, so a single forward pass is enough regardless of log order.
    retracted_crowns: set[str] = set()
    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f", 3)
        if len(parts) < 3:
            continue
        rc_trailers = scan_trailers(parts[2])
        if "Retract-Crown" in rc_trailers:
            retracted_crowns.add(rc_trailers["Retract-Crown"].strip())

    # Per-scope "has the most recent crown for this scope already been
    # decided" tracker. Only the single newest crown commit per scope is
    # ever eligible to become active — once resolved (active or retracted),
    # older crowns for the same scope must stay inert forever (they must
    # never resurface just because the newest one got retracted).
    crown_decision_resolved: set[str] = set()
    crown_memo_resolved: set[str] = set()

    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f", 3)
        if len(parts) < 3:
            continue
        sha, subject, body = parts[0], parts[1], parts[2]
        ts = 0
        if len(parts) >= 4:
            try:
                ts = int(parts[3].strip()) if parts[3].strip() else 0
            except ValueError:
                ts = 0
        trailers = scan_trailers(body)

        # Last context bookmark — canonical criterion: type starts with "context("
        # after stripping leading emoji/whitespace (same predicate as get_last_context_time)
        if not last_context:
            _cleaned = re.sub(r"^[^\w#]+", "", subject).strip()
            if _cleaned.lower().startswith("context("):
                # SEC-CRIT-NEW-04: the raw commit subject is untrusted
                # (attacker-controlled commit message) and is printed
                # verbatim on the RESUME section's `Last:` line — sanitize
                # it the same way Decision/Memo/Remember values already are.
                last_context = f"{sha} {_sanitize_trailer_value(subject)}"

        # SEC-CRIT-NEW-04: parse_scope(subject) is untrusted (attacker-
        # controlled commit subject) and feeds the `label`/`scope_prefix`
        # embedded verbatim in Decision/Memo/Remember/Next entries below —
        # sanitize it here, once, same as the trailer VALUE right next to it.
        scope = _sanitize_trailer_value(parse_scope(subject) or "")
        label = f"({scope})" if scope else "(global)"

        # Tombstones (GC markers) — collect in same pass
        for key in TOMBSTONE_KEYS:
            if key in trailers:
                tombstones.add(normalize(trailers[key]))

        # Pending items (include subject for branch-relevance scoring)
        if "Next" in trailers and len(pending) < MAX_PENDING:
            text = _sanitize_trailer_value(trailers["Next"])
            if normalize(text) not in tombstones:
                scope_prefix = f"({scope}) " if scope else ""
                issue_match = re.search(r"#(\d+)", text)
                pending.append({
                    "sha": sha,
                    "scope": scope,
                    "text": text,
                    "display": f"{sha}: {scope_prefix}{text}",
                    "issue": int(issue_match.group(1)) if issue_match else None,
                    "timestamp": ts,
                })

        # Blockers
        if "Blocker" in trailers and len(blockers) < MAX_BLOCKERS:
            text = _sanitize_trailer_value(trailers["Blocker"])
            if normalize(text) not in tombstones:
                blockers.append(f"{sha}: {text}")

        # Decisions (one per scope; crowned entries bypass MAX_DECISIONS cap)
        if "Decision" in trailers:
            is_crown = False
            if trailers.get("Crown") == "Decision":
                if scope not in crown_decision_resolved:
                    crown_decision_resolved.add(scope)
                    is_crown = sha not in retracted_crowns
                # else: an older crown for this scope was already superseded
                # (active or retracted) — never let it resurface.
            if scope not in decision_scopes:
                if len(decisions) < MAX_DECISIONS or is_crown:
                    decision_scopes.add(scope)
                    decisions.append((label, _sanitize_trailer_value(trailers["Decision"]), is_crown))
            elif is_crown:
                # Crown beats a non-crowned entry for the same scope
                _crown_replace(decisions, label, _sanitize_trailer_value(trailers["Decision"]))

        # Memos (one per scope, skip tombstoned; crowned entries bypass MAX_MEMOS cap)
        if "Memo" in trailers:
            text = _sanitize_trailer_value(trailers["Memo"])
            is_crown = False
            if trailers.get("Crown") == "Memo":
                if scope not in crown_memo_resolved:
                    crown_memo_resolved.add(scope)
                    is_crown = sha not in retracted_crowns
                # else: an older crown for this scope was already superseded
                # (active or retracted) — never let it resurface.
            if scope not in memo_scopes and normalize(text) not in tombstones:
                if len(memos) < MAX_MEMOS or is_crown:
                    memo_scopes.add(scope)
                    memos.append((label, text, is_crown))
            elif is_crown and scope in memo_scopes:
                _crown_replace(memos, label, text, tombstones)

        # Remembers (personality notes between sessions, skip tombstoned)
        if "Remember" in trailers:
            text = _sanitize_trailer_value(trailers["Remember"])
            norm = normalize(text)
            if norm not in remember_seen and norm not in tombstones:
                remember_seen.add(norm)
                is_crown = (trailers.get("Crown") == "Remember") and (sha not in retracted_crowns)
                remembers.append((label, text, is_crown))

    return {
        "last_context": last_context,
        "pending": pending,
        "blockers": blockers,
        "decisions": decisions,
        "memos": memos,
        "remembers": remembers,
        "tombstones": tombstones,
    }


def extract_glossary() -> dict:
    """Extract a full glossary of decisions and memos from the entire git history.

    Goes deeper than extract_memory() — scans ALL commits, not just last 30.
    Returns deduplicated lists by scope (most recent wins per scope).
    """
    from parsing import scan_trailers_memory as scan_trailers, normalize, parse_scope
    from git_helpers import run_git

    # SEC-CRIT-NEW-01: same NUL-separated record boundary fix as
    # extract_memory() above — see the comment there for why -z closes the
    # control-byte record-forgery hole for good.
    code, log_output = run_git([
        "log", "-z", "--all", "-n500",
        "--pretty=format:%h\x1f%s\x1f%b"
    ])
    if code != 0 or not log_output:
        return {"decisions": [], "memos": [], "remembers": []}

    decisions: list[tuple[str, str, bool]] = []
    memos: list[tuple[str, str, bool]] = []
    remembers: list[tuple[str, str, bool]] = []
    decision_scopes: set[str] = set()
    memo_scopes: set[str] = set()
    remember_seen: set[str] = set()
    glossary_tombstones: set[str] = set()

    commits = log_output.split("\x00")

    # Retracted crown hashes, collected up front over the same range (mirrors
    # extract_memory() — see notes there on why a single forward pass suffices).
    retracted_crowns: set[str] = set()
    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f", 2)
        if len(parts) < 3:
            continue
        rc_trailers = scan_trailers(parts[2])
        if "Retract-Crown" in rc_trailers:
            retracted_crowns.add(rc_trailers["Retract-Crown"].strip())

    # Per-scope "newest crown already decided" trackers — see extract_memory()
    # for why only the single newest crown per scope may ever become active.
    crown_decision_resolved: set[str] = set()
    crown_memo_resolved: set[str] = set()

    for entry in commits:
        entry = entry.strip()
        if not entry:
            continue
        parts = entry.split("\x1f", 2)
        if len(parts) < 3:
            continue
        sha, subject, body = parts[0], parts[1], parts[2]
        trailers = scan_trailers(body)
        # SEC-CRIT-NEW-04: same untrusted-scope sanitization as extract_memory()
        scope = _sanitize_trailer_value(parse_scope(subject) or "")
        label = f"({scope})" if scope else "(global)"

        # Collect tombstones from the full glossary range
        for key in TOMBSTONE_KEYS:
            if key in trailers:
                glossary_tombstones.add(normalize(trailers[key]))

        if "Decision" in trailers:
            text = _sanitize_trailer_value(trailers["Decision"])
            is_crown = False
            if trailers.get("Crown") == "Decision":
                if scope not in crown_decision_resolved:
                    crown_decision_resolved.add(scope)
                    is_crown = sha not in retracted_crowns
            if scope not in decision_scopes:
                if len(decisions) < GLOSSARY_MAX_DECISIONS or is_crown:
                    decision_scopes.add(scope)
                    decisions.append((label, text, is_crown))
            elif is_crown:
                # Crown beats a non-crowned entry for the same scope already in the glossary
                _crown_replace(decisions, label, text)

        if "Memo" in trailers:
            text = _sanitize_trailer_value(trailers["Memo"])
            is_crown = False
            if trailers.get("Crown") == "Memo":
                if scope not in crown_memo_resolved:
                    crown_memo_resolved.add(scope)
                    is_crown = sha not in retracted_crowns
            if scope not in memo_scopes:
                if len(memos) < GLOSSARY_MAX_MEMOS or is_crown:
                    memo_scopes.add(scope)
                    memos.append((label, text, is_crown))
            elif is_crown:
                # CRB-01: a retired crowned Memo must not resurrect and evict
                # a newer, active, never-retired entry for the same scope.
                _crown_replace(memos, label, text, glossary_tombstones)

        if "Remember" in trailers:
            text = _sanitize_trailer_value(trailers["Remember"])
            norm = normalize(text)
            if norm not in remember_seen:
                remember_seen.add(norm)
                is_crown = (trailers.get("Crown") == "Remember") and (sha not in retracted_crowns)
                remembers.append((label, text, is_crown))

    return {
        "decisions": decisions,
        "memos": memos,
        "remembers": remembers,
        "tombstones": glossary_tombstones,
    }


_project_root_cache: str | None = None


def _get_project_root() -> str | None:
    """Get project root, cached for the process."""
    from git_helpers import run_git

    global _project_root_cache
    if _project_root_cache is None:
        code, root = run_git(["rev-parse", "--show-toplevel"])
        _project_root_cache = root if code == 0 and root else ""
    return _project_root_cache or None


def _glossary_cache_path() -> str | None:
    """Return path to .claude/.unmassk/glossary-cache.json, or None if no project root."""
    root = _get_project_root()
    if not root:
        return None
    return os.path.join(root, ".claude", ".unmassk", "glossary-cache.json")


def _read_glossary_cache() -> dict | None:
    """Read glossary cache if fresh. Returns None if stale or missing."""
    from git_helpers import run_git

    path = _glossary_cache_path()
    if not path or not os.path.isfile(path):
        return None
    try:
        # SEC-MED-NEW-02: symlink-safe read, symmetric with
        # _write_glossary_cache()'s existing open_no_follow_symlink() guard —
        # a symlink planted at this path (pointing outside the repo) must be
        # rejected exactly like "no valid cache", not silently followed.
        with open_no_follow_symlink(path, "r") as f:
            cache = json.load(f)
        # Check staleness
        generated = cache.get("generated_at", "")
        if generated:
            gen_dt = datetime.fromisoformat(generated)
            if gen_dt.tzinfo is None:
                gen_dt = gen_dt.replace(tzinfo=timezone.utc)
            age = (datetime.now(timezone.utc) - gen_dt).total_seconds()
            if age > GLOSSARY_CACHE_TTL:
                return None
        # Check schema_version
        if cache.get("schema_version") != 1:
            return None
        # Check that decisions are 3-element lists
        decisions = cache.get("decisions", [])
        if decisions and len(decisions[0]) != 3:
            return None
        # Check HEAD match
        code, head_sha = run_git(["rev-parse", "HEAD"])
        if code != 0:
            return None
        if cache.get("head_sha") != head_sha:
            return None
        return cache
    except (json.JSONDecodeError, OSError, ValueError, KeyError):
        return None


def _write_glossary_cache(glossary: dict) -> None:
    """Write glossary cache to .claude/.unmassk/glossary-cache.json."""
    from git_helpers import ensure_gitignore, run_git

    path = _glossary_cache_path()
    if not path:
        return
    code, head_sha = run_git(["rev-parse", "HEAD"])
    if code != 0:
        return
    # tombstones is a set — serialize as sorted list for JSON stability
    raw_tombstones = glossary.get("tombstones", set())
    cache = {
        "schema_version": 1,
        "head_sha": head_sha,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "decisions": glossary.get("decisions", []),
        "memos": glossary.get("memos", []),
        "remembers": glossary.get("remembers", []),
        "tombstones": sorted(raw_tombstones),
    }
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open_no_follow_symlink(path, "w") as f:
            json.dump(cache, f, indent=2)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        root = _get_project_root()
        if root:
            ensure_gitignore(root)
    except OSError:
        pass


def extract_glossary_cached() -> dict:
    """Extract glossary, using cache if available."""
    cached = _read_glossary_cache()
    if cached:
        return {
            "decisions": cached.get("decisions", []),
            "memos": cached.get("memos", []),
            "remembers": cached.get("remembers", []),
            "tombstones": set(cached.get("tombstones", [])),
        }
    glossary = extract_glossary()
    _write_glossary_cache(glossary)
    return glossary
