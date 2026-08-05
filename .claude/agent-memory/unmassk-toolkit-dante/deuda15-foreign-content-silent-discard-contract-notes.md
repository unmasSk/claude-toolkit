---
name: deuda15-foreign-content-silent-discard-contract-notes
description: DEUDA.md #15 RED contract — upsert_managed_blocks() overwrites foreign/hand-written content inside an existing block's BEGIN/END markers with zero trace in its only output channel (the log list)
metadata:
  type: project
---

## The gap (real incident, 2026-08-02)

A state note was hand-written inside an existing managed block in this
project's own `CLAUDE.md`. Next session start, `upsert_managed_blocks()`
matched `BEGIN...END` non-greedy and replaced the whole span with the
canonical body — the note vanished. Only trace: the generic log line
`"updated {begin}"`, which carries none of the destroyed content. Recovered
by luck from conversation history, not from anything the function reported.

## Test written (RED, confirmed for the right reason)

`unmassk-toolkit/tests/test_managed_blocks.py::TestUpsertManagedBlocks::
test_foreign_content_inside_block_is_not_silently_discarded` — writes a
distinctive non-canonical note into `BLOCKS[3]`'s interior (text the
generator never produced — compares two separately-written things: the
test's note vs. the function's canonical body), then asserts the note is
recoverable from `log`. Fails today: `log` only ever contains short
templated strings (`"unchanged {begin}"` / `"updated {begin}"` / `"appended
{begin}"` / `"removed legacy ..."` / `"regenerated {begin} (orphaned END
marker)"`), never the actual old interior content.

## What the test deliberately does NOT decide

Whether the fix should refuse-to-overwrite-and-warn, or overwrite-and-warn
(surface the destroyed content in the log/return so it's recoverable). No
document says which. Left as an open question for Ultron to raise with the
owner — the test only pins "it notices and says so," not the remediation
shape.

## Output-channel finding (for Ultron)

`upsert_managed_blocks()`'s ONLY output channel today is its own
`log: list[str]` return value — no stdout/stderr writes inside
`lib/managed_blocks.py` itself. Callers (`session-start-crew.py`, the
installer) decide what to do with that list. So the fix has to either (a)
embed lost-content evidence into existing log strings, or (b) extend the
return shape (e.g. a third tuple element) — both are viable from the
module's current API surface, neither is forced by the test.

## Existing coverage this sits next to

`test_outdated_block_is_updated` (same file) already covers the *ordinary*
stale-body case (canonical text differs from a prior canonical version) and
asserts the current generic `"updated {begin}"` behavior as correct —
that's the routine-refresh path, deliberately left alone. The new test
targets specifically the silent-discard-of-foreign-content failure mode,
not routine staleness.

Related: [issue-63-t1-end-marker-magic-string-contract-notes](issue-63-t1-end-marker-magic-string-contract-notes.md),
[issue-63-magic-string-reconciliation-notes](issue-63-magic-string-reconciliation-notes.md) —
same module, same BEGIN/END marker matching machinery, different bug class.
