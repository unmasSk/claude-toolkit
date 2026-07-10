"""
Own fetch-success stamp I/O for lib/boot_git_checks.py (issue #60, boot
MEMORY freshness relabel — decisions 90d096d / v2 and 787b698 / v3).

Split out of lib/boot_git_checks.py (round 3, Cerberus S2 — that file
crossed 1000 LOC in the v2 round alone), mirroring lib/boot_glossary_cache.py's
own earlier split off lib/boot_memory.py: this module owns the on-disk "own
success stamp" (.claude/.unmassk/boot-fetch-stamp.json) that replaced
.git/FETCH_HEAD's mtime as the freshness/rate-limit signal for the boot's
memory fetch — path resolution, read (with identity + schema validation, two
strictness levels), atomic write, and the rate-limit decision built on top of
the read.

lib/boot_git_checks.py re-imports every public name below BY ITS ORIGINAL
NAME (see the import block near its own FETCH_TIMEOUT_SECONDS), so every
existing caller/test — including the pre-existing TestReadOwnStampAgeDirectCalls
pinning class, which calls `boot_git_checks._read_own_stamp_age(...)` and
reads `boot_git_checks._OWN_STAMP_FILENAME` / `._OWN_STAMP_SCHEMA_VERSION`
directly — keeps resolving exactly as before. This is a pure extraction, no
public-API/contract change.

Why the identity model has two strictness levels (v3, decision 787b698):
Moriarty v2 showed that matching a stamp by remote ALIAS + branch alone
("origin"/"main") lets a stamp file copied verbatim between two unrelated
repos that merely share that common alias/branch convention (template
scaffolding, backup, dotfiles-sync — no adversary or git operation required)
pass as "this project's own confirmed sync", short-circuiting the rate-limit
gate before a real fetch is ever attempted. `_read_own_stamp_age()` is the
STRICT check (remote + branch + real URL + schema, used to grant
"rate_limited"/"synced" — the only place a real fetch can be skipped).
`_read_stamp_age_by_alias_only()` is a separate, deliberately narrower
fallback used ONLY by `boot_git_checks._check_remote_is_live()`'s dead-remote
branch (Cerberus S1) to preserve an INFORMATIVE age for the "LOCAL — last
fetch Xs ago, unverified" wording when this repo's OWN remote entry has
disappeared entirely — safe because that caller's status is always
"no_remote", never "rate_limited"/"fetched", so this looser match can never
skip a real fetch or produce a false "synced" claim.

What this identity model does NOT cover: an attacker (or any tool) with
local write access to THIS repo's own .claude/.unmassk/ directory can always
hand-craft a byte-for-byte "correct" stamp (right URL, right branch, right
schema) — that is local write compromise of this repo itself, the same
threat class every other gitignored, locally-writable cache file in this
codebase already sits outside the trust boundary for (glossary-cache.json,
boot-log-latest.txt, ...), not a hole specific to this mechanism. A
tampered/backdated-but-otherwise-matching stamp can still only ever cause an
extra (harmless) or a skipped fetch attempt — the same fail-open philosophy
as every other branch in this module.
"""

import json
import os
import tempfile
import time
from datetime import datetime, timezone

try:
    # Symlink-safe reader, same rationale/pattern as every other generated-
    # file reader in this codebase (lib/boot_glossary_cache.py,
    # lib/boot_git_checks.py's own SCOPES reader, etc.). Imported
    # defensively: tests/test_migrate_statusline.py stubs out git_helpers
    # with a minimal fake module that predates this helper, and this module
    # is reachable transitively during that stub window (via
    # lib/boot_git_checks.py, imported at hooks/session-start-boot.py's
    # module level).
    from git_helpers import open_no_follow_symlink
except ImportError:
    # T3-1 (Cerberus): shared fallback, not a second hand-copied
    # reimplementation — see lib/_symlink_safe_open.py.
    from _symlink_safe_open import open_no_follow_symlink_fallback as open_no_follow_symlink

try:
    # SEC-HIGH-003 pattern: canonical .claude/.unmassk/ creation helper +
    # symlinked-parent guard for the write path. Imported defensively for
    # the same reason as open_no_follow_symlink above.
    from git_helpers import ensure_runtime_dir, verify_path_within_project
