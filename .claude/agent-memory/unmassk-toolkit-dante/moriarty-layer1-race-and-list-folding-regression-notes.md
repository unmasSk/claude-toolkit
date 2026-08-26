---
name: moriarty-layer1-race-and-list-folding-regression-notes
description: unmassk-memory (v2) two Moriarty-found, hand-fixed bugs locked into permanent regressions (2026-08-02) -- indexes.py insert/remove real-process race (deterministic forced-window technique, no 40-trial statistics needed) and format.py Keys/Origin/Replaces missing _fold
metadata:
  type: project
---

Context: Moriarty broke layer 1 and found two bugs Cerberus/Argus missed,
already fixed by hand but with zero test coverage -- same pattern as the
[format-py-full-contract-notes](format-py-full-contract-notes.md)
batch earlier the same day. Task: lock both in as permanent regressions.
Baseline 61 green -> 63 green in the two touched files (test_notes.py's
6 errors were a concurrent colleague's in-progress `notes.py`, unrelated,
confirmed transient -- resolved on its own moments later to 69 green
total, never touched by this task).

**Bug 1, the serious one -- `indexes.py` insert() vs remove() real-process
race, `test_indexes.py`.** Two real OS processes (not threads -- the
historical bug model, `insert()` with NO `file_lock()` at all, doing a raw
`path.open("a")` append, genuinely races against another process's locked
critical section in a way a same-interpreter thread wouldn't reliably
model) racing insert vs. remove on the SAME index file lost the newly
inserted note silently (both processes exit 0). "insert vs insert held up
fine" (OS append is atomic on its own) -- what broke was mixing insert
with a full rewrite (`remove()`'s read-modify-write).

**Technique: deterministic forced-window race, not 40-trial statistics.**
The original bug was found via 40 real-process trials, 25 failures
(62.5%) -- flaky by nature, timing-dependent. Rather than porting that
statistical shape into the permanent suite (slow AND still not
guaranteed to catch a regression), built a **deterministic forced-window**
construction instead, reusing the marker-file-handoff family of
techniques from
[file-lock-lost-update-contract-notes](file-lock-lost-update-contract-notes.md):
monkeypatch `pathlib.Path.read_text` (class-level, contained to ONE
subprocess only, never touching the file on disk) so that ONLY the call
matching the target index path does: real read -> write a "read done"
marker -> block-poll for a "release" marker before returning. The parent
test spawns the `remove()` subprocess first, waits for its "read done"
marker (proving remove's read already landed), THEN spawns a real,
unmodified `insert()` subprocess, gives it a fixed head start (0.3s) to
run to completion, and only THEN releases remove's pause. This forces
insert() to land (or attempt to land, if it correctly blocks on the real
lock) EXACTLY inside remove()'s read-to-write gap, every single time --
zero reliance on OS scheduler luck. Verified in BOTH directions before
writing the shipped test (scratchpad,
`dante_bug_regressions_20260802/race_probe_v2.py` +
`dante_bug_regressions_20260802/indexes_bug/indexes.py`, never
`lib/memory/` on disk): 5/5 against real fixed code (D-099 survives,
D-005 gone, both rc=0 -- because insert(), when it finally acquires the
lock after blocking, does its READ inside the same locked section, so it
always sees remove()'s already-landed write, never stale data) and 5/5
against a mutated copy with `insert()` reverted to the historical
unlocked-append model (D-099 NEVER appears in the final index, both
processes still rc=0 -- exactly "los dos procesos terminaban con exito,
sin un solo error").

**General technique worth reusing for any future insert-vs-rewrite race
regression on this codebase:** identify which side of the race is the
"rewrite" (reads the whole file, computes a derived result, writes back)
and patch ITS `Path.read_text` (or whatever its read primitive is) to
pause AFTER the real read returns, gated behind a marker; run the other
(unmodified) side for real during that pause; release the pause; assert
the final state. This is strictly more powerful than patching the
"insert-like" side's write function (tried first, see below) because it
targets the actual vulnerable window (the rewriter's read-to-write gap),
not just adds delay somewhere plausible-looking.

**Dead-end tried first, worth remembering to skip next time:** initially
patched `indexes.atomic_write` (via `indexes.atomic_write = wrapper`,
the name-bound-at-import trick already established in
[unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md))
on the INSERT side to widen ITS critical section instead. This only
proves the fixed code's `file_lock()` serializes correctly (which it
does, 5/5 GREEN) -- it does NOT discriminate the historical bug, because
if you narrow the mutation to "lock wraps only the write, not the read"
(a second plausible undo of the fix, matching indexes.py's own docstring
literally: "no solo la escritura"), the marker fires only AFTER insert's
unprotected read already happened, so remove() (spawned only after
seeing that marker) can never land inside insert's read-write gap either
-- the test stays vacuously green against a genuinely broken variant.
Realized this by tracing the exact write-ordering by hand before trusting
the first construction; switched to patching remove()'s read side (the
rewriter) instead, which correctly discriminates both undo variants.

**Bug 2 -- `format.py` `Keys`/`Origin`/`Replaces` written raw, no
`_fold`, `test_format.py`.** `_body_field_line()` wrote these three via a
plain f-string (`f"Keys: {_encode_list(note.keys)}"`) while
`Why`/`Awaits`/`Description` already went through `_fold()`. A key with
an embedded `\n` produced an unfolded raw continuation line that
`_parse_body_fields` couldn't recognize (doesn't start with the
continuation space, doesn't match any field prefix) -- `parse_message`
returned `None`, silently, no exception, losing the WHOLE note (not just
the field) exactly like bugs 1/2 in the earlier five-regressions batch.
Reused the exact same `_note()`/`_assert_fields_match()` machinery
already in the file (see
[format-py-full-contract-notes](format-py-full-contract-notes.md)),
no new fixtures needed. Mutation-check (scratchpad,
`dante_bug_regressions_20260802/format_bug/`, reverted `_fold` back to
raw f-strings for the three fields): `parse_message` returned `None`
against the broken copy, round-tripped correctly against the real file.

Both mutation-checks ran entirely from
`dante_bug_regressions_20260802/` in the session scratchpad -- zero
writes to `lib/memory/` at any point (confirmed via `git status
--porcelain` before/after: only `tests/memory/test_indexes.py` and
`tests/memory/test_format.py` show as touched, both already untracked
new files on this branch, no diff to any `lib/memory/*.py`, matching the
2026-08-02 absolute ban documented in
[mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)).

Reference: [format-py-full-contract-notes](format-py-full-contract-notes.md), [file-lock-lost-update-contract-notes](file-lock-lost-update-contract-notes.md), [indexes-contract-and-shared-dir-incident-notes](indexes-contract-and-shared-dir-incident-notes.md), [format-py-full-contract-notes](format-py-full-contract-notes.md), [mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)
