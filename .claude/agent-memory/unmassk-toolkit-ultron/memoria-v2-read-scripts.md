---
name: memoria-v2-read-scripts
description: Building bin/memory/search.py, boot.py, reindex.py, bench.py (capa 5, PIEZAS.md Sec.10, tanda de lectura) -- boot.py cwd-resolution bug fixed at the script layer (never touching lib/memory/boot.py), reindex.py's private-attribute reuse tradeoff, bench.py correctly left unbuilt
metadata:
  type: project
---

Building the four *read* scripts of memoria-v2's Capa 5 (`search.py`,
`boot.py`, `reindex.py`, `bench.py`, PIEZAS.md Sec.10) against tests
Dante had already written in red. See [[memoria-v2-build]] and
[[memoria-v2-write-scripts]] for the wider build context (the four
*write* scripts, `note.py`/`close.py`/`context.py`/`work.py`, built
earlier in the same layer).

## `boot.py` (lib/memory) has a real cwd-resolution bug -- fixed at the SCRIPT layer, never touching the library file

`lib/memory/boot.py::build()` computes `root = Path.cwd()` and uses it
for two things: `project=root.name` (display) and
`indexes.archived_ids(notes.pm_root(root))` (data). Its own docstring
documents the assumption "whoever calls already runs from inside the
repo." That assumption holds for `git log`-based reads (git resolves the
enclosing repo from any subdirectory) but **not** for
`notes.pm_root(root)`, which is pure path arithmetic (`Path(root) /
".claude" / "project-memory"`, no git call) -- from a nested subdirectory,
`Path.cwd()` is NOT the repo root, so both `project` and the indices read
point at the wrong place. Caught by
`test_boot_script.py::TestRepoResolvedByProcessCwd` (launches the script
from `<repo>/src/some/nested/place` and expects the exact same render as
from the repo root) -- confirmed live: output showed `MEMORIA · place`
instead of `MEMORIA · repo`.

The task's hard constraint was "no toques ningun modulo de
`lib/memory/`" -- so the fix does NOT touch `lib/memory/boot.py`. It goes
in `bin/memory/boot.py::main()` instead: `os.chdir(notes.repo_root())`
(which DOES resolve via `git rev-parse --show-toplevel`, confirmed
reading `gitcmd.repo_root()`) before calling `boot_lib.build()` --
normalizing the process cwd to the true repo root satisfies the
library's own documented assumption instead of violating it, entirely
from within the one file this task authorized touching. All 5
`test_boot_script.py` tests pass with this fix; 4/5 already passed
without it (only the nested-cwd one needed it) -- confirmed by running
before/after.

**Lesson for whoever eventually touches `lib/memory/boot.py` itself**:
the real fix belongs there (`root = notes.repo_root()` instead of
`Path.cwd()`), matching how `note.py`/`close.py`/`work.py` already do it
for `pm_root()`. The script-level workaround is correct and complete for
this task's scope, but it's a workaround, not a root-cause fix -- flagged
as an Observation in the final report, not silently left implicit.

## `reindex.py`: no library function does "rebuild the index from git" -- composed from existing pieces, reusing a PRIVATE sibling constant on purpose

