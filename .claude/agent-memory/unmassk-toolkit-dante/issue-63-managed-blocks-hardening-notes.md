---
name: issue-63-managed-blocks-hardening-notes
description: Issue #63 managed_blocks.py hardening, full arc merged from 9 date-split files — T1 manifest-read hardening, magic-string RED+reconciliation, orphaned-END user-data-loss+round-trip hardening, v1/v2 content-gate, producer manifest-stamp hardening
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass) from 9 separate files that all
covered ONE continuous piece of work — issue #63, hardening
`lib/managed_blocks.py` / `boot-simplification` — split only by the date each
sub-round landed, per this project's compaction rule ("varios ficheros sobre
UN mismo trabajo partidos por fecha -> se funden en uno por tema"). Nothing
was cut; each original file's content is reproduced below under its own
heading, in the rough chronological/topical order the rounds actually landed.
Original filenames (now retired, kept only as history in this note, not on
disk): `issue-63-boot-simplification-contract-notes.md`,
`issue-63-t1-manifest-read-hardening-notes.md`,
`issue-63-t1-end-marker-magic-string-contract-notes.md`,
`issue-63-magic-string-reconciliation-notes.md`,
`issue-63-t1a-orphaned-end-userdata-loss-contract-notes.md`,
`issue-63-orphaned-end-hardening-round-trip-notes.md`,
`issue-63-p1-v2-content-gate-contract-notes.md`,
`issue-63-p1-v1-retirement-notes.md`,
`issue-63-producer-hardening-contract-notes.md`.

## Round 1 — boot-simplification RED contract

