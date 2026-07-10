#!/usr/bin/env python3
"""
Pre-compact snapshot hook.

Before Claude compresses context, extracts critical memory from recent
commits and re-injects it as a compact summary. This ensures Next:,
Decision:, and Blocker: trailers survive context compression.

Exit codes:
    0: Always (non-blocking, injects context via stdout).
"""

import os
import re
import secrets
import sys
from typing import Any

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from constants import TOMBSTONE_KEYS
from git_helpers import run_git, is_git_repo, is_shallow_clone
from parsing import normalize, scan_trailers_memory, sanitize_trailer_value as _sanitize

# Issue #57 round 2d (Moriarty bullet B, decision 0cef65c): the snapshot's
# own header/footer are ordinary printable strings, not control bytes --
# sanitize_trailer_value() has no reason to touch them, so a hostile
# Decision/Memo/Next/Blocker/subject value containing this literal text
# reproduces the real frame byte-for-byte INSIDE the snapshot body, making
# a forged frame indistinguishable from the genuine one. This is a
# different class from byte-sanitization (no control byte involved at
# all), so it's deliberately NOT folded into the canonical
# sanitize_trailer_value() in lib/parsing.py -- that function is shared by
# every hook/script in the repo and shouldn't be coupled to a delimiter
# that only this one hook defines. Instead, every commit-derived field
# below is neutralized for these two specific strings right before it
# enters the snapshot, so the real frame can only ever appear once.
_SNAPSHOT_HEADER = "=== GIT MEMORY SNAPSHOT (pre-compact) ==="
_SNAPSHOT_FOOTER = "=== END SNAPSHOT ==="


def _neutralize_snapshot_delimiters(text: str) -> str:
    """Neutralize literal occurrences of the snapshot's own frame delimiters.

    Replaces (not blanks) any exact occurrence of the header or footer
    string so real surrounding content survives while the forged frame no
    longer reads as an exact match -- keeps `stdout.count(delimiter) == 1`
    true for the real frame regardless of what a commit tries to smuggle.
    """
    if not text:
        return text
    text = text.replace(_SNAPSHOT_HEADER, "[snapshot-frame-text-neutralized]")
    text = text.replace(_SNAPSHOT_FOOTER, "[snapshot-frame-text-neutralized]")
    return text


def _sanitize_for_snapshot(text: str) -> str:
    """Canonical control-byte sanitization plus snapshot-delimiter neutralization.

    Every commit-derived field rendered into format_snapshot()'s output
    must go through this (not the bare `_sanitize()` alias) so the whole
    output-sanitization class -- control bytes AND this hook's own
    plain-text frame -- is closed at the same choke point.
    """
    return _neutralize_snapshot_delimiters(_sanitize(text))


