---
name: boot-contract-root-vs-pmroot-notes
description: test_boot.py RED contract (PIEZAS Sec.9.5) -- which "root" to seed indexes at depends on which module you're feeding, not on copying a sibling file's literal code
metadata:
  type: project
---

Writing `tests/memory/test_boot.py` (boot.py = PIEZAS.md Sec.9.5, the
"menu del dia") surfaced a landmine worth remembering for any future
`lib/memory/` test: **there are TWO different, both-real, both-in-production
conventions for where the 8 index files live, and picking the wrong one
for your dependency breaks the test for reasons unrelated to the module
under test.**

**The measured fact** (confirmed by running `pytest tests/memory/test_report.py -q`
before writing anything -- 1 of 4 tests fails today with
`ValueError: 'M-001' no esta en MEMOS.md`): `notes.write()` resolves its
`root` via `gitcmd.repo_root(Path.cwd())` and passes that literal repo
root straight to `indexes.seed()`/`indexes.insert()` -- never
`<root>/.claude/project-memory/`. This is a known, queued bug (DEUDA.md).

Two sibling test files cope with it in two DIFFERENT, both-correct ways,
because they depend on different production modules:

- `test_report.py`/`test_report_render.py` seed at `_pm_root(root)`
  (`.claude/project-memory/`) because `report.py` itself (already
  written, already green) NEVER reads the 7 vigente index files at
  all -- it reads notes via `query.by_zone`/`query.by_word` (git
  history directly) and only touches `zones.json`/`ARCHIVED.md` at
  `_pm_root`. Seeding indexes at `_pm_root` is for the record only
  (satisfies `indexes.seed()`'s idempotent precondition on SOME path);
  report.py's own reads never look there for the 7 vigente files.
- `test_health.py` (already green) seeds and calls
  `health.coherence(root)`/`health.duplicates(root)` with the LITERAL
  repo root, matching where `notes.write()` actually writes -- because
  `health.py`'s functions take `root` as an explicit parameter and its
  own contract, as written, expects the caller to pass the real
  location.

**Rule going forward:** before copying "the seeding form that dodges
the bug" from any sibling test file, check WHICH production module your
new module depends on (declared in PIEZAS.md "con que se construye"),
and use THAT module's own established root convention -- verified by
reading its real, already-green test file -- not the first sibling test
file you find. Blindly copying `_pm_root(root)` into a module that
depends on `health.py` (not `report.py`) reproduces the exact
`FileNotFoundError`/`ValueError` the copy was supposed to avoid, just at
a different call site.

Verification technique used before trusting this: wrote a throwaway
script in the scratchpad dir (never in the repo) that exercises
`notes.write()` + `indexes.remove()` + `health.coherence()` against a
real temp git repo, confirmed the exact discrepancy tuple
(`('M-001: existe en git pero falta en el indice',)`, `lineas=1,
notas=2`) before writing any assertion depending on it -- cheaper than
discovering a wrong assumption after Ultron implements against the RED
contract.

**UTC round-trip gotcha, same session:** `context.latest()` returns the
git commit's REAL author-date timestamp with its LOCAL offset (e.g.
`+02:00`), never normalized to UTC. A test asserting "the hour carries
its UTC label" must derive the expected day/hour via
`timestamp.astimezone(timezone.utc)` before formatting -- comparing
against the raw local-offset value would make the assertion pass or
fail based on the machine's timezone relative to a day boundary, which
is exactly the two-machines-disagree bug the row exists to prevent.

Related: [issue-63-managed-blocks-hardening-notes](issue-63-managed-blocks-hardening-notes.md) for the general
`import_lib_memory_module` FileNotFoundError-as-RED pattern this whole
branch relies on.
