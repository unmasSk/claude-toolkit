"""
bootstrap_commits -- Recent git commit history analysis for
bin/git-memory-bootstrap.py.

Split out of git-memory-bootstrap.py (was 953 LOC). This module owns the
"what does recent commit history tell us" concern (contributor count,
trailer adoption, scope usage) — kept separate from bootstrap_tree.py and
bootstrap_deps.py, which never touch git history.
"""

import re
from collections import defaultdict
from typing import Any

from git_helpers import run_git
from parsing import sanitize_trailer_value

SCAN_COMMITS = 20

# issue #57 round 2d (Argus SEC-MED, bullet E): `git memory bootstrap
# --json` does json.dumps(output, ...), which escapes control bytes but
# has no reason to touch '<'/'>' -- a literal generic tag (e.g. <system>,
# </system>) in a commit subject survives byte-for-byte and is fully
# reconstructable by anything reading the JSON text. sanitize_trailer_value()
# only strips its OWN </memory-data> fence marker, not arbitrary tag names,
# so this is a distinct, deliberately generic regex (catches any tag name,
# not just "system") applied alongside it, local to this module rather than
# folded into the shared canonical sanitizer.
#
# issue #57 round 2e (decision e861680, Moriarty EXPLOIT-3): the original
# regex assumed a "naked" tag -- no attributes, and a single `.sub()` pass.
# Three constructions bypassed it: `<system role="root">` (an attribute
# breaks the bare-`>` assumption -- `[\w-]*\s*>` never consumes `role="root"`
# so the whole tag never matches), `<system/>` (the literal `/` before `>`
# isn't consumed by `[\w-]*` or `\s*` either, so it survives verbatim), and
# `<sy<system>stem>` (nested -- one pass strips only the innermost
# `<system>`, leaving the outer `<system>...>` intact). Structural fix:
# 1) tolerate anything between the tag name and the closing `>` (attributes,
# a trailing `/`, whitespace) instead of assuming a bare tag, and 2) iterate
# to a fixed point instead of a single substitution, so a nested tag
# revealed by stripping the inner one gets caught on the next pass. Ordinary
# arithmetic (`a < b`) is unaffected: the regex still requires a letter
# immediately after `<` (`[a-zA-Z]`), so a bare `< b` with a space never
# matches. `Foo<Bar>`-style generics ARE still neutralized (accepted
# trade-off for this bootstrap-json context, per the round's decision).
_GENERIC_TAG_RE = re.compile(r"</?[a-zA-Z][^>]*>")
_GENERIC_TAG_FIXED_POINT_MAX_ITERATIONS = 10

# issue #59 (ReDoS, plan docs/plan/fix-fence-a2-close-57.md task b, Dante):
# _GENERIC_TAG_RE's negated character class ([^>]*) has no catastrophic
# (exponential) backtracking risk, but is still O(n^2) against a long run of
# unmatched "<letter" openers with no closing ">" anywhere -- for EVERY
# "<letter" start position the engine scans to the end of the remaining
# string before concluding there's no match. Empirically confirmed
# (2026-07-10, this machine): "<a" * 200000 (400,000 chars) took ~41s;
# "<a" * 60000 (120,000 chars) took ~4.2s. This function only ever runs on a
# single commit subject or author name (both already passed through
# sanitize_trailer_value() by every call site below) -- no legitimate value
# is remotely close to this length, so a hard cap on the INPUT before the
# regex ever runs closes the DoS at the source instead of trying to
# out-optimize the regex itself. 4096 chars keeps worst-case processing time
# far under the 2.0s bound (quadratic scaling from the 120K/4.2s measurement
# puts a 4096-char worst case at ~5ms) while being generous enough that no
# real subject/author is ever affected.
_GENERIC_TAG_MAX_INPUT_LEN = 4096


def _strip_generic_tags(text: str) -> str:
    """Strip any HTML/XML-like tag from commit-derived text before --json output.

    Runs to a fixed point (bounded) so a nested construction like
    `<sy<system>stem>` -- whose inner tag is stripped first, revealing an
    outer tag that a single pass would miss -- is fully neutralized.

    Input longer than _GENERIC_TAG_MAX_INPUT_LEN is truncated BEFORE the
    regex ever runs (issue #59, ReDoS) -- see that constant's comment.
    """
    if not text:
        return text
    if len(text) > _GENERIC_TAG_MAX_INPUT_LEN:
        text = text[:_GENERIC_TAG_MAX_INPUT_LEN]
    for _ in range(_GENERIC_TAG_FIXED_POINT_MAX_ITERATIONS):
        stripped = _GENERIC_TAG_RE.sub("", text)
        if stripped == text:
            return stripped
        text = stripped
    return text


