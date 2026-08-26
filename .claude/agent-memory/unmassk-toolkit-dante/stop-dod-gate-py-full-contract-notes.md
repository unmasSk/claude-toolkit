---
name: stop-dod-gate-py-full-contract-notes
description: hooks/stop-dod-gate.py full campaign merged from 4 date-split files — corrupt-config warn contract, D-042 declared-identity coverage, working-tree fingerprint cache, declared-contract-in-flight mechanism
metadata:
  type: project
---

Merged 2026-08-25 (memory compaction pass, phase 2) from 4 separate files that all covered the SAME piece of
code — `hooks/stop-dod-gate.py` (plus its sibling `bin/stop-dod-declare.py`, born in Round 4) — split only by
which session touched it. Per this project's compaction rule ("varios ficheros sobre UN mismo trabajo... se
funden en uno por tema"). Nothing was cut; each original file's content is reproduced below verbatim under
its own dated heading, in chronological order. Original filenames (now retired, kept only as history in this
note, not on disk): `stop-dod-gate-corrupt-config-contract-notes.md`,
`stop-dod-gate-d042-declared-identity-coverage-notes.md`, `stop-dod-gate-fingerprint-cache-contract-notes.md`,
`stop-dod-gate-declared-contract-in-flight-notes.md`.

## Round 1 (2026-08-06) — corrupt config.json must warn, distinct from not-configured silence

Task: write-only RED contract for `hooks/stop-dod-gate.py`
(`_read_test_command()`), owner-reported gap. `except (OSError,
json.JSONDecodeError): return None` makes a CORRUPT `config.json`
(invalid JSON, or unreadable e.g. a directory at that path) produce the
exact same silent exit-0 as a config.json that simply never declared
`test_command` (valid opt-out). Per this project's threat model ("the
system against itself", not an attacker) that's the forbidden shape: a
failure passing with zero signal. The opt-out case is correct and must
stay silent -- only the corrupt case must start warning (stderr or any
visible channel), while staying fail-open (never blocks close).

**Found and fixed in the same pass: the test file itself had gone
stale.** `tests/test_stop_dod_gate.py`'s `_write_config()` wrote to
`.claude/git-memory-config.json` (old system). The hook's own
`CONFIG_SUBPATH` comment says it moved to
`.claude/project-memory/config.json` *the same day* (2026-08-06) as the
last live consumer of the old file. Result: 4 of the file's 21 tests
(all of `TestCommandFailsBlocks`) had been silently red-for-the-wrong-reason
-- the fixture wrote a config the hook never reads, so the hook always
took the "no test_command" branch and never exercised the block path at
all. Confirmed by running the suite before touching anything: `4 failed,
17 passed`. Fixed the path in `_write_config()` (new helper
`_write_raw_config()` added alongside it for non-JSON content) + the
docstring, with a dated `[corregido 2026-08-06: ...]` annotation
explaining what was wrong and why, per
[[test-file-self-drift-correction-notes]]. After the fix: `21 passed`.
Then added the new contract on top of a now-correct baseline.

**Empirical repro before writing assertions (own convention, followed
here):** ran the hook by hand via subprocess against a temp dir with
`.claude/project-memory/config.json` containing `{ INVALID JSON }` --
confirmed `rc=0, stdout='', stderr=''`. Same empirical check for the
"not configured" baseline (valid JSON, no `test_command` key) -- also
`rc=0, stdout='', stderr=''`, proving the two cases are indistinguishable
today. Also confirmed cross-platform validity of a *second* repro for
the corrupt case (`config.json` as a directory instead of a file):
on Windows `open(dir_path, "r")` raises `PermissionError`, a subclass of
`OSError` -- same swallow path as `json.JSONDecodeError`, so it is a real
second instance of the same gap, not a cosmetic variant.

**Final RED state:** `tests/test_stop_dod_gate.py` -- 27 tests total, 23
green / 4 red. New classes: `TestNoCommandStaysSilent` (2 tests, green --
pins the correct silent baseline explicitly, including stdout/stderr
emptiness which no prior test in the file asserted) and
`TestCorruptConfigMustWarn` (4 tests, red for the right reason -- all
fail on `assert stderr.strip() != ""` or the direct
stderr-corrupt-vs-stderr-not-configured differs assertion). Did not touch
`hooks/stop-dod-gate.py` or `lib/memory/config.py` -- Ultron's task is to
make `_read_test_command()` distinguish the two cases (e.g. re-raise or
log on `json.JSONDecodeError`/`OSError` specifically instead of
swallowing both into `None`), keeping fail-open (rc always 0, never
blocks) intact.

