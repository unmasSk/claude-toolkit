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

**Follow-up session (2026-07-08, real Windows box, HEAD 82645d8) — hardening
the TEST SIDE after #52's production fix landed.** House root-caused 2 fresh
CI crashes (`test_security_regression.py` BUG K/P, `test_crown_retraction.py`)
to test-only `write_text()`/`_sp.run(text=True)` calls missing `encoding=`
— the W1 production guard doesn't reach test helper code or `-c` code-strings
run as a child subprocess. Full tree sweep (AST for `write_text`/`read_text`/
`open`, regex paren-matching for `subprocess.run`/`_sp.run` since many of
those live INSIDE triple-quoted f-string code blocks, invisible to
`ast.parse()` of the outer file) found **140 unencoded sites across 16
files** (50 subprocess-class, 90 write_text/read_text-class, 0 remaining
`open()` — that class was already fully swept in the #52 session above).
Only 3 of the 140 were the ones House named explicitly — the other 137 were
genuinely latent, never having crashed yet. Two NEW script bugs surfaced
while automating this, both reusable lessons:

1. **`ast` `col_offset`/`end_col_offset` are UTF-8 BYTE offsets, not
   character offsets.** A naive `line[end_col_offset - 1]` insertion breaks
   silently (produces a stray line, not even a clean crash) on any line
   containing a multi-byte char BEFORE the target column — e.g.
   `"SENSITIVE ORIGINAL CONTENT — INSTALL"` (em-dash, 3 UTF-8 bytes) shifted
   the byte offset 2 past the true character position. Fix: encode the line
   to UTF-8 bytes, slice by the byte offset, decode back, take `len()` of
   that to get the real character index — `len(line.encode("utf-8")[:col].decode("utf-8"))`.
   Caught immediately by `py_compile`-ing every touched file after each
   automated pass (mandatory step, not optional, whenever a script inserts
   text by computed offset).
2. **Nested same-quote f-strings are a SyntaxError below Python 3.12
   (PEP 701).** Auto-inserting `encoding="utf-8"` (double quotes) into a
   call that sits inside `f"...{victim.read_text()!r}"` (also double-quoted)
   produces `f"...{victim.read_text(encoding="utf-8")!r}"` — invalid syntax
   pre-3.12. Fix: always insert the encoding value with single quotes
   (`encoding='utf-8'`) since call sites are never themselves inside a
   single-quoted f-string in this codebase — cheap, universally safe,
   costs nothing when the call isn't inside an f-string at all.
   Both bugs were caught by the same cheap gate: `python3 -m py_compile`
   (or a full `ast.parse()` sweep) on every file immediately after an
   automated multi-site edit, BEFORE running pytest — never trust an
   automated insert-by-offset script without a compile check in between.

**Verification gotcha: ambient `PYTHONUTF8=1` in this shell masks the very
bug being fixed.** `locale.getpreferredencoding(False)` reported `utf-8` on
this real Windows box on first check — looked like the box just doesn't
have a cp1252 problem. Re-checked with `python3 -X utf8=0 -c "..."`: revealed
`PYTHONUTF8=1` was set ambient in the shell env, and Python's UTF-8 mode
overrides `locale.getpreferredencoding()` to always report `utf-8`
regardless of the OS ANSI codepage. With `PYTHONUTF8=0` explicitly, the same
call reports `cp1252` — the box's TRUE codepage, and the actual condition
that broke CI. Re-ran the full verification suite with `PYTHONUTF8=0`
(not just `PYTHONIOENCODING`, which only affects stdout/stderr text mode,
NOT `open()`/`write_text()`/`subprocess.run(text=True)` default encoding) —
103 passed, 64 skipped (symlink tests gated by `real_symlink_capable`, no
privilege on this box), 0 failed, matching the plain run. **Lesson: on a
real target box, don't trust `locale.getpreferredencoding()` at face value
without also checking `PYTHONUTF8`/`sys.flags.utf8_mode` — an ambient env
var in the CURRENT shell can silently make the "real Windows repro" not
actually exercise the failure mode you're trying to verify against.**

**Issue #54 (2026-07-12), linear mode, regression pass — `errors=` param on
`open_no_follow_symlink()`/`_open_no_follow_symlink_fallback()`.** Follow-on
bug in the same family as #52: a lone surrogate (`"\udc80"`, half a broken
Unicode pair — this codebase's git-log decoding can produce one) in
write-mode text raised `UnicodeEncodeError` (a `ValueError` subclass) from
inside `os.fdopen(...).write()`, escaping the "only OSError escapes this
function" contract every caller relies on. Ultron's fix: both twins (and the
Windows sub-function) gained `errors: str = "strict"` (default unchanged, no
behavior change for existing callers); `write_boot_log()` is the one real
call site opting in with `errors="backslashreplace"`. Tests added to
`test_crossplatform_symlink_guard.py` (`TestErrorsParameterSurrogateEscape`,
right before the existing "Item 7" cp1252 section) and
`test_boot_output.py` (`TestWriteBootLogSurrogateEscape`, right after
`TestBootLogWriteFailureFallback`, same subprocess-load-the-hook-via-
`spec_from_file_location` pattern as `_render_banner_with_branch`/
`_run_boot_with_failing_log_write`).

