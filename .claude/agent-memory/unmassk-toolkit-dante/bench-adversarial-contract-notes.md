---
name: bench-adversarial-contract-notes
description: RED contract for the adversarial bench (PIEZAS.md Sec.14, ten attacks) in lib/memory/bench.py, plus wiring into HealthReport/boot AVISOS -- module location decision, disclosed signature assumptions, field-name decisions
metadata:
  type: project
---

Test-first CONTRACT pass (before Ultron), `unmassk-toolkit/tests/memory/test_bench.py`,
13 tests, all RED via `FileNotFoundError: lib/memory/bench.py` (module does not
exist yet) -- baseline untouched: 214 passed / 3 pre-existing red (the already-written
`test_bench_script.py`, not touched).

## Decisions made without the owner (documented per branch rule: "anota lo que
decidas y sigue")

**Module location**: `lib/memory/bench.py` (new, 24th module -- ARQUITECTURA.md
Sec.2's list of 23 doesn't include it). Mirrors the `bin/memory/<x>.py` +
`lib/memory/<x>.py` same-name pattern already used by `zones.py`/`context.py`/
`boot.py`. Imports `validator` (to run the ten attacks against it); imported BY
`health.py` (for the boot wiring below). Never touches `notes`/`gitcmd` -- the
bench writes nothing, per Sec.14's literal invariant ("en proceso, contra el
validador puro, sin escribir un solo commit").

**bench.py surface assumed (disclosed in the test file's own docstring,
"ASUNCIONES DE FIRMA, DISCLOSED" -- same pattern [[validator-contract-notes]]
already uses)**:
- `run() -> tuple[AttackResult, ...]`, zero args, ten items in Sec.14's order.
- `AttackResult`: `number`, `caught_by` (bare validator.py function name, e.g.
  `"validate_replacement"`), `inputs` (dict, exact kwargs to replay
  `getattr(validator, caught_by)(**inputs)` independently), `rejection`,
  `ok`, and `normalized_keys` (attack 6 only).
- Every attack test reconstructs the ground truth by calling the REAL
  validator function directly with `result.inputs`, and compares structural
  equality against `result.rejection` -- never trusts bench's self-report
  alone (Dante's own rule: "comprueba que el ataque es cazado por la funcion
  que dice la ficha, no solo que algo lo rechaza").

**Attack 2 is the one that invents the most, said out loud**: PIEZAS.md
Sec.14 names `validate_pointers` as the catcher for "a restriction (R) born
without saying which incident it came from", with the rejection listing
"ALL candidate incidents of the zone" -- but validate_pointers' real,
already-shipped signature is `(note, known_ids)`, and `known_ids` is a bare
`frozenset[str]` with no descriptive content, so it structurally CANNOT list
incidents with id+date+headline. Assumed a third parameter,
`existing_in_zone: tuple[Note, ...]` (same name `validate_replacement`
already uses, same data `Context` already carries). If Ultron solves this
differently, only that one test fails loud (TypeError naming the mismatch) --
by design, not a defect.

**Wiring into the boot line** (Sec.14: "su veredicto sale en la misma linea
del arranque... no en un registro aparte", plus the explicit precedent named
in the task: [[boot-py-v2-full-contract-notes]] -- `coherence_rules()`
was written, green, and mute for a while until HealthReport/boot.py were
extended). Same shape applied here, field names decided in this session (not
sourced from any doc, mirroring `rule_commits`/`rule_lines`/
`rule_discrepancies`):
- `HealthReport.bench_caught: int`
- `HealthReport.bench_total: int`
- `HealthReport.bench_failures: tuple[str, ...]` (which attack failed, not
  just how many -- same "que regla diverge, no solo cuantas" principle).
- `boot.py` AVISOS block paints a line mentioning "banco" with the real
  caught/total numbers, symbol ✓/⚠, next to the existing "IDs sin
  duplicados"/"indices coherentes con git" lines. Literal wording is NOT
  fixed (TEXTOS.md Sec.3.1 doesn't have this row yet) -- tests check
  substrings/numbers, never a hand-typed full line, same criterion the rule
  wiring precedent already established.

## Restricted files respected

`lib/memory/{boot,vocabulary,notes,zones,rules}.py` have other agents working
in them this same session -- none edited (never intended to; Dante never
writes production). Their PAIRED test files (`test_boot.py`, `test_health.py`,
etc.) were also deliberately NOT touched, to avoid a second agent landing on
the same file mid-session (an incident already logged once on this branch) --
the boot/health wiring is instead verified entirely from the new
`test_bench.py`, importing `boot`/`health`/`indexes`/`notes`/`rules` read-only
(same technique `test_bench_script.py` already uses against the scripts it
tests).

## Coverage declared (acceptance-granularity pass, EXHAUSTION PROTOCOL does
NOT apply -- see Dante's own Build Mode rules for test-first contract passes)

10 tests (one per PIEZAS.md Sec.14 row) + 1 structural (`run()` returns the
ten, in order) + 1 HealthReport wiring + 1 boot AVISOS wiring = 13, "una fila
= un test, ni una mas" (branch convention). Explicitly excluded, per Sec.14's
own "Que NO cubre" paragraph: malicious-attacker scenarios (no threat model
here), the four validations with separate contracts (type mismatch, issue
existence, incident closure, wip exemption -- all already covered elsewhere),
the three live hooks bench (Sec.11, different piece), and whether the
generator/customs assemble the validator's inputs correctly (only that the
validator rejects when given data describing one of the ten cases).

Related: [[boot-py-v2-full-contract-notes]], [[validator-contract-notes]],
[[capa5-read-scripts-and-facade-contract-notes]].