def extract_memory_from_log() -> dict[str, Any]:
    """Read the last 30 commits and extract memory trailers.

    Collects Next:, Blocker:, Decision:, and Memo: trailers. Respects
    GC tombstones (Resolved-Next:, Stale-Blocker:) to skip resolved items.

    Returns:
        Dict with keys: pending, blockers, decisions, memos, last_context.
        Empty dict if git log fails.
    """
    # SEC-CRIT-NEW-01 pattern (Argus, mirrored from lib/boot_memory.py's
    # extract_memory()/extract_glossary(), issue #57): `-z` (NUL, \x00)
    # record boundaries instead of an embedded \x1e in the --pretty=format
    # string. A commit BODY is fully attacker-controlled and CAN contain a
    # literal \x1e byte -- str.split()-ing on it let a single real commit
    # forge an entire fake decision/memo/blocker entry that this hook then
    # prints verbatim to stdout, which Claude receives directly as context
    # right after PreCompact. A commit message can never contain a raw NUL
    # byte, so splitting on \x00 has no forgeable equivalent. \x1f (ASCII
    # Unit Separator) remains the FIELD separator within a single record --
    # impossible to type as an ordinary keystroke, but not immune to being
    # embedded programmatically, which is why the record boundary (not the
    # field separator) is the one that must resist forgery.
    #
    # Structural fix (issue #57 root-fix round, decision 0682e75): %s
    # (subject) is last in the header, separated from %b (body) by %n (a
    # real newline), not by \x1f. git guarantees %s never contains a
    # literal newline, so the FIRST "\n" in a record reliably separates
    # the header zone (sha\x1fsubject) from the body zone -- a stray
    # \x1f embedded anywhere in the SUBJECT alone used to consume the
    # maxsplit slot meant for the real subject/body boundary, erasing the
    # real trailer entirely from stdout. Now any extra \x1f in the
    # subject is absorbed into `subject` itself (header.split("\x1f", 1)
    # below), never bleeding into `body`.
    # House root-cause (issue #61): a transient git failure here used to
    # collapse to {} with zero trace, indistinguishable from "no recent
    # commits". log_stderr_on_failure=True leaves a breadcrumb on stderr
    # when code != 0; the {} return value is unchanged.
    code, output = run_git([
        "log", "-n", "30", "-z",
        "--pretty=format:%h\x1f%s%n%b",
        "--",
    ], log_stderr_on_failure=True)

    if code != 0 or not output:
        return {}

    memory: dict[str, Any] = {
        "pending": [],       # Next: items
        "blockers": [],      # Blocker: items
        "decisions": {},     # scope → Decision: (latest per scope)
        "memos": {},         # scope → Memo: (latest per scope)
        "last_context": None,  # Last context() commit
    }

    commits = [c for c in output.split("\x00") if c.strip()]

    # First pass: collect GC tombstones (Resolved-Next:, Stale-Blocker:)
    tombstones = set()
    for commit in commits:
        header, _, body = commit.strip().partition("\n")
        parts = header.split("\x1f", 1)
        if len(parts) < 2:
            continue
        body = body.strip()
        trailers = scan_trailers_memory(body)
        for key in TOMBSTONE_KEYS:
            if key in trailers:
                tombstones.add(normalize(trailers[key]))

    # Second pass: extract memory, skipping tombstoned items
    for commit in commits:
        header, _, body = commit.strip().partition("\n")
        parts = header.split("\x1f", 1)
        if len(parts) < 2:
            continue

        sha = parts[0].strip()
        subject = parts[1].strip()
        body = body.strip()

        # Strip emoji prefix before parsing type/scope
        cleaned = re.sub(r"^[^\w#]+", "", subject).strip()

        # Extract scope from subject.
        # SEC-CRIT-NEW-04 (issue #57, Task 2b, mirrored from
        # lib/boot_memory.py): `scope` comes straight from the fully
        # attacker-controlled commit subject, yet it feeds the "Active
        # decisions:"/"Active memos:" lines below with no sanitization --
        # unlike every trailer VALUE in this function, which already goes
        # through _sanitize(). Sanitizing once here propagates to every
        # downstream use (dict keys for decisions/memos/remembers).
        scope_match = re.match(r"^\w+\(([^)]+)\)", cleaned)
        scope = _sanitize_for_snapshot(scope_match.group(1)) if scope_match else "global"

        # Check if context commit
        if cleaned.lower().startswith("context"):
            if memory["last_context"] is None:
                # SEC-CRIT-NEW-04: the raw commit subject is untrusted and
                # is printed verbatim on the "Last session:" line below --
                # sanitize it the same way scope/trailer values are.
                memory["last_context"] = {
                    "sha": sha,
                    "subject": _sanitize_for_snapshot(subject),
                    "scope": scope,
                }

        # Extract trailers from body using shared parser
        trailers = scan_trailers_memory(body)

        if "Next" in trailers:
            next_text = _sanitize_for_snapshot(trailers["Next"])
            if normalize(next_text) not in tombstones:
                memory["pending"].append({
                    "sha": sha, "subject": subject, "next": next_text,
                })

        if "Blocker" in trailers:
            blocker_text = _sanitize_for_snapshot(trailers["Blocker"])
            if normalize(blocker_text) not in tombstones:
                existing = [b["blocker"].lower() for b in memory["blockers"]]
                if blocker_text.lower() not in existing:
                    memory["blockers"].append({
                        "sha": sha, "blocker": blocker_text,
                    })

        if "Decision" in trailers:
            if scope not in memory["decisions"]:
                memory["decisions"][scope] = {
                    "sha": sha, "subject": subject,
                    "decision": _sanitize_for_snapshot(trailers["Decision"]),
                }

        if "Memo" in trailers:
            memo_text = _sanitize_for_snapshot(trailers["Memo"])
            if scope not in memory["memos"] and normalize(memo_text) not in tombstones:
                memory["memos"][scope] = {
                    "sha": sha, "memo": memo_text,
                }

        if "Remember" in trailers:
            text = _sanitize_for_snapshot(trailers["Remember"])
            if "remembers" not in memory:
                memory["remembers"] = {}
            if (
                text.lower() not in {r["remember"].lower() for r in memory.get("remembers", {}).values()}
                and normalize(text) not in tombstones
            ):
                memory["remembers"][f"{scope}:{text[:20]}"] = {
                    "sha": sha, "remember": text,
                }

    return memory


