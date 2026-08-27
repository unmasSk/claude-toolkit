"""RED acceptance contract for price_check.py (NOT lifted -- written here).

Every other script in this plugin was lifted verbatim from tradermonty
(MIT, see CREDITS.md). ``price_check.py`` is the exception: a sweep of 291
published trading skills found nothing that cross-checks a quote against a
second venue or stamps a quote with its age, so there was no source to copy.
No implementation exists yet -- this file is the contract Ultron implements
against, and it is expected to be RED until it does.

WHY THE IMPLEMENTATION IS IMPORTED INSIDE EACH TEST (``_pc()``): while
price_check.py is missing, a module-level import would collapse this whole
file into one collection error. Importing per test makes every unmet clause
of the contract show up as its own named FAILURE, which is what a RED
contract is for. After the implementation lands, the import is a dict lookup.

THE SHAPES BELOW ARE REAL, PROBED 2026-08-27, NOT IMAGINED:

  GET https://api.kraken.com/0/public/Ticker?pair=XBTEUR
    {"error":[],"result":{"XXBTZEUR":{"c":["68644.20000","0.00002398"], ...}}}
    -- note the result key is XXBTZEUR, NOT the XBTEUR that was asked for
    -- last traded price is result[<key>]["c"][0], a STRING
    -- there is NO timestamp anywhere in this response
  GET https://api.kraken.com/0/public/Ticker?pair=NOPEEUR
    HTTP 200 with {"error":["EQuery:Unknown asset pair"]} and NO result key
    -- a 200 that is actually a failure: the silent-failure trap of this script

  GET https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCEUR
    {"symbol":"BTCEUR","price":"68656.96000000"}   -- price is a STRING, no timestamp
  GET .../api/v3/ticker/price?symbol=NOPEEUR
    HTTP 400 with {"code":-1121,"msg":"Invalid symbol."}

Neither venue timestamps its ticker, so the only honest age is receipt time,
stamped by the caller-injected ``clock`` AFTER the body arrives (pinned by
test_kraken_stamps_receipt_time_after_the_body_arrives).

SCOPE OF THIS PASS: acceptance granularity (test-first contract pass). The
exhaustive branch/error-path sweep belongs to the hardening pass, after there
is real code to measure.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

# ---------------------------------------------------------------------------
# The contract's own vocabulary. These four strings and the two default
# thresholds ARE the specification (the verdict table), so they are written
# here on purpose rather than imported from the module under test -- a
# contract that reads its expectations out of the implementation proves
# nothing. test_documented_defaults_are_the_ones_the_module_ships crosses the
# two sides over.
# ---------------------------------------------------------------------------
OK = "OK"
DISAGREE = "DISAGREE"
STALE = "STALE"
SINGLE_SOURCE = "SINGLE_SOURCE"
NON_OK_VERDICTS = (DISAGREE, STALE, SINGLE_SOURCE)

SPEC_MAX_SPREAD_BPS = Decimal("50")
SPEC_MAX_AGE_SECONDS = 60

TOP_LEVEL_KEYS = {"pair", "checked_at", "sources", "spread_bps", "verdict", "reason"}
SOURCE_KEYS = {"price", "fetched_at", "age_seconds", "error"}

NOW = datetime(2026, 8, 27, 12, 0, 0, tzinfo=timezone.utc)
PAIR = "BTC/EUR"


def _pc():
    """Import price_check.py (put on sys.path by this directory's conftest)."""
    import price_check

    return price_check


# ---------------------------------------------------------------------------
# Factories. Tests override only what they care about.
# ---------------------------------------------------------------------------
def make_quote(source="kraken", price="68644.20000", fetched_at=NOW):
    """Build a price_check.Quote. price is passed as Decimal, never float."""
    pc = _pc()
    return pc.Quote(
        source=source,
        price=None if price is None else Decimal(price),
        fetched_at=fetched_at,
    )


def quote_fetcher(quote):
    """A fetcher that records its calls and returns a fixed quote."""

    def fetch(pair):
        fetch.calls.append(pair)
        return quote

    fetch.calls = []
    return fetch


def failing_fetcher(source, reason):
    """A fetcher that fails the way a real venue failure must surface."""
    pc = _pc()

    def fetch(pair):
        fetch.calls.append(pair)
        raise pc.SourceError(source, reason)

    fetch.calls = []
    return fetch


def check(
    kraken=None,
    binance=None,
    now=NOW,
    max_spread_bps=SPEC_MAX_SPREAD_BPS,
    max_age_seconds=SPEC_MAX_AGE_SECONDS,
):
    """Run the decision layer with two injected fetchers. No network."""
    pc = _pc()
    fetchers = {
        "kraken": kraken if kraken is not None else quote_fetcher(make_quote("kraken")),
        "binance": binance
        if binance is not None
        else quote_fetcher(make_quote("binance", "68644.20000")),
    }
    return pc.check_prices(
        pair=PAIR,
        fetchers=fetchers,
        now=now,
        max_spread_bps=max_spread_bps,
        max_age_seconds=max_age_seconds,
    )


def aged(seconds, source="kraken", price="68644.20000"):
    """A quote whose receipt time is exactly `seconds` before NOW."""
    return make_quote(source, price, NOW - timedelta(seconds=seconds))


def recording_http(body, status=200):
    """An injectable transport: returns a body, records the URL it was given."""

    def http_get(url, **kwargs):
        http_get.urls.append(url)
        return body

    http_get.urls = []
    http_get.status = status
    return http_get


def raising_http(exc):
    def http_get(url, **kwargs):
        http_get.urls.append(url)
        raise exc

    http_get.urls = []
    return http_get


KRAKEN_OK_BODY = json.dumps(
    {"error": [], "result": {"XXBTZEUR": {"c": ["68644.20000", "0.00002398"]}}}
)
BINANCE_OK_BODY = json.dumps({"symbol": "BTCEUR", "price": "68656.96000000"})


def _walk_floats(obj, path="$"):
    """Yield the path of every float found anywhere in a parsed JSON document."""
    if isinstance(obj, float):
        yield path
    elif isinstance(obj, dict):
        for key, value in obj.items():
            yield from _walk_floats(value, f"{path}.{key}")
    elif isinstance(obj, list):
        for index, value in enumerate(obj):
            yield from _walk_floats(value, f"{path}[{index}]")


def run_cli(argv, fetchers, now=NOW):
    pc = _pc()
    return pc.main(argv, fetchers=fetchers, now=now)


def two_fetchers(kraken_quote, binance_quote):
    return {
        "kraken": quote_fetcher(kraken_quote),
        "binance": quote_fetcher(binance_quote),
    }


# ===========================================================================
# A. The injectable seam -- without it, nothing below can be tested offline
# ===========================================================================
def test_default_fetchers_are_exactly_the_two_named_venues():
    pc = _pc()
    assert set(pc.DEFAULT_FETCHERS) == {"kraken", "binance"}
    assert callable(pc.DEFAULT_FETCHERS["kraken"])
    assert callable(pc.DEFAULT_FETCHERS["binance"])


def test_documented_defaults_are_the_ones_the_module_ships():
    pc = _pc()
    assert Decimal(str(pc.DEFAULT_MAX_SPREAD_BPS)) == SPEC_MAX_SPREAD_BPS
    assert pc.DEFAULT_MAX_AGE_SECONDS == SPEC_MAX_AGE_SECONDS


def test_verdict_logic_runs_with_no_network_at_all(monkeypatch):
    """The decision layer must never reach urllib when fetchers are injected."""

    def explode(*args, **kwargs):
        raise AssertionError("check_prices opened a socket; the fetcher seam is not real")

    monkeypatch.setattr(urllib.request, "urlopen", explode)
    kraken = quote_fetcher(make_quote("kraken"))
    binance = quote_fetcher(make_quote("binance"))
    report = check(kraken=kraken, binance=binance)
    assert report["verdict"] == OK
    assert kraken.calls == [PAIR]
    assert binance.calls == [PAIR]


def test_report_has_exactly_the_documented_keys():
    report = check()
    assert set(report) == TOP_LEVEL_KEYS
    assert set(report["sources"]) == {"kraken", "binance"}
    assert set(report["sources"]["kraken"]) == SOURCE_KEYS
    assert set(report["sources"]["binance"]) == SOURCE_KEYS


# ===========================================================================
# B. The verdict table
# ===========================================================================
def test_two_fresh_agreeing_sources_are_OK():
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "68644.20000")),
        binance=quote_fetcher(make_quote("binance", "68656.96000000")),
    )
    assert report["verdict"] == OK
    assert report["reason"]
    assert report["sources"]["kraken"]["error"] is None
    assert report["sources"]["binance"]["error"] is None


