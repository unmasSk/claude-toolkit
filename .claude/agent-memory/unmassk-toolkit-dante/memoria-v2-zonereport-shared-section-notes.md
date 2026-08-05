---
name: memoria-v2-zonereport-shared-section-notes
description: lib/memory/report.py Sec.9.2 RED contract when a PIEZAS.md section is shared by two pieces (report.py + report_render.py) built in fila; seeding via a real sibling transaction (notes.write) instead of format+gitcmd by hand; simulating a missing replace()/close() by hand with already-green primitives
metadata:
  type: project
---

Task: write the RED contract for `unmassk-toolkit/lib/memory/report.py`
(`build_zone`, `build_word`) — memoria-v2, tanda 4b, in fila before
`report_render.py`. PIEZAS.md Sec.9.2 shares its "Sus tests" table (5
rows) with Sec.9.3 (report_render.py), and the task explicitly scoped
me to only `report.py`'s slice ("el que decide qué se enseña y en qué
orden — no el que lo convierte en texto").

**Splitting a shared "Sus tests" table across two build-mode passes.**
When a PIEZAS.md ficha covers two pieces built sequentially (`en fila`),
map each row to whichever piece actually *decides* it, not whichever
piece the row's prose superficially describes. Row 1 here ("el orden se
cumple: restricciones primero... preguntas al final") reads like the
build piece's concern but isn't: the report data class's category order
is a **dataclass field order**, already fixed and green in `model.py`.
The piece that *iterates* those fields to produce ordered text is the
render piece. Testing "order" against the build function's return value
would just re-test `model.py` under a new file name. Result: 4/5 rows
written now, row 1 explicitly deferred in the docstring to the future
render-piece Dante pass — not silently dropped, not force-fit.
**Why:** "una fila = un test, ni uno más" is a strong directive; the
right response to a row that doesn't fit the piece in front of you is
to say so in the docstring and move on (per the task's own escape
hatch), never to invent a tautological test just to hit the count.
**How to apply:** whenever a ficha is shared across two build-in-fila
pieces, check literally which piece owns the *decision* behind each row
before assuming the row is yours.

**Seed via the real transaction sibling, not format+gitcmd by hand.**
Older sibling contracts (query.py, clusters.py) predate `notes.py` and
hand-roll seeding with `format.build_message` + `gitcmd.commit`. By the
time this contract was written, `notes.py` (validate -> index -> commit,
one commit or none) already existed and was green. Seeding through
`notes.write(note, ctx)` is strictly more real (the actual production
write seam, ids assigned for real, index line inserted for real) and
cuts a layer of duplicated commit logic out of the test. **Why:** §34 /
"real by default" — once a real producer exists, hand-assembling its
output is a regression in realism, not a neutral choice. **How to
apply:** before copying an older sibling's seeding pattern, check
whether a newer, more complete transaction piece has landed in the
meantime and prefer it.

**Simulating a missing `replace()`/`close()` with already-green
primitives, without inventing their contract.** The note-transaction
module's `replace()`/`close()` were declared in the piece's surface but
deliberately left `NotImplementedError` by a prior task ("esas seis
[filas], ni una más" — scope discipline). To get an *archived* note
into a test's fixed state (needed for `include_archived` tests), do the
two real steps by hand: `indexes.remove(old_id, index_name, root)` then
`indexes.archive(ArchiveLine(...), root)` — both already-green sibling
pieces, used exactly as documented, never reimplemented. This is not
"filling the gap that `replace()` will one day close": it's composing
existing primitives for a fixture, and is honestly documented as such
in the test docstring so nobody mistakes it for asserting on
`replace()`'s future contract.

**Axis ambiguity sidestepped by construction, not by guessing.** A
build function taking a bare `zone: str` didn't say whether it binds to
a note's first or second zone axis (the system tags every note with two
zones, e.g. `[testing][auth]`). Rather than guess and risk a false-red/
false-green against the real implementation choice, every seeded note
in this contract used `zone1 == zone2 == <same value>` — the assertion
holds under either axis interpretation. Documented as an explicit open
question for whoever implements, not resolved by assumption. Same
technique is reusable any time a contract's string param could plausibly
bind to either of two symmetric fields and no doc pins which.

Related: [[query-contract-notes]] pattern of declared assumptions in a
module docstring when Sec text has a real gap; [[clusters-contract-notes]]
"don't assert on unwritten contract" (supuesto 3, not asserting how
`Cluster.archived_ids` marks children — same restraint applied here to
how a flat tuple would mark archived membership).
