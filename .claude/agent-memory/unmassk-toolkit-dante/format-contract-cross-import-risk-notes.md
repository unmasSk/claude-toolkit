---
name: format-contract-cross-import-risk-notes
description: unmassk-memory (v2) Capa 1 -- lib/memory/format.py (RED, no existe) contract tests from PIEZAS.md Sec.6.4, 4 rows; timestamp/SubjectParts assumptions disclosed, and a live-verification INCIDENT that surfaced a real cross-module-import risk for whoever builds format.py
metadata:
  type: project
---

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