def test_spread_over_the_threshold_is_DISAGREE():
    # 99.70 vs 100.30: diff 0.60 over mid 100 -> exactly 60 bps > 50.
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "99.70")),
        binance=quote_fetcher(make_quote("binance", "100.30")),
    )
    assert report["verdict"] == DISAGREE
    assert Decimal(report["spread_bps"]) == Decimal("60")


def test_spread_exactly_at_the_threshold_is_still_OK():
    # 99.75 vs 100.25: diff 0.50 over mid 100 -> exactly 50 bps, which does
    # not EXCEED the limit. Pinned because an off-by-one here silently turns
    # a passing quote into a blocked one, or the reverse.
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "99.75")),
        binance=quote_fetcher(make_quote("binance", "100.25")),
    )
    assert Decimal(report["spread_bps"]) == Decimal("50")
    assert report["verdict"] == OK


def test_a_source_older_than_the_limit_is_STALE_and_names_it():
    report = check(
        kraken=quote_fetcher(aged(61, "kraken")),
        binance=quote_fetcher(aged(0, "binance")),
    )
    assert report["verdict"] == STALE
    assert "kraken" in report["reason"]
    assert report["sources"]["kraken"]["age_seconds"] == 61


def test_a_source_exactly_at_the_age_limit_is_still_OK():
    report = check(
        kraken=quote_fetcher(aged(60, "kraken")),
        binance=quote_fetcher(aged(60, "binance")),
    )
    assert report["sources"]["kraken"]["age_seconds"] == 60
    assert report["verdict"] == OK


