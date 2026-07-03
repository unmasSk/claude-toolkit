---
name: crown-retraction-design-notes
description: Non-obvious design gotcha found while writing the Crown-retraction contract tests (unmassk-toolkit Mode C consolidator feature)
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
