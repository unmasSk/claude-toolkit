---
name: encoding-contract-notes
description: issue #52 (Windows cp1252 crash) test-first contract — W1/W2/W3 fixes, the parent-decode gotcha that flipped a believed-GREEN scenario to RED, and the AST-based open()-encoding sweep technique
metadata:
  type: project
---

**Issue #52 (2026-07-07), T1, test-first mode — House round 2 root cause:**
no entry point under `unmassk-toolkit/bin/*.py`/`hooks/*.py` forces UTF-8 on
stdout/stderr (W1). Under a Windows console on a legacy codepage (e.g.
cp1252), any `print()` of an emoji/arrow raises `UnicodeEncodeError`, RC=1.
Reproducible on ANY OS via `PYTHONIOENCODING=cp1252` env — no real Windows
box needed. I wrote the acceptance CONTRACT (4 scenarios, see
`unmassk-toolkit/tests/test_encoding_contract.py`) — Ultron implements W1
next, then the `xfail(strict=False)` markers come off.

**The gotcha that matters most for future contract work: "the child didn't
crash" is not the same as "the scenario is green" — you must trace through
the PARENT's own decode, not just the child's exit code.** Scenario (d),
`hooks/session-start-boot.py`, looked GREEN on first manual check: piping
its cp1252-forced stdout through a bash terminal showed mojibake but no
crash (RC=0) — its only "special" stdout character on the normal path, an
em-dash U+2014, happens to already be encodable in cp1252 (byte 0x97), so
the CHILD's `print()` never raises. But `conftest.py`'s `run_script()` (used
by the actual pytest test, not my manual bash check) decodes the child's
captured stdout as UTF-8 (see W2 below) — and byte 0x97 alone is not valid
UTF-8, so `UnicodeDecodeError` fires INSIDE `run_script()`/`run_cmd()`
itself, before the test body ever receives a clean `(rc, out, err)` tuple
to assert on. `pytest.mark.xfail` still catches this correctly (it wraps
the whole test body, not just `assert` statements) — no special exception
handling needed in the test itself. **Lesson: a manual repro via raw shell
piping (`echo ... | python3 script.py`) tells you whether the CHILD
crashes, but says nothing about whether a UTF-8-decoding PARENT (subprocess
harness, CI log collector, etc.) can even read the child's output — always
also reproduce through the actual test harness's own decode path
(`subprocess.run(..., encoding="utf-8")`, matching what `run_cmd` does)
before declaring a scenario GREEN.** Caught this by re-running the file
with `--runxfail` (see below) and getting an unexpected 4th failure where I
expected only 3.

**Verification pattern for "acceptance contract must be RED before Ultron
implements": `pytest --runxfail`.** When a test-first contract needs
`xfail(strict=False)` markers so the suite stays green while unimplemented
(coordinator's explicit ask, to avoid polluting the normal CI signal), you
can't just run the file normally to see red — `xfail` swallows the failure
into an `XFAIL` report line, not a `FAILED` one. `pytest <file> -q
--runxfail` ignores all xfail markers and reports the TRUE pass/fail state,
which is what actually proves the contract bites. Then re-run WITHOUT
`--runxfail` to confirm the suite reports clean `XFAIL` (not `FAILED`) so
CI stays green. Do both and report both numbers — only one of them proves
red, only the other proves the suite is safe to merge.

**W2 fix — `conftest.py::run_cmd`'s `subprocess.run(text=True)` needed
explicit `encoding="utf-8"`.** Without it, the parent decodes child
stdout/stderr using `locale.getpreferredencoding(False)` — UTF-8 on a
properly configured macOS/Linux box (so the fix is a no-op there, confirmed
via full-suite re-run: 984/2 unchanged), but the Windows console's ANSI
codepage otherwise. Once Ultron's W1 fix lands (child always emits UTF-8
regardless of ambient `PYTHONIOENCODING`), the parent needs to decode as
UTF-8 to match — this fix is "correct for the future child," which is
exactly why it exposes scenario (d) as red today (see above): the OLD,
not-yet-fixed child still emits cp1252 bytes, and the NEW parent now
insists on UTF-8, so today they disagree. That disagreement is not a bug
in the fix — it's the fix correctly refusing to paper over W1's absence.

