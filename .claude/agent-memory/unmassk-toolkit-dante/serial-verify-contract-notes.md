---
name: serial-verify-contract-notes
description: unmassk-electronics serial_verify.py acceptance contract (test-first pass 1) -- pyserial install gotcha, evaluate_lines/CLI separation pattern, what the hardening pass still owes
metadata:
  type: project
---

Test file: `unmassk-electronics/skills/electronics-micro/scripts/tests/test_serial_verify.py`
(+ `conftest.py` in the same dir). Script under contract (not yet built):
`unmassk-electronics/skills/electronics-micro/scripts/serial_verify.py`.

**This is a NEW plugin directory for scripts/*.py CLI+import tests** --
`unmassk-electronics` had zero test infra before this session (no
`tests/`, no `conftest.py`). Followed the SAME naming convention already
established in `unmassk-3d/skills/unmassk-3d/scripts/tests/conftest.py`
(`run_cli_for`, `import_module_from`, `parse_stdout_json`) for consistency
across the toolkit, but wrote a fresh, self-contained conftest.py -- plugins
are isolated from each other, no cross-plugin conftest import path exists
or should be created.

**Contract shape (pinned by the task, not derived from code):**
`evaluate_lines(lines_iterable, expect, reject_patterns) -> dict` is a pure
decision function, deliberately separated from the pyserial/real-port layer
so it's testable with fake line lists, no hardware. Output dict is exactly
`{"ok": bool, "matched_expect": bool, "matched_reject": str|None, "reason":
str}`. Decision order matters and is asymmetric: a reject pattern anywhere
in the stream wins even if it appears AFTER the expect marker (crash always
overrides), but the expect marker only resolves to `ok:true` if no reject
ever showed up -- meaning a correct implementation must scan the WHOLE
finite stream (or short-circuit only on a reject match, never on an expect
match) rather than returning as soon as expect is seen. The literal string
`"expect marker never seen"` is pinned by the contract for the timeout/EOF
case -- assert it verbatim, not just "reason is non-empty", exactly the
kind of one contract-pinned string that's fine to hardcode (§34 "fabricated
ground truth" is about hand-typing *derived* values, not literal strings
the task itself specifies).

**pyserial install gotcha (macOS homebrew python 3.14, externally-managed
environment, PEP 668):** plain `pip install pyserial` fails with
`error: externally-managed-environment`. This repo's environment already
has `trimesh`/`cadquery` installed directly into
`/opt/homebrew/lib/python3.14/site-packages` from a prior session, meaning
`--break-system-packages` was used before -- same fix applies:
`python3 -m pip install --break-system-packages pyserial`. Confirmed
installed (3.5) but genuinely NOT imported anywhere in the test files
themselves for this contract pass -- `evaluate_lines` tests use plain
Python lists, and the only CLI test exercises the unopenable-port path
(interpreter fails to even launch the missing script, no pyserial call
happens). Installed pre-emptively per the task's own instruction ("so the
script will import later"), not because these tests needed it.

**Test-first pass 1 scope discipline (re-read Dante's own Build Mode rules
before writing):** almost drifted into EXHAUSTION-PROTOCOL-level coverage
(case-sensitivity of substring matching, empty reject-pattern list, a
poison-generator test proving early-exit on a decisive reject match without
draining an infinite/lazy iterable, a real pty-backed CLI round trip using
`pty.openpty()` as a hardware-free but still-real serial device). All of
that is genuinely valuable and DEFERRED explicitly (named in both the test
file's module docstring and this memo) to the hardening pass once Ultron
has implemented -- the orchestrator's task text itself scoped CLI coverage
for this pass to ONLY the bogus-port failure case ("You can test the
unopenable-port path via the CLI with a bogus --port"), which is a contract
pass instruction that overrides the usual §34.5 "at least one test must
exercise the real wiring end-to-end" default for this specific first pass.
Whoever runs the hardening pass should pick up: case sensitivity, empty
reject list, the streaming/early-exit proof (matters because a naive
`list(lines_iterable)`-first implementation would hang forever against a
real unbounded serial generator instead of returning the instant a crash
string appears), and the pty round trip for the CLI happy path (POSIX-only,
`os.ttyname(pty.openpty()[1])` opens fine via `serial.Serial()` without
real hardware).

**RED verification technique used:** rather than a single module-level
import causing one blanket collection error, put the importlib load
(`import_module_from`) behind a per-test `serial_verify_module` PYTEST
FIXTURE (not a bare module-level call). This makes pytest report 5 clean
`ERROR at setup` (FileNotFoundError) for the `evaluate_lines`-based tests
while the CLI test fails independently and for its own reason (subprocess
launch failure, "can't open file" on stderr from the interpreter itself,
not from serial_verify.py). Both are legitimate "RED because absent" but
distinguishing them at once is stronger proof the test bodies aren't
malformed than a single blanket collection error would have been --
`pytest --collect-only` on the file still cleanly enumerates all 6 items
with zero collection errors, which is the actual proof the test/conftest
Python itself is syntactically and import-wise sound.

See also: [run-cadquery-stale-output-contract-notes](run-cadquery-stale-output-contract-notes.md),
[cad-trimesh-validate-mesh-contract-notes](cad-trimesh-validate-mesh-contract-notes.md)
(the two prior scripts/*.py contract-test sessions this one's conventions
were pattern-matched against).
