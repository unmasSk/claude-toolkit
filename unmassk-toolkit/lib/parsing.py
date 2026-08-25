"""
Parsing functions for unmassk-toolkit.

Commit type extraction, trailer parsing, scope detection, and text
normalization. Used by validation hooks and CLI scripts.
"""

import re

from constants import VALID_KEYS


def parse_commit_type(subject: str) -> str | None:
    """Extract commit type from conventional commit subject.

    Supports:
    - Emoji prefix: '✨ feat(scope): ...'
    - Git prefixes: 'fixup!', 'squash!', 'amend!' (nested)
    - Internal Git: 'Merge branch', 'Revert', 'Cherry-pick'
    - WIP commits: 'wip: ...'

    Returns lowercase type string, "internal" for Git messages,
    "wip" for WIP commits, or None if unparseable.
    """
    # Allow internal Git messages (merge, revert, cherry-pick)
    if re.match(r"^(Merge branch|Merge remote-tracking branch|Revert |Cherry-pick )", subject):
        return "internal"

    # Strip Git prefixes for validation (handles nested: squash! fixup! feat:)
    cleaned = re.sub(r"^((?:fixup!|squash!|amend!)\s*)+", "", subject).strip()

    # Strip leading emoji(s) and whitespace (preserve # for issue refs)
    cleaned = re.sub(r"^[^\w#]+", "", cleaned).strip()

    # Match: type(scope): or type:
    match = re.match(r"^(\w+)(?:\([^)]*\))?[!]?:", cleaned)
    if match:
        return match.group(1).lower()

    return None


def parse_scope(subject: str) -> str | None:
    """Extract scope from conventional commit subject.

    'feat(auth): ...' → 'auth'
    'feat: ...' → None
    """
    cleaned = re.sub(r"^[^\w#]+", "", subject).strip()
    match = re.match(r"^\w+\(([^)]+)\)", cleaned)
    return match.group(1) if match else None


