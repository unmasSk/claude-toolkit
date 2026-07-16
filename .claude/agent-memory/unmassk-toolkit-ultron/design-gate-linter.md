---
name: design-gate-linter
description: unmassk-toolkit/bin/design_gate.py (skill frontmatter collision linter) -- corpus shape, pyyaml precedent, and 3 false-positive traps found verifying against the real repo
metadata:
  type: implementation-patterns
---

## What it is and where

`unmassk-toolkit/bin/design_gate.py` walks every `SKILL.md` in the repo
(excluding `.ref-repos/` -- vendored source material condensed into other
skills, never itself an active/routable skill -- and the usual
node_modules/.git/__pycache__ noise), parses `name`+`description` from
YAML frontmatter, and flags two collision classes: (1) the same
distinctive term claimed by 2+ skills' `"... or mentions any of: term1,
term2, ..."` list, and (2) `Use when NOT:` clause anomalies (dangling
reference to a nonexistent skill name; mutual contradiction where two
skills both exclude the same ground that nobody's positive keyword list
actually claims). Script is standalone, not yet wired into CI (explicit
phase-1 scope -- CI wiring is a deliberate follow-up, not an oversight).

## pyyaml is an acceptable dependency for bin/ scripts, even though no
## production bin/lib code used it before

Grepped the whole repo before deciding: zero production `bin/`/`lib/`
files import `yaml` (only `tests/test_user_prompt_skill_router.py` does,
for this exact SKILL.md-frontmatter-parsing job). But `.github/workflows/toolkit-ci.yml`
already does `pip install pytest pyyaml` -- pyyaml is an established,
CI-available dependency for this repo, just previously test-only. Given
the parsing job is EXACTLY "parse a YAML `>` folded block scalar
correctly" (the existing test's own comment warns "a naive string-search
would treat the folded newlines differently than yaml.safe_load's real
folding rules"), reinventing a hand-rolled folder parser would repeat a
mistake already flagged in this codebase. `import yaml` with a plain
`try/except ImportError: yaml = None` + a loud stderr error message (not a
crash) at the top of `design_gate.py` was the right call, not a stdlib-only
rewrite.

## Frontmatter split pattern: reuse the existing one-liner, don't reparse

Every real `SKILL.md` starts with `---` on line 1. The existing test
(`test_user_prompt_skill_router.py`) already does
`content.split("---", 2)` -> `parts[1]` is the frontmatter text. Mirrored
exactly rather than writing a regex -- one canonical way to extract the
block in the whole repo now.

## Real "mentions any of:" list boundary: non-greedy regex to the first
## period+whitespace works, because the list itself is period-free

`re.compile(r"mentions any of:\s*(.+?)\.(?:\s|$)", re.IGNORECASE | re.DOTALL)`
correctly isolates the keyword list in every sampled real skill because
items like `Motion.dev`, `Barba.js` have a period NOT followed by
whitespace (mid-token), so the non-greedy match doesn't stop early -- it
stops exactly at the list's own terminating period before the next
sentence ("Covers the ..."). Comma-splitting must be quote-aware (a
trailing quoted example phrase, e.g. `"what's this animation called"`,
contains an apostrophe that must NOT be treated as closing the outer
double-quote) -- track `in_quote` and only close on the SAME quote char
that opened it, don't special-case apostrophes.

## Three false-positive traps found ONLY by running against the real repo
## (would have shipped broken without this step)