def test_one_failed_venue_is_SINGLE_SOURCE_and_the_survivor_is_still_reported():
    report = check(
        kraken=failing_fetcher("kraken", "timeout after 5.0s"),
        binance=quote_fetcher(make_quote("binance", "68656.96000000")),
    )
    assert report["verdict"] == SINGLE_SOURCE
    assert report["sources"]["binance"]["price"] == "68656.96000000"
    assert report["sources"]["kraken"]["price"] is None


def test_both_venues_failing_is_still_a_named_non_OK_verdict():
    report = check(
        kraken=failing_fetcher("kraken", "timeout after 5.0s"),
        binance=failing_fetcher("binance", "HTTP 503 Service Unavailable"),
    )
    assert report["verdict"] != OK
    assert "kraken" in report["reason"]
    assert "binance" in report["reason"]
    assert report["spread_bps"] is None


def test_a_dead_venue_outranks_a_stale_one():
    """Precedence SINGLE_SOURCE > STALE: with a venue missing there is nothing
    to cross-check, which is a worse answer than a slow one."""
    report = check(
        kraken=failing_fetcher("kraken", "timeout after 5.0s"),
        binance=quote_fetcher(aged(999, "binance")),
    )
    assert report["verdict"] == SINGLE_SOURCE


def test_a_stale_quote_outranks_a_disagreement():
    """Precedence STALE > DISAGREE: a spread computed from an old price is not
    evidence of disagreement, so it must not be reported as one."""
    report = check(
        kraken=quote_fetcher(aged(999, "kraken", "99.70")),
        binance=quote_fetcher(aged(0, "binance", "100.30")),
    )
    assert report["verdict"] == STALE
    assert Decimal(report["spread_bps"]) == Decimal("60")


