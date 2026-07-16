#!/usr/bin/env python3
"""
design_gate -- Skill frontmatter collision linter ("design-gate").

Walks every SKILL.md in the repo, parses its YAML frontmatter (`name` +
`description`), and flags two classes of routing collision between skills:

  1. Keyword/trigger collision -- the SAME distinctive term is claimed by
     2+ skills' "... or mentions any of: term1, term2, ..." keyword list
     (and, as a secondary check, the same exact quoted example phrase from
     the "Use when the user asks to '...'" clause). Two skills claiming the
     same distinctive trigger is a possible routing overlap worth a human
     look -- it is NOT necessarily wrong (some overlap is expected between
     sibling skills), just worth reviewing.

  2. "Use when NOT" anomalies -- most descriptions end with a
     `Use when NOT: ...` clause that defers some domain to a sibling skill.
     Two things are flagged there:
       a. dangling_skill_reference -- the description text contains a
          token that LOOKS like a skill name (matches a real family prefix
          already seen elsewhere in the repo, e.g. `design-`, `pentesting-`,
          `electronics-`) but does not match any real skill's `name:` field
          -- likely a typo, a renamed/removed skill, or a stale reference.
       b. mutual_contradiction -- skill A's "Use when NOT" clause defers a
          topic to skill B (word-overlap with B's own claimed keywords),
          AND skill B's "Use when NOT" clause defers an OVERLAPPING topic
          back to skill A -- a circular exclusion that leaves the shared
          ground unclaimed by either.

This is a HEURISTIC, best-effort linter over a documented-but-informal
prose convention -- not an NLP system and not a formal grammar. It is
expected to need human judgment on its output, which is why phase one
(this script) is verified by hand against the real repo before anything
wires it into CI.

What counts as a "skill" here: every `SKILL.md` found under the repo root,
EXCLUDING `.ref-repos/` (vendored third-party source material that is
condensed into our own skills elsewhere -- never itself an active,
routable skill) and the usual dependency/VCS noise directories.

Usage:
  design_gate.py                  # human-readable report, scans from git root (or cwd)
  design_gate.py --root PATH       # scan a specific directory instead
  design_gate.py --json            # machine-readable JSON report only

Exit codes:
  0: no collisions found (parse warnings alone do not fail the gate)
  1: one or more collisions found (keyword, phrase, dangling ref, or mutual contradiction)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from typing import Any

# ── Shared lib ────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "lib"))
from encoding_guard import force_utf8_streams
force_utf8_streams()

from git_helpers import run_git

try:
    import yaml
except ImportError:  # pragma: no cover -- exercised only in an environment
    # missing pyyaml; toolkit-ci.yml already installs it (`pip install
    # pytest pyyaml`), so this is a genuine environment problem, not a
    # normal code path. Fail loud with a clear instruction rather than a
    # bare ModuleNotFoundError traceback.
    yaml = None


# ── Config ────────────────────────────────────────────────────────────────

SKIP_DIR_NAMES = {
    "node_modules", ".git", ".ref-repos", "__pycache__", ".venv", "venv",
    ".pytest_cache", "dist", "build", ".hg", ".svn",
}

# Generic/boilerplate words that show up across many unrelated skill
# descriptions -- filtered out before anything is indexed as a
# "distinctive" trigger term, so routing noise doesn't drown real
# collisions. Deliberately generic-English-only: real trigger terms in
# this corpus are technical nouns (library/tool/protocol names) that never
# collide with this list.
#
# "specific" and "wiring" were added after running against the real repo
# (verification pass): "specific" is a generic adjective with no routing
# signal ("specific format" vs "specific workflows"), and "wiring" is a
# cross-domain homonym -- design-flutter uses it for software "dependency
# wiring" while the electronics skills use it for physical wire
# connections; matching on the bare word produced a false "mutual
# contradiction" between unrelated domains.
GENERIC_TERMS = {
    "use", "used", "using", "uses", "add", "adds", "adding", "make", "makes",
    "making", "build", "building", "review", "reviews", "audit", "audits",
    "test", "tests", "testing", "code", "app", "apps", "web", "design",
    "designs", "designing", "create", "creates", "creating", "implement",
    "implements", "implementing", "user", "users", "asks", "ask", "task",
    "tasks", "request", "requests", "help", "this", "that", "with", "from",
    "into", "domain", "domains", "scope", "different", "the", "and", "or",
    "for", "a", "an", "is", "are", "any", "all", "other", "not", "no",
    "here", "those", "work", "works", "element", "elements", "concern",
    "concerns", "branch", "branches", "separate", "outside", "baseline",
    "layer", "layers", "task", "trigger", "covers", "covering", "based",
    "family", "families", "general", "generic", "specific", "wiring",
    "about", "elsewhere", "handled", "handles", "belongs", "deferred",
    "those", "these", "there", "their", "where", "which", "instead",
}


# ── Frontmatter parsing ───────────────────────────────────────────────────

def load_skill_frontmatter(path: str) -> tuple[dict[str, Any] | None, str | None]:
    """Read one SKILL.md and parse its YAML frontmatter.

    Returns:
        (frontmatter_dict, None) on success -- dict has at least
        'name' (str) and 'description' (str).
        (None, warning_message) on any failure -- never raises.
    """
    try:
        with open(path, encoding="utf-8") as f:
            content = f.read()
    except (OSError, UnicodeDecodeError) as exc:
        return None, f"could not read file: {exc}"

    if not content.startswith("---"):
        return None, "no frontmatter delimiter ('---') at start of file"

    # Same split-on-first-two-delimiters approach already used by
    # tests/test_user_prompt_skill_router.py for the same file shape.
    parts = content.split("---", 2)
    if len(parts) < 3:
        return None, "malformed frontmatter (missing closing '---')"

    frontmatter_text = parts[1]

    if yaml is None:
        return None, "pyyaml not installed -- cannot parse frontmatter (pip install pyyaml)"

    try:
        data = yaml.safe_load(frontmatter_text)
    except yaml.YAMLError as exc:
        return None, f"invalid YAML frontmatter: {exc}"

    if not isinstance(data, dict):
        return None, "frontmatter did not parse to a mapping"

    name = data.get("name")
    description = data.get("description")
    if not name or not isinstance(name, str):
        return None, "missing or invalid 'name' field"
    if not description or not isinstance(description, str):
        return None, "missing or invalid 'description' field"

    return {"name": name.strip(), "description": description}, None


def find_skill_md_files(root: str) -> list[str]:
    """Walk root and return every SKILL.md path, skipping vendor/VCS noise
    directories (see SKIP_DIR_NAMES) and .ref-repos (vendored reference
    material, never an active skill)."""
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIR_NAMES]
        if "SKILL.md" in filenames:
            found.append(os.path.join(dirpath, "SKILL.md"))
    return sorted(found)


# ── Term extraction (pure) ────────────────────────────────────────────────

_MENTIONS_RE = re.compile(r"mentions any of:\s*(.+?)\.(?:\s|$)", re.IGNORECASE | re.DOTALL)
_QUOTED_RE = re.compile(r'"([^"]{3,100})"')
_USE_WHEN_NOT_RE = re.compile(r"use when not:?\s*(.+)", re.IGNORECASE | re.DOTALL)


def _split_top_level_commas(text: str) -> list[str]:
    """Split text on commas that are not inside a matching quote pair.

    Handles items like `"what's this animation called"` (an apostrophe
    inside a double-quoted item) without breaking on the apostrophe --
    only the SAME quote character that opened a quoted run closes it.
    """
    items: list[str] = []
    buf: list[str] = []
    in_quote: str | None = None
    for ch in text:
        if in_quote:
            buf.append(ch)
            if ch == in_quote:
                in_quote = None
        elif ch in ('"', "'"):
            in_quote = ch
            buf.append(ch)
        elif ch == ",":
            items.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
    if buf:
        items.append("".join(buf))
    return items


def extract_mention_terms(description: str) -> list[str]:
    """Extract the comma-separated keyword list from the documented
    "... or mentions any of: term1, term2, ..." clause. Returns [] if the
    description doesn't use this convention -- not every skill does, and
    that's not itself a warning, just no Type-1 signal from this skill."""
    match = _MENTIONS_RE.search(description)
    if not match:
        return []
    terms = []
    for item in _split_top_level_commas(match.group(1)):
        t = item.strip().strip('"').strip("'").strip()
        t = t.rstrip(".").strip()
        if t:
            terms.append(t)
    return terms


