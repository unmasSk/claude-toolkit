---
name: vocabulary-contract-notes
description: unmassk-memory (v2) Capa 1 -- lib/memory/vocabulary.py (RED, no existe) contract tests from PIEZAS.md Sec.6.1, 4 rows; FieldSpec/TypeSpec attribute-naming assumption + live mutation-check technique
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_vocabulary.py` (4 tests, RED
by design) -- one test per row of the "Sus tests" table in
`docs/memoria-v2/PIEZAS.md` Sec.6.1, literally, no extra coverage added
(same explicit override of the EXHAUSTION PROTOCOL as
[memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md)
-- test-first acceptance-granularity pass, contract table rows only).

**Naming assumption, disclosed because PIEZAS.md doesn't fix it
literally:** `FieldSpec` exposes `.reader` (a `"modulo.funcion"` string,
module relative to `lib/memory/`); `TypeSpec` exposes
`.required_fields` and `.allowed_fields` (collections of field names).
Unlike `FIELDS`/`TYPES`/`PAIN_QUESTION`/`INDEX_FILES` (cited literally in
PIEZAS §6.1 "Superficie"), these two nested dataclasses are only
described in prose ("descripcion, campos obligatorios, campos
permitidos" / "su LECTOR declarado, ruta de la funcion que lo lee"). If
Ultron picks different attribute names, row 1 and row 3 fail with a
readable `AttributeError` naming the missing attribute -- not a mute
red. Flag this to whoever reviews the GREEN pass.

**Row 1 (the most important one) mechanics:** walks `vocabulary.FIELDS`,
splits each declared `reader` on the last `.` into
`(module_name, function_name)`, loads `module_name` via
`import_lib_memory_module` (never `import memory.X` -- see
[memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)),
and asserts the function is actually callable there. This is the
mechanical form of PIEZAS's "el modulo falla al importarse si un campo
no tiene lector" -- distinct from (and narrower than) the cross-cutting
`tests/test_p2_sin_zombis.py` from `PLAN-CONSTRUCCION.md` paso 1.10,
which is FASE 1 scope, not this task's.

**Row 2 (pain question) scope decision:** scans only `.py` files under
the toolkit root (`_TOOLKIT_ROOT`, derived from `conftest.LIB_MEMORY_DIR`
-- never a private conftest name), not `docs/`. Verified live before
writing: the literal pain-question text already appears 3x in
`docs/memoria-v2/{PIEZAS,TEXTOS}.md` + `docs/spec-sistema-memoria-v2.md`
(legitimate doc citations) and 0x in `unmassk-toolkit/` (code) today --
confirms "en todo el codigo" means code, not docs, and that scoping the
grep to `.py` files avoids a false-positive fail once vocabulary.py
exists with its own docstring citing the question.

**Row 3 grounded assertions (not arbitrary):** `"description" in
required_fields` for all seven types comes from `model.py`'s own
comment in PIEZAS §5.3 ("`description: str # obligatorio en los siete
tipos`"). `"why" in TYPES["D"].required_fields` (and NOT in the other
six) comes from `spec-sistema-memoria-v2.md` §4's table row for D ("con
su Why obligatorio") -- the only type where the spec uses that word.
Did NOT assert `"awaits"` is required for B: the spec only says B
"Lleva campo `espera:`" (has the field), never says obligatorio --
asserting required would be inventing a rule not in the source.

**Row 4:** the eight file names come from `spec-sistema-memoria-v2.md`
§7 (`DECISIONS.md MEMOS.md RESTRICTIONS.md QUESTIONS.md INCIDENTS.md
DISCARDED.md BLOCKED.md ARCHIVED.md`), plus explicit negative checks for
`PLANS.md` and `MEMORY.md` (same doc: "Indice general MEMORY.md /
indice de planes PLANS.md -> rechazados").

**Verification technique used before reporting done (not just "red for
the right reason"):** wrote a throwaway fake `lib/memory/vocabulary.py`
(dataclasses + plausible field/type data, reader pointed at the real
`utf8.force_utf8_streams`) in the same bash command that deleted it
immediately after, to prove all 4 assertions are satisfiable and not
vacuous -- confirmed 4 passed, then confirmed the suite reverted to RED
after cleanup (`ls lib/memory/` showed only `emojis.py`/`utf8.py`
again). This is the mutation-check pattern from prior sessions, applied
to a not-yet-existing module instead of a real code change.

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory -v` -> 8 passed
(pre-existing: 2 smoke + 3 utf8 + 3 emojis), 4 errors (vocabulary, RED
by design, `FileNotFoundError` at fixture setup, one per row).

**UPDATE 2026-08-02, same session: row 1 rewritten under a coordinator
correction, not my own bug.** My first version required all 8 declared
readers to be importable -- correct against the doc *as it stood when I
wrote it*, but the coordinator caught that PIEZAS.md §6.1 itself had a
gap: 6 of 8 readers live in upper-layer modules (`report_render`,
`query`, `clusters`, `boot`, `health`, `context`) that legitimately
don't exist yet during test-first construction, so the test would stay
red for weeks -- "un test permanentemente rojo se ignora, y detras se
esconde un fallo real". Fix landed in the doc first (three-state rule:
verificado/pendiente/roto, PIEZAS §6.1 lines ~461-473) with `FieldSpec`/
`TypeSpec` attribute names now fixed literally in the doc (no longer an
assumption on my side). Rewrote only the row-1 test to match:

- **pendiente vs roto decided by `os.path.exists()` on the module file
  BEFORE attempting import** -- explicitly not a generic try/except,
  because that would blur "module doesn't exist" (fine) with "module
  exists but lacks the function" (must stay red forever, it's the exact
  v1 failure mode: a declared-but-unread field).
- **Prints the pending count unconditionally** (`print(...)`, needs
  `pytest -s` to see it) -- "el cero se ensena, no se calla" (P6), and
  the coordinator asked for literal visible output, not just a passing
  assert.
- Verified all three states live against the REAL `lib/memory/vocabulary.py`
  (Ultron had already built it in parallel while this correction landed
  -- not a fake double this time): created a throwaway
  `lib/memory/report_render.py` with `def render(): pass` -> 2 fields
  flipped pending->verificado (2/6/0), test PASSED. Renamed the function
  inside the same file (module still exists, target function doesn't)
  -> same 2 fields flipped to roto (0/6/2), test FAILED with the exact
  field:reader pair named in the assertion message. Deleted the file +
  `__pycache__` -> back to real baseline (0 verificado / 8 pendiente / 0
  roto), 4/4 passed. This is the pattern for verifying a 3-state
  classifier without ever leaving a fake module behind: flip one real
  file through all three states in sequence, in the same bash block
  that deletes it.
- Tests 2-4 untouched (coordinator confirmed they were correct); they
  now pass for real against the real `vocabulary.py`, not the earlier
  disposable fake.

**General lesson:** when a contract doc itself has a gap that only
surfaces once a test tries to enforce it literally, the fix belongs in
the doc (coordinator/architect layer), not in loosening the test
quietly -- confirmed here: PIEZAS.md was corrected first, my test
followed the corrected doc, never the other way around.

Reference: [memoria-v2-fase0-emojis-utf8-contract-notes](memoria-v2-fase0-emojis-utf8-contract-notes.md), [memoria-v2-conftest-package-collision-notes](memoria-v2-conftest-package-collision-notes.md)