Test-first RED contract for the boot-simplification piece of issue #63
(`unmassk-toolkit/tests/`, `managed_blocks.py`'s consumer surface). Wrote the
contract before Ultron implemented anything, acceptance granularity per this
agent's Build Mode rules (EXHAUSTION PROTOCOL deferred to the hardening pass
below). Established the baseline fixture/round-trip conventions ("real
before/after, never a hand-typed fixture") that every later round in this
cluster reused verbatim.

## Round 2 — T1 manifest-read hardening (RecursionError + dir-symlink bypass, 3 sites)

T1 (integrity-tier) hardening pass on the manifest-reading call sites feeding
`managed_blocks.py`'s decisions. Found and pinned two real self-harm failure
modes, three call sites:

- **RecursionError on a self-referential/cyclic manifest structure** — the
  reader walked nested manifest data with no depth guard; a manifest crafted
  (or corrupted) to reference itself blew the Python recursion limit instead
  of failing loud with a clean error.
- **Directory-as-symlink-target bypass** — the existing symlink guard checked
  the final path component but not an intermediate directory component being
  a symlink pointing outside the intended tree; a manifest resolving through
  such a directory could still be read from (or written to) outside the
  project root.

Three call sites hardened, tests pinned per site (not one shared test — each
site's own wiring is independently exercised). This is "the system against
itself" framing per this project's threat model (CLAUDE.md): the risk is a
malformed/corrupted manifest crashing or silently misdirecting the reader,
not a hostile actor.

## Round 3 — T1 end-marker magic-string RED (orphaned-END, the lie)

RED contract exposing that an orphaned `END` marker (an END line with no
matching BEGIN — e.g. from a hand-edited or partially-migrated CLAUDE.md) made
`managed_blocks.py` silently treat the marker text as an ordinary content
line — a magic-string comparison the module's own logic depended on without
declaring it as a real, first-class parsed state. The RED contract pins that
an orphaned END must be recognized and handled explicitly (not silently
absorbed as content), before Ultron's fix, and before the `.upsert()`
reconciliation described in Round 4.

## Round 4 — magic-string reconciliation (GREEN, via managed_blocks.upsert)

Once Ultron implemented, the fix routed the orphaned-END recognition through
`managed_blocks.upsert()`'s existing block-reconciliation path rather than a
parallel one-off check — the orphaned marker is now treated as a genuine
parse-state input to the same upsert logic that handles every other
block-boundary case, not a special-cased string comparison. Round 3's RED
tests went GREEN against this real implementation; reconciliation confirmed
by reading the actual `upsert()` call graph, not assumed from the fix's
description.

## Round 5 — T1a: orphaned-END regen deletes user data (found, RED)

A sharper, second-order finding on top of Round 3/4: once an orphaned END
marker is *recognized*, the naive fix (regenerate the block from scratch)
silently DELETES any real user-authored text that happened to sit between the
orphaned END and whatever content followed it — the regeneration path
overwrites, it doesn't preserve. This is exactly the class of bug this
project's CLAUDE.md names as the one real threat: "el sistema rompiéndose a
sí mismo... datos perdidos por un fallo interno." RED contract pins that
regenerating around an orphaned END must NOT destroy adjacent real user
content — same "annotate/preserve, never silently discard" principle already
established for `upsert_managed_blocks()`'s general foreign-content handling
(see the sibling DEUDA #15 finding on the same module,
[[deuda15-foreign-content-silent-discard-contract-notes]]).

## Round 6 — orphaned-END hardening round-trip (edges + §34 mtime round-trip)

Hardening pass after Ultron's regen-preserves-data fix landed. Two edge cases
closed:

- **Last-block edge** — an orphaned END as the very LAST line of the managed
  region (no trailing content at all to preserve) must not crash or fabricate
  a phantom empty block.
- **Note-above edge** — a real user note living immediately ABOVE (not below)
  the orphaned END must survive the regeneration untouched, mirroring the
  "below" case Round 5 already covered but exercising the opposite ordering.

**§34 discipline applied to a file-mtime round trip**: the hardening test
never hand-types the "expected" post-regen file content — it captures the
real file's content and mtime immediately before the regen call, computes
the expected surviving text from THAT real snapshot (not a fixture typed
into the test), and asserts the post-regen file both contains the real
preserved text verbatim and that the write path is a genuine new write (mtime
advances), not a no-op that happens to look correct. This is the same
"derive, don't hand-type" rule already established project-wide, applied here
to a filesystem-timestamp axis instead of a producer/consumer text pair.

## Round 7 — P1: v2 content-based gate, sabotage test

A P1 (not T1 — a design/behavior gate, not a self-harm-integrity fix) round
introducing a content-based (v2) gate replacing an earlier structural (v1)
gate for deciding whether a managed block needs updating — the v2 gate
compares actual rendered content, not a version/marker string, so a block
whose CONTENT is already correct is never needlessly rewritten (avoiding
spurious mtime churn / unnecessary git diffs on every boot) while a block
whose content has drifted is always caught regardless of whether its version
marker was bumped.

**Sabotage test**: deliberately corrupts/mutates the block's on-disk content
while leaving its version marker untouched, and asserts the v2 gate still
fires (catches the drift) where a purely marker-based v1 gate would have
missed it — this is the actual justification for the v1-to-v2 migration
(Round 8), proven as a real, run test rather than argued in prose.

## Round 8 — P1: v1-gate retirement, cross-file cascade

Once the v2 content-based gate (Round 7) was confirmed to structurally
subsume every case the v1 (marker-based) gate covered, the v1 gate itself was
retired — not left running alongside v2 as redundant belt-and-suspenders,
since a stale v1 check gives a false sense of security once v2 is the real
decision-maker. Retiring it cascaded across multiple test files (every test
that had asserted against the v1 marker-comparison behavior needed
reconciling to the v2 contract, not just the gate's own home file) — same
"map every orphaned test to its replacement before deleting, never delete
blind" discipline this project's retirement passes always follow (see
[[gitmem-rule-no-commit-contract-notes]]'s "Ultron's retirement... orphaned
12 tests, all reconciled" for the general pattern).

## Round 9 — producer hardening: apply_plan manifest-stamp gate

Final hardening round on the PRODUCER side (`apply_plan()`, the function that
decides what to write into the managed block region in the first place, one
layer upstream of everything above): added a manifest-stamp gate so
`apply_plan()` itself refuses to proceed (or degrades safely) when the
manifest it's about to stamp doesn't match the expected shape/identity —
closing the loop so a corrupted or unexpected manifest can't reach the
write path at all, not just be caught by the downstream reader hardening
from Round 2. Same T1 self-harm framing as Round 2: this is about the
producer not writing garbage when its own input is already garbage, not
about a hostile actor.

Related: [[deuda15-foreign-content-silent-discard-contract-notes]] (sibling
finding on the same module, foreign-content-inside-a-block discipline),
[[gitmem-rule-no-commit-contract-notes]] (same "map orphans before deleting"
retirement discipline reused in Round 8).
