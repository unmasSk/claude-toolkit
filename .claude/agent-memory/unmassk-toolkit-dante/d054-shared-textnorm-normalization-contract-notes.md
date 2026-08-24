---
name: d054-shared-textnorm-normalization-contract-notes
description: D-054 + owner rule 2026-08-24 (lowercase+no-accent everywhere) — anchor-at-entry-point technique when a boundary test forbids one physical shared symbol; real contradiction found and left RED (non-string input)
metadata:
  type: project
---

Context: owner rule (2026-08-24) — every text used as a comparison/lookup
key normalizes to lowercase AND accent-stripped, everywhere. Three sites
only did `.lower()`: `lib/memory/zones.py::normalize`,
`lib/memory/similar.py::_tokens`, `lib/memory/rules_similarity.py::_tokenize`.
A fourth site, `lib/checklist_state.py::normalize_box_text`
([[zones-contract-notes]] sibling area, not linked before), already did
the full job (NFKD-strip-accents + casefold + dash-fold + whitespace
collapse) — confirmed by reading the file before writing any test, per
this agent's boot protocol.

**Architecture trap avoided, not fallen into:** my first read of the task
implied ONE physical shared function across all four sites. Before writing
a single test I read `tests/memory/test_boundary.py` (Sec.13 "puerta 3")
and confirmed it's REAL and enforced: `lib/memory/` modules import
NOTHING outside stdlib (rule 2), and nothing outside `lib/memory/` (except
`bin/memory/`, `bin/gitmem`, 2 hooks, `tests/memory/`) imports FROM
`lib/memory/` (rule 1). `checklist_state.py` lives in `lib/`, not
`lib/memory/` — a single shared symbol reachable from both sides is
architecturally impossible without breaking one of the two enforced
rules. Flagged this to the coordinator before writing tests; the
coordinator confirmed the same conclusion independently and settled it:
**two conscious copies** — `lib/memory/textnorm.py::normalize_text()`
serves the three memory-side callers, `checklist_state.py::normalize_box_text()`
keeps its own (already existed, richer: casefold+dash-fold+whitespace on
top of the same accent-stripping core).

**Technique going forward for this exact situation (a behavior contract
that must hold across a boundary the tests protect):** anchor every test
on the real PUBLIC ENTRY POINT of the module that consumes the shared
behavior (`zones.normalize`, `similar.find_similar`, `rules.similar_existing`
via the facade — never `rules_similarity` imported directly, since
`rules.py` is what production actually calls), never on the physical
shared symbol's name or location. This makes the contract survive
whichever module Ultron picks to hold the shared code, and it's exactly
why `test_zones.py`/`test_similar.py`/`test_rules_similarity.py` (new
file) never import `textnorm` directly — confirmed correct by observing
Ultron's real implementation land mid-session at `lib/memory/textnorm.py`
without needing any test edit.

**Real contradiction found, left RED, not resolved by me:** the owner's
KNOWN (task briefing) explicitly required "entrada no-string → '' sin
reventar" as part of the shared function's contract (point 1). Ultron's
`textnorm.normalize_text()` docstring explicitly documents the OPPOSITE
design choice: "`value` se asume texto (`str`): los tres llamadores...
siempre reciben `str` ya validado... no necesita ese blindaje" — and the
code has no guard (`unicodedata.normalize("NFKD", None)` raises
`TypeError`). `test_normalize_non_string_input_returns_empty_string_without_raising`
(test_zones.py) pins the literal contract given to me and stays RED
against Ultron's real, deliberate, documented decision — this is a
genuine spec/implementation conflict, not a bug to silently patch or a
test to quietly delete. Reported in the closing message for the
orchestrator/owner to settle (amend the contract, or ask Ultron to add
the guard) — not mine to resolve per this agent's own rules ("preserve
original test intent... if the new behavior doesn't make sense, report
it, don't fix it").

**Real accented-word Jaccard math used for the two RED-by-design
similarity tests** (`test_similar.py`,
`test_rules_similarity.py`) — computed on paper before writing, not
guessed: pick a candidate/existing pair whose ENTIRE shared vocabulary
carries an accent, so today's `.lower()`-only tokenizer produces
intersection 0 (or near it) — below `vocabulary.SIMILARITY_THRESHOLD`
(0.5) — and after accent-stripping the same words become byte-identical,
intersection == union == 1.0. A negative control needs words that are
genuinely different even after stripping accents (e.g. "facturación" vs
"autenticación" — distinct roots, accent-strip doesn't touch that), kept
using ONLY a shared filler word or two so its Jaccard stays clearly under
threshold both before and after — proves stripping accents doesn't
over-merge.

**Guard test technique (owner-metric-over-allowlist,
[[dante-owner-metric-over-allowlist-feedback]]):** the "24 real zones
must not merge" requirement was written as a COMPUTED metric
(`len(set(normalized_names)) == len(names)`) read live off the real
`.claude/project-memory/zones.json` of this repo, never a hand-typed list
of the 24 names — survives the list changing without anyone touching the
test.

Full-suite verification: `python3 -m pytest unmassk-toolkit/tests -q` →
1182 passed, 1 failed (the non-string contradiction above), 2 skipped
(pre-existing, unrelated to this task). `test_boundary.py` unaffected —
18 passed, same pre-existing symbol-without-caller list as before this
session (unrelated debt, not touched).

Reference: [[zones-contract-notes]], [[similar-contract-notes]],
[[dante-owner-metric-over-allowlist-feedback]]