1. **Trailing punctuation glued onto word tokens.** A word regex that
   allows `.`/`-`/`/` mid-token (needed to keep compounds like
   `prefers-reduced-motion`, `3D/WebGL`, `Motion.dev` intact) also grabs a
   sentence-final period onto the last word: `"... out of scope here."` ->
   token `"here."`, which is a DIFFERENT string from `"here"` and silently
   escapes the stopword filter. This alone produced 27 fake "mutual
   contradiction" findings across the real repo (every skill's `Use when
   NOT:` ends in `out of scope here.` or similar). Fix: `raw.strip("./-+")`
   on every matched token before the stopword/length check. [[lessons]]

2. **Inverted "contradiction" semantics flag healthy skill boundaries.**
   First draft of the mutual-exclusion check said "A defers topic T to B
   AND B defers back to A" == contradiction. Ran for real:
   `design-3d` excludes 2D motion (-> design-motion) while `design-motion`
   excludes 3D/WebGL (-> design-3d) -- that's a textbook CORRECT
   complementary split, not a contradiction, and the naive check flagged
   it (and 6 other equally-healthy sibling pairs) as broken. The
   corrected definition: only flag when the SAME excluded ground is
   claimed by NEITHER skill's own positive keyword list anywhere in the
   repo (`_claimed_anywhere`) -- i.e. both sides punt and nobody actually
   owns it. A healthy pair's shared boundary term IS one side's own
   claimed keyword, so it's correctly suppressed.

3. **Cross-domain homonyms and stemming gaps still leak through after
   fix #2.** Remaining false positives after the semantic fix: `wiring`
   (design-flutter's "dependency wiring" vs electronics' physical
   wiring -- same word, unrelated domains) and inflection mismatches
   (`flashed` in one skill's exclusion vs `flash` in another's OWN
   keyword list; `3D-printing` hyphenated-as-one-token in an exclusion
   vs `3D printing` two-words-so-only-"printing"-survives in another
   skill's own list). Fixed with a minimal `_stem()` (strip ing/ed/es/s,
   never below 3 chars) plus hyphen-sub-part expansion, applied ONLY
   inside the `_claimed_anywhere` ownership check (not the exact-token
   "shared ground" display, which stays literal). `wiring`/`specific`
   added to the generic-terms stoplist as known homonym/non-distinctive
   words found this way.

**Rule for any future prose-heuristic linter over this SKILL.md corpus**:
running it against the real 87-skill corpus (not just eyeballing the
regex) is what surfaces these -- a synthetic 2-skill fixture with a
deliberately-orphaned exclusion term (`widgetsync`, claimed by neither
side) plus a deliberately-healthy shared term (`sharedwidget`, claimed by
one side) is the fastest way to prove BOTH the positive-detection path AND
the suppression path actually fire, since the real corpus currently has
zero live positives for the Type-2 checks (clean real-world scores don't
prove the mechanism works -- a synthetic fixture does).

## Verified real-corpus baseline (2026-07-16)

87 real skill `SKILL.md` files (excluding `.ref-repos`), 1 pre-existing
warning (`unmassk-typescript/skills/typescript-strict/SKILL.md` -- plain
unquoted `description:` scalar contains a literal `Language skill: ...`
mid-value, which YAML's plain-scalar rules forbid; genuine pre-existing
bug in THAT file, confirmed by inspection, not a parser bug in
design_gate.py -- not fixed here, out of scope for this task).

## Round 2 (Cerberus review, same day): 3 blockers + 2 improvements

1. **Digit-after-hyphen blind spot** (`find_dangling_skill_references`):
   `token_re` required `[a-z]` right after the hyphen, so the entire
   `-3d` family (`design-3d`, `unmassk-3d`, a hypothetical `foo-3dghost`)
   was structurally unreachable by the dangling-reference check. Fixed to
   `[a-z0-9]`. Verified with an isolated 2-skill fixture (`foo-3dwidget`
   real, `foo-3dghost` not) -- the real skill is correctly excluded, the
   fake one correctly flagged.

2. **Short-acronym filter ate live collisions** (`_is_distinctive`): the
   "single word, no hyphen/dot, len<4" filter dropped `dpa` (3 chars) and
   `mrr` (3 chars) even though both are REAL live collisions in the repo
   (`compliance-gdpr`/`compliance-legal-docs` both claim `DPA`;
   `db-vector-rag`/`unmassk-marketing` both claim `MRR`). Fixed by passing
   the PRE-normalization original term alongside the lowercased one:
   `original.strip().isupper()` overrides the length floor (an ALL-CAPS
   token in the source IS the technical-acronym marker), but the absolute
   `len(term) < 3` floor stays regardless, so 2-letter noise ("AI", "3D")
   still can't sneak through.

3. **0-skills-scanned silently read as CLEAN**: fixed with a `report["error"]`
   field set whenever `len(skills) == 0`, forcing `ok=False` independent
   of the allowlist (nothing to allowlist your way out of an empty scan).
   `main()` also echoes it to stderr as `FATAL: ...` regardless of
   `--json`/text mode. The final "Result:" line now reads `FATAL` (not
   the misleading `COLLISIONS FOUND`) when this path fires.

4. **Allowlist mechanism added** (`unmassk-toolkit/design-gate-allowlist.json`,
   sibling to `bin/`, overridable with `--allowlist`): a JSON object with
   one array per finding category (`keyword_collisions`, `phrase_collisions`,
   `dangling_references`, `mutual_contradictions`). Each finding gets a
   canonical string key (`_finding_key()`) -- the bare term/phrase for
   Type-1, `skill::token` for dangling refs, `skill_a::skill_b::shared,terms`
   for mutual contradictions (sorted, comma-joined). An allowlisted
   finding is tagged `[allowlisted]` in every report (never hidden) but
   doesn't fail the gate; anything else is tagged `[NEW]` and does. Seeded
   with the real baseline (10 keyword + 1 phrase + 1 mutual-contradiction
   finding) so a fresh CI run starts CLEAN and only a genuinely NEW
   collision breaks it.

5. **`extract_quoted_phrases()` scope narrowed** to the actual `asks to
   "..."` clause (via `_ASKS_TO_RE`, cut off at `or mentions any of:` /
   `Use when NOT` / end of description) instead of scanning the whole
   description for any double-quoted substring. This correctly drops a
   real false-inclusion (design-taste's `"make this not look like AI
   slop"` lives in ITS `Use when NOT:` clause, not an "asks to" example)
   and matches what the docstring always claimed. Known, accepted
   precision/recall trade-off: `media-remotion`'s description uses an
   alternate lead-in ("Trigger phrases:" instead of "the user asks to"),
   so its quoted examples (e.g. `"trim video"`, also claimed by
   `media-ffmpeg`) are no longer captured at all -- not fixed further,
   since broadening to catch alternate conventions wasn't asked for and
   would grow scope; documented as an observation instead.