# ===========================================================================
# C. Property 1 -- two disagreeing prices are NEVER blended into one number
# ===========================================================================
def test_disagreeing_prices_are_never_averaged_or_reduced_to_one():
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "99.70")),
        binance=quote_fetcher(make_quote("binance", "100.30")),
    )
    assert report["verdict"] == DISAGREE
    assert report["sources"]["kraken"]["price"] == "99.70"
    assert report["sources"]["binance"]["price"] == "100.30"
    # No top-level single price, mid, average or "best" to reach for.
    assert set(report) == TOP_LEVEL_KEYS
    blended = {"100.00", "100", "100.0"}
    assert report["sources"]["kraken"]["price"] not in blended
    assert report["sources"]["binance"]["price"] not in blended


def test_a_missing_source_never_produces_a_zero_spread():
    """spread_bps None, never 0 -- a 0 would read as perfect agreement, which
    is the exact lie this script exists to prevent."""
    report = check(
        kraken=failing_fetcher("kraken", "malformed body"),
        binance=quote_fetcher(make_quote("binance")),
    )
    assert report["spread_bps"] is None


# ===========================================================================
# D. Property 2 -- no price is ever emitted without its age
# ===========================================================================
@pytest.mark.parametrize(
    "kraken_age,kraken_price,binance_price,expected",
    [
        (0, "99.99", "100.01", OK),
        (0, "99.70", "100.30", DISAGREE),
        (999, "68644.20000", "68644.20000", STALE),
    ],
    ids=["ok", "disagree", "stale"],
)
def test_every_reported_price_carries_an_integer_age(
    kraken_age, kraken_price, binance_price, expected
):
    # Built inside the test, never in the decorator: a factory that runs at
    # collection time would turn this RED contract into a collection error.
    report = check(
        kraken=quote_fetcher(aged(kraken_age, "kraken", kraken_price)),
        binance=quote_fetcher(aged(0, "binance", binance_price)),
    )
    assert report["verdict"] == expected
    for name, entry in report["sources"].items():
        assert entry["price"] is not None, name
        assert type(entry["age_seconds"]) is int, name
        assert entry["fetched_at"] is not None, name


def test_an_age_that_cannot_be_established_is_stale_not_fresh():
    """fetched_at=None means we do not know when this price was true. Unknown
    age must never pass as fresh."""
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "68644.20000", None)),
        binance=quote_fetcher(make_quote("binance", "68644.20000")),
    )
    assert report["verdict"] == STALE
    assert "kraken" in report["reason"]
    assert report["sources"]["kraken"]["price"] == "68644.20000"
    assert report["sources"]["kraken"]["age_seconds"] is None


def test_a_naive_timestamp_is_stale_never_assumed_to_be_utc():
    """A datetime with no offset cannot be turned into an age without guessing
    a zone; guessing is how a two-hour-old price passes as fresh."""
    naive = datetime(2026, 8, 27, 12, 0, 0)
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "68644.20000", naive)),
        binance=quote_fetcher(make_quote("binance", "68644.20000")),
    )
    assert report["verdict"] == STALE
    assert "kraken" in report["reason"]


def test_a_timestamp_in_the_future_is_stale_never_eternally_fresh():
    """Clock skew must not produce a negative age: a future stamp would keep
    a frozen price looking fresh forever."""
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "68644.20000", NOW + timedelta(seconds=300))),
        binance=quote_fetcher(make_quote("binance", "68644.20000")),
    )
    assert report["verdict"] == STALE
    assert "kraken" in report["reason"]


