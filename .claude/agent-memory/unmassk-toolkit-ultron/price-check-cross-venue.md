---
name: price-check-cross-venue
description: Building price_check.py against Dante's 62-test contract — the judgment calls the contract did NOT pin (exit codes, age rounding, spread precision) and the SKILL.md invocation that does not exist
metadata:
  type: project
---

# price_check.py, the one unmassk-trading script that was written, not lifted (2026-08-27)

Test-first: Dante's `tests/test_price_check.py` was the whole spec, 62 tests,
61 red (the 62nd probes the live venues and never needed code). Green on the
first suite run; `433 passed, 0 failed` for the plugin.

**Why:** a sweep of published trading skills found none that cross-checks a
quote against a second venue, so there was nothing to lift (contrast
[[trading-lift-tradermonty]], where every other script came verbatim from
tradermonty). M-132 governs what it may claim: arithmetic and facts, never a
direction call.

**How to apply — the three decisions the contract left open, and what I chose:**

- **Exit codes skip 2.** `argparse` spends 2 on its own usage error, so
  `DISAGREE/STALE/SINGLE_SOURCE` are 3/4/5. The contract only demanded
  `1 <= rc <= 255` and non-zero; with `DISAGREE = 2` a caller could not tell a
  bad quote from a typo in the flags. All four observed executed, plus
  argparse's own 2.
- **Age is ceiled, with integer arithmetic, never `total_seconds()`.**
  `total_seconds()` is a float, and truncating rounds a quote *younger* than it
  is — the one direction a staleness check must never err in. Ceil on
  `delta.days*86400 + delta.seconds + (1 if microseconds else 0)` is exact and
  keeps floats out of the module entirely.
- **`spread_bps` is NOT quantized**, so it prints 28 significant digits
  (`"0.9872427905869303572802622581"`). It cannot be: one contract test feeds
  two prices that differ by 1E-17 and demands the spread still be `> 0`, which
  any sane rounding would flatten to zero. The prose `reason` therefore carries
  the same long number. Ugly for a beginner-facing skill; a rounded *display*
  form is a product decision, not mine to invent.

**Found, not fixed (outside the one-file write scope):** `SKILL.md` line 81
documents `python3 scripts/price_check.py BTCEUR` — a positional argument the
contract never declares. Executed: it fails with argparse `unrecognized
arguments: BTCEUR`, exit 2. The contract's surface is `--pair`. Adding an
undeclared positional to satisfy a doc is inventing surface; correcting the doc
is Alexandria's.

**Venue facts worth not re-deriving:** Kraken answers `pair=XBTEUR` under the
key `XXBTZEUR` (read the key from the response, never from the request) and
signals a bad pair with **HTTP 200 + `{"error":[...]}` and no `result`**.
Binance's bad symbol is a real HTTP 400 whose informative body
(`{"code":-1121,"msg":"Invalid symbol."}`) is *dropped* — reading it needs
`HTTPError.read()`, and the contract's own fixture builds `HTTPError(..., fp=None)`,
where that read raises. So the error surfaces as `HTTP 400 Bad Request`.