def format_snapshot(memory: dict[str, Any]) -> str:
    """Format memory data as a compact text snapshot for re-injection.

    Produces a short summary (max ~18 lines) covering branch, last session,
    pending items, blockers, decisions, and memos.

    Args:
        memory: Structured memory dict from extract_memory_from_log().

    Returns:
        Multi-line string ready to print to stdout.
    """
    lines = []
    # A2 token-fence (issue #59, decision feed852): a per-invocation,
    # cryptographically unpredictable nonce rides on both frame delimiters
    # so two invocations over identical repo state stop being
    # byte-identical -- no value committed in advance (necessarily static)
    # can ever reproduce today's real frame. The delimiter literals
    # themselves ("=== GIT MEMORY SNAPSHOT (pre-compact) ===" /
    # "=== END SNAPSHOT ===") are left byte-exact and unchanged: they are
    # asserted verbatim elsewhere (test_drift.py, this file's own PART M
    # delimiter-spoofing tests in test_control_byte_injection.py) as the
    # anchor a consumer greps/counts on, and _neutralize_snapshot_delimiters()
    # above still needs the exact literal to recognize and strip a spoofed
    # copy from commit-derived content.
    fence_nonce = secrets.token_hex(8)
    lines.append(f"=== GIT MEMORY SNAPSHOT (pre-compact) === (nonce:{fence_nonce})")

    # Shallow clone warning
    if is_shallow_clone():
        lines.append("!!! WARNING: Shallow clone detected. Memory may be incomplete. !!!")

    # Branch
    # House root-cause (issue #61): a transient failure here silently
    # omitted the "Branch:" line with zero trace. log_stderr_on_failure=True
    # leaves a breadcrumb on stderr when code != 0; behavior (omit the
    # line) is unchanged.
    code, branch = run_git(["branch", "--show-current"], log_stderr_on_failure=True)
    if code == 0:
        lines.append(f"Branch: {branch}")

    # Last context
    if memory.get("last_context"):
        ctx = memory["last_context"]
        lines.append(f"Last session: {ctx['sha']} {ctx['subject']}")

    def trunc(text: str, limit: int = 200) -> str:
        """Truncate text to limit chars, appending '...' if needed."""
        return (text[:limit] + "...") if len(text) > limit else text

    # Pending items — prioritize context() Next: first, then others
    if memory.get("pending"):
        ctx_sha = memory["last_context"]["sha"] if memory.get("last_context") else None
        # Split: context Next first, then unique others
        ctx_next = [p for p in memory["pending"] if p["sha"] == ctx_sha]
        other_next = [p for p in memory["pending"] if p["sha"] != ctx_sha]
        # Dedup others by text similarity (skip if already covered by context Next)
        ctx_texts = {n["next"].lower() for n in ctx_next}
        unique_others = []
        for item in other_next:
            if item["next"].lower() not in ctx_texts:
                unique_others.append(item)
        ordered = ctx_next + unique_others
        if ordered:
            lines.append("Pending:")
            for item in ordered[:2]:  # Max 2 items to stay ≤18 lines total
                marker = " (current)" if item["sha"] == ctx_sha else ""
                lines.append(f"  - [{item['sha']}] {trunc(item['next'])}{marker}")
            if len(ordered) > 2:
                lines.append(f"  + {len(ordered) - 2} older items")

    # Blockers (deduped by text — overflow rare, capped at 2)
    if memory.get("blockers"):
        lines.append("Blockers:")
        for item in memory["blockers"][:2]:  # Max 2 to stay compact
            lines.append(f"  - [{item['sha']}] {trunc(item['blocker'])}")

    # Active decisions (1 per scope — overflow only if >3 scopes in last 30 commits)
    if memory.get("decisions"):
        lines.append("Active decisions:")
        for scope, item in list(memory["decisions"].items())[:3]:  # Max 3 to stay ≤18 lines total
            lines.append(f"  - ({scope}) {trunc(item['decision'])}")

    # Active memos (1 per scope — overflow only if >2 scopes in last 30 commits)
    if memory.get("memos"):
        lines.append("Active memos:")
        for scope, item in list(memory["memos"].items())[:2]:  # Max 2 to stay ≤18 lines total
            lines.append(f"  - ({scope}) {trunc(item['memo'])}")

    # Remember notes (personality/working-style notes between sessions)
    if memory.get("remembers"):
        lines.append("Remember (personality notes):")
        for key, item in list(memory["remembers"].items())[:3]:
            lines.append(f"  🧠 {trunc(item['remember'])}")

    lines.append(f"=== END SNAPSHOT === (nonce:{fence_nonce})")
    return "\n".join(lines)


def main() -> None:
    """Entry point. Extracts memory from git log and prints a snapshot to stdout."""
    if not is_git_repo():
        sys.exit(0)

    memory = extract_memory_from_log()

    if not memory:
        sys.exit(0)

    # Check if there's anything worth snapshotting
    has_content = (
        memory.get("pending")
        or memory.get("blockers")
        or memory.get("decisions")
        or memory.get("memos")
        or memory.get("last_context")
    )

    if has_content:
        snapshot = format_snapshot(memory)
        # Print to stdout so Claude receives it as context
        print(snapshot)

    # After compaction, Claude receives this output. Instruct it to
    # create a context commit so the next session (or post-compaction
    # continuation) has a rich checkpoint in git history.
    print()
    plugin_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    commit_script = os.path.join(plugin_root, "bin", "git-memory-commit.py")
    print(
        "CRITICAL — CONTEXT CHECKPOINT REQUIRED: "
        "Your context was just compacted. "
        "IMMEDIATELY create a context() commit capturing what you worked on this session. "
        f'Use: python3 "{commit_script}" context <scope> "<summary>" '
        '--trailer "Next=<what to do next>" '
        '--trailer "Decision=<any decisions made>" '
        '--trailer "Memo=<any preferences or patterns learned>" '
        '--trailer "Blocker=<any blockers>" '
        "Include ALL relevant trailers. This is how the next session picks up your work. "
        "Do this BEFORE responding to the user."
    )

    sys.exit(0)


if __name__ == "__main__":
    main()