def extract_quoted_phrases(description: str) -> list[str]:
    """Extract every double-quoted example trigger phrase in the
    description (the `Use when the user asks to "..."` examples)."""
    return [m.strip() for m in _QUOTED_RE.findall(description) if m.strip()]


def extract_use_when_not(description: str) -> str | None:
    """Extract the `Use when NOT: ...` clause text, stopping before a
    trailing attribution sentence ("Based on ...") if present. Returns
    None if the description has no such clause."""
    match = _USE_WHEN_NOT_RE.search(description)
    if not match:
        return None
    text = re.split(r"\bBased on\b", match.group(1), maxsplit=1, flags=re.IGNORECASE)[0]
    return text.strip()


def split_exclusion_clauses(use_when_not_text: str) -> list[str]:
    """Split a 'Use when NOT' clause into individual excluded-domain
    fragments. Real descriptions use ';' as the primary separator; a few
    use ', or ' / ' or ' instead when there's only one alternative."""
    if ";" in use_when_not_text:
        parts = [p.strip() for p in use_when_not_text.split(";")]
    else:
        parts = [p.strip() for p in re.split(r",?\s+or\s+", use_when_not_text)]
    return [p for p in parts if p]


def _normalize_term(term: str) -> str:
    return re.sub(r"\s+", " ", term.strip().lower())


