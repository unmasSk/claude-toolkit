---
name: query-contract-notes
description: unmassk-memory (v2) Capa 3 -- lib/memory/query.py (RED, test-first) contract from PIEZAS.md Sec.8.2, 4 rows; seeded via real format.py+gitcmd.py (notes.py doesn't exist yet), transient-git-failure retry simulated at the subprocess.run boundary targeting the first "git log" call only
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_query.py` (4 tests, RED by
design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.8.2, literally, no extra coverage added
(same test-first acceptance-granularity override as
[format-py-full-contract-notes](format-py-full-contract-notes.md)
and [zones-py-full-contract-notes](zones-py-full-contract-notes.md)). query.py is "el
unico lector del historial" -- the v1 had THREE separate 562-line
implementations of this, synced by hand, already failed three times the
same way.

**Seeding without `notes.py`:** `lib/memory/notes.py` (Sec.8.1, the
validate->index->commit transaction) doesn't exist yet either -- a
parallel colleague owns its contract. Seeding with it would invent that
logic ahead of its own test-first pass (restriccion D). Instead, each
test commits for real against `tmp_repo` using only pieces already real
and green: `format.build_message(note)` for the commit text +
`gitcmd.commit(message, paths=[...], allow_empty=False)` to write it,
plus a plain `git add` via `subprocess.run` (gitcmd.py has no `add()`).
Real memory, real git commits, written with the same building blocks
production will use -- just without the orchestrating transaction piece.

**Four declared-but-unsourced assumptions (disclosed in the test file's
module docstring, same practice as every other Capa-1+ contract file in
this project):**
1. **No `root`/`cwd` param on any of the four functions** (`by_id(note_id)
   -> Note | None`, etc.) -- assumed to read against process cwd, same
   convention as `gitcmd.commit()` ("hereda el cwd ambiental del
   proceso"). Every test does `monkeypatch.chdir(tmp_repo)` before
   calling `query.*`.
2. **Row 3 (transient retry) is simulated at the `subprocess.run`
   boundary**, never inside `gitcmd.run()` -- Sec.7.1 explicitly says
   `gitcmd.run()` has NO retry of its own ("un returncode != 0 es un
   resultado normal"). The retry is `query.py`'s own responsibility, so
   the only way to test it without guessing the internal call graph is
   to fake the failure at the real subprocess boundary any internal path
   would eventually hit.
3. **The simulated failure targets ONLY the first `git log` invocation**
   (checks `"log" in cmd`), not the first `subprocess.run` call overall
   -- guards against query.py possibly issuing an unretried prep call
   (e.g. `gitcmd.repo_root()`, which raises `RuntimeError` on failure
   with zero retry) before the actual history read. `"log"` was chosen
   because Sec.8.2 says literally that `by_file` reads via `git log --
   <ruta>` "directamente" -- the most likely shared subcommand across
   all four functions. Flagged explicitly as a guessable implementation
   detail: if Ultron's real query.py uses a different subcommand, this
   is a one-line fix, not a redesign.
4. **`Note.timestamp` excluded from all comparisons** -- same reasoning
   as `test_format.py`: its source of truth is git's author date, not a
   value this test can pre-seed and expect back byte-for-byte.

**`_assert_fields_match` (field-by-field, never `==`)** -- same
class-identity trap as every other Capa 1+ contract file in this branch
(`test_zones.py`, `test_format.py`, `test_similar.py`): the `model`
fixture loaded via `import_lib_memory_module("model")` and whatever
`model` query.py imports internally (`from model import Note`, flat
import per PIEZAS Sec.3.3bis) can end up as two distinct Python classes
despite identical source.

**Row 1 design (all four query paths in one test, matching the
contract's own single-row wording "por identificador, por zona, por
palabra y por fichero"):** three seeded notes -- A (`testing/query-alpha`),
B (`testing/query-beta`, same zone1 as A, different zone2), C
(`another/place`, different zone1 entirely) -- each committed touching
its own marker file (`markers/note_a.txt` etc.) so `by_file` has
something concrete to filter on. A unique needle word
(`zzqueryalphaneedle`) lives only in A's `why` field, letting `by_word`
exclusivity be asserted without ambiguity about tokenization rules the
contract doesn't specify.

**Row 4 design:** two notes, needle word (`zzwordneedle`) only in one
note's `why` field. Asserts three things `by_word` must return together:
the matching note IS present, the non-matching note is NOT present, and
the matched-lines tuple for the matching note is non-empty AND contains
the needle verbatim -- the exact failure the row exists to prevent ("el
informe no puede marcar cual fue y hay que ir a buscarla por otra
puerta").

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory -q` -> 57 passed (baseline
untouched), 4 errors (mine), all `FileNotFoundError:
lib/memory/query.py` -- RED for the right reason, one per row.
`--collect-only` -> 61 tests collected, zero collection errors. Only
file touched/added this task: `test_query.py` (new) -- confirmed via
`git status --porcelain`, no other teammate's file modified.

Reference: [format-py-full-contract-notes](format-py-full-contract-notes.md), [zones-py-full-contract-notes](zones-py-full-contract-notes.md), [similar-contract-notes](similar-contract-notes.md), [gitcmd-contract-notes](gitcmd-contract-notes.md)
