---
name: format-py-full-contract-notes
description: lib/memory/format.py full campaign merged from 2 files — original §6.4 RED contract (cross-import-identity incident) + 5 round-trip regressions (4 format.py, 1 zones.json)
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 3) from 2 separate files that both cover the SAME piece of
code — `lib/memory/format.py`'s `build_*`/`parse_*` producer/consumer pair — split only by which session
touched it. Round 2's fifth regression (zones.json `aliases` as a string instead of a list) is a minor
appendage of the same locked-in regression BATCH, not a separate zones.py campaign — it shares the batch's own
mutation-check technique and was tested alongside the four format.py bugs in one sitting; forcing it out would
split one coherent regression-locking session into two. Nothing was cut; each original file's content is
reproduced below verbatim under its own heading. Original filenames (now retired, kept only as history in
this note, not on disk): `format-contract-cross-import-risk-notes.md`, `five-regressions-format-zones-notes.md`.

**Deliberately NOT merged in here** (re-examined carefully this pass, per explicit instruction — "reléelo con
el cuidado que pediste... si fundirlo tergiversa, déjalo y explica por qué"):
- `similar-contract-notes.md` — `lib/memory/similar.py`'s own §6.5 contract. No file shares its theme; kept
  standalone. (`d054-shared-textnorm-normalization-contract-notes.md` touches `similar.find_similar` too, but
  only as ONE of three entry points it exercises for a different module's — `textnorm.py`'s — contract, not as
  a continuation of `similar.py`'s own campaign; see that file's own note below.)
- `d054-shared-textnorm-normalization-contract-notes.md` — genuinely a cross-cutting file about the shared
  `lib/memory/textnorm.py` normalization module, tested through THREE already-clustered entry points
  (`zones.normalize`, `similar.find_similar`, `rules.similar_existing`) plus a fourth outside `lib/memory/`
  entirely (`lib/checklist_state.py`). It never even mentions `format.py`. Forcing it into any one of the three
  entry-point clusters would misrepresent it as "that module's own work" when its real subject is the shared
  utility underneath all three. Left standalone.
- `moriarty-layer1-race-and-list-folding-regression-notes.md` — bundles TWO Moriarty-found bugs from the same
  session: `indexes.py`'s insert/remove race (the dominant one, its own text calls it "the serious one," ~2/3
  of the file, a real-process deterministic-race technique) and a smaller `format.py` folding gap (~1/3).
  Majority subject is `indexes.py`, not `format.py` — pulling it in here would misrepresent it the same way
  `customs-doctor-20260806-two-red-contracts-notes.md` was correctly left out of the customs.py cluster in
  phase 2. Left standalone.

## Round 1 — lib/memory/format.py §6.4 original RED contract + the cross-module-import-identity incident

