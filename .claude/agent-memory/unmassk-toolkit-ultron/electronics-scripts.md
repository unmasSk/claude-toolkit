---
name: electronics-scripts
description: unmassk-electronics scripts/*.py conventions - pure decision function split, house setup pattern reuse, ssh self-verify scope
metadata:
  type: project
---

## serial_verify.py: pure decision function vs port layer

`unmassk-electronics/skills/electronics-micro/scripts/serial_verify.py` splits
`evaluate_lines(lines_iterable, expect, reject_patterns) -> dict` (pure, no
pyserial import at module level -- `import serial` is deferred inside
`_iter_serial_lines()`) from the CLI/port layer. Decision order: a reject
match short-circuits (`return` inside the `for` loop, so a lazy generator
stops being pulled); an expect match does NOT short-circuit -- the loop must
keep draining until either a reject appears or the iterable ends, since a
crash pattern appearing AFTER the expect marker still overturns it. This is
the load-bearing subtlety Dante's contract tests pin
(`test_reject_after_expect_still_ok_false_crash_wins`).

## House pattern for setup_*.py: unmassk-3d/skills/unmassk-3d/scripts/setup_cad_env.py

The canonical shape for a START-step installer script in this toolkit:
`run_setup() -> dict` (importable, never raises), a `main()` with a
last-resort `try/except Exception` guard around the whole summary build,
`_import_ok()`/`_pip_install_command()`/`_pip_install()` helpers, and a
platform-aware "missing manual tool" entry (`install_cmd` on macOS, `note`
pointing at the OS package manager on Linux/other). Reused verbatim (by
mirroring, not importing -- these `scripts/*.py` files are standalone by
convention, see conftest.py's own docstring) for both
`electronics-micro/scripts/setup_micro_env.py` (pip core: platformio +
pyserial; CLI-checked-only: pio/node/npx) and the SSH-based
`electronics-pi/scripts/setup_pi_env.py`.

## setup_pi_env.py: real install runs on the Pi, never fabricate a remote self-run

Since the real install target (a Raspberry Pi) doesn't exist in this dev
environment, `run_setup(host=None)` has 3 branches: `missing-ssh` (local
`ssh` absent), `no-host` (prints the exact on-Pi command block, exits 0 --
nothing to do locally), and `remote` (runs `ssh <host> "..."` for
apt+pip install and verify). Only the first two branches are
self-verifiable without a real Pi -- verified missing-ssh by stripping any
PATH dir containing an executable `ssh`, not by mocking `shutil.which`.
Never simulate a "successful remote run" JSON by hand; that would be a
fabricated fixture, not evidence.

## setup_pi_env.py: ssh over the remote branch needs BatchMode + ConnectTimeout + PEP 668 fallback

Cerberus review round (2026-07-14) caught 2 blocking issues in the initial
`--host` branch, both confirmed live:
- `subprocess.run(["ssh", host, cmd], ...)` with no `-o BatchMode=yes` /
  `-o ConnectTimeout=N` and no `stdin=subprocess.DEVNULL` can block on an
  inherited-stdin host-key/password prompt until the outer `timeout=`
  fires (up to 600s for the install call). Fix: always pass
  `["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", host, cmd]`
  plus `stdin=subprocess.DEVNULL`. Verified live against a black-holed IP
  (`10.255.255.1`): capped at 15.047s wall time, clean JSON, no hang.
- `python3 -m pip install --user ...` alone FAILS on Bookworm (current
  Raspberry Pi OS) because it's PEP 668 externally-managed --  `--user`
  does not bypass that. Fix: `--user --break-system-packages ... ||
  --user ...` (try-then-fallback string, single ssh command) so older Pi
  OS whose pip predates the flag still works.
- Also: when the install step itself fails, short-circuit and skip the
  2 follow-up verify ssh round-trips (`import gpiozero`, `pinctrl -h`) --
  they'd only reproduce the same one root cause 2 more times and waste
  the SSH_TIMEOUT_SECONDS budget twice for nothing new.

Rule for any future ssh-over-subprocess call in this toolkit: BatchMode +
ConnectTimeout + stdin=DEVNULL are not optional extras, they're the
difference between "fails in 15s with a clear reason" and "hangs for the
full outer timeout inheriting a TTY prompt nobody can answer."

## serial_verify.py: empty --expect must be a usage error, not an always-pass

`expect in line` is trivially `True` for `expect == ""` on the very first
line read -- an empty/whitespace `--expect` silently turns the gate into
an unconditional pass regardless of a crashed board (Cerberus, same
round). Guard added in `run_cli()` (not in `evaluate_lines()` -- the pure
function's contract/tests are untouched): `if not args.expect.strip():`
returns a clean `ok:false` JSON with a clear reason before ever touching
the serial port. Verified live: `--port /dev/null --expect ""` -> exit 1,
`{"ok": false, ..., "reason": "--expect must be a non-empty marker, ..."}`.
