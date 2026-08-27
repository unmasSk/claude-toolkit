---
name: price-check-red-contract-notes
description: RED contract AND hardening sweep for unmassk-trading's price_check.py — the two venues' real response shapes, the checked_at-after-fetch flaw the live round-trip caught, the per-test-import RED technique, and why the __main__ line needs a real process to be covered
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

---

# Update — hardening pass (2026-08-27, same day)

Second entry, after Ultron implemented and the review round closed. New file
`tests/test_price_check_hardening.py` (212 tests) alongside the untouched 62-test contract.
Whole plugin suite **433 → 645 passed** (3 consecutive identical runs).

## Measured coverage, not asserted coverage

`coverage run --branch --include="*/price_check.py"` over the whole tests directory:
**202 statements, 54 branches, 0 missed, 0 partial — 100.0%**, and an AST cross-check confirms
**20/20 functions** and **19/19 raise sites** executed. Do not assert a coverage floor inside a
test: measure it and report the number, the way the coordinator asked.

**The one line pytest can never see is `sys.exit(main())` under `if __name__ == "__main__"`.**
In-process coverage reported 99.2% with exactly that line missing. Fix that is honest rather than
cosmetic: `coverage run --append --branch --include=... <script> --help` — a REAL process running
the real entry point, appended to the same data file. That is also the only way the shebang path
gets exercised at all, and it is the path a person actually enters by.

## Behaviours pinned as they ARE, on purpose

- **A frozen quote delivered instantly reads as fresh.** `age_seconds` is measured from RECEIPT,
  not from when the venue last moved the price, and neither venue's ticker carries a price
  timestamp. The STALE guard catches a caller-supplied quote, a clock jump, and an unreadable
  timestamp — not this. Written as a long-named test explaining what it does and does not cover,
  so wiring a venue timestamp later means deliberately rewriting a test instead of silently
  changing behaviour. **A limit named in a test is a limit; a limit named in a doc is a rumour.**
- **Zero venues answering is `SINGLE_SOURCE`, not a fifth verdict.** Recommended KEEPING the
  four-verdict vocabulary: the caller's contract is the exit code plus the reason, both already
  correct, and for the caller "one venue" and "no venue" mean the same thing — nothing
  cross-checks this, do not trade. A fifth code would change every consumer's switch to fix a
  cosmetic reading of one field. Instead the reason is now pinned by test: it must contain
  "no venue answered" and must NOT contain "only price left".

## Real finding: the slashless form skips the XBT alias on a 4-letter quote

`_split_pair` splits a slashless pair as `base[:-3] / base[-3:]`, so `BTCUSDT` becomes
`BTCU`/`SDT` and the `BTC→XBT` alias never fires — Kraken is asked for `BTCUSDT`. Base+quote
re-concatenates identically, so the URL is not corrupted and the venue refuses it by name; it
fails loudly, never quotes the wrong asset. `BTC/USDT` with the slash resolves correctly to
`XBTUSDT`. Pinned by test as a known limit. `BTCEUR` and every 3-letter-quote pair are unaffected.

## Two assertions of MINE that were wrong, caught by running

- `json.loads(b'{"a":1}')` **succeeds** — json accepts bytes. My "bytes body is malformed" case was
  wrong, and the transport decodes to `str` before this point anyway, so it was also a lab case.
  Dropped rather than argued.
- Nothing else. The other 211 passed first time, which is what reading the implementation before
  writing assertions buys.

## Technique worth repeating: probe the branches in a REPL before asserting on them

Before writing a line of the sweep I ran every edge input through the real functions and printed
the actual results (`_split_pair` on 7 spellings, `_receipt_age` on 8 deltas including the
microsecond rounding, both CLI validators on 17 bad values). That is where the facts came from —
e.g. a half-second-old quote rounds to **1s, older never younger**, and `-300.5s` in the future
still reports `-300`. Guessing those and asserting the guess is how a hardening pass turns into an
argument with the implementer.