except ImportError:
    ensure_runtime_dir = None
    verify_path_within_project = None


_OWN_STAMP_FILENAME = "boot-fetch-stamp.json"

# v3 (decision 787b698): bumped 1 -> 2 because the stamp's SHAPE changed —
# a "remote_url" field is now mandatory for a stamp to ever be trusted by
# the strict reader. A schema_version the reader doesn't recognize collapses
# to "no evidence at all" (see _load_own_stamp() below), so a pre-v3
# schema=1 stamp (written before this field existed, by an older toolkit
# version) is correctly treated as absent rather than partially trusted —
# the same fail-open-toward-fetching outcome a missing remote_url field
# would already produce on its own; the bump just makes that explicit and
# self-documenting instead of relying on an incidental `None != url` result.
_OWN_STAMP_SCHEMA_VERSION = 2

# Skip the fetch if the own success stamp (below) is younger than this.
# Read by boot_git_checks.fetch_memory_ref() via the re-export.
FETCH_RATE_LIMIT_SECONDS = 300


def _own_stamp_path(project_root: str) -> str | None:
    """Resolve the own-success-stamp path, verified to stay inside
    project_root (SEC-HIGH-003 pattern: a symlinked .claude parent must not
    let this escape the repo). Returns None on any resolution failure —
    including the test-stub window where verify_path_within_project itself
    could not be imported — callers must treat None exactly like "no
    stamp", fail-open toward fetching.
    """
    if verify_path_within_project is None:
        return None
    path = os.path.join(project_root, ".claude", ".unmassk", _OWN_STAMP_FILENAME)
    try:
        return verify_path_within_project(path, project_root)
    except OSError:
        return None


def _load_own_stamp(project_root: str) -> tuple[dict | None, float | None]:
    """Read+validate the own-success-stamp file's shape and schema_version
    ONLY — no identity (remote/branch/URL) comparison, that is each
    caller's own job (_read_own_stamp_age() for the strict remote+branch
    +URL match, _read_stamp_age_by_alias_only() for the narrower
    alias-only fallback). Shared here so both readers agree byte-for-byte
    on what counts as a structurally valid, current-schema stamp, and on
    how its age is measured.

    Returns (data, age_seconds) on success, or (None, None) on ANY
    failure: missing file, symlink, hard link, unreadable/corrupt/empty/
    malformed-JSON content, wrong top-level shape (not a dict), or an
    unrecognized schema_version (v3, decision 787b698 — Dante RED 2 /
    Cerberus nitpick 2: a stamp from a different schema must never be
    partially trusted, exactly as untrustworthy as an absent stamp until
    this reader is updated to understand it).

    Age is the STAMP FILE'S OWN mtime, fstat'd on the already-open
    descriptor (never a separate os.path.getmtime() call afterwards — that
    would reopen a TOCTOU gap between the symlink-safety check and the
    measurement this function replaces FETCH_HEAD's mtime with). Never
    derived from any field inside the JSON content, and never from
    .git/FETCH_HEAD. A negative age (this machine's clock behind the
    stamp's mtime, or any other reason the mtime reads as "future") is
    returned as-is, never clamped to 0 — callers decide what a negative
    age means (the rate-limit check treats it as "not fresh", same
    contract the old FETCH_HEAD-mtime gate had).

    Never raises — every expected failure mode collapses to (None, None).
    """
    path = _own_stamp_path(project_root)
    if path is None:
        return None, None
    try:
        # Symlink-safe read (SEC-CRIT-001/SEC-MED-NEW-02 pattern, same as
        # every other generated-file reader in this codebase):
        # reject_hardlinks=True — this file is toolkit-generated-only
        # (never a legitimate user file), same rationale as
        # glossary-cache.json's read guard (lib/boot_glossary_cache.py).
        with open_no_follow_symlink(path, "r", reject_hardlinks=True) as f:
            mtime = os.fstat(f.fileno()).st_mtime
            content = f.read()
        data = json.loads(content)
        if not isinstance(data, dict) or data.get("schema_version") != _OWN_STAMP_SCHEMA_VERSION:
            return None, None
        return data, time.time() - mtime
    except (OSError, ValueError, TypeError):
        # OSError: missing file / symlink / hard link / permission error.
        # ValueError: json.JSONDecodeError (a ValueError subclass) for
        # corrupt/empty content. TypeError: defense-in-depth for a
        # malformed .get() target. Fail-open toward fetching in every case
        # — this stamp is a best-effort optimization, never a trust
        # boundary.
        return None, None