def _is_distinctive(term: str) -> bool:
    """Filter for Type-1 keyword indexing: drop stopwords, too-short
    fragments, and single common English words with no technical marker
    (hyphen/digit/dot) that are likely prose leakage rather than a real
    trigger term."""
    if len(term) < 3 or term in GENERIC_TERMS:
        return False
    if " " not in term and "-" not in term and "." not in term and len(term) < 4:
        return False
    return True


_WORD_RE = re.compile(r"[a-z0-9][a-z0-9+/_.-]{2,}")


def _significant_words(text: str) -> set[str]:
    """Lowercase significant-word tokens (len >= 4, not a generic term)
    used for the word-overlap heuristic in the Use-when-NOT checks.

    Trailing/leading '.', '-', '/', '+' are stripped after matching -- the
    word regex allows those chars mid-token to keep real compounds intact
    ("prefers-reduced-motion", "Motion.dev", "3D/WebGL"), but a token
    landing at the end of a sentence ("... out of scope here.") would
    otherwise carry the period into the token itself ("here."), which
    silently escapes the GENERIC_TERMS filter (a distinct string from
    "here") and floods every comparison with boilerplate-driven noise.
    """
    words = set()
    for raw in _WORD_RE.findall(text.lower()):
        w = raw.strip("./-+")
        if len(w) >= 4 and w not in GENERIC_TERMS:
            words.add(w)
    return words


# ── Skill record assembly ─────────────────────────────────────────────────