def test_the_check_time_is_sampled_after_both_venues_have_answered():
    """Ages are measured against ``checked_at``. If that instant is taken
    BEFORE the fetches, every fresh quote lands a second in the future and the
    script calls its own good data STALE.

    This is not hypothetical: the live round-trip at the bottom of this file
    hit exactly that ("binance is stamped in the future (-1s): clock skew")
    while the contract was being written. Pinned here so it is caught offline.
    """
    order = []

    def watched(name):
        def fetch(pair):
            order.append(name)
            return make_quote(name, "68644.20000", NOW)

        return fetch

    def clock():
        order.append("clock")
        return NOW

    pc = _pc()
    report = pc.check_prices(
        pair=PAIR,
        fetchers={"kraken": watched("kraken"), "binance": watched("binance")},
        clock=clock,
        max_spread_bps=SPEC_MAX_SPREAD_BPS,
        max_age_seconds=SPEC_MAX_AGE_SECONDS,
    )
    assert order == ["kraken", "binance", "clock"]
    assert report["verdict"] == OK
    assert report["checked_at"] == NOW.isoformat()


def test_checked_at_is_timezone_aware():
    report = check()
    assert datetime.fromisoformat(report["checked_at"]).tzinfo is not None
    assert datetime.fromisoformat(report["sources"]["kraken"]["fetched_at"]).tzinfo is not None


# ===========================================================================
# E. Property 3 -- a non-OK verdict exits non-zero
# ===========================================================================
def test_an_OK_check_exits_zero(capsys):
    rc = run_cli(
        [],
        two_fetchers(make_quote("kraken", "99.99"), make_quote("binance", "100.01")),
    )
    assert rc == 0
    assert json.loads(capsys.readouterr().out)["verdict"] == OK


@pytest.mark.parametrize(
    "scenario,expected",
    [("disagree", DISAGREE), ("stale", STALE), ("dead", SINGLE_SOURCE)],
    ids=[DISAGREE, STALE, SINGLE_SOURCE],
)
def test_every_non_OK_verdict_exits_non_zero(scenario, expected, capsys):
    scenarios = {
        "disagree": two_fetchers(make_quote("kraken", "99.70"), make_quote("binance", "100.30")),
        "stale": two_fetchers(aged(999, "kraken"), aged(0, "binance")),
        "dead": {
            "kraken": failing_fetcher("kraken", "timeout after 5.0s"),
            "binance": quote_fetcher(make_quote("binance")),
        },
    }
    rc = run_cli([], scenarios[scenario])
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == expected
    assert rc != 0
    # A caller that only reads the process status must still be protected: an
    # exit code outside 1..255 is truncated by the OS and 256 becomes 0.
    assert 1 <= rc <= 255


def test_the_json_is_printed_even_when_the_verdict_is_bad(capsys):
    """The reason must reach the caller on the bad path too, not only on the
    good one -- a non-zero exit with an empty stdout is a silent failure."""
    rc = run_cli(
        [],
        {
            "kraken": failing_fetcher("kraken", "timeout after 5.0s"),
            "binance": quote_fetcher(make_quote("binance")),
        },
    )
    out = capsys.readouterr().out
    assert rc != 0
    report = json.loads(out)
    assert report["verdict"] == SINGLE_SOURCE
    assert report["reason"]


# ===========================================================================
# F. Property 4 -- SINGLE_SOURCE names the venue AND the failure
# ===========================================================================
@pytest.mark.parametrize(
    "reason_text,token",
    [
        ("timeout after 5.0s", "timeout"),
        ("HTTP 503 Service Unavailable", "503"),
        ("malformed body: Expecting value", "malformed"),
        ("missing field 'c' in result", "missing field"),
    ],
    ids=["timeout", "http-status", "malformed", "missing-field"],
)
def test_the_reason_names_both_the_venue_and_what_happened(reason_text, token):
    report = check(
        kraken=failing_fetcher("kraken", reason_text),
        binance=quote_fetcher(make_quote("binance")),
    )
    assert report["verdict"] == SINGLE_SOURCE
    assert "kraken" in report["reason"]
    assert token in report["reason"].lower()
    assert token in report["sources"]["kraken"]["error"].lower()


def test_source_error_carries_the_venue_and_the_reason_separately():
    pc = _pc()
    exc = pc.SourceError("binance", "HTTP 400 Invalid symbol.")
    assert exc.source == "binance"
    assert exc.reason == "HTTP 400 Invalid symbol."
    assert "binance" in str(exc)
    assert "400" in str(exc)


