#!/usr/bin/env python3
"""Cross-venue price check: one pair, two independent public venues, one verdict.

NOT lifted. Every other script in this plugin came verbatim from tradermonty
(MIT, see CREDITS.md); a sweep of published trading skills found none that
cross-checks a quote against a second venue or stamps it with its age, so this
one is written here, against the contract in ``tests/test_price_check.py``.

It answers one question: can this price be trusted to gate a decision? It
reports arithmetic and facts only -- two prices, their ages, the spread between
them -- and never a direction call, a target or a score.

Three things it refuses to do, because each one is a quiet lie:
  * average two disagreeing prices into one number;
  * report a spread of 0 when a venue is missing (that reads as agreement);
  * let a price out without its age.

Neither Kraken nor Binance timestamps its ticker, so the only honest age is
receipt time, stamped by the injected clock AFTER the body arrives. The check
instant is sampled once BOTH venues have answered; taken any earlier, every
fresh quote lands in the future and the script condemns its own good data.

No float touches the money path: prices are Decimal built from the venue's own
string, and leave as strings.

    python3 price_check.py --pair BTC/EUR
    echo $?    # 0 OK | 3 DISAGREE | 4 STALE | 5 SINGLE_SOURCE (2 is argparse's own)
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

OK = "OK"
DISAGREE = "DISAGREE"
STALE = "STALE"
SINGLE_SOURCE = "SINGLE_SOURCE"

# 2 is skipped on purpose: argparse spends it on its own usage error, and a
# caller must be able to tell a bad command line from a bad quote.
EXIT_CODES = {OK: 0, DISAGREE: 3, STALE: 4, SINGLE_SOURCE: 5}

DEFAULT_PAIR = "BTC/EUR"
DEFAULT_MAX_SPREAD_BPS = Decimal("50")
DEFAULT_MAX_AGE_SECONDS = 60
DEFAULT_TIMEOUT_SECONDS = 8

# Upper bounds for the two command-line limits: a spread limit above 100% or an
# age limit beyond a day is not a looser check, it is no check at all.
MAX_SPREAD_LIMIT_BPS = Decimal("10000")
MAX_AGE_LIMIT_SECONDS = 86400

BPS = Decimal(10000)
SECONDS_PER_DAY = 86400

KRAKEN_URL = "https://api.kraken.com/0/public/Ticker"
BINANCE_URL = "https://data-api.binance.vision/api/v3/ticker/price"
# Kraken spells bitcoin XBT, and answers a request for XBTEUR under the key
# XXBTZEUR -- which is why the result key is read from the response, never from
# the request.
KRAKEN_BASE_ALIASES = {"BTC": "XBT"}
USER_AGENT = "unmassk-trading/price_check"


@dataclass(frozen=True)
class Quote:
    """One venue's last traded price and the instant it reached us."""

    source: str
    price: Decimal | None
    fetched_at: datetime | None


class SourceError(Exception):
    """A venue did not give a usable price. Carries venue and cause apart."""

    def __init__(self, source: str, reason: str) -> None:
        super().__init__(f"{source}: {reason}")
        self.source = source
        self.reason = reason


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------
def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _http_get(url: str, timeout: float = DEFAULT_TIMEOUT_SECONDS) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        return response.read().decode("utf-8")


def _read_body(source, url, http_get, timeout):
    """Every transport failure becomes a named SourceError, never a default."""
    try:
        return http_get(url, timeout=timeout)
    except urllib.error.HTTPError as exc:
        raise SourceError(source, f"HTTP {exc.code} {exc.reason}") from exc
    except TimeoutError as exc:
        raise SourceError(source, f"timeout after {timeout}s") from exc
    except urllib.error.URLError as exc:
        if isinstance(exc.reason, TimeoutError) or "timed out" in str(exc.reason).lower():
            raise SourceError(source, f"timeout after {timeout}s") from exc
        raise SourceError(source, f"transport failure: {exc.reason}") from exc
    except OSError as exc:
        raise SourceError(source, f"transport failure: {exc}") from exc


def _parse_json(source, body):
    try:
        payload = json.loads(body)
    except (ValueError, TypeError) as exc:
        raise SourceError(source, f"malformed body: {exc}") from exc
    if not isinstance(payload, dict):
        raise SourceError(source, "malformed body: the top level is not a JSON object")
    return payload


def _price_from(source, raw, field):
    """Turn the venue's own string into a Decimal, or say why it cannot be one."""
    if not isinstance(raw, str) or not raw.strip():
        raise SourceError(source, f"unusable {field} field: {raw!r}")
    try:
        price = Decimal(raw.strip())
    except InvalidOperation as exc:
        raise SourceError(source, f"unreadable {field} field: {raw!r}") from exc
    if not price.is_finite() or price <= 0:
        raise SourceError(source, f"{field} field is not a positive number: {raw!r}")
    return price