PIEZAS.md Sec.10's row for `reindex.py` says "Llama a: `indexes` +
`health`" (two modules, not one dotted function like every other script's
row) -- deliberately looser than the "one function" rule that governs the
other ten scripts, because no single library function reconstructs an
index from git. The rebuild composes: `query.by_zone(None, None)` (all
real notes), `indexes.archived_ids(pm)` (what's already retired),
`indexes.read(name, pm)` per vigente file (what's on disk today), and for
each divergence in either direction, `indexes.insert()` (git has it, no
index file does -- not archived) or `indexes.remove()` (an index file has
it, git doesn't). Scope is intentionally narrower than
`health.coherence_rules()` (rules.md) -- PIEZAS.md Sec.9.4's own "Quien lo
llama" line names only `health.coherence(root)` for this script, not
`coherence_rules`.

**The one real friction**: knowing which of the seven vigente index files
a given note TYPE belongs to. That table exists in exactly one place in
the whole codebase -- `notes.py::_TYPE_TO_INDEX_FILE`, a leading-underscore
module attribute, never exported publicly (confirmed: no equivalent in
`vocabulary.py`, which only has the type vocabulary and the *file names*,
not the type->file mapping). Two options: (a) reach into
`notes._TYPE_TO_INDEX_FILE` directly (read-only, no edit to `notes.py`),
or (b) declare a second copy of the same seven-entry dict locally in
`reindex.py`. Chose (a): a second copy is exactly the "same fact typed
twice, drifts silently" pattern this whole memory system exists to kill
(cf. `SIMILARITY_THRESHOLD` being centralized into `vocabulary.py` after
living duplicated in `validator.py`+`rules.py`, and the three independent
`git log` readers consolidated into `query.run_git_log()` -- both
documented in [[memoria-v2-build]]). The established codebase pattern
when a sibling module needs an existing private helper is to make it
PUBLIC (drop the underscore, e.g. `query.is_unborn_branch`,
`rules.rules_file_path`) -- but that requires editing `notes.py`, which
this task's explicit scope forbids ("no toques ningun modulo de
`lib/memory/`"). Reaching into the private attribute read-only, without
editing the file, was judged the lesser deviation versus a second
hand-typed copy that WILL drift if `notes.py` ever gains/loses a type.
Flagged as a Suggestion for whoever next touches `notes.py`: promote
`_TYPE_TO_INDEX_FILE` to public, same treatment already given to three
other originally-private helpers in this exact codebase.

Verified live end-to-end (not just via the test): removing a note's line
by hand from `DECISIONS.md`, running `reindex.py` with no flags,
`rebuilt_content == original_content` byte for byte -- `indexes.insert()`
reproduces the exact same header + blank line + index-line structure that
the original single `insert()` call (from `notes.write()`) produced,
because the test's corruption helper only strips the line containing
`[note_id]`, leaving the blank line after the header intact.

## `bench.py`: correctly left UNBUILT -- the task's own warning was accurate, confirmed by reading the tree before writing anything

The task explicitly warned: the adversarial bench (PIEZAS.md Sec.14, ten
attacks) doesn't exist as any `lib/memory/` module yet, and said to STOP
rather than invent an empty bench that fakes a pass. Confirmed before
writing a single line: `ls lib/memory/` has no `bench.py`, no module
named anything adversarial, and no function anywhere that "runs the ten
attacks." `test_bench_script.py` itself only asserts the SCRIPT runs,
prints something non-empty, and never moves `HEAD` -- it does not check
attack count/names/format, exactly matching its own docstring's stated
narrow scope. Since PIEZAS.md Sec.10's row for `bench.py` says it calls
"el banco adversarial" (singular real thing, not "compose from existing
pieces" like `reindex.py`'s row), and no such thing exists, building
`bin/memory/bench.py` today would mean either inventing the ten attacks
(explicitly forbidden) or writing a script that calls nothing real and
just prints a fabricated "result" (a fake green test, exactly the
anti-pattern `unmassk-standards` and this project's own CLAUDE.md both
exist to prevent). Left unbuilt; 3/3 `test_bench_script.py` tests stay
red for this single, isolated, already-anticipated reason -- confirmed
each failure is "can't open file ... bench.py" (script absent), not a
logic bug.

## Full read-layer result, isolated

`pytest tests/memory/test_search_script.py -q` -> 7/7.
`pytest tests/memory/test_boot_script.py -q` -> 5/5.
`pytest tests/memory/test_reindex_script.py -q` -> 4/4.
`pytest tests/memory/test_bench_script.py -q` -> 0/3 (expected, see above).
Full `pytest tests/memory -q`: 214 passed, 3 failed (only bench) --
confirmed the 3 failures are exclusively `test_bench_script.py`, nothing
else regressed (`test_gitmem_facade.py` and the four write-script test
files re-checked in isolation, still green).