@pytest.mark.parametrize(
    "venue,fetcher_name,exc,token",
    [
        ("kraken", "fetch_kraken", TimeoutError("timed out"), "timeout"),
        (
            "kraken",
            "fetch_kraken",
            urllib.error.HTTPError("http://x", 503, "Service Unavailable", {}, None),
            "503",
        ),
        ("binance", "fetch_binance", TimeoutError("timed out"), "timeout"),
        (
            "binance",
            "fetch_binance",
            urllib.error.HTTPError("http://x", 400, "Bad Request", {}, None),
            "400",
        ),
    ],
    ids=["kraken-timeout", "kraken-503", "binance-timeout", "binance-400"],
)
def test_a_transport_failure_becomes_a_named_SourceError(venue, fetcher_name, exc, token):
    pc = _pc()
    fetcher = getattr(pc, fetcher_name)
    with pytest.raises(pc.SourceError) as caught:
        fetcher(PAIR, http_get=raising_http(exc), clock=lambda: NOW)
    assert caught.value.source == venue
    assert token in caught.value.reason.lower()


# ===========================================================================
# G. Property 5 -- money never round-trips through a binary float
# ===========================================================================
def test_a_price_with_more_digits_than_a_float_holds_survives_verbatim(capsys):
    """float("70123.456789012345678") loses digits. If a float is anywhere in
    the path, this string comes back changed."""
    exact = "70123.456789012345678"
    rc = run_cli(
        [], two_fetchers(make_quote("kraken", exact), make_quote("binance", exact))
    )
    report = json.loads(capsys.readouterr().out)
    assert rc == 0
    assert report["sources"]["kraken"]["price"] == exact
    assert report["sources"]["binance"]["price"] == exact


def test_no_float_survives_anywhere_in_the_emitted_json(capsys):
    run_cli([], two_fetchers(make_quote("kraken", "99.70"), make_quote("binance", "100.30")))
    report = json.loads(capsys.readouterr().out)
    assert list(_walk_floats(report)) == []
    assert isinstance(report["sources"]["kraken"]["price"], str)
    assert isinstance(report["spread_bps"], str)


def test_quote_price_is_a_decimal_not_a_float():
    pc = _pc()
    quote = pc.fetch_binance(
        PAIR, http_get=recording_http(BINANCE_OK_BODY), clock=lambda: NOW
    )
    assert isinstance(quote.price, Decimal)
    assert quote.price == Decimal("68656.96000000")


def test_a_difference_too_small_for_a_float_is_still_a_difference():
    """Both of these collapse to the same float64. Under Decimal the spread is
    tiny but real; under float it is exactly zero -- perfect agreement that
    never happened."""
    report = check(
        kraken=quote_fetcher(make_quote("kraken", "10000.00000000000000001")),
        binance=quote_fetcher(make_quote("binance", "10000.00000000000000002")),
    )
    assert Decimal(report["spread_bps"]) > 0
    assert report["verdict"] == OK


