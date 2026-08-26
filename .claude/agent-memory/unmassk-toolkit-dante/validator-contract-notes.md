---
name: validator-contract-notes
description: unmassk-memory (v2) lib/memory/validator.py (RED, test-first) PIEZAS Sec.7.5 8-row contract -- the load-bearing piece (two callers must see one truth); "stops"/"is_distillation" not Note fields (disclosed extra params); mandatory isolated-tmp-dir mutation-check technique (never write into lib/memory/ while teammates work there)
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_validator.py` (8 tests, RED
by design) -- one test per row of PIEZAS.md Sec.7.5's "Sus tests" table,
literally, no extra coverage (same test-first acceptance-granularity
override as [config-contract-notes](config-contract-notes.md),
[rejection-contract-notes](rejection-contract-notes.md),
[zones-py-full-contract-notes](zones-py-full-contract-notes.md),
[similar-contract-notes](similar-contract-notes.md)).

**Why this piece is different from its siblings: it's the one place
"valid" is decided, called by exactly two consumers (`notes` and
`hooks/customs.py`).** PIEZAS frames the whole task around the v1
`Sources:` field death (obligatory per one agent, absent from the
parser's key list, silently dropped by all three readers) -- two
implementations of validity is how that happened. The task explicitly
forbids using a real git repo for any of the 8 rows: the validator's
`Context` is a pure input object built by the caller, so "same data,
same verdict, always" (row 8) is provable with zero commits.

**Signature reality check that shaped every row: `Context`/`validate_note`
are the ONLY fully-fixed signatures in PIEZAS Sec.7.5; the other ten
functions (`validate_headline`, `validate_pain_question`,
`validate_replacement`, `validate_fields`, `validate_distillation`,
`is_wip`, etc.) are listed with elided `(...)` args.** Two fields
that TEXTOS.md's own CLI examples use (`--stops yes/no` for the pain
question, and "is this a distillation" for §13's one-time v1-migration
notes) are **not** among `model.Note`'s 13 frozen fields (verified by
reading the real `model.py`, which landed mid-session from parallel
work) -- so they structurally cannot be read off a `Note` object.
Disclosed as extra parameters instead of forcing them into `Note`:
`validate_pain_question(note, stops)` and
`validate_distillation(note, is_distillation)`. Same "fails loud via
TypeError naming the mismatch, not a mute red" allowance already used
for `rejection.build(**parts)`. Row 3 ("dice entonces es una R") is
tested as a STRUCTURAL property (relaunch command matches
`\bnote\s+R\b`) rather than literal-copied TEXTOS prose, since it's a
*derived* fact (not an input echoed back) -- the marker-propagation
technique from rejection.py doesn't apply to derived facts, only to
echoed content (row 4's "candidatas completas" IS an echo, so that row
uses real marker strings in `why`/`keys`).

**`is_wip` tested at its own boundary, not through `validate_note`:**
`emojis.py` (already in production) states wip commits are written
directly by git, "no gitmem -- no tiene productor en este sistema" --
they never become a `Note` (no zones, no type). So "wip receives zero
questions" can only be tested as the predicate itself (`🚧` prefix
recognized/rejected correctly); the actual skip-wiring lives in
`hooks/customs.py` (Capa 6, unbuilt) and is out of scope for this file
-- disclosed explicitly rather than silently narrowing the row.

**NEW MANDATORY RULE from this task, now a standing practice for any
piece under active parallel construction: mutation-check in an
ISOLATED TEMP DIRECTORY, never in `lib/memory/`.** Prior contract
passes (config.py, rejection.py, zones.py) wrote a throwaway real
implementation directly into `lib/memory/<name>.py` and deleted it in
the same bash block -- safe when solo, but this task explicitly
prohibited it because teammates were writing real files in that same
directory concurrently (confirmed live: `model.py`, `config.py`,
`vocabulary.py`, `format.py`, `ids.py`, `similar.py`, `zones.py` all
appeared in `lib/memory/` mid-session, none touched). New technique:
`mktemp -d`, copy the REAL already-existing dependency modules
(`model.py`, `config.py`, `vocabulary.py`) into it, write a fake
`validator.py` there matching the disclosed contract, run a standalone
Python runner (`importlib.util.spec_from_file_location`, `sys.path`
pointed at the temp dir, never touching the real
`import_lib_memory_module`/`conftest.py`) that re-executes every
assertion from the real test file against the fake module, confirm all
pass (not vacuous), then `rm -rf` the temp dir and re-run the real
suite to confirm RED is unchanged. `git status --porcelain
lib/memory/` before and after must show zero lines attributable to
this session.

**Verification command used (matches the task's exact ask):**
`python3 -m pytest unmassk-toolkit/tests/memory/test_validator.py -v`
-> 8 errors, all `FileNotFoundError:
.../lib/memory/validator.py`, one per row -- RED for the right reason.
`conftest.py`'s `import_lib_memory_module` gained a content-hash cache
mid-session (parallel work, not mine) -- the `FileNotFoundError`
contract is unchanged by that, confirmed live.

**Scope note:** `conftest.py`, `test_conftest_smoke.py`, and every
sibling `lib/memory/*.py`/`tests/memory/test_*.py` file were already
modified/added by parallel agents before and during this task -- none
touched. Only `test_validator.py` is this session's change (confirmed
via `git status --porcelain`).

**Regression found post-implementation (2026-08-02) — `_present_fields()`
checks required-field presence by two DIFFERENT rules, and both let a
blank value through.** `description` uses truthiness (`if
note.description`) -- catches `""` but NOT whitespace-only (`"   "` is
truthy). `why` uses existence (`if note.why is not None`) -- catches
NEITHER `""` NOR whitespace-only, confirmed live via Moriarty's PoC
(`why=""` on a D returns zero rejections although `why` is
`required_fields` for D). Added two RED regression tests to
`test_validator.py` (not fixed -- that's Ultron's scope, per Dante's
absolute prohibition on implementing): `why=""`/`why="   "` on a D, and
`description="   "` looped over all seven real `vocabulary.TYPES` keys
(not a hardcoded list) with the type's OTHER required fields
(`why`/`awaits`) filled so the test isolates the description gap.
**Lesson for any future `lib/memory/*.py` required-field check: "is this
present" on a `str` field needs `.strip()` before the truthiness/None
check, not two inconsistent ad-hoc rules per field** -- the inconsistency
itself (one field stricter than its sibling in the same function) is
what let this slip past the original 8-row contract, which never tested
a blank-but-present value, only present-vs-absent.

**Regression found 2026-08-04 — `validate_pointers` (split into
`validator_pointers.py`, PIEZAS.md Sec.7.5, same file-size ceiling as
`validator_zones.py`/`validator_issue.py`) has a case/whitespace-sensitive
`_NOTE_ID_PATTERN` (`^[DMRQXIB]-\d+$`, no `re.IGNORECASE`, no `.strip()`).**
Reserved for exempting v1 commit hashes (`4f2a1bc`) cited in a distillation's
`origin` -- but the pattern also silently exempts a real note id typed
almost right (`d-030` for `D-030`, `D-030 ` with a trailing space) from ANY
dangling-pointer check, so the note saves linked to nothing and nobody is
ever told. **Fixed behavior locked in (orchestrator decision, revocable by
owner): reject, never auto-correct** -- reuses the existing `dangling_pointer`
rejection instead of inventing new TEXTOS.md prose. `replaces` was checked
too, but reading the code showed it was ALREADY correct (no shape-pattern
gate at all -- compared against `known_ids` unconditionally), confirmed by
a guard test, not assumed. 6 tests added to `test_validator.py` via
`validator.validate_pointers` (flat reexport, `validator_pointers.py` is
never imported directly in this repo's test style): 4 RED (lowercase
origin, leading/trailing-whitespace origin, lowercase R-incident-pointer,
mixed hash+bad-case in the same `origin` tuple), 2 green guards (v1 hash
stays exempt, `replaces` case-mismatch already rejects) that must survive
the fix unchanged -- `python3 -m pytest test_validator.py -q` -> 4 failed /
12 passed (all 12 prior tests untouched). **Same "two independently-written
values" rule as every prior contract here: the pointer string is the test's
literal, `known_ids` is a separately-built frozenset -- never compare a
result against itself.**

Reference: [config-contract-notes](config-contract-notes.md), [rejection-contract-notes](rejection-contract-notes.md), [zones-py-full-contract-notes](zones-py-full-contract-notes.md), [similar-contract-notes](similar-contract-notes.md)