def _read_own_stamp_age(
    project_root: str,
    remote_name: str,
    remote_branch: str,
    remote_url: str | None = None,
) -> float | None:
    """Age (seconds) of this project's own last confirmed-successful fetch
    against `remote_name`/`remote_branch`/`remote_url`, or None when there
    is no valid evidence for that EXACT identity.

    `remote_url` defaults to None only for backward compatibility with
    direct-call callers that pre-date v3 (e.g.
    tests/test_boot_freshness_hardening.py::TestReadOwnStampAgeDirectCalls,
    which exercises the malformed-shape paths above and never reaches the
    identity comparison at all) — every real production call site
    (boot_git_checks._check_own_stamp_rate_limit(), itself called only
    after _resolve_fetch_target() has already resolved a concrete URL)
    always passes a real, non-None value.

    A mismatch on ANY of remote/branch/URL collapses to the exact same "no
    evidence" outcome as a missing file (v3, decision 787b698 — Moriarty's
    cross-repo stamp-copy PoC: two repos sharing the "origin"/"main" alias
    convention but with genuinely different remotes must never let one
    repo's real stamp be read as evidence for the other's). See this
    module's own docstring for the two-strictness-level design and what it
    does/doesn't cover.

    Never raises — delegates every failure mode to _load_own_stamp().
    """
    data, age = _load_own_stamp(project_root)
    if data is None:
        return None
    if (
        data.get("remote") != remote_name
        or data.get("branch") != remote_branch
        or data.get("remote_url") != remote_url
    ):
        return None
    return age


def _read_stamp_age_by_alias_only(project_root: str, remote_name: str, remote_branch: str) -> float | None:
    """Cerberus S1 (round 3, decision 787b698): narrower, INFORMATIONAL-ONLY
    fallback for boot_git_checks._check_remote_is_live()'s dead-remote
    branch — used exclusively when `git remote get-url` itself fails
    (the remote entry is gone), so there is no live URL left to compare
    against for the strict check above.

    Deliberately compares remote/branch ONLY, never the URL — there is
    nothing to compare it to once the remote itself no longer resolves.
    This is safe SOLELY because the caller's own returned status on that
    branch is ALWAYS "no_remote", never "rate_limited"/"fetched": the age
    this returns can only ever feed the "LOCAL — last fetch Xs ago,
    unverified" wording, never a "remote (synced ...)" claim, and it can
    never cause a real fetch attempt to be skipped (the caller always
    still returns an early "no_remote" result forcing a real refetch next
    time the gate is checked past the window). Do NOT reuse this helper
    anywhere its result could feed a rate-limit or "synced" decision.

    Never raises — delegates every failure mode to _load_own_stamp().
    """
    data, age = _load_own_stamp(project_root)
    if data is None:
        return None
    if data.get("remote") != remote_name or data.get("branch") != remote_branch:
        return None
    return age