Reference: [[test-file-self-drift-correction-notes]] (same drift shape:
prose/fixture referencing a path/name the production code moved away
from, caught only by re-running against current code, not by trusting
the file's own green history).

## Round 2 (2026-08-20) — D-042 declared-identity coverage gap closed

Task: Ultron shipped D-042 (Moriarty finding: `classify_missing_module()` now
checks the project's OWN DECLARED identity -- pyproject.toml
`[project].name` / `[tool.poetry].name` / `[tool.setuptools].packages` +
`packages.find`, `setup.cfg [metadata] name`, `-`→`_` normalized -- BEFORE
falling back to the old disk/git layout signal, `seg_exists()`) with zero
tests. Closed with a mix: `tests/test_dod_gate_classify.py` (new classes
`TestDeclaredFirstPartyIdentity`, `TestDeclaredIdentityFailsSafe`,
`TestNoDeclaredIdentityStillBlocksNewTopLevel` -- direct unit calls
against real pyproject.toml/setup.cfg files written to `tmp_path`, real
`tomllib`/`configparser`, no mocking) + `tests/test_stop_dod_gate.py`
(new class `TestDeclaredIdentityD042EndToEnd`, 2 tests -- real hook +
real pytest subprocess + real `pyproject.toml`, exactly the shape
Moriarty broke).

**Empirical gotcha, confirmed by hand before writing the end-to-end
tests:** `import moria` inside a test FUNCTION body (`def test_foo():
import moria`) makes pytest collect the test successfully -- the
`ModuleNotFoundError` fires at test EXECUTION time, not collection, so
the hook sees exit 1 (real test failure), never reaches
`classify_collection_error()` at all. This is the exact false negative
Ultron missed while unit-testing the helpers directly. The import MUST be
at MODULE level (top of the test file) to reproduce the real D-042 shape
-- verified live: module-level `import moria` → real pytest exit 2 with
`No module named 'moria'` in the output.

**Bug found while writing coverage, reported not fixed (out of Dante's
lane):** `_names_from_setup_cfg()`'s own docstring promises "never
raises", but `configparser.ConfigParser.read()` raises a bare
`UnicodeDecodeError` on a non-UTF-8 `setup.cfg` -- NOT a subclass of
either `OSError` or `configparser.Error`, so the function's own
`except (OSError, configparser.Error):` misses it. Confirmed empirically:
`_names_from_setup_cfg()` and `_declared_first_party_names()` called
DIRECTLY on a binary setup.cfg both raise uncaught. The bug is currently
MASKED at the only boundary the hook actually calls --
`classify_missing_module()`'s own blanket `except Exception: return
"block_thirdparty"` swallows it one layer up, so the OBSERVABLE hook
behavior stays safe (D2 holds: block on doubt). Tested accordingly:
`TestDeclaredIdentityFailsSafe.test_unreadable_binary_setup_cfg_never_allows_at_classify_boundary`
asserts the safe masked behavior at `classify_missing_module()`; a
SEPARATE test in the same class
(`test_malformed_but_valid_utf8_setup_cfg_degrades_to_empty_names`) tests
`_names_from_setup_cfg()` directly but only with a syntactically-broken
**valid-UTF8** cfg (the already-safe, already-caught `configparser.Error`
path) -- deliberately did NOT write a passing/failing unit test calling
`_names_from_setup_cfg()` directly with binary content, since that would
either pin today's contract violation as "expected" or go RED against
production code I'm not allowed to touch. Once Ultron adds
`UnicodeDecodeError` to that except clause, the regression test for the
fix is exactly that direct call.

Result: 61/61 green
(`python3 -m pytest unmassk-toolkit/tests/test_stop_dod_gate.py
unmassk-toolkit/tests/test_dod_gate_classify.py -q`).

See also [[issue-53-hardlink-reject-contract-notes]]-style precedent for
"found a real bug mid-coverage-pass, reported instead of routing around
it" -- same discipline applied here.

**Follow-up, same day:** Ultron fixed it -- added `UnicodeDecodeError` to
`_names_from_setup_cfg()`'s except clause; `_names_from_pyproject()` was
already covered via its existing `except (OSError, ValueError)`
(UnicodeDecodeError is a ValueError subclass). Regression added: new
class `TestUnicodeDecodeErrorFixDirectCalls` in
`test_dod_gate_classify.py`, calling `_names_from_setup_cfg()`,
`_names_from_pyproject()`, and `_declared_first_party_names()` DIRECTLY
(bypassing `classify_missing_module()`'s outer `except Exception`, which
is exactly what masked the original bug) with binary/non-UTF8 content --
each must return an empty set and never raise. 64/64 green.

**Final follow-up, same day (Yoda finding):** `_run_test_command()` had a
separate silent-failure hole -- a real exit-1 failure whose output
contained an invalid UTF-8 byte raised `UnicodeDecodeError` inside
`subprocess.run()`, which fell into the broad `except (..., ValueError)`
fail-open branch and allowed session close in silence over a genuine red.
Ultron fixed it with `errors="replace"` on `subprocess.run()` (decoding
can no longer raise under normal operation -- confirmed empirically: a
raw `0xFF` byte decodes to U+FFFD without exception) plus a narrower
`except UnicodeDecodeError:` (checked before the wider tuple) returning a
sentinel exit code (`_DECODE_ERROR_EXIT_CODE = -9999`) as defense in
depth. Regression added: new classes in `test_stop_dod_gate.py` --
`TestInvalidUtf8ByteInRealFailureBlocks` (exact repro: real exit 1,
invalid byte in output, blocks with `�` in the reason, never
empty), `TestInvalidUtf8ByteDedupStability` (dedup stays stable with the
replacement char in the signature; cross-session determinism verified by
reading `last_block_signature` from two separate real state files),
`TestUnknownNonzeroExitCodeAlwaysBlocks` (the general "any unnamed
non-zero exit -> BLOCK" fallback that `-9999` itself would rely on --
the sentinel has no real repro path once `errors="replace"` prevents the
raise, so this tests the umbrella contract with a real arbitrary exit
code instead, plus an explicit cross-check against the already-covered
real SIGHUP case). 69/69 green.

## Round 3 (2026-08-22, Caso 15/16) — working-tree fingerprint cache + volatile-memory-address signature

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

See also Round 2 above and
[[customs-doctor-20260806-two-red-contracts-notes]] for prior sessions on
this same hook file -- same test-first + real-subprocess discipline.

## Round 4 (2026-08-22, Caso 17, same day) — declared test-first RED must not block Stop

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
   as 2 of Round 3 above's 4 tests.
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
Round 3 above's Caso 16): isolates
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

See also Round 3 above and
Round 2 above for prior
same-file test-first sessions -- same real-subprocess, no-mock
discipline, same "local helpers next to the test class that needs them"
placement convention (not the shared Helpers section at the top).
