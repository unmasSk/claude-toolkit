---
name: rejection-contract-notes
description: unmassk-memory (v2) lib/memory/rejection.py (RED, test-first) PIEZAS Sec.7.4 3-row contract -- ten-rejections enumeration (1.8 excluded), build()/**parts naming assumption, tuple-command design for the two-branch case, synthetic-marker property-test technique
metadata:
  type: project
---

Context: `unmassk-toolkit/tests/memory/test_rejection.py` (3 tests, RED
by design) -- one test per row of PIEZAS.md Sec.7.4 "Sus tests" table,
literally, no extra coverage (same test-first acceptance-granularity
override as [vocabulary-contract-notes](vocabulary-contract-notes.md)
and [zones-contract-notes](zones-contract-notes.md)).

**Which ten rejections, and why 1.8 is excluded:** TEXTOS.md Sec.1 has
sections 1.1-1.11, but 1.8 ("key marcadora mal escrita") titles itself
literally "no es rechazo, es aviso al guardar" -- confirmed independently
by PIEZAS.md Sec.7.5 ("la key mal escrita no es un rechazo... si se
quiere rechazo de verdad, la mecanica cambia"). Two independent sources
agree it's not a rejection. The ten are: 1.1 zone_not_found, 1.2
zone_blacklisted, 1.3 ambiguous_word, 1.4 no_type_fits, 1.5
missing_pain_answer, 1.6 overlaps_existing, 1.7
distillation_without_sources, 1.9 issue_not_found, 1.10
incident_close_needs_restriction_answer, 1.11 headline_too_long.

**Naming assumption, disclosed (PIEZAS Sec.7.4 only fixes the top-level
signature `build(kind: str, **parts) -> Rejection`, never the kwarg
names inside `**parts`):** assumed `what` (str), `options` (tuple of
str), `command` (**tuple** of str, not a bare str -- TEXTOS 1.10 shows
TWO valid relaunch commands depending on which branch the user answers,
"no" vs "new"; a length-1 tuple covers the other nine without a special
case). If Ultron's real implementation uses different kwarg names, row
1 fails loud with `TypeError: build() got an unexpected keyword
argument` naming the mismatch -- not a mute red. Same disclosure pattern
as `FieldSpec.reader` in vocabulary-contract-notes.md.

**Why the tests never assume `kind` is a fixed enum:** grepped
`docs/spec-sistema-memoria-v2.md` Sec.6 (the "nueve validaciones" that
PIEZAS Sec.7.5 cites as rejection.py's real source) -- it lists the nine
validations in prose, never as string constants/an enum. `kind` in the
test file is therefore just a free-form label I invented per case
(`"zone_not_found"` etc.), never asserted against anything Ultron
writes -- it's passed through opaquely and never inspected in an
assertion, so a different internal `kind` vocabulary in the real
implementation can't break these tests.

**Property-test technique (per the task's explicit instruction: "no
copies el texto esperado de TEXTOS.md y compares cadenas -- eso prueba
que sabes copiar"):** every one of the ten `what`/`options`/`command`
values is synthetic content with a unique `MARK_<KIND>_...` token,
never TEXTOS.md's literal wording. Tests assert the marked substrings
survive verbatim through `build()` + both renders -- proving the
render composes the three parts and doesn't mangle them, without ever
comparing against a hand-typed "expected" rejection string.

**Row 2 mechanics (comillas):** the ten `command` tuples use realistic
shell syntax with single quotes, double quotes, and one escaped
double-quote (`\\"`) inside a double-quoted arg (the issue_not_found
case) -- validated with `shlex.split()` on each string *before* writing
the test file (11 commands, 0 `ValueError`; also re-asserted live
inside the test itself as a fixture sanity check, separate from the
production-facing assertion that the command survives byte-for-byte in
both renders).

**Mutation-check used before reporting done:** wrote a throwaway fake
`lib/memory/rejection.py` (dataclass + naive `build`/`render_terminal`/
`render_hook_block` implementing exactly the assumed kwarg names) in
the same bash block that deleted it right after -- confirmed all 3 pass
against the fake (assertions satisfiable, not vacuous), then confirmed
`ls lib/memory/` no longer lists `rejection.py` and the suite reverted
to 3 RED (`FileNotFoundError` at fixture setup) afterward.

**Parallel-work note:** at the time of this task, `tests/memory/` had
several other in-flight contract files from parallel agents
(test_config.py, test_format.py, test_gitcmd.py, test_ids.py,
test_indexes.py, test_similar.py, test_zones.py, plus
`lib/memory/indexes.py`) -- none touched, `conftest.py` not touched,
confirmed via `git status` showing only `test_rejection.py` as this
session's addition.

Verification command used (matches the task's exact ask):
`python3 -m pytest unmassk-toolkit/tests/memory/test_rejection.py -v`
-> 3 errors, all `FileNotFoundError` at `rejection()` fixture setup
(lib/memory/rejection.py does not exist yet) -- RED for the right
reason.

Reference: [vocabulary-contract-notes](vocabulary-contract-notes.md), [zones-contract-notes](zones-contract-notes.md)
