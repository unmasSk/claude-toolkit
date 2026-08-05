---
name: five-regressions-format-zones-notes
description: unmassk-memory (v2) 5 round-trip regressions locked into test_format.py/test_zones.py (2026-08-02) -- headline/context-point newline, arrow-separator headline, comma-in-list, zones aliases-as-string; scratchpad-only mutation-check technique for verifying RED without touching lib/memory/
metadata:
  type: project
---

Context: five round-trip bugs in `lib/memory/format.py`/`zones.py` were
found and fixed by hand (verified by running, not reading) but had no
test locking them in place. Task: add them as permanent regressions to
`unmassk-toolkit/tests/memory/test_format.py` (4 tests) and
`test_zones.py` (1 test). Baseline 52 green, ended at 57 green, zero
regressions. This is a DIFFERENT test type than the contract-pass tests
already in those files ([format-contract-cross-import-risk-notes](format-contract-cross-import-risk-notes.md),
[zones-contract-notes](zones-contract-notes.md)) -- those describe a
design rule; these describe a specific failure mode that actually
happened, named in each docstring so the test isn't deleted as
apparent redundancy a year later.

**The five, and the property each one proves:**
1. Headline with embedded `\n` (subject folding) -- property: round trip
   identical, whatever the content.
2. Context point with embedded `\n` (context folding) -- same property,
   but the failure mode is worse: the WHOLE session-close note vanished,
   not just the one point (`parse_context_message` returned `None` on
   any non-`"- "`-prefixed line).
3. Headline containing the literal `  →  ` separator (this project's own
   prose uses that arrow constantly) -- archive-line parsing matched the
   FIRST occurrence instead of requiring the closed destination
   vocabulary after it.
4. A key/origin item containing `", "` (e.g. `"a, b"`) -- naive
   `join`/`split` without escaping split it into extra entries.
5. `zones.json` with `"aliases": "front"` (string instead of list) --
   `tuple("front")` silently chopped it letter-by-letter into five fake
   aliases, no error. **Different property than 1-4**: this one proves
   fail-loud (raises `ValueError` naming the file and the zone), not
   round-trip fidelity.

**Mutation-check technique used to prove RED-without-the-fix, extending
the scratchpad-only rule from
[mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md):**
copied `model.py`/`format.py`/`emojis.py`/`zones.py` into the session
scratchpad (never `lib/memory/`), wrote a small generator script
(`make_broken_variants.py`) that does a targeted `str.replace()` per bug
to undo ONLY that bug's specific mechanism (e.g. bug 1: `build_subject`
returns `prefix + note.headline` with no folding, `parse_message`'s
subject-continuation `while` loop removed; bug 5: the `isinstance`
shape-check block deleted, back to blind `tuple(aliases)`), each
`assert new_src != original_src` guarding against a silent no-op
replace. A second script (`probe.py`) loads each variant by file path
(`spec_from_file_location`, same mechanism as
`import_lib_memory_module`) and runs the exact same round-trip logic
the real test would, as plain asserts (no pytest) for fast iteration --
confirmed all 5 RED against the broken variant AND all 5 GREEN against
the real fixed module, before writing a single line into the actual
test files. This is a *generator* pattern (one script produces N
broken variants + a green baseline check) rather than the earlier
single-file edit/run/revert dance -- worth reusing whenever a task asks
to lock in several related regressions at once instead of one.

**Test design notes:**
- Bugs 1-4 all reuse the existing `_note()` factory and
  `_assert_fields_match()` helper already in `test_format.py` (see
  [format-contract-cross-import-risk-notes](format-contract-cross-import-risk-notes.md)
  for why field-by-field, never `==`) -- no new fixtures needed.
- Bug 3's regression note deliberately reuses `id="D-036"` and a
  rename-flavored headline (`"rename colors.py  →  emojis.py..."`),
  mirroring the exact example already in the module's own docstring
  (`format.py:87`) -- not invented, taken from the contract's own
  illustration of the failure.
- Bug 5's assertion checks BOTH `path.name` and the zone name
  (`"billing"`) appear in the `ValueError` message text -- matching the
  task's explicit ask ("nombrando el fichero y la zona"), not just that
  *some* exception was raised.

No production code touched. No file written under `lib/memory/` at any
point (confirmed via `git status --porcelain` before and after -- zero
new/modified files outside the two test files task-scoped to touch).

Reference: [format-contract-cross-import-risk-notes](format-contract-cross-import-risk-notes.md), [zones-contract-notes](zones-contract-notes.md), [mutation-check-collision-incident-ids](mutation-check-collision-incident-ids.md)
