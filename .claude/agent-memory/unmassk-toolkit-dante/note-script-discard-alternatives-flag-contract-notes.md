---
name: note-script-discard-alternatives-flag-contract
description: note.py --discard flag RED contract wiring notes.discard_alternatives(); description-vs-why field decision for X-type alternatives
metadata:
  type: project
---

Task (2026-08-04): `lib/memory/notes.py::discard_alternatives(decision, alternatives, ctx)`
was written and unit-tested but never called from `bin/memory/note.py` — same
orphan-wiring pattern `notes.replace()` had earlier in this branch
([[note-script-replaces-not-archiving-regression-notes]]). Owner decision: wire it.

**Flag form decided (Dante's design call, delegated explicitly by the owner):**
`--discard <headline> <why>`, repeatable (`argparse action="append", nargs=2`), same
tier as `--origin`/`--keys`/`--replaces`. Example:

```
note.py D --zones product auth "login with JWT + Google OAuth" \
    --why "sessions do not scale multi-tenant; Google avoids owning passwords" \
    --description "Brainstorm on login options..." \
    --discard "server-side sessions" "sticky routing complicates horizontal scaling" \
    --discard "own password login" "maintaining passwords costs us one incident a year"
```

**Critical gotcha, verified against `vocabulary.py` before writing tests:** the second
value of each `--discard` pair MUST map to `Note.description`, never `Note.why`.
`TYPES["X"].required_fields == frozenset({"description"})` — `why` is optional for X.
If the CLI put the reason into `why` instead, every alternative would be born missing
its one required field and `validator.validate_fields` would reject it every time —
the flag could never save anything. This only surfaces by reading `vocabulary.py`
directly; nothing in `TEXTOS.md` or `PIEZAS.md` states it, and the owner's own boot-output
example (`🚫 X-003 ... └─ mantener contraseñas nos cuesta un incidente al año`) reads like
a "why" semantically but has to land in `description` mechanically.

**Origin is NOT a CLI concern:** `discard_alternatives()` prepends the decision's real id
to each alternative's `origin` internally (`notes.py:292-293`, `dataclasses.replace(alternative,
origin=(decision_result.note_id,) + alternative.origin)`). `note.py` must never pass the
decision id itself via any origin flag for the alternatives — that would duplicate the pointer.
`--discard` intentionally has no third value for origin.

**No literal output molde exists.** Grepped `TEXTOS.md` for `note.py`/`discard` — zero hits.
Tests assert behavior only (exit code, real commit count, real index lines, `Note.origin`/
`Note.description` read back via `query.by_id`, and `clusters.group()` producing the correct
parent/children structure) — never invented screen text.

**Test technique — real producer↔consumer round trip (unmassk-standards §34):** after running
`note.py` as a subprocess, `monkeypatch.chdir(tmp_repo)` then call `query.by_zone()` +
`clusters.group()` **directly in-process** (not via another script) to verify the `Origin`
trailer round-tripped through a real git commit and that clustering (which only groups by
pointers, never similarity) links the alternatives to the decision for real. Same
`monkeypatch.chdir` pattern as `test_query.py` (see [[query-contract-notes]]).

File: `unmassk-toolkit/tests/memory/test_note_script.py` — added 2 tests (1 RED behavioral
contract, 1 GREEN control proving `--discard`'s absence doesn't change plain-decision
behavior). All 12 pre-existing tests stayed green. Unrelated to this task:
`test_boundary.py::test_every_public_symbol_has_a_real_importer` was already RED before this
session's edits (pre-existing orphan-symbol finding, not touched, not caused by this change).
