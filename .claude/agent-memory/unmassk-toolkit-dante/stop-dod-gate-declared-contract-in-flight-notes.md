---
name: stop-dod-gate-declared-contract-in-flight-notes
description: 2026-08-22 test-first RED contract for stop-dod-gate.py -- declared test-first contract (RED-on-purpose during Ultron's implementation) must not block Stop like a real failure; declared/cleared/queried via a new bin/stop-dod-declare.py, per-session
metadata:
  type: project
---

Task (owner-reported, urgent, parallel to Ultron editing `hooks/stop-dod-gate.py`
live -- forbidden from opening that file, worked from the prose spec only):
the toolkit's own test-first method (Dante writes the RED contract, Ultron
implements to GREEN) collides with `stop-dod-gate.py` itself -- a
deliberate RED (module exists, test collects, exit 1) reads as a real
average and blocks every Stop for the whole implementation window.

Owner's fixed solution (declared, never inferred): the orchestrator, who
knows a contract is in flight, declares it explicitly. Six numbered
requirements, all written as separate test classes in
`unmassk-toolkit/tests/test_stop_dod_gate.py`, new "Caso 17" section
(before `TestImportSanity`):

1. `TestDeclaredContractSkipsBlock` (2 tests) -- a failure INSIDE an
   active declaration does not block; a visible one-line notice (keyword
   `contrato`/`declar`/`contract`, case-insensitive, checked across
   stdout+stderr combined -- deliberately not pinned to one channel)
   must appear, never silent.
2. `TestUndeclaredFailureStillBlocks` (1 test) -- a declaration in force
   for a DIFFERENT test does not shield an undeclared failure; this is
   the test that stops the mechanism becoming a kill switch for the
   whole gate.
3. `TestMixedDeclaredAndUndeclaredBlocksNamingUndeclared` (1 test) --
   one declared + one undeclared failing together → blocks, reason
   names the undeclared one specifically.
4. `TestDeclarationAutoClearsWhenGreen` (1 test) -- full round trip:
   declare (red) → allow with notice → `status` shows it declared →
   flip the SAME file/test name to green → allow (normal) → `status`
   shows it gone. Nobody has to retire the declaration by hand.
5. `TestNoDeclarationBehavesAsBefore` (1 test) -- anchor, never calls
   `declare` at all. **Already GREEN today** (58/69 passed baseline
   unaffected) -- pins that the mere existence of the new mechanism
   doesn't loosen the normal case, same "invariant, not new RED" pattern
   as 2 of [[stop-dod-gate-fingerprint-cache-contract-notes]]'s 4 tests.
6. `TestDeclarationScopedToSession` (2 tests) -- a declaration made
   under session A does NOT apply to a Stop event carrying session B;
   and (contrast test) a declaration DOES survive multiple Stops within
   the SAME session (not a one-shot notice).

**The executable path, fixed by Dante since the task explicitly said "no
inventes el nombre del comando, fija el comportamiento observable":** a
new script `unmassk-toolkit/bin/stop-dod-declare.py` (does not exist yet
-- RED), CLI:

```
python3 bin/stop-dod-declare.py declare <test_node_id> [...] --session <ID>
python3 bin/stop-dod-declare.py clear --session <ID>
python3 bin/stop-dod-declare.py status --session <ID>
```

`status` prints JSON to stdout with at least `{"declared": [...]}` (a
list of pytest node ids `<file>::<function>`, exact strings as they
appear in a real `FAILED` line -- the hook already needs to extract
those for the anti-drip signature, Caso 10-12, so matching reuses that
extraction, not a new one). All three subcommands exit 0 on success and
operate on the process cwd (same convention as every other `bin/*.py`
script in this suite -- no `--repo`/`--cwd` flag). New class
`TestDeclareClearStatusCommandRoundTrip` (4 tests) tests this command
directly: declare→status shows it, clear→status empty, status on a
never-declared session is empty, and (requirement 6's "same file"
clause) `declare` writes into the EXISTING
`.claude/.unmassk/stop-dod-gate-state.json` -- confirmed by reading that
exact file after declaring and asserting the node id string is inside
it, without pinning the internal JSON key name (that's Ultron's choice).

**Deliberate non-git workdirs throughout** (same technique as
[[stop-dod-gate-fingerprint-cache-contract-notes]]'s Caso 16): isolates
this contract from the working-tree fingerprint cache Ultron is adding
in parallel -- a non-git workdir is guaranteed to always re-run
`test_command` for real, so none of these 12 new tests can accidentally
pass or fail because of caching instead of the declaration logic itself.

**Result, run in isolation from `hooks/stop-dod-gate.py` (never opened,
per the task's own lane restriction):** 11 of 12 new tests RED for the
exact expected reason (`bin/stop-dod-declare.py`: No such file or
directory, rc=2) -- confirmed by reading each failure's own stderr, not
assumed. 1 green (the requirement-5 anchor). Whole-file baseline: 58
passed / 11 failed, no interference detected from Ultron's concurrent
edits to the hook itself as of this run.

See also [[stop-dod-gate-fingerprint-cache-contract-notes]] and
[[stop-dod-gate-d042-declared-identity-coverage-notes]] for prior
same-file test-first sessions -- same real-subprocess, no-mock
discipline, same "local helpers next to the test class that needs them"
placement convention (not the shared Helpers section at the top).