**W3 sweep — AST-based `open()` search, not grep.** The coordinator asked
for a full sweep of `tests/*.py` `open()` calls missing `encoding=`. A grep
for `open(` gives false positives (comments/docstrings mentioning `open()`
as prose, e.g. dozens of lines in `test_security_regression.py`'s bug
descriptions) and false negatives are easy to introduce by hand-editing 100+
call sites. Used `ast.walk()` to find real `ast.Call` nodes with
`func.id == "open"`, checked `node.keywords` for an existing `encoding=`
kwarg (skip), checked the 2nd positional arg / `mode=` kwarg against a
binary-mode set (`"wb"`, `"rb"`, etc. — skip, encoding is invalid there),
then used `node.end_lineno`/`node.end_col_offset` (Python 3.8+) to find the
exact column of the call's closing `)` and insert `, encoding="utf-8"`
immediately before it — processing matches within each file sorted by
`(-end_lineno, -end_col_offset)` so inserting on one line never shifts the
column offsets of a not-yet-processed match. 120 call sites across 16
files, 0 remaining after, all files still `py_compile`-clean, full suite
unchanged (984/2) after. This technique is reusable for any future
"find every real call to X across the test suite, ignoring comments"
sweep — much more reliable than regex/grep for anything involving nested
parens (`open(os.path.join(...))` breaks naive single-paren regexes) or
docstring false-positives.

**Note: `open_no_follow_symlink()` (production helper, `lib/git_helpers.py`)
already defaults `encoding="utf-8"`** — so `test_crossplatform_symlink_guard*.py`'s
`target_open(...)` calls (aliases to it) were correctly EXCLUDED from the
sweep; only the builtin `open()` needed touching.

**Task 4 — stderr preservation in shared test helpers that wrap a
production subprocess.** `test_drift.py::run_snapshot()` and
`conftest.py::run_doctor_json()` both used `rc, out, _ = run_cmd(...)`
(or `run_script`), silently discarding stderr from every caller — exactly
what makes a CI-only crash (e.g. House's "7 ubuntu failures that don't
reproduce locally") unexplainable from the pytest failure message alone.
Fixed both to capture `err` and surface it: `run_snapshot` now asserts
`rc == 0` immediately with `stdout`/`stderr` embedded in the message (fails
fast, at the crash site, instead of some unrelated downstream assert
failing with zero context); `run_doctor_json` adds a non-breaking `"_debug"`
key to its already-existing failure-fallback dict (preserves the exact
return shape every existing caller relies on — `{"status": "error",
"checks": []}` — while making rc/stdout/stderr available to any test that
wants to assert on it). **Scope decision, worth remembering:**
`conftest.py::check_hook_msg()` has the SAME "returns int rc only, discards
stdout+stderr" shape and is used in ~50+ call sites across the suite —
identified but deliberately NOT touched, since changing its return
signature would ripple across every caller; flagged in the report as
out-of-scope rather than silently expanded. Don't assume "fix the pattern
everywhere" when one instance has a return-signature change with a large
blast radius and the ask didn't explicitly require it — flag instead of
silently expanding scope.

**Closed (same day):** Ultron implemented the UTF-8 guard
(`lib/encoding_guard.py` + 23 entry points, commit `38f5728`). Removed all
4 `xfail(strict=False)` markers from `test_encoding_contract.py` — verified
`pytest test_encoding_contract.py -q` → 4 passed clean, and full suite →
988 passed, 2 skipped, 0 xfailed/xpassed (984 baseline + these 4 now
counted as real passes instead of xfailed). Contract closed exactly as
designed: no test logic needed to change, only the markers came off.

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md) (git identity / symlink-guard sessions earlier the same day).
