---
name: issue-double-registration-and-notes-path-bug-notes
description: conftest.py import_lib_memory_module double-registration fix (plain sys.modules name, adopt-existing) + real production bug found in notes.py (wrong index root, not report.py/indexes.py)
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/conftest.py`, 2026-08-02, same day
as [import-lib-memory-module-cache-fix-and-stash-incident-notes](import-lib-memory-module-cache-fix-and-stash-incident-notes.md)
which added the content-hash `_MODULE_CACHE`. Only file touched:
`conftest.py`. No production file touched (task explicitly forbade it).

**Bug 1 — double registration, root cause and fix.** The cache fix above
still named every loaded module `f"lib_memory_{module_name}"` in
`spec_from_file_location` and never touched `sys.modules`. That's fine
in isolation, but `lib/memory/` siblings import each other PLAINLY
(`from model import ZoneReport`, PIEZAS.md Sec.3.3bis) — a real Python
`from X import Y` statement, which is NOT routed through our loader.
When `zones.py` (loaded via our function) executes that import during
its own `exec_module()`, Python's normal import machinery searches
`sys.path` (which includes `LIB_MEMORY_DIR`), finds `model.py` fresh,
execs it AGAIN, and registers it as `sys.modules['model']` — a SECOND,
distinct module object from whatever our loader separately produced
under the name `lib_memory_model`. A frozen dataclass's `__eq__`/
`isinstance` checks `__class__ is other.__class__` first, so
`isinstance(build_zone(...), model.ZoneReport)` failed with the
confusing `<class 'model.ZoneReport'>` vs `<class
'lib_memory_model.ZoneReport'>` message.

Fix: load under the PLAIN name (`spec_from_file_location(module_name,
path)`, not prefixed) and `sys.modules[module_name] = mod` BEFORE
`exec_module()` (standard importlib pattern for circular/sibling
imports). This alone only fixes the case where the test asks for the
dependency (e.g. `model`) BEFORE the module that imports it plainly
(e.g. `zones`). The REVERSE order (ask for `zones` first, `model` never
requested directly until later) still produced two objects, because
Python's natural import already created `sys.modules['model']` by the
time our function got asked for `"model"` — and our function would
otherwise create ANOTHER fresh object and silently overwrite
`sys.modules['model']`, orphaning whatever `zones.py` had already bound.

Full fix, both directions: before creating a fresh load, check
`existing = sys.modules.get(module_name)`; if `existing.__file__`
resolves (`os.path.abspath`) to the SAME path we were about to load,
ADOPT it (store in `_MODULE_CACHE`, return it) instead of creating a
second object. Verified live in both orders via a real repro script
(load `zones` first vs `model` first) — see the toolkit-wide
`--collect-only` count (835, unchanged) and `tests/memory -q` (119
passed vs 118 before, the one flipped test being exactly the
`isinstance(result, model.ZoneReport)` assertion in `test_report.py`).

No name collision risk found: grepped `lib/` (v1, top-level, NOT
`lib/memory/`) for module-name overlap with any `lib/memory/*.py` stem
(`model`, `config`, `format`, `similar`, `notes`, `query`, `context`,
`rules`, `health`, `dispatch`, `clusters`, `validator`, `rejection`,
`indexes`, `ids`, `vocabulary`, `zones`, `emojis`, `utf8`, `gitcmd`,
`report`) — zero overlap. `test_indexes.py`'s own subprocess-based
mutation-check scripts (lines ~433-489) load modules via their OWN
inline `_load()` helper in a separate `subprocess.run` process, never
touching this conftest's `sys.modules`/`_MODULE_CACHE` — confirmed no
interaction.

**Bug 2 — real production bug found while diagnosing, NOT fixed (not
my file).** `unmassk-toolkit/lib/memory/notes.py:198`
(`root = _repo_root()`) never appends `.claude/project-memory` before
using `root` as the index-file root for `indexes.seed()`/`.read()`/
`.insert()` (lines 210, 211, 234) and for `index_path` (line 236).
Confirmed with a standalone repro script (natural imports, no pytest):
`notes.write()` returns `ok=True, note_id='M-001'` and the commit really
happens (`git show HEAD:MEMOS.md` has the line), but it all lands at
`<repo_root>/MEMOS.md`, not `<repo_root>/.claude/project-memory/MEMOS.md`
— confirmed by reading `pm_root/MEMOS.md` right after `insert()`, still
just the header. Cross-checked against the ONE explicit statement of
where the eight indices live: PIEZAS.md line ~1200, *"El fichero de
reglas es `.claude/project-memory/rules.md` del proyecto, junto a los
ocho índices y a `zones.json`/`config.json`"* — and `rules.py:138`
correctly does `root / ".claude" / "project-memory" / "rules.md"`,
proving the convention exists and `notes.py` just doesn't follow it.
This is why `test_report.py::test_history_only_appears_with_include_archived_true`
fails with `ValueError: 'M-001' no esta en MEMOS.md`: the test seeds
indices at the CORRECT `_pm_root(root)` and later calls
`indexes.remove(old_result.note_id, "MEMOS.md", pm_root)` against that
same correct location — `notes.write()` wrote the line somewhere else
entirely.

Not a test bug in `test_report.py` (it already follows the documented
path). Also observed (read-only, did not touch): `test_notes.py`
independently assumes `root = Path(tmp_repo)` directly (no pm subdir)
for both seeding and reading back — internally consistent with the
CURRENT buggy `notes.py`, so its own write-path tests don't trip this.
Whether `test_notes.py` needs to switch to `_pm_root()` too once
`notes.py` is fixed is for whoever owns that file / the fix, not
diagnosed further here.

**Pattern for next time:** when a `ValueError`/`FileNotFoundError` shows
up in a test that seeds one path and reads back a DIFFERENT one, don't
assume the test's path helper is wrong — grep the piece's own docs
(PIEZAS.md) for the ONE explicit sentence declaring the real location,
and diff it against a sibling piece (`rules.py`) that already implements
it correctly. A standalone repro script with real imports (no pytest,
no fixtures) that prints intermediate disk state after each production
call is faster than instrumenting the test itself, and never risks
touching production.

Reference: [import-lib-memory-module-cache-fix-and-stash-incident-notes](import-lib-memory-module-cache-fix-and-stash-incident-notes.md),
[memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md),
[notes-replace-close-contract-notes](notes-replace-close-contract-notes.md)
