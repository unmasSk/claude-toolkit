---
name: context-py-contract-notes
description: lib/memory/context.py Sec.9.6 RED contract (3-row table) -- gitcmd.commit() empty-paths tension, HEADLINE_MAX cross-check technique for "aduana exenta" claims
metadata:
  type: project
---

Wrote `unmassk-toolkit/tests/memory/test_context.py`, test-first contract
pass for `lib/memory/context.py` (PIEZAS.md Sec.9.6, `write(ctx: ContextNote)
-> WriteResult` / `latest() -> ContextNote | None`). 3 tests, one per row of
"Sus tests", confirmed RED for the right reason (FileNotFoundError at the
`context` fixture, module doesn't exist yet). See [[query-contract-notes]]
for the sibling pattern this reused almost verbatim (module-fixture-first
ordering, `_assert_fields_match` field-by-field comparator, timestamp
exclusion).

**Undeclared-internals gap, flagged as an open question, not invented:**
Sec.9.6 says context commits have "sin indice y sin lapida" (no index
file, no archive line touched), but `gitcmd.commit()` (Sec.7.1, already
green) raises `ValueError` on an empty `paths` sequence -- it's not
written anywhere HOW `write()` reconciles that (a bare `gitcmd.run(["commit",
"--allow-empty", ...])` bypassing the `commit()` wrapper, or some file
that isn't an index/archive). Resolution: tests never assert on what path
gets touched internally -- only call the declared surface (`write`,
`latest`) and check round-trip behavior against a real tmp_repo. Keeps the
contract honest without guessing Ultron's implementation.

**Technique for proving "aduana exenta" claims (Sec.9.6 row 3) without a
strawman:** `ContextNote` has no `zones`/`type` fields, so none of
`validator.py`'s zone/type checks apply directly. Used
`vocabulary.HEADLINE_MAX` (real constant, imported not hardcoded) to build
a headline one char over the cap, then called `validator.validate_headline()`
directly (real check, real module) to CONFIRM it rejects that exact string
for an ordinary Note -- only then asserted `context.write()` accepts the
same string with `rejections == ()`. Proves the customs bypass against a
genuine trigger, not an assumption that the trigger works. Generalizes:
whenever a contract row claims "X is exempt from check Y", cross-verify Y's
real trigger condition first, in the same test, before asserting the
exemption.