# ===========================================================================
# H. Property 6 -- a malformed venue answer is a named failure, never a zero
# ===========================================================================
@pytest.mark.parametrize(
    "fetcher_name,body,token",
    [
        # Truncated mid-stream: the classic half-read response.
        ("fetch_kraken", '{"error":[],"result":{"XXBTZEUR":{"c":["686', "malformed"),
        ("fetch_binance", '{"symbol":"BTCEUR","price":"6865', "malformed"),
        # HTTP 200 that is actually an error -- Kraken's real behaviour.
        ("fetch_kraken", '{"error":["EQuery:Unknown asset pair"]}', "unknown asset pair"),
        # Valid JSON, price field simply absent.
        ("fetch_kraken", '{"error":[],"result":{"XXBTZEUR":{}}}', "c"),
        ("fetch_binance", '{"symbol":"BTCEUR"}', "price"),
        # Present but unusable.
        ("fetch_binance", '{"symbol":"BTCEUR","price":null}', "price"),
        ("fetch_binance", '{"symbol":"BTCEUR","price":""}', "price"),
        # Zero is not a price.
        ("fetch_binance", '{"symbol":"BTCEUR","price":"0.00000000"}', "price"),
        ("fetch_binance", '{"symbol":"BTCEUR","price":"-1.00000000"}', "price"),
        # Empty result mapping: nothing to read, and nothing to invent.
        ("fetch_kraken", '{"error":[],"result":{}}', "result"),
    ],
    ids=[
        "kraken-truncated",
        "binance-truncated",
        "kraken-200-with-error-array",
        "kraken-no-c-field",
        "binance-no-price-field",
        "binance-null-price",
        "binance-empty-price",
        "binance-zero-price",
        "binance-negative-price",
        "kraken-empty-result",
    ],
)
def test_a_broken_body_is_a_named_failure_never_a_default(fetcher_name, body, token):
    pc = _pc()
    fetcher = getattr(pc, fetcher_name)
    with pytest.raises(pc.SourceError) as caught:
        fetcher(PAIR, http_get=recording_http(body), clock=lambda: NOW)
    assert token in caught.value.reason.lower()


# ===========================================================================
# I. The fetchers themselves: right venue, right symbol, honest stamp
# ===========================================================================
def test_kraken_is_asked_for_the_venues_own_symbol_at_the_venues_own_host():
    pc = _pc()
    http = recording_http(KRAKEN_OK_BODY)
    quote = pc.fetch_kraken(PAIR, http_get=http, clock=lambda: NOW)
    assert len(http.urls) == 1
    url = http.urls[0]
    assert "api.kraken.com" in url
    assert "EUR" in url
    assert "XBT" in url or "BTC" in url
    assert "BTC/EUR" not in url  # the canonical pair is translated, not pasted
    assert quote.source == "kraken"
    assert quote.price == Decimal("68644.20000")


def test_binance_is_asked_for_the_venues_own_symbol_at_the_public_data_host():
    pc = _pc()
    http = recording_http(BINANCE_OK_BODY)
    quote = pc.fetch_binance(PAIR, http_get=http, clock=lambda: NOW)
    assert len(http.urls) == 1
    url = http.urls[0]
    assert "data-api.binance.vision" in url
    assert "BTCEUR" in url
    assert quote.source == "binance"
    assert quote.price == Decimal("68656.96000000")


def test_kraken_result_key_is_read_from_the_response_not_from_the_request():
    """Kraken answers a request for XBTEUR under the key XXBTZEUR. Hard-coding
    the requested symbol as the lookup key is a guaranteed KeyError in prod."""
    pc = _pc()
    quote = pc.fetch_kraken(
        PAIR, http_get=recording_http(KRAKEN_OK_BODY), clock=lambda: NOW
    )
    assert quote.price == Decimal("68644.20000")


def test_kraken_stamps_receipt_time_after_the_body_arrives():
    """Neither venue timestamps its ticker, so receipt time is the only honest
    age -- and it must be taken AFTER the response lands, or a slow reply gets
    stamped younger than it is."""
    order = []

    def http_get(url, **kwargs):
        order.append("http")
        return KRAKEN_OK_BODY

    def clock():
        order.append("clock")
        return NOW

    pc = _pc()
    quote = pc.fetch_kraken(PAIR, http_get=http_get, clock=clock)
    assert order == ["http", "clock"]
    assert quote.fetched_at == NOW


# ===========================================================================
# J. The CLI surface
# ===========================================================================
def test_the_default_pair_is_the_one_the_owner_starts_on(capsys):
    run_cli([], two_fetchers(make_quote("kraken"), make_quote("binance")))
    assert json.loads(capsys.readouterr().out)["pair"] == "BTC/EUR"