def build_skill_records(skill_mds: list[str]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    """Parse every SKILL.md into a skill record. Returns (records, warnings).

    Each record: name, path, description, mention_terms, quoted_phrases,
    use_when_not (str | None), wordbag (set of significant words drawn
    from this skill's own claimed keywords -- used to judge whether
    ANOTHER skill's exclusion clause plausibly defers to this one).
    """
    records = []
    warnings = []
    for path in skill_mds:
        frontmatter, warning = load_skill_frontmatter(path)
        if warning:
            warnings.append({"path": path, "reason": warning})
            continue
        description = frontmatter["description"]
        mention_terms = extract_mention_terms(description)
        quoted_phrases = extract_quoted_phrases(description)
        wordbag: set[str] = set()
        for term in mention_terms + quoted_phrases:
            wordbag |= _significant_words(term)
        records.append({
            "name": frontmatter["name"],
            "path": path,
            "description": description,
            "mention_terms": mention_terms,
            "quoted_phrases": quoted_phrases,
            "use_when_not": extract_use_when_not(description),
            "wordbag": wordbag,
        })
    return records, warnings


# ── Type 1: keyword / phrase collisions (pure) ────────────────────────────

def find_keyword_collisions(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Terms from 'mentions any of:' lists claimed by 2+ different skills."""
    index: dict[str, set[str]] = {}
    for skill in skills:
        for term in skill["mention_terms"]:
            norm = _normalize_term(term)
            if not _is_distinctive(norm):
                continue
            index.setdefault(norm, set()).add(skill["name"])
    return [
        {"term": term, "skills": sorted(owners)}
        for term, owners in sorted(index.items())
        if len(owners) >= 2
    ]


def find_phrase_collisions(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Exact quoted example trigger phrases claimed verbatim by 2+ skills.

    Independent of find_keyword_collisions -- this checks the illustrative
    "asks to '...'" examples, not the structured keyword list.
    """
    index: dict[str, set[str]] = {}
    for skill in skills:
        for phrase in skill["quoted_phrases"]:
            norm = _normalize_term(phrase)
            if len(norm) < 6:
                continue
            index.setdefault(norm, set()).add(skill["name"])
    return [
        {"phrase": phrase, "skills": sorted(owners)}
        for phrase, owners in sorted(index.items())
        if len(owners) >= 2
    ]


# ── Type 2: "Use when NOT" anomalies (pure) ───────────────────────────────

def find_dangling_skill_references(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag description text that names something shaped like a skill (a
    known family prefix + hyphen + more lowercase segments) that doesn't
    match any real skill's `name:` field.

    Family prefixes are derived from the real skill names actually found
    (the text before the first hyphen), not hardcoded -- so this adapts as
    new skill families are added instead of needing to be updated by hand.
    """
    real_names = {skill["name"] for skill in skills}
    prefixes = {name.split("-", 1)[0] for name in real_names if "-" in name}
    if not prefixes:
        return []

    prefix_pattern = "|".join(re.escape(p) for p in sorted(prefixes, key=len, reverse=True))
    token_re = re.compile(rf"\b(?:{prefix_pattern})-[a-z][a-z0-9-]*\b")

    findings = []
    for skill in skills:
        # Scoped to the 'Use when NOT' clause specifically -- that's where
        # a description would name a sibling skill it defers to. Scanning
        # the whole description also catches ordinary English compounds
        # from the "Covers ..." prose (e.g. "design-engineering
        # philosophy") that only coincidentally share a family prefix and
        # were never meant as a skill reference.
        if not skill["use_when_not"]:
            continue
        for match in token_re.finditer(skill["use_when_not"].lower()):
            token = match.group(0)
            if token != skill["name"] and token not in real_names:
                findings.append({"skill": skill["name"], "token": token})
    # De-duplicate identical (skill, token) pairs (a token can repeat in one description).
    seen = set()
    deduped = []
    for f in findings:
        key = (f["skill"], f["token"])
        if key not in seen:
            seen.add(key)
            deduped.append(f)
    return deduped


def _stem(word: str) -> str:
    """Minimal suffix stripper (ing/ed/es/s), never shortening below 3
    chars -- just enough to equate "flash"/"flashed", "print"/"printing"
    for the ownership check below. Not a real stemmer (no linguistic
    rules); good enough for this corpus's plain-English technical nouns."""
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 3:
            return word[: -len(suffix)]
    return word


def _expand_variants(word: str) -> set[str]:
    """A word plus its stem and (if hyphenated) its >=4-char sub-parts.

    Exists only for the "is this ground claimed by anyone?" ownership
    check in find_mutual_contradictions -- verified against the real repo:
    electronics-pi's exclusion says "flashed" while electronics-micro's
    OWN claimed keyword list says "flash" (different inflection, same
    word); electronics-robotics's exclusion says "3D-printing" (one
    hyphenated token) while unmassk-3d's OWN claimed keyword list says
    "3D printing" (two words, so only "printing" survives the length
    filter). Without this expansion both read as "nobody claims this",
    which is a false positive -- someone genuinely does, just spelled
    differently.
    """
    variants = {word, _stem(word)}
    if "-" in word:
        for part in word.split("-"):
            if len(part) >= 4:
                variants.add(part)
                variants.add(_stem(part))
    return variants


def _expand_wordset(words: set[str]) -> set[str]:
    expanded: set[str] = set()
    for w in words:
        expanded |= _expand_variants(w)
    return expanded


def find_mutual_contradictions(skills: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Flag pairs (A, B) that both exclude the SAME ground in their 'Use
    when NOT' clause -- i.e. both skills punt this topic as "someone
    else's job" -- while NO skill in the repo actually claims that ground
    as a positive keyword (mention_terms / quoted_phrases). That is a real
    contradiction: two skills agree it's out of scope for both of them,
    yet nothing routes to it.

    This is deliberately narrower than "any shared exclusion word between
    two skills" -- a healthy, well-designed pair of complementary skills
    (e.g. design-3d excluding 2D motion toward design-motion, and
    design-motion excluding 3D toward design-3d) will naturally share the
    boundary term ("3D/WebGL") in both of their exclusion clauses, and
    that boundary term IS one of design-3d's own claimed keywords -- so it
    is correctly NOT flagged here. Only shared exclusion ground that maps
    to NO skill's claimed keywords anywhere in the repo (after the
    stem/hyphen expansion above) counts.
    """
    expanded_wordbags = [_expand_wordset(skill["wordbag"]) for skill in skills]

    def _claimed_anywhere(words: set[str]) -> bool:
        expanded_shared = _expand_wordset(words)
        return any(expanded_shared & bag for bag in expanded_wordbags)

    clauses_by_skill: dict[str, list[tuple[str, set[str]]]] = {}
    for skill in skills:
        if not skill["use_when_not"]:
            continue
        clauses_by_skill[skill["name"]] = [
            (clause, _significant_words(clause))
            for clause in split_exclusion_clauses(skill["use_when_not"])
        ]

    findings = []
    seen_pairs = set()
    names = sorted(clauses_by_skill)
    for a_name in names:
        for b_name in names:
            if a_name >= b_name:
                continue
            for a_clause, a_words in clauses_by_skill[a_name]:
                for b_clause, b_words in clauses_by_skill[b_name]:
                    shared = a_words & b_words
                    if not shared:
                        continue
                    if _claimed_anywhere(shared):
                        continue  # someone actually owns this ground -- healthy handoff
                    pair_key = (a_name, b_name, tuple(sorted(shared)))
                    if pair_key in seen_pairs:
                        continue
                    seen_pairs.add(pair_key)
                    findings.append({
                        "skill_a": a_name,
                        "clause_a": a_clause,
                        "skill_b": b_name,
                        "clause_b": b_clause,
                        "shared_terms": sorted(shared),
                    })
    return findings


# ── Report assembly + I/O ─────────────────────────────────────────────────

def run_gate(root: str) -> dict[str, Any]:
    """Scan root and produce the full report dict. Never raises."""
    skill_mds = find_skill_md_files(root)
    skills, warnings = build_skill_records(skill_mds)

    keyword_collisions = find_keyword_collisions(skills)
    phrase_collisions = find_phrase_collisions(skills)
    dangling_references = find_dangling_skill_references(skills)
    mutual_contradictions = find_mutual_contradictions(skills)

    ok = not (keyword_collisions or phrase_collisions or dangling_references or mutual_contradictions)

    return {
        "ok": ok,
        "root": root,
        "skills_scanned": len(skills),
        "warnings": warnings,
        "keyword_collisions": keyword_collisions,
        "phrase_collisions": phrase_collisions,
        "dangling_references": dangling_references,
        "mutual_contradictions": mutual_contradictions,
    }


def format_human_report(report: dict[str, Any]) -> str:
    lines = []
    lines.append("=== design-gate: skill frontmatter collision check ===")
    lines.append(f"Root: {report['root']}")
    lines.append(f"Skills scanned: {report['skills_scanned']}")

    if report["warnings"]:
        lines.append(f"\nWarnings ({len(report['warnings'])}) -- malformed/unparsed SKILL.md, not a collision:")
        for w in report["warnings"]:
            lines.append(f"  - {w['path']}: {w['reason']}")

    if report["keyword_collisions"]:
        lines.append(f"\nKeyword collisions ({len(report['keyword_collisions'])}):")
        for c in report["keyword_collisions"]:
            lines.append(f"  - '{c['term']}' claimed by: {', '.join(c['skills'])}")
    else:
        lines.append("\nKeyword collisions: none")

    if report["phrase_collisions"]:
        lines.append(f"\nQuoted phrase collisions ({len(report['phrase_collisions'])}):")
        for c in report["phrase_collisions"]:
            lines.append(f"  - \"{c['phrase']}\" claimed by: {', '.join(c['skills'])}")
    else:
        lines.append("Quoted phrase collisions: none")

    if report["dangling_references"]:
        lines.append(f"\nDangling skill references ({len(report['dangling_references'])}):")
        for d in report["dangling_references"]:
            lines.append(f"  - {d['skill']} mentions '{d['token']}', which is not a real skill name")
    else:
        lines.append("Dangling skill references: none")

    if report["mutual_contradictions"]:
        lines.append(f"\nMutual contradictions ({len(report['mutual_contradictions'])}):")
        for m in report["mutual_contradictions"]:
            lines.append(
                f"  - {m['skill_a']} excludes \"{m['clause_a']}\" (-> {m['skill_b']}) "
                f"while {m['skill_b']} excludes \"{m['clause_b']}\" (-> {m['skill_a']}); "
                f"shared ground: {', '.join(m['shared_terms'])}"
            )
    else:
        lines.append("Mutual contradictions: none")

    lines.append(f"\nResult: {'CLEAN' if report['ok'] else 'COLLISIONS FOUND'}")
    return "\n".join(lines)


def find_project_root() -> str:
    """Git toplevel of cwd, falling back to cwd if not in a git repo."""
    code, git_root = run_git(["rev-parse", "--show-toplevel"])
    if code == 0 and git_root:
        return git_root
    return os.getcwd()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Detect skill frontmatter routing collisions (keyword overlap, "
        "quoted phrase overlap, dangling skill references, mutual 'Use when NOT' contradictions)."
    )
    parser.add_argument("--root", default=None, help="Directory to scan (default: git toplevel, or cwd)")
    parser.add_argument("--json", action="store_true", help="Print the JSON report only")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root) if args.root else find_project_root()

    if yaml is None:
        print("Error: pyyaml is required (pip install pyyaml)", file=sys.stderr)
        return 1

    if not os.path.isdir(root):
        print(f"Error: root path does not exist or is not a directory: {root}", file=sys.stderr)
        return 1

    report = run_gate(root)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_human_report(report))

    return 0 if report["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