def scan_recent_commits(depth: int = SCAN_COMMITS) -> dict[str, Any] | None:
    """Analyze recent commits for contributor count, trailer usage, and scopes.

    Returns:
        Dict with commit stats, or None if git log fails or is empty.
    """
    # SEC-CRIT-NEW-01 pattern (Argus, mirrored from lib/boot_memory.py's
    # extract_memory()/extract_glossary(), issue #57): `-z` (NUL, \x00)
    # record boundaries instead of an embedded \x1e in the --pretty=format
    # string. A commit body CAN contain a literal \x1e byte -- str.split()-
    # ing on it let a single real commit forge an entire fake commit entry
    # (attacker-chosen sha/scope/date/author) in the "recent" list fed to
    # `git memory bootstrap --json`. A commit message can never contain a
    # raw NUL byte, so splitting on \x00 has no forgeable equivalent. \x1f
    # remains the FIELD separator within a single record.
    #
    # Structural fix (issue #57 root-fix round, decision 0682e75): this
    # site has THREE fully/semi attacker-controlled free-text fields --
    # %s (subject, never contains a real newline, git-guaranteed), %an
    # (author name, no such guarantee), and %b (body). Only ONE free-text
    # field can be "last in its header" and safely absorb a stray \x1f --
    # you cannot protect two independent free-text fields with a single
    # %n split. Two narrower git log calls, each shaped so its own single
    # free-text field is the LAST thing split on, closes this cleanly
    # instead of chasing per-field reorderings (Task 2b's previous round,
    # which only handled a stray \x1f in the BODY -- a stray \x1f in the
    # SUBJECT alone still corrupted `date`/`author`, confirmed live in
    # this round's contract).
    #
    # Call 1: %h/%aI (both structured, never contain \x1f or a newline),
    # then %s last-in-header (absorbs any stray \x1f in the subject),
    # then %b after the first real "\n" (%n) -- git guarantees %s has no
    # literal newline, so this split is always unambiguous.
    # breadcrumb #61: transient git failure here used to collapse to None
    # with zero trace; log_stderr_on_failure leaves a trace, None return
    # value unchanged (see run_git()'s docstring in git_helpers.py).
    code, output = run_git([
        "log", "-n", str(depth), "-z",
        # %aI (not %at): this date is never parsed, only carried through to
        # bin/git-memory-bootstrap.py's --json output for presentation to
        # the user (see that script's own docstring). %aI gives a readable
        # ISO-8601 string; do not "fix" this back to a raw epoch digit
        # string -- a bare epoch is not presentable as-is, and this module
        # never parses the field, so there is no equivalent robustness
        # argument for %at here (see test_date_parsing_epoch_contract.py's
        # TestBootstrapCommitsDateFieldContract for the full reasoning).
        "--pretty=format:%h\x1f%aI\x1f%s%n%b",
        "--",
    ], log_stderr_on_failure=True)
    if code != 0 or not output:
        return None

    # Call 2: %h/%an ONLY -- %an is the last (and only) field after %h in
    # THIS record, so it independently absorbs any stray \x1f embedded in
    # the author name, the same way %s does above. Looked up by sha below;
    # a missing/failed second call degrades to an empty author per commit
    # rather than failing the whole scan.
    authors_by_sha: dict[str, str] = {}
    # breadcrumb #61: same rationale as Call 1's run_git() above — a
    # failure here degrades to an empty author dict silently; trace only.
    code2, output2 = run_git([
        "log", "-n", str(depth), "-z",
        "--pretty=format:%h\x1f%an",
        "--",
    ], log_stderr_on_failure=True)
    if code2 == 0 and output2:
        for araw in output2.split("\x00"):
            araw = araw.strip()
            if not araw:
                continue
            aparts = araw.split("\x1f", 1)
            if len(aparts) < 2:
                continue
            authors_by_sha[aparts[0].strip()] = aparts[1].strip()

    commits: list[dict[str, Any]] = []
    authors: defaultdict[str, int] = defaultdict(int)
    has_trailers = 0
    trailer_re = re.compile(r"^[A-Z][a-z]+(?:-[A-Z][a-z]+)*:\s*.+$", re.MULTILINE)
    scope_re = re.compile(r"^\w+\(([^)]+)\)")

    for raw in output.split("\x00"):
        # Field-displacement gotcha (issue #57, Task 2b, Dante; still
        # applies after the root-fix restructure): str.strip() treats
        # \x1c-\x1f (and "\n") as whitespace. A commit with an EMPTY body
        # produces a raw record ending in a bare "\n" (the %n separator)
        # -- .strip() eats it, so `body` legitimately comes back empty
        # for a perfectly ordinary, real commit; `body` is read
        # defensively either way.
        raw = raw.strip()
        if not raw:
            continue
        header, _, body = raw.partition("\n")
        parts = header.split("\x1f", 2)
        if len(parts) < 3:
            continue

        sha, date, subject = parts[0].strip(), parts[1].strip(), parts[2].strip()
        author = authors_by_sha.get(sha, "")
        authors[author] += 1

        if trailer_re.search(body):
            has_trailers += 1

        # Extract scope
        scope = None
        m = scope_re.match(subject)
        if m:
            scope = m.group(1)

        # issue #57 round 2d (Argus SEC-MED, bullet E): subject/author are
        # fully commit-derived and reach `git memory bootstrap --json`'s
        # stdout via json.dumps() unmodified -- json.dumps() escapes
        # control bytes but has no reason to touch '<'/'>' tag-like
        # substrings (e.g. </memory-data>, <system>), which survive intact
        # and are fully reconstructable by anything reading the JSON text.
        # Sanitize once here so both --json and any other consumer of
        # "recent" are covered by a single choke point.
        commits.append({
            "sha": sha,
            "subject": _strip_generic_tags(sanitize_trailer_value(subject)),
            "scope": scope,
            "date": date,
            "author": _strip_generic_tags(sanitize_trailer_value(author)),
        })

    return {
        "count": len(commits),
        "authors": dict(authors),
        "has_trailers": has_trailers,
        "recent": commits[:5],
    }
