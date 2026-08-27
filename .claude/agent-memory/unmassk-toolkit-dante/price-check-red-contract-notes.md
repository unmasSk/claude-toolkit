---
name: price-check-red-contract-notes
description: RED contract for unmassk-trading's price_check.py — the two venues' real response shapes, the checked_at-after-fetch flaw the live round-trip caught, and the per-test-import technique that keeps a RED contract failing instead of erroring at collection
metadata:
  type: project
---

# RED contract: `price_check.py` (unmassk-trading, 2026-08-27)

Test-first contract pass. File:
`unmassk-trading/skills/unmassk-trading/scripts/tests/test_price_check.py`, 62 tests.
The only script in this plugin NOT lifted from tradermonty — nothing published cross-checks a
quote against a second venue, so there was no source to copy and it got a contract first.

## Technique: keep a RED contract FAILING, not ERRORING

A missing implementation imported at module level collapses the whole file into ONE collection
error. Importing it inside each test (`def _pc(): import price_check; return price_check`) makes
every unmet clause a separate named FAILURE — which is the whole point of a RED contract, and
gives the orchestrator a real count. Verified: **61 failed, each `ModuleNotFoundError: No module
named 'price_check'`, 0 collection errors**.

**The trap that undoes it:** a `@pytest.mark.parametrize` whose arguments call a factory
(`aged(...)`, `make_quote(...)`) runs at COLLECTION time, so it re-imports the missing module
before any test starts and the file errors out anyway. Parametrize over plain data (price
strings, ages) and build the objects inside the test body.

## Live round-trip found a flaw in MY OWN contract before the implementer saw it

The `@pytest.mark.live` end-to-end test failed against a throwaway satisfiability prototype with:
`binance is stamped in the future (-1s): clock skew` → verdict STALE on perfectly good data.
Cause: the contract said "a future timestamp is STALE" (right) while `checked_at` was sampled
BEFORE the fetches (wrong) — so every fresh receipt stamp landed after `checked_at`. Pinned
offline afterwards by `test_the_check_time_is_sampled_after_both_venues_have_answered`, which
asserts the call order is `["kraken", "binance", "clock"]`. **An age can only be measured against
an instant taken after the data arrived.** This is the argument for §34.5 in one incident: no
fixture would ever have produced that -1.

## Satisfiability probe — do this for every contract worth the name

A contract nobody can satisfy is a bug in the contract. I wrote a throwaway `price_check.py` in
the SCRATCHPAD (never in the repo, deleted after) and ran the suite against it with
`PYTHONPATH=<scratchpad>`: **62 passed**, including both live tests. That is what proved the
contract is achievable and internally consistent — and it is what surfaced the flaw above. Delete
the probe afterwards: an unreviewed prototype sitting next to the task is an invitation to skip
Ultron and the reviewers.

## The two venues, probed live 2026-08-27 (do not trust from memory — re-probe)

- `GET https://api.kraken.com/0/public/Ticker?pair=XBTEUR`
  → `{"error":[],"result":{"XXBTZEUR":{"c":["68644.20000","0.00002398"],...}}}`
  Last traded price is `result[<key>]["c"][0]`, a **string**. The result key is `XXBTZEUR`, NOT
  the `XBTEUR` that was requested — reading the response by the requested symbol is a guaranteed
  KeyError in production.
- `GET .../Ticker?pair=NOPEEUR` → **HTTP 200** with `{"error":["EQuery:Unknown asset pair"]}`
  and no `result` key at all. A 200 that is really a failure: the silent-failure trap here.
- `GET https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCEUR`
  → `{"symbol":"BTCEUR","price":"68656.96000000"}`, price a **string**.
- `GET .../ticker/price?symbol=NOPEEUR` → HTTP **400** `{"code":-1121,"msg":"Invalid symbol."}`.
- **Neither venue timestamps its ticker.** `/api/v3/ticker/24hr` has `closeTime`, `/ticker/price`
  does not, and Kraken has nothing anywhere. So the only honest age is receipt time, stamped by
  an injected `clock` AFTER the body arrives (a stamp taken before the request makes a slow reply
  look younger than it is).
- Real Kraken↔Binance BTC/EUR divergence at the time of the probe: **1.86 bps** against a 50 bps
  default threshold — a live `verdict == "OK"` assertion is not flaky at that margin.

## Money without a float, expressed as tests

- Prices and `spread_bps` are emitted as JSON **strings**; a helper walks the parsed document and
  asserts **no float exists anywhere** in it.
- The detector that actually catches a hidden `float()`: two prices that collapse to the same
  float64 (`10000.00000000000000001` vs `...02`). Under `Decimal` the spread is tiny but > 0;
  under float it is exactly 0 — perfect agreement that never happened.
- Clean bps arithmetic for boundary tests, mid-price reference `|a-b| / ((a+b)/2) * 10000`:
  `99.75/100.25` = exactly 50 bps (the threshold, still OK — "exceeds" is strict),
  `99.70/100.30` = exactly 60 bps (DISAGREE).

## Contract decisions I made that Ultron/Yoda may overrule (flagged, not smuggled)

Verdict precedence **SINGLE_SOURCE > STALE > DISAGREE**; a missing source yields `spread_bps:
null` and never `0` (a zero would read as perfect agreement); an unknown/naive/future timestamp is
STALE, never fresh; a zero or negative price is a named failure, not a price.

## The `live` marker

Registered by a `pytest_configure` appended to the shared `conftest.py` — a marker cannot be
registered from inside a test module and the repo's `pyproject.toml` declares no `[markers]`.
Deselect with `-m "not live"`. Note `pyproject.toml` sets `testpaths = ["unmassk-toolkit/tests"]`,
so this plugin's suite only runs when given its path explicitly.
