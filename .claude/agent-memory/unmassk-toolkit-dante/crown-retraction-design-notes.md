---
name: crown-retraction-design-notes
description: Non-obvious design gotchas in unmassk-toolkit's Crown mechanism (Mode C consolidator) — multi-crown retraction edge case, and the tombstone-vs-crown-override gap (CRB-01)
metadata:
  type: project
---

unmassk-toolkit's memory-Crown feature (gitto.md Mode C — Consolidator) is
gaining a **retraction** mechanism: a `Retract-Crown: <hash>` trailer on a new
memo/decision commit tells boot to stop rendering that specific crown commit
as 👑. As of 2026-07, this was documented in `agents/gitto.md` with zero code
support (`lib/constants.py`, `hooks/session-start-boot.py`,
`hooks/*-validate-commit-trailers.py` had no `Retract-Crown` references).
Contract tests live in `unmassk-toolkit/tests/test_crown_retraction.py`
(test-first pass, written before Ultron implemented anything).

**Why:** the retraction spec has a subtle multi-crown edge case that a naive
implementation gets wrong, and it's easy to miss without writing it out.

**The trap:** implementing retraction as a simple per-commit patch —
`is_crown = (trailers.get("Crown") == kind) and (commit_sha not in retracted_hashes)`
— looks sufficient and passes the simple single-crown case, but FAILS the
multi-crown (re-consolidation) case: if scope X has an older crown A and a
newer crown B (B superseded A the normal way), and B later gets retracted,
this naive patch makes B's `is_crown` False, and then the existing
scope-dedup loop (`elif is_crown: replace non-crowned entry`) lets the OLDER,
already-superseded crown A resurface as if it were still active. The spec
explicitly forbids this: retracting the newest/active crown must fall back to
**fully uncrowned**, never to an older superseded crown.

**How to apply:** the correct implementation must track, per scope, whether a
*newer* crown has ever existed for that scope during the scan — not just
whether the current commit's own crown status survives retraction. Concretely:
only the single most-recent crown commit per scope is ever a retraction
candidate; once retracted, older crowns for that same scope must stay inert
even though they were never themselves retracted. This is exactly what
`test_11_retracting_newest_crown_falls_back_to_uncrowned_not_older_crown` in
test_crown_retraction.py pins down — if Ultron's implementation passes
test_10 (retract older, newer stays 👑) but fails test_11, that's the naive
per-commit patch, not the full fix.

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md).

## CRB-01 — crown-OVERRIDE branch skips the tombstone check (Cerberus finding, session 2026-07-05)

A SIBLING bug to the multi-crown edge case above, found during a full audit
of `session-start-boot.py`. Both `extract_glossary()`'s own Memo-dedup loop
and `main()`'s glossary-merge loop for MEMOS have TWO branches per entry:
an INSERTION branch (first time this scope is seen) and an OVERRIDE branch
(`elif is_crown:` / `elif gis_crown:` — a crowned entry replacing an
already-present non-crowned one for the same scope). The insertion branch
correctly checks the tombstone set (`normalize(text) not in tombstones`);
the OVERRIDE branch does not check it at all.

**Reproduction shape** (see `test_boot_tombstones.py::TestCrownOverrideResurrectsTombstonedMemo`):
old crowned Memo commit for scope X → `Resolved-Memo:` trailer retiring
that exact text → enough filler commits to push BOTH beyond SCAN_DEPTH=30
(so only `extract_glossary()`'s full-history scan sees them, not
`extract_memory()`) → a NEWER, non-crowned Memo commit for the SAME scope
X inside the recent window. `extract_glossary()` walks newest-first,
inserts the newer non-crowned entry first (tombstone check passes, it was
never retired), then later reaches the older crowned commit — since the
scope is already occupied by a non-crowned entry, it takes the override
branch and swaps in the OLD, explicitly-retired text, with no tombstone
check. `main()`'s own glossary-merge override branch repeats the same
mistake on top of that.

**How to apply:** the fix needs the override branch's tombstone check
added in BOTH places (`extract_glossary()`'s Memo loop AND `main()`'s MEMOS
merge loop) — fixing only one still leaves the bug reachable via the other
path, since either one alone can perform the unchecked resurrection.
