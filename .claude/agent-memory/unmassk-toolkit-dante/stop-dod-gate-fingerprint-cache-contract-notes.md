---
name: stop-dod-gate-fingerprint-cache-contract-notes
description: 2026-08-22 test-first RED contract for stop-dod-gate.py -- working-tree fingerprint cache (skip re-running test_command when nothing changed) + anti-drip signature must survive volatile content (memory addresses). Counter-file-outside-workdir technique.
metadata:
  type: project
---

Task (real consumer-project report, with proof): `stop-dod-gate.py` runs
`test_command` on EVERY Stop event. With a red suite that's dozens of runs
in a row -- one real project's `test_command` launched real audio and
**704 orphaned processes accumulated until the machine could no longer
`fork`**. Separately, the existing anti-drip dedup (sha256 of
FAILED/ERROR/E-prefixed lines) never fired because `E   ` lines can carry
volatile content -- a generator object's memory address
(`0x...`) that differs on every real run even for the exact same failure.

Wrote 5 new RED tests in `unmassk-toolkit/tests/test_stop_dod_gate.py`
("Caso 15" / "Caso 16", end of file, before `TestImportSanity`), test-first
mode, tests-only:

**Caso 15 -- `TestFingerprintSkipsRerunWhenTreeUnchanged`** (4 tests): a
working-tree fingerprint, stored alongside the existing
`.claude/.unmassk/stop-dod-gate-state.json`, must make a SECOND Stop with
an unchanged tree reuse the previous decision WITHOUT re-running
`test_command` -- proven with a real subprocess that appends one line to
a counter file per REAL execution (not per Stop). Covers: red-suite
unchanged (1 real run, both Stops still block), green-suite unchanged (1
real run, both Stops still allow -- this is the actual savings case),
tree change between the two Stops forces a second real run (deliberately
UNCOMMITTED -- "árbol de trabajo", not HEAD), and no-git-repo (fingerprint
uncomputable) always runs, never skips on doubt. 2 of the 4 already pass
today (change-forces-rerun, non-git-always-runs) because the CURRENT hook
already always reruns unconditionally -- that's expected, they pin
invariants the new caching layer must not break, not new RED lines. The
other 2 (red/green "runs once") are genuinely RED today: counter shows 2
runs, not 1.

**Key technique, load-bearing for the whole contract**: the counter file
lives OUTSIDE the workdir (`tmp_path / "counters_*"`, a sibling directory)
via `_write_counting_command(workdir, counter_dir, exit_code)`. If it
lived inside the workdir being fingerprinted, `test_command`'s own
execution would dirty the very tree the test claims is "unchanged"
between the two Stops, self-invalidating the RED contract regardless of
whether Ultron implements caching correctly.

**Caso 16 -- `TestBlockSignatureSurvivesVolatileMemoryAddress`** (1 test):
`_write_address_varying_failing_command()` writes a real Python
`test_command` that prints a line with the EXACT shape reported broken
(`E    +  where False = any(<generator object test_x at {hex(id(object()))}>)`)
and exits 1 -- the address varies naturally across the two invocations
because each is a fresh child process (no manual randomization needed).
Genuinely RED today: reason2 contains the fresh address and a newline
dump instead of the deduped one-liner.

**Deliberately non-git workdir for Caso 16** (contrast with Caso 15,
which is git): this isolates signature-computation correctness from
Caso 15's fingerprint-cache correctness -- a non-git workdir is
GUARANTEED (per Caso 15's own contract) to always re-run `test_command`
for real on both Stops, so the second invocation is never skipped by the
new caching layer regardless of whether it lands correctly. Without this
choice, testing volatile-content survival in a git workdir would
implicitly depend on the tree-change-detection logic too, conflating two
independently-testable behaviors added in the same task.

Verification: `python3 -m pytest unmassk-toolkit/tests/test_stop_dod_gate.py
unmassk-toolkit/tests/test_dod_gate_classify.py -q` -> 71 passed (69
pre-existing + 2 invariant-pinning new tests), 3 failed for the exact
expected reasons (RED, correct cause confirmed by reading each failure's
own assertion message before declaring done -- no exception/crash, no
wrong-reason red).

See also [[stop-dod-gate-d042-declared-identity-coverage-notes]] and
[[customs-doctor-20260806-two-red-contracts-notes]] for prior sessions on
this same hook file -- same test-first + real-subprocess discipline.
