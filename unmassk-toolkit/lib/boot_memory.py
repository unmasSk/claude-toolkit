"""
Memory extraction for session-start-boot.py (CRB-04 split).

Owns everything that turns raw git commit history into the boot briefing's
memory data structures: pending Next items, blockers, decisions, memos,
remembers, tombstones, and the crown (canonical entry) override rule.

Moved out of hooks/session-start-boot.py verbatim (Cerberus CRB-04): these
functions all read/derive the same commit-history-backed memory model and
are cohesive as a unit, distinct from main()'s rendering/orchestration
concerns which stay in the hook file.

The on-disk glossary cache (.claude/.unmassk/glossary-cache.json) that lets
extract_glossary()'s full-history scan be skipped on most boots now lives in
lib/boot_glossary_cache.py (further split — that module's I/O concern is
distinct from this file's commit-parsing concern; it imports
extract_glossary() from here, never the reverse).
"""

import re

from constants import TOMBSTONE_KEYS
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

    Moriarty (issue #49 repair round 2, T3 — NOT reverted, see below):
    a previous round made this multi-match (replace the first match,
    delete any further matches) on the theory that a merged-diverged
    memory dict could hand it more than one entry per scope. VERIFIED:
    that theory is false as of this call graph — `_merge_diverged_memory()`
    never calls `_crown_replace` at all, it only concatenates local's and
    the remote-labeled side's lists. The 4 production call sites
    (extract_memory() x2, extract_glossary() x2) all run inside a single
    scan where `decision_scopes`/`memo_scopes` already gate "at most one
    entry per scope" before this function is ever reached, so in practice
    at most one match ever exists here today.
    Kept multi-match anyway (did not simplify to single-match-and-return):
    tests/test_boot_freshness_hardening.py::TestCrownReplaceMultiMatch
    pins the multi-match behavior directly as this function's own unit
    contract (5 assertions, independent of which call sites currently
    exercise it), and this repair round's mandate is to touch test files
    only for mechanical literal changes, never test logic/assertions.
    Simplifying this function back to single-match-and-return would fail
    `test_replaces_first_match_and_drops_later_duplicate_for_same_scope`
    (confirmed by running it against a single-match revert). Flagged for
    Yoda/Bex: either accept this as intentional unit-level defensive
    headroom with no live call site today, or authorize retiring that
    test class in a future round so the implementation can be simplified
    to match actual reachability.
    """
    from parsing import normalize
    if tombstones is not None and normalize(text) in tombstones:
        return
    replaced = False
    i = 0
    while i < len(entries):
        rscope, _rtext, ris_crown = entries[i]
        if rscope == key and not ris_crown:
            if not replaced:
                entries[i] = (key, text, True)
                replaced = True
                i += 1
            else:
                del entries[i]
        else:
            i += 1


def extract_memory(ref: str = "HEAD") -> dict:
    """Extract memory from recent commits.

    `ref` (issue #49, plan Task 4) selects which tip to scan from — defaults
    to HEAD (byte-identical to the pre-#49 behavior). The boot passes
    `origin/<branch>` here when local is strictly behind (so the newest
    memory, which only exists on the remote side, becomes visible instead
    of a stale local Next), or calls it twice (once per side) when
    diverged. Same -z/NUL pipeline and sanitization either way — only the
    log's starting point changes.
    """
    from parsing import scan_trailers_memory as scan_trailers, normalize, parse_scope
    from git_helpers import run_git

    # SEC-CRIT-001 (Argus, defense-in-depth): `ref` is either the "HEAD"
    # constant (always safe) or an upstream tracking ref resolved elsewhere
    # (today always remote-name-prefixed, e.g. "origin/main" — never
    # exploitable in practice) — but this function must not silently depend
    # on that invariant holding forever. Reject anything that could be
    # misread as a git option before it ever reaches a positional argument.
    if not ref or ref.startswith("-"):
        return {}

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
        "log", ref, "-z", f"-n{SCAN_DEPTH}",
        "--pretty=format:%h\x1f%s\x1f%b\x1f%at",
        # SEC-CRIT-001 (Argus, defense-in-depth): trailing `--` — on top of
        # the leading-dash rejection above — so `ref` is never depended on
        # implicitly staying option-safe if this call site is ever changed.
        "--",
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


# ── Boot memory freshness — origin-side reads (issue #49, plan Task 4) ──
#
# extract_memory(ref=...) above is source-agnostic (it just scans whatever
# ref it's given). These three functions are the orchestration layer that
# decides WHICH ref(s) to scan and how to present the result, called from
# hooks/session-start-boot.py's main() with the ahead/behind numbers
# get_ahead_behind() (lib/boot_git_checks.py) already computed.

REMOTE_PROVENANCE_LABEL = " [source: remote]"


def _label_remote_provenance(memory: dict) -> dict:
    """Tag every displayable field of a memory dict as sourced from
    origin/<branch>, not local HEAD. Used when local is strictly behind (the
    incident fix criterion: the newest Next only exists on the remote side,
    and whatever RESUME line it produces must carry a visible remote label,
    not read like an ordinary local entry) and for the remote side of a
    divergence.
    """
    labeled = dict(memory)
    if labeled.get("last_context"):
        labeled["last_context"] = labeled["last_context"] + REMOTE_PROVENANCE_LABEL
    if labeled.get("pending"):
        labeled["pending"] = [
            {**item, "display": item["display"] + REMOTE_PROVENANCE_LABEL}
            for item in labeled["pending"]
        ]
    if labeled.get("blockers"):
        labeled["blockers"] = [b + REMOTE_PROVENANCE_LABEL for b in labeled["blockers"]]
    for key in ("decisions", "memos", "remembers"):
        if labeled.get(key):
            labeled[key] = [
                (label, text + REMOTE_PROVENANCE_LABEL, is_crown)
                for label, text, is_crown in labeled[key]
            ]
    return labeled


def _merge_diverged_memory(local_memory: dict, remote_memory: dict) -> dict:
    """Diverged case (ahead>0 AND behind>0): show BOTH sides, remote side
    labeled, never silently merged/deduped into one truth (plan Task 4 —
    "never auto-merge"). `last_context` stays local's own (it genuinely is
    local HEAD's last context commit; the RESUME section only ever renders
    one `Last:` line, so the remote's own last_context is dropped here, not
    the remote's Next/Decision/Memo/Remember/Blocker items — those are all
    additive below).
    """
    labeled_remote = _label_remote_provenance(remote_memory)
    merged = dict(local_memory)
    for key in ("pending", "blockers", "decisions", "memos", "remembers"):
        merged[key] = list(local_memory.get(key, [])) + list(labeled_remote.get(key, []))
    merged["tombstones"] = (
        set(local_memory.get("tombstones", set())) | set(remote_memory.get("tombstones", set()))
    )
    return merged


def resolve_boot_memory(ahead_n: int, behind_n: int, upstream_ref: str | None) -> dict:
    """Pick which side(s) of history the boot reads memory from (issue #49,
    plan Task 4), given the ahead/behind numbers get_ahead_behind() already
    computed for the BRANCH section (never a second, potentially divergent
    calculation):

      - No upstream at all -> local HEAD, exactly as before #49.
      - Strictly behind (ahead==0, behind>0) -> read from `upstream_ref`
        and label it remote-provenance. This is the incident fix criterion:
        a second machine's newer Next must become visible instead of A's
        own stale local Next.
      - Diverged (both>0) -> read BOTH sides, remote labeled, never merged
        into a single silent truth.
      - Up to date or strictly ahead -> local HEAD, exactly as before.
    """
    if not upstream_ref:
        return extract_memory()
    if behind_n > 0 and ahead_n == 0:
        return _label_remote_provenance(extract_memory(ref=upstream_ref))
    if ahead_n > 0 and behind_n > 0:
        local_memory = extract_memory()
        remote_memory = extract_memory(ref=upstream_ref)
        return _merge_diverged_memory(local_memory, remote_memory)
    return extract_memory()


# Backward-compat re-export, test-compatibility shim ONLY (not a real logic
# dependency — see lib/boot_glossary_cache.py's module docstring for the
# forward direction of this split). tests/test_security_regression.py's
# TestBugAOEnsureRuntimeDirFallbackBranchSymlinkedParent probe loads THIS
# file directly via importlib.util.spec_from_file_location under a
# throwaway module name (not the real "boot_memory"), then calls
# `mod._write_glossary_cache(...)` — that attribute must keep resolving on
# this file even though the real implementation now lives in
# lib/boot_glossary_cache.py. Placed at the very bottom, after every name
# boot_glossary_cache.py's own deferred import needs (extract_glossary) is
# already defined above, so this import cannot deadlock into a circular
# import: boot_glossary_cache.py's top-level code never touches boot_memory
# (its own `from boot_memory import extract_glossary` is deferred inside
# extract_glossary_cached()'s body), so importing it here just runs it
# straight through.
from boot_glossary_cache import (  # noqa: E402
    _get_project_root,
    _glossary_cache_path,
    _read_glossary_cache,
    _write_glossary_cache,
    extract_glossary_cached,
)