def parse_trailers(message: str) -> dict[str, str]:
    """Extract trailers from commit message (bottom-up, single value per key).

    Reads from the end of the message, stopping at the first empty line
    or non-trailer line. Used by validation hooks.
    """
    trailers: dict[str, str] = {}
    lines = message.strip().split("\n")

    for line in reversed(lines):
        line = line.strip()
        if not line:
            break
        match = re.match(r"^([A-Z][a-z]+(?:-[A-Z][a-z]+)*):\s*(.+)$", line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            if key in VALID_KEYS:
                trailers[key] = value
        else:
            break

    return trailers


def parse_trailers_full(body: str) -> dict[str, str | list[str]]:
    """Extract all trailers from commit body (full scan, multi-value support).

    Scans all lines (not just trailing block). If a key appears multiple
    times, values are collected into a list. Used by dashboard/gc.
    """
    trailers: dict[str, str | list[str]] = {}
    for line in body.strip().split("\n"):
        line = line.strip()
        match = re.match(r"^([A-Z][a-z]+(?:-[A-Z][a-z]+)*):\s*(.+)$", line)
        if match and match.group(1) in VALID_KEYS:
            key = match.group(1)
            val = match.group(2).strip()
            if key in trailers:
                existing = trailers[key]
                if isinstance(existing, list):
                    existing.append(val)
                else:
                    trailers[key] = [existing, val]
            else:
                trailers[key] = val
    return trailers


def extract_commit_message(command: str) -> str | None:
    """Try to extract commit message from a git commit command.

    Handles multiple -m flags. Returns None if cannot parse
    (heredoc, -F, no -m, etc.)
    """
    if "git commit" not in command:
        return None

    messages: list[str] = []
    pattern = r'-m\s+(?:"((?:[^"\\]|\\.)*)"|\'((?:[^\'\\]|\\.)*)\'|(\S+))'
    matches = re.finditer(pattern, command)
    for match in matches:
        msg = match.group(1) or match.group(2) or match.group(3)
        if msg:
            messages.append(msg)

    if not messages:
        return None

    return "\n\n".join(messages)


def sanitize_trailer_value(text: str) -> str:
    """Strip injection characters from a trailer value.

    Canonical sanitizer — used by lib/incidents.py, bin/git-memory-log.py,
    and bin/git-memory-doctor.py (formerly also recall, session-start-boot,
    and precompact-snapshot, all removed with the v1 boot/memory chain,
    2026-08-05). Single source of truth.

    Removes:
    - Newlines and carriage returns (\\n, \\r)
    - Unicode line/paragraph separators (U+2028, U+2029)
    - Vertical tab and form feed (\\x0b, \\x0c)
    - ANSI escape byte (\\x1b) — SEC-MED-NEW-08: prevents terminal
      escape-sequence injection (screen clears, recoloring) when a
      trailer-adjacent value (e.g. a manifest "version" field) is printed
      directly to a terminal in non-JSON mode.
    - DEL byte (\\x7f) — issue #57 Task 2b (Moriarty gap): the same
      class of terminal control-byte injection as \\x1b, just a
      different byte.
    - File/Group/Record/Unit separators (\\x1c, \\x1d, \\x1e) — issue #57
      root-fix round (decision 0682e75, Argus/Moriarty bullet D): without
      these, a control byte interleaved INSIDE the </memory-data> fence
      marker (e.g. </memory-data\\x1e>) broke the exact-substring match
      below and let the whole marker survive intact. Stripping these
      bytes FIRST (before the fence-marker substring removal) closes that
      evasion for any of the three bytes, in any position.
    - NEL / Next Line (\\x85, U+0085) — issue #57 round 2d (Moriarty
      bullet A): the same fence-marker-interleaving evasion as
      \\x1c/\\x1d/\\x1e above, just a Unicode control byte the earlier
      round's character class didn't cover yet (</memory-data\\x85>
      survived byte-for-byte before this).
    - Unit Separator (\\x1f) — issue #57 round 2e (decision e861680,
      Moriarty gap): not previously in this class at all, so
      </memory-data\\x1f> survived 100% raw/unconverted.
    - HTML comment markers (<!-- and -->)
    - memory-data zone delimiters (<memory-data> / </memory-data>,
      case-insensitive) — issue #57 round 2e (decision e861680, memo
      b49eb60): this is the STRUCTURAL closure, not another byte added to
      the list above. The control-byte-to-space substitution above turns
      ANY interleaved byte into a literal space INSIDE the marker (e.g.
      </memory-data\\x1e> -> </memory-data >), and the old exact
      (no-`\\s`) `</?memory-data>` regex never matched that shape, so the
      fence marker survived intact regardless of which byte produced the
      space. The fix asserts the INVARIANT instead of a byte: any run of
      whitespace (`\\s*`) around the "memory-data" token, any interleaved
      control byte or none, open or close tag — closes the mechanism, not
      one more byte. Runs AFTER the control-byte-to-space substitution so
      it catches the space that substitution introduces.
    """
    text = re.sub(r"[\r\n  \x0b\x0c\x1b\x1c\x1d\x1e\x1f\x7f\x85]", " ", text)
    text = text.replace("<!--", "").replace("-->", "")
    text = re.sub(r"<\s*/?\s*memory-data\s*>", "", text, flags=re.IGNORECASE)
    return text.strip()


def suggest_scope_from_paths(changed_files: list[str], scope_map: dict[str, str]) -> str | None:
    """Suggest a commit scope based on changed file paths and a monorepo scope map.

    Matches each changed file against scope_map prefixes. If all changes
    belong to a single scope, returns that scope. If ambiguous, returns None.

    Args:
        changed_files: List of relative file paths (e.g., ["apps/web/src/index.ts"])
        scope_map: Mapping of directory prefixes to scope names
                   (e.g., {"apps/web": "web", "packages/ui": "ui"})

    Returns:
        Scope name if all files map to one scope, None if ambiguous or unmapped.
    """
    if not changed_files or not scope_map:
        return None

    # Sort prefixes longest-first for greedy matching
    sorted_prefixes = sorted(scope_map.keys(), key=len, reverse=True)

    matched_scopes: set[str] = set()
    for filepath in changed_files:
        # Normalize separators
        normalized = filepath.replace("\\", "/")
        for prefix in sorted_prefixes:
            if normalized.startswith(prefix + "/") or normalized == prefix:
                matched_scopes.add(scope_map[prefix])
                break
        # Files outside any scope prefix are ignored (root-level configs, etc.)

    if len(matched_scopes) == 1:
        return matched_scopes.pop()

    return None