**Side effect discovered by re-running against the real repo after fix
#5** (the reason "run it for real, don't just reason about it" matters):
narrowing the quote scan ALSO removed a previously-accidental capture --
`design-3d`'s "Covers ..." prose contains a quoted phrase `"3D/WebGL for
web"` that used to leak into its wordbag and (coincidentally) suppress 4
real mutual-contradiction findings between `design-3d`/`design-motion`/
`design-scroll`/`design-animation-formats` (all share the boundary term
`3D/WebGL`). Removing the leak correctly exposed that `_expand_variants`
only split compound tokens on `-`, never on `/` -- so `"3d/webgl"` (one
token, since `_WORD_RE` keeps `/` mid-token) never matched the plain
`"webgl"` keyword `design-3d` actually claims in its OWN "mentions any
of:" list. Fixed by extending `_expand_variants` to split on `/` the same
way as `-`. Rule for future edits to this script: any change to
`extract_quoted_phrases`/wordbag construction can silently remove a
FORTUITOUS suppression elsewhere -- always re-run the full real-repo scan
after touching that path, not just the fixture that motivated the change.

10 real Type-1 keyword collisions (`actuator`, `ccpa`, `connection
pooling`, `data breach`, `dpa`, `gdpr`, `hipaa`, `hreflang`, `mrr`,
`pgvector` -- `dpa`/`mrr` newly surfaced by fix #2) plus 1 phrase
collision (`onboarding flow`), and 1 real Type-2 mutual contradiction
(`design-motion` / `design-taste`, shared ground `slop`) make up the
current allowlist
baseline. Gate is CLEAN (exit 0) against the real repo with the allowlist
in place; exit 1 with the allowlist removed/pointed elsewhere (every
baseline finding reads `[NEW]` again) -- confirms the allowlist actually
gates, not just decorates.