Context: `unmassk-toolkit/tests/memory/test_format.py` (4 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.6.4, same acceptance-granularity pass as
[vocabulary-contract-notes](vocabulary-contract-notes.md) and
[memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md).
This is the piece the task called "la más importante de la capa" --
format.py is the producer/consumer pair (build_* / parse_*) for all
seven note types plus the `⏩` context commit.

**Two disclosed assumptions, same spirit as vocabulary.py's
FieldSpec/TypeSpec naming gap:**

1. **`SubjectParts`** (the return type of `parse_subject`) appears
   nowhere in model.py's thirteen declared classes (PIEZAS Sec.5.3) and
   is never described in prose. The emoji-position test
   (`test_emoji_after_brackets_enforced`) deliberately never constructs
   or inspects a `SubjectParts` instance -- it only checks string
   position in `build_subject`'s output and `is None` / `is not None`
   on `parse_subject`'s result, so it doesn't depend on guessing
   attribute names.

2. **`Note.timestamp` has no textual home in any TEXTOS Sec.5 template**
   (not even the `⏩` context commit). PIEZAS Sec.5.3 says it's "UTC,
   del autor del commit" -- its source of truth is git's author date,
   not commit body text. The round-trip helper (`_assert_fields_match`,
   see below) excludes `timestamp` when comparing `Note`/`ContextNote`,
   with the reasoning spelled out in the test file's module docstring.
   Flagged for whoever reviews the GREEN pass: if this reading is
   wrong, tightening it is a one-line change, not a redesign.

**INCIDENT during this task's live mutation-check -- real signal, not
just a self-inflicted mess.** Following the established pattern (build
a throwaway fake module, prove the 4 assertions are satisfiable, delete
it, confirm RED returns -- see vocabulary-contract-notes.md), wrote a
throwaway `lib/memory/model.py` + `lib/memory/format.py`. Mid-verification,
**a concurrent process (Ultron/parallel builders, per the task's own
"tres compañeros escribiendo en paralelo zones.py/config.py/similar.py"
context) started writing REAL content to the exact same `model.py` path**
-- it got truncated from my throwaway 4-class version down to a
production-shaped `IndexLine`-only version mid-run (confirmed via a
system reminder: "model.py was modified... this change was intentional").
**Cleaned up correctly:** deleted only my own untouched `format.py`
(confirmed via `git status` + content check it still had my own
"THROWAWAY fake" docstring, no external edits); left the concurrently-
owned `model.py` completely alone, did not attempt to restore or revert
it. Re-ran `test_format.py` after cleanup: still 4/4 ERROR, all
`FileNotFoundError` on `format.py` (RED for the right reason, just a
different missing file than before the collision -- still correct).

**Lesson for future test-first passes on THIS branch specifically:**
when multiple agents build sibling `lib/memory/*.py` files in the same
session, a throwaway file for a live mutation-check is a genuine
collision risk if its path is also a target another agent is actively
writing to. Before planting a throwaway production file for
verification, check `git status` on that exact path first -- if it's
already untracked-but-present (meaning some other process already
created it, even a stub), do NOT overwrite it wholesale; either pick a
path that can't collide, or skip the live-file verification technique
this round and say so explicitly in the report instead of forcing it.

**Real cross-module-import-identity risk this incident surfaced --
already independently confirmed by the parallel `test_zones.py` writer
(see [zones-contract-notes](zones-contract-notes.md), same session,
"CRITICAL infra gap"), so this is not a one-off artifact of the
throwaway harness above, it's a real property of `import_lib_memory_module()`.**
`format.py`'s declared signatures return `model.py`'s dataclasses
(`Note`, `ContextNote`, `IndexLine`, `ArchiveLine`). If production
`format.py` imports these via a normal `from .model import ...` while
the TEST harness loads each `lib/memory/*.py` file independently via
`import_lib_memory_module()` (a separate `spec_from_file_location` call
per module, synthetic non-dotted name, no parent package), zones.py's
writer found the production import itself fails outright
(`ImportError: attempted relative import with no known parent package`)
when probed through this harness -- a harder failure than the milder
one reproduced here (two *successfully* loaded copies of the same
source producing two distinct, mutually-`!=` classes). **Fix applied to
this test file in response, not deferred:** `_assert_fields_match()`
compares `Note`/`ContextNote`/`IndexLine`/`ArchiveLine` field-by-field
via `dataclasses.fields(expected)` + `getattr`, never `parsed ==
expected` -- so this test's round-trip assertions stay correct
regardless of which class-identity outcome the eventual conftest fix
produces. **This is now the standing rule for any round-trip test in
this repo comparing a `model.py` dataclass instance built through format/
parse:** compare fields, never the object with `==`. The underlying
infra gap itself (production `lib/memory/*.py` files being unable to
import a sibling through this harness at all) is zones.py's finding to
own, not re-litigated here -- confirmed still present and NOT fixed
(conftest.py was off-limits for this task, same restriction zones.py
had).

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory/test_format.py -v` ->
4 errors, one per row, all `FileNotFoundError` on whichever of
`model.py`/`format.py` was missing at that instant (lib/memory/ was
being actively written to by concurrent agents throughout this task --
the specific missing file varied between runs, always for the same
legitimate reason: the real production module genuinely doesn't exist
yet). Also confirmed `python3 -m py_compile` clean and
`pytest --collect-only` finds exactly the 4 intended tests, no
collection errors.

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md), [memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)

## Round 2 (2026-08-02) — 5 round-trip regressions locked in (4 in format.py, 1 in zones.json's aliases-as-string)

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