Two things worth remembering for next time this shape recurs:
1. **§34 "derive, don't hand-type" for a codec-transform round trip**:
   when the write transforms the payload (backslashreplace escapes the
   surrogate into literal ASCII, so reread != original payload), the
   correct anti-fixture technique is computing
   `expected = payload.encode("utf-8", errors="backslashreplace").decode("utf-8")`
   inside the test itself — Python's own stdlib codec is an independent,
   uneditable contract (neither Dante nor Ultron can tune it to fit the
   day's behavior), so this isn't a hand-typed fixture even though it's
   computed outside the production call. It's also literally the same
   transform `os.fdopen(errors="backslashreplace")` delegates to
   internally, so it inherently matches.
2. **Confirming a pre-fix RED baseline without reverting production code**:
   ran the identical write via the CURRENT (fixed) function but simply
   omitting the `errors=` kwarg (default "strict") — this reproduces
   exactly what every pre-fix call site did unconditionally (no such
   parameter existed) and confirms `UnicodeEncodeError` fires, proving
   case 1 would have failed red before the fix. Cheaper than checking out
   the pre-fix commit, and just as honest since the default path is
   byte-identical to the old unconditional behavior.
3. **The guard test (case 4, default stays "strict") matters as much as the
   fix test** — it's what stops a future refactor from silently flipping
   the default to `"backslashreplace"` everywhere, which would hide real
   encoding corruption at every one of the dozens of call sites that never
   opted in.

See also: [unmassk-toolkit-python-test-conventions](unmassk-toolkit-python-test-conventions.md) (git identity / symlink-guard sessions earlier the same day).

**Stale-assertion repair (2026-08-04) — `TestUserPromptMemoryCheckCp1252`, line 130.**
Owner decided the per-message watchdog (`user-prompt-memory-check.py`) must
always print something (even "nothing to report") instead of staying silent
on a no-match turn — a silent watchdog is indistinguishable from one that
isn't running. That fix turned this test green except for one assertion:
`assert "git-memory-recall.py" in out` — a v1-system script name, deleted at
the start of `feat/memoria-v2`, that can never appear in output again.
**Lesson for any future contract test in a fast-moving branch: an assertion
tied to a literal string naming another file/script is a landmine** — it
silently outlives the file it names. Fix was NOT to delete the assertion
outright (the class's whole point — "useful output", not just rc==0 — was
still worth keeping) but to replace it with a structural, convention-based
pair: (1) `out.strip()` truthy (the actual behavior the owner just asked
for: hook must never emit nothing), (2) `out.strip().startswith("[")` (the
bracket-label convention every line in this hook already follows —
`[git-memory-boot]`, `[git-memory]`, `[skill-router]`, `[memory-check]` —
verified against the hook's real `main()`, not invented). Neither assertion
names a literal banner sentence, so a future rewrite of the wording doesn't
false-positive this test. Deliberately did NOT extend
`test_user_prompt_recall.py::TestNoRegression::test_base_output_not_empty`
(which already asserts plain non-emptiness) to cover this — that test runs
under normal encoding; this one's whole reason to exist is the SAME
invariant verified specifically under the cp1252 encoding-guard path, which
is a distinct failure mode (a swallowed exception in the encoding guard
could silently drop output even with rc==0) that the plain-encoding test
cannot catch. Left a dated inline comment in the test itself explaining the
literal-string trap, so nobody restores the old assertion thinking it was
lost by accident.