def test_an_explicit_pair_is_echoed_and_passed_to_both_fetchers(capsys):
    kraken = quote_fetcher(make_quote("kraken"))
    binance = quote_fetcher(make_quote("binance"))
    run_cli(["--pair", "ETH/EUR"], {"kraken": kraken, "binance": binance})
    assert json.loads(capsys.readouterr().out)["pair"] == "ETH/EUR"
    assert kraken.calls == ["ETH/EUR"]
    assert binance.calls == ["ETH/EUR"]


def test_a_tighter_spread_limit_from_the_command_line_changes_the_verdict(capsys):
    fetchers = two_fetchers(make_quote("kraken", "99.99"), make_quote("binance", "100.01"))
    rc = run_cli(["--max-spread-bps", "1"], fetchers)
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == DISAGREE
    assert rc != 0


def test_a_tighter_age_limit_from_the_command_line_changes_the_verdict(capsys):
    fetchers = two_fetchers(aged(30, "kraken"), aged(0, "binance"))
    rc = run_cli(["--max-age-seconds", "10"], fetchers)
    report = json.loads(capsys.readouterr().out)
    assert report["verdict"] == STALE
    assert rc != 0


def test_stdout_is_one_json_document_and_nothing_else(capsys):
    """A caller pipes this into jq. Any banner, log line or second document
    breaks that, and breaks it silently."""
    run_cli([], two_fetchers(make_quote("kraken"), make_quote("binance")))
    out = capsys.readouterr().out
    assert json.loads(out)
    assert out.strip().startswith("{")
    assert out.strip().endswith("}")


# ===========================================================================
# K. Live round-trip against both real venues (unmassk-standards 34.5).
#    Deselect with -m "not live". A fixture of these responses is exactly how
#    a venue format change reaches production unnoticed, so nothing here is
#    stored: it is re-fetched every run.
# ===========================================================================
def _live_get(url):
    with urllib.request.urlopen(url, timeout=20) as response:  # noqa: S310 - fixed https URLs
        return response.read().decode("utf-8")


@pytest.mark.live
def test_live_the_two_venues_still_answer_in_the_shape_this_script_reads():
    """Independent of the implementation: proves the shape assumed above is
    the shape returned TODAY."""
    kraken = json.loads(_live_get("https://api.kraken.com/0/public/Ticker?pair=XBTEUR"))
    assert kraken["error"] == []
    assert len(kraken["result"]) == 1
    entry = next(iter(kraken["result"].values()))
    kraken_last = entry["c"][0]
    assert isinstance(kraken_last, str)
    assert Decimal(kraken_last) > 0

    binance = json.loads(
        _live_get("https://data-api.binance.vision/api/v3/ticker/price?symbol=BTCEUR")
    )
    assert binance["symbol"] == "BTCEUR"
    assert isinstance(binance["price"], str)
    assert Decimal(binance["price"]) > 0

    # The two venues are quoting the same asset in the same currency: nothing
    # else can put them this close. 5% is far wider than any real spread and
    # far narrower than a wrong pair.
    mid = (Decimal(kraken_last) + Decimal(binance["price"])) / 2
    assert abs(Decimal(kraken_last) - Decimal(binance["price"])) / mid < Decimal("0.05")


@pytest.mark.live
def test_live_the_script_end_to_end_against_both_real_venues(capsys):
    """The real wiring: real fetchers, real network, real verdict, real exit
    code. A DISAGREE or STALE here is a finding about the venues, not a bug in
    the test -- read the reason before touching anything."""
    pc = _pc()
    rc = pc.main(["--pair", PAIR])
    report = json.loads(capsys.readouterr().out)
    assert set(report) == TOP_LEVEL_KEYS
    assert report["verdict"] == OK, report["reason"]
    assert rc == 0
    for name in ("kraken", "binance"):
        entry = report["sources"][name]
        assert Decimal(entry["price"]) > 0, name
        assert type(entry["age_seconds"]) is int, name
        assert entry["age_seconds"] <= SPEC_MAX_AGE_SECONDS, name
        assert entry["error"] is None, name
    assert Decimal(report["spread_bps"]) < SPEC_MAX_SPREAD_BPS
    assert list(_walk_floats(report)) == []