# ---------------------------------------------------------------------------
# The two venues
# ---------------------------------------------------------------------------
def _split_pair(pair):
    base, _, quote = pair.upper().partition("/")
    if not quote:
        return base[:-3], base[-3:]
    return base, quote


def fetch_kraken(pair, *, http_get=None, clock=None, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Last traded price from Kraken's public Ticker, stamped on receipt."""
    base, quote = _split_pair(pair)
    symbol = f"{KRAKEN_BASE_ALIASES.get(base, base)}{quote}"
    url = f"{KRAKEN_URL}?{urllib.parse.urlencode({'pair': symbol})}"
    body = _read_body("kraken", url, http_get or _http_get, timeout)
    fetched_at = (clock or _utc_now)()
    return Quote(source="kraken", price=_kraken_price(body), fetched_at=fetched_at)


def _kraken_price(body):
    payload = _parse_json("kraken", body)
    errors = payload.get("error") or []
    if errors:
        # Kraken answers a bad pair with HTTP 200 and this array: a 200 that is
        # really a failure, and the silent-failure trap of this script.
        raise SourceError("kraken", "venue error: " + "; ".join(str(item) for item in errors))
    result = payload.get("result")
    if not isinstance(result, dict) or not result:
        raise SourceError("kraken", "empty or missing result mapping")
    if len(result) != 1:
        raise SourceError("kraken", f"ambiguous result mapping, {len(result)} pairs: {sorted(result)}")
    key, entry = next(iter(result.items()))
    last = entry.get("c") if isinstance(entry, dict) else None
    if isinstance(last, list):
        last = last[0] if last else None
    if last is None:
        raise SourceError("kraken", f"missing field 'c' in result {key}")
    return _price_from("kraken", last, "c")


def fetch_binance(pair, *, http_get=None, clock=None, timeout=DEFAULT_TIMEOUT_SECONDS):
    """Last price from Binance's public data host, stamped on receipt."""
    base, quote = _split_pair(pair)
    url = f"{BINANCE_URL}?{urllib.parse.urlencode({'symbol': f'{base}{quote}'})}"
    body = _read_body("binance", url, http_get or _http_get, timeout)
    fetched_at = (clock or _utc_now)()
    return Quote(source="binance", price=_binance_price(body), fetched_at=fetched_at)


def _binance_price(body):
    payload = _parse_json("binance", body)
    if "price" not in payload:
        raise SourceError("binance", "missing field 'price' in the response")
    return _price_from("binance", payload["price"], "price")


DEFAULT_FETCHERS = {"kraken": fetch_kraken, "binance": fetch_binance}


# ---------------------------------------------------------------------------
# The decision layer -- no network, ever
# ---------------------------------------------------------------------------
def _receipt_age(fetched_at, checked_at, max_age_seconds):
    """(age_seconds, problem). A problem means it must not pass as fresh."""
    if fetched_at is None:
        return None, "no receipt time, so its age is unknown"
    if fetched_at.tzinfo is None or fetched_at.utcoffset() is None:
        return None, "receipt time carries no timezone, so its age cannot be established"
    delta = checked_at - fetched_at
    # Integer arithmetic on purpose: total_seconds() is a float, and rounding a
    # quote down is rounding it younger than it is.
    age = delta.days * SECONDS_PER_DAY + delta.seconds + (1 if delta.microseconds else 0)
    if age < 0:
        return age, f"stamped {-age}s in the future (clock skew)"
    if age > max_age_seconds:
        return age, f"{age}s old, past the {max_age_seconds}s limit"
    return age, None


def _source_rows(fetchers, quotes, errors, checked_at, max_age_seconds):
    rows, stale = {}, {}
    for name in fetchers:
        quote = quotes.get(name)
        age, problem = (None, None)
        if quote is not None:
            age, problem = _receipt_age(quote.fetched_at, checked_at, max_age_seconds)
            if problem is not None:
                stale[name] = problem
        price = None if quote is None or quote.price is None else str(quote.price)
        fetched_at = None if quote is None or quote.fetched_at is None else quote.fetched_at.isoformat()
        rows[name] = {
            "price": price,
            "fetched_at": fetched_at,
            "age_seconds": age,
            "error": errors.get(name),
        }
    return rows, stale


def _spread_bps(prices):
    """None -- never 0 -- when a price is missing: 0 would read as agreement."""
    if len(prices) < 2 or any(price is None for price in prices):
        return None
    low, high = min(prices), max(prices)
    mid = (low + high) / 2
    if mid <= 0:
        return None
    return (high - low) / mid * BPS


def _decide(rows, stale, spread_bps, max_spread_bps, max_age_seconds):
    """Precedence SINGLE_SOURCE > STALE > DISAGREE, each with its own reason."""
    missing = [name for name, row in rows.items() if row["price"] is None]
    alive = [name for name in rows if name not in missing]
    if missing or len(rows) < 2:
        told = [f"{n} unavailable ({rows[n]['error'] or 'no price in the response'})" for n in missing]
        told.append(
            f"{', '.join(alive)} is the only price left, so nothing cross-checks it"
            if alive
            else "no venue answered with a usable price"
        )
        return SINGLE_SOURCE, "; ".join(told)
    if stale:
        return STALE, "; ".join(f"{n} cannot pass as fresh: {why}" for n, why in stale.items())
    if spread_bps is not None and spread_bps > max_spread_bps:
        return DISAGREE, (
            f"{' and '.join(rows)} differ by {spread_bps} bps, past the "
            f"{max_spread_bps} bps limit -- reported apart, never averaged"
        )
    return OK, (
        f"{' and '.join(rows)} agree within {spread_bps} bps (limit {max_spread_bps}) "
        f"and are no older than {max_age_seconds}s"
    )


def check_prices(
    *,
    pair,
    fetchers,
    now=None,
    clock=None,
    max_spread_bps=DEFAULT_MAX_SPREAD_BPS,
    max_age_seconds=DEFAULT_MAX_AGE_SECONDS,
):
    """Ask every fetcher for `pair` and say whether the answer can be trusted."""
    max_spread_bps = Decimal(str(max_spread_bps))
    quotes, errors = {}, {}
    for name, fetch in fetchers.items():
        try:
            quotes[name] = fetch(pair)
        except SourceError as exc:
            errors[name] = exc.reason
    # Sampled here on purpose: after every venue has answered. Taken earlier,
    # each fresh quote is stamped in the future and condemned as stale.
    checked_at = now if now is not None else (clock or _utc_now)()
    rows, stale = _source_rows(fetchers, quotes, errors, checked_at, max_age_seconds)
    spread_bps = _spread_bps([quotes[n].price if n in quotes else None for n in fetchers])
    verdict, reason = _decide(rows, stale, spread_bps, max_spread_bps, max_age_seconds)
    return {
        "pair": pair,
        "checked_at": checked_at.isoformat(),
        "sources": rows,
        "spread_bps": None if spread_bps is None else str(spread_bps),
        "verdict": verdict,
        "reason": reason,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def _spread_limit(text):
    try:
        value = Decimal(text)
    except InvalidOperation:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not value.is_finite() or value <= 0 or value > MAX_SPREAD_LIMIT_BPS:
        raise argparse.ArgumentTypeError(
            f"must be above 0 and at most {MAX_SPREAD_LIMIT_BPS} bps: {text!r}"
        )
    return value


def _age_limit(text):
    try:
        value = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a whole number of seconds: {text!r}") from None
    if value <= 0 or value > MAX_AGE_LIMIT_SECONDS:
        raise argparse.ArgumentTypeError(
            f"must be above 0 and at most {MAX_AGE_LIMIT_SECONDS} seconds: {text!r}"
        )
    return value


def _parser():
    parser = argparse.ArgumentParser(
        description="Cross-check one pair across two public venues before it gates a decision."
    )
    parser.add_argument("--pair", default=DEFAULT_PAIR, help="canonical pair, e.g. BTC/EUR")
    parser.add_argument(
        "--max-spread-bps",
        type=_spread_limit,
        default=DEFAULT_MAX_SPREAD_BPS,
        help="spread above this many basis points is DISAGREE (default: %(default)s)",
    )
    parser.add_argument(
        "--max-age-seconds",
        type=_age_limit,
        default=DEFAULT_MAX_AGE_SECONDS,
        help="a quote older than this is STALE (default: %(default)s)",
    )
    return parser


def main(argv=None, *, fetchers=None, now=None, clock=None):
    """One JSON document on stdout, and an exit code no caller can ignore."""
    args = _parser().parse_args(argv)
    report = check_prices(
        pair=args.pair,
        fetchers=DEFAULT_FETCHERS if fetchers is None else fetchers,
        now=now,
        clock=clock,
        max_spread_bps=args.max_spread_bps,
        max_age_seconds=args.max_age_seconds,
    )
    print(json.dumps(report, indent=2))
    return EXIT_CODES[report["verdict"]]


if __name__ == "__main__":
    sys.exit(main())
