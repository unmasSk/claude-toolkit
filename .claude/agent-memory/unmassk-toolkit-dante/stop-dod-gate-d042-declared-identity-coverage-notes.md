---
name: stop-dod-gate-d042-declared-identity-coverage-notes
description: D-042 (dod_gate_classify.py declared-identity first-party check) coverage gap closed 2026-08-20 -- module-level-vs-function-level import gotcha, and a masked UnicodeDecodeError bug found (not fixed) in _names_from_setup_cfg
metadata:
  type: project
---

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