def _write_own_stamp(project_root: str, remote_name: str, remote_branch: str, remote_url: str | None) -> None:
    """Record a confirmed-successful fetch against remote_name/remote_branch
    /remote_url. Called ONLY by boot_git_checks._run_hardened_fetch(),
    immediately after its real `git fetch` exits 0.

    `remote_url` is required (v3, decision 787b698): an unresolved/empty/
    option-shaped URL at write time (see boot_git_checks._check_remote_is_live()'s
    own guard, which is what actually prevents such a value from ever
    reaching this function in the real fetch path) must never produce a
    stamp that LOOKS like confirmed identity evidence for a future strict
    read — this function no-ops rather than writing a claim with a hole in
    it, so the next boot simply re-fetches for real instead of trusting a
    partial record.

    Atomic (temp file + os.replace): a crash or a concurrent boot mid-write
    can never leave a truncated/partial stamp for the next read to trip
    over. os.replace() itself never follows a symlink planted at the
    DESTINATION — it unlinks/relinks the directory entry, exactly like
    every atomic rename — which is what makes the destination side of this
    write symlink-safe by construction, unlike a plain open(path, "w")
    would be (Windows-safe too: os.replace() has been atomic on Windows
    since Python 3.3, unlike the older os.rename()). The temp file is
    created via tempfile.mkstemp() in the SAME directory (same filesystem,
    so the final os.replace() is atomic across POSIX and Windows alike) —
    mkstemp()'s own O_EXCL-based creation at a randomly-generated name is
    already immune to a pre-planted symlink, so a separate
    open_no_follow_symlink() call is not needed for the temp file itself
    (it IS needed, and used, for every READ of the final path — see
    _load_own_stamp() above).

    Never raises (fail-open, same contract as the rest of this module) —
    any failure here must never break the boot or mask the fetch's own
    real success.
    """
    if ensure_runtime_dir is None or verify_path_within_project is None:
        return
    if not remote_url:
        return
    tmp_path = None
    try:
        runtime_dir = ensure_runtime_dir(project_root)
        final_path = verify_path_within_project(
            os.path.join(runtime_dir, _OWN_STAMP_FILENAME), project_root
        )
        payload = json.dumps({
            "schema_version": _OWN_STAMP_SCHEMA_VERSION,
            "remote": remote_name,
            "branch": remote_branch,
            "remote_url": remote_url,
            # Debug-only, human-readable — the canonical age signal is
            # ALWAYS the final file's own mtime (see _load_own_stamp()'s
            # docstring); this field is never read back for that purpose.
            "written_at": datetime.now(timezone.utc).isoformat(),
        })
        fd, tmp_path = tempfile.mkstemp(
            dir=runtime_dir, prefix=f".{_OWN_STAMP_FILENAME}.", suffix=".tmp"
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(payload)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, final_path)
        tmp_path = None  # replaced — no longer ours to clean up
        try:
            os.chmod(final_path, 0o600)
        except OSError:
            # Windows has no POSIX permission-bit model — this os.chmod()
            # call (like every other 0o600 call in this codebase, e.g.
            # lib/boot_glossary_cache.py's own glossary-cache.json write)
            # does not deny read/write access to other accounts/groups on
            # that platform; see lib/boot_git_checks.py's _ASKPASS_FAILFAST
            # comment block for more on this project's general POSIX-vs-
            # Windows security posture. Best-effort hardening only — a
            # failure here (on any platform) is always silently ignored,
            # same fail-open policy as the rest of this write.
            pass
        from git_helpers import ensure_gitignore
        ensure_gitignore(project_root)
    except (OSError, ValueError, TypeError):
        pass
    finally:
        if tmp_path is not None:
            try:
                os.remove(tmp_path)
            except OSError:
                pass


def _check_own_stamp_rate_limit(
    project_root: str,
    remote_name: str,
    remote_branch: str,
    remote_url: str | None = None,
) -> tuple[dict | None, float | None]:
    """Rate-limit check against the own success stamp (replaces the old
    FETCH_HEAD-mtime half of the gate). Returns (early_result, age):
    `early_result` is not None when the caller must return it immediately
    (still inside the rate-limit window, STRICT identity match — remote +
    branch + URL + schema, see _read_own_stamp_age()); `age` is the
    stamp's current age either way (or None), reused by the caller's final
    "failed" status so a failed refetch still reports how long ago the
    LAST successful sync against this EXACT identity was.

    `remote_url` defaults to None for the same backward-compatibility
    reason documented on _read_own_stamp_age() itself.

    Moriarty #1 (clock skew), preserved exactly: a NEGATIVE age means the
    stamp's mtime is in the FUTURE relative to this machine's clock — not
    freshness, a broken measurement. Only a genuine non-negative age
    inside the window counts as rate-limited; a negative age falls through
    and forces a real fetch attempt instead.
    """
    age = _read_own_stamp_age(project_root, remote_name, remote_branch, remote_url)
    if age is not None and 0 <= age < FETCH_RATE_LIMIT_SECONDS:
        return {"status": "rate_limited", "age_seconds": age}, age
    return None, age
