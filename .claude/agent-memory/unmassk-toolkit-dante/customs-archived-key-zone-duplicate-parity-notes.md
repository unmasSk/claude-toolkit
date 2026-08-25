---
name: customs-archived-key-zone-duplicate-parity-notes
description: test_customs_archived_key_zone_duplicate_parity.py RED -- hooks/customs.py::_decide_note builds existing_in_zone from query.by_zone() with NO archived filter (note.py has it, customs.py doesn't), so a legit git commit gets falsely blocked citing an archived note
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_customs_archived_key_zone_duplicate_parity.py`
(4 tests: 2 RED, 2 GREEN) -- second entry point for the SAME class of bug
already fixed on the `note.py` side and documented in
[note-archived-similarity-bypass-contract-notes](note-archived-similarity-bypass-contract-notes.md).
`bin/memory/note.py::_build_context()` (note.py:154-156) filters
`query.by_zone()` against `indexes.archived_ids(pm)` before building
`existing_in_zone`. `hooks/customs.py::_decide_note()` (customs.py:666)
never got that filter: `existing_in_zone = query.by_zone(note.zone1,
note.zone2)`, raw, archived notes included. Same root cause the sibling
file already fixed on one call site, still open on the other -- two
producers of the same `Context`, only one patched.

**Isolated the exact-key-zone gate on purpose, not Jaccard:** used
`similar.py::_find_exact_key_match` (same keys tuple `("socket",
"leak")`, different headline/description every time) so the RED doesn't
depend on textual similarity tuning -- matches
[note-exact-key-zone-duplicate-gate-contract-notes](note-exact-key-zone-duplicate-gate-contract-notes.md).

**Commit message built from the real producer, not hand-typed:**
`format.build_message()` on a real `model.Note` -- same Sec.34
producer/consumer technique `test_customs_hook.py::_expected_block_text`
already uses, avoids duplicating the `[ID][zone1][zone2] emoji headline`
wire format or guessing `emojis.TYPE_EMOJI["I"]` by hand.

**`I` type has no `--replaces` field**
(`vocabulary.TYPES["I"].allowed_fields == {"description", "why", "keys",
"issue"}`) -- the overcorrection-guard test (archived A + live B, same
keys) can't use the `--replaces none` sentinel the M-type sibling test
uses; seeding B plain works anyway BECAUSE `note.py` already filters A
out (the GREEN control confirms this first). No `validate_pointers`
uniqueness check on `note.id` either -- a hand-picked fresh id
(`"I-777"`) for the commit-driven note needs no collision-avoidance
logic.

**Both RED failures show the precise bug shape, not "no blocking at
all":** the overcorrection-guard RED shows today's rejection naming
BOTH candidates (I-002 live, I-001 archived) -- proves the fix target is
"blocking against the wrong set", not "blocking too much/too little".

Verification: `python3 -m pytest
unmassk-toolkit/tests/memory/test_customs_archived_key_zone_duplicate_parity.py
-v` -> 2 failed / 2 passed. Ran alongside the full
`test_customs_hook.py` suite (65 passed / 1 skipped, pre-existing
win32-only skip) to confirm no collision on shared fixtures/helpers.

Reference: [note-archived-similarity-bypass-contract-notes](note-archived-similarity-bypass-contract-notes.md), [note-exact-key-zone-duplicate-gate-contract-notes](note-exact-key-zone-duplicate-gate-contract-notes.md)
